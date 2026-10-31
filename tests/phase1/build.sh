#!/usr/bin/env bash
# 阶段一：编译 hello / vadd 裸机测试镜像（RISC-V RV64GCV）
# 用法: bash tests/phase1/build.sh [输出目录，默认 build/phase1]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$ROOT/build/phase1}"
CC="${RISCV_CC:-riscv-none-elf-gcc}"
OBJCOPY="${RISCV_OBJCOPY:-riscv-none-elf-objcopy}"

mkdir -p "$OUT"

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -n "$IP" ] || IP="127.0.0.1"
cat > "$OUT/ip_addr.h" <<EOF
#define IP_ADDR "IP address: $IP"
EOF

FLAGS="-march=rv64gcv -mabi=lp64d -nostdlib -nostartfiles -fno-pic -mcmodel=medany -T $ROOT/tests/phase1/link.ld"

"$CC" $FLAGS -I"$OUT" -o "$OUT/hello.elf" "$ROOT/tests/phase1/hello.S"
"$OBJCOPY" -O binary "$OUT/hello.elf" "$OUT/hello.bin"

"$CC" $FLAGS -o "$OUT/vadd.elf" "$ROOT/tests/phase1/vadd.S"
"$OBJCOPY" -O binary "$OUT/vadd.elf" "$OUT/vadd.bin"

echo "IP_ADDR = $IP"
ls -l "$OUT"/*.bin
