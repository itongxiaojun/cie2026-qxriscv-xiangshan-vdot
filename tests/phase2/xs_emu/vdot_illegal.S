/* 阶段二 · 香山昆明湖 V2 emu 定向测试：vdot.vv 非法配置
 *
 * 期望行为（与 NEMU vdot 实现、spec 一致）：
 *   SEW != 8 / LMUL != 1 / vm == 0 / vill / 保留编码  ->  illegal instruction (mcause=2)
 * 每个非法用例执行一次 vdot，trap handler 统计 mcause==2 的次数并跳过该指令；
 * 最终 trap code = 0 表示 5/5 非法均被正确识别。
 *
 * vdot.vv v3, v1, v2 (vm=1) = 0xFE2081D7
 * vdot.vv v3, v1, v2 (vm=0) = 0xFC2081D7
 * vsetvli x0, x0, 0x20（vsew=4 保留编码 -> vill） = 0x02007057
 */
#ifndef UART_THR
#define UART_THR 0x40600004          /* XiangShan SimTop UART Lite THR */
#endif

    .section .text.init, "ax", @progbits
    .globl _start
_start:
    li      t0, 0x2200
    csrrs   x0, mstatus, t0

    li      t2, UART_THR
    la      s3, hextab
    la      t0, trap_entry
    csrw    mtvec, t0
    li      s4, 0                   /* 正确识别为 EX_II 的次数 */
    li      s5, 0                   /* 其他 trap 次数 */

    /* T0: SEW = e32 */
    li      t0, 16
    vsetvli t1, t0, e32, m1, ta, ma
    .word   0xFE2081D7

    /* T1: LMUL = m2 */
    li      t0, 16
    vsetvli t1, t0, e8, m2, ta, ma
    .word   0xFE2081D7

    /* T2: vm = 0（译码阶段即非法） */
    .word   0xFC2081D7

    /* T3: vill（vsew=4 保留编码） */
    li      t0, 16
    .word   0x02007057              /* vsetvli x0, x0, 0x20 */
    .word   0xFE2081D7

    /* T4: LMUL = m4 */
    li      t0, 16
    vsetvli t1, t0, e8, m4, ta, ma
    .word   0xFE2081D7

    /* ---------------- 汇总 ---------------- */
    la      a0, trap_str
    jal     ra, puts
    mv      a0, s4
    jal     ra, print_hex
    la      a0, bad_str
    jal     ra, puts
    mv      a0, s5
    jal     ra, print_hex
    la      a0, newline_str
    jal     ra, puts

    li      t0, 5
    bne     s4, t0, 1f
    bnez    s5, 1f
    li      a0, 0
    j       2f
1:
    li      a0, 1
2:
    .word   0x0005006b
9:
    j       9b

/* ---------------- trap handler ---------------- */
    .balign 4
trap_entry:
    csrr    t3, mcause
    csrr    t5, mepc
    addi    t5, t5, 4
    csrw    mepc, t5
    li      t4, 2
    bne     t3, t4, 1f
    addi    s4, s4, 1
    mret
1:
    addi    s5, s5, 1
    mret

/* ---------------- 子程序 ---------------- */
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

puts:
1:
    lbu     t4, 0(a0)
    beqz    t4, 2f
    sb      t4, 0(t2)
    addi    a0, a0, 1
    j       1b
2:
    ret

    .section .rodata
hextab:
    .ascii  "0123456789abcdef"
trap_str:
    .asciz  "ILLEGAL traps="
bad_str:
    .asciz  " other="
newline_str:
    .asciz  "\n"
