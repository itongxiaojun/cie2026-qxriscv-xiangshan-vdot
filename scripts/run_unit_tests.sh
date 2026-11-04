#!/usr/bin/env bash
# vdot 单元级回归：模型自检 -> 向量生成 -> 三方模型交叉比对 -> 构建 -> 运行 -> 代码覆盖率
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="docs/phase2/logs"
mkdir -p "$LOG" build docs/phase2/waveform

VERILATOR="$(command -v verilator || true)"
[ -x .tools/verilator/bin/verilator ] && VERILATOR=".tools/verilator/bin/verilator"
VERILATOR_COV="$(command -v verilator_coverage || true)"
[ -x .tools/verilator/bin/verilator_coverage ] && VERILATOR_COV=".tools/verilator/bin/verilator_coverage"

echo "== [1/6] Python 参考模型自检 =="
python3 tests/ref_vdot.py 2>&1 | tee "$LOG/00_ref_model_selfcheck.log"

echo "== [2/6] 生成测试向量 =="
python3 tests/gen_vectors.py -o tests/vectors/vdot_vectors.txt 2>&1 | tee "$LOG/01_gen_vectors.log"

echo "== [3/6] C 参考模型（NEMU-ready）自检与交叉比对 =="
gcc -O2 -std=c11 -Wall -Wextra -o build/vdot_ref tests/model/vdot_ref.c 2>&1 | tee "$LOG/04_c_model_build.log"
./build/vdot_ref --selfcheck 2>&1 | tee "$LOG/05_c_model_selfcheck.log"
./build/vdot_ref tests/vectors/vdot_vectors.txt 2>&1 | tee "$LOG/06_c_model_crosscheck.log"

echo "== [4/6] 构建仿真 =="
bash scripts/build_sim.sh 2>&1 | tee "$LOG/02_build.log"

echo "== [5/6] 运行 RTL 单元测试（同时导出前 400 周期波形）=="
set +e
./build/obj_dir/tb_vdot tests/vectors/vdot_vectors.txt docs/phase2/waveform/vdot_unit.vcd 2>&1 | tee "$LOG/03_unit_test.log"
rc=${PIPESTATUS[0]}
set -e

echo "[run] exit code = $rc"

echo "== [6/6] 行覆盖率（Verilator --coverage-line，阈值 1）=="
if [ -n "$VERILATOR_COV" ]; then
  rm -rf build/obj_cov build/cov_line_annotated
  export VERILATOR_ROOT="$ROOT/.tools/verilator"
  "$VERILATOR" --cc --exe --build -j "$(nproc)" --coverage-line --assert --trace \
    --top-module VDot -Mdir build/obj_cov -o tb_cov \
    -CFLAGS "-O2 -std=c++17" \
    rtl/verilog/VDot.v tests/tb/tb_vdot.cpp > "$LOG/07_coverage_build.log" 2>&1
  ( cd build/obj_cov && ./tb_cov "$ROOT/tests/vectors/vdot_vectors.txt" - ) \
    > "$LOG/07_coverage_run.log" 2>&1
  "$VERILATOR_COV" --annotate build/cov_line_annotated --annotate-min 1 \
    build/obj_cov/coverage.dat 2>&1 | tee "$LOG/07_coverage.log"
else
  echo "coverage: SKIP（未找到 verilator_coverage）" | tee "$LOG/07_coverage.log"
  rc=1
fi

exit "$rc"
