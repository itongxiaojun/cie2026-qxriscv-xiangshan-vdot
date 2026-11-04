# 操作步骤截图与录屏（阶段一~四）

> 项目：2026CIE · qxriscv · xiangshan-vdot
> 用途：按官方业务流程（1.1/1.2/1.3、2.1/2.2/2.3、3.1.1/3.1.2/3.2/3.3）逐步骤留痕，
> 供三阶段文档与视频提交位使用。

## 1. 产物一览

| 阶段 | 对应官方要求 | 步骤 | 截图 | 录屏 | 时长 | 大小 |
|---|---|---|---|---|---|---|
| 阶段一 环境搭建与 RTL 链路贯通 | 1.1 / 1.2 / 1.3 | 6 | 12 张 | [stage1_environment.mp4](stage1_environment/video/stage1_environment.mp4) | 00:35.53 | 424 KB |
| 阶段二 设计实现与 RTL 验证 | 2.1 / 2.2 / 2.3 | 6 | 12 张 | [stage2_design_rtl.mp4](stage2_design_rtl/video/stage2_design_rtl.mp4) | 00:38.23 | 360 KB |
| 阶段三 NEMU 扩展、协同仿真与加速评估 | 3.1.1 / 3.1.2 / 3.2 / 3.3 | 7 | 14 张 | [stage3_nemu_cosim.mp4](stage3_nemu_cosim/video/stage3_nemu_cosim.mp4) | 00:46.13 | 600 KB |
| 阶段四 收口、综合评估与提交检查 | 质量/提交门径 | 5 | 10 张 | [stage4_release.mp4](stage4_release/video/stage4_release.mp4) | 00:34.23 | 408 KB |

- 每个步骤固定两张截图：`<NN>_<slug>_command.png`（命令与官方要求标签）、`<NN>_<slug>_result.png`（真实输出）。
- 每阶段另有 `transcript.txt`，按步骤记录命令与完整输出（截图/视频仅展示前若干行）。
- 所有画面均为 H.264 / yuv420p / 1920×1080 / 30 fps，可直接播放。

## 2. 阶段一：环境搭建与 RTL 链路贯通

目录：[stage1_environment](stage1_environment) · 录屏：`video/stage1_environment.mp4`

| 步骤 | 官方要求 | 屏幕内容 | 截图 |
|---|---|---|---|
| 1-1 | 1.1 环境准备 | `uname -m`、Python / RISC-V GCC / Verilator 版本 | `01_toolchain_*.png` |
| 1-2 | 1.2 操作日志 | 香山与 NEMU 的 commit 锁定 | `02_commits_*.png` |
| 1-3 | 1.1 环境准备 | emu、hello.bin、vadd.bin 构建产物核对 | `03_artifacts_*.png` |
| 1-4 | 1.1 hello 程序 | `hello xiangshan, I am qxriscv...` 与 GOOD TRAP（真实日志回放） | `04_hello_*.png` |
| 1-5 | 1.3 vadd 波形 | `--dump-wave -b 8200 -e 8360` 采集参数（真实日志回放） | `05_vadd_wave_*.png` |
| 1-6 | 1.3 vadd 波形 | 取指→译码→发射执行→访存→写回→提交时间线 + 波形图文件 | `06_vadd_timeline_*.png` |

## 3. 阶段二：设计实现与 RTL 验证

目录：[stage2_design_rtl](stage2_design_rtl) · 录屏：`video/stage2_design_rtl.mp4`

| 步骤 | 官方要求 | 屏幕内容 | 截图 |
|---|---|---|---|
| 2-1 | 2.1 设计文档 | `design.md` 章节结构（语义、位宽、数据通路、时序、集成） | `01_design_doc_*.png` |
| 2-2 | 2.2 RTL 实现 | `VDot.v` / `VDotCore.sv` 行数与文件信息 | `02_rtl_files_*.png` |
| 2-3 | 2.3 单元测试 | 1518/1518、3 cycle、1.0 inst·cycle⁻¹（真实回归日志回放） | `03_unit_regression_*.png` |
| 2-4 | 2.3 单元测试 | 行覆盖率 36/36 与 Chisel 等价回归 1518/1518 | `04_coverage_*.png` |
| 2-5 | 2.2 昆明湖 V2 集成 | 香山 emu 定向用例 7/7、difftest 0 mismatch | `05_emu_directed_*.png` |
| 2-6 | 2.3 单元测试 | 非法配置用例 5/5 触发 trap | `06_emu_illegal_*.png` |

## 4. 阶段三：NEMU 扩展、协同仿真与加速评估

目录：[stage3_nemu_cosim](stage3_nemu_cosim) · 录屏：`video/stage3_nemu_cosim.mp4`

| 步骤 | 官方要求 | 屏幕内容 | 截图 |
|---|---|---|---|
| 3-1 | 3.1.1 参考模型扩展 | NEMU 补丁 diffstat + 反向 apply 校验（PATCH CONSISTENT） | `01_patch_*.png` |
| 3-2 | 3.1.2 / 3.2 协同仿真 | 1513/1513、边界自检、动态指令数（真实日志回放） | `02_cosim_*.png` |
| 3-3 | 3.2 协同仿真 | `rtl_vs_nemu` 1513 vs 1513，0 mismatch | `03_rtl_diff_*.png` |
| 3-4 | 3.2 基线功能实现 | 纯 RVV 基线 1513/1513、6→1 数据通路指令 | `04_baseline_*.png` |
| 3-5 | 3.3 性能评估 | 单元级 3 cycle / 1.0 inst·cycle⁻¹ | `05_unit_perf_*.png` |
| 3-6 | 3.3 加速比 / G5 | emu 四内核 3 次重复：中位数、极差 0、per-iter 与 9.8×/11.8× | `06_perf_repeat_*.png` |
| 3-7 | 3.3 加速比 | `(C_k−C_empty)/NITER` 核算与加速比打印 | `07_speedup_*.png` |

## 5. 阶段四：收口、综合评估与提交检查

目录：[stage4_release](stage4_release) · 录屏：`video/stage4_release.mp4`

| 步骤 | 门径 | 屏幕内容 | 截图 |
|---|---|---|---|
| 4-1 | 质量门径 | Verilator `-Wall` 严格 lint，无 Warning/Error | `01_lint_*.png` |
| 4-2 | 质量门径 | Yosys generic 综合：4186 单元、最长路径 25 级 | `02_synth_*.png` |
| 4-3 | 质量门径 | 面积量级 ≈5.3k–8.4k GE | `03_area_*.png` |
| 4-4 | 提交门径 | `scripts/run_all.sh` 七步回归全 PASS（真实执行回放） | `04_run_all_*.png` |
| 4-5 | 提交门径 | 检查表已勾选 29 项 + 视频提交位置条目 | `05_checklist_*.png` |

## 6. 复现方式

```bash
python3 scripts/make_operation_recordings.py
```

- 依赖：`Pillow`、`ffmpeg`（本仓库使用 `.tools/ffmpeg/ffmpeg`）；字体取自系统 Noto Sans CJK 与 DejaVu Sans Mono。
- 脚本逐步骤执行命令并捕获输出，再渲染为终端画面；中间帧写入 `build/opt_record_frames/`（不随仓库提交）。
- 重新生成会覆盖本目录下的截图、录屏与 `transcript.txt`。

## 7. 真实性说明（无 GUI 主机）

- 本机为无图形界面的 Linux 终端，无法直接抓取桌面录屏；因此录屏由**真实命令输出**渲染成终端帧后经 ffmpeg 编码，画面中的命令、输出与退出状态均来自本机执行。
- `emu`、NEMU 协同仿真、`run_all.sh` 等单次耗时较长（数十秒至数分钟），为避免录屏等待，这些步骤回放 `docs/` 下**已捕获的真实日志**，并在画面中用黄色注记标明"长耗时步骤：回放已捕获的真实日志"；其余步骤为本次现场执行。
- 完整未截断的命令输出见各阶段 `transcript.txt`；回归证据见 [run_all.log](_evidence/run_all.log) 与 [阶段三最终报告](../phase3/final_report.md)。

## 8. 与提交位的对应

| 官方提交位 | 使用的录屏 | 配套文档 |
|---|---|---|
| 阶段一（环境与 vadd） | `stage1_environment/video/stage1_environment.mp4` | [docs/phase1/env.md](../../docs/phase1/env.md)、[docs/phase1/vadd_wave.md](../../docs/phase1/vadd_wave.md) |
| 阶段二（设计与实现） | `stage2_design_rtl/video/stage2_design_rtl.mp4` | [docs/phase2/design.md](../../docs/phase2/design.md)、[docs/phase2/test_report.md](../../docs/phase2/test_report.md) |
| 阶段三（协同仿真与评估） | `stage3_nemu_cosim/video/stage3_nemu_cosim.mp4` | [docs/phase3/cosim_report.md](../../docs/phase3/cosim_report.md)、[docs/phase3/perf_analysis.md](../../docs/phase3/perf_analysis.md) |
| 补充：阶段四收口 | `stage4_release/video/stage4_release.mp4` | [docs/phase4/release_report.md](../../docs/phase4/release_report.md) |
