#!/usr/bin/env python3
"""vdot 家族参考模型（Golden Model）

覆盖三条指令（均为 3 级流水、1 inst/cycle、VLEN=128）：

1) vdot.vv（INT8，原基线）
     S = sum_{i=0..7} sext8(vs1[i]) * sext8(vs2[i])
     vd[31:0] = S，vd[127:32] = 0

2) vdot4x2.vv（INT4 打包，双结果双累加流）
     每字节 2 个 4-bit 有符号 nibble，nibble n = bits[4n+3:4n]
     r0 = sum_{n=0..7}  sext4(vs1[n]) * sext4(vs2[n])
     r1 = sum_{n=8..15} sext4(vs1[n]) * sext4(vs2[n])
     vd[31:0] = r0，vd[63:32] = r1，vd[127:64] = 0

3) vtdot.vv（BitNet 1.58 三值权重，双结果双累加流）
     vs1 的低 128 bit 提供 16 个 int8 激活 a_i = sext8(vs1[8*i +: 8])
     vs2 低 32 bit 提供 16 个 2-bit 三值码 code_i = vs2[2*i +: 2]
       code=00/11 -> 0，code=01 -> +a_i，code=10 -> -a_i
     r0 = sum_{i=0..7}  tern(a_i, code_i)
     r1 = sum_{i=8..15} tern(a_i, code_i)
     vd 布局与 vdot4x2 相同

本模型是测试期望值的唯一来源，不依赖 RTL 输出。
"""
from typing import List

VLEN = 128
K = 8
OUT_W = 32
DUAL_W = 12
TERN_W = 9


def sext8(x: int) -> int:
    """把 0..255 解释为 int8。"""
    x &= 0xFF
    return x - 0x100 if x & 0x80 else x


def sext4(x: int) -> int:
    """把 0..15 解释为 int4（二补码）。"""
    x &= 0xF
    return x - 0x10 if x & 0x8 else x


def ref_vdot(vs1_bytes: List[int], vs2_bytes: List[int]) -> int:
    """返回 vdot.vv 的 128 bit 结果（INT8）。

    vs1_bytes / vs2_bytes：长度 >= 8 的字节列表，lane i 为第 i 个字节。
    高 64 bit 不参与运算。
    """
    s = 0
    for i in range(K):
        s += sext8(vs1_bytes[i]) * sext8(vs2_bytes[i])
    # 32 bit 二补码截断 + 高位通道清零
    return s & ((1 << OUT_W) - 1)


def ref_vdot_signed(vs1_bytes: List[int], vs2_bytes: List[int]) -> int:
    """返回 vdot.vv 的有符号 32 bit 结果（便于打印十进制）。"""
    v = ref_vdot(vs1_bytes, vs2_bytes)
    return v - (1 << OUT_W) if v & (1 << (OUT_W - 1)) else v


def pack_dual(r0: int, r1: int) -> int:
    """把两个 32 bit 有符号结果打包成 128 bit vd（高 64 bit 清零）。"""
    return (r0 & 0xFFFFFFFF) | ((r1 & 0xFFFFFFFF) << OUT_W)


def ref_vdot4x2(vs1: int, vs2: int) -> int:
    """返回 vdot4x2.vv 的 128 bit 结果（INT4 打包，双结果）。"""
    r0 = 0
    r1 = 0
    for n in range(16):
        a = sext4((vs1 >> (4 * n)) & 0xF)
        b = sext4((vs2 >> (4 * n)) & 0xF)
        if n < 8:
            r0 += a * b
        else:
            r1 += a * b
    return pack_dual(r0, r1)


def _tern(a: int, code: int) -> int:
    """BitNet 1.58 三值选择：00/11 -> 0，01 -> +a，10 -> -a。"""
    if code == 1:
        return a
    if code == 2:
        return -a
    return 0


def ref_vtdot(vs1: int, vs2: int) -> int:
    """返回 vtdot.vv 的 128 bit 结果（三值权重，双结果）。"""
    r0 = 0
    r1 = 0
    for i in range(16):
        a = sext8((vs1 >> (8 * i)) & 0xFF)
        code = (vs2 >> (2 * i)) & 0x3
        if i < 8:
            r0 += _tern(a, code)
        else:
            r1 += _tern(a, code)
    return pack_dual(r0, r1)


def bytes_from_int(value: int, nbytes: int = VLEN // 8) -> List[int]:
    """128 bit 整数（lane0 在最低字节）转字节列表。"""
    return [(value >> (8 * i)) & 0xFF for i in range(nbytes)]


def int_from_bytes(bs: List[int]) -> int:
    v = 0
    for i, b in enumerate(bs):
        v |= (b & 0xFF) << (8 * i)
    return v


if __name__ == "__main__":
    # 自检：闭式边界结论（与设计规格书一致）
    assert ref_vdot([127] * 8, [127] * 8) == 0x0001F808, "INT8 max positive"
    assert ref_vdot([0x80] * 8, [0x80] * 8) == 0x00020000, "INT8 19-bit boundary"
    assert ref_vdot([0x80] * 8, [0x7F] * 8) == 0xFFFE0400, "INT8 max negative"
    assert ref_vdot([0] * 8, [0] * 8) == 0, "INT8 zero"
    assert ref_vdot([1, 255] * 4, [1] * 8) == 0, "INT8 cancellation"

    # INT4：全 -8 x -8，每组 8 项 -> 512
    assert ref_vdot4x2(0x8888888888888888, 0x8888888888888888) == 0x0000020000000200, \
        "INT4 max positive"
    # INT4：全 -8 x +7，每组 8 项 -> -448
    assert ref_vdot4x2(0x8888888888888888, 0x7777777777777777) == 0xFFFFFE40FFFFFE40, \
        "INT4 max negative"
    # INT4：高 32 bit 与低 32 bit 独立（低组全 0，高组全 -8 x -8）
    assert ref_vdot4x2(0x8888888800000000, 0x8888888800000000) == 0x0000020000000000, \
        "INT4 dual-stream independence"
    assert ref_vdot4x2(0, 0) == 0, "INT4 zero"

    # 三值：a=-128，全 +1 -> -1024；全 -1 -> +1024（验证 9-bit 取反）
    all_neg128 = int_from_bytes([0x80] * 16)
    codes_plus1 = sum(1 << (2 * i) for i in range(16))     # 0x55555555
    codes_minus1 = sum(2 << (2 * i) for i in range(16))     # 0xAAAAAAAA
    assert ref_vtdot(all_neg128, codes_plus1) == 0xFFFFFC00FFFFFC00, \
        "ternary max negative"
    assert ref_vtdot(all_neg128, codes_minus1) == 0x0000040000000400, \
        "ternary +128 negation boundary"
    assert ref_vtdot(all_neg128, 0xFFFFFFFF) == 0, "ternary code 11 is zero"
    assert ref_vtdot(0, 0x55555555) == 0, "ternary zero activation"
    # 三值双流独立：低组全 +1（-1024），高组全 0
    low_only = int_from_bytes([0x80] * 8 + [0] * 8)
    assert ref_vtdot(low_only, codes_plus1) == 0x00000000FFFFFC00, \
        "ternary dual-stream independence"

    print("ref_vdot family self-check: PASS")
