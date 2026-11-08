# 阶段三最终总结报告：NEMU 扩展 · 协同仿真 · 基线与加速评估

> 项目：2026CIE · qxriscv · xiangshan-vdot
> 指令族：`vdot.vv`（INT8）、`vdot4x2.vv`（INT4 打包、双结果）、`vtdot.vv`（BitNet b1.58 三值、双结果）
> 版本：v1.1　|　日期：2026-11-08（v1.0 为 2026-11-04 的 INT8 单模式版）
> 覆盖任务：T3.1–T3.7，以及 T3.8/T3.10/T3.11 的系统级闭环；v1.1 增补 T3.12/T2.7
> 结论：功能、协同仿真、基线等价与实测性能全部完成；`run_all.sh` 七步全绿；G5 重复测量关闭。
> **v1.1 追补**：NEMU/协同/Chisel 已扩到三模式（3032 用例 / 4551 字 / 0 mismatch）；系统级 emu 实测仍是 INT8 一组数据（9.8×/11.8×），INT4/三值 emu 重跑列入 B6。

---

## 1. 摘要

阶段三的目标是回答三个问题：**自定义指令在参考模型里语义是否正确、RTL 与参考模型是否逐位一致、相对纯 RVV 基线到底快多少**。本阶段以香山同源 NEMU（`a683e0b`）为参考模型，完成：

1. `vdot` 指令族的 NEMU 译码与执行扩展（3 文件，170 行），并与金标准 `tests/ref_vdot.py`、RTL 三方比对：INT8 **1513/1513**、三模式 **3032 用例 / 4551 字**，0 mismatch。
2. 边界行为自检：三模式 `vl=0` 不写回、4 类非法配置各触发 1 次 `EX_II`，全部 PASS。
3. 纯 RVV 1.0 组合基线实现（INT8 语义），1513/1513 与 `vdot` 结果逐位一致；数据通路指令数 **6→1**，单用例核心指令 **14→7**。
4. 单元级实测 **3 cycle 延迟 / 1.0 inst·cycle⁻¹ 吞吐**；MAC/cycle = **8:16:16**（INT8/INT4/三值）。
5. 香山昆明湖 V2 `emu` 整程序实测（INT8）：`vdot` **0.5075 cycle/点积**，相对标量 **9.8×（lane 公平）**、相对 RVV 基线 **11.8×（16-lane，属上界）**；四内核各重复 3 次，周期数完全一致，极差 0。

对外主结论采用 lane 公平的 **9.8×**；11.8× 必须标注“RVV 基线为 VLMAX=16、2× lane 工作量，属上界”。

---

## 2. 交付物与证据链

| 类别 | 交付物 | 说明 |
|---|---|---|
| NEMU 扩展 | `patches/nemu-vdot.patch` | 3 文件 +42 行；由当前工作树 `git diff` 生成，`git apply` 可复现 |
| 测试程序生成 | `tests/as/mini_asm.py` | 纯 Python 手写汇编器；支持 CSR、`mret`、`la`、`vdot` 编码 |
| NEMU 自测/协同 | `tests/run_nemu_cosim.py` | 1513 写回用例 + 边界自检；支持 RTL 导出 diff |
| 基线实现 | `tests/ref_baseline.py`、`tests/run_nemu_baseline.py` | RVV 组合序列，1513/1513 等价 |
| 单元性能 | `rtl/verilog/tb_vdot.cpp`、`docs/phase3/04_rtl_unit_perf.log` | 延迟/吞吐/全量周期统计 |
| 系统级用例 | `tests/phase2/xs_emu/*.S`、`build.sh`、`run_emu.sh` | 定向 7 用例、非法 5 类、性能 4 内核（NITER 固定 2000） |
| 报告 | `docs/phase3/cosim_report.md`、`docs/phase3/perf_analysis.md`、`docs/phase3/05_perf_repeat.log` | 协同仿真、性能分析、重复测量 |

一键回归：`bash scripts/run_all.sh`，覆盖 unit / lint / chisel / nemu / rtl_export / cosim / baseline 七步。

---

## 3. 实现要点

### 3.1 NEMU 扩展

- 译码：在 `def_THelper(vopivv)` 增加 `"111111 ? ????? ????? ??? ????? ????? ??"` → `vdot`。
- 注册：`VECTOR_INSTR_TERNARY(vdot)`。
- 执行：校验 `vsew==0 && vlmul==0 && vm==1`，否则 `EX_II`；`vstart >= vl`（含 `vl==0`）正常退休不写回；否则按 `int8` 取 K=8 lane 做有符号乘累加，`vd[31:0]=sum`、`vd[127:32]=0`；`vstart != 0` 时幂等重算。
- 两个关键工程约束：
  - 直接按 64 bit 字写 `vreg_l()` 并显式清零高位，避免 `set_vreg(idx=1..15, vsew=2)` 在 VLEN=128 下换算成 `reg+3` 污染相邻寄存器。
  - `CONFIG_PERF_OPT` 会把 EHelper 线程化展开进 `execute()`，**不能用 `return` 收尾**，统一改为 if/else 结构。

### 3.2 协同仿真与覆盖分工

- 1518 条向量中 1513 条为“合法且写回”，用于 NEMU↔金标准↔RTL 三方逐位比对。
- 其余 5 条（1 条 `vl=0` + 4 条非法）由 RTL 全量回归、NEMU 边界自检与香山 emu 汇编用例分别覆盖。
- RTL 与 NEMU 只比较 `vd[31:0]`；高 96 bit 二者均置 0，但不纳入判定，避免与 tail-agnostic 策略耦合。

### 3.3 基线序列

```asm
vsetvli    t0, x0, e8, m1
vsext.vf2  v4, v1            # e8(f0.5) -> e16(m1)
vsext.vf2  v6, v2
vsetvli    t0, x0, e32, m2
vsext.vf2  v8,  v4           # e16(m1) -> e32(m2)
vsext.vf2  v12, v6
vmul.vv    v16, v8, v12      # e32m2
vsetvli    t0, x0, e32, m1
vredsum.vs v3, v16, v0       # v0 预清零
vmv.x.s    t1, v3
```

必须两级加宽到 32 bit：`vredsum.vs` 的累加宽度等于目标 SEW，停在 e16 会在 `+131072` 处溢出。

---

## 4. 功能验证结果

| 验证项 | 结果 | 证据 |
|---|---|---|
| NEMU 单指令自测（对金标准） | 1513/1513，0 fail，0 extra | `docs/phase3/01_nemu_cosim.log` |
| RTL ↔ NEMU 逐例 diff | 1513 vs 1513，**0 mismatch** | 同上、`02_rtl_export.txt` |
| NEMU 边界：`vl=0` 不写回 | PASS（`vd` 保持哨兵 `11223344`） | 同上 `boundary_checks` |
| NEMU 边界：非法配置 `EX_II` | 4/4 PASS（vm=0 / e16 / e64 / m2） | 同上 |
| 基线（纯 RVV）等价 | 1513/1513，`alu_op_ratio 6.0x` | `docs/phase3/03_baseline_nemu.log` |
| RTL 单元全量 | 1518/1518 PASS；全量总周期 10,220 | `docs/phase2/logs/03_unit_test.log` |
| 香山 emu 定向用例 | 7/7，difftest 0 mismatch | `docs/phase2/logs/xs_emu_vdot_directed.log` |
| 香山 emu 非法用例 | 5/5（架构级自检） | `docs/phase2/logs/xs_emu_vdot_illegal.log` |
| 一键回归 | 七步全绿 `ALL : PASS` | `scripts/run_all.sh` 输出 |

> 非法用例在 emu 上使用 `--no-diff`：DUT 提交 `mepc/mcause/mstatus` 后，参考模型在同一比较点仍为旧值，属于已知 difftest 滞后，与 `vdot` 实现无关。

---

## 5. 性能结果

### 5.1 单元级实测（Verilator 5.034）

| 指标 | 实测值 | 口径 |
|---|---|---|
| 单条延迟 | **3 cycle** | `in_valid` 拉高到 `out_valid` |
| 流式吞吐 | **1.0 inst/cycle** | 1024 条背靠背，`(完成数−1)/(末−首完成周期)` |
| 1513 子集总周期 | 10,185 | 1513 用例 + 1024 流式 + 自检 + 排空 |
| 1518 全量总周期 | 10,220 | 全量单元回归 |
| 结构性资源 | 8×8 有符号乘法器、7×20 bit 加法树（3 级） | 数据通路固定需求 |

### 5.2 系统级实测（香山昆明湖 V2 emu，NITER=2000）

方法：`per_iter(k)=(C_k−C_empty)/2000`；每内核独立运行 3 次。

| 内核 | 3 次 cycleCnt | 中位数 | 极差 | per-iter (cyc) |
|---|---|---|---|---|
| empty | 11,108 / 11,108 / 11,108 | 11,108 | 0（0.00%） | 基准 |
| vdot | 12,123 / 12,123 / 12,123 | 12,123 | 0（0.00%） | **0.5075** |
| rvv | 23,109 / 23,109 / 23,109 | 23,109 | 0（0.00%） | 6.0005 |
| scalar | 21,022 / 21,022 / 21,022 | 21,022 | 0（0.00%） | 4.9570 |

- vdot vs scalar：4.9570 / 0.5075 = **9.77 ≈ 9.8×**（标量恰好做 8 个乘积，lane 公平）。
- vdot vs rvv：6.0005 / 0.5075 = **11.82 ≈ 11.8×**（RVV 为 VLMAX=16，2× lane，属上界）。
- rvv vs scalar：4.9570 / 6.0005 = 0.826 ≈ 0.83×（RVV 基线比标量慢约 21%）。
- 12/12 次均 `PERF result=OK` 且 `HIT GOOD TRAP`。

### 5.3 公平性口径（必读）

`perf_rvv` 内核沿用 `vsetvli e8,m1` 的 VLMAX=16，`vwmul.vv`/`vwredsum.vs` 对 16 个 lane 做乘加（后 8 字节为 0 填充），而 `vdot.vv` 规范只做 K=8。因此：

- **9.8×** 是 lane 公平的实测值，作为主结论。
- **11.8×** 是 16-lane 基线的实测上界，不得当作 lane 归一后的收益。
- 没有直接把 RVV 内核改成 `vl=8`，原因是香山 NEMU 的 `reduction_instr` 在宽归约时按 `vtype->vsew` 读取 `vs2` 而非 `vsew+1`；实测 `vl=4/8/16` 只累加 `vl/2` 个元素（`22/60/120`），`vl=8` 时 difftest 直接失败。该缺陷属 NEMU 参考模型，不在 `vdot` 补丁范围。

### 5.4 指令数与面积

| 指标 | 基线（8-lane） | vdot | 比值 |
|---|---|---|---|
| 计算指令数 | 6 | 1 | 6:1 |
| 含 `vsetvli` 的总指令数 | 9 | 1（通常复用 vtype） | 9:1 |
| 向量 uop 数 | 10 | 1 | 10:1 |
| 写回带宽 | ≈6×128 bit + 标量 | 1×128 bit | ≈6:1 |
| NEMU 动态指令（1513 用例镜像） | 89,294 | 78,701 | −11.9% |

> 动态指令数含 UART 打印等脚手架开销，偏保守；纯算法部分为单用例核心指令 14 vs 7。

面积（Yosys generic 综合，历史日志）：4,186 单元 / 172 FF / 最长寄存器到寄存器路径 25 级，约 **5.3k–8.4k GE（中值 ≈6.9k）**。未做 PDK 映射，µm² 与 ns 不可引用。

---

## 6. 审计与修正记录（2026-11-03 / 11-04）

阶段三一致性审计关闭了 8 类文档-实现偏差，并新增两类证据：

| # | 问题 | 修正 |
|---|---|---|
| 1 | 补丁仍含旧 `return` 实现、声明 +44 行 | 按工作树 `git diff` 重新生成，改为 +42 行 |
| 2 | 文档未说明线程化 EHelper 禁止 `return` | 协同报告 §5 增加第 6 条 |
| 3 | `build.sh` 未固定 NITER，重建退化为 20000 | 显式 `-DPERF_NITER=${PERF_NITER:-2000}` 并重建 |
| 4 | RVV 退休指令数误写 3 | 修正为 2 |
| 5 | 标量 IPC 误写 3.2 | 修正为 17/4.96 ≈ 3.4 |
| 6 | RVV 比标量慢 17% | 修正为约 21% |
| 7 | 总周期 10113 过期 | 更新为 10185（1513 子集）/10,220（1518 全量） |
| 8 | 旧结论“不宣称实测加速比”与 emu 实测矛盾 | 改写为指向 `perf_analysis.md` §6 |

新增证据：

- `tests/run_nemu_cosim.py` 边界自检：`vl=0` + 4 类非法 `EX_II`，纳入 PASS 判定。
- `docs/phase3/05_perf_repeat.log`：四内核 3 次重复测量，极差 0，G5 关闭。

---

## 7. 门径完成情况

| 门径/任务 | 状态 | 说明 |
|---|---|---|
| M4（NEMU 扩展 + 协同仿真） | **完成** | 1513/1513，0 mismatch；边界自检 PASS |
| T3.1–T3.7 | **完成** | 补丁、汇编器、协同、基线、单元性能、报告全部就绪 |
| T3.8/T3.10/T3.11 | **完成** | 香山 emu 集成、定向/非法用例、实测加速比 |
| U-04（延迟加速分析） | **关闭** | 单元级 3 cycle / 1.0 inst·cycle⁻¹；emu 实测 9.8×/11.8× |
| G5（每点 3 次、中位数/极差） | **关闭（2026-11-04）** | 极差 0（0.00%，判据 <5%）；12/12 次 GOOD TRAP |
| M5（基线与加速比 + 提交） | 95% | 技术与证据已完成；仅剩提交动作待批准 |
| B3（真实加速比） | **关闭** | emu 实测完成 |
| B4（PDK 面积/时序） | 部分关闭 | generic 规模/深度已有；µm²/ns 待 PDK |

---

## 8. 风险与未闭合项

| # | 风险 | 影响 | 现状/后续 |
|---|---|---|---|
| P-1 | 基线序列语义 | 对比失真 | **已关闭**：1513/1513 + emu difftest 通过 |
| P-2 | `L_pipe` 经验值 | 延迟区间偏宽 | **已关闭**：改用整程序实测 |
| P-3 | 未含存储/取指瓶颈 | 批处理收益偏差 | 内核仅寄存器运算；存储受限结论需另建内核 |
| P-4 | 未做 PDK 综合 | 面积/时序不可引用 | 保持估算口径（B4 部分关闭） |
| P-5 | 与其它向量指令争用发射端口 | 实际上限低于 10× | 需混合负载实测 |
| P-6 | RVV 与 vdot lane 数不同 | 11.8× 高估 | 已标注为上界；lane 归一值待 NEMU 宽归约缺陷修复 |

其他边界：emu 是功能级仿真，周期数不含真实存储层次与物理频率，横向比值可信、绝对值不可外推；`vdot` 仅在本地香山工作树集成，未向上游提交。

---

## 9. 复现命令

```bash
# 全量回归（unit / lint / chisel / nemu / rtl_export / cosim / baseline）
bash scripts/run_all.sh

# 分项复现
python3 tests/run_nemu_cosim.py                  # NEMU 自测 + 边界自检 + RTL 导出
python3 tests/run_nemu_cosim.py --rtl-export docs/phase3/02_rtl_export.txt
python3 tests/run_nemu_baseline.py               # 基线等价 + 动态指令数
bash tests/phase2/xs_emu/build.sh                # PERF_NITER 默认 2000
bash tests/phase2/xs_emu/run_emu.sh              # emu 定向/非法/性能用例
```

环境：NEMU `a683e0b`（+`patches/nemu-vdot.patch`）、香山 `16ae9dd`、Verilator 5.034、VLEN=128。

---

## 10. 结论

阶段三的技术目标已全部达成：

1. **语义正确**：NEMU 扩展与金标准、RTL 三方 1513/1513 一致，0 mismatch；边界行为显式验证。
2. **基线可比**：纯 RVV 1.0 组合序列 1513/1513 等价，数据通路 6→1、核心指令 14→7。
3. **性能可测**：单元级 3 cycle / 1.0 inst·cycle⁻¹；系统级 0.5075 cycle/点积，9.8×（lane 公平）/11.8×（16-lane 上界），3 次重复零离散。
4. **证据可复现**：七步回归全绿，所有数字均有日志或脚本出处。
5. **表述有边界**：不宣称 PDK 面积时序、真实频率绝对性能、FPGA/流片结果；11.8× 始终标注为上界。
