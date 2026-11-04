// 2026CIE · qxriscv · vdot.vv 答辩 PPT（12 页）
// 运行：node deck.js
"use strict";

const pptxgen = require("pptxgenjs");
const {
  warnIfSlideHasOverlaps,
  warnIfSlideElementsOutOfBounds,
  calcTextBoxHeightSimple,
} = require("./pptxgenjs_helpers");

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pptx.author = "qxriscv";
pptx.company = "qxriscv";
pptx.subject = "2026CIE 自定义 vdot.vv 指令设计与验证";
pptx.title = "vdot.vv：边缘 AI 推理的 RISC-V 自定义向量点积指令";
pptx.lang = "zh-CN";
pptx.theme = {
  headFontFace: "Microsoft YaHei",
  bodyFontFace: "Microsoft YaHei",
  lang: "zh-CN",
};

const C = {
  navy: "0B2545",
  ink: "16283D",
  gray: "5B6B7C",
  faint: "8A99A8",
  line: "DCE3EA",
  bg: "FFFFFF",
  soft: "F5F8FB",
  teal: "0E7C86",
  tealSoft: "E6F2F3",
  orange: "B45309",
  orangeSoft: "FDF3E7",
  green: "15803D",
  greenSoft: "EAF5EE",
  red: "B42318",
  redSoft: "FDEDEC",
};

const F = "Microsoft YaHei";
const MONO = "Consolas";
const W = 13.333;
const H = 7.5;
const M = 0.62;
const CW = W - 2 * M;

pptx.defineSlideMaster({
  title: "BASE",
  background: { color: C.bg },
  objects: [
    { rect: { x: 0, y: 0, w: W, h: 0.09, fill: { color: C.navy } } },
    {
      rect: { x: 0, y: H - 0.34, w: W, h: 0.012, fill: { color: C.line } },
    },
    {
      text: {
        text: "qxriscv  ·  2026 CIE RISC-V 自定义指令赛  ·  vdot.vv",
        options: {
          x: M,
          y: H - 0.3,
          w: 8.6,
          h: 0.22,
          fontSize: 8.5,
          color: C.faint,
          fontFace: F,
          align: "left",
          valign: "middle",
        },
      },
    },
  ],
});

const addPageNo = (slide, n) => {
  slide.addText(String(n).padStart(2, "0"), {
    x: W - M - 1.2,
    y: H - 0.3,
    w: 1.2,
    h: 0.22,
    fontSize: 8.5,
    color: C.faint,
    fontFace: MONO,
    align: "right",
    valign: "middle",
  });
};

const addHeader = (slide, kicker, title, n) => {
  slide.addText(kicker, {
    x: M,
    y: 0.42,
    w: CW,
    h: 0.24,
    fontSize: 10,
    color: C.teal,
    fontFace: MONO,
    charSpacing: 2,
    bold: true,
    valign: "middle",
  });
  slide.addText(title, {
    x: M,
    y: 0.68,
    w: CW,
    h: 0.62,
    fontSize: 27,
    color: C.navy,
    fontFace: F,
    bold: true,
    valign: "middle",
  });
  slide.addShape(pptx.ShapeType.line, {
    x: M,
    y: 1.42,
    w: CW,
    h: 0,
    line: { color: C.line, width: 1 },
  });
  addPageNo(slide, n);
};

const card = (slide, o) => {
  slide.addShape(pptx.ShapeType.roundRect, {
    x: o.x,
    y: o.y,
    w: o.w,
    h: o.h,
    rectRadius: 0.04,
    fill: { color: o.fill || C.soft },
    line: { color: o.border || C.line, width: o.borderWidth || 1 },
  });
};

const kpi = (slide, x, y, w, value, unit, label, color) => {
  card(slide, { x, y, w, h: 1.38, fill: "FFFFFF", border: C.line });
  slide.addText(
    [
      { text: value, options: { fontSize: 34, bold: true, color: color || C.navy } },
      { text: unit ? " " + unit : "", options: { fontSize: 15, color: C.gray } },
    ],
    {
      x: x + 0.18,
      y: y + 0.12,
      w: w - 0.36,
      h: 0.72,
      fontFace: F,
      valign: "middle",
      align: "left",
    }
  );
  slide.addText(label, {
    x: x + 0.18,
    y: y + 0.86,
    w: w - 0.36,
    h: 0.36,
    fontSize: 10.5,
    color: C.gray,
    fontFace: F,
    valign: "middle",
  });
};

const bullet = (slide, x, y, w, items, opts = {}) => {
  const fontSize = opts.fontSize || 12;
  const para = items.map((t, i) => ({
    text: typeof t === "string" ? t : t.text,
    options: {
      bullet: { characterCode: "25AA" },
      fontSize: typeof t === "object" && t.size ? t.size : fontSize,
      color: typeof t === "object" && t.color ? t.color : C.ink,
      breakLine: true,
      paraSpaceAfter: 6,
      bold: typeof t === "object" && t.bold ? true : false,
    },
  }));
  const h = calcTextBoxHeightSimple(para, fontSize, w - 0.1, { fontFace: F });
  slide.addText(para, {
    x,
    y,
    w,
    h: Math.min(h + 0.1, opts.maxH || 3.2),
    fontFace: F,
    valign: "top",
    lineSpacingMultiple: 1.12,
  });
};

const table = (slide, o) => {
  const rows = o.rows.map((r, ri) =>
    r.map((cell) => ({
      text: String(cell),
      options: {
        fontSize: o.fontSize || 10.5,
        bold: ri === 0 || (o.boldCol0 && String(r[0]).length > 0 && o.boldCol0),
        color: ri === 0 ? "FFFFFF" : o.colors && o.colors[ri] ? o.colors[ri] : C.ink,
        fill: { color: ri === 0 ? C.navy : ri % 2 === 0 ? C.soft : "FFFFFF" },
        align: ri === 0 ? "center" : o.align || "left",
        valign: "middle",
        fontFace: o.mono && ri > 0 ? MONO : F,
        margin: 0.06,
      },
    }))
  );
  slide.addTable(rows, {
    x: o.x,
    y: o.y,
    w: o.w,
    colW: o.colW,
    rowH: o.rowH || 0.34,
    border: { type: "solid", color: C.line, pt: 0.75 },
    autoPage: false,
  });
};

const note = (slide, text) => slide.addNotes(text);

/* ------------------------------------------------------------------ */
/* 01 封面                                                             */
/* ------------------------------------------------------------------ */
const s1 = pptx.addSlide();
s1.background = { color: C.navy };
s1.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.18, h: H, fill: { color: C.teal } });
s1.addText("2026 CIE  ·  RISC-V 自定义指令赛  ·  香山昆明湖 V2", {
  x: 1.0,
  y: 1.05,
  w: 11,
  h: 0.3,
  fontSize: 12,
  color: "9FC3CB",
  fontFace: MONO,
  charSpacing: 1.5,
  bold: true,
});
s1.addText("vdot.vv：面向边缘 AI 推理的\nRISC-V 自定义向量点积指令", {
  x: 1.0,
  y: 1.55,
  w: 11.2,
  h: 1.85,
  fontSize: 38,
  color: "FFFFFF",
  fontFace: F,
  bold: true,
  lineSpacingMultiple: 1.12,
  valign: "top",
});
s1.addShape(pptx.ShapeType.line, {
  x: 1.0,
  y: 3.62,
  w: 3.4,
  h: 0,
  line: { color: C.teal, width: 3 },
});
s1.addText("单 uop 完成 8 个 int8 乘累加  ·  数据通路指令数 6→1  ·  香山 emu 实测加速比 9.8×", {
  x: 1.0,
  y: 3.82,
  w: 11.4,
  h: 0.4,
  fontSize: 15,
  color: "D6E4E8",
  fontFace: F,
});
const coverMeta = [
  ["团队", "qxriscv"],
  ["目标平台", "香山 昆明湖 V2（VLEN=128）"],
  ["交付", "RTL · 验证 · 协同仿真 · 综合评估"],
];
coverMeta.forEach((m, i) => {
  const x = 1.0 + i * 3.7;
  s1.addText(m[0], {
    x,
    y: 5.35,
    w: 3.3,
    h: 0.24,
    fontSize: 9.5,
    color: "7FA3AD",
    fontFace: MONO,
    charSpacing: 1.2,
    bold: true,
  });
  s1.addText(m[1], {
    x,
    y: 5.62,
    w: 3.3,
    h: 0.32,
    fontSize: 12.5,
    color: "FFFFFF",
    fontFace: F,
    bold: true,
  });
});
note(
  s1,
  "开场 20 秒：我们做的是香山昆明湖 V2 上的一条自定义向量点积指令 vdot.vv，目标是把 8 个 int8 的乘累加压缩成单 uop。首页数字均为已验证结果或明确标注的模型口径。"
);

/* ------------------------------------------------------------------ */
/* 02 问题                                                             */
/* ------------------------------------------------------------------ */
const s2 = pptx.addSlide({ masterName: "BASE" });
addHeader(s2, "01 / 问题", "为什么需要一条专用的点积指令", 2);

kpi(s2, M, 1.72, 3.9, "6 → 1", "uop", "每 8 元素点积的数据通路指令数", C.navy);
kpi(s2, M + 4.1, 1.72, 3.9, "12 → 3", "cycle", "同一操作的结构模型延迟", C.teal);
kpi(s2, M + 8.2, 1.72, 3.9, "−11.9", "%", "同一负载的动态指令数（89,294→78,701）", C.orange);

card(s2, { x: M, y: 3.3, w: 5.9, h: 3.05, fill: "FFFFFF" });
s2.addText("通用 RVV 序列要做什么", {
  x: M + 0.25,
  y: 3.42,
  w: 5.4,
  h: 0.32,
  fontSize: 13,
  bold: true,
  color: C.navy,
  fontFace: F,
});
bullet(
  s2,
  M + 0.25,
  3.78,
  5.45,
  [
    "vsext 两次：把 int8 扩到 int16",
    "vmul：逐元素 16 bit 乘",
    "vredsum：跨 lane 归约求和",
    "共 6 条 uop（含两条符号扩展），依赖链贯穿 4 个向量操作",
  ],
  { fontSize: 11.5, maxH: 2.3 }
);

card(s2, { x: M + 6.15, y: 3.3, w: 5.94, h: 3.05, fill: C.tealSoft, border: "BFDDE0" });
s2.addText("代价落在哪里", {
  x: M + 6.4,
  y: 3.42,
  w: 5.4,
  h: 0.32,
  fontSize: 13,
  bold: true,
  color: C.navy,
  fontFace: F,
});
bullet(
  s2,
  M + 6.4,
  3.78,
  5.5,
  [
    "更多译码/发射/写回端口占用，且每一步都要读写向量寄存器堆",
    "归约命令引出额外的跨 lane 网络，难以与后续像素级算子流水",
    "点积是 int8 量化推理（注意力打分、卷积）的主算子，值得单指令化",
    "目标：一条指令内部完成乘 + 归约 + 写回，且保持全流水",
  ],
  { fontSize: 11.5, maxH: 2.3 }
);
note(
  s2,
  "问题页：先用三个数字建立冲击力，再解释通用的 RVV 组合序列为什么贵。强调 6→1 是数据通路指令数、12→3 是结构模型延迟，二者口径不同，后面第 10 页会再次声明。"
);

/* ------------------------------------------------------------------ */
/* 03 赛题理解                                                         */
/* ------------------------------------------------------------------ */
const s3 = pptx.addSlide({ masterName: "BASE" });
addHeader(s3, "02 / 赛题理解", "约束先行：能改的与不能改的", 3);

const q = [
  ["平台", "香山 昆明湖 V2", "VLEN=128，复用既有向量发射/写回框架"],
  ["实现方式", "新增 1 个 VFu", "不新建流水段，零改动既有 VFu 逻辑"],
  ["指令语义", "SEW=8 · K=8", "一次 8 个 int8 有符号乘累加，单 uop"],
  ["输出格式", "vd[31:0] + 高 96 位清零", "32 bit 二补码，不做饱和"],
];
q.forEach((it, i) => {
  const x = M + (i % 2) * 6.15;
  const y = 1.75 + Math.floor(i / 2) * 1.55;
  card(s3, { x, y, w: 5.94, h: 1.36, fill: "FFFFFF" });
  s3.addShape(pptx.ShapeType.rect, { x, y: y + 0.16, w: 0.05, h: 1.04, fill: { color: C.teal } });
  s3.addText(it[0], {
    x: x + 0.22,
    y: y + 0.14,
    w: 1.5,
    h: 0.3,
    fontSize: 10.5,
    color: C.teal,
    fontFace: MONO,
    bold: true,
  });
  s3.addText(it[1], {
    x: x + 0.22,
    y: y + 0.44,
    w: 5.4,
    h: 0.4,
    fontSize: 16,
    color: C.navy,
    fontFace: F,
    bold: true,
  });
  s3.addText(it[2], {
    x: x + 0.22,
    y: y + 0.84,
    w: 5.5,
    h: 0.42,
    fontSize: 10.5,
    color: C.gray,
    fontFace: F,
  });
});

card(s3, { x: M, y: 4.95, w: CW, h: 1.55, fill: C.soft });
s3.addText("由此得到的设计边界", {
  x: M + 0.25,
  y: 5.05,
  w: 3,
  h: 0.3,
  fontSize: 11,
  bold: true,
  color: C.navy,
  fontFace: F,
});
bullet(
  s3,
  M + 0.25,
  5.38,
  CW - 0.5,
  [
    "数据通路只能取两个源寄存器低 64 bit；高 64 bit 保留但本单元不解引用（属预期语义）",
    "合法性只在 vm=1 / e8 / m1 时成立；其余组合在单元内显式报 illegal，不静默执行",
  ],
  { fontSize: 11, maxH: 0.95 }
);
note(
  s3,
  "赛题理解页：把可改与不可改列清楚。特别说明高 64 bit 不解引用是语义决定，不是漏写——这也是阶段四 lint 时唯一需要局部豁免的地方。"
);

/* ------------------------------------------------------------------ */
/* 04 阶段一：环境部署与 vadd 波形（已闭环）                            */
/* ------------------------------------------------------------------ */
const s4 = pptx.addSlide({ masterName: "BASE" });
addHeader(s4, "03 / 阶段一", "环境部署与 vadd 波形：已闭环", 4);

card(s4, { x: M, y: 1.72, w: CW, h: 0.86, fill: C.greenSoft, border: "B7DCC4" });
s4.addText("状态披露", {
  x: M + 0.22,
  y: 1.8,
  w: 1.2,
  h: 0.3,
  fontSize: 10.5,
  bold: true,
  color: C.green,
  fontFace: MONO,
});
s4.addText(
  "香山 16ae9dd 的 emu 已构建（EXIT=0），芯片级 hello 打印真实 IP，vadd 波形已采集并逐 cycle 讲解，官方 1.1–1.3 全部达标；vdot 已在香山昆明湖 V2 emu 内集成并验证（定向 7/7、非法 5/5），并取得实测加速比 9.8×（对标量，8-lane 公平）/ 11.8×（对 RVV，16-lane，属上界）。",
  {
    x: M + 1.45,
    y: 1.78,
    w: CW - 1.7,
    h: 0.72,
    fontSize: 11.5,
    color: C.ink,
    fontFace: F,
    valign: "middle",
  }
);

const flow = [
  ["香山 emu", "16ae9dd 构建，EXIT=0\n耗时约 54 min，261 MB"],
  ["官方 hello", "真实 UART 输出 + GOOD TRAP\ninstrCnt 295 / cycleCnt 10,819"],
  ["vadd 波形", "8200–8360 cycle 采集\n逐 cycle 五阶段 + 截图入库"],
];
flow.forEach((f, i) => {
  const x = M + i * 4.18;
  card(s4, {
    x,
    y: 2.86,
    w: 3.72,
    h: 1.62,
    fill: "FFFFFF",
    border: "BFDDE0",
  });
  s4.addText(f[0], {
    x: x + 0.2,
    y: 2.98,
    w: 3.3,
    h: 0.3,
    fontSize: 13,
    bold: true,
    color: C.teal,
    fontFace: F,
  });
  s4.addText(f[1], {
    x: x + 0.2,
    y: 3.34,
    w: 3.3,
    h: 0.95,
    fontSize: 10.5,
    color: C.ink,
    fontFace: F,
    lineSpacingMultiple: 1.15,
  });
  if (i < 2) {
    s4.addText("→", {
      x: x + 3.72,
      y: 3.42,
      w: 0.46,
      h: 0.4,
      fontSize: 20,
      color: C.faint,
      fontFace: F,
      align: "center",
    });
  }
});

card(s4, { x: M, y: 4.75, w: CW, h: 1.78, fill: "FFFFFF" });
s4.addText("阶段一证据（可复现）", {
  x: M + 0.25,
  y: 4.88,
  w: 5,
  h: 0.3,
  fontSize: 12,
  bold: true,
  color: C.navy,
  fontFace: F,
});
bullet(
  s4,
  M + 0.25,
  5.22,
  CW - 0.5,
  [
    "环境：01_env_setup.log 记录版本锁定、构建命令与三阶段耗时（15:33 / 8:43 / 29:58，EXIT=0）",
    "运行：02_hello_run.log 保留真实 UART 输出与 EXIT=0；03_vadd_run.log 保留波形 dump 参数",
    "波形：vadd_pipeline_wave.png + vadd_wave.md 覆盖取指/译码/执行/访存写回，数据逐字节可核对",
  ],
  { fontSize: 10.8, maxH: 1.2 }
);
note(
  s4,
  "阶段一已闭环：emu 构建、hello 真实 UART 输出、vadd 波形三件事都有日志与截图随仓库提交。vdot 的 I1–I7 香山内集成已于 2026-11-03 完成并在 emu 上验证（定向 7/7、非法 5/5），平台周期与加速比见第 10 页。"
);

/* ------------------------------------------------------------------ */
/* 05 指令语义                                                         */
/* ------------------------------------------------------------------ */
const s5 = pptx.addSlide({ masterName: "BASE" });
addHeader(s5, "04 / 指令语义", "编码、伪代码与 19 bit 陷阱", 5);

table(s5, {
  x: M,
  y: 1.72,
  w: 6.0,
  colW: [1.5, 1.35, 1.35, 1.8],
  rowH: 0.38,
  fontSize: 10,
  mono: true,
  boldCol0: false,
  rows: [
    ["字段", "位域", "取值", "说明"],
    ["funct6", "[31:26]", "111111", "RVV 保留空间"],
    ["vm", "[25]", "1", "仅无掩码形态合法"],
    ["vs2 / vs1", "[24:15]", "—", "各取低 64 bit"],
    ["funct3", "[14:12]", "000", "OPIVV"],
    ["vd", "[11:7]", "—", "结果写入 [31:0]"],
    ["opcode", "[6:0]", "0x57", "OP-V"],
  ],
});

card(s5, { x: M, y: 4.62, w: 6.0, h: 1.92, fill: C.tealSoft, border: "BFDDE0" });
s5.addText("位宽裁决", {
  x: M + 0.22,
  y: 4.72,
  w: 2,
  h: 0.3,
  fontSize: 11,
  bold: true,
  color: C.teal,
  fontFace: F,
});
s5.addText(
  [
    { text: "8 项和上界 ", options: { fontSize: 10.8, color: C.ink } },
    { text: "8×128×128 = 131,072", options: { fontSize: 10.8, bold: true, color: C.navy, fontFace: MONO } },
    { text: "，18 bit 有符号最大仅 131,071。\n所以累加位宽取 ACC_W=20（≥19），否则全 -128 输入会溢出。", options: { fontSize: 10.8, color: C.ink } },
  ],
  {
    x: M + 0.22,
    y: 5.08,
    w: 5.55,
    h: 1.28,
    fontFace: F,
    lineSpacingMultiple: 1.18,
  }
);

const pseudo = [
  "if SEW!=8 or LMUL!=1 or vm!=1: illegal",
  "if vl == 0: return          # 不写回",
  "S = 0",
  "for i in 0..7:",
  "    S += sext8(vs1[i]) * sext8(vs2[i])",
  "vd[31:0]   = S[31:0]",
  "vd[127:32] = 0",
];
s5.addShape(pptx.ShapeType.roundRect, {
  x: M + 6.15,
  y: 1.72,
  w: 5.94,
  h: 2.62,
  fill: { color: C.navy },
  line: { color: C.navy, width: 1 },
  rectRadius: 0.04,
});
s5.addText(
  pseudo.map((t) => ({
    text: t,
    options: { fontFace: MONO, fontSize: 10.5, color: "DCE9EC", breakLine: true },
  })),
  { x: M + 6.38, y: 1.9, w: 5.5, h: 2.28, valign: "top", lineSpacingMultiple: 1.22 }
);

card(s5, { x: M + 6.15, y: 4.62, w: 5.94, h: 1.92, fill: "FFFFFF" });
s5.addText("边界用例固化", {
  x: M + 6.38,
  y: 4.72,
  w: 3,
  h: 0.3,
  fontSize: 11,
  bold: true,
  color: C.navy,
  fontFace: F,
});
s5.addText(
  [
    { text: "TC-B03  全 -128 输入\n", options: { fontSize: 10.5, bold: true, color: C.navy, fontFace: F } },
    { text: "期望 ", options: { fontSize: 10.5, color: C.gray } },
    { text: "0x00020000", options: { fontSize: 10.5, color: C.teal, fontFace: MONO, bold: true } },
    { text: "；若累加器写成 16/18 bit 即在此处翻车。", options: { fontSize: 10.5, color: C.ink } },
  ],
  { x: M + 6.38, y: 5.08, w: 5.45, h: 1.2, valign: "top", lineSpacingMultiple: 1.2 }
);
note(
  s5,
  "语义页重点讲 131072 这个数：8×128×128 刚好越过 18 bit 有符号上界 131071，所以必须 19 bit 以上，我们取 20。这是设计里最容易出错的一处，已固化为 TC-B03。"
);

/* ------------------------------------------------------------------ */
/* 06 微架构                                                           */
/* ------------------------------------------------------------------ */
const s6 = pptx.addSlide({ masterName: "BASE" });
addHeader(s6, "05 / 微架构", "三级流水：乘、归约、格式化", 6);

const stages = [
  ["EX1", "8 × 有符号 8×8 乘法", "prod[0..7]", "16 bit"],
  ["EX2", "加法树 8→4→2→1", "sum2", "20 bit"],
  ["WB", "符号扩展 + 高 96 位清零", "out_vd", "128 bit"],
];
stages.forEach((st, i) => {
  const x = M + i * 4.22;
  card(s6, { x, y: 1.78, w: 3.6, h: 1.75, fill: i === 1 ? C.tealSoft : "FFFFFF", border: i === 1 ? "BFDDE0" : C.line });
  s6.addText(st[0], {
    x: x + 0.2,
    y: 1.9,
    w: 1.2,
    h: 0.3,
    fontSize: 12,
    bold: true,
    color: C.teal,
    fontFace: MONO,
    charSpacing: 1.2,
  });
  s6.addText(st[1], {
    x: x + 0.2,
    y: 2.24,
    w: 3.2,
    h: 0.55,
    fontSize: 12.5,
    bold: true,
    color: C.navy,
    fontFace: F,
  });
  s6.addText([{ text: "寄存器  ", options: { color: C.gray, fontSize: 9.5 } }, { text: st[2], options: { color: C.ink, fontSize: 9.5, fontFace: MONO } }, { text: "  ·  " + st[3], options: { color: C.gray, fontSize: 9.5 } }], {
    x: x + 0.2,
    y: 2.92,
    w: 3.2,
    h: 0.32,
    fontFace: F,
  });
  if (i < 2) {
    s6.addText("→", {
      x: x + 3.6,
      y: 2.45,
      w: 0.6,
      h: 0.4,
      fontSize: 20,
      color: C.faint,
      fontFace: F,
      align: "center",
    });
  }
});

// 周期时间轴
s6.addText("in_valid", {
  x: M,
  y: 3.72,
  w: 1.1,
  h: 0.26,
  fontSize: 9.5,
  color: C.gray,
  fontFace: MONO,
  align: "right",
});
for (let i = 0; i < 3; i++) {
  const x = M + 1.2 + i * 1.62;
  // 文字直接填在色块内（单一元素），避免"形状 + 文本"叠放
  s6.addText(["EX1", "EX2", "WB"][i], {
    x,
    y: 3.68,
    w: 1.5,
    h: 0.34,
    fontSize: 9,
    color: "FFFFFF",
    fontFace: MONO,
    bold: true,
    align: "center",
    valign: "middle",
    fill: { color: i === 0 ? C.navy : i === 1 ? C.teal : C.green },
  });
}
s6.addText("3 个时钟沿后 out_valid 有效；流水无状态，可每周期接收一条新请求", {
  x: M + 6.25,
  y: 3.7,
  w: 5.9,
  h: 0.32,
  fontSize: 10.5,
  color: C.ink,
  fontFace: F,
  valign: "middle",
});

const spec = [
  ["8", "个 8×8 有符号乘法器", "EX1 专用，不与 EX2 复用", C.navy],
  ["7", "个 20 bit 加法器", "三级树，常数索引展开", C.teal],
  ["172", "个触发器", "generic 综合统计，含控制位", C.orange],
];
spec.forEach((sp, i) => {
  const x = M + i * 4.22;
  card(s6, { x, y: 4.3, w: 3.9, h: 1.34, fill: C.soft });
  s6.addText(
    [
      { text: sp[0], options: { fontSize: 27, bold: true, color: sp[3], fontFace: F } },
      { text: "  " + sp[1], options: { fontSize: 11, bold: true, color: C.navy, fontFace: F } },
    ],
    { x: x + 0.22, y: 4.42, w: 3.46, h: 0.56, valign: "middle" }
  );
  s6.addText(sp[2], {
    x: x + 0.22,
    y: 5.04,
    w: 3.46,
    h: 0.4,
    fontSize: 9.5,
    color: C.gray,
    fontFace: F,
  });
});

card(s6, { x: M, y: 5.86, w: CW, h: 0.82, fill: "FFFFFF" });
s6.addText(
  "面积与延迟的交换：不做跨 uop 归约、不在两级间复用乘法器，换来单 uop 与 1 条/周期；代价是 8 个乘法器与 172 bit 流水寄存器。",
  {
    x: M + 0.25,
    y: 5.93,
    w: CW - 0.5,
    h: 0.66,
    fontSize: 10.5,
    color: C.ink,
    fontFace: F,
    valign: "middle",
  }
);
note(
  s6,
  "微架构页：讲清 3 级流水与 1 条/周期的来源——乘法与加法树各有独立硬件，不共享乘法器，也没有跨 uop 归约状态。"
);

/* ------------------------------------------------------------------ */
/* 07 集成方案                                                         */
/* ------------------------------------------------------------------ */
const s7 = pptx.addSlide({ masterName: "BASE" });
addHeader(s7, "06 / 集成", "只做加法：7 个注册点挂进既有框架", 7);

table(s7, {
  x: M,
  y: 1.7,
  w: 8.1,
  colW: [0.7, 1.5, 5.9],
  rowH: 0.4,
  fontSize: 10,
  rows: [
    ["#", "环节", "动作"],
    ["I1", "译码", "新增 vdot.vv 匹配项（opcode / funct3 / funct6 / vm）"],
    ["I2", "uop 类型", "新增 VFuType.VDot"],
    ["I3", "功能单元", "新增 VDot 模块，参考 VMul 结构实例化"],
    ["I4", "发射/忙表", "绑定端口与释放条件"],
    ["I5", "写回", "复用向量写回端口，置整寄存器 dirty"],
    ["I6", "配置校验", "SEW/LMUL/vm 检查，非法抛 illegal"],
    ["I7", "参数", "GROUP_K / OUT_W 参数化，便于回退"],
  ],
});

card(s7, { x: M + 8.28, y: 1.7, w: 3.81, h: 3.14, fill: C.tealSoft, border: "BFDDE0" });
s7.addText("原则", {
  x: M + 8.5,
  y: 1.82,
  w: 2,
  h: 0.3,
  fontSize: 11,
  bold: true,
  color: C.teal,
  fontFace: F,
});
bullet(
  s7,
  M + 8.5,
  2.16,
  3.35,
  [
    "不新建流水段、不改既有 VFu",
    "每完成一个环节跑一次既有向量冒烟",
    "参数化保留语义回退路径",
  ],
  { fontSize: 10.5, maxH: 2.4 }
);

card(s7, { x: M, y: 5.12, w: CW, h: 1.55, fill: C.orangeSoft, border: "EBCFAF" });
s7.addText("状态声明", {
  x: M + 0.22,
  y: 5.22,
  w: 1.2,
  h: 0.3,
  fontSize: 10.5,
  bold: true,
  color: C.orange,
  fontFace: MONO,
});
s7.addText(
  "I1–I7 已按 patches/xiangshan-vdot-integration.md 在香山源码落地，并重新生成 RTL、重建 emu：定向 7/7（difftest 0 mismatch）、非法 5/5。集成中修复两处真实缺陷（vtype 取自控制通路、vl==0 回写 oldVd）。",
  {
    x: M + 1.45,
    y: 5.16,
    w: CW - 1.7,
    h: 0.8,
    fontSize: 10.8,
    color: C.ink,
    fontFace: F,
    valign: "middle",
  }
);
note(
  s7,
  "集成页讲事实：7 个注册点都是加法式改动，已在 16ae9dd 上落地并跑通；两处缺陷（VlData 只有 8 bit、vl==0 不能屏蔽写回）是集成时暴露出来的，说明真跑过而不是纸面推演。"
);

/* ------------------------------------------------------------------ */
/* 08 功能验证                                                         */
/* ------------------------------------------------------------------ */
const s8 = pptx.addSlide({ masterName: "BASE" });
addHeader(s8, "07 / 功能验证", "1518 条用例与四个校验维度", 8);

table(s8, {
  x: M,
  y: 1.7,
  w: 7.3,
  colW: [2.1, 1.4, 1.9, 1.9],
  rowH: 0.42,
  fontSize: 10,
  rows: [
    ["用例类", "数量", "结果", "覆盖点"],
    ["定向功能", "18", "18/18", "正/负/零/边界"],
    ["随机 + 边界密集", "1500", "1500/1500", "全 int8 域、密集边界"],
    ["背靠背流式", "1024", "1024/1024", "交错发射、无气泡"],
    ["三方模型一致", "1518", "1518/1518", "Python / C / RTL"],
  ],
});

card(s8, { x: M + 7.5, y: 1.7, w: 4.59, h: 2.3, fill: C.soft });
s8.addText("1518", {
  x: M + 7.7,
  y: 1.85,
  w: 2.2,
  h: 0.75,
  fontSize: 40,
  bold: true,
  color: C.navy,
  fontFace: F,
});
s8.addText("条用例，逐位比对 128 bit 输出", {
  x: M + 7.7,
  y: 2.62,
  w: 4.1,
  h: 0.32,
  fontSize: 11,
  color: C.gray,
  fontFace: F,
});
s8.addText("断言违反 0；非法配置与 vl=0 均按语义处理", {
  x: M + 7.7,
  y: 3.02,
  w: 4.1,
  h: 0.5,
  fontSize: 10.5,
  color: C.ink,
  fontFace: F,
  lineSpacingMultiple: 1.15,
});

const dims = [
  ["全 128 bit", "不只比 vd[31:0]，高 96 位必须为 0"],
  ["语义分支", "vm=0 / SEW≠8 / LMUL≠1 → illegal；vl=0 → 不写回"],
  ["边界值", "全 -128（+131072）、全 -1、全 127、混合符号"],
  ["时序", "in_valid → out_valid 恰 3 个时钟沿，无额外气泡"],
];
dims.forEach((d, i) => {
  const x = M + (i % 2) * 6.15;
  const y = 4.2 + Math.floor(i / 2) * 1.12;
  card(s8, { x, y, w: 5.94, h: 0.98, fill: "FFFFFF" });
  s8.addShape(pptx.ShapeType.rect, { x, y: y + 0.12, w: 0.05, h: 0.74, fill: { color: C.teal } });
  s8.addText(d[0], {
    x: x + 0.2,
    y: y + 0.1,
    w: 1.7,
    h: 0.3,
    fontSize: 11,
    bold: true,
    color: C.navy,
    fontFace: F,
  });
  s8.addText(d[1], {
    x: x + 0.2,
    y: y + 0.42,
    w: 5.5,
    h: 0.44,
    fontSize: 10,
    color: C.gray,
    fontFace: F,
    valign: "middle",
  });
});
note(
  s8,
  "验证页：1518 条是向量文件规模，1024 条流式是额外运行时测试。四个维度里最重要的是全 128 bit 比对与边界值，这两点直接对应题面。"
);

/* ------------------------------------------------------------------ */
/* 09 协同仿真                                                         */
/* ------------------------------------------------------------------ */
const s9 = pptx.addSlide({ masterName: "BASE" });
addHeader(s9, "08 / 协同仿真", "同一向量集，两条执行路径，0 mismatch", 9);

const flow2 = [
  ["向量文件", "1513 条写回用例", C.navy],
  ["NEMU", "vdot 译码 + EHelper", C.teal],
  ["RTL", "Verilator 仿真导出", C.green],
];
flow2.forEach((f, i) => {
  const x = M + i * 1.85;
  card(s9, { x, y: 1.72, w: 1.62, h: 1.12, fill: "FFFFFF", border: C.line });
  s9.addText(f[0], { x: x + 0.1, y: 1.82, w: 1.42, h: 0.28, fontSize: 10.5, bold: true, color: f[2], fontFace: F, align: "center" });
  s9.addText(f[1], { x: x + 0.1, y: 2.14, w: 1.42, h: 0.6, fontSize: 8.5, color: C.gray, fontFace: F, align: "center", lineSpacingMultiple: 1.1 });
  if (i < 2) {
    s9.addText("→", { x: x + 1.62, y: 2.1, w: 0.23, h: 0.3, fontSize: 14, color: C.faint, fontFace: F, align: "center" });
  }
});

card(s9, { x: M, y: 3.05, w: 6.1, h: 2.0, fill: C.soft });
s9.addText("比对结果", {
  x: M + 0.22,
  y: 3.15,
  w: 2,
  h: 0.3,
  fontSize: 11,
  bold: true,
  color: C.navy,
  fontFace: F,
});
s9.addText(
  [
    { text: "1513 / 1513", options: { fontSize: 26, bold: true, color: C.teal, fontFace: F } },
    { text: "   RTL 结果与 NEMU 语义一致", options: { fontSize: 10.5, color: C.gray, fontFace: F } },
  ],
  { x: M + 0.22, y: 3.5, w: 5.6, h: 0.55, valign: "middle" }
);
bullet(
  s9,
  M + 0.22,
  4.12,
  5.6,
  [
    "1518 条用例中 5 条为非法/vl=0，不产生写回，比对集为 1513 条",
    "NEMU 侧改动 3 个文件、+42 行，可用 patch 复现",
  ],
  { fontSize: 10, maxH: 0.9 }
);

card(s9, { x: M + 6.35, y: 3.05, w: 5.74, h: 2.0, fill: "FFFFFF" });
s9.addText("基线对照（同一 NEMU 平台）", {
  x: M + 6.57,
  y: 3.15,
  w: 5,
  h: 0.3,
  fontSize: 11,
  bold: true,
  color: C.navy,
  fontFace: F,
});
s9.addText(
  [
    { text: "6 → 1", options: { fontSize: 26, bold: true, color: C.navy, fontFace: F } },
    { text: "   数据通路 uop（RVV 组合序列 → vdot）", options: { fontSize: 10.5, color: C.gray, fontFace: F } },
  ],
  { x: M + 6.57, y: 3.5, w: 5.2, h: 0.55, valign: "middle" }
);
bullet(
  s9,
  M + 6.57,
  4.12,
  5.25,
  [
    "基线：vsext ×2 → vmul → vredsum，共 4 个向量操作、6 条 uop",
    "基线在 NEMU 上 1513/1513 结果一致，保证比较公平",
  ],
  { fontSize: 10, maxH: 0.9 }
);

card(s9, { x: M, y: 5.32, w: CW, h: 1.3, fill: C.tealSoft, border: "BFDDE0" });
s9.addText(
  "为什么这是强证据：向量由同一文件驱动，NEMU 与 RTL 各自独立执行，任何位级差异都会暴露；非法分支与 vl=0 分支另有定向用例覆盖。",
  {
    x: M + 0.25,
    y: 5.42,
    w: CW - 0.5,
    h: 1.1,
    fontSize: 10.8,
    color: C.ink,
    fontFace: F,
    valign: "middle",
    lineSpacingMultiple: 1.15,
  }
);
note(
  s9,
  "协同页：强调同一向量集、两条独立实现路径，0 mismatch 才有意义。基线也在同一 NEMU 上跑通，避免拿不同平台的结果对比。"
);

/* ------------------------------------------------------------------ */
/* 10 性能                                                             */
/* ------------------------------------------------------------------ */
const s10 = pptx.addSlide({ masterName: "BASE" });
addHeader(s10, "09 / 性能", "三个指标，一个明确口径", 10);

table(s10, {
  x: M,
  y: 1.72,
  w: 6.55,
  colW: [2.35, 1.5, 1.35, 1.35],
  rowH: 0.5,
  fontSize: 10,
  rows: [
    ["指标", "基线", "vdot", "变化"],
    ["数据通路 uop", "6", "1", "6.0×"],
    ["emu per-iter (cycle)", "4.96", "0.51", "9.8×"],
    ["动态指令数", "89,294", "78,701", "−11.9%"],
  ],
});

s10.addChart(
  pptx.ChartType.bar,
  [
    { name: "基线", labels: ["uop 数", "per-iter 实测"], values: [6, 4.96] },
    { name: "vdot", labels: ["uop 数", "per-iter 实测"], values: [1, 0.51] },
  ],
  {
    x: M + 6.8,
    y: 1.66,
    w: 5.26,
    h: 3.35,
    barDir: "col",
    chartColors: [C.gray, C.teal],
    showValue: true,
    dataLabelFontSize: 9,
    dataLabelFontFace: MONO,
    catAxisLabelFontSize: 9,
    catAxisLabelFontFace: F,
    valAxisLabelFontSize: 9,
    valAxisLabelFontFace: MONO,
    showLegend: true,
    legendPos: "b",
    legendFontSize: 9,
    valGridLine: { style: "dash", color: C.line },
    border: { color: C.line, pt: 0.75 },
  }
);

card(s10, { x: M, y: 4.12, w: 6.55, h: 1.35, fill: C.soft });
s10.addText("口径声明", {
  x: M + 0.22,
  y: 4.22,
  w: 2,
  h: 0.3,
  fontSize: 10.5,
  bold: true,
  color: C.orange,
  fontFace: MONO,
});
s10.addText(
  "uop 数与动态指令数为实测；per-iter 为香山昆明湖 V2 emu 四内核实测（NITER=2000，扣除空循环骨架），相对标量 9.8×（8-lane 公平）、相对 RVV 基线 11.8×（16-lane，属上界）。12→3 cycle 仅为结构模型，不作实测口径。",
  { x: M + 0.22, y: 4.56, w: 6.1, h: 0.82, fontSize: 10, color: C.ink, fontFace: F, lineSpacingMultiple: 1.15 }
);

card(s10, { x: M + 6.8, y: 5.2, w: 5.26, h: 1.42, fill: "FFFFFF" });
s10.addText("怎么读这三个数", {
  x: M + 7.02,
  y: 5.3,
  w: 3,
  h: 0.3,
  fontSize: 10.5,
  bold: true,
  color: C.navy,
  fontFace: F,
});
bullet(
  s10,
  M + 7.02,
  5.62,
  4.85,
  [
    "6→1 是结构事实：一条指令替代一串组合",
    "9.8× 是整程序实测，含空循环骨架开销",
    "RVV 基线 VLMAX=16（2× lane 工作量），故对 RVV 的 11.8× 只是上界",
  ],
  { fontSize: 9.5, maxH: 0.95 }
);
note(
  s10,
  "性能页的关键是主动交代口径。若评委问加速比，回答：香山昆明湖 V2 emu 实测 9.8×（对标量，8-lane 公平）/ 11.8×（对 RVV，16-lane，属上界），口径为每迭代周期扣除空循环骨架（NITER=2000）；4.0× 延迟是结构模型，不作为实测引用。"
);

/* ------------------------------------------------------------------ */
/* 11 面积与代价                                                       */
/* ------------------------------------------------------------------ */
const s11 = pptx.addSlide({ masterName: "BASE" });
addHeader(s11, "10 / 面积", "generic 综合：4186 单元、172 触发器、25 级", 11);

const big = [
  ["4,186", "通用单元", C.navy],
  ["172", "触发器 (SDFF)", C.teal],
  ["25", "最长 R2R 路径（级）", C.orange],
  ["5.3–8.4k", "GE 等效面积（中值 ≈6.9k）", C.green],
];
big.forEach((b, i) => {
  kpi(s11, M + i * 3.13, 1.7, 2.92, b[0], "", b[1], b[2]);
});

table(s11, {
  x: M,
  y: 3.28,
  w: 6.55,
  colW: [1.9, 1.4, 1.4, 1.85],
  rowH: 0.4,
  fontSize: 10,
  mono: true,
  rows: [
    ["单元类型", "数量", "占比", "说明"],
    ["$_AND_", "1,929", "46.1%", "加法树与乘法阵列"],
    ["$_XOR_", "1,362", "32.5%", "部分积压缩"],
    ["$_OR_", "655", "15.6%", "控制与选择"],
    ["$_NOT_", "68", "1.6%", "反相"],
    ["SDFF", "172", "4.1%", "同步复位寄存器"],
  ],
});

card(s11, { x: M + 6.8, y: 3.28, w: 5.3, h: 2.42, fill: C.soft });
s11.addText("口径与边界", {
  x: M + 7.02,
  y: 3.38,
  w: 3,
  h: 0.3,
  fontSize: 10.5,
  bold: true,
  color: C.navy,
  fontFace: F,
});
bullet(
  s11,
  M + 7.02,
  3.72,
  4.85,
  [
    "Yosys 0.52 synth -noabc + techmap：工艺无关、未做 PDK 映射",
    "ABC 缺失导致结果偏保守，真实映射后通常更小",
    "µm² 与 ns 签核需工艺库，列为待解锁项 B4",
    "“每单位面积收益”需平台侧同类 VFu 数据，暂不宣称",
  ],
  { fontSize: 9.5, maxH: 2.0 }
);

card(s11, { x: M, y: 5.92, w: CW, h: 0.72, fill: C.tealSoft, border: "BFDDE0" });
s11.addText(
  "阶段四还清理了 RTL 中一整套无读者的加法树与两个无读者触发器：功能与周期不变，但严格 lint 从 4 告警降到 0，避免误导流水理解。",
  { x: M + 0.25, y: 5.98, w: CW - 0.5, h: 0.58, fontSize: 10, color: C.ink, fontFace: F, valign: "middle" }
);
note(
  s11,
  "面积页：主动说明这是 generic 综合、不是签核值，且 ABC 缺失使结果偏保守。5.3–8.4k GE 是区间口径，不报单一假精确值。"
);

/* ------------------------------------------------------------------ */
/* 12 结论                                                             */
/* ------------------------------------------------------------------ */
const s12 = pptx.addSlide({ masterName: "BASE" });
addHeader(s12, "11 / 结论", "完成度、限制与下一步", 12);

const st = [
  ["阶段一", "完成", "emu/hello/vadd 波形入库", C.green],
  ["阶段二", "完成", "1518/1518；emu 7/7", C.green],
  ["阶段三", "完成", "1513/1513；实测 9.8×", C.green],
  ["阶段四", "完成", "lint 0，综合与回归全绿", C.green],
];
st.forEach((sx, i) => {
  const x = M + i * 3.13;
  card(s12, { x, y: 1.72, w: 2.92, h: 1.06, fill: "FFFFFF" });
  s12.addText(sx[0], { x: x + 0.18, y: 1.78, w: 1.2, h: 0.26, fontSize: 9.5, color: C.gray, fontFace: MONO, bold: true });
  s12.addText(
    [
      { text: sx[1], options: { fontSize: 16, bold: true, color: sx[3] } },
    ],
    { x: x + 0.18, y: 2.08, w: 2.6, h: 0.34, fontFace: F }
  );
  s12.addText(sx[2], { x: x + 0.18, y: 2.44, w: 2.62, h: 0.26, fontSize: 8.8, color: C.gray, fontFace: F });
});

card(s12, { x: M, y: 3.05, w: 6.1, h: 3.6, fill: C.soft });
s12.addText("三条结论", {
  x: M + 0.25,
  y: 3.16,
  w: 3,
  h: 0.3,
  fontSize: 11,
  bold: true,
  color: C.navy,
  fontFace: F,
});
bullet(
  s12,
  M + 0.25,
  3.5,
  5.6,
  [
    "语义可辩护：19/20 bit 累加、全 128 bit 写回、illegal 与 vl=0 分支均有定向用例",
    "实现可复现：一条 run_all.sh 串起单元、lint、NEMU、RTL 导出、协同、基线六道门禁",
    "口径可审计：所有数字标注实测或模型，未测项（平台周期、µm²）明确列为阻塞",
  ],
  { fontSize: 10.5, maxH: 2.9 }
);

card(s12, { x: M + 6.35, y: 3.05, w: 5.74, h: 3.6, fill: "FFFFFF" });
s12.addText("下一步与答辩要点", {
  x: M + 6.57,
  y: 3.16,
  w: 4.6,
  h: 0.3,
  fontSize: 11,
  bold: true,
  color: C.navy,
  fontFace: F,
});
bullet(
  s12,
  M + 6.57,
  3.5,
  5.25,
  [
    "剩余限制：PDK 面积/时序签核（无工艺库），不得外推真实频率性能",
    "设计演进：LMUL>1 分组、双半区并行、与 VMul 的面积对比",
    "答辩准备：为何不用 16 bit 累加 / 为何新增 VFu / vstart 如何幂等",
    "表述约束：可宣称 emu 集成验证与实测 9.8×（lane 公平）/11.8×（16-lane 上界），不宣称流片级结果",
  ],
  { fontSize: 10.5, maxH: 2.9 }
);
note(
  s12,
  "收尾 30 秒：三条结论对应评审关心的三件事——语义对不对、能不能复现、数字可不可审计。最后主动说出限制，比被追问更好。"
);

/* ------------------------------------------------------------------ */
const OUT = require("path").join(__dirname, "qxriscv-vdot-2026CIE.pptx");
pptx.slides.forEach((s, i) => {
  warnIfSlideHasOverlaps(s, pptx);
  warnIfSlideElementsOutOfBounds(s, pptx);
});

// PptxGenJS 写表格时 graphicFrame 高度固定为 1 英寸，真实高度由行高决定。
// 这里按 <a:tr h> 之和回填 ext cy，避免部分渲染器裁切表格底部。
const fs = require("fs");
const JSZip = require("jszip");
async function fixTableFrames(file) {
  const zip = await JSZip.loadAsync(fs.readFileSync(file));
  let n = 0;
  for (const name of Object.keys(zip.files).filter((k) =>
    /^ppt\/slides\/slide\d+\.xml$/.test(k)
  )) {
    const xml = await zip.file(name).async("string");
    const out = xml.replace(/<p:graphicFrame>[\s\S]*?<\/p:graphicFrame>/g, (frame) => {
      if (!frame.includes("<a:tbl>")) return frame;
      const rows = [...frame.matchAll(/<a:tr h="(\d+)"/g)].map((m) => parseInt(m[1], 10));
      if (!rows.length) return frame;
      const total = rows.reduce((a, b) => a + b, 0);
      n += 1;
      return frame.replace(/(<a:ext cx="\d+" cy=")\d+("\/>)/, `$1${total}$2`);
    });
    zip.file(name, out);
  }
  fs.writeFileSync(file, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
  console.log("table frames fixed:", n);
}

pptx.writeFile({ fileName: OUT }).then(async (f) => {
  console.log("WROTE", f);
  await fixTableFrames(OUT);
});

