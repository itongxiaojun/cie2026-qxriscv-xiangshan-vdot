//=============================================================================
// vdot 家族 C 参考模型（Golden Model / NEMU-ready）
//
// 覆盖三条指令：
//   1) vdot.vv      INT8 点积，单结果
//   2) vdot4x2.vv   INT4 打包，双结果双累加流
//   3) vtdot.vv     BitNet 1.58 三值权重，双结果双累加流
//
// 语义（与 docs/phase2/design.md 一致）：
//   INT8   S = sum_{i=0..7} (int8)vs1[i] * (int8)vs2[i]
//          vd[31:0] = S，vd[127:32] = 0
//   INT4   nibble n = bits[4n+3:4n]
//          r0 = sum_{n=0..7}  sext4(vs1[n]) * sext4(vs2[n])
//          r1 = sum_{n=8..15} sext4(vs1[n]) * sext4(vs2[n])
//          vd[31:0] = r0，vd[63:32] = r1，vd[127:64] = 0
//   三值   a_i = sext8(vs1[8*i +: 8])，code_i = vs2[2*i +: 2]
//          code 00/11 -> 0，01 -> +a_i，10 -> -a_i
//          r0 = sum_{i=0..7} tern(...)，r1 = sum_{i=8..15} tern(...)
//          vd 布局与 INT4 相同
//
// 用途：
//   1) 作为第三份独立实现，与 tests/ref_vdot.py（Python）和
//      tests/tb/tb_vdot.cpp（C++ 内联）交叉比对
//   2) 保留纯函数式接口，可直接移植进 NEMU 的 RVV 执行路径
//
// 构建：  gcc -O2 -std=c11 -o build/vdot_ref tests/model/vdot_ref.c
// 自检：  build/vdot_ref --selfcheck
// 比对：  build/vdot_ref tests/vectors/vdot_vectors.txt
//=============================================================================
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>

#define K      8
#define ACC_W  20
#define OUT_W  32

// --- NEMU 移植接口 -----------------------------------------------------------
// INT8：返回 128 bit 结果中低 32 bit 的有符号值
typedef struct {
    int32_t  s;        // 有符号和，范围 [-130048, 131072]
    uint32_t bits;     // vd[31:0] 的原始位模式
} vdot_result_t;

// INT4 / 三值：两个独立的 32 bit 结果，打包进低 64 bit
typedef struct {
    int32_t  s0;       // r0 有符号值，INT4 ∈ [-448,512]，三值 ∈ [-1024,1024]
    int32_t  s1;       // r1 有符号值
    uint64_t bits;     // vd[63:0] 的原始位模式（高 64 bit 恒为 0）
} vdot_dual_result_t;

static inline int8_t sext8(uint8_t b) {
    return (int8_t)b;
}

static inline int8_t sext4(uint8_t n) {
    n &= 0xF;
    return (int8_t)((n & 0x8) ? (n | 0xF0) : n);
}

static inline uint64_t pack_dual(int32_t r0, int32_t r1) {
    return ((uint64_t)(uint32_t)r0) | ((uint64_t)(uint32_t)r1 << 32);
}

vdot_result_t vdot_vv(const uint8_t vs1[K], const uint8_t vs2[K]) {
    vdot_result_t r;
    int32_t s = 0;
    for (int i = 0; i < K; i++) {
        s += (int32_t)sext8(vs1[i]) * (int32_t)sext8(vs2[i]);
    }
    // ACC_W=20 位宽足以承载 [-130048, +131072]，此处直接以 32 bit 承载
    r.s    = s;
    r.bits = (uint32_t)s;
    return r;
}

vdot_dual_result_t vdot4x2_vv(const uint8_t vs1[K], const uint8_t vs2[K]) {
    vdot_dual_result_t r;
    int32_t s0 = 0, s1 = 0;
    for (int i = 0; i < K; i++) {
        int8_t a_lo = sext4(vs1[i] & 0xF);
        int8_t a_hi = sext4((vs1[i] >> 4) & 0xF);
        int8_t b_lo = sext4(vs2[i] & 0xF);
        int8_t b_hi = sext4((vs2[i] >> 4) & 0xF);
        int32_t p = (int32_t)a_lo * b_lo + (int32_t)a_hi * b_hi;
        if (i < 4) s0 += p;
        else       s1 += p;
    }
    r.s0   = s0;
    r.s1   = s1;
    r.bits = pack_dual(s0, s1);
    return r;
}

vdot_dual_result_t vtdot_vv(const uint8_t act[16], uint32_t codes) {
    vdot_dual_result_t r;
    int32_t s0 = 0, s1 = 0;
    for (int i = 0; i < 16; i++) {
        int32_t a = (int32_t)sext8(act[i]);
        uint32_t c = (codes >> (2 * i)) & 0x3u;
        int32_t v = (c == 1u) ? a : (c == 2u) ? -a : 0;
        if (i < 8) s0 += v;
        else       s1 += v;
    }
    r.s0   = s0;
    r.s1   = s1;
    r.bits = pack_dual(s0, s1);
    return r;
}

// 把 128 bit 十六进制串转成 16 个 lane 字节（lane0 = 最低字节）
static void hex128_to_lanes(const char *hex, uint8_t lanes[16]) {
    // hex 为 32 个字符，MSB 在左；lane i 是整体 128 bit 的第 i 个字节
    for (int i = 0; i < 16; i++) {
        int hi = i * 2;
        char a = hex[30 - hi], b = hex[31 - hi];
        unsigned v = 0;
        for (int k = 0; k < 2; k++) {
            char c = (k == 0) ? a : b;
            unsigned d = (c <= '9') ? (unsigned)(c - '0')
                                    : (unsigned)(tolower((unsigned char)c) - 'a' + 10);
            v = (v << 4) | d;
        }
        lanes[i] = (uint8_t)v;
    }
}

// 由低 64 bit 构造 128 bit 期望串（高 64 bit 恒为 0）
static void bits_to_hex128(uint64_t low64, char out[33]) {
    snprintf(out, 33, "%016llx%016llx", 0ull, (unsigned long long)low64);
}

// 十六进制串大小写无关比较（不依赖 POSIX strcasecmp）
static int hex_streq(const char *a, const char *b) {
    while (*a && *b) {
        if (tolower((unsigned char)*a) != tolower((unsigned char)*b)) return 0;
        a++; b++;
    }
    return *a == '\0' && *b == '\0';
}

static int selfcheck(void) {
    int bad = 0;

    struct { int8_t a[K]; int8_t b[K]; int32_t want; } tc8[] = {
        {{127,127,127,127,127,127,127,127}, {127,127,127,127,127,127,127,127}, 0x1F808},
        {{-128,-128,-128,-128,-128,-128,-128,-128}, {-128,-128,-128,-128,-128,-128,-128,-128}, 0x20000},
        {{-128,-128,-128,-128,-128,-128,-128,-128}, {127,127,127,127,127,127,127,127}, -130048},
        {{0,0,0,0,0,0,0,0}, {0,0,0,0,0,0,0,0}, 0},
        {{1,-1,1,-1,1,-1,1,-1}, {1,1,1,1,1,1,1,1}, 0},
    };
    int n8 = (int)(sizeof(tc8) / sizeof(tc8[0]));
    for (int i = 0; i < n8; i++) {
        uint8_t a[K], b[K];
        for (int k = 0; k < K; k++) { a[k] = (uint8_t)tc8[i].a[k]; b[k] = (uint8_t)tc8[i].b[k]; }
        vdot_result_t r = vdot_vv(a, b);
        if (r.s != tc8[i].want) {
            printf("SELFCHECK FAIL INT8 case %d: got %d want %d\n", i, r.s, tc8[i].want);
            bad++;
        }
    }

    struct { int32_t r0, r1; uint64_t bits; const char *name; } tc4[] = {
        {512, 512, 0x0000020000000200ull, "INT4 max positive"},
        {-448, -448, 0xFFFFFE40FFFFFE40ull, "INT4 max negative"},
        {0, 512, 0x0000020000000000ull, "INT4 dual-stream independence"},
        {0, 0, 0, "INT4 zero"},
    };
    int n4 = (int)(sizeof(tc4) / sizeof(tc4[0]));
    for (int i = 0; i < n4; i++) {
        uint8_t a[K], b[K];
        for (int k = 0; k < K; k++) { a[k] = (i == 2 && k < 4) ? 0x00 : 0x88; b[k] = a[k]; }
        if (i == 2) { for (int k = 4; k < K; k++) { a[k] = 0x88; b[k] = 0x88; } }
        if (i == 1) { for (int k = 0; k < K; k++) b[k] = 0x77; }
        if (i == 3) { for (int k = 0; k < K; k++) { a[k] = 0; b[k] = 0; } }
        vdot_dual_result_t r = vdot4x2_vv(a, b);
        if (r.s0 != tc4[i].r0 || r.s1 != tc4[i].r1 || r.bits != tc4[i].bits) {
            printf("SELFCHECK FAIL %s: got (%d,%d,0x%llx) want (%d,%d,0x%llx)\n",
                   tc4[i].name, r.s0, r.s1, (unsigned long long)r.bits,
                   tc4[i].r0, tc4[i].r1, (unsigned long long)tc4[i].bits);
            bad++;
        }
    }

    struct { int32_t r0, r1; uint64_t bits; uint32_t codes; const char *name; } tcT[] = {
        {-1024, -1024, 0xFFFFFC00FFFFFC00ull, 0x55555555u, "ternary max negative"},
        {1024, 1024, 0x0000040000000400ull, 0xAAAAAAAAu, "ternary +128 boundary"},
        {0, 0, 0, 0xFFFFFFFFu, "ternary code 11 is zero"},
        {-1024, 0, 0x00000000FFFFFC00ull, 0x55555555u, "ternary dual-stream independence"},
    };
    int nT = (int)(sizeof(tcT) / sizeof(tcT[0]));
    for (int i = 0; i < nT; i++) {
        uint8_t act[16];
        for (int k = 0; k < 16; k++) act[k] = (i == 3 && k >= 8) ? 0x00 : 0x80;
        vdot_dual_result_t r = vtdot_vv(act, tcT[i].codes);
        if (r.s0 != tcT[i].r0 || r.s1 != tcT[i].r1 || r.bits != tcT[i].bits) {
            printf("SELFCHECK FAIL %s: got (%d,%d,0x%llx) want (%d,%d,0x%llx)\n",
                   tcT[i].name, r.s0, r.s1, (unsigned long long)r.bits,
                   tcT[i].r0, tcT[i].r1, (unsigned long long)tcT[i].bits);
            bad++;
        }
    }

    if (bad == 0) printf("SELFCHECK PASS (%d cases)\n", n8 + n4 + nT);
    return bad ? 1 : 0;
}

static int check_vectors(const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); return 2; }

    char line[512];
    int total = 0, pass = 0, fail = 0;
    while (fgets(line, sizeof(line), f)) {
        if (line[0] == '#' || line[0] == '\n') continue;
        char id[64], vs1h[64], vs2h[64], expdh[64];
        int vl_zero, vm, sew, lmul, wr, ill, mode = 0;
        int nf = sscanf(line, "%63s %d %d %d %d %63s %63s %63s %d %d %d",
                        id, &vl_zero, &vm, &sew, &lmul, vs1h, vs2h, expdh,
                        &wr, &ill, &mode);
        if (nf != 11) {
            // 兼容旧格式：无 mode 列时按 INT8 处理
            if (nf != 10) {
                fprintf(stderr, "bad line: %s", line);
                fclose(f);
                return 2;
            }
            mode = 0;
        }
        total++;
        uint8_t l1[16], l2[16], a[K], b[K];
        hex128_to_lanes(vs1h, l1);
        hex128_to_lanes(vs2h, l2);
        for (int i = 0; i < K; i++) { a[i] = l1[i]; b[i] = l2[i]; }

        uint64_t got_bits = 0;
        switch (mode) {
            case 0: got_bits = (uint64_t)vdot_vv(a, b).bits; break;
            case 1: got_bits = vdot4x2_vv(a, b).bits; break;
            case 2: {
                uint32_t codes = (uint32_t)l2[0] | ((uint32_t)l2[1] << 8) |
                                 ((uint32_t)l2[2] << 16) | ((uint32_t)l2[3] << 24);
                got_bits = vtdot_vv(l1, codes).bits;
                break;
            }
            default: got_bits = 0; break;   // 保留模式不写回
        }

        int legal = (vm == 1 && sew == 0 && lmul == 0 && mode != 3);
        char got[33];
        bits_to_hex128(got_bits, got);

        int ok = 1;
        if (!legal) {
            if (ill != 1) ok = 0;
        } else if (vl_zero) {
            if (wr != 0) ok = 0;
        } else {
            if (mode == 0) {
                // INT8 只比较低 32 bit；模型高 64 bit 恒 0
                got_bits = (uint64_t)vdot_vv(a, b).bits;
                bits_to_hex128(got_bits, got);
            }
            if (wr != 1 || !hex_streq(got, expdh)) ok = 0;
        }
        if (ok) pass++;
        else {
            fail++;
            printf("FAIL %s: mode=%d legal=%d vl_zero=%d got=%s expected=%s\n",
                   id, mode, legal, vl_zero, got, expdh);
        }
    }
    fclose(f);
    printf("vector_crosscheck: total=%d pass=%d fail=%d\n", total, pass, fail);
    printf("RESULT: %s\n", fail == 0 ? "PASS" : "FAIL");
    return fail == 0 ? 0 : 1;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s --selfcheck | <vectors.txt>\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "--selfcheck") == 0) return selfcheck();
    return check_vectors(argv[1]);
}
