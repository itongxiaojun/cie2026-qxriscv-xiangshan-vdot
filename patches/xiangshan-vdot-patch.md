# 香山 `vdot.vv` 集成补丁说明

对应文件：[`xiangshan-vdot.patch`](xiangshan-vdot.patch)（5 个文件，`+119/−7`），基线：香山 `16ae9dd`（昆明湖 V2 基线快照，`DefaultConfig`，VLEN=128）。

## 1. 补丁用途

把 `vdot.vv`（SEW=8、K=8、ACC_W=20、VLEN=128）接入香山昆明湖 V2 的向量执行通路，共 I1–I7 七项改动：

| 文件 | +/− | 作用 |
|---|---|---|
| `src/main/scala/xiangshan/Parameters.scala` | +1/−1 | 新增 `VdotCfg`（`vl` 上限、写回延迟等参数） |
| `src/main/scala/xiangshan/backend/decode/VecDecoder.scala` | +8/−0 | 识别 `vdot.vv`（`opcode 1010111`、`funct6 100100`）并映射到 `Vdot` |
| `src/main/scala/xiangshan/backend/fu/FuType.scala` | +7/−2 | 新增 `FuType.vdot` 与 `fuConfig` 映射 |
| `src/main/scala/xiangshan/backend/fu/FuConfig.scala` | +25/−4 | 在 VFEX0 注册 `VDotUnit`（`VecPipedFuncUnit`，延迟 3、吞吐 1/cycle） |
| `src/main/scala/xiangshan/backend/fu/wrapper/VDotUnit.scala` | +78/−0 | **新增**执行单元：按 lane 累加点积、`vl==0` 不写回、4 类非法配置触发 `EX_II` |

补丁**不包含**：模块级 `rtl/verilog/VDot.v`、Chisel 源、NEMU 扩展（见 [`nemu-vdot.patch`](nemu-vdot.patch)）、emu 构建产物与波形；这些在仓库其他目录或运行时生成。

## 2. 前置条件

- 香山源码位于 `16ae9dd`（或其祖先之上、且未改动上述 5 个文件）；
- 已具备 JDK 21 / mill / firtool 环境（重建 RTL 与 emu 时需要，本补丁本身不依赖）；
- 工作区干净，或有能力区分业务改动与补丁改动。

## 3. 应用、校验与回滚

推荐用脚本（在仓库根目录执行）：

```bash
# 仅检查（不改文件）
bash scripts/apply_xiangshan_patch.sh check

# 应用
bash scripts/apply_xiangshan_patch.sh apply

# 回滚
bash scripts/apply_xiangshan_patch.sh revert

# 指定其它香山工作树
bash scripts/apply_xiangshan_patch.sh check /path/to/XiangShan
```

脚本行为：
- `check` 自动区分「未应用（可 apply）」「已应用（可 -R）」与「上下文冲突」三种状态；
- `apply` / `revert` 先执行 `git apply --check`，通过后才真正改动；
- 结束时输出 `git diff --stat`，便于确认 5 个文件 +119/−7；
- 默认工作树 `build/xs-work/XiangShan`，可用 `XS_REPO` 环境变量或第二个参数覆盖。

手工等价命令：

```bash
cd build/xs-work/XiangShan
git apply --check ../../patches/xiangshan-vdot.patch
git apply         ../../patches/xiangshan-vdot.patch
# 回滚
git apply -R      ../../patches/xiangshan-vdot.patch
```

## 4. 应用后的验证

补丁只改源码，需自行重生成 RTL 并重建 emu：

```bash
cd build/xs-work/XiangShan
make -C . rtl   # 或按 env.md §5.2 的 mill/firtool 流程
make -C . emu CONFIG=DefaultConfig
```

期望结果（历史实测，见 `docs/phase2/test_report.md`、`docs/phase3/`）：
- 系统级定向用例 7/7，difftest 0 mismatch；非法配置 5/5 触发 `EX_II`；
- 性能四内核全部 `PERF result=OK`；
- 单元级回归 3047/3047（三模式）与补丁无冲突（模块 RTL 独立验证）；三模式 Scala 编译 573 任务 0 error。

## 5. 边界与限制

- 补丁上下文绑定 `16ae9dd`；换基线提交需重新生成 diff，或至少 `git apply -3` 处理冲突后复核。
- 只覆盖香山侧集成；NEMU 侧改动须另打 `nemu-vdot.patch`。
- 不改变默认配置：仍为 `DefaultConfig`（昆明湖 V2 口径），未启用 V3 配置。
- 若工作区已有改动，`apply` 可能因上下文不匹配失败；先 `git status` 确认，不要强推。
