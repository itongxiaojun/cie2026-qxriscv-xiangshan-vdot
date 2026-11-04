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
| 最后更新 | 2026-11-03 |

---

## 1. 里程碑总览

| 里程碑 | 内容 | IPD 门径 | 计划 | 状态 | 完成度 |
|---|---|---|---|---|---|
| M1 | 环境就绪 + 向量加法波形 | TR3 | D6 | **完成** | 100%（香山 `16ae9dd` 的 emu 已构建；hello 真实 UART 输出、4 份原始日志、vadd 波形与逐 cycle 分析均已入库） |
| M2 | vdot 单元 RTL + 单元验证 | TR3 | D10 | **完成** | 100%（1518/1518 PASS；行覆盖率 36/36 = 100%；Chisel 版编译并生成 RTL，同向量等价回归 1518/1518） |
| M3 | 香山内集成 + 汇编级正/负/边界测试 | TR4 | D12 | **完成** | 100%（`vdot` 接入 VFEX0；定向 7/7 difftest 0 mismatch，非法 5/5；见 `docs/phase2/logs/xs_emu_*.log`） |
| M4 | NEMU 扩展 + 协同仿真 | TR4 | D15 | **完成** | 100%（1513/1513，RTL↔NEMU 0 mismatch） |
| M5 | 基线与加速比 + 提交 | TR6/ADCP | D20 | 进行中 | 95%（基线与协同仿真全绿；**香山 emu 实测加速比 9.8×（对标量，8-lane 公平）/11.8×（对 RVV，16-lane，属上界）已完成**；generic 综合为历史日志、当前无 yosys 不可复跑；仅剩提交动作待批准） |

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
| 3.1.2 协同仿真 | NEMU vs RTL 比对 | **完成** | [01_nemu_cosim.log](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase3/01_nemu_cosim.log)：1513/1513，0 mismatch；边界自检 vl=0 不写回 + 非法 4/4 |
| 3.2 基线实现 | 组合指令程序 | **完成**（NEMU 上跑通） | [run_nemu_baseline.py](file:///home/dbqxxs/xsriscv/cieriscv/tests/run_nemu_baseline.py)：1513/1513 |
| 3.3 加速分析 | 分析报告 | **完成（香山 emu 实测）**：per-iter vdot 0.51 cyc vs 标量 4.96 cyc / RVV 6.00 cyc → **9.8×（对标量，8-lane 公平）/ 11.8×（对 RVV，16-lane，属上界）**（NITER=2000） | [perf_analysis.md](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase3/perf_analysis.md) §6、`docs/phase2/logs/xs_emu_perf_*.log` |

## 3. 详细任务表（当前迭代）

| ID | 任务 | 交付物 | 状态 | 依赖 | 证据 |
|---|---|---|---|---|---|
| T2.1 | vdot 语义与位宽裁决 | 规格书 §2 | 完成 | — | `ipd/01` |
| T2.2 | 模块级 RTL | `rtl/verilog/VDot.v` | 完成 | T2.1 | 1518/1518 PASS |
| T2.3 | 参考模型（Python/C） | `tests/ref_vdot.py`、`model/vdot_ref.c` | 完成 | T2.1 | `logs/06_*` |
| T2.4 | 单元测试台与向量 | `tb_vdot.cpp`、1518 条向量 | 完成 | T2.2/T2.3 | `logs/03_*`、VCD；含逐 lane 8/8、`vstart` 重放 3/3、保留 SEW、复位空闲自检 |
| T2.5 | 阶段二报告与设计文档 | `docs/phase2/*` | 完成 | T2.4 | `design.md` v1.2、`test_report.md` v1.2 |
| T2.6 | 行覆盖率与 Chisel 版等价回归 | 覆盖率日志 + `rtl/chisel/VDotCore.sv` | 完成 | T2.4 | `logs/07_coverage.log`（36/36 = 100%）；`logs/09_chisel_equiv.log`（1518/1518，3 cycle，1.0 inst/cycle）；脚本 `scripts/run_chisel_equiv.sh` |
| T3.1 | NEMU 中新增 `vdot.vv` 译码与执行 | NEMU 源码改动 | 完成 | NEMU 源码 | `patches/nemu-vdot.patch`（3 文件 +42 行，与工作树 `git diff` 一致） |
| T3.2 | 最小 RISC-V 测试程序（手写机器码） | `tests/as/*.py` + 二进制 | 完成 | — | `tests/as/mini_asm.py`；1513 用例镜像 48720 B |
| T3.3 | NEMU 单指令自测（vdot 结果正确） | 运行日志 | 完成 | T3.1/T3.2 | `docs/phase3/01_nemu_cosim.log`：1513/1513 PASS；边界自检 `vl0=PASS`、`illegal=PASS(4/4)` |
| T3.4 | RTL ↔ NEMU 协同仿真（同向量集比对） | 比对日志 + 报告 | 完成 | T3.3 | 1513 vs 1513，0 mismatch（`02_rtl_export.txt`） |
| T3.5 | 基线汇编实现（RVV 组合） | 汇编程序 | 完成 | T3.2 | `tests/run_nemu_baseline.py`：1513/1513，6→1 数据通路指令 |
| T3.6 | 延迟/吞吐实测（rdcycle） | 测量日志 | 完成（单元级实测） | 需香山或 NEMU 计时 | `04_rtl_unit_perf.log`：3 cycle / 1.0 inst/cycle；NEMU 动态指令 78701 vs 89294 |
| T3.7 | 阶段三报告（实测替换估算） | `docs/phase3/*` | 完成 | T3.4/T3.6 | [cosim_report.md](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase3/cosim_report.md) |
| T3.8 | 香山内集成（VFU） | 香山源码改动 | 完成 | 香山 `16ae9dd` + emu | I1–I7 完成（`FuType.vdot`/`VecDecoder`/`VdotCfg`/`VDotUnit`/VFEX0）；RTL 重生成 + emu 重建；定向 7/7、非法 5/5 |
| T3.10 | 香山 emu 汇编级用例（正/负/边界） | `tests/phase2/xs_emu/*.S` | 完成 | T3.8 | `vdot_directed.S`（7 用例：正/负/极值/符号交替/vl=8/vl=0）difftest 0 mismatch；`vdot_illegal.S`（5 类非法配置）5/5 |
| T3.11 | 香山 emu 实测加速比 | 实测日志 + 报告 | 完成 | T3.8 | `docs/phase3/perf_analysis.md` §6：9.8×（对标量，8-lane 公平）/ 11.8×（对 RVV 基线，16-lane，属上界），NITER=2000 |
| T3.9 | 阶段一（环境/hello/vadd 波形） | 日志 + 波形 + 文档 | 完成 | xs-env | `docs/phase1/logs/01–04`、`wave/vadd_pipeline_wave.png`、`vadd_wave.md`；emu 构建 EXIT=0 |
| T4.1 | RTL 死逻辑清理与严格 lint 门禁 | `VDot.v` 修订 | 完成 | T2.2 | `02_verilator_lint.log`：4 告警 → **0** |
| T4.2 | generic 综合与逻辑深度评估 | 综合日志 | 完成 | T4.1 | `01_yosys_synth.log`：4186 单元 / 172 FF / 最长路径 25 级 |
| T4.3 | 面积估算（GE 口径） | 估算表 | 完成 | T4.2 | `release_report.md` §3.2：≈5.3k–8.4k GE |
| T4.4 | 加速模型（延迟/吞吐）与答辩口径 | 模型表 | 完成 | T4.1 | `release_report.md` §5：4.0× 延迟 / 6.0× 吞吐（模型） |
| T4.5 | 清理后全量回归（单元/协同/基线） | 回归日志 | 完成 | T4.1 | 1518/1518；1513/1513，0 mismatch；基线 6.0× |
| T4.6 | 一键回归脚本（单元+lint+Chisel 等价+协同+基线） | `scripts/run_all.sh` | 完成 | T4.5 | 本机 `ALL : PASS`（7 步全绿，2026-11-02 加入 Chisel 等价步骤） |
| T4.7 | 文档一致性同步（行号/信号/面积口径） | `design.md` v1.1、`perf_analysis.md` §5、`ipd/01` Q5 | 完成 | T4.1–T4.4 | 清除 `s1_valid/s2_valid`、`sum_c` 旧引用；面积改为 generic 综合口径 |

## 4. 阻塞与风险

| # | 阻塞项 | 缺什么 | 解锁条件 | 解锁后下一步 |
|---|---|---|---|---|
| B1 | 阶段一全部内容 | — | — | **已关闭（2026-11-01）**：emu 构建、hello 运行、vadd 波形与四份日志均已入库（见 §2 的 1.1–1.3 证据） |
| B2 | 香山内集成与回归 | — | — | **已关闭（2026-11-03）**：I1–I7 完成，RTL 重生成 + emu 重建；定向 7/7 difftest 0 mismatch、非法 5/5；见 `docs/phase2/logs/xs_emu_*.log` |
| B3 | 真实加速比 | — | — | **已关闭（2026-11-03）**：emu 实测 9.8×（对标量，8-lane 公平）/ 11.8×（对 RVV，16-lane，属上界），见 `perf_analysis.md` §6 |
| B4 | PDK 面积/时序签核 | 工艺库 + DC/Genus | 环境允许 | **部分关闭**：generic 规模/深度已取得（`docs/phase4/01_yosys_synth.log`）；µm² 与 ns 仍待做 |

> **表述口径（2026-11-03 更新）**：B2/B3 关闭后，可以宣称"`vdot` 已在香山昆明湖 V2 的 `emu`（Verilator）+ difftest 环境验证，并取得实测加速比 9.8×（lane 公平）/11.8×（16-lane 上界）"。仍不得宣称的内容：PDK 级面积/时序（B4 未关闭）、真实频率下的绝对性能、FPGA/流片结果。非法配置用例的 difftest 存在参考模型侧已知滞后，故采用程序内自检，见 `docs/phase2/test_report.md` §8.1。

## 5. 当前环境复跑记录（2026-11-02 / 2026-11-03）

### 2026-11-03 香山 emu 系统级验证（B2/B3 关闭）

| 步骤 | 结果 | 说明 |
|---|---|---|
| RTL 重生成（mill + firtool） | **EXIT=0** | 27 min（主机负载较高）；`build/rtl/VDotUnit.sv` 中已出现 `vpu_vsew/vpu_vlmul/vpu_vill` 端口，`vecWen` 不再被抑制 |
| emu 重建（Verilator 5.034 + C++，`-j48`） | **EXIT=0** | 约 75 min；产物 `build/emu` |
| `vdot_directed`（difftest） | **PASS** | `DIRECTED fails=00000000`、`HIT GOOD TRAP`；992 inst / 13,565 cyc；0 mismatch |
| `vdot_illegal`（`--no-diff` 自检） | **PASS** | `ILLEGAL traps=00000005 other=00000000`、`HIT GOOD TRAP`；10,429 cyc |
| 普通非法指令对照（difftest） | 已知误报 | 陷阱指令提交时参考模型 CSR 滞后；DUT 侧正确（`logs/xs_emu_baseline_illegal_difftest.log`） |
| `perf_empty/vdot/rvv/scalar`（difftest） | **PASS** | cycleCnt 11,108 / 12,123 / 23,109 / 21,022（NITER=2000），`PERF result=OK` |
| 实测加速比 | **9.8× / 11.8×** | 对标量（8-lane 公平）/ 对 RVV 基线（16-lane，上界），见 `docs/phase3/perf_analysis.md` §6 |

### 2026-11-02 单元/协同回归

> 2026-11-01 的记录见本节末尾历史段；2026-11-02 在阶段二收口时复跑。

| 步骤 | 结果 | 说明 |
|---|---|---|
| `bash scripts/run_unit_tests.sh`（6 步） | **PASS** | 1518/1518，0 fail；延迟 3 cycle / 非法 3 cycle；吞吐 1 inst/cycle；`total_cycles 10220`；`lane_checks 8/8`、`replay_checks 3/3`、`reserved_sew`、`reset_idle` 均 PASS |
| 行覆盖率 | **36/36 = 100%** | `--coverage-line` + `verilator_coverage --annotate-min 1`，`logs/07_coverage.log` |
| `bash scripts/run_chisel_equiv.sh` | **PASS** | Chisel 6.6.0 编译 + firtool 1.62.1 生成 `VDotCore.sv`；同一测试台 1518/1518、3 cycle、1.0 inst/cycle |
| `bash scripts/run_all.sh`（7 步） | **ALL : PASS** | 单元 → 严格 lint → Chisel 等价 → NEMU 自测 → RTL↔NEMU → 基线全绿 |

### 历史复跑记录（2026-11-01）

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
| 2026-11-04 | 操作留痕产物入库：新增 `doc/operation_record/`，按官方 1.1/1.2/1.3、2.1/2.2/2.3、3.1.1/3.1.2/3.2/3.3 拆为 24 个步骤，生成 48 张命令/结果截图、4 段 MP4 录屏（1920×1080@30fps）与各阶段 `transcript.txt`；长耗时步骤回放已捕获日志并在画面标注；索引见 `doc/operation_record/README.md`，`ipd/04` 视频提交行改为指向该索引 |
| 2026-11-04 | 性能数据 3 次重复测量（G5 关闭）：四个内核各独立跑 3 次（NITER=2000），cycleCnt 中位数 empty 11,108 / vdot 12,123 / rvv 23,109 / scalar 21,022，极差全为 0（0.00%，判据 <5%），12/12 次 `PERF result=OK` 且 `HIT GOOD TRAP`；新增 `docs/phase3/05_perf_repeat.log`，同步 `ipd/04` 勾选与 `perf_analysis.md` §6.1/§6.3 重复测量表；新增阶段三最终总结报告 `docs/phase3/final_report.md` |
| 2026-11-03 | 阶段三一致性审计与迭代：`patches/nemu-vdot.patch` 按当前 NEMU 工作树重新生成（+44→+42 行，修正已在源码中规避的 `return` 缺陷）；`tests/run_nemu_cosim.py` 新增 NEMU 边界自检（`vl=0` 不写回 + vm=0/e16/e64/m2 四类非法各触发 1 次 `EX_II`），`mini_asm` 增加 CSR/`mret`/`la` 支持；`tests/phase2/xs_emu/build.sh` 固定 `PERF_NITER=2000`（此前重建会退化为 20000）；修正 `perf_analysis.md` 中 RVV 退休指令 3→2、标量 IPC 3.2→3.4、RVV 慢 17%→21% 等口径；新增 §6.4 公平性口径（RVV 内核 VLMAX=16，属 2× lane 工作量，11.8× 仅为上界，主结论用 lane 公平的 9.8×），并同步 README/PROGRESS/release_report/design/PR/ipd/PPT；刷新 `docs/phase3/{00,01,02,03,04}` 与 `nemu_standalone_perf_*.log` |
| 2026-11-03 | 香山内集成闭环（T3.8/T3.10/T3.11，关闭 B2/B3）：`vdot` 接入 VFEX0 并在昆明湖 V2 上重生成 RTL、重建 emu；修复两个集成缺陷（D-07 `vl==0` 屏蔽写回导致架构 vd 变随机值；D-08 `VlData` 仅 8 bit 使 SEW/LMUL/vill 检查被优化掉）；定向 7/7 difftest 0 mismatch、非法 5/5、性能四内核全绿；实测加速比 9.8×（对标量，8-lane 公平）/11.8×（对 RVV 基线，16-lane，属上界）；新增 `docs/phase2/logs/xs_emu_*.log`、`tests/phase2/xs_emu/{vdot_directed,vdot_illegal,vdot_perf}.S`、`build.sh`、`run_emu.sh`；`test_report.md` §7/§8/§10、`perf_analysis.md` §6、`patches/xiangshan-vdot-integration.md` §5/§8/§10 同步 |
| 2026-11-02 | 阶段二收口（T2.4–T2.6）：修复 `in_sew` 2 bit 截断保留编码缺陷（改 3 bit，新增 TC-E05）；测试台新增复位空闲、逐 lane 8/8、`vstart` 重放 3/3 自检，`total_cycles` 更新为 10220；接入 Verilator 行覆盖率（36/36 = 100%）；Chisel 版编译通过并生成 `rtl/chisel/VDotCore.sv`，经 `VDotWrap.v` 完成 1518/1518 等价回归；新增 `scripts/run_chisel_equiv.sh`，`scripts/run_all.sh` 扩为 7 步；`design.md`/`test_report.md` 升至 v1.2，README/`ipd/04`/集成说明/`env.md` 同步 Chisel 状态 |
| 2026-11-01 | 阶段一闭环（T3.9 / M1）：`.tools/` 手工等价部署（Temurin 21.0.13、mill 0.12.3、xPack GCC 15.2.0、Verilator 5.034），构建香山 `16ae9dd` 的 emu（`EXIT=0`，约 54 min）；hello 输出 `hello xiangshan, I am qxriscv, IP address: 192.168.0.168`，vadd 波形（8200–8360）采集并出图；新增 `docs/phase1/logs/01–04`、`docs/phase1/wave/vadd_pipeline_wave.png`、`docs/phase1/vadd_wave.md`、`scripts/plot_phase1_wave.py`；`docs/phase1/env.md` 重写为"当前可用环境 + 旧机历史"；1.1–1.3 与 T3.9 标完成，B1 关闭 |
| 2026-11-01 | 环境迁移收口：文档内旧路径 `/mnt/hdata/qxriscv/cieriscv` 全部更新为 `/home/dbqxxs/xsriscv/cieriscv`；`docs/phase1/env.md` 重写为"当前环境基线 + 旧环境历史（已失效）"两段式；README/PROGRESS 当时记录 `xs-env`/香山源码/RISC-V 工具链缺失、阶段一阻塞（该状态已于同日随后闭环，见上一行）；`scripts/build_sim.sh` 增加陈旧构建目录自动清理；全链路复跑 `ALL : PASS` |
| 2026-10-28 | 阶段四文档一致性收口（T4.7）：`docs/phase2/design.md` v1.1 对齐清理后的 RTL 行号/信号与综合结果；`docs/phase3/perf_analysis.md` §5 面积改为 generic 综合口径；`docs/phase2/test_report.md` U-05 与 `ipd/01` Q5 标注"部分关闭"；`scripts/run_all.sh` 6 步一键回归本机全绿 |
| 2026-10-28 | 阶段四完成（T4.1–T4.5）：RTL 死逻辑清理（`sum_c` 加法树、`s1_valid`/`s2_valid`）+ 严格 lint 告警 4→0；yosys generic 综合 4186 单元 / 172 FF / 最长 R2R 路径 25 级，估算 ≈5.3k–8.4k GE；补加速模型（延迟 12→3 cycle，4.0×；吞吐 6.0×）；清理后全量回归 1518/1518、1513/1513 0 mismatch、基线 6.0× 全绿；B4 部分关闭，报告 `docs/phase4/release_report.md` |
| 2026-10-27 | 阶段三文档一致性收口：README 阶段三状态/证据链/仓库结构/复现命令/版本锁定（NEMU `a683e0b`）同步；`vdot` 编码由 `funct6=100000`（建议值）定值为 `111111`，回写至 `ipd/01` §2.2、`docs/phase2/design.md` §2.1、`patches/xiangshan-vdot-integration.md` I1，O2 关闭 |
| 2026-10-27 | 阶段三 T3.1–T3.7 全部完成：NEMU `vdot` 实现 + 协同仿真 1513/1513（RTL↔NEMU 0 mismatch）+ RVV 组合基线跑通（6→1 数据通路指令）+ 单元级实测 3 cycle/1.0 inst/cycle；M4 关闭，报告 `docs/phase3/cosim_report.md` |
| 2026-10-27 | 建立本表；阶段二（M2）标记完成，证据为 1518/1518 PASS + 3 cycle/1 inst/cycle；启动阶段三（M4/M5） |

