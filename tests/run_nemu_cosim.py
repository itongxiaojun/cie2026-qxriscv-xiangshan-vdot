#!/usr/bin/env python3
"""NEMU 协同仿真驱动：用同一向量集驱动 NEMU 的 vdot.vv 实现并与金标准比对

流程：
  1) 读 tests/vectors/vdot_vectors.txt，筛出"合法 + 写回"用例
  2) 调用 tests/as/mini_asm.py 生成平面镜像（代码 + 数据）
  3) `nemu -b <img>` 运行，程序把每条 vdot 的 vd[31:0] 以 8 位十六进制打到 UART
  4) 按行与金标准（ref_vdot.py）比对；若提供 RTL 导出文件，再做 NEMU vs RTL 直接 diff
  5) 边界自检：vl=0 不写回，vm=0/e16/e64/m2 四类非法配置各触发一次 EX_II

用法：
  python3 tests/run_nemu_cosim.py --nemu .tools/nemu/build/riscv64-nemu-interpreter
  python3 tests/run_nemu_cosim.py --rtl-export docs/phase3/rtl_export.txt
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "as"))
from mini_asm import build_image, UART_MMIO          # noqa: E402

VECTORS = os.path.join(HERE, "vectors", "vdot_vectors.txt")
HEXLINE = re.compile(r"^[0-9a-f]{8}$")
DYNLINE = re.compile(r"total guest instructions = ([0-9,]+)")

# 边界自检：vl=0 不得写回 vd；4 类非法配置各触发一次 EX_II
BOUNDARY_SENTINEL = 0x11223344
BOUNDARY_EXPECT_ILLEGAL = 4


def build_boundary_program(data_off, ncases, verdict_reg=10):
    """NEMU 侧边界程序：在数据区首条用例位置放 vd 的哨兵值。

    输出两行十六进制：
      1) vl=0 执行 vdot 后 vd[31:0]（必须等于哨兵，证明未写回）
      2) 非法配置触发的 EX_II 次数（必须等于 BOUNDARY_EXPECT_ILLEGAL）
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

    # 1) vl=0：vdot 应正常退休但不写回
    a.vsetvli(M.T1, M.X0, 0x00)       # e8, m1 -> VLMAX
    a.vle8_v(M.V3, M.S1, 0)           # v3 = 哨兵
    a.addi(M.T4, M.X0, 0)             # AVL = 0
    a.vsetvli(M.T1, M.T4, 0x00)       # vl = 0
    a.vdot_vv(M.V3, M.V1, M.V2)
    a.vsetvli(M.T1, M.X0, 0x10)       # e32, m1
    a.vmv_x_s(M.T0, M.V3)
    a.hex_print(M.T0)
    a.print_str("\n")

    # 2) 四类非法配置：vm=0 / SEW=e16 / SEW=e64 / LMUL=m2
    for vtype, vm in ((0x00, 0), (0x08, 1), (0x18, 1), (0x01, 1)):
        a.vsetvli(M.T1, M.X0, vtype)
        a.vdot_vv(M.V3, M.V1, M.V2, vm=vm)
        a.vsetvli(M.T1, M.X0, 0x00)   # 恢复合法配置，供下一类使用
    a.hex_print(M.S4)
    a.print_str("\n")

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
    """在 NEMU 上跑边界程序，返回 (vl0_ok, illegal_ok, lines, image_size)。"""
    import mini_asm as M
    sentinel = bytes([0x44, 0x33, 0x22, 0x11]) + bytes(12)
    img, _sym, _off = M.build_image([(sentinel, bytes(16))],
                                    program=build_boundary_program)
    os.makedirs(os.path.dirname(image_path), exist_ok=True)
    with open(image_path, "wb") as f:
        f.write(img)
    p = subprocess.run([nemu, "-b", "-I", str(max_instr), image_path],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    raw = p.stdout.decode("utf-8", "replace")
    lines = [ln for ln in raw.splitlines() if HEXLINE.match(ln)]
    vl0_ok = len(lines) >= 1 and lines[0] == f"{BOUNDARY_SENTINEL:08x}"
    illegal_ok = (len(lines) >= 2
                  and lines[1] == f"{BOUNDARY_EXPECT_ILLEGAL:08x}")
    return vl0_ok, illegal_ok, lines, len(img)


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
            cases.append(dict(id=cid, vl_zero=vl_zero, vm=vm, sew=sew, lmul=lmul,
                              vs1=int(vs1, 16), vs2=int(vs2, 16), exp=int(exp, 16)))
    return cases


def select_runnable(cases):
    """程序固定用 e8/m1/vm=1 且 vl=VLMAX，故只包含合法且写回的用例。"""
    return [c for c in cases
            if c["vm"] == 1 and c["sew"] == 0 and c["lmul"] == 0 and c["vl_zero"] == 0]


def hex128_bytes(v):
    return (v & ((1 << 128) - 1)).to_bytes(16, "little")


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
                    help="tb_vdot 导出的逐用例 128 bit 结果（每行一个）")
    ap.add_argument("--out", default="docs/phase3/01_nemu_cosim.log")
    args = ap.parse_args()

    cases = load_cases(args.vectors)
    run = select_runnable(cases)
    print(f"vectors total={len(cases)} runnable={len(run)}")

    img, sym, data_off = build_image(
        [(hex128_bytes(c["vs1"]), hex128_bytes(c["vs2"])) for c in run])
    os.makedirs(os.path.dirname(args.image), exist_ok=True)
    with open(args.image, "wb") as f:
        f.write(img)
    print(f"image  {args.image}: {len(img)} bytes, data_off={data_off}, "
          f"uart=0x{UART_MMIO:08x}")

    # 同步导出"写回用例"子集，保证 tb_vdot 的用例顺序与 NEMU 镜像完全一致
    subset = os.path.join(os.path.dirname(args.image), "cosim_vectors.txt")
    with open(subset, "w", encoding="utf-8") as f:
        f.write("# write-back subset for tb_vdot result export (same order as NEMU image)\n")
        for c in run:
            f.write(f"{c['id']} {c['vl_zero']} {c['vm']} {c['sew']} {c['lmul']} "
                    f"{c['vs1']:032x} {c['vs2']:032x} {c['exp']:032x} 1 0\n")
    print(f"subset {subset}: {len(run)} cases (feed to tb_vdot as argv[1])")

    cmd = [args.nemu, "-b", "-I", str(args.max_instr), args.image]
    print("run    " + " ".join(cmd))
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    raw = p.stdout.decode("utf-8", "replace")
    dyn = DYNLINE.search(raw)
    dyn_instr = dyn.group(1) if dyn else "-"

    lines = [ln for ln in raw.splitlines() if HEXLINE.match(ln)]
    if "VDOT" not in raw:
        print("!! 未看到 UART banner 'VDOT'，UART 通路可能异常，原始输出如下：")
        print(raw[:2000])
    print(f"nemu exit={p.returncode} results={len(lines)}")

    fails = []
    for i, c in enumerate(run):
        if i >= len(lines):
            fails.append((i, c["id"], "缺输出", hex(c["exp"] & 0xFFFFFFFF), "-"))
            continue
        got = int(lines[i], 16)
        exp = c["exp"] & 0xFFFFFFFF
        if got != exp:
            fails.append((i, c["id"], "值不符", f"{exp:08x}", f"{got:08x}"))

    extra = max(0, len(lines) - len(run))

    if args.no_boundary:
        boundary_ok, boundary_note = True, "SKIP"
    else:
        vl0_ok, ill_ok, blines, _bsize = run_boundary(
            args.nemu, args.boundary_image, 200000)
        boundary_ok = vl0_ok and ill_ok
        ill_count = blines[1] if len(blines) >= 2 else "-"
        boundary_note = (f"vl0={'PASS' if vl0_ok else 'FAIL'}"
                         f"(vd={blines[0] if blines else '-'}) "
                         f"illegal={'PASS' if ill_ok else 'FAIL'}"
                         f"(traps={ill_count}, expect={BOUNDARY_EXPECT_ILLEGAL})")

    rtl_fail = 0
    rtl_note = "未提供"
    if args.rtl_export:
        with open(args.rtl_export, encoding="utf-8") as f:
            rtl = [ln.strip().lower() for ln in f if ln.strip() and not ln.startswith("#")]
        n = min(len(rtl), len(lines))
        mism = [(i, rtl[i], lines[i]) for i in range(n) if rtl[i][-8:] != lines[i]]
        rtl_fail = len(mism) + abs(len(rtl) - len(lines))
        rtl_note = f"lines={len(rtl)}/nemu={len(lines)} mismatch={len(mism)}"
        for i, a, b in mism[:10]:
            print(f"RTL!=NEMU  #{i} rtl={a} nemu={b}")

    verdict = "PASS" if (not fails and extra == 0 and rtl_fail == 0
                         and boundary_ok and p.returncode == 0) else "FAIL"
    report = []
    report.append("NEMU co-simulation (vdot.vv vs golden model)")
    report.append(f"nemu_binary      : {args.nemu}")
    report.append(f"image            : {args.image} ({len(img)} bytes)")
    report.append(f"uart_mmio        : 0x{UART_MMIO:08x}")
    report.append(f"cases_expected   : {len(run)}")
    report.append(f"cases_observed   : {len(lines)}")
    report.append(f"cases_fail       : {len(fails)}")
    report.append(f"cases_extra      : {extra}")
    report.append(f"nemu_exit_code   : {p.returncode}")
    report.append(f"nemu_dyn_instr   : {dyn_instr}")
    report.append(f"boundary_checks  : {boundary_note}")
    report.append(f"rtl_vs_nemu      : {rtl_note}")
    if fails:
        for i, cid, why, exp, got in fails[:20]:
            report.append(f"  FAIL #{i} {cid} {why} exp={exp} got={got}")
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
