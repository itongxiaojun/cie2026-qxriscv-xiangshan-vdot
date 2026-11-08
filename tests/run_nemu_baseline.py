#!/usr/bin/env python3
"""基线实现（纯 RVV 组合指令）在 NEMU 上的等价性与指令数对比

背景：vdot.vv 单条指令完成 K=8 的 int8 点积。没有该指令时，编译器需用
RVV 1.0 已有的组合序列实现同样语义：

    vsext.vf2 (e8 -> e16)     x2
    vsext.vf2 (e16 -> e32)    x2
    vmul.vv   (e32, m2)       x1
    vredsum.vs(e32, m2)       x1
    ------------------------------
    共 6 条向量数据通路指令（另有 2 条 vle8.v 与若干 vsetvli 为两者共有的开销）

本脚本把该序列编成机器码，在 NEMU 上逐用例运行，验证输出与 vdot 的
金标准（tests/ref_vdot.py）完全一致，并输出指令数对比。

用法：
  python3 tests/run_nemu_baseline.py
  python3 tests/run_nemu_baseline.py --out docs/phase3/03_baseline_nemu.log
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "as"))
import mini_asm as M                                        # noqa: E402
from run_nemu_cosim import load_cases, select_runnable, hex128_bytes  # noqa: E402

VECTORS = os.path.join(HERE, "vectors", "vdot_vectors.txt")
HEXLINE = re.compile(r"^[0-9a-f]{8}$")


def build_program_baseline(data_off, ncases, verdict_reg=M.A0):
    """基线序列程序：每条用例 6 条向量数据通路指令。"""
    a = M.Asm()
    a.auipc(M.S0, 0)
    a.addi(M.S0, M.S0, data_off)
    a.addi(M.S3, M.S0, 0)              # s3 = &hextab
    a.addi(M.S1, M.S0, 16)             # s1 = &cases
    a.lui(M.T2, M.UART_MMIO >> 12)
    a.addi(M.T0, M.X0, 0x200)
    a.csrs(M.CSR_MSTATUS, M.T0)
    a.print_str("VBASE\n")
    if ncases <= 2047:
        a.addi(M.T5, M.X0, ncases)
    else:
        a.lui(M.T5, ncases >> 12)
        if ncases & 0xFFF:
            a.addi(M.T5, M.T5, ncases & 0xFFF)

    a.label("loop")
    a.vsetvli(M.T1, M.X0, 0x00)        # e8, m1  -> vl=16，用于字节装载
    a.vle8_v(M.V1, M.S1, 0)
    a.addi(M.T4, M.S1, 16)
    a.vle8_v(M.V3, M.T4, 0)
    a.vsetvli(M.T1, M.X0, 0x08)        # e16, m1 -> vl=8
    a.vsext_vf2(M.V2, M.V1)
    a.vsext_vf2(M.V6, M.V3)
    a.vsetvli(M.T1, M.X0, 0x11)        # e32, m2 -> vl=8
    a.vsext_vf2(M.V4, M.V2)
    a.vsext_vf2(M.V8, M.V6)
    a.vmul_vv(M.V4, M.V4, M.V8)
    a.vredsum_vs(M.V10, M.V4, M.V0)    # v0 为 0 号种子
    a.vsetvli(M.T1, M.X0, 0x10)        # e32, m1
    a.vmv_x_s(M.T0, M.V10)
    a.hex_print(M.T0)
    a.print_str("\n")
    a.addi(M.S1, M.S1, M.CASE_SIZE)
    a.addi(M.T5, M.T5, -1)
    a.bne(M.T5, M.X0, "loop")
    a.addi(verdict_reg, M.X0, 0)
    a.nemu_trap()
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nemu", default=".tools/nemu/build/riscv64-nemu-interpreter")
    ap.add_argument("--vectors", default=VECTORS)
    ap.add_argument("--image", default="build/nemu/vdot_baseline.bin")
    ap.add_argument("--max-instr", default="20000000")
    ap.add_argument("--out", default="docs/phase3/03_baseline_nemu.log")
    args = ap.parse_args()

    cases = load_cases(args.vectors)
    # 基线实现的是 INT8 语义，只与 mode=0 用例比对；INT4/三值不在本脚本范围。
    run = [c for c in select_runnable(cases) if c["mode"] == 0]
    print(f"vectors total={len(cases)} runnable={len(run)} (int8 only)")

    img, sym, data_off = M.build_image(
        [(hex128_bytes(c["vs1"]), hex128_bytes(c["vs2"])) for c in run],
        program=build_program_baseline)
    os.makedirs(os.path.dirname(args.image), exist_ok=True)
    with open(args.image, "wb") as f:
        f.write(img)
    print(f"image  {args.image}: {len(img)} bytes, data_off={data_off}")

    cmd = [args.nemu, "-b", "-I", str(args.max_instr), args.image]
    print("run    " + " ".join(cmd))
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    raw = p.stdout.decode("utf-8", "replace")
    lines = [ln for ln in raw.splitlines() if HEXLINE.match(ln)]
    dyn = re.search(r"total guest instructions = ([0-9,]+)", raw)
    dyn_instr = dyn.group(1) if dyn else "-"

    fails = []
    for i, c in enumerate(run):
        exp = c["exp"] & 0xFFFFFFFF
        if i >= len(lines):
            fails.append((i, c["id"], "缺输出", f"{exp:08x}", "-"))
            continue
        got = int(lines[i], 16)
        if got != exp:
            fails.append((i, c["id"], "值不符", f"{exp:08x}", f"{got:08x}"))
    extra = max(0, len(lines) - len(run))

    verdict = "PASS" if (not fails and extra == 0 and p.returncode == 0) else "FAIL"
    report = [
        "NEMU baseline (RVV composition) equivalence",
        f"nemu_binary      : {args.nemu}",
        f"image            : {args.image} ({len(img)} bytes)",
        "baseline_seq     : vsext.vf2 x4 + vmul.vv + vredsum.vs (e8->e16->e32)",
        "  vector_alu_ops : 6 / case",
        "  vdot_alu_ops   : 1 / case",
        "  alu_op_ratio   : 6.0x",
        f"cases_expected   : {len(run)}",
        f"cases_observed   : {len(lines)}",
        f"cases_fail       : {len(fails)}",
        f"cases_extra      : {extra}",
        f"nemu_exit_code   : {p.returncode}",
        f"nemu_dyn_instr   : {dyn_instr}",
    ]
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
