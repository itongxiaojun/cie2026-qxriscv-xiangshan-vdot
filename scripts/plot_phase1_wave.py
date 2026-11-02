#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段一 1.3：从香山 emu 导出的 VCD 抽取信号，绘制 vadd.vv 流水线波形图。

用法：
  python3 scripts/plot_phase1_wave.py <vadd.vcd> [-o out.png]

VCD 来源（窗口必须覆盖 8200–8360）：
  cd build/xs-work/XiangShan
  ./build/emu -i <repo>/build/phase1/vadd.bin \
      --diff=ready-to-run/riscv64-nemu-interpreter-so \
      --dump-wave -b 8200 -e 8360 --wave-path=/tmp/vadd_wave.vcd

说明：
  - VCD 时间戳即 difftest 的 cycleCnt，每个 cycle 连续编号；图中横轴单位均为 cycle。
  - 本脚本同时向 stdout 打印"信号命中表 + 关键事件表"，即 docs/phase1/logs/04_wave_parse.log 的来源。
  - 依赖 matplotlib 与中文字体 Noto Sans CJK SC。
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'docs/phase1/wave/vadd_pipeline_wave.png')
LO, HI = 8200, 8360

SCOPE = 'l_soc > core_with_l2 > core > '
SIGS = {
    'fetch_valid': SCOPE + 'frontend > inner_ibuffer > outputEntries_0_valid',
    'fetch_pc':    SCOPE + 'frontend > inner_ibuffer > outputEntries_0_bits_pc',
    'fetch_inst':  SCOPE + 'frontend > inner_ibuffer > outputEntries_0_bits_inst',
    'dec_valid':   SCOPE + 'backend > inner_ctrlBlock > decodePipeRenameModule > io_in_valid',
    'dec_pc':      SCOPE + 'backend > inner_ctrlBlock > decodePipeRenameModule > io_in_bits_pc',
    'dec_inst':    SCOPE + 'backend > inner_ctrlBlock > decodePipeRenameModule > io_in_bits_instr',
    'vialu_in':    SCOPE + 'backend > inner_vfExuBlock > exus_2 > VialuFix > io_in_valid',
    'vialu_out':   SCOPE + 'backend > inner_vfExuBlock > exus_2 > VialuFix > io_out_valid',
    'vialu_op':    SCOPE + 'backend > inner_vfExuBlock > exus_2 > VialuFix > io_in_bits_ctrl_fuOpType',
    'vialu_vsew':  SCOPE + 'backend > inner_vfExuBlock > exus_2 > VialuFix > io_in_bits_ctrl_vpu_vsew',
    'vldu0_v':     SCOPE + 'memBlock > io_mem_to_ooo_writebackVldu_0_valid',
    'vldu1_v':     SCOPE + 'memBlock > io_mem_to_ooo_writebackVldu_1_valid',
    'vldu0_d':     SCOPE + 'memBlock > io_mem_to_ooo_writebackVldu_0_bits_data',
    'vldu1_d':     SCOPE + 'memBlock > io_mem_to_ooo_writebackVldu_1_bits_data',
    'st_in_v':     SCOPE + 'memBlock > inner_StoreUnit_1 > io_vecstin_valid',
    'st_dc_v':     SCOPE + 'memBlock > inner_StoreUnit_1 > io_dcache_req_valid',
    'st_s3_v':     SCOPE + 'memBlock > inner_StoreUnit_1 > s3_valid',
    'st_out_v':    SCOPE + 'memBlock > inner_StoreUnit_1 > io_vecstout_valid',
    'st_vaddr':    SCOPE + 'memBlock > inner_StoreUnit_1 > io_vecstout_bits_vaddr',
}


def parse_header(path):
    scope, path2id, id2width = [], {}, {}
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.startswith('$scope'):
                scope.append(s.split()[2])
            elif s.startswith('$upscope'):
                scope.pop()
            elif s.startswith('$var'):
                p = s.split()
                full = ' > '.join(scope[2:]) + ' > ' + p[4]
                path2id[full] = p[3]
                id2width[p[3]] = int(p[2])
            elif s.startswith('$enddefinitions'):
                break
    return path2id, id2width


def parse_changes(path, id2name):
    changes = {n: [] for n in id2name.values()}
    t = 0
    started = False
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not started:
                if s.startswith('$enddefinitions'):
                    started = True
                continue
            if not s or s[0] == '$':
                continue
            if s[0] == '#':
                t = int(s[1:])
            elif s[0] == 'b':
                val, vid = s[1:].split(' ')
                if vid in id2name:
                    changes[id2name[vid]].append((t, int(val, 2)))
            elif s[0] in '01xz':
                vid = s[1:]
                if vid in id2name:
                    changes[id2name[vid]].append((t, 1 if s[0] == '1' else 0))
    return changes


def sample(changes, name, lo, hi):
    seq, cur, ev = [], 0, changes[name]
    j = 0
    for c in range(lo, hi + 1):
        while j < len(ev) and ev[j][0] <= c:
            cur = ev[j][1]
            j += 1
        seq.append(cur)
    return seq


def report(header_ok, widths, changes):
    print('[1] VCD 头解析：命中 %d / %d 个目标信号' % (len(header_ok), len(SIGS)))
    print()
    print('%-13s %-4s %-6s %s' % ('逻辑名', '位宽', '窗口变化', '完整层次路径'))
    for n in SIGS:
        ev = [c for c in changes[n] if LO <= c[0] <= HI]
        print('%-13s %-4d %-8d %s' % (n, widths[n], len(ev), SIGS[n]))
    print()
    print('[2] 关键事件（cycle: 值），窗口 %d–%d' % (LO, HI))
    print()

    def edges(n):
        seq = sample(changes, n, LO, HI)
        return [LO + i for i in range(1, len(seq)) if seq[i] == 1 and seq[i - 1] == 0]

    print('  取指 valid 上升沿 :', edges('fetch_valid'))
    print('  译码 valid 上升沿 :', edges('dec_valid'))
    print('  执行 io_in_valid  :', edges('vialu_in'))
    print('  执行 io_out_valid :', edges('vialu_out'))
    print('  加载写回 Vldu_0/1 :', edges('vldu0_v'), edges('vldu1_v'))
    print('  存储 vecstin      :', edges('st_in_v'))
    print('  存储 dcache_req   :', edges('st_dc_v'))
    print('  存储 s3_valid     :', edges('st_s3_v'))
    print('  存储 vecstout     :', edges('st_out_v'))
    print()
    for n in ('fetch_pc', 'fetch_inst', 'dec_pc', 'dec_inst', 'vialu_op',
              'vialu_vsew', 'st_vaddr'):
        ev = [(t, v) for t, v in changes[n] if LO <= t <= HI]
        txt = ', '.join('%d:0x%x' % (t, v) for t, v in ev[:12])
        print('  %-10s 变化点: %s%s' % (n, txt, ' ...' if len(ev) > 12 else ''))
    print()


def main():
    vcd = sys.argv[1] if len(sys.argv) > 1 else '/tmp/vadd_wave_r2.vcd'
    out = OUT
    if '-o' in sys.argv:
        out = sys.argv[sys.argv.index('-o') + 1]

    path2id, id2width = parse_header(vcd)
    id2name = {}
    for name, path in SIGS.items():
        if path not in path2id:
            raise SystemExit('missing signal in VCD header: ' + path)
        id2name[path2id[path]] = name
    widths = {n: id2width[path2id[SIGS[n]]] for n in SIGS}

    print('VCD      : %s (%d B)' % (vcd, os.path.getsize(vcd)))
    print('窗口     : %d – %d cycle' % (LO, HI))
    changes = parse_changes(vcd, id2name)
    report(list(SIGS), widths, changes)

    plt.rcParams['font.family'] = ['Noto Sans CJK SC', 'DejaVu Sans']
    plt.rcParams['font.monospace'] = ['Noto Sans Mono CJK SC', 'DejaVu Sans Mono']
    plt.rcParams['axes.unicode_minus'] = False
    fig = plt.figure(figsize=(17.5, 13.2), dpi=150)
    gs = fig.add_gridspec(4, 1, height_ratios=[3.0, 3.1, 2.4, 4.2],
                          hspace=0.66, left=0.235, right=0.978, top=0.928, bottom=0.085)
    axes = [fig.add_subplot(gs[i]) for i in range(4)]

    C_SIG, C_HL, C_VEC, C_MEM = '#1f6fb2', '#e8590c', '#6741d9', '#0b7285'

    def bit_row(ax, y, name, lo, hi, label, color=C_SIG, h=0.52):
        seq = sample(changes, name, lo, hi)
        ax.plot([lo, hi], [y, y], color='#ced4da', lw=0.6, zorder=1)
        i, n = 0, len(seq)
        while i < n:
            j = i
            while j + 1 < n and seq[j + 1] == seq[i]:
                j += 1
            if seq[i] == 1:
                ax.add_patch(Rectangle((lo + i, y - h / 2), j - i + 1, h,
                                       facecolor=color, edgecolor='none', alpha=0.80, zorder=2))
            i = j + 1
        ax.text(lo - (hi - lo) * 0.012, y, label, ha='right', va='center', fontsize=7.8,
                family='monospace')

    def bus_row(ax, y, name, lo, hi, label, labels, fs=7.0, yoff=0.34):
        ax.plot([lo, hi], [y, y], color='#dee2e6', lw=0.9, zorder=1)
        ax.text(lo - (hi - lo) * 0.012, y, label, ha='right', va='center', fontsize=7.2,
                family='monospace')
        for c, txt, ha in labels:
            x = c + (0.2 if ha == 'left' else -0.2)
            ax.annotate(txt, xy=(x, y), xytext=(x, y + yoff), fontsize=fs, family='monospace',
                        color='#212529', ha=ha, va='center', zorder=4,
                        bbox=dict(boxstyle='round,pad=0.16', facecolor='#f8f9fa',
                                  edgecolor='#ced4da', lw=0.5, alpha=0.95),
                        arrowprops=dict(arrowstyle='-', lw=0.5, color='#adb5bd'))

    def note(ax, x, y, text, fs=7.2, color='#212529', ha='left'):
        ax.text(x, y, text, ha=ha, va='center', fontsize=fs, color=color, zorder=4,
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='none', alpha=0.85))

    def base(ax, title, ylim, lo, hi):
        ax.set_title(title, loc='left', fontsize=11.5, pad=8)
        ax.set_xlim(lo, hi)
        ax.set_ylim(*ylim)
        ax.grid(axis='x', color='#e9ecef', lw=0.5, zorder=0)
        ax.set_xticks(range(lo, hi + 1, 5 if hi - lo >= 40 else 1))
        ax.tick_params(axis='x', labelsize=7.4, length=2)
        ax.set_yticks([])
        for sp in ('top', 'right', 'left'):
            ax.spines[sp].set_visible(False)

    # A. 取指
    LA, HA = 8240, 8296
    ax = axes[0]
    base(ax, 'A · 取指 Fetch —— frontend.inner_ibuffer.outputEntries_0', (-1.0, 3.25), LA, HA)
    bit_row(ax, 2.62, 'fetch_valid', LA, HA, 'outputEntries_0_valid')
    bus_row(ax, 1.42, 'fetch_pc', LA, HA, 'outputEntries_0_bits_pc',
            [(8246, '0x80000000', 'left'), (8281, '0x80000022', 'left'), (8284, '0x80000036', 'left')])
    bus_row(ax, 0.18, 'fetch_inst', LA, HA, 'outputEntries_0_bits_inst',
            [(8246, '0x000022b7', 'left'), (8281, '0x0c0072d7', 'left'), (8284, '0x00000513', 'left')])
    note(ax, 8242, 3.12, '8246 前端输出首个取指包（pc=0x80000000，即镜像入口 lui t0,0x2）；'
                         '8246–8249 ibuffer 头部 pc 连续跳变（预测/重定向），8280 后按序取指', fs=7.0)
    note(ax, 8279, -0.72, 'vadd 前序取指：vsetvli(0x22) → vle8.v v2(0x2a) → li a0(0x36)', fs=7.0, color=C_HL)

    # B. 译码
    LB, HB = 8278, 8296
    ax = axes[1]
    base(ax, 'B · 译码 Decode —— backend.inner_ctrlBlock.decodePipeRenameModule', (-1.0, 3.25), LB, HB)
    ax.add_patch(Rectangle((8284.5, -0.98), 3.0, 4.1, facecolor='#ffe066', alpha=0.25,
                           edgecolor='none', zorder=0))
    bit_row(ax, 2.62, 'dec_valid', LB, HB, 'io_in_valid')
    bus_row(ax, 1.42, 'dec_pc', LB, HB, 'io_in_bits_pc', [(8285, '0x8000002e', 'left')])
    bus_row(ax, 0.18, 'dec_inst', LB, HB, 'io_in_bits_instr', [(8285, '0x021101d7', 'left')])
    note(ax, 8285.0, 3.10, 'cycle 8285 译码 vadd.vv：pc=0x8000002e，instr=0x021101d7', fs=7.6, color=C_HL)
    note(ax, 8285.8, 2.30, 'vadd.vv  v3, v1, v2', fs=10, color=C_HL)
    note(ax, 8282.4, -0.72,
         '8282 vsetvli(0x22) | 8283 vle8.v v1(0x26) | 8284 vle8.v v2(0x2a) | '
         '8285 vadd.vv(0x2e) | 8286 vse8.v(0x32)', fs=6.8)

    # C. 发射执行
    LC, HC = 8318, 8331
    ax = axes[2]
    base(ax, 'C · 发射执行 Issue/Execute —— backend.inner_vfExuBlock.exus_2.VialuFix', (-1.3, 3.3), LC, HC)
    bit_row(ax, 2.68, 'vialu_in', LC, HC, 'io_in_valid', color='#2f9e44')
    bit_row(ax, 2.02, 'vialu_out', LC, HC, 'io_out_valid', color=C_HL)
    bus_row(ax, 1.22, 'vialu_op', LC, HC, 'io_in_bits_ctrl_fuOpType', [(8323, '0x040', 'left')])
    bus_row(ax, 0.30, 'vialu_vsew', LC, HC, 'io_in_bits_ctrl_vpu_vsew', [(8323, '0b00 = e8', 'left')])
    ax.axvline(8323.5, color=C_HL, ls='--', lw=1.0, alpha=0.75, zorder=0)
    note(ax, 8323.8, 2.58, 'cycle 8323：vadd.vv 进入 VialuFix', fs=7.8, color=C_HL)
    note(ax, 8324.2, 1.93, 'cycle 8324：out_valid，结果写回', fs=7.8, color=C_HL)
    note(ax, 8318, -0.5, 'fuOpType=0x040 → {FMT=00, SINT=1, opcode=000000}=vadd_vv；vsew=0 → e8；vl=16', fs=7.2)
    note(ax, 8318, -1.06, 'src1(v1)=00..0f，src0(v2)=10..1f → res=10 12 14 … 2e（逐字节相加）', fs=7.2, color='#5f3dc4')

    # D. 访存写回
    LD, HD = 8309, 8345
    ax = axes[3]
    base(ax, 'D · 向量访存写回 Vector Memory Writeback —— memBlock（Vldu / StoreUnit_1）', (-2.0, 4.15), LD, HD)
    bit_row(ax, 3.72, 'vldu0_v', LD, HD, 'Vldu_0_valid', color=C_VEC)
    bit_row(ax, 3.08, 'vldu1_v', LD, HD, 'Vldu_1_valid', color=C_VEC)
    bus_row(ax, 2.28, 'vldu0_d', LD, HD, 'Vldu_0_bits_data', [(8317, '00 01 02 … 0f (v1)', 'left')], fs=7.0)
    bus_row(ax, 1.52, 'vldu1_d', LD, HD, 'Vldu_1_bits_data', [(8317, '10 11 12 … 1f (v2)', 'left')], fs=7.0)
    bit_row(ax, 0.84, 'st_in_v', LD, HD, 'StoreUnit_1.io_vecstin_valid', color=C_MEM)
    bit_row(ax, 0.24, 'st_dc_v', LD, HD, 'StoreUnit_1.io_dcache_req_valid', color=C_MEM)
    bit_row(ax, -0.36, 'st_s3_v', LD, HD, 'StoreUnit_1.s3_valid', color=C_MEM)
    bit_row(ax, -0.96, 'st_out_v', LD, HD, 'StoreUnit_1.io_vecstout_valid', color=C_HL)
    bus_row(ax, -1.72, 'st_vaddr', LD, HD, 'io_vecstout_bits_vaddr', [(8336, '0x80000060 (dst)', 'left')], fs=7.0)
    note(ax, 8310, 4.10, 'cycle 8317：vle8.v v1 / v2 同时写回（fuOpType=0x080=VlduType.vle，vl=16，e8）',
         fs=7.4, color=C_VEC)
    note(ax, 8345, 3.34, '8339：vse8.v 写回（fuOpType=0x100=VstuType.vse）', fs=7.0, color=C_HL, ha='right')
    note(ax, 8332.3, 1.06, '8332 向量存储 → StoreUnit_1 → L1 DCache；8335 s3_valid；8336 vecstout',
         fs=7.2, color=C_MEM)
    ax.axvline(8345, color='#2f9e44', ls=':', lw=1.2, zorder=1)
    ax.annotate('8351 GOOD TRAP', xy=(8345, 4.1), fontsize=7.2, color='#2f9e44', ha='right', va='center')

    fig.suptitle('香山昆明湖 V2（XiangShan Kunminghu V2）· vadd.vv (e8, m1) 流水线波形（分阶段局部放大）',
                 fontsize=13.5, y=0.982)
    fig.text(0.235, 0.036,
             'image: tests/phase1/vadd.S -> build/phase1/vadd.bin | cmd: ./build/emu -i vadd.bin '
             '--diff=ready-to-run/riscv64-nemu-interpreter-so --dump-wave -b 8200 -e 8360 '
             '| result: HIT GOOD TRAP at pc=0x80000038, instrCnt=18, cycleCnt=8351, difftest 0 mismatch',
             fontsize=7.6, family='monospace', color='#495057')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, bbox_inches='tight')
    print('[3] 已写出：%s (%d B)' % (out, os.path.getsize(out)))


if __name__ == '__main__':
    main()
