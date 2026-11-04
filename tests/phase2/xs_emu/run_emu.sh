#!/usr/bin/env bash
# 阶段二 · 在香山昆明湖 V2 emu（Verilator）上运行 vdot 汇编用例（含 difftest）
#
# 用法: bash tests/phase2/xs_emu/run_emu.sh [日志目录，默认 docs/phase2/logs]
# 依赖: build/xs-work/XiangShan/build/emu 已构建；NEMU .so 参考模型存在
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
XS="$ROOT/build/xs-work/XiangShan"
EMU="$XS/build/emu"
DIFF="${NEMU_SO:-$ROOT/.tools/nemu/build/riscv64-nemu-interpreter-so}"
BIN="$ROOT/build/phase2/xs_emu"
LOG="${1:-$ROOT/docs/phase2/logs}"
TMO="${EMU_TIMEOUT:-1800}"

mkdir -p "$LOG"
[ -x "$EMU" ]  || { echo "缺少 emu: $EMU"; exit 1; }
[ -f "$DIFF" ] || { echo "缺少 NEMU .so: $DIFF"; exit 1; }

for name in vdot_directed vdot_illegal perf_empty perf_vdot perf_rvv perf_scalar; do
  echo "===== $name ====="
  # 说明：本 emu 的 difftest 在“陷阱指令”上存在参考模型侧的状态滞后——DUT 提交
  # mepc/mcause/mstatus 后，NEMU 参考模型在同一比较点仍为旧值，导致 CSR 误报
  # （用一条普通非法指令 `.word 0` 即可复现，见 logs/xs_emu_baseline_illegal_difftest.log）。
  # 因此非法配置用例改为架构级自检（--no-diff，程序内统计 5 个 illegal trap）。
  if [ "$name" = "vdot_illegal" ]; then
    opt="--no-diff"
  else
    opt="--diff=$DIFF"
  fi
  ( cd "$XS" && timeout "$TMO" "$EMU" -i "$BIN/$name.bin" "$opt" ) \
    > "$LOG/xs_emu_$name.log" 2>&1
  rc=$?
  echo "EXIT=$rc"
  grep -aE "HIT GOOD TRAP|HIT BAD TRAP|instrCnt|PERF result|DIRECTED|ILLEGAL|mismatch" \
    "$LOG/xs_emu_$name.log" | sed 's/\x1b\[[0-9;]*m//g' | tail -8
done
