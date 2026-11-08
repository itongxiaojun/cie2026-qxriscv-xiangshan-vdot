#!/usr/bin/env python3
"""迷你 RISC-V/RVV 汇编器 + NEMU 测试镜像生成器

背景：本环境没有 RISC-V 交叉工具链，因此用纯 Python 手工编码机器码，
把 `vdot.vv` 自测程序与测试数据一起打包成 NEMU 可直接 `-b` 运行的平面镜像。

镜像布局（BASE = 0x80000000，即 NEMU 复位向量）：
    [0, DATA_OFF)          程序代码
    [DATA_OFF, +16)        十六进制字符表 "0123456789abcdef"
    [DATA_OFF+16, ...)     用例数组：每条 16 字节 vs1 + 16 字节 vs2

程序行为（对每条用例）：
    vsetvli e8,m1 -> vle8.v v1/v2 -> vdot.vv -> vsetvli e32,m1 -> vmv.x.s
    -> 把 vd[31:0] 打印成 8 个十六进制字符 + 换行（UART16550 MMIO 0x310b0000）
正常结束时 a0=0 并执行 nemu_trap。

编码依据：RISC-V 非特权手册 / RVV 1.0；NEMU (`src/isa/riscv64/instr/rvv/decode.h`)
的译码表作为第二重交叉校验。
"""
import struct

BASE_DEFAULT = 0x80000000
UART_MMIO = 0x310B0000
CASE_SIZE = 32          # 16B vs1 + 16B vs2
HEXTAB = b"0123456789abcdef"
CSR_MSTATUS = 0x300
CSR_MTVEC = 0x305
CSR_MEPC = 0x341

# ---------------- 通用寄存器编号 ----------------
X0, T0, T1, T2, S0, S1, S2, S3 = 0, 5, 6, 7, 8, 9, 18, 19
S4 = 20
T4, T5, T6, A0, A1 = 29, 30, 31, 10, 11
V0, V1, V2, V3 = 0, 1, 2, 3
V4, V6, V8, V10 = 4, 6, 8, 10

# ---------------- 基础编码器 ----------------
def _sext_ok(imm, bits):
    lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    return lo <= imm <= hi


def r_type(opcode, rd, f3, rs1, rs2, f7):
    return ((f7 & 0x7F) << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) \
        | ((f3 & 7) << 12) | ((rd & 0x1F) << 7) | (opcode & 0x7F)


def i_type(opcode, rd, f3, rs1, imm):
    assert _sext_ok(imm, 12), f"imm out of range: {imm}"
    return ((imm & 0xFFF) << 20) | ((rs1 & 0x1F) << 15) | ((f3 & 7) << 12) \
        | ((rd & 0x1F) << 7) | (opcode & 0x7F)


def s_type(opcode, f3, rs1, rs2, imm):
    assert _sext_ok(imm, 12), f"imm out of range: {imm}"
    u = imm & 0xFFF
    return ((u >> 5) << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15) \
        | ((f3 & 7) << 12) | ((u & 0x1F) << 7) | (opcode & 0x7F)


def b_type(opcode, f3, rs1, rs2, off):
    assert off % 2 == 0 and _sext_ok(off, 13), f"branch offset out of range: {off}"
    u = off & 0x1FFF
    return (((u >> 12) & 1) << 31) | (((u >> 5) & 0x3F) << 25) | ((rs2 & 0x1F) << 20) \
        | ((rs1 & 0x1F) << 15) | ((f3 & 7) << 12) | (((u >> 1) & 0xF) << 8) \
        | (((u >> 11) & 1) << 7) | (opcode & 0x7F)


def u_type(opcode, rd, imm20):
    return ((imm20 & 0xFFFFF) << 12) | ((rd & 0x1F) << 7) | (opcode & 0x7F)


# ---------------- 汇编器 ----------------
class Asm:
    """两遍汇编：先按 4 字节/条分配地址，再解析 label 完成编码。"""

    def __init__(self, base=BASE_DEFAULT):
        self.base = base
        self.items = []          # ("L", name) 或 ("I", fn)

    def label(self, name):
        self.items.append(("L", name))

    def _insn(self, fn):
        self.items.append(("I", fn))

    # --- 整数指令 ---
    def auipc(self, rd, imm20):
        self._insn(lambda sym, pc, rd=rd, imm20=imm20: u_type(0x17, rd, imm20))

    def lui(self, rd, imm20):
        self._insn(lambda sym, pc, rd=rd, imm20=imm20: u_type(0x37, rd, imm20))

    def addi(self, rd, rs1, imm):
        def f(sym, pc):
            v = sym[imm] - pc if isinstance(imm, str) else imm
            return i_type(0x13, rd, 0, rs1, v)
        self._insn(f)

    def andi(self, rd, rs1, imm):
        self._insn(lambda sym, pc, rd=rd, rs1=rs1, imm=imm: i_type(0x13, rd, 7, rs1, imm))

    def srli(self, rd, rs1, sh):
        assert 0 <= sh < 64
        self._insn(lambda sym, pc, rd=rd, rs1=rs1, sh=sh: i_type(0x13, rd, 5, rs1, sh))

    def add(self, rd, rs1, rs2):
        self._insn(lambda sym, pc, rd=rd, rs1=rs1, rs2=rs2: r_type(0x33, rd, 0, rs1, rs2, 0))

    def lbu(self, rd, rs1, imm=0):
        self._insn(lambda sym, pc, rd=rd, rs1=rs1, imm=imm: i_type(0x03, rd, 4, rs1, imm))

    def sb(self, rs2, rs1, imm=0):
        self._insn(lambda sym, pc, rs2=rs2, rs1=rs1, imm=imm: s_type(0x23, 0, rs1, rs2, imm))

    def csrs(self, csr, rs1):
        """CSRRS rd=x0, csr, rs1 —— 置位 CSR 中的位（x0 为目标表示只写）"""
        self._insn(lambda sym, pc, csr=csr, rs1=rs1: i_type(0x73, X0, 2, rs1, csr))

    def csrw(self, csr, rs1):
        """CSRRW rd=x0, csr, rs1 —— 直接写 CSR"""
        self._insn(lambda sym, pc, csr=csr, rs1=rs1: i_type(0x73, X0, 1, rs1, csr))

    def csrr(self, rd, csr):
        """CSRRS rd, csr, x0 —— 读 CSR"""
        self._insn(lambda sym, pc, rd=rd, csr=csr: i_type(0x73, rd, 2, X0, csr))

    def mret(self):
        self._insn(lambda sym, pc: 0x30200073)

    def la(self, rd, target):
        """地址装载：auipc rd, 0 + addi rd, rd, target-auipc_pc（目标需在 ±2 KiB 内）"""
        self._insn(lambda sym, pc, rd=rd: u_type(0x17, rd, 0))
        def f(sym, pc):
            # auipc 的 pc 是当前 addi 的 pc-4，故偏移需 +4
            return i_type(0x13, rd, 0, rd, sym[target] - pc + 4)
        self._insn(f)

    def bne(self, rs1, rs2, target):
        def f(sym, pc):
            return b_type(0x63, 1, rs1, rs2, sym[target] - pc)
        self._insn(f)

    def nemu_trap(self):
        self._insn(lambda sym, pc: 0x0000006B)

    # --- 向量指令 ---
    def vsetvli(self, rd, rs1, vtype):
        """vtype 为 8 bit 立即数：bits[2:0]=vlmul, [5:3]=vsew, [6]=vta, [7]=vma"""
        assert 0 <= vtype < 0x800
        self._insn(lambda sym, pc, rd=rd, rs1=rs1, vt=vtype: i_type(0x57, rd, 7, rs1, vt))

    def vle8_v(self, vd, rs1, imm=0):
        # imm 字段同时承载 vm(bit25) 与 lumop/nf：vm=1 对应 imm 的 bit5=0x20
        # nf=0, mew=0, mop=00, lumop=00000
        self._insn(lambda sym, pc, vd=vd, rs1=rs1, imm=imm: i_type(0x07, vd, 0, rs1, imm | 0x20))

    def vle_v(self, vd, rs1, sew_bytes, imm=0):
        """通用 vle<SEW>.v：width 字段 = log2(SEW/8)，opcode=LOAD-FP(0x07)，默认 vm=1"""
        f3 = {1: 0, 2: 1, 4: 2, 8: 3}[sew_bytes]
        self._insn(lambda sym, pc, vd=vd, rs1=rs1, imm=imm,
                   f3=f3: i_type(0x07, vd, f3, rs1, imm | 0x20))

    def vse_v(self, vs3, rs1, sew_bytes, imm=0):
        """通用 vse<SEW>.v：opcode=STORE-FP(0x27)，wd 字段位于 bits[11:7]，默认 vm=1"""
        f3 = {1: 0, 2: 1, 4: 2, 8: 3}[sew_bytes]
        self._insn(lambda sym, pc, vs3=vs3, rs1=rs1, imm=imm,
                   f3=f3: s_type(0x27, f3, rs1, vs3, imm | 0x20))

    def _vdot_vv(self, funct6, vd, vs1, vs2, vm=1):
        # 本族三条指令统一 funct3=000（OPIVV），用 funct6 区分
        # 参数顺序与 RISC-V 一致：vs1 -> bits[19:15]，vs2 -> bits[24:20]
        def f(sym, pc):
            return (((funct6 & 0x3F) << 26) | ((vm & 1) << 25) | ((vs2 & 0x1F) << 20)
                    | ((vs1 & 0x1F) << 15) | (0 << 12) | ((vd & 0x1F) << 7) | 0x57)
        self._insn(f)

    def vdot_vv(self, vd, vs1, vs2, vm=1):
        # funct6=111111（RVV 保留空间，本项目专用）, funct3=000
        self._vdot_vv(0x3F, vd, vs1, vs2, vm)

    def vdot4x2_vv(self, vd, vs1, vs2, vm=1):
        # funct6=111110, funct3=000 -> INT4 打包双结果
        self._vdot_vv(0x3E, vd, vs1, vs2, vm)

    def vtdot_vv(self, vd, vs1, vs2, vm=1):
        # funct6=111101, funct3=000 -> BitNet 三值权重双结果
        self._vdot_vv(0x3D, vd, vs1, vs2, vm)

    def vop_mvv(self, funct6, vd, vs2, vs1, funct3=2):
        """OPMVV 通用编码（funct3=010，vm=1）"""
        def f(sym, pc):
            return (((funct6 & 0x3F) << 26) | (1 << 25) | ((vs2 & 0x1F) << 20)
                    | ((vs1 & 0x1F) << 15) | ((funct3 & 7) << 12)
                    | ((vd & 0x1F) << 7) | 0x57)
        self._insn(f)

    # --- 基线（RVV 组合）指令 ---
    def vmul_vv(self, vd, vs2, vs1):
        self.vop_mvv(0x25, vd, vs2, vs1)          # funct6=100101

    def vredsum_vs(self, vd, vs2, vs1):
        self.vop_mvv(0x00, vd, vs2, vs1)          # funct6=000000

    def vsext_vf2(self, vd, vs2):
        # RVV vxunary0 组：funct6=010010, vs1=00111, funct3=010
        self.vop_mvv(0x12, vd, vs2, 0x07)

    def vmv_x_s(self, rd, vs2):
        # funct6=010000, vm=1, rs1=0, funct3=010
        def f(sym, pc):
            return ((0x10 << 26) | (1 << 25) | ((vs2 & 0x1F) << 20) | (0 << 15)
                    | (2 << 12) | ((rd & 0x1F) << 7) | 0x57)
        self._insn(f)

    # --- 输出辅助（约定：T2 = UART 基址，S3 = 字符表地址） ---
    def print_str(self, text):
        for ch in text.encode():
            self.addi(T6, X0, ch)
            self.sb(T6, T2, 0)

    def hex_print(self, reg):
        """把 32 bit 值按 8 个十六进制字符输出（clobber T6）"""
        for sh in (28, 24, 20, 16, 12, 8, 4, 0):
            self.srli(T6, reg, sh)
            self.andi(T6, T6, 0xF)
            self.add(T6, T6, S3)
            self.lbu(T6, T6, 0)
            self.sb(T6, T2, 0)

    # --- 输出 ---
    def encode(self):
        sym = {}
        addr = self.base
        for it in self.items:
            if it[0] == "L":
                assert it[1] not in sym, f"duplicate label {it[1]}"
                sym[it[1]] = addr
            else:
                addr += 4
        out = bytearray()
        pc = self.base
        for it in self.items:
            if it[0] == "I":
                out += struct.pack("<I", it[1](sym, pc) & 0xFFFFFFFF)
                pc += 4
        return bytes(out), sym

    def n_insn(self):
        return sum(1 for it in self.items if it[0] == "I")


def _align(n, a):
    return (n + a - 1) // a * a


def build_program(data_off, ncases, mode=0, verdict_reg=A0):
    """构造自测程序。data_off = 数据区相对 BASE 的字节偏移。

    mode: 0=vdot.vv(INT8)，1=vdot4x2.vv(INT4)，2=vtdot.vv(BitNet 三值)。
    双结果模式（1/2）先按 SEW=64 读回 vd[63:0]，分两行分别输出 r0、r1。
    """
    a = Asm()
    # banner: 确认 UART 通路可用；所有模式都含 "VDOT" 前缀
    banner = {0: "VDOT\n", 1: "VDOT4X2\n", 2: "VTDOT\n"}[mode]
    a.auipc(S0, 0)                 # s0 = BASE
    a.addi(S0, S0, data_off)       # s0 = &hextab
    a.addi(S3, S0, 0)              # s3 = &hextab
    a.addi(S1, S0, 16)             # s1 = &cases
    a.lui(T2, UART_MMIO >> 12)     # t2 = UART MMIO 基址
    # 裸机复位后 mstatus.VS=Off，向量指令一律非法；先把 VS 置为 Initial
    a.addi(T0, X0, 0x200)          # mstatus.VS[10:9] = 0b01
    a.csrs(CSR_MSTATUS, T0)
    a.print_str(banner)
    a.addi(T5, X0, ncases)         # t5 = 剩余用例数

    a.label("loop")
    # vta=vma=0（undisturbed）：NEMU 配置了 CONFIG_RVV_AGNOSTIC，一旦 ta/ma 置位，
    # 其 vle 快速路径会把整个向量寄存器（含活跃 lane）覆写为全 1，故此处取 undisturbed。
    a.vsetvli(T1, X0, 0x00)        # e8, m1, tu, mu
    a.vle8_v(V1, S1, 0)
    a.addi(T4, S1, 16)
    a.vle8_v(V2, T4, 0)
    if mode == 1:
        a.vdot4x2_vv(V3, V1, V2)
    elif mode == 2:
        a.vtdot_vv(V3, V1, V2)
    else:
        a.vdot_vv(V3, V1, V2)
    if mode == 0:
        a.vsetvli(T1, X0, 0x10)    # e32, m1
        a.vmv_x_s(T0, V3)          # t0 = vd[31:0]（SEW=32 元素 0）
        a.hex_print(T0)
        a.print_str("\n")
    else:
        a.vsetvli(T1, X0, 0x18)    # e64, m1 -> 元素 0 = vd[63:0]
        a.vmv_x_s(T0, V3)          # t0 = r0 | (r1 << 32)
        a.hex_print(T0)            # r0
        a.print_str("\n")
        a.srli(T0, T0, 32)
        a.hex_print(T0)            # r1
        a.print_str("\n")
    a.addi(S1, S1, CASE_SIZE)
    a.addi(T5, T5, -1)
    a.bne(T5, X0, "loop")
    a.addi(verdict_reg, X0, 0)     # a0 = 0 -> nemu_trap 正常退出
    a.nemu_trap()
    return a


def build_image(cases, program=build_program):
    """cases: [(vs1_bytes16, vs2_bytes16)] -> 平面镜像 bytes"""
    n = len(cases)
    # 指令条数与 data_off 无关，故先算一次规模
    prog0 = program(0, n)
    code_bytes = _align(prog0.n_insn() * 4, 16)
    assert code_bytes <= 2047, "DATA_OFF 必须放进 addi 的 12 bit 立即数"
    prog = program(code_bytes, n)
    code, sym = prog.encode()
    assert len(code) == prog.n_insn() * 4
    if "loop" in sym:
        assert sym["loop"] >= BASE_DEFAULT

    img = bytearray(code)
    img += b"\x00" * (code_bytes - len(img))
    img += HEXTAB
    for vs1, vs2 in cases:
        assert len(vs1) == 16 and len(vs2) == 16
        img += vs1 + vs2
    return bytes(img), sym, code_bytes


def _demo():
    img, sym, off = build_image([(bytes(range(16)), bytes(range(16, 32)))])
    print(f"insn/data_off/image = {len(img)} bytes, data_off={off}, sym={sym}")


if __name__ == "__main__":
    _demo()
