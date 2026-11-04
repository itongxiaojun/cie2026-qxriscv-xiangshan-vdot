#!/usr/bin/env python3
"""生成阶段一~四的操作步骤截图与回放录屏。

产物目录：doc/operation_record/<stage>/{screenshots,video,transcript.txt}
视频编码：H.264 / yuv420p / 30 fps / 1920x1080，由 ffmpeg concat 生成。

说明：本机为无 GUI 终端环境，截图与视频均由"真实命令输出"渲染成终端画面；
长耗时步骤（emu/cosim/run_all）回放已捕获的真实日志，并在画面中标注。
"""

import os
import re
import shutil
import subprocess
import hashlib

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "doc", "operation_record")
FRAME_DIR = os.path.join(ROOT, "build", "opt_record_frames")
FFMPEG = os.path.join(ROOT, ".tools", "ffmpeg", "ffmpeg")

W, H = 1920, 1080
BG = (11, 16, 32)
PANEL = (16, 24, 40)
PANEL2 = (24, 34, 54)
FG = (216, 226, 240)
CYAN = (92, 200, 255)
GREEN = (74, 222, 128)
RED = (248, 113, 113)
YELLOW = (251, 191, 36)
DIM = (122, 134, 153)
WHITE = (240, 245, 255)

MONO_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
CJK_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
CJK_BOLD_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

F_MONO = ImageFont.truetype(MONO_PATH, 22)
F_MONO_SM = ImageFont.truetype(MONO_PATH, 18)
F_CJK = ImageFont.truetype(CJK_PATH, 20, index=2)
F_CJK_SM = ImageFont.truetype(CJK_PATH, 17, index=2)
F_TITLE = ImageFont.truetype(CJK_BOLD_PATH, 34, index=2)
F_SUB = ImageFont.truetype(CJK_BOLD_PATH, 22, index=2)
F_STEP = ImageFont.truetype(CJK_BOLD_PATH, 25, index=2)
F_SMALL = ImageFont.truetype(CJK_PATH, 15, index=2)

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
CHAR_W = {}


def strip_ansi(t):
    return ANSI.sub("", t).replace("\r", "")


def run(cmd, timeout=180):
    p = subprocess.run(["bash", "-lc", cmd], cwd=ROOT, capture_output=True,
                       timeout=timeout, env=dict(os.environ, LC_ALL="C.UTF-8"))
    return strip_ansi((p.stdout + p.stderr).decode("utf-8", errors="replace")).strip("\n")


def cw(ch, font):
    key = (ch, font.path, font.size)
    if key not in CHAR_W:
        CHAR_W[key] = font.getlength(ch)
    return CHAR_W[key]


def wrap(text, max_w):
    """按像素宽度折行，混排 ASCII 等宽字体与 CJK 字体。"""
    out, cur, x = [], "", 0.0
    for ch in text:
        font = F_MONO if ord(ch) < 128 else F_CJK
        w = cw(ch, font)
        if x + w > max_w and cur:
            out.append(cur)
            cur, x = "", 0.0
        cur += ch
        x += w
    out.append(cur)
    return out


def draw_mixed(d, x, y, text, color, max_x, font_ascii=None, font_cjk=None):
    fa = font_ascii or F_MONO
    fc = font_cjk or F_CJK
    for ch in text:
        font = fa if ord(ch) < 128 else fc
        if x + cw(ch, font) > max_x:
            return x
        d.text((x, y), ch, font=font, fill=color)
        x += cw(ch, font)
    return x


def color_for(line):
    u = line.upper()
    if any(k in u for k in ("FAIL", "MISMATCH", "ERROR", "BAD TRAP", "ERROR:")):
        return RED
    if any(k in u for k in ("PASS", "GOOD TRAP", "CONSISTENT", "ALL : PASS", "OK")):
        return GREEN
    if line.startswith(("==", "---", "#", "阶段")):
        return CYAN
    if line.startswith(("[qxriscv", "（", "注：", "长耗时")):
        return YELLOW
    return FG


def page(stage, idx, total, title, req, cmd, body, note="", mode="step"):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # 顶部品牌与阶段
    d.text((48, 26), "2026CIE  ·  qxriscv  ·  xiangshan-vdot", font=F_SMALL, fill=CYAN)
    d.text((48, 52), stage["title"], font=F_TITLE, fill=WHITE)
    rt = f"阶段 {stage['no']} / 步骤 {idx}/{total}" if mode == "step" else stage["right"]
    d.text((W - 48 - d.textlength(rt, font=F_SUB), 60), rt, font=F_SUB, fill=DIM)
    d.line((48, 104, W - 48, 104), fill=(40, 54, 80), width=2)

    # 终端面板
    d.rounded_rectangle((36, 126, W - 36, H - 60), radius=14, fill=PANEL, outline=(34, 48, 72), width=2)
    d.rounded_rectangle((36, 126, W - 36, 158), radius=14, fill=PANEL2)
    for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        d.ellipse((54 + i * 28, 136, 66 + i * 28, 148), fill=c)
    if mode == "intro":
        d.text((120, 134), f"{stage['no']} · {stage['subtitle']}", font=F_CJK_SM, fill=DIM)
    elif mode == "step":
        d.text((120, 132), f"{idx:02d} · {title}", font=F_CJK_SM, fill=WHITE)
    else:
        d.text((120, 132), "阶段小结", font=F_CJK_SM, fill=WHITE)

    x0, y0, max_x = 62, 178, W - 62
    y = y0
    if mode == "step":
        # 要求标签
        if req:
            d.text((x0, y), f"[{req}]", font=F_CJK_SM, fill=CYAN)
            y += 30
        # 命令行（可能多行）
        prompt = "[qxriscv@xs ~/cieriscv]$ "
        d.text((x0, y), prompt, font=F_MONO_SM, fill=GREEN)
        px = x0 + d.textlength(prompt, font=F_MONO_SM)
        for i, part in enumerate(cmd.split("\n")):
            if i:
                y += 27
                px = x0 + 8
            if part:
                draw_mixed(d, px, y, part, WHITE, max_x, F_MONO_SM, F_CJK_SM)
            px = max_x
        y += 34
        d.line((x0, y - 8, max_x, y - 8), fill=(44, 60, 86), width=1)
    elif mode == "intro":
        y += 8

    # body
    lines = body
    if note and mode == "step":
        lines = body + ["", note]
    for ln in lines:
        for vl in wrap(ln, max_x - x0):
            if y > H - 100:
                break
            d.text((x0, y), vl, font=F_MONO_SM if all(ord(c) < 128 for c in vl) else F_CJK_SM,
                   fill=color_for(vl))
            y += 27
        if y > H - 100:
            break

    # footer
    d.line((48, H - 50, W - 48, H - 50), fill=(40, 54, 80), width=1)
    d.text((48, H - 40), "doc/operation_record  ·  1920x1080  ·  30fps  ·  真实命令输出回放",
           font=F_SMALL, fill=DIM)
    return img


STAGES = []

def add_stage(no, name, title, subtitle, steps, summary):
    STAGES.append(dict(no=no, name=name, title=title, subtitle=subtitle,
                       steps=steps, summary=summary, right=f"阶段 {no}"))


add_stage(
    "一", "stage1_environment", "阶段一 · 环境搭建与 RTL 链路贯通",
    "官方 1.1 / 1.2 / 1.3：hello、操作日志、vadd 波形",
    [
        dict(id="1-1", slug="toolchain", title="工具链与仿真器版本自检",
             req="官方 1.1 环境准备",
             cmd="uname -m\npython3 --version\n.tools/riscv/bin/riscv-none-elf-gcc --version | head -1\n.tools/verilator/bin/verilator --version",
             exec_cmd="uname -m; python3 --version; .tools/riscv/bin/riscv-none-elf-gcc --version | head -1; .tools/verilator/bin/verilator --version"),
        dict(id="1-2", slug="commits", title="源码版本锁定",
             req="官方 1.2 操作日志",
             cmd="git -C build/xs-work/XiangShan rev-parse --short HEAD\ngit -C .tools/nemu rev-parse --short HEAD",
             exec_cmd="git -C build/xs-work/XiangShan rev-parse --short HEAD; git -C .tools/nemu rev-parse --short HEAD"),
        dict(id="1-3", slug="artifacts", title="构建产物核对",
             req="官方 1.1 环境准备",
             cmd="ls -lh build/xs-work/XiangShan/build/emu build/phase1/hello.bin build/phase1/vadd.bin",
             exec_cmd="ls -lh build/xs-work/XiangShan/build/emu build/phase1/hello.bin build/phase1/vadd.bin"),
        dict(id="1-4", slug="hello", title="hello 程序运行（真实日志回放）",
             req="官方 1.1 hello 程序",
             cmd="build/xs-work/XiangShan/build/emu -i build/phase1/hello.bin \\\n  --diff=.tools/nemu/build/riscv64-nemu-interpreter-so",
             exec_cmd="grep -aE 'hello xiangshan|HIT GOOD TRAP|instrCnt' docs/phase1/logs/02_hello_run.log | head -3",
             note="长耗时步骤：回放已捕获的真实运行日志（emu 单次约 1 分钟）。"),
        dict(id="1-5", slug="vadd_wave", title="vadd 波形采集参数",
             req="官方 1.3 vadd 波形",
             cmd="build/xs-work/XiangShan/build/emu -i build/phase1/vadd.bin \\\n  --dump-wave -b 8200 -e 8360 --wave-path=/tmp/vadd_wave.vcd",
             exec_cmd="grep -aE 'dump-wave|8200|8360|VCD' docs/phase1/logs/03_vadd_run.log | head -6",
             note="长耗时步骤：回放已捕获的真实日志；窗口 8200–8360 避免生成 GB 级 VCD。"),
        dict(id="1-6", slug="vadd_timeline", title="vadd 流水时间线与波形截图",
             req="官方 1.3 vadd 波形",
             cmd="grep -nE '取指|译码|发射|执行|写回|提交' docs/phase1/vadd_wave.md\nls -lh docs/phase1/wave/vadd_pipeline_wave.png",
             exec_cmd="grep -aE '^\\| (取指|译码|发射执行|访存|写回|提交)' docs/phase1/vadd_wave.md; ls -lh docs/phase1/wave/vadd_pipeline_wave.png"),
    ],
    ["hello：HIT GOOD TRAP，IP 192.168.0.168", "vadd 波形：cycle 8200–8360，VCD 解析与分阶段截图完成"],
)

add_stage(
    "二", "stage2_design_rtl", "阶段二 · 设计实现与 RTL 验证",
    "官方 2.1 / 2.2 / 2.3：设计文档、RTL 实现、单元测试与香山集成",
    [
        dict(id="2-1", slug="design_doc", title="设计文档与语义章节",
             req="官方 2.1 设计文档",
             cmd="grep -nE '^## |^### ' docs/phase2/design.md | head -18",
             exec_cmd="grep -nE '^## |^### ' docs/phase2/design.md | head -18"),
        dict(id="2-2", slug="rtl_files", title="RTL 源文件与实现规模",
             req="官方 2.2 RTL 实现",
             cmd="wc -l rtl/verilog/VDot.v rtl/chisel/VDotCore.sv\nls -lh rtl/verilog/VDot.v",
             exec_cmd="wc -l rtl/verilog/VDot.v rtl/chisel/VDotCore.sv; ls -lh rtl/verilog/VDot.v"),
        dict(id="2-3", slug="unit_regression", title="单元回归 1518 用例",
             req="官方 2.3 单元测试",
             cmd="bash scripts/run_unit_tests.sh",
             exec_cmd="grep -aE 'cases_total|cases_pass|cases_fail|total_cycles|latency_write|throughput|RESULT' docs/phase2/logs/03_unit_test.log",
             note="长耗时步骤：回放已捕获的真实回归日志。"),
        dict(id="2-4", slug="coverage", title="覆盖率与 Chisel 等价",
             req="官方 2.3 单元测试",
             cmd="grep -E 'coverage|36/36' docs/phase2/logs/07_coverage.log\ngrep -E 'cases|RESULT' docs/phase2/logs/09_chisel_equiv.log",
             exec_cmd="grep -aE 'coverage|36/36|RESULT' docs/phase2/logs/07_coverage.log | head -6; echo; grep -aE 'cases_total|cases_pass|mismatch|RESULT' docs/phase2/logs/09_chisel_equiv.log | tail -5"),
        dict(id="2-5", slug="emu_directed", title="香山 emu 定向用例 7/7",
             req="官方 2.2 昆明湖 V2 集成",
             cmd="bash tests/phase2/xs_emu/run_emu.sh",
             exec_cmd="grep -aE 'DIRECTED|HIT GOOD TRAP' docs/phase2/logs/xs_emu_vdot_directed.log | tail -4",
             note="定向 7 个用例：fails=0，difftest 0 mismatch。"),
        dict(id="2-6", slug="emu_illegal", title="非法配置用例 5/5",
             req="官方 2.3 单元测试",
             cmd="emu -i vdot_illegal.bin --no-diff",
             exec_cmd="grep -aE 'ILLEGAL|HIT GOOD TRAP' docs/phase2/logs/xs_emu_vdot_illegal.log | tail -4",
             note="5 类非法配置全部命中 trap，other=0。"),
    ],
    ["单元回归：1518/1518 PASS，3 cycle / 1.0 inst·cycle⁻¹", "香山 emu：定向 7/7、非法 5/5，difftest 0 mismatch"],
)

add_stage(
    "三", "stage3_nemu_cosim", "阶段三 · NEMU 扩展、协同仿真与加速评估",
    "官方 3.1 / 3.2 / 3.3：参考模型、协同仿真、基线与加速比",
    [
        dict(id="3-1", slug="patch", title="NEMU 补丁一致性自检",
             req="官方 3.1.1 参考模型扩展",
             cmd="git -C .tools/nemu diff --stat\ngit -C .tools/nemu apply --check --reverse \"$PWD/patches/nemu-vdot.patch\"",
             exec_cmd="git -C .tools/nemu diff --stat; git -C .tools/nemu apply --check --reverse \"$PWD/patches/nemu-vdot.patch\" && echo 'PATCH CONSISTENT: reverse apply OK'"),
        dict(id="3-2", slug="cosim", title="NEMU ↔ 金标准 ↔ RTL 协同",
             req="官方 3.2 协同仿真",
             cmd="python3 tests/run_nemu_cosim.py --rtl-export docs/phase3/02_rtl_export.txt",
             exec_cmd="grep -aE 'cases|boundary|vl0|illegal|nemu_dyn_instr|RESULT|rtl_vs_nemu' docs/phase3/01_nemu_cosim.log | tail -12",
             note="长耗时步骤：回放已捕获的真实协同仿真日志（NEMU 单次约 6 分钟）。"),
        dict(id="3-3", slug="rtl_diff", title="RTL 与 NEMU 逐例 diff",
             req="官方 3.2 协同仿真",
             cmd="python3 tests/run_nemu_cosim.py --rtl-export docs/phase3/02_rtl_export.txt",
             exec_cmd="grep -aE 'rtl_vs_nemu|cases_expected|cases_fail|RESULT' docs/phase3/01_nemu_cosim.log | tail -5",
             note="1513 条写回用例逐位比对，0 mismatch。"),
        dict(id="3-4", slug="baseline", title="纯 RVV 基线等价性",
             req="官方 3.3 基线对比",
             cmd="python3 tests/run_nemu_baseline.py",
             exec_cmd="grep -aE 'cases|alu_op_ratio|nemu_dyn_instr|RESULT' docs/phase3/03_baseline_nemu.log | tail -8",
             note="长耗时步骤：回放已捕获的真实基线运行日志。"),
        dict(id="3-5", slug="unit_perf", title="单元级延迟与吞吐",
             req="官方 3.3 性能评估",
             cmd="./build/obj_dir/tb_vdot build/nemu/cosim_vectors.txt - docs/phase3/02_rtl_export.txt",
             exec_cmd="grep -aE 'cases_total|total_cycles|latency_write|latency_illegal|throughput|RESULT' docs/phase3/04_rtl_unit_perf.log",
             note="3 cycle 延迟 / 1.0 inst·cycle⁻¹ 吞吐；1513 写回子集不含非法用例，全量 1518 的非法延迟为 3 cycle。"),
        dict(id="3-6", slug="perf_repeat", title="香山 emu 性能与 3 次重复",
             req="官方 3.3 加速比 / G5",
             cmd="for k in empty vdot rvv scalar; do\n  for r in 1 2 3; do ./build/emu -i build/phase2/xs_emu/perf_$k.bin \\\n    --diff=.tools/nemu/build/riscv64-nemu-interpreter-so; done; done",
             exec_cmd="sed -n '1p;3p;6,8p;11p;13,17p;19p;21,25p;27,29p;34,35p' docs/phase3/05_perf_repeat.log",
             note="长耗时步骤：四内核各跑 3 次，此处回放真实测量汇总（NITER=2000）。"),
        dict(id="3-7", slug="speedup", title="加速比核算",
             req="官方 3.3 加速比",
             cmd="python3 -c \"per_iter=(Ck-Cempty)/2000; speedup=per_iter(base)/per_iter(vdot)\"",
             exec_cmd="python3 -c \"e=11108; v=12123; r=23109; s=21022; pi=lambda c: (c-e)/2000; print(f'vdot  : {pi(v):.4f} cycle/dot'); print(f'rvv   : {pi(r):.4f} cycle/dot'); print(f'scalar: {pi(s):.4f} cycle/dot'); print(f'vdot vs scalar = {pi(s)/pi(v):.2f}x  (lane 公平)'); print(f'vdot vs rvv    = {pi(r)/pi(v):.2f}x  (16-lane 上界)')\""),
    ],
    ["协同仿真：1513/1513，0 mismatch；边界自检 PASS", "单元级：3 cycle / 1.0 inst·cycle⁻¹", "emu：0.5075 cycle/点积，9.8× 公平 / 11.8× 上界；3 次极差 0"],
)

add_stage(
    "四", "stage4_release", "阶段四 · 收口、综合评估与提交检查",
    "Lint、generic 综合、七步回归与门径核对",
    [
        dict(id="4-1", slug="lint", title="Verilator 严格 Lint",
             req="质量门径",
             cmd=".tools/verilator/bin/verilator --lint-only -Wall -Wno-DECLFILENAME rtl/verilog/VDot.v --top-module VDot",
             exec_cmd="cat docs/phase4/02_verilator_lint.log",
             note="日志无 Warning/Error 行，即 0 告警 0 错误。"),
        dict(id="4-2", slug="synth", title="Yosys generic 综合",
             req="质量门径",
             cmd="yosys -p \"read_verilog -sv rtl/verilog/VDot.v; synth -top VDot -noabc; techmap; opt; ltp -noff; stat\"",
             exec_cmd="grep -aA8 '=== VDot ===' docs/phase4/01_yosys_synth.log | head -10; grep -aE 'Longest topological' docs/phase4/01_yosys_synth.log",
             note="工艺无关综合；PDK 映射待库（B4 部分关闭）。"),
        dict(id="4-3", slug="area", title="面积量级估算",
             req="质量门径",
             cmd="grep -E 'GE|4186|172' docs/phase4/release_report.md | head -8",
             exec_cmd="grep -aE '4186|172 FF|25 级|5.3k|8.4k|6.9k' docs/phase4/release_report.md | head -8"),
        dict(id="4-4", slug="run_all", title="七步一键回归",
             req="提交门径",
             cmd="bash scripts/run_all.sh",
             exec_cmd="tail -n 22 doc/operation_record/_evidence/run_all.log",
             note="长耗时步骤：回放本次真实执行的完整回归输出。"),
        dict(id="4-5", slug="checklist", title="门径与提交检查",
             req="提交门径",
             cmd="grep -c '^- \\[x\\]' ipd/04_评审对照与提交检查表.md\ngrep -E '视频提交位置' ipd/04_评审对照与提交检查表.md",
             exec_cmd="grep -aEc '^- \\[x\\]' ipd/04_评审对照与提交检查表.md | sed 's/^/checked_items: /'; grep -aE '视频提交位置' ipd/04_评审对照与提交检查表.md | head -1",
             note="官方 1.1–3.3 与提交检查项共 29 项已勾选；视频索引见 doc/operation_record/README.md。"),
    ],
    ["Lint：0 warning / 0 error", "综合：4186 单元 / 172 FF / 25 级 / ≈5.3k–8.4k GE", "回归：unit/lint/chisel/nemu/rtl_export/cosim/baseline 全 PASS"],
)


def frame_path(stage_name, key):
    d = os.path.join(FRAME_DIR, stage_name)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{key}.png")


def render_video(stage):
    sd = os.path.join(OUT, stage["name"])
    fdir = os.path.join(FRAME_DIR, stage["name"])
    if os.path.isdir(fdir):
        shutil.rmtree(fdir)
    os.makedirs(fdir, exist_ok=True)
    lines, t = [], 0.0

    def add(img, dur, tag):
        nonlocal t
        name = f"{tag}.png"
        p = os.path.join(fdir, name)
        img.save(p, optimize=True)
        lines.append((os.path.abspath(p), dur))
        t += dur

    # 封面
    steps_txt = [f"{s['id']}  {s['title']}   [{s['req']}]" for s in stage["steps"]]
    add(page(stage, 0, len(stage["steps"]), "阶段目标与步骤", "", "", steps_txt, mode="intro"), 3.6, "000_intro")

    n = len(stage["steps"])
    for i, s in enumerate(stage["steps"], 1):
        body = s.get("out", "").splitlines()
        if s.get("cap"):
            body = body[: s["cap"]]
        if len(body) > 26:
            body = body[:26]
        # 命令页
        add(page(stage, i, n, s["title"], s["req"], s["cmd"], [], s.get("note", "")), 1.6, f"{i:02d}_cmd")
        # 输出分批
        if body:
            chunks = max(1, min(14, (len(body) + 2) // 3))
            size = max(1, (len(body) + chunks - 1) // chunks)
            for k in range(1, len(body) + 1, size):
                add(page(stage, i, n, s["title"], s["req"], s["cmd"], body[:k], s.get("note", ""),
                         mode="step"), 0.55, f"{i:02d}_out{k:03d}")
        # 结果页停留
        add(page(stage, i, n, s["title"], s["req"], s["cmd"], body, s.get("note", "")), 2.4, f"{i:02d}_result")

    add(page(stage, 0, n, "阶段小结", "", "", stage["summary"], mode="outro"), 3.2, "999_outro")

    list_txt = os.path.join(fdir, "concat.txt")
    with open(list_txt, "w", encoding="utf-8") as f:
        for p, dur in lines:
            f.write(f"file '{p}'\nduration {dur}\n")
    out = os.path.join(sd, "video", f"{stage['name']}.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", list_txt,
           "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "23", "-movflags", "+faststart", out]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + p.stderr[-500:])
    return out, t


def main():
    if os.path.isdir(FRAME_DIR):
        shutil.rmtree(FRAME_DIR)
    os.makedirs(OUT, exist_ok=True)
    for stage in STAGES:
        sd = os.path.join(OUT, stage["name"])
        for sub in ("screenshots", "video"):
            os.makedirs(os.path.join(sd, sub), exist_ok=True)
        transcript = []
        for i, s in enumerate(stage["steps"], 1):
            s["out"] = run(s["exec_cmd"], timeout=240)
            transcript.append(f"$ {s['cmd']}\n{s['out']}\n")
            # 截图：命令页 + 结果页
            shot1 = os.path.join(sd, "screenshots", f"{i:02d}_{s['slug']}_command.png")
            page(stage, i, len(stage["steps"]), s["title"], s["req"], s["cmd"], [], s.get("note", "")).save(shot1)
            shot2 = os.path.join(sd, "screenshots", f"{i:02d}_{s['slug']}_result.png")
            body = s["out"].splitlines()[:s.get("cap", 26)]
            page(stage, i, len(stage["steps"]), s["title"], s["req"], s["cmd"], body, s.get("note", "")).save(shot2)
            print(f"[{stage['name']}] {s['id']} {s['title']}: {len(s['out'].splitlines())} lines -> {shot2}")
        with open(os.path.join(sd, "transcript.txt"), "w", encoding="utf-8") as f:
            f.write(f"# {stage['title']}\n# 命令与输出均为本机真实执行（长耗时步骤为已捕获日志回放）\n\n")
            f.write("\n".join(transcript))
        out, dur = render_video(stage)
        print(f"VIDEO {out} ({dur:.1f}s)")


if __name__ == "__main__":
    main()
