#!/usr/bin/env bash
# 阶段二 · 香山昆明湖 V2 emu 汇编用例构建（RV64GCV 裸机镜像）
# 用法: bash tests/phase2/xs_emu/build.sh [输出目录，默认 build/phase2/xs_emu]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OUT="${1:-$ROOT/build/phase2/xs_emu}"
CC="${RISCV_CC:-$ROOT/.tools/riscv/bin/riscv-none-elf-gcc}"
OBJCOPY="${RISCV_OBJCOPY:-$ROOT/.tools/riscv/bin/riscv-none-elf-objcopy}"

mkdir -p "$OUT"

FLAGS="-march=rv64gcv -mabi=lp64d -nostdlib -nostartfiles -fno-pic -mcmodel=medany -T $ROOT/tests/phase1/link.ld"

for name in vdot_directed vdot_illegal; do
  "$CC" $FLAGS -o "$OUT/$name.elf" "$ROOT/tests/phase2/xs_emu/$name.S"
  "$OBJCOPY" -O binary "$OUT/$name.elf" "$OUT/$name.bin"
done

# U-04 性能对照：同一骨架的四个内核（0=空循环 1=vdot 2=标准RVV 3=标量）
# 性能日志统一使用 PERF_NITER=2000（见 docs/phase3/perf_analysis.md §6.1）；
# 源码默认 20000 仅用于单独手工实验，构建产物必须显式固定为 2000 以保证可复现。
PERF_NITER="${PERF_NITER:-2000}"
for k in 0 1 2 3; do
  case $k in
    0) name=perf_empty ;;
    1) name=perf_vdot ;;
    2) name=perf_rvv ;;
    3) name=perf_scalar ;;
  esac
  "$CC" $FLAGS -DPERF_KERNEL=$k -DPERF_NITER=$PERF_NITER \
    -o "$OUT/$name.elf" "$ROOT/tests/phase2/xs_emu/vdot_perf.S"
  "$OBJCOPY" -O binary "$OUT/$name.elf" "$OUT/$name.bin"
done

ls -l "$OUT"/*.bin
