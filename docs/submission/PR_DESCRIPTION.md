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
- 阶段二：`vdot.vv` 语义与微架构设计（SEW=8、VLEN=128、K=8、ACC_W=20）、Verilog/Chisel RTL、正/负/边界 1518 条用例（18 定向 + 1500 随机/边界）、1024 条背靠背流式测试，全部通过。
- 阶段三：NEMU 扩展（3 文件 +44 行）、同一向量集 1513 条 RTL↔NEMU 比对 0 mismatch、RVV 组合基线（6→1 数据通路 uop）跑通。
- 阶段四：Verilator 严格 lint 0 告警；Yosys generic 综合 4186 单元 / 172 FF / 25 级 R2R / ≈5.3k–8.4k GE；`scripts/run_all.sh` 六步回归全绿。
- 关键结论：数据通路指令数 6→1（结构事实）；动态指令数 89,294→78,701（−11.9%，实测）；延迟 12→3 cycle（4.0×）为显式假设的结构模型，平台实测待 `vdot` 集成后实施。

## 验证与复现

```bash
git clone https://github.com/qixuan-cn/cie2026-qxriscv-xiangshan-vdot.git
cd cie2026-qxriscv-xiangshan-vdot
bash scripts/run_all.sh   # 单元 / lint / NEMU / RTL 导出 / 协同 / 基线，末行 ALL : PASS
```

详细证据：`docs/phase2/test_report.md`、`docs/phase3/cosim_report.md`、`docs/phase4/release_report.md`。
