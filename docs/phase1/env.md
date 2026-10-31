# 阶段一 · 环境部署记录

本文记录"从零到 `hello xiangshan`"的完整部署过程，包括主机约束、工具链获取方式、香山版本锁定、
构建命令与踩坑修复，供评审复现。对应赛题要求 **1.1 环境部署验证 / 1.2 操作日志**。

## 1. 主机与约束

| 项 | 值 |
|---|---|
| 发行版 | Debian GNU/Linux 13.4 (trixie) |
| 内核 | 6.12.73+deb13-amd64 |
| CPU | 48 逻辑核 |
| 内存 | 31 GiB（另有 22 GiB swap） |
| 磁盘 | `/mnt/hdata` 约 270 GB 可用 |
| 权限 | **普通用户 `qxriscv`，无 root、无 sudo** |

关键约束：官方推荐的 `xs-env` 通过 Docker 镜像提供工具链，而 Docker 需要 root。
本机无法安装或用 Docker，因此采用**等价手工部署**：逐项安装 xs-env 镜像内的同版本组件，
并把它们放在用户目录下，用 `/mnt/hdata/qxriscv/xs-work/env.sh` 统一注入环境变量。

## 2. 版本锁定

以 `doc/` 赛题要求"昆明湖 V2"为准，取官方 `xs-env` 仓库固定的香山提交作为基线：

| 组件 | 版本 / 提交 | 说明 |
|---|---|---|
| xs-env | `OpenXiangShan/xs-env`（XiangShan 子模块 gitlink） | 版本裁决依据 |
| XiangShan | **`16ae9ddcda54fc9a2fddffad73174cf793ac7814`** | `feat(Top): make address spaces of seperate TL port configurable (#4496)`，2025-04-03 |
| 分支 | 本地 `kunminghu-v2-pin` | `git init` + `fetch --depth 1` 固定，不随上游漂移 |
| 子模块 | coupledL2 / fudian / huancun / openLLC / ready-to-run / rocket-chip / utility / yunsuan / difftest / aia | 全部对齐 gitlink（`git submodule status` 无 `+`/`-`） |

> 上游默认分支此刻是 `kunminghu-v3`（tip `a0c2a26`）。虽然 v3 也能构建，但与赛题"昆明湖 V2"
> 不符，故弃用已编译的 v3 副本，重建并固定到 `16ae9dd`。

## 3. 手工工具链清单

| 组件 | 版本 | 获取方式 | 路径 |
|---|---|---|---|
| JDK | OpenJDK **21.0.13** (`21.0.13+9-1-deb13u2-Debian`) | `apt-get download openjdk-21-jdk*` → `dpkg-deb -x` 解包 | `/mnt/hdata/qxriscv/tools/jdk` |
| Scala 构建器 mill | **0.12.17** | Maven Central `mill-dist-0.12.17.exe`（自解压 shell+jar） | `/mnt/hdata/qxriscv/tools/mill/mill-0.12.17` |
| firtool (CIRCT) | **1.62.1**（该提交 `.mill-version` 对应的 firtool） | mill/coursier 首次构建时自动下载 | `~/.cache/llvm-firtool/1.62.1` |
| RISC-V GCC | xPack **riscv-none-elf-gcc 15.2.0** | 官方 xpack tarball | `/mnt/hdata/qxriscv/tools/riscv` |
| Verilator | **5.034** (2025-02-24) | **源码构建**（`git clone` + `autoconf` + `make -j`） | `/mnt/hdata/qxriscv/cieriscv/.tools/verilator`，prefix `.tools/verilator-inst` |
| GTKWave / fst2vcd | 3.3.121 | `apt-get download gtkwave libjudy*` → `dpkg-deb -x` | `/mnt/hdata/qxriscv/tools/gtkwave` |
| NEMU 参考库 | 预编译 `riscv64-nemu-interpreter-so` | 随 XiangShan `ready-to-run` 子模块 | `ready-to-run/riscv64-nemu-interpreter-so` |

统一环境脚本 `xs-work/env.sh`：

```bash
export JAVA_HOME=/mnt/hdata/qxriscv/tools/jdk/usr/lib/jvm/java-21-openjdk-amd64
export RISCV_HOME=/mnt/hdata/qxriscv/tools/riscv
export PATH=$JAVA_HOME/bin:/mnt/hdata/qxriscv/tools/riscv/bin:/mnt/hdata/qxriscv/tools/bin:\
/mnt/hdata/qxriscv/cieriscv/.tools/verilator/bin:$PATH
export NOOP_HOME=/mnt/hdata/qxriscv/xs-work/XiangShan
export NEMU_HOME=/mnt/hdata/qxriscv/xs-work/XiangShan/difftest
export JVM_XMX=12G
```

`JVM_XMX=12G` 必须显式覆盖：Makefile 默认 `JVM_XMX ?= 40G`，本机 31 GiB 内存会直接 OOM。

## 4. 无 root 适配中的四个坑与修复

| 现象 | 根因 | 修复 |
|---|---|---|
| `Error loading java.security file` | deb 解包后大量符号链接仍指向 `/etc/java-21-openjdk/...`，本机不存在 | 遍历 `find -xtype l`，把断链重指向 `$JAVA_HOME/../etc/...` 对应文件 |
| `trustAnchors parameter must be non-empty`，mill/coursier 所有 HTTPS 下载失败 | 解包 JDK 未带 `lib/security/cacerts` | 从 `/etc/ssl/certs/ca-certificates.crt` 用 `keytool` 拆分 150 张证书；**必须为 JKS 格式**（PKCS12 放在默认路径不被识别） |
| `not found: object fudian`（370 个 Scala 文件编译失败） | `fudian`/`aia` 子模块目录为空（gitlink 存在但工作区未检出） | `git -C fudian checkout -f HEAD` + `git submodule update --init`（softfloat/testfloat） |
| `make emu` 被前台会话终止连带 kill | 长时间构建挂在交互终端进程组下 | 改后台运行 + 日志重定向（`make ... > build_emu.log 2>&1`），中断后只需重跑 Verilator 之后的阶段 |

## 5. 构建与运行命令

```bash
source /mnt/hdata/qxriscv/xs-work/env.sh
cd $NOOP_HOME
make emu -j8 EMU_TRACE=fst JVM_XMX=12G      # EMU_TRACE=fst 打开 FST 波形能力
```

产物：

| 产物 | 位置 | 说明 |
|---|---|---|
| `SimTop.sv` + 分离式 RTL | `build/rtl/` | Chisel elaborate + firtool 输出 |
| `build/emu` | `build/emu` | Verilator C++ 仿真器 |

耗时（本机实测见 [report.md](report.md) §2）：

| 阶段 | 耗时 |
|---|---|
| Chisel elaborate → FIR | 26 min 43 s（wall），峰值 RSS 13.2 GB |
| firtool 1.62.1 → SystemVerilog | 约 9 min（1.4 GB FIR） |
| Verilator 生成 C++ | 见 report.md |
| C++ 编译链接 | 见 report.md |

## 6. 裸机测试镜像

不经 `xs-env` 的 `riscv64-unknown-elf-gcc`，改用 xPack 工具链，参数：

```
-march=rv64gcv -mabi=lp64d -nostdlib -nostartfiles -fno-pic -mcmodel=medany -T link.ld
```

源码与脚本：[tests/phase1](../../tests/phase1/)

| 镜像 | 大小 | 说明 |
|---|---|---|
| `hello.bin` | 100 B | UART 逐字节输出问候语与真实 IP，`ebreak` 结束 |
| `vadd.bin` | 112 B | `vsetvli e8,m1` + `vle8.v`/`vadd.vv`/`vse8.v`，供波形分析 |

`build.sh` 会读取 `hostname -I` 首个地址写入 `ip_addr.h`，本次为 `192.168.0.168`。

## 7. 运行方式

```bash
cd $NOOP_HOME
./build/emu -i /mnt/hdata/qxriscv/cieriscv/build/phase1/hello.bin \
           --diff=ready-to-run/riscv64-nemu-interpreter-so
```

波形：

```bash
./build/emu -i /mnt/hdata/qxriscv/cieriscv/build/phase1/vadd.bin \
           --diff=ready-to-run/riscv64-nemu-interpreter-so \
           --dump-wave --wave-path=/mnt/hdata/qxriscv/cieriscv/docs/phase1/wave/vadd.fst
```

## 8. 已知限制

- 未使用官方 `xs-env` 镜像，组件版本按 xs-env 固定提交手工对齐；**不是**官方镜像的逐字节复现。
- 波形以 FST 采集，本机无 GTKWave GUI，用 `fst2vcd` + 自写脚本渲染时序图（见 [vadd_wave.md](vadd_wave.md)）。
- 无 root 导致无法安装新版 binutils/gtkwave 等系统包，一律解包到用户目录。
