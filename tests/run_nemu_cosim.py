#!/usr/bin/env python3
"""NEMU 协同仿真驱动：用同一向量集驱动 NEMU 的三条点积指令并与金标准比对

流程：
  1) 读 tests/vectors/vdot_vectors.txt，按 mode 分组筛出"合法 + 写回"用例
     mode 0 = vdot.vv (INT8)，1 = vdot4x2.vv (INT4 打包双结果)，2 = vtdot.vv (BitNet 三值)
  2) 每种 mode 调用 tests/as/mini_asm.py 生成一个平面镜像（代码 + 数据）
  3) `nemu -b <img>` 运行，程序把结果以 8 位十六进制打到 UART
     INT8 每条 1 行（vd[31:0]）；双结果模式每条 2 行（r0 = vd[31:0]、r1 = vd[63:32]）
  4) 按行与金标准（ref_vdot.py）比对；若提供 RTL 导出文件，再做 NEMU vs RTL 直接 diff
  5) 边界自检：三种模式各做 vl=0 不写回 + 4 类非法配置触发 EX_II

用法：
  python3 tests/run_nemu_cosim.py --nemu .tools/nemu/build/riscv64-nemu-interpreter
  python3 tests/run_nemu_cosim.py --rtl-export docs/phase3/rtl_export.txt
"""
import argparse
import os
import re
import subprocess
import sys
from functools import partial

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "as"))
from mini_asm import build_image, UART_MMIO          # noqa: E402

VECTORS = os.path.join(HERE, "vectors", "vdot_vectors.txt")
HEXLINE = re.compile(r"^[0-9a-f]{8}$")
DYNLINE = re.compile(r"total guest instructions = ([0-9,]+)")

MODE_INT8 = 0
MODE_INT4X2 = 1
MODE_TERNARY = 2
MODE_NAMES = {MODE_INT8: "int8", MODE_INT4X2: "int4x2", MODE_TERNARY: "vtdot"}

# 边界自检：每种模式 vl=0 不得写回 vd；4 类非法配置各触发一次 EX_II
BOUNDARY_LO = 0x11223344
BOUNDARY_HI = 0x55667788
BOUNDARY_EXPECT_ILLEGAL = 4


def _emit_vdot(a, mode, vd, vs2, vs1, vm=1):
    """按 mode 发射对应点积指令。"""
    if mode == MODE_INT4X2:
        a.vdot4x2_vv(vd, vs2, vs1, vm=vm)
    elif mode == MODE_TERNARY:
        a.vtdot_vv(vd, vs2, vs1, vm=vm)
    else:
        a.vdot_vv(vd, vs2, vs1, vm=vm)


def build_boundary_program(data_off, ncases, verdict_reg=10):
    """NEMU 侧边界程序：三种模式各做 vl=0 与 4 类非法配置检查。

    每种模式输出 3 行：
      1) vl=0 执行后 vd[31:0]（必须等于哨兵低字，证明未写回）
      2) vl=0 执行后 vd[63:32]（必须等于哨兵高字，证明未写回）
      3) 该模式下非法配置触发的 EX_II 次数（必须等于 4）
    """
    import mini_asm as M
    a = M.Asm()
    a.auipc(M.S0, 0)
    a.addi(M.S0, M.S0, data_off)      # s0 = &hextab
    a.addi(M.S3, M.S0, 0)             # s3 = 字符表
    a.addi(M.S1, M.S0, 16)            # s1 = 哨兵（首条用例的 vs1）
    a.lui(M.T2, M.UART_MMIO >> 12)
    a.addi(M.T0, M.X0, 0x200)         # mstatus.VS = Initial
    a.csrs(M.CSR_MSTATUS, M.T0)
    a.la(M.T0, "trap")
    a.csrw(M.CSR_MTVEC, M.T0)
    a.addi(M.S4, M.X0, 0)             # s4 = 非法陷阱计数
    a.print_str("VBOUND\n")

    for mode in (MODE_INT8, MODE_INT4X2, MODE_TERNARY):
        # 1) vl=0：指令应正常退休但不写回（vd 保持哨兵）
        a.vsetvli(M.T1, M.X0, 0x00)   # e8, m1 -> VLMAX
        a.vle8_v(M.V3, M.S1, 0)       # v3 = 哨兵
        a.addi(M.T4, M.X0, 0)         # AVL = 0
        a.vsetvli(M.T1, M.T4, 0x00)   # vl = 0
        _emit_vdot(a, mode, M.V3, M.V1, M.V2)
        a.vsetvli(M.T1, M.X0, 0x18)   # e64, m1
        a.vmv_x_s(M.T0, M.V3)
        a.hex_print(M.T0)             # vd[31:0]
        a.print_str("\n")
        a.srli(M.T0, M.T0, 32)
        a.hex_print(M.T0)             # vd[63:32]
        a.print_str("\n")

        # 2) 四类非法配置：vm=0 / SEW=e16 / SEW=e64 / LMUL=m2
        for vtype, vm in ((0x00, 0), (0x08, 1), (0x18, 1), (0x01, 1)):
            a.vsetvli(M.T1, M.X0, vtype)
            _emit_vdot(a, mode, M.V3, M.V1, M.V2, vm=vm)
            a.vsetvli(M.T1, M.X0, 0x00)   # 恢复合法配置，供下一类使用
        a.hex_print(M.S4)
        a.print_str("\n")
        a.addi(M.S4, M.X0, 0)         # 清零，供下一种模式使用

    a.addi(verdict_reg, M.X0, 0)
    a.nemu_trap()

    # 陷阱处理：mepc += 4，计数 +1，返回
    a.label("trap")
    a.csrr(M.T0, M.CSR_MEPC)
    a.addi(M.T0, M.T0, 4)
    a.csrw(M.CSR_MEPC, M.T0)
    a.addi(M.S4, M.S4, 1)
    a.mret()
    return a


def run_boundary(nemu, image_path, max_instr):
    """在 NEMU 上跑边界程序，返回 (ok, note, lines, image_size)。"""
    import mini_asm as M
    sentinel = bytes([0x44, 0x33, 0x22, 0x11, 0x88, 0x77, 0x66, 0x55]) + bytes(8)
    img, _sym, _off = M.build_image([(sentinel, bytes(16))],
                                    program=build_boundary_program)
    os.makedirs(os.path.dirname(image_path), exist_ok=True)
    with open(image_path, "wb") as f:
        f.write(img)
    p = subprocess.run([nemu, "-b", "-I", str(max_instr), image_path],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    raw = p.stdout.decode("utf-8", "replace")
    lines = [ln for ln in raw.splitlines() if HEXLINE.match(ln)]

    per_mode = 3
    notes = []
    ok = True
    for mode in (MODE_INT8, MODE_INT4X2, MODE_TERNARY):
        base = mode * per_mode
        lo = lines[base] if base < len(lines) else "-"
        hi = lines[base + 1] if base + 1 < len(lines) else "-"
        ill = lines[base + 2] if base + 2 < len(lines) else "-"
        mode_ok = (lo == f"{BOUNDARY_LO:08x}"
                   and hi == f"{BOUNDARY_HI:08x}"
                   and ill == f"{BOUNDARY_EXPECT_ILLEGAL:08x}")
        ok = ok and mode_ok
        notes.append(f"{MODE_NAMES[mode]}={'PASS' if mode_ok else 'FAIL'}"
                     f"(vd={lo}/{hi}, traps={ill})")
    return ok, "; ".join(notes), lines, len(img)


def load_cases(path):
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = line.split()
            cid, vl_zero, vm, sew, lmul = p[0], int(p[1]), int(p[2]), int(p[3]), int(p[4])
            vs1, vs2, exp = p[5], p[6], p[7]
            mode = int(p[10]) if len(p) > 10 else MODE_INT8   # 兼容旧 10 列
            cases.append(dict(id=cid, vl_zero=vl_zero, vm=vm, sew=sew, lmul=lmul,
                              vs1=int(vs1, 16), vs2=int(vs2, 16), exp=int(exp, 16),
                              mode=mode))
    return cases


def select_runnable(cases):
    """程序固定用 e8/m1/vm=1 且 vl=VLMAX，故只包含合法且写回的用例。"""
    return [c for c in cases
            if c["vm"] == 1 and c["sew"] == 0 and c["lmul"] == 0
            and c["vl_zero"] == 0 and c["mode"] in MODE_NAMES]


def hex128_bytes(v):
    return (v & ((1 << 128) - 1)).to_bytes(16, "little")


def expected_words(c):
    """返回该用例的期望输出字列表：INT8 单结果，双结果模式 r0/r1。"""
    if c["mode"] == MODE_INT8:
        return [c["exp"] & 0xFFFFFFFF]
    return [c["exp"] & 0xFFFFFFFF, (c["exp"] >> 32) & 0xFFFFFFFF]


def run_mode(nemu, mode, cases, image_path, max_instr):
    """为单一 mode 生成镜像并运行，返回 (lines, raw, rc, img_size, data_off)。"""
    img, _sym, data_off = build_image(
        [(hex128_bytes(c["vs1"]), hex128_bytes(c["vs2"])) for c in cases],
        program=partial(_build_mode_program, mode=mode))
    os.makedirs(os.path.dirname(image_path), exist_ok=True)
    with open(image_path, "wb") as f:
        f.write(img)
    cmd = [nemu, "-b", "-I", str(max_instr), image_path]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    raw = p.stdout.decode("utf-8", "replace")
    lines = [ln for ln in raw.splitlines() if HEXLINE.match(ln)]
    return lines, raw, p.returncode, len(img), data_off


def _build_mode_program(data_off, ncases, mode=MODE_INT8):
    import mini_asm as M
    return M.build_program(data_off, ncases, mode=mode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nemu", default=".tools/nemu/build/riscv64-nemu-interpreter")
    ap.add_argument("--vectors", default=VECTORS)
    ap.add_argument("--image", default="build/nemu/vdot_cosim.bin")
    ap.add_argument("--boundary-image", default="build/nemu/vdot_boundary.bin")
    ap.add_argument("--no-boundary", action="store_true",
                    help="跳过 vl=0 / 非法配置的 NEMU 边界自检")
    ap.add_argument("--max-instr", default="2000000")
    ap.add_argument("--rtl-export", default=None,
                    help="tb_vdot 导出的逐用例结果（INT8 每行 1 个，双结果每行 2 个）")
    ap.add_argument("--out", default="docs/phase3/01_nemu_cosim.log")
    args = ap.parse_args()

    cases = load_cases(args.vectors)
    run = select_runnable(cases)
    groups = {m: [c for c in run if c["mode"] == m]
              for m in (MODE_INT8, MODE_INT4X2, MODE_TERNARY)}
    print(f"vectors total={len(cases)} runnable={len(run)} "
          + " ".join(f"{MODE_NAMES[m]}={len(groups[m])}"
                     for m in (MODE_INT8, MODE_INT4X2, MODE_TERNARY)))

    all_lines = []
    fails = []
    extras = 0
    rc_all = 0
    dyn_instr = "-"
    img_total = 0
    data_offs = {}

    for mode in (MODE_INT8, MODE_INT4X2, MODE_TERNARY):
        grp = groups[mode]
        if not grp:
            continue
        stem, ext = os.path.splitext(args.image)
        img_path = f"{stem}_{MODE_NAMES[mode]}{ext}"
        lines, raw, rc, size, data_off = run_mode(
            args.nemu, mode, grp, img_path, args.max_instr)
        img_total += size
        data_offs[mode] = data_off
        rc_all = rc_all or rc
        dyn = DYNLINE.search(raw)
        if dyn:
            dyn_instr = dyn.group(1)
        if "VDOT" not in raw:
            print(f"!! mode={MODE_NAMES[mode]} 未看到 UART banner，原始输出：")
            print(raw[:1200])
        print(f"image  {img_path}: {size} bytes, data_off={data_off}")

        # 按用例顺序消费输出行
        pos = 0
        for c in grp:
            words = expected_words(c)
            got = lines[pos:pos + len(words)]
            pos += len(words)
            if len(got) < len(words):
                fails.append((c["id"], mode, "缺输出",
                              "/".join(f"{w:08x}" for w in words), "-"))
                continue
            for w, g in zip(words, got):
                if int(g, 16) != w:
                    fails.append((c["id"], mode, "值不符", f"{w:08x}", g))
                    break
        extras += max(0, len(lines) - pos)
        all_lines.extend(lines)

    # 同步导出"写回用例"子集（按实际运行顺序），供 tb_vdot 结果导出对齐
    subset = os.path.join(os.path.dirname(args.image), "cosim_vectors.txt")
    with open(subset, "w", encoding="utf-8") as f:
        f.write("# write-back subset for tb_vdot result export "
                "(same order as NEMU images)\n")
        for mode in (MODE_INT8, MODE_INT4X2, MODE_TERNARY):
            for c in groups[mode]:
                f.write(f"{c['id']} {c['vl_zero']} {c['vm']} {c['sew']} {c['lmul']} "
                        f"{c['vs1']:032x} {c['vs2']:032x} {c['exp']:032x} 1 0 {mode}\n")
    print(f"subset {subset}: {len(run)} cases (feed to tb_vdot as argv[1])")

    if args.no_boundary:
        boundary_ok, boundary_note = True, "SKIP"
    else:
        boundary_ok, boundary_note, blines, _bsize = run_boundary(
            args.nemu, args.boundary_image, 200000)

    rtl_fail = 0
    rtl_note = "未提供"
    if args.rtl_export:
        with open(args.rtl_export, encoding="utf-8") as f:
            rtl = [ln.strip().lower() for ln in f if ln.strip() and not ln.startswith("#")]
        # RTL 导出是 32-bit 字/行，与 NEMU 行序一致
        n = min(len(rtl), len(all_lines))
        mism = [(i, rtl[i], all_lines[i]) for i in range(n) if rtl[i] != all_lines[i]]
        rtl_fail = len(mism) + abs(len(rtl) - len(all_lines))
        rtl_note = f"lines={len(rtl)}/nemu={len(all_lines)} mismatch={len(mism)}"
        for i, a, b in mism[:10]:
            print(f"RTL!=NEMU  #{i} rtl={a} nemu={b}")

    verdict = "PASS" if (not fails and extras == 0 and rtl_fail == 0
                         and boundary_ok and rc_all == 0) else "FAIL"
    report = []
    report.append("NEMU co-simulation (vdot family vs golden model)")
    report.append(f"nemu_binary      : {args.nemu}")
    report.append(f"image_prefix     : {args.image} ({img_total} bytes total)")
    report.append(f"image_data_off   : "
                  + " ".join(f"{MODE_NAMES[m]}={data_offs[m]}" for m in sorted(data_offs)))
    report.append(f"uart_mmio        : 0x{UART_MMIO:08x}")
    report.append(f"cases_expected   : {len(run)} "
                  + " ".join(f"{MODE_NAMES[m]}={len(groups[m])}"
                             for m in (MODE_INT8, MODE_INT4X2, MODE_TERNARY)))
    report.append(f"word_expected    : {sum(len(expected_words(c)) for c in run)}")
    report.append(f"word_observed    : {len(all_lines)}")
    report.append(f"cases_fail       : {len(fails)}")
    report.append(f"cases_extra      : {extras}")
    report.append(f"nemu_exit_code   : {rc_all}")
    report.append(f"nemu_dyn_instr   : {dyn_instr}")
    report.append(f"boundary_checks  : {boundary_note}")
    report.append(f"rtl_vs_nemu      : {rtl_note}")
    if fails:
        for cid, mode, why, exp, got in fails[:20]:
            report.append(f"  FAIL {cid} mode={MODE_NAMES[mode]} {why} "
                          f"exp={exp} got={got}")
    report.append(f"RESULT           : {verdict}")
    text = "\n".join(report) + "\n"

    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
