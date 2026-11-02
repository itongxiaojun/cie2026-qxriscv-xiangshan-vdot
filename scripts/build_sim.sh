#!/usr/bin/env bash
# 构建 VDot 单元级仿真（Verilator）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -z "${VERILATOR:-}" ]; then
  if [ -x "$ROOT/.tools/verilator-inst/bin/verilator" ]; then
    VERILATOR="$ROOT/.tools/verilator-inst/bin/verilator"
  elif [ -x "$ROOT/.tools/verilator/bin/verilator" ]; then
    # 本地源码树直接使用（未执行 make install，仅缺少 man page 生成）
    export VERILATOR_ROOT="$ROOT/.tools/verilator"
    VERILATOR="$VERILATOR_ROOT/bin/verilator"
  else
    VERILATOR="verilator"
  fi
fi

echo "[build] VERILATOR = $VERILATOR"
"$VERILATOR" --version

mkdir -p "$ROOT/build"

# 构建产物会写死生成时的绝对路径。若工作区被移动/迁移，旧的 obj_dir 会导致
# make 找不到源文件（stat: ... 权限不够 / 没有规则可制作目标）。检测到路径不符即清理重建。
if [ -d "$ROOT/build/obj_dir" ] && ! grep -q "$ROOT/tests/tb/tb_vdot.cpp" \
      "$ROOT/build/obj_dir/VVDot.mk" 2>/dev/null; then
  echo "[build] 检测到陈旧构建产物（指向其它工作目录），清理后重建"
  rm -rf "$ROOT/build/obj_dir"
fi

"$VERILATOR" --cc --exe --build -j "$(nproc)" --assert --trace \
  --top-module VDot \
  -Mdir "$ROOT/build/obj_dir" \
  -o tb_vdot \
  -CFLAGS "-O2 -std=c++17" \
  "$ROOT/rtl/verilog/VDot.v" \
  "$ROOT/tests/tb/tb_vdot.cpp"

echo "[build] OK: $ROOT/build/obj_dir/tb_vdot"
