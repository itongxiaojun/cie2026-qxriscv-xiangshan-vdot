# 阶段四 · RTL 收口、综合评估与加速模型报告

> 项目：2026CIE · qxriscv · xiangshan-vdot
> 对应进度表 T4.1–T4.4；所有数字均来自 `docs/phase4/` 下日志，可复现。
> 口径声明：面积/逻辑深度为 **generic 工艺无关综合**（三模式 7427 单元 / 356 FF / 25 级，INT8 单模式对照 4187 / 172 / 25），不是 PDK 签核结果；延迟/吞吐的 4.0×/6.0× 为 **结构模型推演**。**实测加速比另有出处**：香山昆明湖 V2 `emu` 整程序 cycleCnt（9.8× 对标量，8-lane 公平 / 11.8× 对 RVV，16-lane，属上界，NITER=2000），见 §5.3 与 `docs/phase3/perf_analysis.md` §6。
>
> **三模式更新（2026-11-08）**：RTL 已扩展为 `vdot.vv` / `vdot4x2.vv` / `vtdot.vv`（BitNet b1.58 三值），单元回归 **3047/3047**、覆盖率 **55/55**、NEMU 协同 **3032 用例 / 4551 字 / 0 fail**、Chisel 等价 **3047/3047**。
> **综合更新（2026-11-10）**：本机已装 yosys 0.52 并对三模式 RTL 实跑，§3 现为 **7427 单元 / 356 FF / 25 级**；INT8 单模式复核为 4187 单元 / 172 FF / 25 级（历史 4186）。

---

## 1. 目的与范围

| 目标 | 手段 | 结论 |
|---|---|---|
| 清除 RTL 中的死逻辑，消除严格 lint 告警 | Verilator `--lint-only -Wall` + 人工复核 | 告警 4 → 0（仅 1 处语义性豁免，见 §2.3） |
| 证明清理未改变功能 | 全量单元回归 + NEMU/RTL 协同仿真 + 基线复跑 | 3047/3047（三模式）、NEMU 3032 用例/4551 字 0 mismatch |
| 取得面积与逻辑深度量级 | yosys 0.52 generic 综合（`synth -noabc; techmap`） | **三模式 7427 单元 / 356 FF / 25 级**；INT8 单模式对照 4187 单元 / 172 FF / 25 级 |
| 给出可辩护的"有/无该指令"差异 | 指令数实测 + 依赖链/吞吐结构模型 + 香山 emu 整程序实测 | 数据通路 6→1；模型延迟 12→3 cycle；实测加速比 9.8×（8-lane 公平）/11.8×（16-lane 上界） |

**不在范围**：PDK 映射后的面积（µm²）、时序签核（ns/GHz）。原因见 §7。香山平台实测周期与加速比已于 2026-11-03 完成（§5.3）。

---

## 2. RTL 收口：发现并修复的问题

### 2.1 死逻辑（面积/可读性缺陷）

`rtl/verilog/VDot.v` 中原本存在一整套**无读者**的组合逻辑，与 Chisel 版（`rtl/chisel/VDot.scala`）不一致：

| 信号 | 位置 | 问题 |
|---|---|---|
| `t0[]`、`t1_0..3`、`t2_0..1`、`sum_c` | 原 EX1→EX2 之间 | 由 `in_vs1/in_vs2` 直接展开的 8→4→2→1 加法树，**无任何读者**；真正使用的是 `s1_prod` 之后的 `u0/u1/u2/sum2` |
| `s1_valid` | EX1→EX2 流水 | 仅驱动 `s2_valid`，无其它读者 |
| `s2_valid` | EX2→WB 流水 | 无读者（写回由 `s2_write` 表达） |

后果：综合工具会全部删除，硅面积无差异，但会误导"EX1 已做归约"的流水理解，并让严格 lint 直接失败。已删除，并在 RTL 中注明"valid 不单独寄存"的理由。

> 该缺陷不影响既有结论：删除前后 `total_cycles` 均为 10113（1024 条背靠背），功能回归全绿（§4）。

### 2.2 语义性未用端口

`in_vs2[127:64]` 在三模式下均不使用：INT8 只取低 64 bit 的 8 个 int8；INT4 只取低 64 bit 的 16 个 nibble（8 字节）；三值只取低 32 bit 的 16 个 2-bit 码。`in_vs1[127:64]` 仅三值模式使用（16 个激活字节）。这是题面固定布局，已在端口处就地豁免 `UNUSEDSIGNAL` 并写明原因，避免用全文件级豁免掩盖将来真实问题。

### 2.3 Lint 结果

`.tools/verilator/bin/verilator --lint-only -Wall -Wno-DECLFILENAME rtl/verilog/VDot.v --top-module VDot`

- 修复前：4 条 `UNUSEDSIGNAL` 告警 → `%Error`
- 修复后：**0 告警 0 错误**（日志 `02_verilator_lint.log`）

---

## 3. 综合评估（generic，三模式 + INT8 对照）

> **口径**：2026-11-10 已在本机装好 yosys 0.52 并对**三模式 `VDot.v`** 实跑综合：**7427 单元 / 356 FF / 最长 R2R 25 级**。同一流程对 v1.2 单模式 RTL 复核得 4187 单元（历史值 4186，差 1 个 `$_OR_`，属等价），工具链口径可信。

- 工具：Yosys 0.52-2（Debian trixie `yosys` + `yosys-abc` deb 包**解包到 `.tools/yosys`**，未安装到系统、未改系统环境；`.tools/` 已被 gitignore）
- 运行方式：`PATH=.tools/yosys/usr/bin:$PATH YOSYS_DATDIR=.tools/yosys/usr/share/yosys`
- 流程：`read_verilog -sv` → `synth -top VDot -noabc` → `techmap` → `opt` → `splitnets -ports` → `opt` → `ltp -noff` → `stat`
- 说明：使用 `-noabc`，映射到 2 输入通用门；结果比 ABC 优化后保守，可作三模式之间的横向对比，不作 µm²。

### 3.1 规模

| 单元 | **三模式（现行）** | INT8 单模式（复核） | 增量 |
|---|---|---|---|
| `$_AND_` | 2954 | 1929 | +1025 |
| `$_XOR_` | 2315 | 1362 | +953 |
| `$_OR_` | 1054 | 656 | +398 |
| `$_MUX_` | 576 | 0 | +576 |
| `$_NOT_` | 172 | 68 | +104 |
| `$_SDFF_PP0_` | **356** | 172 | +184 |
| **合计** | **7427** | 4187 | **+3240（+77.4%）** |

增量来源与结构完全对得上：16 个 `4×4` 乘法器（约 +380 XOR / +部分 AND）、16 条三值 lane 的 9-bit 取反与选择（约 +300 XOR、+576 MUX 的主要部分）、两棵 12-bit 归约树（14 个 12-bit 加法器）、`s1_dual9`(144 bit) 与 `s2_r0/r1`(24 bit) 等新增流水寄存器（FF 172→356）。

### 3.2 面积估算（GE 口径）

GE 权重沿用 §3 历史口径（2 输入 NAND 等效，低/高）：

| 单元 | 三模式数量 | 低权重 | 高权重 | 低 GE | 高 GE |
|---|---|---|---|---|---|
| AND2 | 2954 | 1.0 | 1.5 | 2954 | 4431 |
| OR2 | 1054 | 1.0 | 1.5 | 1054 | 1581 |
| XOR2 | 2315 | 1.5 | 2.5 | 3472.5 | 5787.5 |
| MUX2 | 576 | 2.0 | 3.0 | 1152 | 1728 |
| INV | 172 | 0.5 | 1.0 | 86 | 172 |
| SDFF | 356 | 4.0 | 6.0 | 1424 | 2136 |
| **合计** | 7427 | — | — | **≈10.1k** | **≈15.8k** |

即三模式 **约 10.1k–15.8k GE（中值 ≈12.9k）**；INT8 单模式为 5.35k–8.38k GE（中值 ≈6.9k）。**相对单模式约 +89%**（单元数 +77%，GE 更高是因为新增 MUX 与 XOR 权重较大）。

按 MAC 折算更说明问题：三模式单周期 8/16/16 MAC，若只看"每 MAC 的乘法器面积"，INT8 为 512 部分积/8 MAC = 64/MAC，INT4 为 256 部分积/16 MAC = 16/MAC，即 **INT4 的单位 MAC 乘法器面积只有 INT8 的 1/4**。

### 3.3 逻辑深度

`ltp -noff` 对三模式报 **最长寄存器到寄存器路径 25 级**，起点 `s1_prod8[1][1]`、终点 `s2_sum8[15]`，与单模式（`s1_prod[1][1]`→`s2_sum[15]`）**同深度、同终点**。

即：**新增的 INT4/三值路径没有进入关键路径**。原因是它们更窄（4×4 乘法、12-bit 树），深度小于 INT8 的 20-bit 树，因此插入后不拉长 R2R。WB 端新增的 128-bit 输出 MUX 只影响写回口本身的组合延迟，不影响寄存器间最坏路径。

> 该深度是 generic 门级拓扑长度，**不是 ns**；真实面积/时序需 PDK 库 + DC/Genus（B4 仍部分关闭）。

---

## 4. 清理后的全量回归

| 项 | 结果 | 日志 |
|---|---|---|
| 单元回归（3047 条，三模式 + 非法/vl=0/边界/随机） | **3047 / 3047 PASS** | `docs/phase2/logs/03_unit_test.log` |
| 延迟 / 吞吐 | 3 cycle / 1.0 inst·cycle⁻¹（INT8/INT4/三值均 1.0） | `03_rtl_full_perf.log` |
| 行覆盖率 | **55 / 55 = 100%** | `docs/phase2/logs/07_coverage.log` |
| NEMU 自测 | **3032 用例 / 4551 结果字，0 fail**，退出码 0 | `docs/phase3/01_nemu_cosim.log` |
| RTL ↔ NEMU | **4551 vs 4551，mismatch 0** | `docs/phase3/02_cosim.log` + `docs/phase3/02_rtl_export.txt` |
| RVV 组合基线（INT8） | **1513 / 1513**，数据通路 6→1 | `docs/phase3/03_baseline_nemu.log` |
| Chisel ↔ Verilog 等价 | **3047 / 3047**，3 cycle | `docs/phase2/logs/09_chisel_equiv.log` |

> NEMU 协同仿真按模式分组：INT8 1513 用例、INT4 759、三值 760；双结果用例每例比对 r0/r1 两个字，故结果字总数为 4551。边界自检覆盖三种模式的 `vl=0` 不写回与 4 类非法配置。

> `docs/phase3/04_rtl_unit_perf.log` 中 `latency_illegal : 0 cycle` 是因为该次运行使用 1513 条**写回子集**（不含非法用例），非功能异常；全量 3047 条运行的该项为 3 cycle，见 `03_rtl_full_perf.log`（旧版为 1518 条）。

---

## 5. 加速分析：指令数、结构模型与系统实测

### 5.1 指令数（NEMU 实测，同一 1513 条 INT8 用例镜像）

| 指标 | vdot.vv | RVV 组合基线 | 比值 |
|---|---|---|---|
| 向量数据通路指令 / 用例 | 1 | 6 | **6.0×** |
| 单用例核心指令（含 2×`vle8.v` 与 `vsetvli`） | 7 | 14 | 2.0× |
| 全镜像动态指令数 | 78,701 | 89,294 | −11.9%（基线多 13.5%） |

### 5.2 周期模型

假设（**显式列出，便于评审质疑**）：香山向量 ALU 每条 1 uop、3 cycle 延迟、1 条/cycle 吞吐；`vle8.v` 两条可并行、不计入 ALU 链。

| 路径 | 组成 | 模型延迟 |
|---|---|---|
| `vdot.vv` | 1 个 uop | **3 cycle** |
| 基线 | `vsext.vf2`(e8→e16) → `vsext.vf2`(e16→e32) → `vmul.vv` → `vredsum.vs`（4 个串行向量操作） | **12 cycle** |

- 单点积延迟比：12 / 3 = **4.0×**
- 稳态吞吐比：6 / 1 = **6.0×**
- 全镜像动态指令比：89,294 / 78,701 = **1.13×**（含 UART 打印等脚手架开销，为保守下界）

> 模型口径对齐：本节 12→3 cycle / 4.0× 是**简化模型**（4 条串行指令各计 3 cycle，不区分 m1/m2 beat 数）；
> `docs/phase3/perf_analysis.md` §3 的 uop-beat 模型按 8-lane 基线计 15–22 cycle，给出 **5–7×**，更保守。
> 两者都是估算，对外只引用 §5.3 的实测 9.8×（lane 公平）/11.8×（16-lane 上界）。

同一次运行内：NEMU 指令数（实测）+ 上述周期模型（推演）互相独立，方向一致。

### 5.3 香山昆明湖 V2 emu 实测（2026-11-03）

四个内核在同一 emu（`DefaultConfig`，昆明湖 V2 基线）下跑 difftest（NITER=2000，`PERF result=OK`），口径 `per_iter=(C_k−C_empty)/NITER`：

| 内核 | instrCnt | cycleCnt | per-iter (cycle) |
|---|---|---|---|
| empty（循环骨架） | 4,118 | 11,108 | — |
| vdot | 6,118 | 12,123 | 0.5075 |
| RVV 组合基线 | 8,119 | 23,109 | 6.0005 |
| 标量基线 | 38,135 | 21,022 | 4.957 |

- 相对标量：4.957 / 0.5075 = **9.8×**（标量恰做 8 个乘积，lane 公平）；相对 RVV：6.0005 / 0.5075 = **11.8×**（RVV 内核为 VLMAX=16、2× lane 工作量，属上界）。
- 时间主要花在循环骨架与 UART 输出上，故加速比小于纯指令数比（6:1）——这是端到端负载的真实占比。
- 日志：`docs/phase2/logs/xs_emu_perf_{empty,vdot,rvv,scalar}.log`；方法学与局限见 `docs/phase3/perf_analysis.md` §6。
- 5.2 的 4.0× 延迟 / 6.0× 吞吐仍属结构模型，**不得作为实测结论引用**。

---

## 6. 与阶段三结论的差异说明

| 项 | 阶段三 | 阶段四 | 原因 |
|---|---|---|---|
| RTL 代码 | 含死逻辑 | 已清理；并扩展为 INT8/INT4/三值三模式 | lint 门禁 + 差异化路线 |
| 功能/协同仿真 | 1518 / 1513 / 0 mismatch | 3047 / 3032 用例 / 4551 字 / 0 mismatch | 三模式扩展 |
| 综合数据 | 无 | 三模式 7427 单元 / 356 FF / 25 级（INT8 单模式 4187 / 172 / 25） | 已装 yosys 0.52 完成三模式综合 |
| 加速结论 | 指令数比 6:1 | 补 4.0× 延迟模型、6.0× 吞吐模型；系统级实测 9.8×（lane 公平）/11.8×（16-lane 上界） | 补答辩所需口径 |
| 向量吞吐 | 8 MAC/cycle | 8 / 16 / 16（INT8/INT4/三值） | 差异化创新 |

---

## 7. 未关闭项

| 编号 | 项 | 状态 |
|---|---|---|
| B1 | `xs-env` + RISC-V 工具链 | **已关闭（2026-11-01）**：`.tools/` 手工等价部署 + 香山 `16ae9dd` 的 emu 已构建，阶段一 hello/vadd 波形已入库 |
| B2 | 香山内集成与回归 | **已关闭（2026-11-03）**：I1–I7 完成，RTL 重生成 + emu 重建；定向 7/7 difftest 0 mismatch、非法 5/5 |
| B3 | 平台真实加速比 | **已关闭（2026-11-03）**：emu 实测 9.8×（对标量，8-lane 公平）/ 11.8×（对 RVV，16-lane，属上界），NITER=2000，见 `docs/phase3/perf_analysis.md` §6 |
| B4 | PDK 面积与时序签核 | **部分关闭**：generic 规模/深度已取得（三模式 7427 单元 / 356 FF / 25 级）；µm² 与 ns 仍需 PDK 库与 DC/Genus |
| B5 | 三模式综合面积 | **已关闭（2026-11-10）**：`docs/phase4/06_yosys_synth_3mode.log`，7427 单元 / 356 FF / 25 级；INT8 对照见 `05_yosys_synth_int8_recheck.log` |
| B6 | INT4/三值的系统级 emu | **未关闭**：三模式 Scala 已编译 PASS，单元 + NEMU + Chisel 已闭环；emu 全量重建后可补跑 |

> 表述口径（2026-11-03 更新）：B2/B3 关闭后，可以宣称"`vdot` 已在香山昆明湖 V2 的 `emu`（Verilator）+ difftest 环境验证，并取得实测加速比 9.8×（lane 公平）/11.8×（16-lane 上界）"。仍不得宣称：PDK 级面积/时序（B4 未关闭）、真实频率下的绝对性能、FPGA/流片结果。

---

## 8. 附件与复现

| 文件 | 内容 |
|---|---|
| `docs/phase4/06_yosys_synth_3mode.log` | **三模式**综合全过程、单元统计、最长路径 |
| `docs/phase4/05_yosys_synth_int8_recheck.log` | INT8 单模式复核（4187 单元，校验工具链口径） |
| `docs/phase4/01_yosys_synth.log` | 历史单模式综合日志（4186 单元，保留存档） |
| `docs/phase4/02_verilator_lint.log` | 严格 lint 结果（0 告警） |
| `docs/phase4/03_rtl_full_perf.log` | 3047 条全量回归与延迟/吞吐 |
| `docs/phase4/04_nemu_cosim_after_clean.log` | NEMU 自测 + RTL↔NEMU diff（清理后，INT8 1513 条） |
| `docs/phase3/01_nemu_cosim.log` | 三模式 NEMU 协同（3032 用例 / 4551 字） |
| `docs/phase2/logs/09_chisel_equiv.log` | Chisel ↔ Verilog 三模式等价回归（3047/3047） |
| `patches/nemu-vdot.patch` | NEMU 三模式译码/执行改动（170 行，3 个文件） |
| `patches/xiangshan-vdot.patch` | 香山三模式集成补丁（译码 + `VDotUnit` + 配置） |
| `docs/phase4/05_baseline_after_clean.log` | 基线等价性与指令数（清理后） |

```bash
# 1) RTL 严格 lint
.tools/verilator/bin/verilator --lint-only -Wall -Wno-DECLFILENAME rtl/verilog/VDot.v --top-module VDot

# 2) 全量单元回归（构建 + 3047 条三模式 + 波形）
bash scripts/run_unit_tests.sh

# 3) NEMU 协同仿真（含 RTL 导出与 diff）
python3 tests/run_nemu_cosim.py --out /tmp/cosim.log
./build/obj_dir/tb_vdot build/nemu/cosim_vectors.txt - /tmp/rtl_export.txt
python3 tests/run_nemu_cosim.py --rtl-export /tmp/rtl_export.txt --out /tmp/cosim.log

# 4) 基线等价性
python3 tests/run_nemu_baseline.py

# 5) generic 综合（已装 .tools/yosys，见 §3）
export PATH="$PWD/.tools/yosys/usr/bin:$PATH" YOSYS_DATDIR="$PWD/.tools/yosys/usr/share/yosys"
yosys -p "read_verilog -sv rtl/verilog/VDot.v; synth -top VDot -noabc; techmap; opt; splitnets -ports; opt; ltp -noff; stat"
```

---

## 9. 环境迁移后的复现状态（2026-11-01）

工作区已迁至 `/home/dbqxxs/xsriscv/cieriscv`。按"哪些证据能复跑"重新核对：

| 项 | 当前状态 | 说明 |
|---|---|---|
| 单元回归 3047 条（三模式） | **可复跑，PASS** | 3047/3047、3 cycle、三模式 1 inst/cycle、覆盖率 55/55 |
| 严格 lint | **可复跑，PASS** | 0 告警 0 错误 |
| NEMU 三模式协同 | **可复跑，PASS** | 3032 用例 / 4551 字，`mismatch=0`，boundary 三模式 PASS |
| Chisel 三模式等价 | **可复跑，PASS** | 3047/3047 |
| RVV 组合基线（INT8） | **可复跑，PASS** | 1513/1513，`alu_op_ratio 6.0x` |
| 一键回归 | **可复跑，PASS** | `bash scripts/run_all.sh` → `ALL : PASS` |
| 香山 Scala 编译（三模式） | **可复跑，PASS** | `mill -i xiangshan.compile`，573 任务 0 error |
| generic 综合（§3） | **可复跑** | 本机 `.tools/yosys`（0.52-2 deb 解包），见 §3 命令 |
| 三模式综合面积（B5） | **已关闭** | `06_yosys_synth_3mode.log`：7427 单元 / 356 FF / 25 级 |
| 香山平台实测（§7 B2–B3） | **INT8 已闭环（2026-11-03）** | 定向 7/7、非法 5/5、四内核 9.8×/11.8×；INT4/三值 emu 待重跑（B6） |

迁移暴露并已修复的缺陷：`build/obj_dir` 内的旧 Makefile 写死旧工作区绝对路径，导致 `make` 报"没有规则可制作目标"；`scripts/build_sim.sh` 已增加陈旧构建目录自动清理（路径不符即重建）。

> 上述复跑不改变 §3 的综合数字与 §5.1/§5.2 的模型口径：它们仍是"历史证据 + 结构推演"，不是当前环境的重新测量；§5.3 是 2026-11-03 的 emu 实测。
