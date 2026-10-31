/* 阶段一 vadd 波形测试：e8/m1 向量加法，覆盖 取指→译码→发射→向量执行→写回 */
    .section .text.init, "ax", @progbits
    .globl _start
_start:
    la      a0, src1
    la      a1, src2
    la      a2, dst
    vsetvli t0, x0, e8, m1, ta, ma
    vle8.v  v1, (a0)
    vle8.v  v2, (a1)
    vadd.vv v3, v1, v2
    vse8.v  v3, (a2)
    li      a0, 0
    ebreak
1:
    j       1b

    .section .data
    .align 4
src1:
    .byte 0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07
    .byte 0x08,0x09,0x0a,0x0b,0x0c,0x0d,0x0e,0x0f
src2:
    .byte 0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17
    .byte 0x18,0x19,0x1a,0x1b,0x1c,0x1d,0x1e,0x1f
dst:
    .byte 0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0
