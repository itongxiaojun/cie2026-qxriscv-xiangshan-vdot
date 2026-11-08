# 阶段三 · NEMU 协同仿真与性能实测报告

> 项目：2026CIE · qxriscv · xiangshan-vdot
> 指令族：`vdot.vv`（INT8）、`vdot4x2.vv`（INT4 打包、双结果）、`vtdot.vv`（BitNet b1.58 三值、双结果）
> 本报告对应进度表 T3.1–T3.7；§1–§5 的 1513 口径是 **v1.2 INT8 单模式历史记录**，三模式现行口径见 §1.1 与 [01_nemu_cosim.log](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase3/01_nemu_cosim.log)。

---

## 1. 目的与范围

| 目标 | 手段 | 结论 |
|---|---|---|
| 证明自定义指令在指令集模拟器语义正确 | 在 NEMU（香山同源）中实现三条 `vdot` 指令，用 3032 条可运行用例自测 | **3032/3032 与金标准一致**（4551 结果字） |
| 复核边界配置的架构行为 | NEMU 边界自检：vl=0 不写回；4 类非法配置各触发 1 次 `EX_II` | 均 PASS |
| 证明 RTL 与 NEMU 逐位一致 | 同一用例集分别驱动 RTL 与 NEMU，直接 diff 结果 | **4551 vs 4551，0 mismatch** |
| 量化"有/无该指令"的代价差 | 用纯 RVV 1.0 组合序列实现同语义基线，在 NEMU 上跑通并计数 | 数据通路指令 6→1；单用例核心指令 14→7 |
| 给出实测性能口径 | Verilator 单元测试台统计延迟/吞吐 | 延迟 3 cycle，吞吐 1 inst/cycle |

**不在范围**：香山昆明湖 V2 平台上的真实周期数与加速比（2026-11-03 已在 `emu` 上完成，见 [性能分析 §6](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase3/perf_analysis.md)；本报告仍只覆盖 NEMU/RTL 协同与单元级口径）。

### 1.1 三模式现行口径（2026-11-08）

| 项 | 结果 |
|---|---|
| NEMU 译码/执行 | 三条指令同一套编码空间（opcode 0x57、funct3 000、funct6 `111111/111110/111101`） |
| 可运行用例 | **3032**（int8=1513、int4x2=759、vtdot=760） |
| 结果字比对 | **4551 vs 4551**（双结果用例各比对 r0/r1），mismatch **0** |
| 边界自检 | 三模式 `vl=0` 不写回（哨兵 `0x11223344/0x55667788` 保持）；4 类非法配置各触发 1 次 `EX_II`，三模式全 PASS |
| 模型修复 | `mini_asm` 的 vs1/vs2 参数顺序修正（D-09）；`vdot_sext4` 改为语句表达式宏以适配 `CONFIG_PERF_OPT` |
| 证据 | [01_nemu_cosim.log](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase3/01_nemu_cosim.log)、`build/nemu/cosim_vectors.txt`、[nemu-vdot.patch](file:///home/dbqxxs/xsriscv/cieriscv/patches/nemu-vdot.patch)（170 行） |

---

## 2. 环境与可复现命令

- NEMU：XiangShan 版，基线 commit `a683e0b`
- VLEN=128；`CONFIG_RVV=y`、`CONFIG_RVV_AGNOSTIC=y`
- 解释器：`.tools/nemu/build/riscv64-nemu-interpreter`
- 测试镜像由纯 Python 手写汇编器生成（`tests/as/mini_asm.py`）；阶段一迁移后 RISC-V 交叉工具链已可用（`.tools/riscv`），此处保留原生成方式以保证镜像与历史结果可复现

```bash
# 1) NEMU 单指令自测 + 金标准比对 + vl=0/非法配置边界自检（同时导出 tb 用子集）
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

补丁：`patches/nemu-vdot.patch`（3 文件，+42 行）

| 文件 | 改动 |
|---|---|
| `src/isa/riscv64/instr/rvv/decode.h` | 在 `def_THelper(vopivv)` 增加 `"111111 ? ????? ????? ??? ????? ????? ??"` → `vdot` |
| `src/isa/riscv64/include/isa-all-instr.h` | `VECTOR_INSTR_TERNARY(vdot)` 注册 |
| `src/isa/riscv64/instr/rvv/vcompute.h` | 新增 `def_EHelper(vdot)`：校验 `vsew==0 && vlmul==0 && vm==1`，否则 `EX_II`；`vstart >= vl`（含 `vl==0`）不写回正常退休；否则按 `int8` 取 K=8 个 lane 做有符号乘累加，`vd[31:0]=sum`（按位，不做符号扩展），`vd[127:32]=0`；`vstart != 0` 时按设计做幂等重算 |

写回实现要点：直接按 64 bit 字写 `vreg_l()` 并显式清零高位。早期使用 `set_vreg(idx=1..15, vsew=2)` 的写法在 VLEN=128/SEW=32 下会被换算成 `reg+3`，污染相邻向量寄存器，已废弃。

> **2026-11-03 补丁复核**：补丁已由当前 NEMU 工作树 `git diff` 重新生成，`git apply` 可直接复现。`vcompute.h` 内不使用 `return` 收尾——`CONFIG_PERF_OPT` 会把 EHelper 线程化展开进 `execute()`，提前 `return` 会跳过 PC 推进并导致该指令无限重放；实现统一改为 if/else 结构。

---

## 4. 结果

### 4.1 T3.3 NEMU 单指令自测

日志：`docs/phase3/01_nemu_cosim.log`

| 项 | 值 |
|---|---|
| 用例总数 / 可运行（合法且写回） | **3047 / 3032**（INT8 1513、INT4 759、三值 760） |
| 观测到的结果字行数 | **4551**（双结果用例按 r0/r1 两行输出） |
| 与金标准不符 | 0 |
| 多余输出 | 0 |
| NEMU 退出码 | 0（`nemu_trap` code 0，GOOD TRAP） |
| 边界：`vl=0` 不写回（`vd` 保持哨兵 `11223344/55667788`） | 3/3 PASS（三模式各 1） |
| 边界：非法配置触发 `EX_II`（vm=0 / e16 / e64 / m2） | 12/12 PASS（三模式各 4） |
| **判定** | **PASS** |

### 4.2 T3.4 RTL ↔ NEMU 直接 diff

日志：`docs/phase3/02_cosim.log`（`rtl_vs_nemu` 行）、`docs/phase3/02_rtl_export.txt`

| 项 | 值 |
|---|---|
| RTL 导出结果字行数 | **4551** |
| NEMU 输出结果字行数 | **4551** |
| 逐字比对不匹配 | **0** |
| **判定** | **PASS** |

比对口径：按 32-bit 结果字逐行比对；INT8 每例 1 字，INT4/三值每例 2 字（`r0`→`vd[31:0]`、`r1`→`vd[63:32]`）。`vd[127:64]` 恒 0 由 RTL 单元测试的 128-bit 全宽比对与断言覆盖，不在本 diff 中重复判定。

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
| 全测试台总周期 | **21588** | 3047 用例 + 1024 流式 + 补充自检 + 排空 |
| 功能用例 | **3032/3032 PASS** | 同 4.1 用例集（4551 结果字） |

NEMU 动态指令数（同一 1513 用例镜像；日志字段 `nemu_dyn_instr`，见 `01_nemu_cosim.log` 与 `03_baseline_nemu.log`）：

| 实现 | 动态指令数 | 相对 |
|---|---|---|
| `vdot.vv` | 78,701 | 基准 |
| RVV 组合基线 | 89,294 | +10,593（相对 vdot +13.5%，相对基线 −11.9%），≈ 7.0 条/用例 |

注：动态指令数含 UART 十六进制打印等测试脚手架开销，故绝对比例偏保守；纯算法部分的差异为上表"14 vs 7"。

> 口径说明：本表性能取自 1513 条**INT8 写回子集**的运行，因此日志中的 `latency_illegal` 为 0（子集不含非法用例），非功能异常。全量 3047 条三模式运行的非法延迟为 3 cycle，见 `docs/phase2/logs/03_unit_test.log`。

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
6. **NEMU 线程化执行模式下 EHelper 不能 `return`**
   `CONFIG_PERF_OPT` 会把 EHelper 展开进 `execute()`，`return` 会跳过 PC 推进，使该指令被无限重放。`vdot` 改为 if/else 收尾，补丁已同步。

---

## 6. 结论与表述约束

- 三条 `vdot` 指令的 NEMU 语义实现与金标准、RTL 三方一致（**3032 用例 / 4551 结果字，0 mismatch**）。
- NEMU 边界自检通过：三模式 `vl=0` 不写回（3/3），4 类非法配置在三模式下各触发一次 `EX_II`（12/12）。
- 相对纯 RVV 1.0 组合基线（INT8），数据通路指令数 6→1，单用例核心指令数 14→7。
- 覆盖分工：3047 条向量中 15 条不参与可运行集——13 条 `vl=0`/非法配置（INT8 5、INT4 4、三值 4）+ 2 条保留 mode；其余 3032 条用于 NEMU↔金标准↔RTL 三方逐位比对。
- 本报告只覆盖 **指令级仿真与单元级 RTL**；香山昆明湖 V2 `emu` 上的整程序周期与加速比见 [`perf_analysis.md` §6](file:///home/dbqxxs/xsriscv/cieriscv/docs/phase3/perf_analysis.md)。

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
