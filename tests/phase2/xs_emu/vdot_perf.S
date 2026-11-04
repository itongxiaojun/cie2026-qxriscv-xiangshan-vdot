/* 阶段二 · 香山昆明湖 V2 emu 性能对照用例（U-04 真实加速比）
 *
 * 同一份骨架编译出四个内核，prologue/epilogue 完全一致，只有循环体不同：
 *   PERF_KERNEL=0  perf_empty  : 循环体为空（仅 addi/bnez）        —— 循环开销
 *   PERF_KERNEL=1  perf_vdot   : 循环体 = 1 条 vdot.vv             —— 定制指令
 *   PERF_KERNEL=2  perf_rvv    : 循环体 = vwmul.vv + vwredsum.vs   —— 标准 RVV 等价序列
 *   PERF_KERNEL=3  perf_scalar : 循环体 = 8 组标量 mul/add         —— 无定制指令的标量实现
 *
 * 四个内核都计算同一个结果：
 *   dot8(k_a, k_b) = 1*8 + 2*7 + ... + 8*1 = 120
 * 所以周期差异只来自指令序列本身。数据在循环前一次性装入寄存器，循环内无访存，
 * 对比的是纯计算吞吐。
 *
 * 加速比算法（C 为 emu 打印的 cycleCnt）：
 *   per_iter(k) = (C_k - C_empty) / PERF_NITER
 *   speedup(baseline) = per_iter(baseline) / per_iter(vdot)
 * 四个程序 prologue/boot 相同，相减可消掉启动、循环开销与 epilogue。
 *
 * 用法（build.sh 会传 -DPERF_KERNEL=0/1/2/3）。
 */
#ifndef PERF_KERNEL
#define PERF_KERNEL 1
#endif
#ifndef PERF_NITER
#define PERF_NITER 20000
#endif
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

    /* ---------------- 公共 prologue ----------------
     * v1 = k_a, v2 = k_b, v3 = k_res（120），vl = VLMAX = 16 元素
     */
    la      a0, k_a
    la      a1, k_b
    la      a5, k_res
    /* tu（tail undisturbed）：vwredsum.vs 在 RVV 里只写 vd[0]，tail 属不确定区；
     * 用 ta 时 NEMU/RTL 会各填各的（NEMU 填全 1），v3 高位就无法确定比较。
     * 用 tu 后两者都必须保留 vd[1..]，结果可确定。 */
    vsetvli t1, x0, e8, m1, tu, ma
    vle8.v  v1, (a0)
    vle8.v  v2, (a1)
    vle8.v  v3, (a5)

    /* 标量累加器清零（kernel 3 在循环内累加，其余内核不使用） */
    li      s1, 0

#if PERF_KERNEL == 2
    vmv.v.i v0, 0                    /* vwredsum.vs 的 vs1 种子 = 0 */
#elif PERF_KERNEL == 3
    /* 标量基线：循环前把 16 个 int8 装入标量寄存器（lb 符号扩展） */
    lb      s5,  0(a0)
    lb      s6,  1(a0)
    lb      s7,  2(a0)
    lb      s8,  3(a0)
    lb      s9,  4(a0)
    lb      s10, 5(a0)
    lb      s11, 6(a0)
    lb      s2,  7(a0)
    lb      t3,  0(a1)
    lb      t4,  1(a1)
    lb      t5,  2(a1)
    lb      t6,  3(a1)
    lb      a3,  4(a1)
    lb      a4,  5(a1)
    lb      a6,  6(a1)
    lb      a7,  7(a1)
#endif

    /* ---------------- 计时循环 ---------------- */
    li      s0, PERF_NITER
loop:
#if PERF_KERNEL == 1
    .word   0xFE2081D7              /* vdot.vv v3, v1, v2 */
#elif PERF_KERNEL == 2
    vwmul.vv    v4, v1, v2          /* 16 lane 各 1 个 16-bit 乘积 */
    vwredsum.vs v3, v4, v0          /* v3[0] = Σ v4，tail 保持（tu） */
#elif PERF_KERNEL == 3
    li      s1, 0                   /* 每次迭代重算一个点积，与 vdot 覆盖 vd 等价 */
    mul     s3, s5,  t3
    add     s1, s1,  s3
    mul     s3, s6,  t4
    add     s1, s1,  s3
    mul     s3, s7,  t5
    add     s1, s1,  s3
    mul     s3, s8,  t6
    add     s1, s1,  s3
    mul     s3, s9,  a3
    add     s1, s1,  s3
    mul     s3, s10, a4
    add     s1, s1,  s3
    mul     s3, s11, a6
    add     s1, s1,  s3
    mul     s3, s2,  a7
    add     s1, s1,  s3
#endif
    addi    s0, s0, -1
    bnez    s0, loop

    /* ---------------- 公共 epilogue：结果自检 + 打印 ----------------
     * 向量结果 v3 必须 = {120, 0, ...}；kernel 3 另外校验标量累加结果 s1。
     */
    la      a2, dst
    li      t0, 16
    vsetvli t1, t0, e8, m1, tu, ma
    vse8.v  v3, (a2)

    li      s4, 0
    lw      a0, 0(a2)
    li      a3, 120
    bne     a0, a3, 3f
    lwu     t4, 4(a2)
    bnez    t4, 3f
    lwu     t4, 8(a2)
    bnez    t4, 3f
    lwu     t4, 12(a2)
    bnez    t4, 3f
#if PERF_KERNEL == 3
    li      a3, 120
    beq     s1, a3, 2f
    j       3f
#else
    j       2f
#endif
3:  addi    s4, s4, 1
    la      a0, bad_str
    jal     ra, puts
    j       4f
2:  la      a0, ok_str
    jal     ra, puts
4:  mv      a0, s4
    .word   0x0005006b              /* nemu_trap：trap code = 失败数，0 为 GOOD TRAP */
9:  j       9b

/* puts: a0=NUL 结尾字符串（clobber t4/a0） */
puts:
1:  lbu     t4, 0(a0)
    beqz    t4, 2f
    sb      t4, 0(t2)
    addi    a0, a0, 1
    j       1b
2:  ret

/* ----------------------- 数据 ----------------------- */
    .section .data
    .balign 16
dst:
    .word   0, 0, 0, 0

    .balign 16
k_a:
    .byte   1, 2, 3, 4, 5, 6, 7, 8
    .byte   0, 0, 0, 0, 0, 0, 0, 0
    .balign 16
k_b:
    .byte   8, 7, 6, 5, 4, 3, 2, 1
    .byte   0, 0, 0, 0, 0, 0, 0, 0
    .balign 16
k_res:
    .byte   120, 0, 0, 0, 0, 0, 0, 0
    .byte   0, 0, 0, 0, 0, 0, 0, 0

    .section .rodata
ok_str:
    .asciz  "PERF result=OK\n"
bad_str:
    .asciz  "PERF result=BAD\n"
