#!/usr/bin/env bash
# 应用 / 校验 / 回滚香山 vdot.vv 集成补丁。
# 用法：bash scripts/apply_xiangshan_patch.sh {check|apply|revert} [香山源码目录]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH="$ROOT/patches/xiangshan-vdot.patch"
BASE="16ae9ddcda54fc9a2fddffad73174cf793ac7814"
ACTION="${1:-check}"
XS="${2:-${XS_REPO:-$ROOT/build/xs-work/XiangShan}}"

die() { echo "错误：$*" >&2; exit 1; }

[[ -f "$PATCH" ]] || die "找不到补丁：$PATCH"
[[ -d "$XS" ]] || die "找不到香山源码目录：$XS（可用第二个参数或 XS_REPO 指定）"
git -C "$XS" rev-parse --git-dir >/dev/null 2>&1 || die "$XS 不是 git 仓库"

HEAD_SHA="$(git -C "$XS" rev-parse HEAD)"
if ! git -C "$XS" merge-base --is-ancestor "$BASE" "$HEAD_SHA" 2>/dev/null; then
  echo "警告：当前 HEAD ${HEAD_SHA:0:7} 不是 $BASE 的后代，补丁上下文可能不匹配。" >&2
fi

# 状态：can=未应用可打；applied=已应用可回滚；conflict=上下文冲突
if git -C "$XS" apply --check "$PATCH" >/dev/null 2>&1; then
  STATE=can
elif git -C "$XS" apply -R --check "$PATCH" >/dev/null 2>&1; then
  STATE=applied
else
  STATE=conflict
fi

show_stat() {
  git -C "$XS" apply --numstat "$PATCH" | awk '
    { add += $1; del += $2; printf "  %s  +%s/-%s\n", $3, $1, $2 }
    END { printf "  合计：%d 个文件，+%d/-%d\n", NR, add, del }'
}

case "$ACTION" in
  check)
    case "$STATE" in
      can)      echo "未应用，可安全打补丁（HEAD ${HEAD_SHA:0:7}）" ;;
      applied)  echo "已应用（可 revert）" ;;
      conflict) git -C "$XS" apply --check "$PATCH" || true
                die "上下文冲突：确认 HEAD 是否在 $BASE 之上、5 个目标文件是否被改动" ;;
    esac
    ;;
  apply)
    [[ "$STATE" == applied ]] && { echo "补丁已应用，无需重复操作"; exit 0; }
    [[ "$STATE" == conflict ]] && die "上下文冲突，未做任何改动"
    git -C "$XS" apply "$PATCH"
    echo "已应用：$(basename "$PATCH")"
    show_stat
    ;;
  revert)
    [[ "$STATE" == can ]] && { echo "补丁未应用，无需回滚"; exit 0; }
    [[ "$STATE" == conflict ]] && die "无法反向应用，工作区可能已被改动"
    git -C "$XS" apply -R "$PATCH"
    echo "已回滚：$(basename "$PATCH")"
    show_stat
    ;;
  *)
    die "未知动作 $ACTION（可选 check / apply / revert）"
    ;;
esac
