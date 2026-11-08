#!/usr/bin/env python3
"""生成 vdot 家族单元级测试向量（定向 + 随机 + 边界密集）

输出格式（空格分隔，每行一个用例）：
  id vl_zero vm sew lmul vs1_hex vs2_hex expected_vd_hex out_valid out_illegal mode

  vl_zero   : 1 表示 vl==0（不应写回）
  vm        : 1 表示无掩码（合法），0 表示掩码形态（应判非法）
  sew       : vtype 中 SEW 编码，0=e8（合法），1=e16，2=e32，3=e64
  lmul      : vtype 中 LMUL 编码，0=m1（合法），1=m2，2=m4，3=m8
  *_hex     : VLEN=128 bit 的无符号十六进制（32 个字符，MSB 在左）
  out_valid : 期望的写回有效
  out_illegal: 期望的非法指令标志
  mode      : 0=vdot(INT8)，1=vdot4x2(INT4 双结果)，2=vtdot(BitNet 三值双结果)，3=保留

期望值全部由 tests/ref_vdot.py 计算，不使用 RTL 输出。
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ref_vdot import VLEN, ref_vdot, ref_vdot4x2, ref_vtdot  # noqa: E402

HEXW = VLEN // 4

MODE_INT8 = 0
MODE_INT4X2 = 1
MODE_TERNARY = 2


def hex128(value: int) -> str:
    return f"{value & ((1 << VLEN) - 1):0{HEXW}x}"


def val(*bytes8: int) -> int:
    """由 8 个 lane 字节构造 128 bit 值（高 64 bit 为 0）。"""
    v = 0
    for i, b in enumerate(bytes8):
        v |= (b & 0xFF) << (8 * i)
    return v


def val16(*bytes16: int) -> int:
    """由 16 个 lane 字节构造完整 128 bit 值（三值模式用满寄存器）。"""
    v = 0
    for i, b in enumerate(bytes16):
        v |= (b & 0xFF) << (8 * i)
    return v


def pack_nibbles(nibs) -> int:
    """把 16 个 nibble 打包成 64 bit（低 nibble 在低位）。"""
    v = 0
    for i, n in enumerate(nibs):
        v |= (n & 0xF) << (4 * i)
    return v


def pack_codes(codes) -> int:
    """把 16 个 2-bit 三值码打包成 32 bit（code i 在 bits[2i+1:2i]）。"""
    v = 0
    for i, c in enumerate(codes):
        v |= (c & 0x3) << (2 * i)
    return v


def vd_expected(vs1: int, vs2: int) -> int:
    b1 = [(vs1 >> (8 * i)) & 0xFF for i in range(8)]
    b2 = [(vs2 >> (8 * i)) & 0xFF for i in range(8)]
    return ref_vdot(b1, b2)


def expected(vs1: int, vs2: int, mode: int) -> int:
    if mode == MODE_INT8:
        return vd_expected(vs1, vs2)
    if mode == MODE_INT4X2:
        return ref_vdot4x2(vs1, vs2)
    if mode == MODE_TERNARY:
        return ref_vtdot(vs1, vs2)
    # 保留模式：结果为 don't care（不写回）
    return 0


def emit(cases, cid, vs1, vs2, vl_zero=0, vm=1, sew=0, lmul=0,
         mode=MODE_INT8, note=""):
    legal = vm == 1 and sew == 0 and lmul == 0 and mode != 3
    write = 1 if (legal and not vl_zero) else 0
    illegal = 0 if legal else 1
    cases.append((cid, vl_zero, vm, sew, lmul, vs1, vs2,
                  expected(vs1, vs2, mode), write, illegal, mode, note))


def build_directed_int8():
    c = []
    # ---- 功能用例 ----
    emit(c, "TC-F01-positive", val(1, 2, 3, 4, 5, 6, 7, 8), val(8, 7, 6, 5, 4, 3, 2, 1))
    emit(c, "TC-F02-negative", val(0x80, 0xFF, 1, 2, 0xF0, 0x10, 0x7F, 0x81),
         val(2, 3, 0xFE, 0x80, 4, 0xF8, 1, 0x7F))
    emit(c, "TC-F03-mixed", val(127, 0x80, 0, 0xFF, 5, 0xFB, 0x55, 0xAA),
         val(0x81, 127, 9, 7, 0xF0, 5, 0xAA, 0x55))
    emit(c, "TC-F05-zeros", val(0, 0, 0, 0, 0, 0, 0, 0),
         val(0, 0, 0, 0, 0, 0, 0, 0))
    # ---- 边界用例 ----
    emit(c, "TC-B01-max-pos", val(*[127] * 8), val(*[127] * 8))
    emit(c, "TC-B02-max-neg", val(*[0x80] * 8), val(*[0x7F] * 8))
    emit(c, "TC-B03-19bit-edge", val(*[0x80] * 8), val(*[0x80] * 8))
    emit(c, "TC-B04-all-zero", val(*[0] * 8), val(*[0] * 8))
    emit(c, "TC-B05-cancel", val(*[1, 0xFF] * 4), val(*[1] * 8))
    emit(c, "TC-B06-lane0-only", val(5), val(7))
    emit(c, "TC-B07-80x7F", val(*[0x80, 0] * 4), val(*[0x7F, 0] * 4))
    emit(c, "TC-B08-max-mixed", val(*[0x80] * 8), val(*[0x80, 0x7F] * 4))
    # ---- 配置/异常用例 ----
    emit(c, "TC-V01-vl-zero", val(1, 2, 3, 4, 5, 6, 7, 8), val(1, 1, 1, 1, 1, 1, 1, 1), vl_zero=1)
    emit(c, "TC-V02-vl-one", val(1, 2, 3, 4, 5, 6, 7, 8), val(1, 2, 3, 4, 5, 6, 7, 8))
    emit(c, "TC-E01-vm0", val(1, 2, 3, 4, 5, 6, 7, 8), val(1, 1, 1, 1, 1, 1, 1, 1), vm=0)
    emit(c, "TC-E02-sew-e16", val(1, 2, 3, 4, 5, 6, 7, 8), val(1, 1, 1, 1, 1, 1, 1, 1), sew=1)
    emit(c, "TC-E03-lmul-m2", val(1, 2, 3, 4, 5, 6, 7, 8), val(1, 1, 1, 1, 1, 1, 1, 1), lmul=1)
    emit(c, "TC-E04-sew-e64", val(1, 2, 3, 4, 5, 6, 7, 8), val(1, 1, 1, 1, 1, 1, 1, 1), sew=3)
    return c


def build_directed_int4x2():
    c = []
    # ---- 功能用例：nibble 序、双流独立 ----
    emit(c, "TC-4F01-positive", pack_nibbles([1] * 16), pack_nibbles([1] * 16),
         mode=MODE_INT4X2)
    emit(c, "TC-4F02-negative", pack_nibbles([0x8, 0x7, 0xF, 0x1] * 4),
         pack_nibbles([0x2, 0x3, 0xE, 0x8] * 4), mode=MODE_INT4X2)
    emit(c, "TC-4F03-mixed", pack_nibbles([7, 0x8, 0, 0xF, 5, 0xB, 1, 0x9] * 2),
         pack_nibbles([0x1, 7, 9, 0xF, 0x0, 5, 0xA, 0x5] * 2), mode=MODE_INT4X2)
    emit(c, "TC-4F04-zero", 0, 0, mode=MODE_INT4X2)
    # ---- 边界用例 ----
    # 全 -8 x -8：每组 8*(64)=512
    emit(c, "TC-4B01-max-pos", pack_nibbles([0x8] * 16), pack_nibbles([0x8] * 16),
         mode=MODE_INT4X2)
    # 全 -8 x +7：每组 8*(-56)=-448
    emit(c, "TC-4B02-max-neg", pack_nibbles([0x8] * 16), pack_nibbles([0x7] * 16),
         mode=MODE_INT4X2)
    # 双流独立：低组全 0，高组全 -8 x -8
    emit(c, "TC-4B03-dual-independent", pack_nibbles([0] * 8 + [0x8] * 8),
         pack_nibbles([0] * 8 + [0x8] * 8), mode=MODE_INT4X2)
    # nibble 序：nibble0=1, nibble7=2, nibble8=3, nibble15=4，其余 0
    n1 = [0] * 16; n1[0] = 1; n1[7] = 2; n1[8] = 3; n1[15] = 4
    emit(c, "TC-4B04-nibble-order", pack_nibbles(n1), pack_nibbles([1] * 16),
         mode=MODE_INT4X2)
    # 正负抵消：nibble 交替 +7 / -7，乘 1
    emit(c, "TC-4B05-cancel", pack_nibbles([7, 0x9] * 8), pack_nibbles([1] * 16),
         mode=MODE_INT4X2)
    # ---- 配置/异常用例 ----
    emit(c, "TC-4E01-vm0", pack_nibbles([1] * 16), pack_nibbles([1] * 16),
         vm=0, mode=MODE_INT4X2)
    emit(c, "TC-4E02-sew-e16", pack_nibbles([1] * 16), pack_nibbles([1] * 16),
         sew=1, mode=MODE_INT4X2)
    emit(c, "TC-4E03-lmul-m2", pack_nibbles([1] * 16), pack_nibbles([1] * 16),
         lmul=1, mode=MODE_INT4X2)
    emit(c, "TC-4E04-vl-zero", pack_nibbles([1] * 16), pack_nibbles([1] * 16),
         vl_zero=1, mode=MODE_INT4X2)
    emit(c, "TC-4E05-mode-reserved", pack_nibbles([1] * 16), pack_nibbles([1] * 16),
         mode=3)
    return c


def build_directed_ternary():
    c = []
    a_mix = [0x7F, 0x80, 0x01, 0xFF, 0x05, 0xFB, 0x55, 0xAA] * 2
    # ---- 功能用例 ----
    emit(c, "TC-TF01-plus1", val16(*a_mix), pack_codes([1] * 16), mode=MODE_TERNARY)
    emit(c, "TC-TF02-minus1", val16(*a_mix), pack_codes([2] * 16), mode=MODE_TERNARY)
    emit(c, "TC-TF03-zero-code", val16(*a_mix), pack_codes([0] * 16), mode=MODE_TERNARY)
    emit(c, "TC-TF04-mixed-code",
         val16(*([1, 2, 3, 0] * 4)), pack_codes([1, 2, 3, 0] * 4), mode=MODE_TERNARY)
    emit(c, "TC-TF05-zero-act", 0, pack_codes([1, 2] * 8), mode=MODE_TERNARY)
    # ---- 边界用例 ----
    # a=-128，全 +1：每组 -1024（验证 9-bit 取反 + 12-bit 树）
    emit(c, "TC-TB01-neg128-plus1", val16(*([0x80] * 16)),
         pack_codes([1] * 16), mode=MODE_TERNARY)
    # a=-128，全 -1：每组 +1024（9-bit 取反溢出边界）
    emit(c, "TC-TB02-neg128-minus1", val16(*([0x80] * 16)),
         pack_codes([2] * 16), mode=MODE_TERNARY)
    # code=11 视为 0
    emit(c, "TC-TB03-code11-zero", val16(*([0x7F] * 16)),
         pack_codes([3] * 16), mode=MODE_TERNARY)
    # 双流独立：低组 -1024，高组 0
    emit(c, "TC-TB04-dual-independent", val16(*([0x80] * 8 + [0] * 8)),
         pack_codes([1] * 16), mode=MODE_TERNARY)
    # 正负抵消：a=1，code 交替 +1/-1
    emit(c, "TC-TB05-cancel", val16(*([1] * 16)),
         pack_codes([1, 2] * 8), mode=MODE_TERNARY)
    # ---- 配置/异常用例 ----
    emit(c, "TC-TE01-vm0", val16(*a_mix), pack_codes([1] * 16),
         vm=0, mode=MODE_TERNARY)
    emit(c, "TC-TE02-sew-e16", val16(*a_mix), pack_codes([1] * 16),
         sew=1, mode=MODE_TERNARY)
    emit(c, "TC-TE03-lmul-m2", val16(*a_mix), pack_codes([1] * 16),
         lmul=1, mode=MODE_TERNARY)
    emit(c, "TC-TE04-vl-zero", val16(*a_mix), pack_codes([1] * 16),
         vl_zero=1, mode=MODE_TERNARY)
    emit(c, "TC-TE05-mode-reserved", val16(*a_mix), pack_codes([1] * 16),
         mode=3)
    return c


def build_random_int8(n_random, n_corner, seed):
    rnd = random.Random(seed)
    c = []
    for i in range(n_random):
        b1 = [rnd.randrange(256) for _ in range(8)]
        b2 = [rnd.randrange(256) for _ in range(8)]
        emit(c, f"TC-R{i:04d}", val(*b1), val(*b2))
    corner = [0x00, 0x01, 0x7E, 0x7F, 0x80, 0x81, 0xFE, 0xFF]
    for i in range(n_corner):
        b1 = [rnd.choice(corner) for _ in range(8)]
        b2 = [rnd.choice(corner) for _ in range(8)]
        emit(c, f"TC-X{i:04d}", val(*b1), val(*b2))
    return c


def build_random_int4x2(n_random, n_corner, seed):
    rnd = random.Random(seed)
    c = []
    for i in range(n_random):
        emit(c, f"TC-4R{i:04d}", rnd.getrandbits(64), rnd.getrandbits(64),
             mode=MODE_INT4X2)
    corner = [0x0, 0x1, 0x7, 0x8, 0x9, 0xF]
    for i in range(n_corner):
        n1 = [rnd.choice(corner) for _ in range(16)]
        n2 = [rnd.choice(corner) for _ in range(16)]
        emit(c, f"TC-4X{i:04d}", pack_nibbles(n1), pack_nibbles(n2),
             mode=MODE_INT4X2)
    return c


def build_random_ternary(n_random, n_corner, seed):
    rnd = random.Random(seed)
    c = []
    for i in range(n_random):
        emit(c, f"TC-TR{i:04d}", rnd.getrandbits(128), rnd.getrandbits(32),
             mode=MODE_TERNARY)
    ac = [0x00, 0x01, 0x7F, 0x80, 0x81, 0xFF]
    for i in range(n_corner):
        a = [rnd.choice(ac) for _ in range(16)]
        codes = [rnd.randrange(4) for _ in range(16)]
        emit(c, f"TC-TX{i:04d}", val16(*a), pack_codes(codes),
             mode=MODE_TERNARY)
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="tests/vectors/vdot_vectors.txt")
    ap.add_argument("--random", type=int, default=1000, help="INT8 随机用例数")
    ap.add_argument("--corner", type=int, default=500, help="INT8 边界密集用例数")
    ap.add_argument("--int4-random", type=int, default=500, help="INT4 随机用例数")
    ap.add_argument("--int4-corner", type=int, default=250, help="INT4 边界密集用例数")
    ap.add_argument("--tern-random", type=int, default=500, help="三值随机用例数")
    ap.add_argument("--tern-corner", type=int, default=250, help="三值边界密集用例数")
    ap.add_argument("--seed", type=int, default=20261027)
    args = ap.parse_args()

    cases = []
    cases += build_directed_int8()
    cases += build_random_int8(args.random, args.corner, args.seed)
    cases += build_directed_int4x2()
    cases += build_random_int4x2(args.int4_random, args.int4_corner, args.seed + 1)
    cases += build_directed_ternary()
    cases += build_random_ternary(args.tern_random, args.tern_corner, args.seed + 2)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(f"# vdot family unit-level test vectors, VLEN={VLEN}, OUT_W=32\n")
        f.write(f"# generated by tests/gen_vectors.py, seed={args.seed}\n")
        f.write("# id vl_zero vm sew lmul vs1_hex vs2_hex expected_vd_hex "
                "out_valid out_illegal mode\n")
        for cid, vl0, vm, sew, lmul, vs1, vs2, exp, wr, ill, mode, _ in cases:
            f.write(f"{cid} {vl0} {vm} {sew} {lmul} {hex128(vs1)} {hex128(vs2)} "
                    f"{hex128(exp)} {wr} {ill} {mode}\n")

    n_write = sum(1 for c in cases if c[8] == 1)
    n_illegal = sum(1 for c in cases if c[9] == 1)
    by_mode = {m: sum(1 for c in cases if c[10] == m) for m in (0, 1, 2, 3)}
    print(f"vectors written: {args.out}")
    print(f"  total={len(cases)} write={n_write} illegal={n_illegal} "
          f"vl_zero={sum(1 for c in cases if c[1] == 1)}")
    print(f"  int8={by_mode[0]} int4x2={by_mode[1]} ternary={by_mode[2]} "
          f"reserved={by_mode[3]}")


if __name__ == "__main__":
    main()
