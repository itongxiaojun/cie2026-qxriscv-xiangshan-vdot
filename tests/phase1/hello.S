/* 阶段一 hello 测试：向 XiangShan SimTop 的 UART Lite（基址 0x4060_0000，THR 偏移 0x4）
 * 逐字节输出 "hello xiangshan, I am <团队标识>, IP address: <真实 IP>"
 * 运行方式：./build/emu -i hello.bin（镜像载入 RAM 0x8000_0000，
 *          复位后 flash(0x1000_0000) 的默认 bootloader 跳转到 0x8000_0000）
 * 结束：a0=0 + `.word 0x0005006b`（XiangShan/NEMU 约定的 nemu_trap 指令，
 *        rs1=a0 的取值作为 trap code，0 表示 GOOD TRAP）
 */
#define UART_THR 0x40600004
#include "ip_addr.h"

#define GREETING "hello xiangshan, I am qxriscv, " IP_ADDR "\n"

    .section .text.init, "ax", @progbits
    .globl _start
_start:
    la      a0, msg
    li      t2, UART_THR
1:
    lbu     t1, 0(a0)
    beqz    t1, 2f
    sb      t1, 0(t2)
    addi    a0, a0, 1
    j       1b
2:
    li      a0, 0
    .word   0x0005006b      /* nemu_trap: a0(=0) 作为 trap code -> GOOD TRAP */
3:
    j       3b

    .section .rodata
    .align 3
msg:
    .asciz GREETING
