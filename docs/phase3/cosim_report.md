# 阶段三 · NEMU 协同仿真与性能实测报告

> 项目：2026CIE · qxriscv · xiangshan-vdot
> 指令：`vdot.vv`（SEW=8, K=8, VLEN=128, OUT_W=32）
> 本报告对应进度表 T3.1–T3.7，所有结论均可由本目录下日志复现。

---

## 1. 目的与范围

| 目标 | 手段 | 结论 |
|---|---|---|
| 证明自定义指令在指令集模拟器语义正确 | 在 NEMU（香山同源）中实现 `vdot.vv`，用 1513 条写回用例自测 | 1513/1513 与金标准一致 |
| 证明 RTL 与 NEMU 逐位一致 | 同一用例集分别驱动 RTL 与 NEMU，直接 diff 结果 | 1513 vs 1513，0 mismatch |
| 量化"有/无该指令"的代价差 | 用纯 RVV 1.0 组合序列实现同语义基线，在 NEMU 上跑通并计数 | 数据通路指令 6→1；单用例核心指令 14→7 |
| 给出实测性能口径 | Verilator 单元测试台统计延迟/吞吐 | 延迟 3 cycle，吞吐 1 inst/cycle |

**不在范围**：香山昆明湖 V2 平台上的真实周期数与加速比（B1 已关闭，B2 集成与 B3 测量尚未执行）。

---

## 2. 环境与可复现命令

- NEMU：XiangShan 版，基线 commit `a683e0b`
- VLEN=128；`CONFIG_RVV=y`、`CONFIG_RVV_AGNOSTIC=y`
- 解释器：`.tools/nemu/build/riscv64-nemu-interpreter`
- 测试镜像由纯 Python 手写汇编器生成（`tests/as/mini_asm.py`）；阶段一迁移后 RISC-V 交叉工具链已可用（`.tools/riscv`），此处保留原生成方式以保证镜像与历史结果可复现

```bash
# 1) NEMU 单指令自测 + 金标准比对（同时导出 tb 用子集）
python3 tests/run_nemu_cosim.py
# 2) RTL 跑同一子集并导出逐用例结果
./build/obj_dir/tb_vdot build/nemu/cosim_vectors.txt - docs/phase3/02_rtl_export.txt
# 3) RTL↔NEMU 直接 diff
python3 tests/run_nemu_cosim.py --rtl-export docs/phase3/02_rtl_export.txt
# 4) 基线（RVV 组合）等价性 + 指令数对比
python3 tests/run_nemu_baseline.py
```

> **2026-11-01 迁移后复跑**：工作区迁至 `/home/dbqxxs/xsriscv/cieriscv`，`bash scripts/run_all.sh` 输出 `ALL : PASS`；NEMU 1513/1513、RTL↔NEMU `mismatch=0`、基线 `alu_op_ratio 6.0x`，与初版一致。NEMU 源码/构建产物（`.tools/nemu`，commit `a683e0b` + 补丁）随工作区迁移仍可用。

---

## 3. NEMU 扩展改动

补丁：`patches/nemu-vdot.patch`（3 文件，+44 行）

| 文件 | 改动 |
|---|---|
| `src/isa/riscv64/instr/rvv/decode.h` | 在 `def_THelper(vopivv)` 增加 `"111111 ? ????? ????? ??? ????? ????? ??"` → `vdot` |
| `src/isa/riscv64/include/isa-all-instr.h` | `VECTOR_INSTR_TERNARY(vdot)` 注册 |
| `src/isa/riscv64/instr/rvv/vcompute.h` | 新增 `def_EHelper(vdot)`：校验 `vsew==0 && vlmul==0 && vm==1`，否则 `EX_II`；按 `int8` 取 K=8 个 lane 做有符号乘累加；`vd[31:0]=sum`（按位，不做符号扩展），`vd[127:32]=0` |

写回实现要点：直接按 64 bit 字写 `vreg_l()` 并显式清零高位。早期使用 `set_vreg(idx=1..15, vsew=2)` 的写法在 VLEN=128/SEW=32 下会被换算成 `reg+3`，污染相邻向量寄存器，已废弃。

---

## 4. 结果

### 4.1 T3.3 NEMU 单指令自测

日志：`docs/phase3/01_nemu_cosim.log`

| 项 | 值 |
|---|---|
| 用例总数 / 可运行（合法且写回） | 1518 / 1513 |
| 观测到的结果行数 | 1513 |
| 与金标准不符 | 0 |
| 多余输出 | 0 |
| NEMU 退出码 | 0（`nemu_trap` code 0，GOOD TRAP） |
| **判定** | **PASS** |

### 4.2 T3.4 RTL ↔ NEMU 直接 diff

日志：`docs/phase3/01_nemu_cosim.log`（`rtl_vs_nemu` 行）、`docs/phase3/02_rtl_export.txt`

| 项 | 值 |
|---|---|
| RTL 导出行数 | 1513 |
| NEMU 输出行数 | 1513 |
| 低 32 bit 逐例比对不匹配 | **0** |
| **判定** | **PASS** |

比对口径：只比较 `vd[31:0]`（本指令的规范结果）。高 96 bit 由 RTL 恒置 0、NEMU 亦置 0，但未纳入判定，避免与 tail-agnostic 策略耦合。

### 4.3 T3.5 基线（纯 RVV 组合）等价性

日志：`docs/phase3/03_baseline_nemu.log`

基线序列（无 `vdot` 时编译器可用的写法）：

```
vsext.vf2 (e8 -> e16)  x2
vsext.vf2 (e16 -> e32) x2
vmul.vv   (e32, m2)    x1
vredsum.vs(e32, m2)    x1
```

| 项 | 值 |
|---|---|
| 用例数 / 与金标准不符 | 1513 / 0 |
| 向量数据通路指令数（基线 / vdot） | 6 / 1 |
| 单用例核心指令数（含 2 条 `vle8.v` 与 `vsetvli`） | 14 / 7 |
| **判定** | **PASS** |

### 4.4 T3.6 性能实测

RTL 单元测试台日志：`docs/phase3/04_rtl_unit_perf.log`

| 指标 | 实测值 | 口径 |
|---|---|---|
| 单条延迟 | 3 cycle | `in_valid` 拉高到 `out_valid` 的周期数 |
| 流式吞吐 | 1.0 inst/cycle | 连续 1024 条背靠背发射，`(完成数-1)/(末-首完成周期)` |
| 1024 条总周期 | 10113 | 含排空 |
| 功能用例 | 1513/1513 PASS | 同 4.1 用例集 |

NEMU 动态指令数（同一 1513 用例镜像）：

| 实现 | 动态指令数 | 相对 |
|---|---|---|
| `vdot.vv` | 78,701 | 基准 |
| RVV 组合基线 | 89,294 | +10,593（+13.5%），≈ 7.0 条/用例 |

注：动态指令数含 UART 十六进制打印等测试脚手架开销，故绝对比例偏保守；纯算法部分的差异为上表"14 vs 7"。

> 口径说明：本表性能取自 1513 条**写回子集**的运行，因此日志中的 `latency_illegal` 为 0（子集不含非法用例），非功能异常。全量 1518 条运行的非法延迟为 3 cycle，见 `docs/phase4/03_rtl_full_perf.log`。

---

## 5. 调试过程中发现并修复的问题

1. **裸机 `mstatus.VS=Off` 导致所有向量指令非法**
   `require_vector()` 内部检查 `mstatus.vs`，为 0 时抛 `EX_II`。测试程序需先 `csrrs mstatus, 0x200`。已固化进 `mini_asm.build_program`。
2. **`vdot` EHelper 写回越界**
   `set_vreg(..., idx=1..15, vsew=2)` 在 VLEN=128 下换算成 `reg+3`，会写坏 `v(reg+3)`。改为直接写 `vreg_l(id_dest->reg, i)`。
3. **`vle8.v` 的 `vm` 位漏编码**
   `vm` 在 bit 25，落在 I 型立即数内；早期 `imm=0` 使指令变成"掩码 load"，NEMU 按 v0（全 0）掩码写入全 0。修正为 `imm | 0x20`。
4. **`CONFIG_RVV_AGNOSTIC=y` 下 `vta=vma=1` 时 `vle` 快速路径整寄存器覆写为全 1**
   现象为 `vmv.x.s` 读出 `ffffffff`。测试程序改用 undisturbed（`vta=vma=0`），语义不受影响（vl=VLMAX、无掩码）。
5. **`vsext.vf2` 编码组号**
   该指令属 `vxunary0` 组 funct6=`010010`（非 `010000`），基线实现据此修正。

---

## 6. 结论与表述约束

- `vdot.vv` 的 NEMU 语义实现与金标准、RTL 三方一致（1513/1513，0 mismatch）。
- 相对纯 RVV 1.0 组合基线，数据通路指令数 6→1，单用例核心指令数 14→7。
- 以上均为 **指令级仿真与单元级 RTL** 证据。在 B1/B2/B3 关闭前，**不宣称"已在香山平台验证"或给出"实测加速比"**。

## 7. 附件

| 文件 | 内容 |
|---|---|
| `docs/phase3/01_nemu_cosim.log` | T3.3/T3.4 判定与统计 |
| `docs/phase3/02_rtl_export.txt` | RTL 逐用例 128 bit 结果 |
| `docs/phase3/03_baseline_nemu.log` | T3.5 判定与指令数对比 |
| `docs/phase3/04_rtl_unit_perf.log` | RTL 延迟/吞吐实测 |
| `patches/nemu-vdot.patch` | NEMU 侧全部改动 |
| `tests/as/mini_asm.py` | 手写汇编器与镜像生成器 |
| `tests/run_nemu_cosim.py` | NEMU↔金标准↔RTL 比对驱动 |
| `tests/run_nemu_baseline.py` | 基线实现等价性与计数 |
