# vdot 指令族设计文档（INT8 / INT4 打包 / BitNet 三值）

| 项目 | 内容 |
|---|---|
| 团队 | qxriscv |
| 目标平台 | 香山（XiangShan）昆明湖 V2，VLEN=128 |
| 交付物对应 | 阶段二 2.1「vdot.vv 设计文档」 |
| 规范性上游 | [ipd/01 指令与微架构设计规格书](file:///home/dbqxxs/xsriscv/cieriscv/ipd/01_vdot指令与微架构设计规格书.md)（需求条目、ADR、开放问题） |
| 实现 | [rtl/verilog/VDot.v](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v)（三模式，已验证）、[rtl/chisel/VDot.scala](file:///home/dbqxxs/xsriscv/cieriscv/rtl/chisel/VDot.scala)（三模式，已编译并生成 RTL） |
| 验证结论 | 单元回归 **3047/3047 PASS**，行覆盖率 **55/55 = 100%**；NEMU 协同仿真 **3032 用例 / 4551 结果字 / 0 fail**；Chisel 生成 RTL 同向量等价回归 **3047/3047** |
| 文档版本 | v1.3（2026-11-08，新增 `vdot4x2.vv` 双结果双累加流、`vtdot.vv` BitNet b1.58 三值融合、三模式共享数据通路与全量验证；含 §3.7–§3.9 BitNet 融合评审） |

---

## 1. 设计目标与约束

本设计在**不新增流水线、不修改既有向量功能单元逻辑**的前提下，为昆明湖 V2 的向量执行单元增加一个自洽的点积功能单元族，用一条 uop 完成一组乘累加，并保持"新增 1 个 VFu、零改动既有 VFu"的集成方式。

| 约束 | 来源 | 设计响应 |
|---|---|---|
| SEW=8、VLEN=128 | 赛题语义 | `VLEN=128`、`K=8` 参数化，SEW/LMUL/vm 非法组合直接拒绝 |
| 复用现有向量实现 | 赛题核心要求 | 只挂接既有向量发射/写回框架，新增 1 个 VFu |
| 正/负/边界三类测试 | 提交要求 2.3.1–2.3.3 | 3047 条向量 + 边界自检 + NEMU 双侧自检 |
| 差异化，不照搬竞品 | 团队路线 | 竞品是"单结果 INT4/INT8/INT16 三档 + 调度器唤醒旁路"；本设计走**双结果双累加流** + **BitNet 三值融合**，见 §3.6 |
| 交付可复现 | 评审要求 | Verilog / Chisel / Python / C / NEMU 五份实现或模型交叉验证 |

三条指令共享同一套合法性判定、三级流水与写回框架，指令之间仅 `EX1` 输入不同：

| 指令 | 计算 | 每指令乘累加 | 结果 |
|---|---|---|---|
| `vdot.vv` | INT8 × INT8，8 lane | 8 | 1 个 32-bit |
| `vdot4x2.vv` | INT4 × INT4，16 nibble | 16 | 2 个 32-bit |
| `vtdot.vv` | BitNet 三值权重 × INT8 激活，16 lane | 16（无乘法器） | 2 个 32-bit |

---

## 2. 指令语义

### 2.1 汇编格式与编码

```
vdot.vv     vd, vs1, vs2      # INT8 点积
vdot4x2.vv  vd, vs1, vs2      # INT4 打包，双结果
vtdot.vv    vd, vs1, vs2      # BitNet b1.58 三值权重，双结果
```

三条指令统一使用 `opcode=0x57`（OP-V）、`funct3=000`（OPIVV）、`vm=1`，用 `funct6` 区分：

| 字段 | 位域 | `vdot.vv` | `vdot4x2.vv` | `vtdot.vv` | 说明 |
|---|---|---|---|---|---|
| funct6 | [31:26] | `111111` | `111110` | `111101` | RVV 保留空间，与 RVV 1.0 已分配项无冲突 |
| vm | [25] | `1` | `1` | `1` | 仅无掩码形态合法 |
| vs2 | [24:20] | 源 2 | 源 2 | 三值权重码 | 提供 lane / nibble / 2-bit 码 |
| vs1 | [19:15] | 源 1 | 源 1 | INT8 激活 | 提供 lane / nibble / 激活字节 |
| funct3 | [14:12] | `000` | `000` | `000` | OPIVV |
| vd | [11:7] | 目标 | 目标 | 目标 | 承载 1 或 2 个结果 |
| opcode | [6:0] | `0x57` | `0x57` | `0x57` | OP-V |

在香山译码中三条指令都映射到 `FuType.vdot`，并用 `fuOpType[1:0]` 区分子模式（`0/1/2`）。模块级 RTL 用同宽输入 `in_mode[1:0]` 表达；`mode=3` 为保留值，按非法指令处理。

**操作数顺序**严格按 RISC-V 字段定义：`vs1` 在 bits[19:15]、`vs2` 在 bits[24:20]。本文件、测试台与 NEMU 模型均按此约定，避免"激活/权重"写反。

### 2.2 规范性伪代码

```python
def vdot_family(vd, vs1, vs2, mode):
    if SEW != 8 or LMUL != 1 or vm != 1 or mode == 3:
        raise IllegalInstruction
    if vl == 0:
        return                              # 不写 vd，不置 dirty

    if mode == 0:                           # vdot.vv, INT8
        s = sum(sext8(vs1[8*i +: 8]) * sext8(vs2[8*i +: 8]) for i in range(8))
        vd[31:0] = s[31:0]
        vd[127:32] = 0

    elif mode == 1:                         # vdot4x2.vv, INT4 packed
        r0 = sum(sext4(vs1[4*n +: 4]) * sext4(vs2[4*n +: 4]) for n in range(8))
        r1 = sum(sext4(vs1[4*n +: 4]) * sext4(vs2[4*n +: 4]) for n in range(8, 16))
        vd[31:0] = r0[31:0]
        vd[63:32] = r1[31:0]
        vd[127:64] = 0

    else:                                   # vtdot.vv, BitNet b1.58
        for i in range(16):
            a = sext8(vs1[8*i +: 8])
            code = vs2[2*i +: 2]
            t[i] = 0 if code in (0b00, 0b11) else (a if code == 0b01 else -a)
        r0 = sum(t[0:8])
        r1 = sum(t[8:16])
        vd[31:0] = r0[31:0]
        vd[63:32] = r1[31:0]
        vd[127:64] = 0
    mark_vd_dirty()
```

### 2.3 结果布局与操作数解释

| 指令 | 数据来源 | 结果位置 |
|---|---|---|
| `vdot.vv` | `vs1[63:0]`、`vs2[63:0]` 的 8 个 int8 | `vd[31:0]=r0`；`vd[127:32]=0` |
| `vdot4x2.vv` | 每字节拆 2 个 nibble：`n = bits[4n+3:4n]`，`n=0..15` | `vd[31:0]=r0`（n=0..7）；`vd[63:32]=r1`（n=8..15）；`vd[127:64]=0` |
| `vtdot.vv` | `vs1` 的 16 个 int8 激活；`vs2` 低 32 bit 中 16 个 2-bit 码 | `vd[31:0]=r0`（i=0..7）；`vd[63:32]=r1`（i=8..15）；`vd[127:64]=0` |

**nibble 顺序**：byte i 的低 nibble 是 `n=2i`，高 nibble 是 `n=2i+1`。因此 r0 对应前 4 个字节（8 个 nibble），r1 对应后 4 个字节。该顺序在 RTL、Python、C、NEMU、Chisel 五处一致，并有 16/16 nibble 定位自检。

**三值码表**（BitNet b1.58 权重 {-1, 0, +1}）：

| `vs2[2i+1:2i]` | 权重 | 输出 |
|---|---|---|
| `00` | 0 | 0 |
| `01` | +1 | `+a_i` |
| `10` | -1 | `-a_i` |
| `11` | 保留（按 0 处理） | 0 |

`11` 不触发异常而按 0 处理：未初始化或填充区域的三值码不会污染累加结果，也不需要软件预清零。

**双结果的含义**：一次指令把 16 个 lane 分成两个独立的 8 项累加流，分别写入 `vd[31:0]` 与 `vd[63:32]`。这不是"打包成一个 64-bit 数再拆"，两路在硬件上由两棵独立归约树产生，软件可以把两组部分和直接相加，或分给两个累加器链。

### 2.4 位宽推导（本设计的关键决策）

| 模式 | 单个 lane 取值 | 8 项组和 | 需要的位宽 |
|---|---|---|---|
| INT8 | 乘积 `[-16256, +16384]`（16 bit） | `[-130048, **+131072**]` | **≥19 bit 有符号**（18 bit 上界仅 131071）→ `ACC_W=20` |
| INT4 | nibble `[-8,7]`，乘积 `[-56,+64]`（8 bit） | `[-448, +512]` | 11 bit 已够，取 **`DUAL_W=12`** 留余量 |
| 三值 | `a ∈ [-128,127]`；`-(-128)=+128` 必须可表示 | `[-1024, **+1024**]` | lane 需 **`TERN_W=9`**；组和 11 bit 上界 +1024 不够（11 bit 最大 1023），取 **`DUAL_W=12`** |

若把 INT8 累加器写成 16/18 bit，"全 `-128` 输入"用例（`S=+131072`）会溢出，已固化为边界用例 `TC-B03`（实测 `0x00020000`）。三值路径若只给 8 bit，`a=-128` 取反得到 `+128` 会被截断为 `-128`，因此 lane 必须 9 bit；组和若只给 11 bit，16 个 `+128` 的一半（8 项）刚好是 `+1024`，会溢出，因此取 12 bit。

所有结果均以 32-bit 二补码写回（符号扩展，无饱和）。

### 2.5 语义判定表

| 条件 | 行为 |
|---|---|
| `vl == 0` | 不写 `vd`、不置 dirty、正常退休 |
| `vl >= 1` | 写满 128 bit（单结果尾通道清零 / 双结果高位通道清零），与 `vl` 数值无关 |
| `vm == 0` | illegal-instruction（显式拒绝未定义形态） |
| `SEW != 8` | illegal-instruction（含 `vsew=4..7` 的保留编码） |
| `LMUL != 1` | illegal-instruction（避免组内布局歧义） |
| `mode == 3` | illegal-instruction（保留模式） |
| `vstart != 0` | illegal-instruction（整寄存器操作无重启点） |
| `vta`/`vma` | 无关：输出固定写满 128 bit |
| `vxrm`/`vxsat` | 不读不写 |

**为什么 `vstart != 0` 直接拒绝**：单元内部没有跨指令累加状态，结果仅由两个源寄存器决定。若允许从中间 lane 重启，必须定义"部分写回"，而本指令是整寄存器一次成型，故按非法配置处理。

---

## 3. BitNet b1.58 与 vdot 的融合设计

### 3.1 为什么可以融合

BitNet b1.58 的核心是把权重约束到 `{-1, 0, +1}`，推理时的乘累加退化为**选择/取反/清零 + 加法**。这与 `vdot` 的"一组 lane 做点积并归约"结构天然同构：

- `vdot` 的瓶颈在 EX1 的乘法器阵列；三值权重把乘法的第二个操作数变成符号，乘法器整体消失。
- `vdot` 的归约树只关心"每个 lane 的有符号贡献"，不关心贡献来自乘法还是选择，因此**同一棵归约树可以直接复用**。
- 双结果布局正好匹配"两个独立 8-lane 部分和"的常见需求（例如把一次 16 元素的 GEMV 拆成两个 8 元素组，分别累加到两个 32-bit 累加器）。

因此 `vtdot.vv` 不是"再造一条独立指令"，而是把 BitNet 的算法结构映射到已有点积数据通路的 EX1 上，形成本队独有的第三条指令。

### 3.2 三值权重的 2-bit 编码与存储收益

| 方案 | 16 个权重的存储 | 相对 INT8 |
|---|---|---|
| INT8 | 16 × 8 bit = 128 bit | 1.0× |
| INT4 打包 | 16 × 4 bit = 64 bit | 2.0× |
| **BitNet 三值（本设计）** | 16 × 2 bit = **32 bit** | **4.0×** |

三值只需 `log2(3) ≈ 1.58` bit，本设计取 2 bit 编码（`00/11→0`、`01→+1`、`10→-1`），32 bit 即可容纳 16 个权重。一个 128-bit 向量寄存器因此可以装下 **64 个三值权重**，但单条 `vtdot.vv` 只消费低 32 bit 的 16 个，与 16 个 INT8 激活配对，保证单 uop 完成。

权重打包由离线/编译器完成（例如每 32 bit 写一个 `uint32_t` 常量），运行时不需要解包指令。

### 3.3 无乘法器的 EX1

三值路径的每个 lane 只做一件事：

```
t_i = (code==01) ? +a_i : (code==10) ? -a_i : 0
```

- `a_i` 先符号扩展到 9 bit；
- `-a_i` 用 9-bit 取反（`0 - a`），覆盖 `a=-128 → +128`；
- 选择器是 2-bit 码驱动的三选一 MUX。

综合视角下，这条路径没有 `8×8` 乘法器，只有 16 个 9-bit 取反器和 16 个三选一 MUX。与 INT4 路径的 16 个 `4×4` 乘法器相比，逻辑深度和面积都更小。

### 3.4 与 INT4 共享归约树

```
EX1:
  INT8   : 8 × (8×8 乘法器)          -> prod8[0..7]  (16 bit)
  INT4   : 16 × (4×4 乘法器)         -> prod4[0..15] (8 bit)
  VTDOT  : 16 × (取反/清零选择)      -> tern9[0..15] (9 bit)

          └──────────────┬──────────────┘
                         ▼
  dual9[0..15]: 按 mode 选择 prod4 / tern9 / 0（统一为 9-bit 有符号）

EX2:
  INT8   : 8 输入 -> 20-bit 归约树                 -> r
  INT4   : dual9[0..7]  -> 12-bit 树 -> r0
           dual9[8..15] -> 12-bit 树 -> r1
  VTDOT  : 同 INT4 的两棵 12-bit 树（输入换成 tern9）
```

INT4 与 VTDOT **共用 EX2 的两棵 12-bit 归约树**，差别只在 EX1 送进 `dual9` 的内容；INT8 保留原有 8×8 乘法器与 20-bit 归约树，行为逐位不变。这样既没有为 BitNet 新增一整条流水，也保证 INT8 基线零回归。

> 面积口径说明：当前 RTL 把三条 EX1 路径并行展开（组合选择），不做分时复用；因此三模式版的面积大于单模式历史值。三模式综合尚未在本机复跑（本机无 yosys），文档只引用单模式历史综合数字并明确标注，见 §5.2。

### 3.5 数值边界与适用性

| 项 | 结论 |
|---|---|
| 权重范围 | 严格 `{-1,0,+1}`；若量化后有其他值，需要软件改用 INT4 模式 |
| 激活范围 | INT8 有符号 `[-128,127]`，与原 `vdot` 一致 |
| 部分和范围 | 每组 8 项 ∈ `[-1024,+1024]`，12-bit 树无溢出 |
| 缩放/零点 | 指令不做反量化；per-channel scale 在指令外完成（折叠进激活或后处理） |
| 典型场景 | BitNet 线性层/GEMV、三值卷积、任何"权重三值化 + 激活 INT8"的推理内核 |

### 3.6 与竞品方案的差异

| 维度 | 竞品（参考队伍） | 本设计 |
|---|---|---|
| INT4 | 单结果，依赖把两组部分和再相加 | `vdot4x2.vv` **双结果双累加流**，两条归约树独立产出 `vd[31:0]`/`vd[63:32]` |
| 三值 | 未提供 | `vtdot.vv` 单指令 16 个三值 MAC，**零乘法器**，与 INT4 共享 EX2 |
| 调度 | 改 VF 调度器做 bypass2 唤醒 | 不改调度器；沿用既有向量发射/写回框架 |
| 权重存储 | INT8/INT4 | 2-bit 三值码，相对 INT8 **4× 压缩** |
| 验证 | 单一参考模型 | Verilog/Chisel/Python/C/NEMU 五方交叉 + 3047 向量 |

### 3.7 BitNet b1.58 的量化前端与本指令的边界

BitNet b1.58 的推理链路分两段：**权重量化在离线完成**，**激活量化在每次前向完成**，两者各带一个标量缩放因子。本指令只承担"量化后操作数的乘累加"，不承担量化与反量化，边界如下。

| 阶段 | BitNet b1.58 做法 | 本设计位置 | 说明 |
|---|---|---|---|
| 权重量化 | `w_q = clip(round(w / β), -1, +1)`，`β = mean(|w|)`（absmean） | 编译期/离线 | 产物就是 `vs2` 里的 2-bit 码；`β` 不进入指令 |
| 激活量化 | `x_q = clip(round(x / γ), -128, 127)`，`γ = max(|x|)`（absmax，逐 token 或逐 tensor） | 指令前由向量代码完成 | 产物是 `vs1` 的 16 个 INT8 |
| 乘累加 | `y = Σ x_q · w_q`（无浮点乘） | `vtdot.vv` 的 EX1+EX2 | 整数部分和，双结果 |
| 反量化 | `y_real = (β·γ) · y` | 指令后由向量代码完成 | 标量 `β·γ` 可折叠进下一层权重或一次 `vfmul`，不在点积内 |

这正好符合 BitNet"矩阵乘内部没有浮点乘法"的初衷：`vtdot.vv` 内部只有选择/取反/加法，`β·γ` 是一次标量缩放，与点积本身解耦。软件侧打包约定为"每 16 个三值权重写成一个 `uint32_t`、低位在前"，与 §2.2 的 `code_i = vs2[2i +: 2]` 逐位对应。

为什么保留 INT8 激活而不是把激活也三值化：BitNet b1.58 的原始配方是 **W1.58A8**（权重三值、激活 8 bit）。把激活也压到 2 bit 会引入第二条三值量化链并损失精度，超出"在既有点积单元上做融合"的范围；若未来需要 W1.58A4（BitNet a4.8 一类配方），可在同一 EX1 上增加 4-bit 激活切片，属于后续扩展。

### 3.8 1.58-bit 打包密度的取舍

`log2(3) ≈ 1.58` bit 是三值权重的信息下界：16 个权重理论需要 `16 × 1.585 ≈ 25.3` bit，而本设计的 2-bit 定长编码用 32 bit，多出 6.7 bit。能否用"5 个三值/字节"（`3^5 = 243 ≤ 256`）把这 6.7 bit 省回来？

| 方案 | 16 权重存储 | 解码 | 结论 |
|---|---|---|---|
| 2-bit 定长（本设计） | 32 bit | 直接按 2 bit 切片，零额外逻辑 | **采用**：与 `vs2[2i +: 2]` 完全对齐 |
| 5-trit/字节（base-3） | 仍为 4 字节 = 32 bit | 需要除 3 或 243 项 LUT | 不采用：见下 |

关键事实是**字节对齐**：16 个 trit 需要 25.3 bit，而 3 字节只有 24 bit，放不下，仍要占 4 字节；所以对**单条指令的 16 个权重**，base-3 打包一个字节也省不下来。只有块足够大时才显现收益：64 个 trit 约 101.4 bit，可压到 13 字节，相对 2-bit 的 16 字节省约 19%。

结论：寄存器内的点积操作数用 2-bit 定长最优；base-3 打包只适合**内存/磁盘侧的大块权重**，解包应由编译器在加载时完成，不应进入 EX1。这个取舍保证 `vtdot.vv` 的"零乘法器"卖点不被解码逻辑破坏。

### 3.9 融合评审结论

| BitNet b1.58 设计理念 | 在本设计中的落点 | 证据 |
|---|---|---|
| 权重三值 `{-1,0,+1}` | 2-bit 码 `01→+a`、`10→-a`、`00/11→0`（§2.2） | `ternary_boundary` 3/3、NEMU 760 用例 |
| 矩阵乘内部无乘法 | EX1 仅 9-bit 取反 + 三选一 MUX | [VDot.v#L136-L153](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L136-L153) |
| 1.58-bit 存储效率 | 16 权重 = 32 bit，相对 INT8 4× 压缩 | `perf_analysis.md` §6.5 |
| INT8 激活（W1.58A8） | `vs1` 16 个 int8，复用 `vdot` 的激活切片 | 3047 向量、RTL/NEMU/Chisel 三方一致 |
| 缩放不进入矩阵乘 | `β·γ` 在指令外折叠（§3.7） | 指令只输出整数部分和 |
| 部分和可分组累加 | 双结果 `r0/r1` 对应两组 8-lane 部分和 | 4551 结果字逐位 diff，0 mismatch |

**评审结论**：可以融合，且已融合。`vtdot.vv` 把 BitNet 的三值权重、无乘法器与 INT8 激活原样映射到既有 `vdot` 数据通路，只新增 EX1 的选择/取反逻辑，复用 EX2 的两棵 12-bit 归约树；唯一的主动偏离是 2-bit 定长编码（相对 1.58-bit 下界多 6.7 bit/16 权重），换来零解码逻辑与零乘法器。未做且不建议在本期做的两件事：激活三值化（超出 W1.58A8 配方）、硬件内 per-tensor 缩放（应留给编译器或后续向量指令）。

**进一步融合的备选（未实现，仅记录）**：

- **行并行 GEMV**：`vs2` 的 128 bit 可放 64 个三值码。若分成 4 组、每组 16 个码与同一组 16 个激活相乘，一条指令可产出 4 个输出通道的部分和（4×32 bit 恰好填满 `vd`），代价是 EX1 扩到 64 路、4 棵归约树，并会改动现有双结果语义与全部验证基线，本期不做。
- **5-trit 打包**：见 §3.8，只在存储侧对大块权重有意义。

---

## 4. 微架构设计

### 4.1 单元定位

| 项 | 规格 |
|---|---|
| 形态 | 新增向量功能单元 `VDot`，不新增流水段、不改调度器 |
| 每指令 uop | 1（128 bit 一次处理，不做多 beat 切分） |
| 流水 | 全流水、无状态、支持背靠背发射 |
| 延迟 | 3 周期（EX1 / EX2 / WB） |
| 吞吐 | 1 条/周期（三模式实测均为 1.0 inst/cycle） |
| 每周期乘累加 | INT8 = 8；INT4 = 16；VTDOT = 16（无乘法器） |
| 阻塞/重放 | 无；不做跨 uop 归约 |
| 旁路 | 不内部旁路，RAW 由既有记分牌保证 |

### 4.2 数据通路

```
        vs1[127:0]                         vs2[127:0]
   ┌──────────┴──────────┐          ┌──────────┴──────────┐
   │ INT8: 8×int8         │          │ INT8: 8×int8         │
   │ INT4: 16×nibble      │          │ INT4: 16×nibble      │
   │ 三值: 16×int8 激活   │          │ 三值: 32×2-bit 码    │
   └──────────┬──────────┘          └──────────┬──────────┘
              ▼  EX1（按 mode 并行展开，输出统一为 9-bit 有符号）
   ┌────────────────────────────────────────────────────────┐
   │ INT8  : 8 × 有符号 8×8 乘法器        -> prod8[0..7]     │
   │ INT4  : 16 × 有符号 4×4 乘法器       -> prod4[0..15]    │
   │ VTDOT : 16 × (取反/清零三选一)       -> tern9[0..15]    │
   └──────────────────────────┬─────────────────────────────┘
                              ▼
   ┌────────────────────────────────────────────────────────┐
   │ dual9[0..15] = mode==INT4 ? prod4 : mode==TERN ? tern9  │
   └──────────────────────────┬────────────────────────────────┘
                    ┌─────────┴─────────┐
                    │ 流水寄存器 s1_*   │
                    └─────────┬─────────┘
                              ▼  EX2
   ┌────────────────────────────────────────────────────────┐
   │ INT8  : 8→4→2→1 归约树（ACC_W=20）            -> sum8   │
   │ dual  : dual9[0..7] / dual9[8..15] 两棵 12-bit 树       │
   │         -> r0_sum / r1_sum                               │
   └──────────────────────────┬────────────────────────────────┘
                    ┌─────────┴─────────┐
                    │ 流水寄存器 s2_*   │
                    └─────────┬─────────┘
                              ▼  WB
   ┌────────────────────────────────────────────────────────┐
   │ INT8  : {96'b0, sext32(sum8)}                           │
   │ dual  : {64'b0, sext32(r1), sext32(r0)}                  │
   └──────────────────────────┬─────────────────────────────┘
                              ▼  向量写回（整寄存器 dirty）
```

### 4.3 周期级时序

| 周期 | 动作 | 关键信号（RTL 命名） |
|---|---|---|
| T0 | 请求接收，锁存源 payload、控制位与 `in_mode` | `in_valid/in_vs1/in_vs2/in_vm/in_sew/in_lmul/in_vl_zero/in_mode` |
| T0 末 | EX1 结果打入第一级 | `s1_prod8[0..7]`、`s1_dual9[0..15]`、`s1_mode`、`s1_illegal/s1_write` |
| T1 末 | EX2 归约结果打入第二级 | `s2_sum8`、`s2_r0`、`s2_r1`、`s2_illegal/s2_write` |
| T2 末 | 按模式格式化并写回 | `out_vd/out_valid/out_illegal/out_dirty` |

实测（`docs/phase2/logs/03_unit_test.log`）：`in_valid` 到 `out_valid` 为 3 个时钟沿；三模式背靠背流式均为 1.0 inst/cycle，无气泡。

### 4.4 参数

| 参数 | 默认 | 可配置 | 说明 |
|---|---|---|---|
| `VLEN` | 128 | 否 | 平台固定 |
| `K` | 8 | 是 | INT8 分组长度；仿真启动检查 `K==8` |
| `ACC_W` | 20 | 是 | 必须 ≥19 |
| `OUT_W` | 32 | 是 | 必须 ≥ACC_W |
| `DUAL_W` | 12 | 是 | INT4/三值组和位宽，必须 ≥12 |
| `TERN_W` | 9 | 是 | 三值 lane 位宽，必须 ≥9 |

---

## 5. RTL 实现说明

### 5.1 模块接口

`rtl/verilog/VDot.v` 提供一个与香山集成解耦的"请求/写回"接口：

| 方向 | 信号 | 位宽 | 含义 |
|---|---|---|---|
| in | `clk`, `reset` | 1 | 同步复位、高有效 |
| in | `in_valid` | 1 | 请求有效 |
| in | `in_vs1`, `in_vs2` | 128 | 源寄存器 payload |
| in | `in_vl_zero` | 1 | `vl==0`：不写回 |
| in | `in_vm`, `in_sew[2:0]`, `in_lmul[2:0]` | 1/3/3 | 合法性判定输入 |
| in | `in_mode[1:0]` | 2 | `0=INT8`、`1=INT4`、`2=三值`、`3=保留（非法）` |
| out | `out_vd` | 128 | 写回数据 |
| out | `out_valid` | 1 | 写回有效 |
| out | `out_illegal` | 1 | 非法指令（不写回） |
| out | `out_dirty` | 1 | 整寄存器脏 |

合法性判定为组合逻辑：`legal = in_vm && (in_sew == 0) && (in_lmul == 0) && (in_mode != 3)`。

`in_sew` 必须保留完整 3 bit（与 `vtype.vsew` 同宽）：若只取低 2 bit，保留编码 `vsew=4`（`3'b100`）会被截断为 0 而误判为 e8。该问题已由 TC-E05 覆盖。

### 5.2 实现结构（与文件对应）

| 功能块 | 位置 | 说明 |
|---|---|---|
| 参数自检 | [VDot.v#L83-L89](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L83-L89) | `K/ACC_W/OUT_W/DUAL_W/TERN_W` 越界即 `$fatal` |
| 合法性判定 | [VDot.v#L95-L96](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L95-L96) | `vm=1 / e8 / m1 / mode!=3` |
| INT8 乘法 | [VDot.v#L103-L112](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L103-L112) | 8 个 `8×8` 有符号乘 |
| INT4 乘法 | [VDot.v#L119-L129](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L119-L129) | 16 个 `4×4` 有符号乘 |
| 三值选择 | [VDot.v#L136-L149](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L136-L149) | 9-bit 扩展 + 取反 + 三选一，无乘法器 |
| dual9 选择 | [VDot.v#L155-L162](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L155-L162) | 按 mode 选 `prod4`/`tern9`/0 |
| EX1→EX2 流水寄存器 | [VDot.v#L170-L190](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L170-L190) | 保存乘积/选择值与 `s1_mode/s1_illegal/s1_write` |
| INT8 归约树 | [VDot.v#L198-L212](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L198-L212) | 8→4→2→1，20 bit |
| INT4/三值归约树 | [VDot.v#L224-L250](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L224-L250) | 两棵 12-bit 8 输入树 → r0/r1 |
| EX2→WB 流水寄存器 | [VDot.v#L255-L276](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L255-L276) | 保存 `sum8/r0/r1` 与控制位 |
| 按模式格式化 | [VDot.v#L283-L298](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L283-L298) | 符号扩展 + 尾通道清零 |
| 写回寄存与断言 | [VDot.v#L300-L336](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v#L300-L336) | 高位清零断言按 mode 区分 |

实现要点：

1. **加法树采用常数索引显式展开**，而非二维数组动态索引。后者在 Verilator 中触发 `UNOPTFLAT`（缺陷记录 D-01），改写后告警消失，同时更接近可综合写法。
2. **乘法器不在两级间复用**：EX1 专用乘法/选择阵列，EX2 只做加法与格式化。这是"3 周期、1 条/周期"的直接来源。
3. **INT4/三值共用 EX2**：共享两棵 12-bit 树，避免为第三条指令复制归约网络。
4. **单模式历史综合口径**：`4186 单元 / 172 FF / 25 级 R2R`（≈5.3k–8.4k GE）是**仅 INT8 单模式**的历史结果，见 `docs/phase4/01_yosys_synth.log`；三模式版面积尚未在本机综合（本机无 yosys），不得把该数字当作三模式面积。

### 5.3 Chisel 版本

`rtl/chisel/VDot.scala` 提供与 Verilog 版同语义的 `VDotCore`：

- `laneSInt` / `nibSInt` / `ext` / `treeSum` 对应 lane 切片、nibble 切片、符号扩展与树形归约；
- 三条 EX1 路径（`prod8`/`prod4`/`tern9`）与 `dual9` 选择、两棵 12-bit 树与 Verilog 版一一对应；
- 三级 `RegNext` 对应 EX1/EX2/WB；
- **状态（v1.3 更新）**：已用 `.tools/jdk` + `.tools/bin/mill` + Chisel 6.6.0 / firtool 1.62.1 重新生成 `rtl/chisel/VDotCore.sv`（475 行），新增 `io_in_mode[1:0]` 端口；经 `rtl/chisel/VDotWrap.v` 对齐端口后，复用同一测试台与同一 3047 条三模式向量，结果 **3047/3047 PASS、3 cycle、三模式 1.0 inst/cycle**（`docs/phase2/logs/09_chisel_equiv.log`）。

编译过程中修正的历史问题（v1.2，仍适用于三模式版）：

1. `s2Sum = RegNext(sum2)` 对宽度推断节点会生成位宽未知的寄存器 → 改为显式 `RegInit(0.S(ACCW.W))`；
2. 加法树各级 `+` 的位宽语义不显式 → 每级 `(a +& b)(ACCW-1,0)` 截断；
3. 断言消息含中文导致 firtool 1.62.1 拒绝 → 断言消息改为 ASCII。

接入香山时仍以该文件为骨架，按下节集成点替换为官方 `VFu` 基类。

---

## 6. 与香山昆明湖 V2 的集成方案

完整步骤、代码骨架与逐项核对清单见 [香山集成说明](file:///home/dbqxxs/xsriscv/cieriscv/patches/xiangshan-vdot-integration.md)，补丁见 [xiangshan-vdot.patch](file:///home/dbqxxs/xsriscv/cieriscv/patches/xiangshan-vdot.patch)。要点：

| # | 集成环节 | 动作 |
|---|---|---|
| I1 | 译码 | 新增三个 `BitPat`（`1111111?` / `1111101?` / `1111011?` + `000` + `1010111`），均映射 `FuType.vdot`，`fuOpType[1:0]=0/1/2` |
| I2 | uop 类型 | 新增 `FuType.vdot`，加入向量算术/`needVecCtrl`/`isVecArith` 集合 |
| I3 | 功能单元 | `VDotUnit` 继承 `VecPipedFuncUnit`，`VdotCfg`（latency=3、`writeVecRf`、`exceptionOut=illegalInstr`） |
| I4 | 发射/忙表 | 加入 `VFEX0` 的 `ExeUnitParams`，复用既有 VF 读端口/写回端口 |
| I5 | 写回 | 复用向量写回端口，整寄存器 dirty |
| I6 | 配置校验 | `vill/vsew/vlmul/vm/vstart` + `mode` 检查，illegal 抛出 |
| I7 | 参数 | `VLEN/K/ACC_W/OUT_W/DUAL_W/TERN_W` 参数化 |

**集成原则**：只做加法（新增文件 + 少量注册点），不改既有 VFu、不改调度器，每完成一个环节跑一次既有向量冒烟测试。

> **状态声明（2026-11-08 更新）**：I1–I7 已在香山 `16ae9dd` 源码上执行；三模式版 `VDotUnit.scala` + `VecDecoder.scala` 已通过 `mill -i xiangshan.compile`（573 个编译任务，28 s，0 error）。INT8 的系统级 emu 证据沿用 2026-11-03 的定向 7/7（difftest 0 mismatch）与非法配置 5/5；INT4/三值的系统级 emu 重跑需重建 emu，列为后续项（单元 + NEMU + Chisel 三方证据已闭环）。

---

## 7. 验证结果摘要

| 项 | 结果 | 证据 |
|---|---|---|
| 单元回归（三模式 + 边界 + 配置异常） | **3047/3047 PASS** | `docs/phase2/logs/03_unit_test.log` |
| 随机 + 边界密集 | 全 PASS | 同上 |
| 背靠背流式（INT8 / INT4 / 三值） | 1024/1024 PASS，三模式 1.0 inst/cycle | 同上 |
| 三方模型一致性（Python / C / RTL） | 3047/3047 | `logs/06_c_model_crosscheck.log` |
| INT4 nibble 逐位定位 | 16/16 PASS | `logs/03_unit_test.log`（`int4_nibble`） |
| 三值边界（`a=-128` 取反、`code=11` 归零） | 3/3 PASS | `logs/03_unit_test.log`（`ternary_boundary`） |
| 保留模式 `mode=3` 拒绝 | PASS（illegal，不写回） | `logs/03_unit_test.log`（`reserved_mode`） |
| 逐 lane 定位（INT8 lane0..7）+ `vstart` 重放 | 8/8、3/3 PASS | `logs/03_unit_test.log` |
| 保留 SEW 编码（`vsew=4`）/ 复位空闲 | PASS | `logs/03_unit_test.log` |
| 延迟 / 吞吐 / 乘累加 | 3 cycle / 1.0 inst/cycle / 8:16:16 | `logs/03_unit_test.log` |
| Chisel ↔ Verilog 等价回归（同测试台/同向量） | 3047/3047 PASS，3 cycle | `logs/09_chisel_equiv.log` |
| 行覆盖率（Verilator `--coverage-line`） | **55/55 = 100%** | `logs/07_coverage.log` |
| NEMU 协同仿真 | 3032 用例 / 4551 结果字 / 0 fail | `docs/phase3/01_nemu_cosim.log` |
| RTL ↔ NEMU 逐字比对 | 4551 vs 4551，mismatch 0 | `docs/phase3/02_cosim.log` |
| NEMU 边界自检（三模式 `vl=0` + 4 类非法） | 三模式全 PASS | 同上（`boundary_checks`） |
| 香山 Scala 编译 | PASS（573 任务，0 error） | `mill -i xiangshan.compile` |
| 严格 lint（Verilator -Wall） | 0 告警 0 错误 | `docs/phase4/02_verilator_lint.log` |
| 断言违反 | 0 | 测试报告 §6 |

---

## 8. 偏差、风险与未决项

| # | 项 | 状态 | 处理 |
|---|---|---|---|
| U-01 | 香山集成 | **已完成**（I1–I7，INT8 emu 定向 7/7、非法 5/5；三模式 Scala 编译 PASS） | 见 §6 与 `docs/phase2/logs/xs_emu_*.log` |
| U-02 | 汇编级测试（emu） | **部分完成**：INT8 定向/非法已跑；INT4/三值需重建 emu | 后续项 |
| U-03 | NEMU 扩展与协同仿真 | **已完成（2026-11-08）**：三模式 3032 用例 / 4551 字 / 0 fail | `docs/phase3/01_nemu_cosim.log` |
| U-04 | 真实加速比 | **已完成（INT8）**：对标量 9.8×（lane 公平）、对 16-lane RVV 11.8×（上界） | `docs/phase3/perf_analysis.md` §6 |
| U-05 | 综合面积/时序 | **部分关闭**：单模式历史综合 4186 单元 / 172 FF / 25 级；三模式面积待综合 | `docs/phase4/01_yosys_synth.log` |
| O2 | funct6 编码冲突 | **已关闭**（`111111/111110/111101` 属 RVV 保留空间） | 集成时 grep 复核 |
| — | `mode=3` 保留编码 | **已关闭** | 单元 `reserved_mode` + NEMU 非法配置自检 |
| — | Chisel 三模式可编译性 | **已关闭（v1.3）** | 生成 475 行 SV，3047/3047 等价回归 |
| — | 三值 `a=-128` 取反溢出 | **已关闭** | `TERN_W=9` + `ternary_boundary` 3/3 |

---

## 9. 追溯

| 需求 | 设计位置 | 验证 |
|---|---|---|
| 8 个 int8 有符号点积 | §2.2、§5.2 INT8 乘法块 | TC-F01/F02/F03、TC-R |
| INT4 打包 16 nibble / 双结果 | §2.1–2.3、§5.2 INT4 乘法 + 双树 | `int4_nibble` 16/16、NEMU int4x2 759 用例 |
| BitNet 三值权重无乘法器 | §3、§5.2 三值选择 | `ternary_boundary` 3/3、NEMU vtdot 760 用例 |
| `vd[31:0]=r0`、`vd[63:32]=r1` | §2.3、§5.2 按模式格式化 | 全部写回用例逐位比对 |
| 高位通道清零 | §5.2 格式化 + 断言 | 断言 + 128 bit 全宽比对 |
| INT8 19-bit 溢出边界 | §2.4 | TC-B03（`0x00020000`） |
| INT4 12-bit / 三值 9-bit 边界 | §2.4 | 边界用例 + NEMU |
| 非法配置拒绝（vm/e16/e64/m2/mode=3/vstart） | §2.5、§5.2 合法性判定 | TC-E01..E05、`reserved_mode`、NEMU boundary |
| 单 uop / 3 周期 / 1 条每周期 | §4.1、§4.3 | 测试报告 §5 |
| Chisel 与 Verilog 语义一致 | §5.3 | `logs/09_chisel_equiv.log`（3047/3047） |
