# 阶段一 · 环境部署与执行记录

> **文档状态（2026-11-01 修订②）**：本文件已按**当前主机实测结果**重写。阶段一官方要求 1.1 / 1.2 / 1.3 已在当前环境全部跑通，证据见 §4 的日志与波形链接。
>
> - **§1–§5 当前环境**：可直接复跑的环境基线、版本锁定、构建过程与阶段一执行结果。
> - **§6 历史环境记录**：旧机器（用户 `qxriscv`、路径 `/mnt/hdata/...`）上的部署过程，**路径与命令均已失效，仅作追溯**。
>
> 结论先行：**阶段一已完成**。emu 由香山 `16ae9dd` 构建（EXIT=0），hello 输出官方要求的问候语并打印真实 IP，vadd 波形已采集且逐 cycle 讲解入库。

---

## 1. 当前环境结论

| 项 | 现状 |
|---|---|
| 工作区 | `/home/dbqxxs/xsriscv/cieriscv` |
| 用户 | `dbqxxs`（属 sudo 组但无免密 sudo；Docker 29.4.0 可用，本次未使用） |
| 工具链部署方式 | 全部解包到工作区 `.tools/`（JDK / mill / RISC-V GCC / Verilator / yosys），无需 root、不改系统目录 |
| `xs-env` | **未安装官方镜像**；按 `OpenXiangShan/xs-env` 固定提交逐项手工等价部署（与旧机做法一致） |
| 香山（XiangShan）源码 | **可用**：`build/xs-work/XiangShan`，commit `16ae9ddcda54fc9a2fddffad73174cf793ac7814` |
| RISC-V 工具链 | **可用**：xPack `riscv-none-elf-gcc` 15.2.0 / objcopy 2.45（`.tools/riscv/bin`） |
| emu | **已构建**：`build/xs-work/XiangShan/build/emu`（261,132,232 B） |
| difftest 参考模型 | **可用**：`build/xs-work/XiangShan/ready-to-run/riscv64-nemu-interpreter-so`（626,696 B） |
| 阶段一产物 | `build/phase1/hello.bin`（98 B）、`vadd.bin`（112 B），本次由 `tests/phase1/build.sh` 重新生成 |
| 阶段一证据 | `docs/phase1/logs/01–04`、`docs/phase1/wave/vadd_pipeline_wave.png`、[vadd_wave.md](vadd_wave.md) |
| 判定 | **完成**（M1 闭环） |

## 2. 主机基线

| 项 | 值 |
|---|---|
| 发行版 / 内核 | Debian GNU/Linux 13 (trixie) / `6.12.73+deb13-amd64` |
| CPU | 48 逻辑核 |
| 内存 | 31 GiB（另有 22 GiB swap） |
| 磁盘 | `/` 417 GB，已用 80%（可用约 82 GB） |
| 权限 | 普通用户 `dbqxxs`；无免密 sudo；Docker 29.4.0 可用 |
| 工作区 | `/home/dbqxxs/xsriscv/cieriscv` |

## 3. 工具可用性清单（2026-11-01 实测）

| 组件 | 状态 | 版本 / 位置 | 用途 |
|---|---|---|---|
| Python | 可用 | 3.13.5 | 参考模型、向量生成、协同仿真、波形解析 |
| gcc / g++ | 可用 | Debian 14.2.0 | C 参考模型、Verilator C++ 测试台、emu 链接 |
| GNU Make | 可用 | 4.4.1 | 构建 |
| Verilator | 可用 | 5.034 2025-02-24（`.tools/verilator`） | 单元级 RTL 仿真、严格 lint、emu 生成 |
| JDK | 可用 | Temurin 21.0.13+9（`.tools/jdk`） | mill / Chisel elaborate |
| mill | 可用 | 0.12.3（`.tools/bin/mill`） | 香山 RTL 生成 |
| RISC-V GCC | 可用 | xPack `riscv-none-elf-gcc` 15.2.0（`.tools/riscv`） | 阶段一裸机镜像 |
| 香山源码 + emu | 可用 | `build/xs-work/XiangShan` @ `16ae9dd` | 阶段一运行与波形采集、后续香山内集成 |
| NEMU | 可用 | `.tools/nemu`，commit `a683e0b` + `patches/nemu-vdot.patch` | NEMU 自测、协同仿真、基线计数 |
| yosys | 可用 | 0.52-2（`yosys` + `yosys-abc` deb 解包到 `.tools/yosys`） | generic 综合、逻辑深度（`docs/phase4/06_yosys_synth_3mode.log`） |
| Chisel 工具链 | 可用 | Chisel 6.6.0 + firtool 1.62.1（本地 coursier 缓存） | `rtl/chisel` 编译、elaboration 与 SystemVerilog 生成 |
| PDK 库 / DC / Genus | **缺失** | — | 面积（µm²）与时序（ns）签核 |
| GTKWave | **缺失** | — | 本次以 VCD + 自写脚本出图，未用 GUI |

## 4. 阶段一执行结果

### 4.1 官方 hello（要求 1.1）

```bash
PATH="$PWD/.tools/riscv/bin:$PATH" bash tests/phase1/build.sh   # IP_ADDR = 192.168.0.168
cd build/xs-work/XiangShan
./build/emu -i /home/dbqxxs/xsriscv/cieriscv/build/phase1/hello.bin \
    --diff=ready-to-run/riscv64-nemu-interpreter-so
```

实测输出（完整日志：[02_hello_run.log](logs/02_hello_run.log)）：

```
hello xiangshan, I am qxriscv, IP address: 192.168.0.168
Core 0: HIT GOOD TRAP at pc = 0x80000020
Core-0 instrCnt = 295, cycleCnt = 10,819, IPC = 0.027267
Host time spent: 74,084ms            # EXIT=0
```

判定：逐字满足官方要求（`hello xiangshan, I am <团队>` + `IP address` + 真实 IP），difftest 全程启用。

### 4.2 完整部署与操作日志（要求 1.2）

| 日志 | 内容 |
|---|---|
| [01_env_setup.log](logs/01_env_setup.log) | 主机基线 → 工具链版本 → 香山 commit 与 10 个子模块 → 镜像编译与 objdump → emu 构建命令/耗时 → 产物清单 |
| [02_hello_run.log](logs/02_hello_run.log) | hello 运行命令、原始输出、EXIT=0、判定与踩坑记录 |
| [03_vadd_run.log](logs/03_vadd_run.log) | vadd 运行 + 波形 dump 参数、VCD 产物、PASS 判定 |
| [04_wave_parse.log](logs/04_wave_parse.log) | `scripts/plot_phase1_wave.py` 的真实 stdout（信号命中表、关键事件、出图） |

四份日志均由本机命令输出生成，含实际命令、报错与解决、耗时。

### 4.3 vadd 波形与执行过程（要求 1.3）

```bash
cd build/xs-work/XiangShan
./build/emu -i /home/dbqxxs/xsriscv/cieriscv/build/phase1/vadd.bin \
    --diff=ready-to-run/riscv64-nemu-interpreter-so \
    --dump-wave -b 8200 -e 8360 --wave-path=/tmp/vadd_wave.vcd
cd /home/dbqxxs/xsriscv/cieriscv
python3 scripts/plot_phase1_wave.py /tmp/vadd_wave.vcd
```

| 产物 | 值 |
|---|---|
| 波形 | VCD 100,664,602 B（窗口 cycle 8200–8360；原始 VCD 100 MB 级，**不入库**） |
| 截图 | [wave/vadd_pipeline_wave.png](wave/vadd_pipeline_wave.png)（4 面板分阶段放大：取指 / 译码 / 执行 / 访存写回） |
| 分析文档 | [vadd_wave.md](vadd_wave.md)（逐 cycle 时间线 + 逐字节核对 + 复现命令） |
| 运行结果 | `HIT GOOD TRAP at pc = 0x80000038`，`instrCnt = 18`，`cycleCnt = 8,351`（Host 42,404 ms，EXIT=0） |

## 5. 版本锁定与构建

### 5.1 版本锁定

| 组件 | 版本 / 提交 |
|---|---|
| XiangShan | `16ae9ddcda54fc9a2fddffad73174cf793ac7814`（2025-04-03，昆明湖 V2 基线快照，`feat(Top): make address spaces of seperate TL port configurable (#4496)`） |
| 子模块 | coupledL2 `82079f4`、difftest `62e4540`、fudian `e1bd469`、huancun `90aaf59`、openLLC `614ceb4`、ready-to-run `ed8c30e`、rocket-chip `bea0af5d`、aia `9464aee`、utility `a8ca0c6`、yunsuan `cadd3c2` |
| JDK | Temurin `21.0.13+9`（`.tools/jdk`） |
| mill | `0.12.3`（`.tools/bin/mill`） |
| firtool | 由 mill 构建自动获取 |
| RISC-V GCC | xPack `riscv-none-elf-gcc` 15.2.0 / objcopy 2.45 |
| Verilator | `5.034 2025-02-24 rev v5.034` |
| difftest 解释器 | `ready-to-run/riscv64-nemu-interpreter-so`（626,696 B） |

> **基线口径（2026-11-05 核对）**：`16ae9dd` 的 GitHub 提交页带有 `kunminghu-v3` 分支标签，是因为它位于 V3 开发线的起点；同时它是 `kunminghu-v2` 分支的祖先提交（`compare/16ae9dd...kunminghu-v2`：behind 0 / ahead 684），且该快照源码内只有 `KunminghuV2Config`、尚无 `KunminghuV3Config`。因此本项目把它作为**昆明湖 V2 基线**：emu 按 `--config DefaultConfig` 构建（香山惯例 `DefaultConfig` 即昆明湖 V2 默认口径，未启用 `KunminghuV2Config` 的 `WithCHI`），并未启用任何 V3 配置或特性。

### 5.2 构建命令

```bash
mkdir -p build/rtl
mill -i -Djvm-xmx=12G -Djvm-xss=256m xiangshan.test.runMain top.SimTop \
    --target-dir build/rtl --config DefaultConfig --issue E.b \
    --firtool-opt "--repl-seq-mem --repl-seq-mem-file=SimTop.sv.conf" \
    --num-cores 1 --dump-fir --target systemverilog --split-verilog \
    --firtool-opt "-O=release --disable-annotation-unknown --lowering-options=explicitBitcast,disallowLocalVariables,disallowPortDeclSharing,locationInfoStyle=none" \
    --enable-difftest --full-stacktrace
make -C ./difftest emu SIM_TOP=SimTop DESIGN_DIR="$(pwd)" NUM_CORES=1 RTL_SUFFIX=sv
```

- `EMU_TRACE=vcd`：本次 emu 以 VCD 波形构建（`--dump-wave` 产物为 `.vcd`）。
- elaboration 期间有 148 条 warning（无 error），最终 `EXIT=0`。

### 5.3 构建耗时（`build/time.log` 摘要）

| 阶段 | 内容 | 耗时 | 峰值 RSS | 退出状态 |
|---|---|---|---|---|
| 1 | Chisel elaborate + firtool（`mill runMain top.SimTop`） | 15:33.44 | 12,984,920 KB | 0 |
| 2 | Verilator 生成 C++ 模型 | 8:42.61 | 12,573,408 KB | 0 |
| 3 | C++ 编译链接（`VSimTop.mk`） | 29:58.29 | 2,652,116 KB | 0 |

时间戳：`21:49:55` → `22:05:33` → `22:14:16` → `22:44`，**总耗时约 54 分钟**。

### 5.4 构建产物

| 产物 | 大小 |
|---|---|
| `build/xs-work/XiangShan/build/emu` | 261,132,232 B |
| `build/xs-work/XiangShan/build/rtl/SimTop.sv` | 1,162,006 B |
| `build/xs-work/XiangShan/build/rtl/SimTop.sv.conf` | 1,777 B |
| `ready-to-run/riscv64-nemu-interpreter-so` | 626,696 B |

## 6. 历史环境记录（旧机器，已失效，仅作追溯）

> 以下内容记录旧机器上的部署过程，供环境恢复时复用经验。**所有 `/mnt/hdata/...` 路径与 `qxriscv` 用户在当前环境不存在**，命令不可直接执行。

### 6.1 旧机器约束

| 项 | 值 |
|---|---|
| 发行版 / 内核 | Debian 13.4 (trixie) / 6.12.73+deb13-amd64 |
| CPU / 内存 | 48 核 / 31 GiB（另有 22 GiB swap） |
| 数据盘 | `/mnt/hdata` 约 270 GB |
| 权限 | 普通用户 `qxriscv`，**无 root、无 sudo、无 Docker** |

因 Docker 不可用，旧环境采用"手工等价部署"：按 `OpenXiangShan/xs-env` 固定提交逐项解包同版本组件，并用统一 `env.sh` 注入变量。

### 6.2 版本锁定（历史）

| 组件 | 版本 / 提交 |
|---|---|
| xs-env | `OpenXiangShan/xs-env`（XiangShan 子模块 gitlink） |
| XiangShan | `16ae9ddcda54fc9a2fddffad73174cf793ac7814`（昆明湖 V2 基线快照，2025-04-03） |
| 获取方式 | 按上述 SHA `fetch --depth 1`（HEAD 分离、无本地分支，不随上游漂移） |
| 子模块 | coupledL2 / fudian / huancun / openLLC / ready-to-run / rocket-chip / utility / yunsuan / difftest / aia |
| JDK | OpenJDK 21.0.13（deb 解包） |
| mill | 0.12.17（Maven Central 自解压） |
| firtool | 1.62.1（mill 首次构建自动下载） |
| RISC-V GCC | xPack `riscv-none-elf-gcc` 15.2.0 |
| Verilator | 5.034（源码构建） |
| GTKWave / fst2vcd | 3.3.121（deb 解包） |

旧环境统一脚本（历史，路径已失效）：

```bash
export JAVA_HOME=/mnt/hdata/qxriscv/tools/jdk/usr/lib/jvm/java-21-openjdk-amd64
export RISCV_HOME=/mnt/hdata/qxriscv/tools/riscv
export PATH=$JAVA_HOME/bin:/mnt/hdata/qxriscv/tools/riscv/bin:/mnt/hdata/qxriscv/tools/bin:$PATH
export NOOP_HOME=/mnt/hdata/qxriscv/xs-work/XiangShan
export NEMU_HOME=/mnt/hdata/qxriscv/xs-work/XiangShan/difftest
export JVM_XMX=12G   # Makefile 默认 40G，31 GiB 内存会 OOM
```

### 6.3 无 root 适配的四个坑（历史，可复用）

| 现象 | 根因 | 修复 |
|---|---|---|
| `Error loading java.security file` | deb 解包后符号链接仍指向 `/etc/java-21-openjdk/...` | `find -xtype l` 找出断链并重指向 `$JAVA_HOME/../etc/...` |
| `trustAnchors parameter must be non-empty`，mill/coursier HTTPS 全部失败 | 解包 JDK 缺 `lib/security/cacerts` | 用 `keytool` 从 `/etc/ssl/certs/ca-certificates.crt` 拆分证书，**必须 JKS 格式** |
| `not found: object fudian`（370 个 Scala 文件失败） | `fudian`/`aia` 子模块目录为空 | `git -C fudian checkout -f HEAD` + `git submodule update --init` |
| `make emu` 被终端中断连带 kill | 长时间构建挂在交互终端进程组 | 后台运行 + 日志重定向 |

### 6.4 旧环境构建与运行（历史命令）

```bash
source /mnt/hdata/qxriscv/xs-work/env.sh
cd $NOOP_HOME
make emu -j8 EMU_TRACE=fst JVM_XMX=12G
./build/emu -i /mnt/hdata/qxriscv/cieriscv/build/phase1/hello.bin \
           --diff=ready-to-run/riscv64-nemu-interpreter-so
./build/emu -i /mnt/hdata/qxriscv/cieriscv/build/phase1/vadd.bin \
           --diff=ready-to-run/riscv64-nemu-interpreter-so \
           --dump-wave --wave-path=/mnt/hdata/qxriscv/cieriscv/docs/phase1/wave/vadd.fst
```

旧环境记录耗时：Chisel elaborate → FIR 约 26 min 43 s（峰值 RSS 13.2 GB），firtool → SystemVerilog 约 9 min。

### 6.5 裸机镜像说明

源码：[tests/phase1](../../tests/phase1/)（`hello.S`、`vadd.S`、`link.ld`、`build.sh`）

| 镜像 | 大小 | 说明 |
|---|---|---|
| `hello.bin` | 98 B | UART 逐字节输出问候语与真实 IP，`nemu_trap` 结束 |
| `vadd.bin` | 112 B | `vsetvli e8,m1` + `vle8.v` / `vadd.vv` / `vse8.v`，供波形分析 |

编译参数：

```
-march=rv64gcv -mabi=lp64d -nostdlib -nostartfiles -fno-pic -mcmodel=medany -T link.ld
```

产物位于 `build/phase1/`（`build/` 被 `.gitignore` 排除）：`hello.bin`、`hello.elf`、`vadd.bin`、`vadd.elf`、`ip_addr.h`。

### 6.6 旧环境已知限制

- 未使用官方 `xs-env` 镜像，组件按固定提交手工对齐，**不是**镜像的逐字节复现。
- 波形以 FST 采集，旧机无 GTKWave GUI，用 `fst2vcd` + 自写脚本查看。
- 无 root，系统包一律解包到用户目录。

## 7. 已知限制与踩坑

| 项 | 说明 |
|---|---|
| emu 运行目录 | 必须在 `build/xs-work/XiangShan` 下执行，`--diff` 显式指向 `ready-to-run/riscv64-nemu-interpreter-so`；Makefile 默认相对路径在本仓库不存在 |
| UART 地址 | UART Lite 基址 `0x40600000`，THR 偏移 `+0x4` → `0x40600004` |
| hello 字符串 | 问候语必须单条 `.asciz`，拆分会因首个 `\0` 截断 |
| 程序结束 | 必须用 `nemu_trap`（`.word 0x0005006b`，`a0=0`）；`ebreak` 会 double trap |
| 波形窗口 | 不限定 `-b/-e` 会生成 1.5 GB 级 VCD；本次限定 8200–8360 |
| VCD 解析 | `$scope/$var/$upscope/$enddefinitions` 行首带空格，必须 `strip()` |
| 仍缺工具 | PDK / sbt 未就位 → PDK 面积与 ns 签核仍不可做；generic 综合已由 `.tools/yosys`（0.52-2）覆盖；Chisel 版已改用 mill + 缓存 firtool 编译（不依赖 sbt） |
| xs-env | 非官方镜像的逐字节复现，仅为同版本组件的手工对齐 |

## 8. 关联文档

| 文档 | 说明 |
|---|---|
| [vadd_wave.md](vadd_wave.md) | 阶段一 1.3：vadd 逐 cycle 执行过程与波形解读 |
| [logs/01–04](logs/) | 阶段一原始日志（部署 / hello / vadd / 波形解析） |
| [README 阶段状态](../../README.md) | 阶段一/二/三/四总览 |
| [任务进度跟踪表](../PROGRESS.md) | 里程碑、交付对照与变更记录 |
| [香山集成说明](../../patches/xiangshan-vdot-integration.md) | 环境就绪后的集成规程 |
