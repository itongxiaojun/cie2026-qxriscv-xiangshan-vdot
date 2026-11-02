# 阶段四 · RTL 收口、综合评估与加速模型报告

> 项目：2026CIE · qxriscv · xiangshan-vdot
> 对应进度表 T4.1–T4.4；所有数字均来自 `docs/phase4/` 下日志，可复现。
> 口径声明：本报告的面积/延迟均为 **generic 工艺无关综合** 与 **结构模型推演**，不是 PDK 签核结果，也不构成平台实测加速比。

---

## 1. 目的与范围

| 目标 | 手段 | 结论 |
|---|---|---|
| 清除 RTL 中的死逻辑，消除严格 lint 告警 | Verilator `--lint-only -Wall` + 人工复核 | 告警 4 → 0（仅 1 处语义性豁免，见 §2.3） |
| 证明清理未改变功能 | 全量单元回归 + NEMU/RTL 协同仿真 + 基线复跑 | 1518/1518、1513/1513、0 mismatch，全部 PASS |
| 取得面积与逻辑深度量级 | yosys 0.52 generic 综合（`synth -noabc; techmap`） | 4186 单元 / 172 FF / 最长 R2R 路径 25 级 |
| 给出可辩护的"有/无该指令"差异 | 指令数实测 + 依赖链/吞吐结构模型 | 数据通路 6→1；模型延迟 12→3 cycle |

**不在范围**：PDK 映射后的面积（µm²）、时序签核（ns/GHz）、香山平台真实周期与加速比。原因见 §7。

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

`in_vs1[127:64]`、`in_vs2[127:64]` 未使用属**设计意图**（本指令只取低 64 bit 的 8 个 int8）。已在端口处就地豁免 `UNUSEDSIGNAL` 并写明原因，避免用全文件级豁免掩盖将来真实问题。

### 2.3 Lint 结果

`.tools/verilator/bin/verilator --lint-only -Wall -Wno-DECLFILENAME rtl/verilog/VDot.v --top-module VDot`

- 修复前：4 条 `UNUSEDSIGNAL` 告警 → `%Error`
- 修复后：**0 告警 0 错误**（日志 `02_verilator_lint.log`）

---

## 3. 综合评估（generic）

- 工具：Yosys 0.52（Debian 包本地解包运行，未安装、未改系统）
- **当前环境（2026-11-01 迁移后）未安装 yosys**：本节数据来自历史日志 `01_yosys_synth.log`，可审阅但**不可在本机复跑**；复跑需先提供 yosys 0.52+。
- 流程：`read_verilog -sv` → `synth -top VDot -noabc` → `techmap` → `opt` → `ltp -noff` → `stat`
- 说明：`abc` 二进制缺失，故以 `techmap/simplemap` 映射到 2 输入通用门；结果比 ABC 优化后保守。

### 3.1 规模

| 项 | 数量 |
|---|---|
| 通用单元总数 | **4186** |
| `$_AND_` | 1929 |
| `$_XOR_` | 1362 |
| `$_OR_` | 655 |
| `$_NOT_` | 68 |
| `$_SDFF_PP0_`（同步复位 FF） | **172** |

### 3.2 面积估算（GE 口径）

GE 权重按常用 2 输入 NAND 等效口径给出区间（低/高）：

| 单元 | 数量 | 低权重 | 高权重 | 低 GE | 高 GE |
|---|---|---|---|---|---|
| AND2 | 1929 | 1.0 | 1.5 | 1929 | 2893.5 |
| OR2 | 655 | 1.0 | 1.5 | 655 | 982.5 |
| XOR2 | 1362 | 1.5 | 2.5 | 2043 | 3405 |
| INV | 68 | 0.5 | 1.0 | 34 | 68 |
| SDFF | 172 | 4.0 | 6.0 | 688 | 1032 |
| **合计** | 4186 | — | — | **≈5.35k** | **≈8.38k** |

即 **约 5.3k–8.4k GE（中值 ≈6.9k）**。数量级与结构相符：8 个有符号 8×8 乘法器 + 7 个 20 bit 加法器 + 172 bit 流水寄存器。

FF 结构上限为 187 bit（`s1_prod` 128 + 控制 4 + `s2_sum` 20 + 输出 32 + 状态 3），综合后 172 bit，差值来自常量折叠与等价寄存器合并。

### 3.3 逻辑深度

`ltp -noff` 报 **最长寄存器到寄存器路径 25 级**，起点为 `s1_prod[1][1]`、经 `maccmap` 全加器压缩树到达 `s2_sum`，即 **EX2 加法树是时序关键级**，而非 EX1 乘法。

> 该深度是 generic 门级拓扑长度，**不是 ns**；真实深度需 PDK 库 + DC/Genus 才能给出。25 级对 20 bit、8 操作数归约属于正常范围（3 层加法器经压缩树折叠）。

---

## 4. 清理后的全量回归

| 项 | 结果 | 日志 |
|---|---|---|
| 单元回归（1518 条，含非法/vl=0/边界/随机） | **1518 / 1518 PASS** | `docs/phase2/logs/03_unit_test.log` |
| 延迟 / 吞吐 | 3 cycle / 1.0 inst·cycle⁻¹；1024 条背靠背 10148 cycle | `03_rtl_full_perf.log` |
| NEMU 自测 | **1513 / 1513，0 fail**，退出码 0 | `04_nemu_cosim_after_clean.log` |
| RTL ↔ NEMU | **1513 vs 1513，mismatch 0** | 同上 + `04_rtl_export_after_clean.txt` |
| RVV 组合基线 | **1513 / 1513**，数据通路 6→1 | `05_baseline_after_clean.log` |

> `docs/phase3/04_rtl_unit_perf.log` 中 `latency_illegal : 0 cycle` 是因为该次运行使用 1513 条**写回子集**（不含非法用例），非功能异常；全量 1518 条运行的该项为 3 cycle，见 `03_rtl_full_perf.log`。

---

## 5. 加速模型（结构推演，非实测）

### 5.1 指令数（NEMU 实测，同一 1513 用例镜像）

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

同一次运行内：NEMU 指令数（实测）+ 上述周期模型（推演）互相独立，方向一致。

---

## 6. 与阶段三结论的差异说明

| 项 | 阶段三 | 阶段四 | 原因 |
|---|---|---|---|
| RTL 代码 | 含死逻辑 | 已清理 | lint 门禁触发 |
| 功能/协同仿真 | 1518 / 1513 / 0 mismatch | 同左，重跑确认 | 清理不改变语义 |
| 综合数据 | 无 | 4186 单元 / 172 FF / 25 级 | 新增 yosys 评估 |
| 加速结论 | 指令数比 6:1 | 补 4.0× 延迟模型、6.0× 吞吐模型 | 补答辩所需口径 |

---

## 7. 未关闭项

| 编号 | 项 | 状态 |
|---|---|---|
| B1 | `xs-env` + RISC-V 工具链 | **已关闭（2026-11-01）**：`.tools/` 手工等价部署 + 香山 `16ae9dd` 的 emu 已构建，阶段一 hello/vadd 波形已入库 |
| B2 | 香山内集成与回归 | **待实施**（环境已就绪，依赖的 B1 已关闭） |
| B3 | 平台真实加速比 | **待实施**（需先完成 B2；现有模型 + 指令级数据） |
| B4 | PDK 面积与时序签核 | **部分关闭**：generic 规模/深度已取得；µm² 与 ns 仍需 PDK 库与 DC/Genus |

> 对外表述约束不变：B2/B3 关闭前，不得宣称"`vdot` 已在香山平台验证"，不得给出实测加速比。

---

## 8. 附件与复现

| 文件 | 内容 |
|---|---|
| `docs/phase4/01_yosys_synth.log` | generic 综合全过程、单元统计、最长路径 |
| `docs/phase4/02_verilator_lint.log` | 严格 lint 结果（0 告警） |
| `docs/phase4/03_rtl_full_perf.log` | 1518 条全量回归与延迟/吞吐 |
| `docs/phase4/04_nemu_cosim_after_clean.log` | NEMU 自测 + RTL↔NEMU diff（清理后） |
| `docs/phase4/04_rtl_export_after_clean.txt` | RTL 逐用例 128 bit 结果 |
| `docs/phase4/05_baseline_after_clean.log` | 基线等价性与指令数（清理后） |

```bash
# 1) RTL 严格 lint
.tools/verilator/bin/verilator --lint-only -Wall -Wno-DECLFILENAME rtl/verilog/VDot.v --top-module VDot

# 2) 全量单元回归（构建 + 1518 条 + 波形）
bash scripts/run_unit_tests.sh

# 3) NEMU 协同仿真（含 RTL 导出与 diff）
python3 tests/run_nemu_cosim.py --out /tmp/cosim.log
./build/obj_dir/tb_vdot build/nemu/cosim_vectors.txt - /tmp/rtl_export.txt
python3 tests/run_nemu_cosim.py --rtl-export /tmp/rtl_export.txt --out /tmp/cosim.log

# 4) 基线等价性
python3 tests/run_nemu_baseline.py

# 5) generic 综合（需 yosys；本环境为 deb 本地解包，见 §3）
yosys -p "read_verilog -sv rtl/verilog/VDot.v; synth -top VDot -noabc; techmap; opt; ltp -noff; stat"
```

---

## 9. 环境迁移后的复现状态（2026-11-01）

工作区已迁至 `/home/dbqxxs/xsriscv/cieriscv`。按"哪些证据能复跑"重新核对：

| 项 | 当前状态 | 说明 |
|---|---|---|
| 单元回归 1518 条 | **可复跑，PASS** | 1518/1518、3 cycle、1 inst/cycle、`total_cycles 10148` |
| 严格 lint | **可复跑，PASS** | 0 告警 0 错误 |
| NEMU 自测 + RTL↔NEMU | **可复跑，PASS** | 1513 vs 1513，`mismatch=0` |
| RVV 组合基线 | **可复跑，PASS** | 1513/1513，`alu_op_ratio 6.0x` |
| 一键回归 | **可复跑，PASS** | `bash scripts/run_all.sh` → `ALL : PASS` |
| generic 综合（§3） | **不可复跑** | 当前环境无 yosys；数据引用历史日志 `01_yosys_synth.log` |
| 香山平台实测（§7 B2–B3） | **待实施** | 环境已就绪（香山 `16ae9dd` 的 emu 已构建）；需先完成 `vdot` 集成（B2）再测量 |

迁移暴露并已修复的缺陷：`build/obj_dir` 内的旧 Makefile 写死旧工作区绝对路径，导致 `make` 报"没有规则可制作目标"；`scripts/build_sim.sh` 已增加陈旧构建目录自动清理（路径不符即重建）。

> 上述复跑不改变 §3 的综合数字与 §5 的模型口径：它们仍是"历史证据 + 结构推演"，不是当前环境的重新测量。
