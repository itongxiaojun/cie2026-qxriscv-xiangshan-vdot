//=============================================================================
// VDot 单元级测试台（Verilator）
//
// 功能：
//   1) 读入 tests/vectors/vdot_vectors.txt，逐个用例驱动并逐位比对 128 bit 输出
//   2) 统计单条延迟（in_valid -> out_valid 的周期数）
//   3) 背靠背连续 1024 条流式测试：乱序/流水交错检查 + 吞吐统计
//
// 判定：任何不一致 -> 退出码 1
//=============================================================================
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>
#include <deque>
#include <fstream>
#include <sstream>
#include <iostream>
#include <algorithm>

#include "VVDot.h"
#include "verilated.h"
#include "verilated_vcd_c.h"

static VVDot *top = nullptr;
static VerilatedVcdC *tfp = nullptr;
static vluint64_t cyc = 0;
static vluint64_t vtime = 0;
static const vluint64_t VCD_MAX_CYCLES = 400;   // 只记录前若干周期，控制文件体积

static void tick() {
    top->clk = 0;
    top->eval();
    if (tfp && cyc < VCD_MAX_CYCLES) tfp->dump(vtime++);
    top->clk = 1;
    top->eval();
    if (tfp && cyc < VCD_MAX_CYCLES) tfp->dump(vtime++);
    ++cyc;
}

struct Wid {
    uint32_t w[4];
};

static Wid hex_to_wid(const std::string &h) {
    Wid r{};
    // 32 hex chars, MSB first -> 需要按 8 字符一段切到 w[3..0]
    // 这里按整体 128 bit 处理：先取高 64 / 低 64
    std::string hi = h.substr(0, 16);
    std::string lo = h.substr(16, 16);
    uint64_t hi64 = std::stoull(hi, nullptr, 16);
    uint64_t lo64 = std::stoull(lo, nullptr, 16);
    r.w[0] = (uint32_t)(lo64 & 0xFFFFFFFFu);
    r.w[1] = (uint32_t)(lo64 >> 32);
    r.w[2] = (uint32_t)(hi64 & 0xFFFFFFFFu);
    r.w[3] = (uint32_t)(hi64 >> 32);
    return r;
}

static Wid vd_read() {
    Wid r{};
    // Verilator 对 128 bit 端口展开为 4 个 32 bit word（小端序）
    r.w[0] = (uint32_t)top->out_vd[0];
    r.w[1] = (uint32_t)top->out_vd[1];
    r.w[2] = (uint32_t)top->out_vd[2];
    r.w[3] = (uint32_t)top->out_vd[3];
    return r;
}

static bool wid_eq(const Wid &a, const Wid &b) {
    for (int i = 0; i < 4; i++)
        if (a.w[i] != b.w[i]) return false;
    return true;
}

static std::string wid_str(const Wid &a) {
    char buf[40];
    std::snprintf(buf, sizeof(buf), "%08x%08x%08x%08x", a.w[3], a.w[2], a.w[1], a.w[0]);
    return std::string(buf);
}

static inline int32_t sext4_cpp(uint8_t n) {
    n &= 0xF;
    return (n & 0x8) ? (int32_t)n - 16 : (int32_t)n;
}

// 与 RTL 无关的 C++ 内联模型（INT8）：vd[31:0] = S，vd[127:32] = 0
static Wid compute_expected(const Wid &a, const Wid &b) {
    int64_t s = 0;
    for (int k = 0; k < 8; k++) {
        int8_t av = (int8_t)((a.w[k / 4] >> (8 * (k % 4))) & 0xFF);
        int8_t bv = (int8_t)((b.w[k / 4] >> (8 * (k % 4))) & 0xFF);
        s += (int)av * (int)bv;
    }
    Wid e{};
    e.w[0] = (uint32_t)(s & 0xFFFFFFFF);
    return e;
}

// 与 RTL 无关的 C++ 内联模型（INT4 打包，双结果）
static Wid compute_expected_int4(const Wid &a, const Wid &b) {
    int32_t r0 = 0, r1 = 0;
    for (int i = 0; i < 8; i++) {
        uint8_t a8 = (uint8_t)((a.w[i / 4] >> (8 * (i % 4))) & 0xFF);
        uint8_t b8 = (uint8_t)((b.w[i / 4] >> (8 * (i % 4))) & 0xFF);
        int32_t p = sext4_cpp(a8 & 0xF) * sext4_cpp(b8 & 0xF)
                  + sext4_cpp((a8 >> 4) & 0xF) * sext4_cpp((b8 >> 4) & 0xF);
        if (i < 4) r0 += p;
        else       r1 += p;
    }
    Wid e{};
    e.w[0] = (uint32_t)r0;
    e.w[1] = (uint32_t)r1;
    return e;
}

// 与 RTL 无关的 C++ 内联模型（BitNet 1.58 三值，双结果）
static Wid compute_expected_ternary(const Wid &a, const Wid &b) {
    int32_t r0 = 0, r1 = 0;
    uint32_t codes = b.w[0];               // 低 32 bit，每 2 bit 一个三值码
    for (int i = 0; i < 16; i++) {
        int32_t av = (int8_t)((a.w[i / 4] >> (8 * (i % 4))) & 0xFF);
        uint32_t c = (codes >> (2 * i)) & 0x3u;
        int32_t v = (c == 1u) ? av : (c == 2u) ? -av : 0;
        if (i < 8) r0 += v;
        else       r1 += v;
    }
    Wid e{};
    e.w[0] = (uint32_t)r0;
    e.w[1] = (uint32_t)r1;
    return e;
}

struct Case {
    std::string id;
    int vl_zero, vm, sew, lmul;
    std::string vs1, vs2, expected;
    int wr, ill, mode;
};

struct CaseResult {
    bool pass;
    int lat;
    std::string detail;
    Wid got;            // 实际观测到的 vd（仅写回用例有效）
};

static CaseResult run_case(const Case &c) {
    CaseResult r{true, 0, "", Wid{}};

    top->in_valid   = 1;
    top->in_vl_zero = c.vl_zero;
    top->in_vm      = c.vm;
    top->in_sew     = c.sew;
    top->in_lmul    = c.lmul;
    top->in_mode    = c.mode;
    Wid a = hex_to_wid(c.vs1);
    Wid b = hex_to_wid(c.vs2);
    for (int i = 0; i < 4; i++) {
        top->in_vs1[i] = a.w[i];
        top->in_vs2[i] = b.w[i];
    }
    top->eval();

    tick();                 // 边沿 1：进入 s1
    top->in_valid = 0;
    top->eval();

    bool seen_valid = false, seen_ill = false;
    int lat = 0;
    for (int k = 1; k <= 8; k++) {
        if (top->out_valid || top->out_illegal) {
            seen_valid = (bool)top->out_valid;
            seen_ill   = (bool)top->out_illegal;
            lat = k;
            break;
        }
        if (k < 8) tick();
    }

    if (c.ill) {
        if (!seen_ill) { r.pass = false; r.detail = "期望 illegal 未出现"; }
        else if (seen_valid) { r.pass = false; r.detail = "illegal 同时写回"; }
    } else if (c.vl_zero) {
        if (seen_valid || seen_ill) { r.pass = false; r.detail = "vl=0 时不应写回/报错"; }
    } else {
        if (!seen_valid) { r.pass = false; r.detail = "未出现写回 valid"; }
        else {
            Wid exp = hex_to_wid(c.expected);
            Wid got = vd_read();
            r.got = got;
            if (!wid_eq(exp, got)) {
                r.pass = false;
                r.detail = "vd 不匹配: exp=" + wid_str(exp) + " got=" + wid_str(got);
            }
        }
    }
    r.lat = lat;
    return r;
}

// 排空流水线，避免用例间干扰
static void drain_pipe() {
    top->in_valid = 0;
    top->eval();
    tick();
    tick();
    tick();
}

typedef Wid (*ExpectedFn)(const Wid &, const Wid &);

// 流式测试：连续 in_valid，按序检查
static bool run_stream(int n, int mode, ExpectedFn fn,
                       int *out_count, uint64_t *first_cyc, uint64_t *last_cyc) {
    std::deque<Wid> q;
    int done = 0;
    *first_cyc = 0;
    *last_cyc = 0;
    uint32_t lfsr = 0x12345678u ^ (0x9E3779B9u * (uint32_t)(mode + 1));

    for (int i = 0; i < n + 8; i++) {
        bool issue = (i < n);
        top->in_valid = issue ? 1 : 0;
        if (issue) {
            Wid a{}, b{};
            for (int w = 0; w < 4; w++) {
                lfsr = lfsr * 1664525u + 1013904223u;
                uint32_t x = lfsr;
                lfsr = lfsr * 1664525u + 1013904223u;
                uint32_t y = lfsr;
                top->in_vs1[w] = x;
                top->in_vs2[w] = y;
                a.w[w] = x;
                b.w[w] = y;
            }
            top->in_vl_zero = 0;
            top->in_vm      = 1;
            top->in_sew     = 0;
            top->in_lmul    = 0;
            top->in_mode    = mode;
            // 期望值由 C++ 内联模型计算（与 Python 模型构成独立交叉实现）
            q.push_back(fn(a, b));
        }
        top->eval();
        bool ov = top->out_valid;
        Wid vd_got = vd_read();
        tick();
        if (ov) {
            if (q.empty()) return false;
            Wid e = q.front();
            q.pop_front();
            if (!wid_eq(e, vd_got)) {
                std::cerr << "stream mode=" << mode << " mismatch at output #" << done
                          << ": exp=" << wid_str(e) << " got=" << wid_str(vd_got) << "\n";
                return false;
            }
            if (done == 0) *first_cyc = cyc;
            *last_cyc = cyc;
            done++;
        }
    }
    *out_count = done;
    return done == n;
}

// 补充自检（不属于向量文件，用于覆盖向量矩阵未显式命中的点）：
//   TC-L00..L07   INT8 逐 lane 定位：仅 lane i 非零，验证通道切片正确
//   TC-V03        无状态重放（模拟 vstart!=0 重算）：同一请求连发 3 次结果一致
//   TC-E05        vsew=4（保留编码）：必须判非法，验证接口保留完整 3 bit SEW
//   TC-N00..N15   INT4 逐 nibble 定位：验证 nibble 切片与双流分组
//   TC-TBxx       三值边界：-128 取反、code=11 清零、双流独立
//   TC-M3         保留 mode=3：必须判非法
static CaseResult run_extra_case(const std::string &id, const Wid &a, const Wid &b,
                                 const Wid &e, int mode, int wr, int ill,
                                 int vl_zero = 0, int sew = 0, int lmul = 0,
                                 int vm = 1) {
    Case c{};
    c.id = id;
    c.vl_zero = vl_zero; c.vm = vm; c.sew = sew; c.lmul = lmul;
    c.vs1 = wid_str(a); c.vs2 = wid_str(b); c.expected = wid_str(e);
    c.wr = wr; c.ill = ill; c.mode = mode;
    CaseResult r = run_case(c);
    drain_pipe();
    return r;
}

static void set_nibble(Wid &w, int idx, uint8_t v) {
    int word = idx / 8;              // 每个 32-bit word 含 8 个 nibble
    int shift = 4 * (idx % 8);
    w.w[word] = (w.w[word] & ~(0xFu << shift)) |
                ((uint32_t)(v & 0xF) << shift);
}

static int run_extra_checks(int *lane_pass, int *replay_pass, bool *reserved_ok,
                            int *int4_nib_pass, int *tern_bound_pass, bool *mode3_ok) {
    int fails = 0;
    *lane_pass = 0;
    *replay_pass = 0;
    *reserved_ok = false;
    *int4_nib_pass = 0;
    *tern_bound_pass = 0;
    *mode3_ok = false;

    for (int i = 0; i < 8; i++) {
        Wid a{}, b{};
        int8_t av = (i & 1) ? -5 : 5;          // 奇数 lane 取负值，正负都覆盖
        int8_t bv = (int8_t)(i + 1);
        a.w[i / 4] = (uint32_t)((uint8_t)av << (8 * (i % 4)));
        b.w[i / 4] = (uint32_t)((uint8_t)bv << (8 * (i % 4)));
        Wid e = compute_expected(a, b);

        Case c{};
        c.id = "TC-L0" + std::to_string(i);
        c.vl_zero = 0; c.vm = 1; c.sew = 0; c.lmul = 0;
        c.vs1 = wid_str(a); c.vs2 = wid_str(b); c.expected = wid_str(e);
        c.wr = 1; c.ill = 0;

        CaseResult r = run_case(c);
        drain_pipe();
        if (r.pass) {
            (*lane_pass)++;
        } else {
            fails++;
            std::cout << "FAIL " << c.id << " : " << r.detail << "\n";
        }
    }

    // TC-V03：无状态单元重放幂等（vstart!=0 时框架重放同一 uop，结果必须一致）
    Wid a{}, b{}, prev{}, e{};
    a.w[0] = 0x80808080u; a.w[1] = 0x80808080u;   // 全 -128，S=+131072
    b.w[0] = 0x80808080u; b.w[1] = 0x80808080u;
    e = compute_expected(a, b);
    for (int k = 0; k < 3; k++) {
        Case c{};
        c.id = "TC-V03-replay" + std::to_string(k);
        c.vl_zero = 0; c.vm = 1; c.sew = 0; c.lmul = 0;
        c.vs1 = wid_str(a); c.vs2 = wid_str(b); c.expected = wid_str(e);
        c.wr = 1; c.ill = 0;

        CaseResult r = run_case(c);
        drain_pipe();
        bool same_as_prev = (k == 0) || wid_eq(r.got, prev);
        if (r.pass && same_as_prev) {
            (*replay_pass)++;
        } else {
            fails++;
            std::cout << "FAIL " << c.id << " : " << r.detail
                      << (same_as_prev ? "" : "（与上次重放结果不一致）") << "\n";
        }
        prev = r.got;
    }

    // TC-E05：vsew=4 为保留编码，不能被 2 bit 截断误判为 e8
    {
        Wid a{}, b{};
        a.w[0] = 0x01010101u; a.w[1] = 0x01010101u;
        b.w[0] = 0x01010101u; b.w[1] = 0x01010101u;
        Case c{};
        c.id = "TC-E05-reserved-sew";
        c.vl_zero = 0; c.vm = 1; c.sew = 4; c.lmul = 0;
        c.vs1 = wid_str(a); c.vs2 = wid_str(b);
        c.expected = wid_str(compute_expected(a, b));
        c.wr = 0; c.ill = 1;

        CaseResult r = run_case(c);
        drain_pipe();
        if (r.pass) {
            *reserved_ok = true;
        } else {
            fails++;
            std::cout << "FAIL " << c.id << " : " << r.detail << "\n";
        }
    }

    // TC-N00..N15：INT4 逐 nibble 定位，验证 nibble 切片与 8/8 双流分组
    for (int i = 0; i < 16; i++) {
        Wid a{}, b{};
        set_nibble(a, i, 7);
        set_nibble(b, i, 1);
        Wid e = compute_expected_int4(a, b);
        char id[32];
        std::snprintf(id, sizeof(id), "TC-N%02d", i);
        CaseResult r = run_extra_case(id, a, b, e, 1, 1, 0);
        if (r.pass) (*int4_nib_pass)++;
        else {
            fails++;
            std::cout << "FAIL " << id << " : " << r.detail << "\n";
        }
    }

    // TC-TBxx：BitNet 三值边界
    {
        Wid a{};
        a.w[0] = 0x80808080u; a.w[1] = 0x80808080u;
        a.w[2] = 0x80808080u; a.w[3] = 0x80808080u;   // 16 个 -128

        Wid b1{}, b2{}, b3{};
        b1.w[0] = 0x55555555u;                         // 全 +1 -> -1024
        b2.w[0] = 0xAAAAAAAAu;                         // 全 -1 -> +1024
        Wid a3{};
        a3.w[0] = 0x7F7F7F7Fu; a3.w[1] = 0x7F7F7F7Fu;
        a3.w[2] = 0x7F7F7F7Fu; a3.w[3] = 0x7F7F7F7Fu;
        b3.w[0] = 0xFFFFFFFFu;                         // code=11 全 0

        struct { const char *id; Wid a; Wid b; } tt[] = {
            {"TC-TB01-neg128-plus1", a, b1},
            {"TC-TB02-neg128-minus1", a, b2},
            {"TC-TB03-code11-zero", a3, b3},
        };
        for (const auto &t : tt) {
            Wid e = compute_expected_ternary(t.a, t.b);
            CaseResult r = run_extra_case(t.id, t.a, t.b, e, 2, 1, 0);
            if (r.pass) (*tern_bound_pass)++;
            else {
                fails++;
                std::cout << "FAIL " << t.id << " : " << r.detail << "\n";
            }
        }
    }

    // TC-M3：保留 mode=3 必须判非法
    {
        Wid a{}, b{};
        a.w[0] = 0x01010101u; a.w[1] = 0x01010101u;
        b.w[0] = 0x01010101u; b.w[1] = 0x01010101u;
        Wid e = compute_expected(a, b);
        CaseResult r = run_extra_case("TC-M3-reserved-mode", a, b, e, 3, 0, 1);
        if (r.pass) *mode3_ok = true;
        else {
            fails++;
            std::cout << "FAIL TC-M3-reserved-mode : " << r.detail << "\n";
        }
    }

    return fails;
}

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    if (argc < 2) {
        std::cerr << "usage: tb_vdot <vectors.txt> [out.vcd] [result_export.txt]\n";
        return 2;
    }
    top = new VVDot;

    // 可选波形：tb_vdot <vectors.txt> <out.vcd>，传 "-" 表示不导出波形
    if (argc >= 3 && std::string(argv[2]) != "-") {
        Verilated::traceEverOn(true);
        tfp = new VerilatedVcdC;
        top->trace(tfp, 99);
        tfp->open(argv[2]);
    }

    // 复位
    top->clk = 0;
    top->reset = 1;
    top->in_valid = 0;
    top->in_vl_zero = 0;
    top->in_vm = 1;
    top->in_sew = 0;
    top->in_lmul = 0;
    top->in_mode = 0;
    for (int i = 0; i < 4; i++) { top->in_vs1[i] = 0; top->in_vs2[i] = 0; }
    for (int i = 0; i < 3; i++) tick();
    top->reset = 0;
    top->eval();

    bool reset_idle = !top->out_valid && !top->out_illegal && !top->out_dirty &&
                      vd_read().w[0] == 0 && vd_read().w[1] == 0 &&
                      vd_read().w[2] == 0 && vd_read().w[3] == 0;

    // 可选：导出逐用例 128 bit 结果，供 NEMU 协同仿真直接 diff
    // 只导出"合法且写回"的用例，顺序与输入文件一致
    std::ofstream export_f;
    if (argc >= 4) {
        export_f.open(argv[3]);
        if (!export_f) {
            std::cerr << "cannot open export file " << argv[3] << "\n";
            return 2;
        }
        export_f << "# one 128-bit result per write-back case (vl_zero=0, ill=0)\n";
    }

    std::ifstream f(argv[1]);
    if (!f) {
        std::cerr << "cannot open " << argv[1] << "\n";
        return 2;
    }

    std::vector<Case> cases;
    std::string line;
    while (std::getline(f, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::istringstream ss(line);
        Case c;
        if (!(ss >> c.id >> c.vl_zero >> c.vm >> c.sew >> c.lmul
                 >> c.vs1 >> c.vs2 >> c.expected >> c.wr >> c.ill)) {
            std::cerr << "bad line: " << line << "\n";
            return 2;
        }
        if (!(ss >> c.mode)) c.mode = 0;   // 兼容旧 10 列格式，默认 INT8
        cases.push_back(c);
    }

    int pass = 0, fail = 0;
    std::vector<int> lat_by_class(4, 0); // 0 write,1 illegal,2 vl0,3 other
    int lat_write = 0, lat_ill = 0;
    for (const auto &c : cases) {
        CaseResult r = run_case(c);
        if (r.pass) {
            pass++;
            if (c.ill) lat_ill = r.lat;
            else if (!c.vl_zero) lat_write = r.lat;
        } else {
            fail++;
            std::cout << "FAIL " << c.id << " : " << r.detail << "\n";
        }
        if (export_f.is_open() && !c.ill && !c.vl_zero) {
            // 与 NEMU 对齐：每个 32-bit 结果字一行。INT8 输出 1 行，
            // INT4/三值输出 r0、r1 共 2 行（NEMU 侧同样按字比对）。
            char wbuf[16];
            std::snprintf(wbuf, sizeof(wbuf), "%08x", (unsigned)r.got.w[0]);
            export_f << wbuf << "\n";
            if (c.mode != 0) {
                std::snprintf(wbuf, sizeof(wbuf), "%08x", (unsigned)r.got.w[1]);
                export_f << wbuf << "\n";
            }
        }
        // 排空流水线，避免用例间干扰
        drain_pipe();
    }

    int lane_pass = 0, replay_pass = 0, int4_nib_pass = 0, tern_bound_pass = 0;
    bool reserved_ok = false, mode3_ok = false;
    int extra_fail = run_extra_checks(&lane_pass, &replay_pass, &reserved_ok,
                                     &int4_nib_pass, &tern_bound_pass, &mode3_ok);

    int stream_n = 1024;
    int s8_got = 0, s4_got = 0, st_got = 0;
    uint64_t c8a = 0, c8b = 0, c4a = 0, c4b = 0, cta = 0, ctb = 0;
    bool s8_ok = run_stream(stream_n, 0, compute_expected,         &s8_got, &c8a, &c8b);
    bool s4_ok = run_stream(stream_n, 1, compute_expected_int4,    &s4_got, &c4a, &c4b);
    bool st_ok = run_stream(stream_n, 2, compute_expected_ternary, &st_got, &cta, &ctb);

    double tp8 = (c8b > c8a) ? (double)(s8_got - 1) / (double)(c8b - c8a) : 0.0;
    double tp4 = (c4b > c4a) ? (double)(s4_got - 1) / (double)(c4b - c4a) : 0.0;
    double tpt = (ctb > cta) ? (double)(st_got - 1) / (double)(ctb - cta) : 0.0;

    std::cout << "---------------------------------------------\n";
    std::cout << "cases_total      : " << cases.size() << "\n";
    std::cout << "cases_pass       : " << pass << "\n";
    std::cout << "cases_fail       : " << fail << "\n";
    std::cout << "latency_write    : " << lat_write << " cycle\n";
    std::cout << "latency_illegal  : " << lat_ill << " cycle\n";
    std::cout << "reset_idle       : " << (reset_idle ? "PASS" : "FAIL") << "\n";
    std::cout << "lane_checks      : " << lane_pass << "/8 PASS\n";
    std::cout << "replay_checks    : " << replay_pass << "/3 PASS\n";
    std::cout << "reserved_sew     : " << (reserved_ok ? "PASS" : "FAIL") << "\n";
    std::cout << "int4_nibble      : " << int4_nib_pass << "/16 PASS\n";
    std::cout << "ternary_boundary : " << tern_bound_pass << "/3 PASS\n";
    std::cout << "reserved_mode    : " << (mode3_ok ? "PASS" : "FAIL") << "\n";
    std::cout << "stream_issued    : " << stream_n << "\n";
    std::cout << "stream_completed : " << s8_got << "\n";
    std::cout << "stream_ok        : " << (s8_ok ? "true" : "false") << "\n";
    std::cout << "throughput       : " << tp8 << " inst/cycle\n";
    std::cout << "stream4_ok       : " << (s4_ok ? "true" : "false") << "\n";
    std::cout << "throughput_int4x2: " << tp4 << " inst/cycle\n";
    std::cout << "streamT_ok       : " << (st_ok ? "true" : "false") << "\n";
    std::cout << "throughput_vtdot : " << tpt << " inst/cycle\n";
    std::cout << "mac_per_cycle    : int8=" << (8.0 * tp8)
              << " int4x2=" << (16.0 * tp4)
              << " vtdot=" << (16.0 * tpt) << "\n";
    std::cout << "total_cycles     : " << cyc << "\n";
    bool all_ok = (fail == 0 && s8_ok && s4_ok && st_ok && reset_idle &&
                   extra_fail == 0);
    std::cout << "RESULT           : " << (all_ok ? "PASS" : "FAIL") << "\n";

    if (export_f.is_open()) export_f.close();

    if (tfp) {
        tfp->close();
        delete tfp;
        tfp = nullptr;
    }
#if VM_COVERAGE
    // 仅在 --coverage 构建时启用：退出前写出覆盖率数据（默认目录为当前工作目录）
    Verilated::threadContextp()->coveragep()->write("coverage.dat");
#endif
    top->final();
    delete top;
    return all_ok ? 0 : 1;
}
