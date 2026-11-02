# 项目进度跟踪表（Living Document）

> **维护规则**
> 1. 每次推进后**当天更新**本表，不允许"做完再补"。
> 2. 状态词表固定为：`未开始` / `进行中` / `阻塞` / `完成` / `已取消`，不得使用其它措辞。
> 3. 每个"完成"项必须挂**可验证证据**（日志、波形、报告、commit），无证据不得标完成。
> 4. 阻塞项必须写清"缺什么、谁能解锁、解锁后的下一步"。
> 5. 表尾"变更记录"按日期倒序追加，一行一条。

| 项 | 内容 |
|---|---|
| 项目 | cie2026-qxriscv-xiangshan-vdot |
| 目标平台 | 香山昆明湖 V2（VLEN=128） |
| 团队 | qxriscv（2–3 人） |
| 工作区 | `/home/dbqxxs/xsriscv/cieriscv`（2026-11-01 迁移至当前主机） |
| 计划基线 | [ipd/03 开发计划](file:///home/dbqxxs/xsriscv/cieriscv/ipd/03_开发计划_WBS与里程碑.md)（D1–D20 / M1–M5） |
| 最后更新 | 2026-11-01 |

---

## 1. 里程碑总览

| 里程碑 | 内容 | IPD 门径 | 计划 | 状态 | 完成度 |
|---|---|---|---|---|---|
| M1 | 环境就绪 + 向量加法波形 | TR3 | D6 | **完成** | 100%（香山 `16ae9dd` 的 emu 已构建；hello 真实 UART 输出、4 份原始日志、vadd 波形与逐 cycle 分析均已入库） |
| M2 | vdot 单元 RTL + 单元验证 | TR3 | D10 | **完成** | 100% |
| M3 | 香山内集成 + 汇编级正/负/边界测试 | TR4 | D12 | **阻塞** | 30%（集成规程就绪） |
| M4 | NEMU 扩展 + 协同仿真 | TR4 | D15 | **完成** | 100%（1513/1513，RTL↔NEMU 0 mismatch） |
| M5 | 基线与加速比 + 提交 | TR6/ADCP | D20 | 进行中 | 85%（基线与协同仿真全绿；generic 综合、逻辑深度与加速模型已完成，其中综合为历史日志、当前无 yosys 不可复跑；平台实测待完成香山集成，提交待实施） |

## 2. 官方交付要求对照

| 要求 | 交付物 | 状态 | 证据 |
|---|---|---|---|
| 1.1 hello + IP | 运行输出截图/日志 | **完成** | [02_hello_run.log](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase1/logs/02_hello_run.log)：`hello xiangshan, I am qxriscv, IP address: 192.168.0.168`，`HIT GOOD TRAP at pc = 0x80000020`（instrCnt 295 / cycleCnt 10,819，EXIT=0） |
| 1.2 操作日志 | 环境部署日志 | **完成** | [01_env_setup.log](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase1/logs/01_env_setup.log)：主机基线→工具链→源码锁定→镜像编译→emu 构建（三阶段耗时）；运行/解析日志 [02](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase1/logs/02_hello_run.log)、[03](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase1/logs/03_vadd_run.log)、[04](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase1/logs/04_wave_parse.log) |
| 1.3 vadd 执行过程文档 | 波形 + 分析 | **完成** | [vadd_wave.md](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase1/vadd_wave.md)、[vadd_pipeline_wave.png](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase1/wave/vadd_pipeline_wave.png)、[03_vadd_run.log](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase1/logs/03_vadd_run.log)、[04_wave_parse.log](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase1/logs/04_wave_parse.log) |
| 2.1 设计文档 | 设计文档 | **完成** | [docs/phase2/design.md](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase2/design.md) |
| 2.2 RTL 实现 | Verilog/Chisel | **完成**（模块级已验证） | [VDot.v](file:///home/dbqxxs/xsriscv/cieriscv/rtl/verilog/VDot.v) |
| 2.3.1 正数测试 | 用例 + 结果 | **完成**（单元级） | [测试报告 §4.1](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase2/test_report.md) |
| 2.3.2 负数测试 | 用例 + 结果 | **完成**（单元级） | 同上 |
| 2.3.3 边界测试 | 用例 + 结果 | **完成**（单元级） | 同上 §4.2 |
| 3.1.1 NEMU 扩展 | 源码改动 | **完成** | [nemu-vdot.patch](file:///home/dbqxxs/xsriscv/cieriscv/patches/nemu-vdot.patch) |
| 3.1.2 协同仿真 | NEMU vs RTL 比对 | **完成** | [01_nemu_cosim.log](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase3/01_nemu_cosim.log)：1513/1513，0 mismatch |
| 3.2 基线实现 | 组合指令程序 | **完成**（NEMU 上跑通） | [run_nemu_baseline.py](file:///home/dbqxxs/xsriscv/cieriscv/tests/run_nemu_baseline.py)：1513/1513 |
| 3.3 加速分析 | 分析报告 | 完成（模型口径）：数据通路 6→1、模型延迟 12→3 cycle（4.0×）、吞吐 6.0×；平台实测待完成香山集成后实施 | [release_report.md](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase4/release_report.md) §5 |

## 3. 详细任务表（当前迭代）

| ID | 任务 | 交付物 | 状态 | 依赖 | 证据 |
|---|---|---|---|---|---|
| T2.1 | vdot 语义与位宽裁决 | 规格书 §2 | 完成 | — | `ipd/01` |
| T2.2 | 模块级 RTL | `rtl/verilog/VDot.v` | 完成 | T2.1 | 1518/1518 PASS |
| T2.3 | 参考模型（Python/C） | `tests/ref_vdot.py`、`model/vdot_ref.c` | 完成 | T2.1 | `logs/06_*` |
| T2.4 | 单元测试台与向量 | `tb_vdot.cpp`、1518 条向量 | 完成 | T2.2/T2.3 | `logs/03_*`、VCD |
| T2.5 | 阶段二报告与设计文档 | `docs/phase2/*` | 完成 | T2.4 | — |
| T3.1 | NEMU 中新增 `vdot.vv` 译码与执行 | NEMU 源码改动 | 完成 | NEMU 源码 | `patches/nemu-vdot.patch`（3 文件 +44 行） |
| T3.2 | 最小 RISC-V 测试程序（手写机器码） | `tests/as/*.py` + 二进制 | 完成 | — | `tests/as/mini_asm.py`；1513 用例镜像 48720 B |
| T3.3 | NEMU 单指令自测（vdot 结果正确） | 运行日志 | 完成 | T3.1/T3.2 | `docs/phase3/01_nemu_cosim.log`：1513/1513 PASS |
| T3.4 | RTL ↔ NEMU 协同仿真（同向量集比对） | 比对日志 + 报告 | 完成 | T3.3 | 1513 vs 1513，0 mismatch（`02_rtl_export.txt`） |
| T3.5 | 基线汇编实现（RVV 组合） | 汇编程序 | 完成 | T3.2 | `tests/run_nemu_baseline.py`：1513/1513，6→1 数据通路指令 |
| T3.6 | 延迟/吞吐实测（rdcycle） | 测量日志 | 完成（单元级实测） | 需香山或 NEMU 计时 | `04_rtl_unit_perf.log`：3 cycle / 1.0 inst/cycle；NEMU 动态指令 78701 vs 89294 |
| T3.7 | 阶段三报告（实测替换估算） | `docs/phase3/*` | 完成 | T3.4/T3.6 | [cosim_report.md](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase3/cosim_report.md) |
| T3.8 | 香山内集成（VFU） | 香山源码改动 | 阻塞 | 环境已就绪（香山 `16ae9dd` + emu），集成未实施 | 集成规程已就绪 |
| T3.9 | 阶段一（环境/hello/vadd 波形） | 日志 + 波形 + 文档 | 完成 | xs-env | `docs/phase1/logs/01–04`、`wave/vadd_pipeline_wave.png`、`vadd_wave.md`；emu 构建 EXIT=0 |
| T4.1 | RTL 死逻辑清理与严格 lint 门禁 | `VDot.v` 修订 | 完成 | T2.2 | `02_verilator_lint.log`：4 告警 → **0** |
| T4.2 | generic 综合与逻辑深度评估 | 综合日志 | 完成 | T4.1 | `01_yosys_synth.log`：4186 单元 / 172 FF / 最长路径 25 级 |
| T4.3 | 面积估算（GE 口径） | 估算表 | 完成 | T4.2 | `release_report.md` §3.2：≈5.3k–8.4k GE |
| T4.4 | 加速模型（延迟/吞吐）与答辩口径 | 模型表 | 完成 | T4.1 | `release_report.md` §5：4.0× 延迟 / 6.0× 吞吐（模型） |
| T4.5 | 清理后全量回归（单元/协同/基线） | 回归日志 | 完成 | T4.1 | 1518/1518；1513/1513，0 mismatch；基线 6.0× |
| T4.6 | 一键回归脚本（单元+lint+协同+基线） | `scripts/run_all.sh` | 完成 | T4.5 | 本机 `ALL : PASS`（6 步全绿） |
| T4.7 | 文档一致性同步（行号/信号/面积口径） | `design.md` v1.1、`perf_analysis.md` §5、`ipd/01` Q5 | 完成 | T4.1–T4.4 | 清除 `s1_valid/s2_valid`、`sum_c` 旧引用；面积改为 generic 综合口径 |

## 4. 阻塞与风险

| # | 阻塞项 | 缺什么 | 解锁条件 | 解锁后下一步 |
|---|---|---|---|---|
| B1 | 阶段一全部内容 | — | — | **已关闭（2026-11-01）**：emu 构建、hello 运行、vadd 波形与四份日志均已入库（见 §2 的 1.1–1.3 证据） |
| B2 | 香山内集成与回归 | 集成实施（香山源码与 emu 已就绪，尚无人力执行 I1–I7） | 已满足（B1 关闭） | 按 `patches/xiangshan-vdot-integration.md` 执行 I1–I7 |
| B3 | 真实加速比 | 香山平台计时（需先完成 B2） | NEMU 计时已可用 | 按 `perf_analysis.md` §6 协议实测 |
| B4 | PDK 面积/时序签核 | 工艺库 + DC/Genus | 环境允许 | **部分关闭**：generic 规模/深度已取得（`docs/phase4/01_yosys_synth.log`）；µm² 与 ns 仍待做 |

> **表述约束（长期有效）**：在 B2/B3 关闭前，任何材料不得宣称"`vdot` 已在香山平台验证"或给出"实测加速比"。阶段一的环境与 vadd 波形确已在香山仿真平台取得，但这不等于 `vdot` 已完成集成或验证。

## 5. 当前环境复跑记录（2026-11-01）

工作区迁移后，在 `/home/dbqxxs/xsriscv/cieriscv` 重新执行全链路，用于确认"文档结论仍成立"：

| 步骤 | 结果 | 说明 |
|---|---|---|
| emu 构建（Chisel+firtool → Verilator → C++ 链接） | **PASS** | `EXIT=0`；三阶段 15:33 / 8:43 / 29:58，总约 54 min；148 条 elaboration warning（无 error）；产物 261,132,232 B |
| `hello.bin` 运行（1.1） | **PASS** | `hello xiangshan, I am qxriscv, IP address: 192.168.0.168`；`HIT GOOD TRAP at pc=0x80000020`；instrCnt 295 / cycleCnt 10,819；Host 74,084 ms |
| `vadd.bin` 运行 + 波形（1.3） | **PASS** | `HIT GOOD TRAP at pc=0x80000038`；instrCnt 18 / cycleCnt 8,351；VCD 100,664,602 B（8200–8360）；Host 42,404 ms |
| `bash scripts/run_unit_tests.sh` | **PASS** | 1518/1518，0 fail；延迟 3 cycle / 非法 3 cycle；吞吐 1 inst/cycle；`total_cycles 10148` |
| Verilator 严格 lint | **PASS** | 0 告警 0 错误 |
| NEMU 自测 + RTL↔NEMU | **PASS** | 1513 vs 1513，`mismatch=0`；NEMU 退出码 0 |
| RVV 组合基线 | **PASS** | 1513/1513，`alu_op_ratio 6.0x` |
| `bash scripts/run_all.sh` | **ALL : PASS** | 6 步全绿 |

本次复跑同时修复了一个环境迁移缺陷：`build/obj_dir` 中的旧 Makefile 写死旧工作区绝对路径，导致构建失败；已在 `scripts/build_sim.sh` 增加"陈旧构建目录自动清理"。本次**未能复跑** generic 综合（当前环境无 yosys），综合数据仍引用 `docs/phase4/01_yosys_synth.log` 历史证据。

阶段一在三阶段复跑之外单独执行：`.tools/` 手工等价部署工具链 → 构建香山 `16ae9dd` 的 emu（约 54 min，`EXIT=0`）→ 跑 hello（Host 74,084 ms）→ 跑 vadd 并 dump 波形（Host 42,404 ms）→ `scripts/plot_phase1_wave.py` 出图。原始日志见 `docs/phase1/logs/`，波形分析见 `docs/phase1/vadd_wave.md`。

## 6. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-11-01 | 阶段一闭环（T3.9 / M1）：`.tools/` 手工等价部署（Temurin 21.0.13、mill 0.12.3、xPack GCC 15.2.0、Verilator 5.034），构建香山 `16ae9dd` 的 emu（`EXIT=0`，约 54 min）；hello 输出 `hello xiangshan, I am qxriscv, IP address: 192.168.0.168`，vadd 波形（8200–8360）采集并出图；新增 `docs/phase1/logs/01–04`、`docs/phase1/wave/vadd_pipeline_wave.png`、`docs/phase1/vadd_wave.md`、`scripts/plot_phase1_wave.py`；`docs/phase1/env.md` 重写为"当前可用环境 + 旧机历史"；1.1–1.3 与 T3.9 标完成，B1 关闭 |
| 2026-11-01 | 环境迁移收口：文档内旧路径 `/mnt/hdata/qxriscv/cieriscv` 全部更新为 `/home/dbqxxs/xsriscv/cieriscv`；`docs/phase1/env.md` 重写为"当前环境基线 + 旧环境历史（已失效）"两段式；README/PROGRESS 当时记录 `xs-env`/香山源码/RISC-V 工具链缺失、阶段一阻塞（该状态已于同日随后闭环，见上一行）；`scripts/build_sim.sh` 增加陈旧构建目录自动清理；全链路复跑 `ALL : PASS` |
| 2026-10-28 | 阶段四文档一致性收口（T4.7）：`docs/phase2/design.md` v1.1 对齐清理后的 RTL 行号/信号与综合结果；`docs/phase3/perf_analysis.md` §5 面积改为 generic 综合口径；`docs/phase2/test_report.md` U-05 与 `ipd/01` Q5 标注"部分关闭"；`scripts/run_all.sh` 6 步一键回归本机全绿 |
| 2026-10-28 | 阶段四完成（T4.1–T4.5）：RTL 死逻辑清理（`sum_c` 加法树、`s1_valid`/`s2_valid`）+ 严格 lint 告警 4→0；yosys generic 综合 4186 单元 / 172 FF / 最长 R2R 路径 25 级，估算 ≈5.3k–8.4k GE；补加速模型（延迟 12→3 cycle，4.0×；吞吐 6.0×）；清理后全量回归 1518/1518、1513/1513 0 mismatch、基线 6.0× 全绿；B4 部分关闭，报告 `docs/phase4/release_report.md` |
| 2026-10-27 | 阶段三文档一致性收口：README 阶段三状态/证据链/仓库结构/复现命令/版本锁定（NEMU `a683e0b`）同步；`vdot` 编码由 `funct6=100000`（建议值）定值为 `111111`，回写至 `ipd/01` §2.2、`docs/phase2/design.md` §2.1、`patches/xiangshan-vdot-integration.md` I1，O2 关闭 |
| 2026-10-27 | 阶段三 T3.1–T3.7 全部完成：NEMU `vdot` 实现 + 协同仿真 1513/1513（RTL↔NEMU 0 mismatch）+ RVV 组合基线跑通（6→1 数据通路指令）+ 单元级实测 3 cycle/1.0 inst/cycle；M4 关闭，报告 `docs/phase3/cosim_report.md` |
| 2026-10-27 | 建立本表；阶段二（M2）标记完成，证据为 1518/1518 PASS + 3 cycle/1 inst/cycle；启动阶段三（M4/M5） |

