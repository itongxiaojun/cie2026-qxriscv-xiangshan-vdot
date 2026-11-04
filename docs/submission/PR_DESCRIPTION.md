## 团队与项目信息

- **团队名称**：qxriscv
- **参赛单位**：<填写学校/单位>
- **赛题**：面向边缘 AI 大语言模型推理的 RISC-V 自定义 vdot 指令设计

## 阶段完成情况

- [x] 阶段一：环境部署与验证（香山 `16ae9dd` 的 emu 已构建；hello 真实 UART 输出 + 4 份日志 + vadd 波形分析入库）
- [x] 阶段二：vdot 设计与实现
- [x] 阶段三：协同仿真与评估

> 阶段四（RTL 收口、generic 综合与全量回归）已完成，作为阶段二/三的补充证据，不计入官方三阶段复选框。

## 提交内容概述

- 作品仓库：https://github.com/qixuan-cn/cie2026-qxriscv-xiangshan-vdot
- 阶段一：已闭环。`hello xiangshan, I am qxriscv, IP address: 192.168.0.168`，`HIT GOOD TRAP at pc = 0x80000020`；vadd 波形（8200–8360）逐 cycle 分析见 `docs/phase1/vadd_wave.md`，原始日志见 `docs/phase1/logs/`。
- 阶段二：`vdot.vv` 语义与微架构设计（SEW=8、VLEN=128、K=8、ACC_W=20）、Verilog/Chisel RTL、正/负/边界 1518 条用例（18 定向 + 1500 随机/边界）、1024 条背靠背流式测试，全部通过；行覆盖率 36/36 = 100%，Chisel 生成 RTL 同向量等价回归 1518/1518。
- 阶段三：NEMU 扩展（3 文件 +42 行）、同一向量集 1513 条 RTL↔NEMU 比对 0 mismatch、NEMU 边界自检（vl=0 不写回 + 4 类非法配置）、RVV 组合基线（6→1 数据通路 uop）跑通。
- 阶段四：Verilator 严格 lint 0 告警；Yosys generic 综合 4186 单元 / 172 FF / 25 级 R2R / ≈5.3k–8.4k GE；`scripts/run_all.sh` 七步回归全绿。
- 系统级（香山昆明湖 V2 emu + difftest）：`vdot.vv` 已集成进 VFEX0（`FuType.vdot`、译码 pattern、`VdotCfg`、`VDotUnit`），RTL 重生成与 emu 重建均完成；定向用例 7/7（difftest 0 mismatch）、非法配置 5/5，日志见 `docs/phase2/logs/xs_emu_*.log`。
- 关键结论：数据通路指令数 6→1（结构事实）；动态指令数 89,294→78,701（−11.9%，实测）；**香山 emu 实测加速比 9.8×（对标量，8-lane 公平）/ 11.8×（对 RVV 组合基线，16-lane，属上界）**，口径为 `per_iter=(C_k−C_empty)/NITER`、NITER=2000；延迟 12→3 cycle 仅为结构模型，不作实测口径。

## 验证与复现

```bash
git clone https://github.com/qixuan-cn/cie2026-qxriscv-xiangshan-vdot.git
cd cie2026-qxriscv-xiangshan-vdot
bash scripts/run_all.sh   # 单元 / lint / Chisel 等价 / NEMU / RTL 导出 / 协同 / 基线，末行 ALL : PASS
```

详细证据：`docs/phase2/test_report.md`、`docs/phase3/cosim_report.md`、`docs/phase4/release_report.md`。
