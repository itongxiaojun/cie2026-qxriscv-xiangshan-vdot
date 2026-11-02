# cie2026-qxriscv-xiangshan-vdot

2026CIE 全国 RISC-V 高水平创新及应用大赛参赛作品：面向边缘 AI 推理的**香山昆明湖 V2 自定义向量点积指令 `vdot.vv`**。

- 目标平台：香山（XiangShan）昆明湖 V2
- 指令约束：`SEW = 8`，`VLEN = 128`，分组长度 `K = 8`
- 交付范围：环境验证 → 指令语义与 RTL 实现 → NEMU 协同仿真与性能分析

## 项目状态

| 阶段 | 内容 | 状态 |
|---|---|---|
| 阶段一 | 环境部署、`hello` 输出、vadd 波形分析 | **完成**：香山 `16ae9dd` 的 emu 已构建；真实 UART 输出 `hello xiangshan, I am qxriscv, IP address: 192.168.0.168`；4 份原始日志 + vadd 波形与逐 cycle 分析已入库（[env.md](docs/phase1/env.md)、[vadd_wave.md](docs/phase1/vadd_wave.md)） |
| 阶段二 | vdot.vv 设计文档、RTL、正/负/边界测试 | **设计 + RTL + 单元级验证完成**（1518/1518 PASS）；香山内集成待实施 |
| 阶段三 | NEMU 扩展、协同仿真、基线对比与加速分析 | **NEMU 扩展 + 协同仿真完成**（1513/1513，RTL↔NEMU 0 mismatch）；单元级实测 3 cycle / 1.0 inst/cycle；平台实测待集成后实施 |
| 阶段四 | RTL 收口、综合评估、加速模型与提交 | **收口完成**：严格 lint 0 告警；generic 综合 4186 单元 / 172 FF / 最长路径 25 级（≈5.3k–8.4k GE）；加速模型 4.0× 延迟、6.0× 吞吐；PDK 签核与提交待实施 |

### 已完成并验证（模块级 RTL 仿真 + NEMU 协同仿真）

| 项 | 结果 | 证据 |
|---|---|---|
| 用例通过率 | **1518 / 1518**（含正数、负数、8 类边界、配置异常、1500 随机） | [测试报告](docs/phase2/test_report.md) |
| 背靠背流式 | 1024 / 1024，按序比对 | 同上 |
| 延迟 / 吞吐 | 3 cycle / 1.0 inst/cycle | 同上 |
| 三方模型一致性 | Python / C / C++ 内联，1518 条一致 | `docs/phase2/logs/06_c_model_crosscheck.log` |
| 基线（RVV 组合）功能等价 | 1513 / 1513 | `docs/phase3/00_baseline_equiv.log` |
| NEMU 内 `vdot.vv` 语义 | **1513 / 1513**，0 fail | [01_nemu_cosim.log](docs/phase3/01_nemu_cosim.log) |
| RTL ↔ NEMU 协同仿真 | **1513 vs 1513，mismatch 0** | [02_rtl_export.txt](docs/phase3/02_rtl_export.txt) |
| 基线在 NEMU 上跑通 | **1513 / 1513**，6→1 数据通路指令 | [03_baseline_nemu.log](docs/phase3/03_baseline_nemu.log) |
| 单元级时序实测 | 3 cycle / 1.0 inst·cycle⁻¹（1024 条背靠背；全量 1518 条回归总 10148 cycles） | [03_rtl_full_perf.log](docs/phase4/03_rtl_full_perf.log) |
| 严格 lint | **0 告警 0 错误**（`-Wall`，仅 1 处语义性豁免） | [02_verilator_lint.log](docs/phase4/02_verilator_lint.log) |
| generic 综合 | 4186 单元 / 172 FF；最长 R2R 路径 **25 级**（EX2 加法树）；**≈5.3k–8.4k GE** | [01_yosys_synth.log](docs/phase4/01_yosys_synth.log)（历史证据，当前环境无 yosys，暂不可复跑） |
| 波形 | `docs/phase2/waveform/vdot_unit.vcd` | — |

> **表述约束**：以上均为**功能单元模块级**仿真与 **NEMU 指令集模拟器**结果。香山昆明湖 V2 内集成与真实加速比**尚未执行**，不得表述为"已在香山平台验证"或给出实测加速比。

## 当前环境（2026-11-01）

工作区已迁移到 `/home/dbqxxs/xsriscv/cieriscv`，主机为 Debian 13 / 48 核 / 31 GiB。工具可用性决定哪些证据能复跑：

| 组件 | 状态 | 可复跑的内容 |
|---|---|---|
| Python 3.13 / gcc 14.2 / Make 4.4 | 可用 | 参考模型、向量、C 交叉比对 |
| Verilator 5.034（`.tools/verilator`） | 可用 | 1518 条单元回归、严格 lint |
| NEMU（`.tools/nemu`，`a683e0b` + 补丁） | 可用 | 1513 条自测、RTL↔NEMU diff、基线计数 |
| yosys | **缺失** | generic 综合**暂不可复跑**（保留历史日志） |
| RISC-V GCC（`.tools/riscv`） | **可用** | `riscv-none-elf-gcc` 15.2.0；阶段一裸机镜像 |
| 香山源码 + emu（`build/xs-work/XiangShan`） | **可用** | 香山 `16ae9dd`；`build/emu` 已构建，阶段一 hello / vadd 波形已复跑 |
| JDK / mill（`.tools/`） | **可用** | Temurin 21.0.13 / mill 0.12.3；香山 RTL 生成 |
| sbt / Scala | **缺失** | Chisel 版仍未编译校验 |

完整清点与版本锁定见 [docs/phase1/env.md](docs/phase1/env.md)。

## 仓库结构

```
.
├── README.md
├── doc/                 # 赛题官方材料（提交要求、赛题资料、提交流程指南）
├── ipd/                 # IPD 流程文档集（方案、规格、测试方案、计划、对照表）
├── docs/                # 阶段交付文档与证据
│   ├── PROGRESS.md      # 任务进度跟踪表（Living Document，持续更新）
│   ├── phase1/          # 环境与执行记录、运行日志（logs/）、vadd 波形截图（wave/）与分析文档
│   ├── phase2/          # 设计文档、测试报告、日志、波形
│   ├── phase3/          # 协同仿真报告、基线日志、单元级性能日志（含估算口径声明）
│   └── phase4/          # RTL 收口、lint、generic 综合、加速模型报告与日志
├── rtl/
│   ├── verilog/VDot.v   # 已验证的模块级 RTL（SystemVerilog 语法）
│   └── chisel/VDot.scala# 香山集成用的 Chisel 骨架（未编译校验）
├── patches/
│   ├── nemu-vdot.patch  # NEMU 扩展补丁（3 文件，+44 行）
│   └── xiangshan-vdot-integration.md  # 香山集成说明（规程，未执行）
├── tests/
│   ├── ref_vdot.py      # Python golden model
│   ├── ref_baseline.py  # 基线指令序列的语义等价模型
│   ├── model/vdot_ref.c # C 参考模型（NEMU-ready）
│   ├── as/mini_asm.py   # 纯 Python 的 RISC-V/RVV 汇编器（不依赖外部工具链生成镜像）
│   ├── run_nemu_cosim.py    # NEMU 自测 + 协同仿真 + RTL 结果导出
│   ├── run_nemu_baseline.py # RVV 组合基线在 NEMU 上跑通并计数
│   ├── gen_vectors.py   # 向量生成（定向 + 随机 + 边界密集）
│   ├── tb/tb_vdot.cpp   # Verilator C++ 测试台
│   └── vectors/         # 1518 条测试向量
└── scripts/             # 一键构建与回归
```

> 工作区内另有 `openTPU-main/`（开源 AI 加速器参考代码），仅在本地用于对照阅读，已被 `.gitignore` 排除，不随仓库分发、也不属于本项目交付物。

## 方案与交付文档

| 文档 | 内容 |
|---|---|
| [项目章程与总体方案](ipd/00_项目章程与总体方案.md) | 赛题解读、目标与范围、IPD 阶段与门径、角色分工、风险登记册 |
| [vdot 指令与微架构设计规格书](ipd/01_vdot指令与微架构设计规格书.md) | 精确语义、位宽推导、数据通路、流水时序、香山集成点、ADR |
| [测试与验证方案](ipd/02_测试与验证方案.md) | 分层验证策略、用例矩阵、协同仿真、性能测量方法学 |
| [开发计划、WBS 与里程碑](ipd/03_开发计划_WBS与里程碑.md) | 4 周排期、WBS、门禁、降级预案 |
| [评审对照与提交检查表](ipd/04_评审对照与提交检查表.md) | 官方要求 → 交付物映射、提交清单、录屏与 PPT 脚本 |
| [阶段二设计文档](docs/phase2/design.md) | 提交版：指令语义、微架构、数据通路、RTL 结构、追溯 |
| [阶段一环境与执行记录](docs/phase1/env.md) | 当前环境基线、版本锁定、构建耗时、1.1/1.2/1.3 执行结果；旧环境历史（仅追溯） |
| [阶段一 vadd 波形分析](docs/phase1/vadd_wave.md) | 按波形逐 cycle 讲解取指→译码→发射→向量执行→写回，含逐字节核对与复现命令（截图 `docs/phase1/wave/vadd_pipeline_wave.png`） |
| [阶段一原始日志](docs/phase1/logs/01_env_setup.log) | `01` 环境与 emu 构建、`02` hello 运行、`03` vadd 波形采集、`04` 波形解析 |
| [阶段二测试报告](docs/phase2/test_report.md) | 1518 条用例结果、时序实测、断言、缺陷记录、未验证项 |
| [香山集成说明](patches/xiangshan-vdot-integration.md) | 集成规程与核对表（**未执行**） |
| [NEMU 扩展补丁](patches/nemu-vdot.patch) | 阶段三提交版：`vdot.vv` 译码 + 执行语义（3 文件，+44 行） |
| [阶段三协同仿真报告](docs/phase3/cosim_report.md) | NEMU 扩展改动、1513 条协同仿真、基线对比、单元级实测与缺陷记录 |
| [阶段四收口与综合报告](docs/phase4/release_report.md) | RTL 死逻辑清理、严格 lint、generic 综合与 GE 估算、加速模型与剩余阻塞 |
| [阶段三性能分析](docs/phase3/perf_analysis.md) | 基线定义与等价性、延迟/吞吐估算、平台实测协议（**估算部分非实测**） |
| [任务进度跟踪表](docs/PROGRESS.md) | 里程碑、官方交付对照、详细任务、阻塞项与变更记录（持续更新） |

## 关键设计结论（摘要）

1. `vdot.vv` 对两个源寄存器的低 64 bit 内 8 个 int8 做有符号点积，结果写入 `vd[31:0]`，`vd[127:32]` 清零。
2. 8 项和的范围为 `[-130048, +131072]`，**必须 ≥19 bit 有符号累加**；内部取 20 bit，输出 32 bit。
3. 微架构为新增单 uop、无状态、全流水的 `VDot` 功能单元，接入香山既有向量发射/写回框架，不新增流水线。

## 复现

```bash
# 一键回归：Python 模型自检 -> 生成向量 -> C 模型交叉比对 -> 构建 -> RTL 仿真 -> 归档日志与波形
bash scripts/run_unit_tests.sh
```

全链路（含 lint、NEMU 协同仿真与基线）：

```bash
bash scripts/run_all.sh    # 任一步失败即返回非 0；末行打印 ALL : PASS / FAIL
```

依赖：`python3`、`gcc`、Verilator（脚本依次探测 `verilator-inst/`、`.tools/verilator/`、系统 PATH），NEMU 已构建于 `.tools/nemu/build/`。

> 工作区迁移后，`build/obj_dir` 里残留的 Makefile 会写死旧目录的绝对路径，导致构建报"没有规则可制作目标"。[scripts/build_sim.sh](scripts/build_sim.sh) 会自动识别并清理这类陈旧产物，无需手工删除 `build/`。

预期输出：

```
cases_total      : 1518
cases_pass       : 1518
cases_fail       : 0
latency_write    : 3 cycle
throughput       : 1 inst/cycle
RESULT           : PASS
```

### 阶段三：NEMU 协同仿真

```bash
# 1) 应用扩展补丁并构建 NEMU（首次或补丁变更后）
git -C .tools/nemu apply ../../patches/nemu-vdot.patch   # 已在源码树中时跳过
make -C .tools/nemu -j"$(nproc)" NEMU_HOME="$(cd .tools/nemu && pwd)" LIBRARY_PATH=/tmp/sdllib

# 2) NEMU 自测 + 导出 1513 条写回结果（喂给 tb_vdot）
python3 tests/run_nemu_cosim.py --rtl-export docs/phase3/02_rtl_export.txt

# 3) RTL 侧跑同一顺序的用例并导出结果
bash scripts/build_sim.sh
./build/obj_dir/tb_vdot build/nemu/cosim_vectors.txt - docs/phase3/02_rtl_export.txt

# 4) RVV 组合基线在 NEMU 上跑通并计数
python3 tests/run_nemu_baseline.py
```

预期输出：`cases_fail 0`、`rtl_vs_nemu : lines=1513/nemu=1513 mismatch=0`、`alu_op_ratio : 6.0x`，均以 `RESULT : PASS` 结尾。

> `tests/as/mini_asm.py` 是本项目自带的最小 RISC-V/RVV 汇编器，用于生成平面镜像（不依赖交叉汇编器）。

### 阶段四：RTL 质量门禁与综合评估

```bash
# 严格 lint（0 告警 0 错误为通过）
.tools/verilator/bin/verilator --lint-only -Wall -Wno-DECLFILENAME rtl/verilog/VDot.v --top-module VDot

# generic 综合评估（需 yosys；无 PDK 库，输出为工艺无关规模与逻辑深度）
yosys -p "read_verilog -sv rtl/verilog/VDot.v; synth -top VDot -noabc; techmap; opt; ltp -noff; stat"
```

预期：lint 无输出告警；综合 `Number of cells: 4186`、`Longest topological path ... (length=25)`。

## 版本锁定

| 组件 | 版本 / commit |
|---|---|
| 工作区 | `/home/dbqxxs/xsriscv/cieriscv`（2026-11-01 迁移到当前主机） |
| xs-env | 未装官方镜像；`.tools/` 手工等价部署（Temurin JDK 21.0.13、mill 0.12.3、xPack GCC 15.2.0、Verilator 5.034） |
| XiangShan | `16ae9ddcda54fc9a2fddffad73174cf793ac7814`（2025-04-03，昆明湖 V2）；子模块见 [env.md](docs/phase1/env.md) §5.1 |
| RISC-V GCC | xPack `riscv-none-elf-gcc` 15.2.0 / objcopy 2.45（`.tools/riscv`） |
| difftest 参考模型 | `ready-to-run/riscv64-nemu-interpreter-so`（626,696 B） |
| NEMU | `a683e0b`（XiangShan 版源码）+ `patches/nemu-vdot.patch` |
| Yosys | 0.52（旧环境 deb 本地解包；**当前环境未安装**，综合日志为历史证据，复跑需另行提供 yosys） |
| Verilator | 5.034（`.tools/verilator` 源码树，`--assert --trace`） |
| g++ | Debian 14.2.0 |
| Python | 3.13.5 |
| Docker | 29.4.0（当前环境可用，可用于 `xs-env` 镜像方案与文件属主修复） |

## 许可与引用

本项目基于开源香山（XiangShan）与 NEMU 进行扩展，相关代码遵循上游许可；新增代码仅用于参赛作品。
