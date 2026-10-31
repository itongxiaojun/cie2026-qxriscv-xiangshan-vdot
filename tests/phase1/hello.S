/* 阶段一 hello 测试：向 XiangShan SimTop 的 AXI4UART(0x1000_0004) 逐字节输出
 * 要求：输出 "hello xiangshan, I am <团队标识>, IP address: <真实 IP>"
 * 结束：a0=0 + ebreak（NEMU 参考模型据此判定 HIT GOOD TRAP）
 */
    .section .text.init, "ax", @progbits
    .globl _start
_start:
    la      a0, msg
1:
    lbu     t1, 0(a0)
    beqz    t1, 2f
    li      t2, 0x10000004       /* 16550 THR: base 0x10000000 + 0x4 */
    sb      t1, 0(t2)
    addi    a0, a0, 1
    j       1b
2:
    li      a0, 0
    ebreak
3:
    j       3b

    .section .rodata
    .align 3
#include "ip_addr.h"
msg:
    .asciz "hello xiangshan, I am qxriscv, "
    .asciz IP_ADDR
    .asciz "\n"
