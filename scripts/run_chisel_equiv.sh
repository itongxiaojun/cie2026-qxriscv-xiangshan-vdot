#!/usr/bin/env bash
# Chisel 版 RTL 等价性回归：
#   rtl/chisel/VDotCore.sv 是 rtl/chisel/VDot.scala 经 mill + firtool 生成的 SystemVerilog，
#   rtl/chisel/VDotWrap.v 把端口映射为与 rtl/verilog/VDot.v 相同的外部接口，
#   复用同一测试台与同一 3047 条三模式向量，验证两版实现功能一致。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="docs/phase2/logs"
mkdir -p "$LOG" build

VERILATOR="$(command -v verilator || true)"
[ -x .tools/verilator/bin/verilator ] && VERILATOR=".tools/verilator/bin/verilator"

echo "== Chisel 生成 RTL 等价性回归 =="
echo "[chisel] VERILATOR = $VERILATOR"

rm -rf build/obj_chisel
"$VERILATOR" --cc --exe --build -j "$(nproc)" --assert --trace \
  --top-module VDot \
  -Mdir build/obj_chisel \
  -o tb_chisel \
  -CFLAGS "-O2 -std=c++17" \
  rtl/chisel/VDotWrap.v rtl/chisel/VDotCore.sv tests/tb/tb_vdot.cpp \
  2>&1 | tee "$LOG/08_chisel_build.log"

./build/obj_chisel/tb_chisel tests/vectors/vdot_vectors.txt - \
  2>&1 | tee "$LOG/09_chisel_equiv.log"
