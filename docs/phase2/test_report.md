# 阶段二 测试报告：vdot 指令族（INT8 / INT4 / 三值）单元级验证

| 项目 | 内容 |
|---|---|
| 被测对象 | `rtl/verilog/VDot.v`（VLEN=128, K=8, ACC_W=20, OUT_W=32, DUAL_W=12, TERN_W=9） |
| 对应规格 | [ipd/01 设计规格书](file:///home/dbqxxs/xsriscv/cieriscv/ipd/01_vdot指令与微架构设计规格书.md) |
| 测试方案 | [ipd/02 测试与验证方案](file:///home/dbqxxs/xsriscv/cieriscv/ipd/02_测试与验证方案.md) |
| 报告版本 | v1.3（2026-11-08：扩展为三模式，新增 INT4/三值用例、模式自检与三模式 NEMU/Chisel 协同） |
| 执行日期 | 2026-10-27（初版）；2026-11-01（迁移后复跑）；2026-11-02（v1.2 回归复跑）；2026-11-08（v1.3 三模式回归） |
| 执行人 | B（验证） |
| **总体结论** | **PASS** —— 3047/3047 用例通过，0 失败；单条延迟 3 cycle，三模式吞吐 1 inst/cycle；行覆盖率 55/55 = 100%；Chisel 版等价回归 3047/3047 |

---

## 1. 结论摘要

| 指标 | 实测结果 |
|---|---|
| 用例总数（INT8 1518 / INT4 763 / 三值 764 / 保留 mode 2） | **3047 / 3047 通过** |
| 定向用例（功能 + 边界 + 配置/异常） | 18 / 18 通过 |
| 随机用例（均匀分布，三模式） | 全部通过 |
| 边界密集随机用例（取值域 8 个极值） | 全部通过 |
| 背靠背流式用例（按序比对，三模式） | 1024 / 1024 通过 |
| 三方模型一致性（Python / C / C++ 内联，3047 条） | 3047 / 3047 一致 |
| INT4 nibble 逐位定位（16 个 nibble 单独非零） | 16 / 16 通过 |
| 三值边界（`a=-128` 取反、`code=11` 归零、全 0） | 3 / 3 通过 |
| 逐 lane 定位自检（INT8 lane0..7 单独非零） | 8 / 8 通过 |
| `vstart` 幂等重放自检（同一请求连续重放 3 次） | 3 / 3 通过 |
| 保留 SEW 编码（`vsew=4`）拒绝 | PASS（illegal，不写回） |
| 保留模式（`mode=3`）拒绝 | PASS（illegal，不写回） |
| 复位空闲检查 | PASS |
| 失败用例 | **0** |
| 单条延迟（in_valid → out_valid） | **3 cycle**（写回路径与 illegal 路径均为 3） |
| 吞吐（无依赖连续发射，三模式） | **1.0 inst/cycle** |
| 总仿真周期 | 21588 cycle |
| 行覆盖率（Verilator `--coverage-line`，`--annotate-min 1`） | **55 / 55 = 100%** |
| Chisel 生成 RTL 等价回归（同一测试台/同一 3047 三模式向量） | **3047 / 3047 PASS**，3 cycle，三模式 1.0 inst/cycle |
| 仿真断言（`--assert`） | 0 触发（高位清零、valid/illegal 互斥等） |
| 128 bit 全宽比对 | 全部用例均比对整 128 bit，非仅低 32 bit |

关键边界结论全部命中：`+127×8 → 0x0001F808`、`-128×-128×8 → 0x00020000`（19 bit 边界）、`-130048 → 0xFFFE0400`；INT4 组和 `[-448,+512]`、三值组和 `[-1024,+1024]` 均在 12 bit 内，`a=-128` 的三值取反 `+128` 由 9 bit 承载。

> 本报告覆盖**单元级**（模块级 RTL 仿真）、**生成 RTL 等价回归**与**香山昆明湖 V2 emu 系统级验证**（§8，系统级为 INT8）。NEMU 三模式协同仿真见 [协同仿真日志](../phase3/01_nemu_cosim.log)。

---

## 2. 验证环境

| 项 | 取值 |
|---|---|
| 主机 | Linux x86_64，48 核，31 GB 内存 |
| 仿真器 | Verilator 5.034（本机从源码构建，`--assert --trace`；覆盖率用 `--coverage-line` + `verilator_coverage --annotate-min 1`） |
| 编译器 | g++ (Debian 14.2.0) `-O2 -std=c++17` |
| 参考模型 | Python 3.13.5（`tests/ref_vdot.py`）；C11（`tests/model/vdot_ref.c`，NEMU-ready） |
| Chisel 工具链 | Chisel 6.6.0 + mill 0.12.3 + Temurin JDK（`.tools/jdk`）+ firtool 1.62.1（`.tools/bin/mill`，本地 coursier 缓存） |
| 版本控制 | git，被测 RTL commit 见仓库提交记录 |
| 波形 | `docs/phase2/waveform/vdot_unit.vcd`（前 400 周期，GTKWave 可打开） |

**环境说明**：阶段二执行时主机无 Verilator 预装与 RISC-V 工具链，因此采用"从源码构建 Verilator + 模块级 C++ 测试台"的方式完成可执行的 RTL 仿真；这保证了本报告数据来自**真实 RTL 仿真**而非行为模型。2026-11-01 环境迁移后 Verilator 5.034 可用，单元回归可复跑（当前 v1.3 为 3047/3047 PASS）。

> **2026-11-01 迁移后复跑**：工作区迁至 `/home/dbqxxs/xsriscv/cieriscv`，重新执行 `bash scripts/run_unit_tests.sh`，当次（单模式）结果：1518/1518 PASS、延迟 3 cycle、吞吐 1 inst/cycle。迁移导致 `build/obj_dir` 中的旧 Makefile 指向旧目录而构建失败，已由 `scripts/build_sim.sh` 的陈旧产物自动清理修复。
>
> **2026-11-02 v1.2 复跑**：测试台新增 4 类自检（复位空闲、逐 lane、`vstart` 重放、保留 SEW），并接入行覆盖率与 Chisel 等价回归。`total_cycles` 由 10148 增加到 **10220**（新增自检用例与排空开销所致），单模式功能结论不变：1518/1518 PASS、0 失败。
>
> **2026-11-08 v1.3 三模式复跑**：新增 `vdot4x2.vv`（763 条）与 `vtdot.vv`（764 条），加保留 mode 2 条，用例总数 **3047**；`total_cycles` 增至 **21588**，行覆盖率 **55/55**，Chisel 等价 **3047/3047**，三模式吞吐均 1.0 inst/cycle，0 失败。

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
   - `tests/model/vdot_ref.c`（C11）对全部 **3047 条三模式向量**独立重算并比对，构成第三份实现；
   - 三份实现均不共享代码，结果两两一致后才用于判定 RTL。
4. **C 模型的双重用途**：同一文件保留纯函数接口 `vdot_vv()`，可直接移植进 NEMU（阶段三 3.1.1）。

### 3.2 测试台结构（`tests/tb/tb_vdot.cpp`）

| 功能 | 说明 |
|---|---|
| 逐用例驱动 | 每用例单独发一条请求，观察 3 周期后的写回 |
| 延迟测量 | 记录 in_valid 到 out_valid 的周期差 |
| 非写回检查 | `vl=0`、非法配置持续观察 8 周期，确认无写回、无误报 illegal |
| 流式测试 | 连续 1024 条请求，按序出队比对，验证流水线交错与背靠背正确性 |
| 复位空闲自检 | 复位释放后检查 `out_valid/out_illegal/out_dirty` 均为 0、`out_vd` 全 0 |
| 逐 lane 自检 | lane0..7 依次单独置非零（奇 lane 取 -5、偶 lane 取 +5），验证 8 个乘法通道各自定位正确 |
| `vstart` 重放自检 | 同一请求连续重放 3 次，结果需与期望及上一次写回完全一致（对应规格 §2.5 幂等性） |
| 保留 SEW 自检 | `vsew=4`（`3'b100`）必须判 illegal 且不写回，验证 `in_sew[2:0]` 未被截断 |
| 断言 | Verilator `--assert`：高位通道必须为 0；valid 与 illegal 不得同时有效；dirty 必须伴随 valid |
| 覆盖率 | `--coverage-line` 构建，退出前写出 `coverage.dat`，`verilator_coverage --annotate-min 1` 统计 |
| 波形 | 前 400 周期导出 VCD |

### 3.3 判定口径

- 写回类：`out_valid==1` 且 `out_vd[127:0] == 期望[127:0]`。
- 非法类：`out_illegal==1`、`out_valid==0`。
- `vl=0`：`out_valid==0` 且 `out_illegal==0`（既不写也不报错）。
- 任一不满足即判 FAIL，测试台返回非 0 退出码。

### 3.4 Chisel 版等价回归

`rtl/chisel/VDot.scala` 经 mill + firtool 生成 `rtl/chisel/VDotCore.sv`（475 行，含 `io_in_mode[1:0]`），再由 `rtl/chisel/VDotWrap.v` 把端口映射为与 `rtl/verilog/VDot.v` 完全相同的外部接口。因此可直接复用**同一测试台、同一 3047 条三模式向量、同一补充自检**，对两版实现逐位比对结果：

- 判定口径与 §3.3 完全相同；
- 两版输出（`cases_pass`、`latency_write`、`throughput`、`total_cycles`）必须一致；
- 证据：`docs/phase2/logs/08_chisel_build.log`（构建）与 `docs/phase2/logs/09_chisel_equiv.log`（运行）。

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
| TC-V01 vl-zero | `vl=0`（`in_vl_zero=1`） | 不写回、不报错、`vd` 不变 | PASS |
| TC-V02 vl-one | `vl=1`（`in_vl_zero=0`） | 正常写回；接口只暴露 `vl_zero`，`vl=1` 与 `vl=16` 在单元级不可区分（输出与 `vl` 数值无关，见 §2.4） | PASS |
| TC-V03 vstart replay（TB 自检） | 同一请求连续重放 3 次（全 `-128`，期望 `+131072`） | 每次写回均与期望及上一次一致（幂等） | 3 / 3 PASS |
| TC-E01 vm0 | `vm=0` | illegal，不写回 | PASS |
| TC-E02 sew-e16 | `SEW=e16`（`vsew=1`） | illegal，不写回 | PASS |
| TC-E03 lmul-m2 | `LMUL=m2`（`vlmul=1`） | illegal，不写回 | PASS |
| TC-E04 sew-e64 | `SEW=e64`（`vsew=3`） | illegal，不写回 | PASS |
| TC-E05 sew-reserved（TB 自检） | `SEW=保留编码`（`vsew=4`，`3'b100`） | illegal，不写回（验证 `in_sew[2:0]` 未被截断为 e8） | PASS |

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
| 总仿真周期 | 3047 用例 + 1024 流式 + 补充自检 + 排空开销 | **21588 cycle** |

与设计规格 §4.1 声明的 3 级流水（EX1 乘法/三值选择 / EX2 加法树 / WB 格式化）一致，无额外气泡。Chisel 生成 RTL 在同一测试台下的时序指标完全相同（3 cycle / 1.0 inst/cycle / 21588 cycle）。

---

## 6. 断言与自检

| 检查项 | 结果 |
|---|---|
| Python 参考模型闭式边界自检（5 项） | PASS（`logs/00_ref_model_selfcheck.log`） |
| C 参考模型闭式边界自检（5 项） | PASS（`logs/05_c_model_selfcheck.log`） |
| C 参考模型对 3047 条三模式向量交叉比对 | **3047 / 3047 PASS**，0 失败（`logs/06_c_model_crosscheck.log`） |
| RTL 断言：高位通道清零（INT8 `[127:32]` / 双结果 `[127:64]`，按 `out_mode` 区分） | 0 次违反 |
| RTL 断言：valid 与 illegal 互斥 | 0 次违反 |
| RTL 断言：dirty 必须伴随 valid | 0 次违反 |
| 参数合法性（`K==8`、`ACC_W>=19`、`OUT_W>=ACC_W`、`DUAL_W>=12`、`TERN_W>=9`） | 仿真启动即检查，未触发 |
| 复位空闲（`out_valid/out_illegal/out_dirty=0`，`vd=0`） | PASS（`logs/03_unit_test.log`） |
| 逐 lane 通道定位（8 个 lane 各自单独非零） | 8 / 8 PASS（`logs/03_unit_test.log`） |
| `vstart` 幂等重放（同一请求连续 3 次） | 3 / 3 PASS（`logs/03_unit_test.log`） |
| 保留 SEW 编码 `vsew=4` 拒绝 | PASS（`logs/03_unit_test.log`） |
| 保留模式 `mode=3` 拒绝 | PASS（`logs/03_unit_test.log`） |
| INT4 nibble 逐位定位 | 16 / 16 PASS（`logs/03_unit_test.log`） |
| 三值边界（`a=-128` 取反、`code=11` 归零） | 3 / 3 PASS（`logs/03_unit_test.log`） |
| Chisel 生成 RTL 与 Verilog 版同向量等价 | 3047 / 3047 PASS（`logs/09_chisel_equiv.log`） |
| Chisel 版断言（firtool 生成的 SV 断言） | 0 次违反（`logs/09_chisel_equiv.log`） |

---

## 7. 开发过程缺陷记录

| # | 阶段 | 现象 | 根因 | 修复 |
|---|---|---|---|---|
| D-01 | 综合/仿真 | Verilator `UNOPTFLAT`：`st2` 组合环告警 | 加法树用二维数组 + 生成块动态索引，工具无法判定元素级依赖 | 改为显式三级加法树（常数索引），同时更接近可综合写法（commit 见仓库） |
| D-02 | 测试台编译 | `Wid got` 与 `int got` 变量遮蔽导致编译失败 | 流式测试内变量命名冲突 | 重命名为 `done` / `vd_got` |
| D-03 | 构建 | `Cannot write build/obj_dir/...` | `-Mdir` 父目录不存在 | 构建脚本增加 `mkdir -p build` |
| D-04 | RTL 接口 | `vsew=4`（保留编码）被误判为合法 e8 | `in_sew` 仅 2 bit，`3'b100` 低 2 位为 0 被截断 | `in_sew` 改为 3 bit（与 `vtype.vsew` 同宽），新增 TC-E05 覆盖（v1.2） |
| D-05 | Chisel elaboration | `Width of VDotCore.s2Sum: Reg[SInt] is unknown!` | `RegNext(sum2)` 继承宽度推断节点，寄存器位宽无法静态确定 | `treeSum` 每级 `(a +& b)(ACCW-1,0)` 显式截断；`s2Sum` 改为 `RegInit(0.S(ACCW.W))` |
| D-06 | Chisel 生成 RTL | firtool 报 `unicode escape not supported in string` | 断言消息含中文，firtool 1.62.1 不支持 SV 字符串 Unicode 转义 | 断言消息改为 ASCII 英文 |
| D-07 | 香山集成/emu | `vl=0` 用例 difftest 报 `v3` 为随机值（`right=0xcafebabedeadbeef`，`wrong=0xbe6cbc9f82570e7a`） | FU 用 `vecWen` 屏蔽写回，但提交阶段仍把架构 `vd` 映射改到重命名后的物理寄存器，该寄存器未被写 → 架构值变成随机数 | 写回端口保持有效，`vstart>=vl` 时回写 `oldVd`（与 `VIAluFix` 同一约定）；不再用 `vecWen` 抑制 |
| D-08 | 香山集成/RTL | 生成 RTL 中 SEW/LMUL/vill 检查全部消失，只剩 `~vm` 与 `vstart` | `DataConfig.VlData` 宽度仅 8 bit（只承载 `vl`），`outVConfig.vtype` 恒 0 被综合优化掉 | 非法判定改用控制通路 `outVecCtrl.vill/vsew/vlmul`（与 `VIAluFix` 一致） |
| D-09 | 测试/NEMU 协同 | 三值 one-hot 用例得到 `a[0]*codes[0]`，激活与权重错位 | `mini_asm._vdot_vv(funct6, vd, vs2, vs1)` 参数命名与 RISC-V 字段顺序相反（vs1 应在 bits[19:15]） | 改为 `(funct6, vd, vs1, vs2)`，三条指令方法与 `build_program` 调用点统一（v1.3） |

**模块级功能缺陷数：0**（3047 条三模式用例未发现 DUT 功能错误）。D-04 是接口位宽导致的功能性误判风险，已由新增 TC-E05 覆盖并在 v1.2 修复。D-07/D-08 属系统集成阶段暴露的问题——模块级测试台只有 `vecWen` 与显式 `vtype` 端口，无法覆盖“重命名/提交语义”和“`VlData` 仅 8 bit”的约束，故仅在香山 emu 中可见。v1.3 另发现并修复测试侧缺陷 D-09（`mini_asm` 的 vs1/vs2 参数顺序与 RISC-V 字段相反，导致 NEMU 三值用例激活/权重写反）。

---

## 8. 系统级（香山昆明湖 V2 emu）验证状态

阶段二初稿曾把 U-01/U-02/U-04 列为阻塞项。本轮已在本机真实部署香山昆明湖 V2 仿真环境并完成集成、汇编级测试与实测加速比，状态如下：

| # | 项目 | 状态 | 证据 |
|---|---|---|---|
| U-01 | 在香山昆明湖 V2 中集成并仿真 | **已关闭** | 香山 @ `16ae9dd`（昆明湖 V2 基线，`DefaultConfig`，VLEN=128），`vdot` 接入 VFEX0；重新生成 RTL（`build/rtl/VDotUnit.sv`）并重建 emu；`vdot_directed` 在 emu + difftest 下 `HIT GOOD TRAP`（992 inst / 13,565 cyc），0 mismatch。见 `logs/xs_emu_vdot_directed.log` |
| U-02 | 汇编级测试（`.S` + emu 运行） | **已关闭** | `tests/phase2/xs_emu/vdot_directed.S` 7 用例（含 `vl=0`）全部与 NEMU 一致（`DIRECTED fails=00000000`）；`vdot_illegal.S` 5 类非法配置 5/5 触发 illegal trap（`ILLEGAL traps=00000005 other=00000000`）。见 `logs/xs_emu_vdot_illegal.log` |
| U-03 | NEMU 扩展 + difftest 协同仿真 | **已完成（三模式）** | 3032 用例 / 4551 结果字 / 0 mismatch；三模式 boundary 全 PASS，见 `docs/phase3/01_nemu_cosim.log`；本轮 emu 里的 difftest 参考模型即该 NEMU 扩展 |
| U-04 | 基线 vs vdot 真实加速比 | **已关闭（实测）** | emu 实测 cycleCnt（NITER=2000）：empty 11,108 / vdot 12,123 / rvv 23,109 / scalar 21,022；`vdot` 0.51 cyc/iter vs 标量 4.96 cyc/iter ≈ **9.8×**（lane 公平；对 RVV 基线 6.00 cyc/iter 为 11.8×，16-lane 上界，见 `perf_analysis.md` §6.4）。见 `docs/phase3/perf_analysis.md` §6 与 `logs/xs_emu_perf_*.log` |
| U-05 | 综合面积/时序 | 部分关闭 | generic 综合 4186 单元 / 172 FF / 25 级 R2R（**INT8 单模式历史值**），见 `docs/phase4/release_report.md` §3；三模式面积与 PDK 级 µm²/ns 待环境 |

### 8.1 验证口径与边界

1. **可以宣称**：`vdot` 指令族已作为香山昆明湖 V2 的向量功能单元完成集成；模块级 3047 条三模式用例全部通过；INT8 已在香山 `emu`（Verilator）+ difftest 上跑通 7+5 条汇编用例。INT4/三值的系统级 emu 尚未重跑（Scala 编译已 PASS）。
2. **不可宣称**：未经综合/布局布线的面积、时序（U-05），以及未在 FPGA/流片平台上的结果。性能数据为 Verilator 功能级仿真的周期数，仅用于横向对比，不代表最终频率下的绝对性能。
3. **已知工具边界**：本 emu 构建中 difftest 对“陷阱指令”存在参考模型侧的一步滞后（DUT 提交 `mepc/mcause/mstatus` 后，NEMU 在同一比较点仍为旧值），用一条普通非法指令 `.word 0` 即可复现（`logs/xs_emu_baseline_illegal_difftest.log`），与本模块无关。因此非法配置用例采用程序内架构自检（`--no-diff`）方式，见 `tests/phase2/xs_emu/run_emu.sh`。
4. **`vstart` 约束**：本实现按整寄存器语义，`vstart != 0` 一律按非法指令处理（`VDotUnit` 与 NEMU 扩展一致），不支持向量重启。

---

## 9. 覆盖情况评估

| 覆盖维度 | 目标 | 实际 |
|---|---|---|
| 符号组合（正/负/混合/零，三模式） | 全覆盖 | 全通过 |
| 边界值（INT8 19-bit / INT4 12-bit / 三值 9-bit 边界） | 全覆盖 | 全通过 |
| lane / nibble 位置（INT8 lane0..7、INT4 nibble0..15 单独有效） | 至少各 1 次 | **逐 lane 8/8 + nibble 16/16** + 随机 |
| 配置组合（vl=0/正常、vm、SEW、LMUL、mode） | 公开接口全组合 | 合法 2 类 + 非法 6 类（含保留 SEW 与 mode=3） |
| 流水行为（单条、背靠背、按序、重放） | 全覆盖 | 4 类均验证 |
| 复位行为 | 复位后空闲 | PASS |
| 代码行覆盖 | ≥95% | **55/55 = 100%**（Verilator `--coverage-line`，`--annotate-min 1`，见 `logs/07_coverage.log`） |
| Chisel 版等价 | 与 Verilog 同结果 | 3047/3047 PASS |
| 系统级集成（香山昆明湖 V2 emu） | 合法功能 + 非法配置 | INT8 合法 7/7（difftest 0 mismatch）+ 非法 5/5（架构自检） |

---

## 10. 结论与下一步

1. 三条指令功能正确：3047 条用例（INT8 1518 / INT4 763 / 三值 764 / 保留 mode 2，含 3 类必测与 4 类边界）全部通过，128 bit 全宽比对无差异；逐 lane 8/8、nibble 16/16、三值边界 3/3、`vstart` 重放 3/3、保留 SEW 与保留 mode 拒绝、复位空闲均 PASS。
2. 时序符合设计：3 级流水、单条延迟 3 cycle、三模式吞吐 1 inst/cycle、无气泡；MAC/cycle = 8:16:16。
3. 位宽设计经边界用例证伪风险已消除：INT8 `+131072`（19 bit）、INT4 组和 `[-448,+512]`（12 bit）、三值 `a=-128` 取反 `+128`（9 bit）与组和 `+1024`（12 bit）全部命中。
4. 证据链完整：行覆盖率 55/55 = 100%；Chisel 生成 RTL 与 Verilog 版在同一测试台/同一 3047 条三模式向量下 3047/3047 等价；NEMU 三模式协同 3032 用例 / 4551 字 / 0 fail。
5. 系统级证据（INT8，2026-11-03）：模块已接入香山昆明湖 V2 并在 emu 上与 NEMU difftest 对齐运行——合法用例 7/7、非法配置 5/5，形成"单元级 + 系统级"双证据链（U-01/U-02 关闭）；同时得到实测加速比 9.8×（U-04）。三模式 Scala 编译 PASS，INT4/三值的 emu 重跑列为 B6。
6. 剩余（阶段四/五）：三模式综合面积、PDK 级面积时序（U-05）与真实平台/FPGA 结果。

---

## 附录 A：复现命令

```bash
# 一键（6 步）：模型自检 -> 生成向量 -> C 模型交叉比对 -> 构建 -> 运行 -> 行覆盖率
bash scripts/run_unit_tests.sh

# 分步
python3 tests/ref_vdot.py
python3 tests/gen_vectors.py -o tests/vectors/vdot_vectors.txt
gcc -O2 -std=c11 -o build/vdot_ref tests/model/vdot_ref.c
./build/vdot_ref --selfcheck
./build/vdot_ref tests/vectors/vdot_vectors.txt
bash scripts/build_sim.sh
./build/obj_dir/tb_vdot tests/vectors/vdot_vectors.txt docs/phase2/waveform/vdot_unit.vcd

# Chisel 版等价回归（生成 RTL + 同一测试台）
bash scripts/run_chisel_equiv.sh

# 全量 7 步回归（单元 -> 严格 lint -> Chisel 等价 -> NEMU 自测 -> RTL↔NEMU 协同 -> 基线）
bash scripts/run_all.sh

# ---------------------------------------------------------------
# 系统级（香山昆明湖 V2 emu）：重新生成 RTL -> 重建 emu -> 跑汇编用例
# ---------------------------------------------------------------
cd build/xs-work/XiangShan
export NOOP_HOME=$(pwd) JAVA_HOME=$PWD/../../../.tools/jdk
export PATH=$PWD/../../../.tools/verilator/bin:$PWD/../../../.tools/bin:$PATH
mill -i -Djvm-xmx=12G xiangshan.test.runMain top.SimTop \
  --target-dir build/rtl --config DefaultConfig --issue E.b --num-cores 1 \
  --target systemverilog --split-verilog --enable-difftest \
  --firtool-opt "--repl-seq-mem --repl-seq-mem-file=SimTop.sv.conf" \
  --firtool-opt "-O=release --disable-annotation-unknown --lowering-options=explicitBitcast,disallowLocalVariables,disallowPortDeclSharing,locationInfoStyle=none"
make -C ./difftest emu -j48 SIM_TOP=SimTop DESIGN_DIR=$(pwd) NUM_CORES=1 RTL_SUFFIX=sv

# 汇编用例（在仓库根目录）：编译 -> 运行（difftest 关闭仅用于非法配置用例）
cd -
bash tests/phase2/xs_emu/build.sh
bash tests/phase2/xs_emu/run_emu.sh            # 六个用例依次运行，日志写入 docs/phase2/logs/
```

## 附录 B：证据文件索引

| 证据 | 路径 |
|---|---|
| Python 模型自检日志 | `docs/phase2/logs/00_ref_model_selfcheck.log` |
| 向量生成日志 | `docs/phase2/logs/01_gen_vectors.log` |
| C 模型编译日志 | `docs/phase2/logs/04_c_model_build.log` |
| C 模型自检日志 | `docs/phase2/logs/05_c_model_selfcheck.log` |
| C 模型交叉比对日志（3047 条三模式） | `docs/phase2/logs/06_c_model_crosscheck.log` |
| 仿真构建日志 | `docs/phase2/logs/02_build.log` |
| RTL 单元测试运行日志 | `docs/phase2/logs/03_unit_test.log` |
| 行覆盖率构建日志 | `docs/phase2/logs/07_coverage_build.log` |
| 行覆盖率运行日志 | `docs/phase2/logs/07_coverage_run.log` |
| 行覆盖率统计（55/55 = 100%） | `docs/phase2/logs/07_coverage.log` |
| 行覆盖率标注源码 | `build/cov_line_annotated/VDot.v` |
| Chisel 等价回归构建日志 | `docs/phase2/logs/08_chisel_build.log` |
| Chisel 等价回归运行日志（3047/3047） | `docs/phase2/logs/09_chisel_equiv.log` |
| Chisel 生成的 SystemVerilog | `rtl/chisel/VDotCore.sv` |
| Chisel 端口适配壳 | `rtl/chisel/VDotWrap.v` |
| 波形 | `docs/phase2/waveform/vdot_unit.vcd` |
| 测试向量（3047 条三模式） | `tests/vectors/vdot_vectors.txt` |
| 香山 emu · 定向用例（difftest，7/7） | `docs/phase2/logs/xs_emu_vdot_directed.log` |
| 香山 emu · 非法配置（自检 5/5） | `docs/phase2/logs/xs_emu_vdot_illegal.log` |
| 香山 emu · 非法配置 difftest 误报复现 | `docs/phase2/logs/xs_emu_vdot_illegal_difftest.log` |
| 香山 emu · 普通非法指令 difftest 误报（对照） | `docs/phase2/logs/xs_emu_baseline_illegal_difftest.log` |
| 香山 emu · 性能基线（empty/vdot/rvv/scalar） | `docs/phase2/logs/xs_emu_perf_{empty,vdot,rvv,scalar}.log` |
