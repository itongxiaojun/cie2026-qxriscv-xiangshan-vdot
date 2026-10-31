#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VCD -> SVG 时序图渲染（仅依赖标准库）

用途：把 XiangShan emu 导出的波形（fst2vcd 转换得到的 VCD）中关心的信号
渲染成文档用时序图，供阶段一《vadd 执行过程》引用。

示例：
  python3 scripts/vcd_timeline.py wave.vcd --list "commit_valid,pc"
  python3 scripts/vcd_timeline.py wave.vcd -o timeline.svg \
      --signals "clock,difftest_commit_0_valid,pc" --start 1200 --end 1280
"""
import argparse
import re
import sys

ROW_H = 30
LEFT = 300
PX_PER_CHANGE = 0.35   # 每个时间点像素（按信号变化点压缩，非等比时间轴）
MIN_SEG = 4


def parse_vcd(path):
    scopes = []
    sigs = {}          # id -> {"name":..., "width":..., "changes":[(t,int)]}
    cur_t = 0
    in_header = True
    with open(path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("$scope"):
                parts = line.split()
                scopes.append(parts[2])
                continue
            if line.startswith("$upscope"):
                if scopes:
                    scopes.pop()
                continue
            if line.startswith("$var"):
                parts = line.split()
                # $var wire WIDTH ID NAME [$end]
                width = int(parts[2])
                vid = parts[3]
                name = parts[4]
                full = ".".join(scopes + [name])
                sigs[vid] = {"name": full, "width": width, "changes": []}
                continue
            if line.startswith("$enddefinitions"):
                in_header = False
                continue
            if in_header:
                continue
            if line.startswith("#"):
                cur_t = int(line[1:])
                continue
            if line.startswith("$"):
                continue
            m = re.match(r"b([01xzXZ]+)\s+(\S+)", line)
            if m:
                bits = m.group(1)
                vid = m.group(2)
                if vid in sigs:
                    val = None
                    if all(c in "01" for c in bits):
                        val = int(bits, 2)
                    sigs[vid]["changes"].append((cur_t, val))
                continue
            m = re.match(r"([01xzXZ])(\S+)", line)
            if m:
                vid = m.group(2)
                if vid in sigs:
                    ch = m.group(1)
                    val = int(ch) if ch in "01" else None
                    sigs[vid]["changes"].append((cur_t, val))
                continue
    return sigs


def pick(sigs, patterns):
    out = []
    for s in sigs.values():
        low = s["name"].lower()
        if any(p.lower() in low for p in patterns):
            out.append(s)
    return out


def rising_edges(sig):
    edges = []
    prev = None
    for t, v in sig["changes"]:
        if prev is not None and prev == 0 and v == 1:
            edges.append(t)
        prev = v
    return edges


def build_timeline(sig, t0, t1):
    """裁剪到 [t0,t1]，返回 [(t,val)]，含窗口起点保持值"""
    ch = [(t, v) for t, v in sig["changes"] if t <= t1]
    if not ch:
        return []
    # 窗口起点值
    start_val = None
    for t, v in ch:
        if t <= t0:
            start_val = v
    res = [(t0, start_val)]
    res += [(t, v) for t, v in ch if t0 < t <= t1]
    # 去掉连续重复
    out = []
    for t, v in res:
        if out and out[-1][1] == v:
            continue
        out.append((t, v))
    return out


def render(sigs, cycles, out_file, title):
    n = len(sigs)
    width = LEFT + max(MIN_SEG, cycles * PX_PER_CHANGE) + 40
    height = 60 + n * ROW_H + 30
    unit = width - LEFT - 20
    def x_of(t):
        return LEFT + (t - cycles[0]) * unit / max(1, (cycles[1] - cycles[0]))

    parts = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(width)}" '
                 f'height="{int(height)}" viewBox="0 0 {int(width)} {int(height)}" '
                 'font-family="Menlo,Consolas,monospace">')
    parts.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    parts.append(f'<text x="16" y="24" font-size="14" font-weight="bold" fill="#1f2937">{title}</text>')
    parts.append(f'<text x="16" y="44" font-size="11" fill="#6b7280">'
                 f'cycle {cycles[0]} – {cycles[1]}</text>')

    # 顶部时间轴
    span = cycles[1] - cycles[0]
    step = max(1, span // 10)
    for c in range(cycles[0], cycles[1] + 1, step):
        x = x_of(c)
        parts.append(f'<line x1="{x:.1f}" y1="50" x2="{x:.1f}" y2="{height-10}" stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="46" font-size="10" fill="#9ca3af" text-anchor="middle">{c}</text>')

    for i, s in enumerate(sigs):
        y = 60 + i * ROW_H
        parts.append(f'<text x="16" y="{y+18}" font-size="11" fill="#111827">{s["name"][-46:]}</text>')
        tl = build_timeline(s, cycles[0], cycles[1])
        if not tl:
            parts.append(f'<text x="{LEFT}" y="{y+18}" font-size="10" fill="#9ca3af">(no data)</text>')
            continue
        hi = y + 6
        lo = y + 24
        if s["width"] == 1:
            prev_v = None
            for j, (t, v) in enumerate(tl):
                x0 = x_of(t)
                x1 = x_of(tl[j + 1][0]) if j + 1 < len(tl) else x_of(cycles[1])
                if v is None:
                    parts.append(f'<rect x="{x0:.1f}" y="{hi}" width="{max(1,x1-x0):.1f}" height="{lo-hi}" '
                                 f'fill="#f3f4f6" stroke="#d1d5db"/>')
                    continue
                yy = lo if v == 1 else hi
                parts.append(f'<line x1="{x0:.1f}" y1="{yy}" x2="{x1:.1f}" y2="{yy}" stroke="#2563eb" stroke-width="1.6"/>')
                if prev_v is not None and prev_v != v:
                    parts.append(f'<line x1="{x0:.1f}" y1="{hi}" x2="{x0:.1f}" y2="{lo}" stroke="#2563eb" stroke-width="1.6"/>')
                prev_v = v
        else:
            for j, (t, v) in enumerate(tl):
                x0 = x_of(t)
                x1 = x_of(tl[j + 1][0]) if j + 1 < len(tl) else x_of(cycles[1])
                w = x1 - x0
                if v is None:
                    parts.append(f'<rect x="{x0:.1f}" y="{hi}" width="{max(1,w):.1f}" height="{lo-hi}" '
                                 f'fill="#f3f4f6" stroke="#d1d5db"/>')
                    continue
                parts.append(f'<rect x="{x0:.1f}" y="{hi}" width="{max(1,w):.1f}" height="{lo-hi}" '
                             f'fill="#eef2ff" stroke="#4338ca" stroke-width="1"/>')
                txt = format_val(v, s["width"])
                if w > 2.2 * len(txt) + 4:
                    parts.append(f'<text x="{(x0+x1)/2:.1f}" y="{y+20}" font-size="10" fill="#1e1b4b" '
                                 f'text-anchor="middle">{txt}</text>')
    parts.append('</svg>')
    with open(out_file, "w") as f:
        f.write("\n".join(parts))
    print(f"wrote {out_file} ({n} signals, {cycles[1]-cycles[0]} cycles)")


def format_val(v, width):
    if v is None:
        return "x"
    if width <= 4:
        return str(v)
    return hex(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vcd")
    ap.add_argument("--signals", default="", help="逗号分隔的名称子串")
    ap.add_argument("--list", default="", help="仅列出匹配名称")
    ap.add_argument("--start", type=int, default=None, help="起始 cycle")
    ap.add_argument("--end", type=int, default=None, help="结束 cycle")
    ap.add_argument("-o", "--out", default="timeline.svg")
    ap.add_argument("--title", default="XiangShan waveform")
    args = ap.parse_args()

    sigs = parse_vcd(args.vcd)
    print(f"parsed {len(sigs)} signals", file=sys.stderr)

    if args.list:
        pats = [p for p in args.list.split(",") if p]
        found = pick(sigs, pats)
        for s in sorted(found, key=lambda s: s["name"]):
            print(f'{s["width"]:>3}b  {s["name"]}')
        print(f"# matched {len(found)}", file=sys.stderr)
        return

    pats = [p for p in args.signals.split(",") if p]
    found = pick(sigs, pats)
    if not found:
        print("no signals matched", file=sys.stderr)
        sys.exit(1)
    clock = next((s for s in sigs.values() if s["name"].endswith(".clock")), None)
    edges = rising_edges(clock) if clock else []
    if edges:
        start = args.start if args.start is not None else edges[0]
        end = args.end if args.end is not None else edges[-1]
        start = max(start, edges[0])
        end = min(end, edges[-1])
        cycles = (start, end)
    else:
        ts = [t for s in found for t, _ in s["changes"]]
        cycles = (args.start or min(ts), args.end or max(ts))
    render(found, cycles, args.out, args.title)


if __name__ == "__main__":
    main()
