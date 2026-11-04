/* 阶段二 · 香山昆明湖 V2 emu 定向测试：vdot.vv 功能正确性
 *
 * 运行环境：XiangShan SimTop emu（UART Lite THR = 0x40600004）
 * 编码：vdot.vv v3, v1, v2
 *   funct6=111111, vm=1, rs2=vs2=v2, rs1=vs1=v1, funct3=000, rd=v3, opcode=0x57
 *   => 0xFC000000 | 0x02000000 | 0x00200000 | 0x00008000 | 0x00000180 | 0x57
 *   => 0xFE2081D7
 *
 * 语义：S = Σ_{i=0..7} sext8(vs1[8i+7:8i]) * sext8(vs2[8i+7:8i])
 *       vd[31:0] = S，vd[127:32] = 0；vl==0 不写回。
 *
 * 每个用例把整个 128 bit vd 写回内存，再检查低 32 bit 是否等于期望、
 * 高 96 bit 是否为 0。任何失败都会累加到 s4，最终作为 nemu_trap 的 trap code。
 *
 * 期望值：
 *   C0  1..8 · 8..1                = 120        (0x00000078)
 *   C1  (-128)x8 · (-128)x8        = 131072     (0x00020000)
 *   C2  (-128)x8 · 127x8           = -130048    (0xFFFE0400)
 *   C3  127x8 · 127x8              = 129032     (0x0001F808)
 *   C4  (-1,2,-3,4,-5,6,-7,8)·(1,-2,3,-4,5,-6,7,-8) = -204 (0xFFFFFF34)
 *   C5  同 C0，但 vl=8             = 120        (0x00000078)
 *   C6  vl=0：架构 vd 应保持预置的 sentinel 不变（FU 写回端口回写 oldVd）
 */
#ifndef UART_THR
#define UART_THR 0x40600004          /* XiangShan SimTop UART Lite THR */
#endif

    .section .text.init, "ax", @progbits
    .globl _start
_start:
    /* 裸机复位后 mstatus.FS/VS = Off，向量指令非法；先置 Initial */
    li      t0, 0x2200
    csrrs   x0, mstatus, t0

    li      t2, UART_THR
    la      s3, hextab
    li      s4, 0                   /* 失败计数 */

    /* ---------------- C0: 正数点积 120 ---------------- */
    li      s6, '0'
    la      a0, c0_vs1
    la      a1, c0_vs2
    la      a2, dst
    li      t0, 16
    vsetvli t1, t0, e8, m1, ta, ma
    vle8.v  v1, (a0)
    vle8.v  v2, (a1)
    .word   0xFE2081D7              /* vdot.vv v3, v1, v2 */
    vse8.v  v3, (a2)
    lw      a0, 0(a2)
    li      a3, 120
    jal     ra, chk_hi0

    /* ---------------- C1: 负×负 边界 0x00020000 ---------------- */
    li      s6, '1'
    la      a0, c1_vs1
    la      a1, c1_vs2
    la      a2, dst
    li      t0, 16
    vsetvli t1, t0, e8, m1, ta, ma
    vle8.v  v1, (a0)
    vle8.v  v2, (a1)
    .word   0xFE2081D7
    vse8.v  v3, (a2)
    lw      a0, 0(a2)
    li      a3, 131072
    jal     ra, chk_hi0

    /* ---------------- C2: 负×正 = -130048 (0xFFFE0400) ---------------- */
    li      s6, '2'
    la      a0, c2_vs1
    la      a1, c2_vs2
    la      a2, dst
    li      t0, 16
    vsetvli t1, t0, e8, m1, ta, ma
    vle8.v  v1, (a0)
    vle8.v  v2, (a1)
    .word   0xFE2081D7
    vse8.v  v3, (a2)
    lw      a0, 0(a2)
    li      a3, -130048             /* 0xFFFE0400 的符号扩展 64 位值 */
    jal     ra, chk_hi0

    /* ---------------- C3: 最大正点积 129032 (0x0001F808) ---------------- */
    li      s6, '3'
    la      a0, c3_vs1
    la      a1, c3_vs2
    la      a2, dst
    li      t0, 16
    vsetvli t1, t0, e8, m1, ta, ma
    vle8.v  v1, (a0)
    vle8.v  v2, (a1)
    .word   0xFE2081D7
    vse8.v  v3, (a2)
    lw      a0, 0(a2)
    li      a3, 129032
    jal     ra, chk_hi0

    /* ---------------- C4: 交替符号 = -204 (0xFFFFFF34) ---------------- */
    li      s6, '4'
    la      a0, c4_vs1
    la      a1, c4_vs2
    la      a2, dst
    li      t0, 16
    vsetvli t1, t0, e8, m1, ta, ma
    vle8.v  v1, (a0)
    vle8.v  v2, (a1)
    .word   0xFE2081D7
    vse8.v  v3, (a2)
    lw      a0, 0(a2)
    li      a3, -204
    jal     ra, chk_hi0

    /* ---------------- C5: vl=8，点积仍取全部 8 lane = 120 ---------------- */
    li      s6, '5'
    la      a0, c0_vs1
    la      a1, c0_vs2
    la      a2, dst
    li      t0, 8
    vsetvli t1, t0, e8, m1, ta, ma
    vle8.v  v1, (a0)
    vle8.v  v2, (a1)
    .word   0xFE2081D7
    vse8.v  v3, (a2)
    lw      a0, 0(a2)
    li      a3, 120
    jal     ra, chk_hi0

    /* ---------------- C6: vl=0 不写回，vd 保持 sentinel ---------------- */
    li      s6, '6'
    la      a0, c0_vs1
    la      a1, c0_vs2
    li      t0, 16
    vsetvli t1, t0, e8, m1, ta, ma
    vle8.v  v1, (a0)
    vle8.v  v2, (a1)
    la      a0, sentinel
    vle8.v  v3, (a0)                 /* 预置 v3 = sentinel */
    li      t0, 0
    vsetvli t1, t0, e8, m1, ta, ma   /* vl = 0 */
    .word   0xFE2081D7               /* 应无任何写回 */
    la      a2, dst
    li      t0, 16
    vsetvli t1, t0, e8, m1, ta, ma
    vse8.v  v3, (a2)
    jal     ra, chk_sentinel

    /* ---------------- 汇总 ---------------- */
    la      a0, summary_str
    jal     ra, puts
    mv      a0, s4
    jal     ra, print_hex
    la      a0, newline_str
    jal     ra, puts

    mv      a0, s4                   /* 0 -> GOOD TRAP */
    .word   0x0005006b
9:
    j       9b

/* ----------------------- 子程序 ----------------------- */

/* chk_hi0: a0=实际低 32 bit, a2=&dst, a3=期望, s6=用例字符
 * 检查 a0 == a3 且 dst[4], dst[8], dst[12] 全 0
 */
chk_hi0:
    mv      s8, ra
    mv      s7, a0
    sb      s6, 0(t2)
    li      a0, ' '
    sb      a0, 0(t2)
    mv      a0, s7
    jal     ra, print_hex
    bne     s7, a3, 1f
    lwu     t4, 4(a2)
    bnez    t4, 1f
    lwu     t4, 8(a2)
    bnez    t4, 1f
    lwu     t4, 12(a2)
    bnez    t4, 1f
    la      a0, ok_str
    jal     ra, puts
    j       2f
1:
    addi    s4, s4, 1
    la      a0, bad_str
    jal     ra, puts
2:
    mv      ra, s8
    ret

/* chk_sentinel: a2=&dst，逐字比对 16 字节 sentinel，s6=用例字符 */
chk_sentinel:
    mv      s8, ra
    sb      s6, 0(t2)
    li      a0, ' '
    sb      a0, 0(t2)
    la      a4, sentinel
    lwu     a5, 0(a4)
    lwu     t4, 0(a2)
    bne     t4, a5, 1f
    lwu     a5, 4(a4)
    lwu     t4, 4(a2)
    bne     t4, a5, 1f
    lwu     a5, 8(a4)
    lwu     t4, 8(a2)
    bne     t4, a5, 1f
    lwu     a5, 12(a4)
    lwu     t4, 12(a2)
    bne     t4, a5, 1f
    la      a0, ok_str
    jal     ra, puts
    j       2f
1:
    addi    s4, s4, 1
    la      a0, bad_str
    jal     ra, puts
2:
    mv      ra, s8
    ret

/* print_hex: a0=32 bit 值，输出 8 个十六进制字符（clobber t3/t4/t5/a0） */
print_hex:
    li      t3, 8
1:
    srli    t4, a0, 28
    andi    t4, t4, 0xf
    add     t4, t4, s3
    lbu     t5, 0(t4)
    sb      t5, 0(t2)
    slli    a0, a0, 4
    addi    t3, t3, -1
    bnez    t3, 1b
    ret

/* puts: a0=NUL 结尾字符串（clobber t4/a0） */
puts:
1:
    lbu     t4, 0(a0)
    beqz    t4, 2f
    sb      t4, 0(t2)
    addi    a0, a0, 1
    j       1b
2:
    ret

/* ----------------------- 数据 ----------------------- */
    .section .data
    .balign 16
dst:
    .word   0, 0, 0, 0

    .balign 16
sentinel:
    .word   0xDEADBEEF, 0xCAFEBABE, 0x12345678, 0x9ABCDEF0

    .balign 16
c0_vs1:
    .byte   1, 2, 3, 4, 5, 6, 7, 8
    .byte   0, 0, 0, 0, 0, 0, 0, 0
c0_vs2:
    .byte   8, 7, 6, 5, 4, 3, 2, 1
    .byte   0, 0, 0, 0, 0, 0, 0, 0

    .balign 16
c1_vs1:
    .byte   0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80
    .byte   0, 0, 0, 0, 0, 0, 0, 0
c1_vs2:
    .byte   0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80
    .byte   0, 0, 0, 0, 0, 0, 0, 0

    .balign 16
c2_vs1:
    .byte   0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80
    .byte   0, 0, 0, 0, 0, 0, 0, 0
c2_vs2:
    .byte   127, 127, 127, 127, 127, 127, 127, 127
    .byte   0, 0, 0, 0, 0, 0, 0, 0

    .balign 16
c3_vs1:
    .byte   127, 127, 127, 127, 127, 127, 127, 127
    .byte   0, 0, 0, 0, 0, 0, 0, 0
c3_vs2:
    .byte   127, 127, 127, 127, 127, 127, 127, 127
    .byte   0, 0, 0, 0, 0, 0, 0, 0

    .balign 16
c4_vs1:
    .byte   -1, 2, -3, 4, -5, 6, -7, 8
    .byte   0, 0, 0, 0, 0, 0, 0, 0
c4_vs2:
    .byte   1, -2, 3, -4, 5, -6, 7, -8
    .byte   0, 0, 0, 0, 0, 0, 0, 0

    .section .rodata
hextab:
    .ascii  "0123456789abcdef"
ok_str:
    .asciz  " OK\n"
bad_str:
    .asciz  " BAD\n"
summary_str:
    .asciz  "DIRECTED fails="
newline_str:
    .asciz  "\n"
