# 阶段二 测试报告：vdot.vv 功能单元单元级验证

| 项目 | 内容 |
|---|---|
| 被测对象 | `rtl/verilog/VDot.v`（VLEN=128, K=8, ACC_W=20, OUT_W=32） |
| 对应规格 | [ipd/01 设计规格书](file:///home/dbqxxs/xsriscv/cieriscv/ipd/01_vdot指令与微架构设计规格书.md) |
| 测试方案 | [ipd/02 测试与验证方案](file:///home/dbqxxs/xsriscv/cieriscv/ipd/02_测试与验证方案.md) |
| 报告版本 | v1.1（2026-11-01 在当前环境复跑确认） |
| 执行日期 | 2026-10-27（初版）；2026-11-01（迁移后复跑，结果一致） |
| 执行人 | B（验证） |
| **总体结论** | **PASS** —— 1518/1518 用例通过，0 失败；单条延迟 3 cycle，吞吐 1 inst/cycle |

---

## 1. 结论摘要

| 指标 | 实测结果 |
|---|---|
| 定向用例（功能 + 边界 + 配置/异常） | 18 / 18 通过 |
| 随机用例（均匀分布） | 1000 / 1000 通过 |
| 边界密集随机用例（取值域 8 个极值） | 500 / 500 通过 |
| 背靠背流式用例（按序比对） | 1024 / 1024 通过 |
| 三方模型一致性（Python / C / C++ 内联，1518 条） | 1518 / 1518 一致 |
| 失败用例 | **0** |
| 单条延迟（in_valid → out_valid） | **3 cycle**（写回路径与 illegal 路径均为 3） |
| 吞吐（无依赖连续发射） | **1.0 inst/cycle** |
| 仿真断言（`--assert`） | 0 触发（高位清零、valid/illegal 互斥等） |
| 128 bit 全宽比对 | 全部用例均比对整 128 bit，非仅低 32 bit |

关键边界结论全部命中：`+127×8 → 0x0001F808`、`-128×-128×8 → 0x00020000`（19 bit 边界）、`-130048 → 0xFFFE0400`。

> 本报告仅覆盖**单元级**（模块级 RTL 仿真）。香山集成、NEMU 协同仿真与端到端加速比因环境缺失未执行，见 §8。

---

## 2. 验证环境

| 项 | 取值 |
|---|---|
| 主机 | Linux x86_64，48 核，31 GB 内存 |
| 仿真器 | Verilator 5.034（本机从源码构建，`--assert --trace`） |
| 编译器 | g++ (Debian 14.2.0) `-O2 -std=c++17` |
| 参考模型 | Python 3.13.5（`tests/ref_vdot.py`）；C11（`tests/model/vdot_ref.c`，NEMU-ready） |
| 版本控制 | git，被测 RTL commit 见仓库提交记录 |
| 波形 | `docs/phase2/waveform/vdot_unit.vcd`（前 400 周期，GTKWave 可打开） |

**环境说明**：阶段二执行时主机无 Verilator 预装与 RISC-V 工具链，因此采用"从源码构建 Verilator + 模块级 C++ 测试台"的方式完成可执行的 RTL 仿真；这保证了本报告数据来自**真实 RTL 仿真**而非行为模型。2026-11-01 环境迁移后 Verilator 5.034 可用，单元回归可复跑（1518/1518 PASS）。

> **2026-11-01 迁移后复跑**：工作区迁至 `/home/dbqxxs/xsriscv/cieriscv`，重新执行 `bash scripts/run_unit_tests.sh`，结果与初版一致：1518/1518 PASS、延迟 3 cycle、吞吐 1 inst/cycle、`total_cycles 10148`。迁移导致 `build/obj_dir` 中的旧 Makefile 指向旧目录而构建失败，已由 `scripts/build_sim.sh` 的陈旧产物自动清理修复。

---

## 3. 验证方法

### 3.1 四路独立实现的一致性结构

```
tests/ref_vdot.py ─生成─► tests/vectors/vdot_vectors.txt ─驱动─► RTL (VDot.v)
      │                              │                                │
      │                              ├──期望值────────────────────────┘  逐位比对 128 bit
      │                              └──交叉比对──► tests/model/vdot_ref.c
      └──同一语义的独立实现（Python）                （C11，NEMU-ready）

tests/tb/tb_vdot.cpp：流式测试中的期望由 C++ 内联模型独立计算
```

1. **期望值唯一来源**：Python golden model，按规格书伪代码逐行实现，且先用闭式边界值（§2.6）自检。
2. **RTL 不做自我参照**：测试台不读取 RTL 输出生成期望；失败时只报告"期望 vs 实际"。
3. **交叉实现校验**：
   - 流式测试中期望值由测试台内的 **C++ 内联模型**独立计算，与 Python 模型构成跨语言双实现；
   - `tests/model/vdot_ref.c`（C11）对全部 **1518 条向量**独立重算并比对，构成第三份实现；
   - 三份实现均不共享代码，结果两两一致后才用于判定 RTL。
4. **C 模型的双重用途**：同一文件保留纯函数接口 `vdot_vv()`，可直接移植进 NEMU（阶段三 3.1.1）。

### 3.2 测试台结构（`tests/tb/tb_vdot.cpp`）

| 功能 | 说明 |
|---|---|
| 逐用例驱动 | 每用例单独发一条请求，观察 3 周期后的写回 |
| 延迟测量 | 记录 in_valid 到 out_valid 的周期差 |
| 非写回检查 | `vl=0`、非法配置持续观察 8 周期，确认无写回、无误报 illegal |
| 流式测试 | 连续 1024 条请求，按序出队比对，验证流水线交错与背靠背正确性 |
| 断言 | Verilator `--assert`：高位通道必须为 0；valid 与 illegal 不得同时有效；dirty 必须伴随 valid |
| 波形 | 前 400 周期导出 VCD |

### 3.3 判定口径

- 写回类：`out_valid==1` 且 `out_vd[127:0] == 期望[127:0]`。
- 非法类：`out_illegal==1`、`out_valid==0`。
- `vl=0`：`out_valid==0` 且 `out_illegal==0`（既不写也不报错）。
- 任一不满足即判 FAIL，测试台返回非 0 退出码。

---

## 4. 用例执行结果

### 4.1 功能用例

| 用例 | 输入（要点） | 期望 `vd[31:0]` | 结果 |
|---|---|---|---|
| TC-F01 positive | lane: 1..8 × 8..1 | `0x00000078`（120） | PASS |
| TC-F02 negative | 含 `0x80(-128)`、`0xFF(-1)`、`0xF0` 等 | `0xFFFFBEB9`（-16711） | PASS |
| TC-F03 mixed | 正负混合 + 非对称 | `0xFFFF47F3`（-47117） | PASS |
| TC-F05 zeros | 全 0 | `0x00000000` | PASS |

### 4.2 边界用例（重点）

| 用例 | 输入 | 期望 | 结果 | 说明 |
|---|---|---|---|---|
| TC-B01 max-pos | 全 `0x7F`(127) | `0x0001F808` = 129032 | PASS | 最大正和 |
| TC-B02 max-neg | vs1 全 `0x80`、vs2 全 `0x7F` | `0xFFFE0400` = -130048 | PASS | 最大负和 |
| TC-B03 19-bit edge | 双方全 `0x80`(-128) | **`0x00020000` = 131072** | PASS | 越过 18 bit 有符号上界 |
| TC-B04 all-zero | 全 0 | `0x00000000` | PASS | 零值 |
| TC-B05 cancel | `+1/-1` 交替 × 4，vs2 全 +1 | `0x00000000` | PASS | 符号抵消 |
| TC-B06 lane0-only | 仅 lane0 = 5×7 | `0x00000023`（35） | PASS | 通道定位 |
| TC-B07 80×7F | 仅 `-128 × 127` 交替 | 见向量文件 | PASS | 单乘积极值 |
| TC-B08 max-mixed | `-128` 与 `127` 混排 | 见向量文件 | PASS | 正负极值混合 |

> TC-B03 是位宽设计的关键验证点：若累加器为 16 或 18 bit，此处会溢出为 0 或负数。本设计 20 bit 累加 + 32 bit 输出，实测正确。

### 4.3 配置与异常用例

| 用例 | 配置 | 期望行为 | 结果 |
|---|---|---|---|
| TC-V01 vl-zero | `vl=0` | 不写回、不报错、`vd` 不变 | PASS |
| TC-V02 vl-one | `vl=1`（语义与 `vl` 无关） | 与 `vl=16` 结果一致 | PASS |
| TC-E01 vm0 | `vm=0` | illegal，不写回 | PASS |
| TC-E02 sew-e16 | `SEW=e16` | illegal，不写回 | PASS |
| TC-E03 lmul-m2 | `LMUL=m2` | illegal，不写回 | PASS |
| TC-E04 sew-e64 | `SEW=e64` | illegal，不写回 | PASS |

### 4.4 随机与流式

| 类别 | 数量 | 分布 | 结果 |
|---|---|---|---|
| TC-R（均匀随机） | 1000 | 每个 lane 取 0..255 均匀 | 1000 PASS |
| TC-X（边界密集） | 500 | 每 lane 从 `{00,01,7E,7F,80,81,FE,FF}` 抽取 | 500 PASS |
| 流式背靠背 | 1024 | 连续发射、按序比对 | 1024 PASS |

随机种子固定为 `20261027`，向量文件随仓库提交，可完全复现。

---

## 5. 时序实测

| 指标 | 定义 | 实测 |
|---|---|---|
| 单条延迟 L | 请求被接收的时钟沿到 `out_valid` 置位 | **3 cycle** |
| 非法指令延迟 | 同上，`out_illegal` 路径 | **3 cycle** |
| 吞吐 TP | 无依赖连续发射，平均每条约占周期 | **1.0 inst/cycle** |
| 总仿真周期 | 1518 用例 + 1024 流式 + 排空开销 | 10148 cycle |

与设计规格 §3.1 声明的 3 级流水（EX1 乘 / EX2 加法树 / WB 格式化）一致，无额外气泡。

---

## 6. 断言与自检

| 检查项 | 结果 |
|---|---|
| Python 参考模型闭式边界自检（5 项） | PASS（`logs/00_ref_model_selfcheck.log`） |
| C 参考模型闭式边界自检（5 项） | PASS（`logs/05_c_model_selfcheck.log`） |
| C 参考模型对 1518 条向量交叉比对 | **1518 / 1518 PASS**，0 失败（`logs/06_c_model_crosscheck.log`） |
| RTL 断言：`out_vd[127:32] == 0` | 0 次违反 |
| RTL 断言：valid 与 illegal 互斥 | 0 次违反 |
| RTL 断言：dirty 必须伴随 valid | 0 次违反 |
| 参数合法性（`K==8`、`ACC_W>=19`、`OUT_W>=ACC_W`） | 仿真启动即检查，未触发 |

---

## 7. 开发过程缺陷记录

| # | 阶段 | 现象 | 根因 | 修复 |
|---|---|---|---|---|
| D-01 | 综合/仿真 | Verilator `UNOPTFLAT`：`st2` 组合环告警 | 加法树用二维数组 + 生成块动态索引，工具无法判定元素级依赖 | 改为显式三级加法树（常数索引），同时更接近可综合写法（commit 见仓库） |
| D-02 | 测试台编译 | `Wid got` 与 `int got` 变量遮蔽导致编译失败 | 流式测试内变量命名冲突 | 重命名为 `done` / `vd_got` |
| D-03 | 构建 | `Cannot write build/obj_dir/...` | `-Mdir` 父目录不存在 | 构建脚本增加 `mkdir -p build` |

**功能缺陷数：0**（1518 用例未发现 DUT 功能错误）。

---

## 8. 未验证项与阻塞说明（重要）

以下项目属于阶段二/三要求，但阶段二执行时本环境无法执行或尚未执行，不计入本报告结论（后续状态已逐项标注）：

| # | 未完成项 | 原因 | 影响 | 计划 |
|---|---|---|---|---|
| U-01 | 在香山昆明湖 V2 中集成并仿真 | 香山源码与工具链已就绪（`build/xs-work/XiangShan` @ `16ae9dd`），集成尚未执行 | 阶段二"基于香山仿真环境"未闭环 | 按 `patches/xiangshan-vdot-integration.md` 执行 I1–I7（B2） |
| U-02 | 汇编级测试（`.S` + emu 运行） | 工具链与 emu 已就绪；`vadd.S` 已跑通，`vdot` 汇编用例待集成后补 | 阶段二 `vdot` 汇编级测试未执行 | 集成后复用同一向量集 |
| U-03 | NEMU 扩展 + difftest 协同仿真 | **已完成**（阶段三 T3.1–T3.4） | 1513/1513，RTL↔NEMU 0 mismatch | 见 `docs/phase3/cosim_report.md` |
| U-04 | 基线 vs vdot 真实加速比 | 依赖 U-01 | 阶段三 3.3 仅有估算 | 见 `docs/phase3/perf_analysis.md`（明确标注估算） |
| U-05 | 综合面积/时序 | 本阶段无 yosys/DC | 面积仅为结构性估算 | **阶段四部分关闭**：generic 综合 4186 单元 / 172 FF / 25 级 R2R，见 `docs/phase4/release_report.md` §3；PDK 级 µm²/ns 待环境 |

**结论表述约束**：本报告不得用于宣称"已在香山平台验证"，仅可表述为"vdot 功能单元模块级 RTL 已通过 1518 条用例验证"。

---

## 9. 覆盖情况评估

| 覆盖维度 | 目标 | 实际 |
|---|---|---|
| 符号组合（正/负/混合/零） | 4 类全覆盖 | 4/4 |
| 边界值（最大正/最大负/零/19 bit 边界） | 全覆盖 | 4/4 |
| lane 位置（lane0..lane7 单独有效） | 至少各 1 次 | 由 TC-B06/B07 与随机覆盖 |
| 配置组合（vl=0/正常、vm、SEW、LMUL） | 公开接口全组合 | 覆盖合法 2 类 + 非法 4 类 |
| 流水行为（单条、背靠背、按序） | 全覆盖 | 3 类均验证 |
| 代码行覆盖 | ≥95%（可选） | 未统计（Verilator `--coverage` 未启用） |

---

## 10. 结论与下一步

1. `vdot.vv` 功能单元模块级 RTL 功能正确：1518 条用例（含 3 类必测与 4 类边界）全部通过，128 bit 全宽比对无差异。
2. 时序符合设计：3 级流水、单条延迟 3 cycle、吞吐 1 inst/cycle、无气泡。
3. 位宽设计经边界用例证伪风险已消除（131072 边界正确）。
4. 下一步（按 IPD 计划）：
   - D1：部署 `xs-env`，把本模块以 Chisel/VFu 形式接入昆明湖 V2（U-01）；
   - D2：将 C 参考模型移植进 NEMU（U-03）；
   - D3：用同一向量集在 emu 上重跑，并与本报告结果比对，形成"单元级 + 系统级"双证据链。

---

## 附录 A：复现命令

```bash
# 一键：模型自检 -> 生成向量 -> C 模型交叉比对 -> 构建 -> 运行 -> 归档日志与波形
bash scripts/run_unit_tests.sh

# 分步
python3 tests/ref_vdot.py
python3 tests/gen_vectors.py -o tests/vectors/vdot_vectors.txt
gcc -O2 -std=c11 -o build/vdot_ref tests/model/vdot_ref.c
./build/vdot_ref --selfcheck
./build/vdot_ref tests/vectors/vdot_vectors.txt
bash scripts/build_sim.sh
./build/obj_dir/tb_vdot tests/vectors/vdot_vectors.txt docs/phase2/waveform/vdot_unit.vcd
```

## 附录 B：证据文件索引

| 证据 | 路径 |
|---|---|
| Python 模型自检日志 | `docs/phase2/logs/00_ref_model_selfcheck.log` |
| 向量生成日志 | `docs/phase2/logs/01_gen_vectors.log` |
| C 模型编译日志 | `docs/phase2/logs/04_c_model_build.log` |
| C 模型自检日志 | `docs/phase2/logs/05_c_model_selfcheck.log` |
| C 模型交叉比对日志（1518 条） | `docs/phase2/logs/06_c_model_crosscheck.log` |
| 仿真构建日志 | `docs/phase2/logs/02_build.log` |
| RTL 单元测试运行日志 | `docs/phase2/logs/03_unit_test.log` |
| 波形 | `docs/phase2/waveform/vdot_unit.vcd` |
| 测试向量（1518 条） | `tests/vectors/vdot_vectors.txt` |
