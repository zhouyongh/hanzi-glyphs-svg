#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成静态浏览页 viewer/index.html（零构建、零依赖、单文件、数据内联）。

用法::

    python src/build_viewer.py [--repo-root DIR] [--repo-slug owner/name]
                               [--cdn-base URL] [--no-cdn]

为什么要内联数据而不是 fetch index.csv：``fetch()`` 读本地文件会被浏览器的同源策略
挡住，直接用 ``file://`` 打开页面时拿不到数据；内联后本地双击和 GitHub Pages 都能用，
代价是数据变了要重跑本脚本。

页面对外只读，只预览 ``glyphs/<书体>/`` 里的 SVG；不复制、不修改任何字形文件。

**字形文件本身不内联**，页面按需去取，取哪个位置由 ``GLYPH_BASES`` 决定：
先是相对路径（本地 ``../glyphs/``），再是 CDN（jsDelivr / raw.githubusercontent）。
部署到 GitHub Pages 时站点只带这一个 HTML，字形从 CDN 取——``glyphs/`` 已
1.1 GB、19.2 万个文件，Pages 装不下。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = [
    ("oracle", "甲骨文", "Oracle bone script",
     "已收录 {n} 个字形（JGW 参数化矢量骨架 CC BY 4.0 + 汉典拓片摹本 CC0 1.0 "
     "+ **小学堂**甲骨文資料庫的位图描摹件 CC0 1.0），"
     "有轮廓层可切换。"),
    ("bronze", "金文", "Bronze script",
     "已收录 {n} 个字形：汉典「书法」矢量件 + **小学堂**金文資料庫的位图描摹件"
     "（均为 CC0 1.0），逐条记出处作品、编号与时代；"
     "一字多形，同字跨时代各一条，可按时代筛选。"),
    ("seal", "篆书", "Seal script",
     "已收录 {n} 个字形，源自汉典「书法」小篆实例（CC0 1.0），"
     "键为 Unicode 篆书区块码位，覆盖率见下方码位登记表。"),
    ("clerical", "隶书", "Clerical script",
     "已收录 {n} 个字形，源自汉典「书法」实例（CC0 1.0），逐条记出处作品、编号与时代；"
     "一字多形，同字跨时代各一条，可按时代筛选。"),
    ("chu", "楚文字", "Chu script",
     "已收录 {n} 个字形，源自汉典「楚系簡帛」实例（CC0 1.0），"
     "逐件记出土文献与位置，并附该字所依据的摹本底本与页.行；可按出土文献筛选。"),
    ("chuanchao", "傳抄古文", "Transmitted ancient script",
     "已收录 {n} 个字形：漢典「傳抄古文」矢量件（CC0 1.0）+ **小学堂**傳抄古文字"
     "資料庫的位图描摹件（CC0 1.0）。"
     "底本为徐在國《傳抄古文字編》；逐件记源书代号与位置，可按源书筛选。"),
    ("qinwenzi", "秦系簡牘", "Qin bamboo and wooden slips script",
     "已收录 {n} 个字形：漢典「书法」栏里的秦系矢量件 + **小学堂**秦系簡牘文字資料庫"
     "的位图描摹件（均为 CC0 1.0）；后者上游原件是位图，本地 SVG 由自动描摹生成。"
     "底本为《睡虎地秦簡文字編》等，逐件记出土文献与位置，可按出土文献筛选。"),
    ("xiaozhuan", "小篆·小学堂", "Seal script (Xiaoxuetang)",
     "已收录 {n} 个字形，源自**小学堂**小篆資料庫（CC0 1.0）："
     "上游原件是位图，本地 SVG 由自动描摹生成。"
     "与「篆书」层（漢典《說文》系，键为 Unicode 篆书区块码位）**不是同一批材料**，"
     "键空间也不同——本层的键是本仓条目号。"),
    ("kaishu", "楷书", "Regular script",
     "已收录 {n} 个字形，从 Ma Shan Zheng 字体（OFL 1.1）提取轮廓；"
     "键为现代字的 Unicode 码位，简体与繁体都在里面。"),
    ("xingshu", "行书", "Running script",
     "已收录 {n} 个字形，从 Zhi Mang Xing 字体（OFL 1.1）提取轮廓；"
     "键为现代字的 Unicode 码位。"),
    ("caoshu", "草书", "Cursive script",
     "已收录 {n} 个字形，从 Liu Jian Mao Cao 字体（OFL 1.1）提取轮廓；"
     "键为现代字的 Unicode 码位。"),
    ("songti", "宋体·简", "Song / Ming script, Simplified Chinese (mainland)",
     "已收录 {n} 个字形，从 Noto Serif SC 字体（OFL 1.1）提取轮廓；"
     "**中国大陆（简体地区）字形规范**。层名里的「简」说的是**地区规范**，"
     "不是「这一层只收简体字」——简体与繁体是不同码位，两种**都在这一层**"
     "（愛 U+611B 与 爱 U+7231），所以看到繁体字是正常的；"
     "凡大陆与港台字形有出入的地方，一律取**大陆**字形。"),
    ("songti-tc", "宋体·繁", "Song / Ming script, Traditional Chinese (TW / HK / MO)",
     "已收录 {n} 个字形，从 Noto Serif TC 字体（OFL 1.1）提取轮廓；"
     "**台湾、香港、澳门（繁体地区）字形规范**；"
     "扩展 B 区有 1,705 个简体层没有的繁体异体码位。"),
    ("heiti-hk", "黑体·港", "Sans script, Hong Kong",
     "已收录 {n} 个字形，从 Chiron Hei HK 字体（OFL 1.1）提取轮廓；"
     "**港版字形**（香港標準字形），与大陆写法有差异；扩展 B 区多出简体层收不到的码位。"),
]

# **按层里实际有的内容**才追加的话。
#
# 说明文字写「另有小学堂描摹件」而层里其实没有，等于告诉读者一个假事实——
# 所以这几段只在层里**真有**位图描摹件时才出现。判据是 provenance 里的
# ``transform`` 是否带 marching-squares（位图 → SVG 的描摹件才带；
# 甲骨层 JGW 的矢量转轮廓不带）。
EXTRA_NOTES = {
    "chu": "另有**小学堂**（中央研究院數位文化中心）楚系簡帛文字資料庫的"
           "**位图描摹件**（CC0 1.0）补缺口：同一字形以漢典矢量为主源，"
           "小學堂只补漢典没有的字形与出處。",
}


def has_traced_glyphs(glyphs_root: Path, script: str) -> bool:
    """这一层里有没有**位图描摹件**（有的话才配说小學堂）。"""
    prov = glyphs_root / "provenance" / f"{script}.jsonl"
    if not prov.is_file():
        return False
    with prov.open(encoding="utf-8") as fh:
        for line in fh:
            if "marching-squares" in line:
                return True
    return False


def extra_note(glyphs_root: Path, script: str) -> str:
    """这一层该追加的说明（没有就返回空串）。"""
    note = EXTRA_NOTES.get(script, "")
    return note if note and has_traced_glyphs(glyphs_root, script) else ""


def pending_note(glyphs_root: Path, script: str) -> str:
    """这一层有没有**待补清单**（有就在说明里说清楚缺多少、缺在哪）。

    数字取**清单里的实际条数**，不写死——写死的数字迟早过期，
    而过期数字比没有数字更坏：读者会拿它当依据。
    """
    path = glyphs_root / script / "pending-xxt.csv"
    if not path.is_file():
        return ""
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        n = sum(1 for _ in csv.DictReader(fh))
    if not n:
        return ""
    return (f"另有 **{n}** 件小學堂位图描摹件暂缺，"
            f"逐条登记在 `glyphs/{script}/pending-xxt.csv`。")

# 仓库的 GitHub slug。用来拼 CDN 地址与文档链接。
DEFAULT_REPO_SLUG = "zhouyongh/hanzi-glyphs-svg"

# 部署到 GitHub Pages 时，站点**不带上** glyphs/（已 1.1 GB、19.2 万个文件，
# Pages 装不下），字形改从 CDN 按需取。
#
# **要几个源，不是一个。** 2026-10-25 实测：线上偶有字形取不到（隶书里三格
# 空白），查下来文件本身完好、CDN 也正常——是**某一次请求**失败，而当时的兜底链
# 只有「相对路径 → raw.githubusercontent」两条：前者部署到站点根必然 404，
# 后者在国内常常连不上，等于没有兜底，那格就永久空白。
#
# jsDelivr 有三个独立的主机名（cdn / fastly / gcore），分属不同网络：
# 某个边缘节点缓存了坏响应时，换一个节点就能拿到。三个都留着，再加 raw 兜底。
DEFAULT_CDN_BASES = (
    "https://cdn.jsdelivr.net/gh/{slug}@main/glyphs/",
    "https://fastly.jsdelivr.net/gh/{slug}@main/glyphs/",
    "https://gcore.jsdelivr.net/gh/{slug}@main/glyphs/",
    "https://raw.githubusercontent.com/{slug}/main/glyphs/",
)

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>汉字字形库 · 浏览</title>
<style>
  /* 视觉语言与兄弟仓库 hanzi-relations 保持一致：纸色底、墨色字、赭色强调。
     设计 token 直接沿用那边的 :root，两个页面看着像一套东西。 */
  :root { --bg:#fbfaf7; --panel:#fff; --ink:#1c1b18; --mute:#6b6862; --line:#e3ded4;
          --accent:#8a6d3b; --accent2:#3f5d52; --warn:#a1442f; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.7 "Noto Serif CJK SC","Source Han Serif SC","Songti SC",Georgia,serif; }
  a { color:var(--accent2); }

  header { background:var(--panel); border-bottom:1px solid var(--line);
           padding:20px 24px 18px; box-shadow:0 1px 3px rgba(0,0,0,.04); }
  h1 { margin:0 0 4px; font-size:24px; letter-spacing:.02em; }
  h1 .latin { color:var(--mute); font-size:.72em; letter-spacing:.04em; }
  .sub { color:var(--mute); font-size:13px; margin:0 0 10px; }
  .lede { color:var(--mute); margin:0; max-width:76em; font-size:13.5px; line-height:1.85; }

  nav { display:flex; gap:8px; flex-wrap:wrap; padding:12px 24px; position:sticky; top:0; z-index:10;
        background:var(--panel); border-bottom:1px solid var(--line);
        box-shadow:0 1px 3px rgba(0,0,0,.04); }
  nav button { appearance:none; border:1px solid var(--line); border-radius:6px;
               background:var(--panel); padding:7px 13px; cursor:pointer;
               font:inherit; font-size:14px; color:var(--mute); }
  nav button:hover { border-color:var(--accent); color:var(--accent); }
  nav button[aria-selected="true"] { background:var(--accent); color:#fff;
               border-color:var(--accent); font-weight:600; }
  nav button .n { font-weight:400; font-size:12px; margin-left:5px; opacity:.7; }

  main { padding:20px 24px 40px; }
  .panel[hidden] { display:none; }
  .toolbar { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
  .seg { display:inline-flex; border:1px solid var(--line); border-radius:6px; overflow:hidden;
         background:var(--panel); }
  .seg button { appearance:none; border:0; background:none; padding:8px 14px; cursor:pointer;
                font:inherit; font-size:14px; color:var(--mute); }
  .seg button:hover { color:var(--accent); }
  .seg button[aria-pressed="true"] { background:var(--accent); color:#fff; font-weight:600; }
  input[type=search] { flex:1; min-width:230px; padding:9px 12px; border:1px solid var(--line);
                       border-radius:6px; font:inherit; font-size:15px;
                       background:var(--panel); color:var(--ink); }
  input[type=search]:focus { outline:2px solid var(--accent); outline-offset:-1px; }
  select.era { padding:8px 12px; border:1px solid var(--line); border-radius:6px; font:inherit;
               font-size:14px; background:var(--panel); color:var(--ink); cursor:pointer; }
  select.era:hover { border-color:var(--accent); }
  label.chk { display:inline-flex; gap:6px; align-items:center; color:var(--mute);
              cursor:pointer; font-size:14px; }
  .count { color:var(--mute); font-size:12.5px; margin-left:auto; }
  .layer-note { color:var(--mute); font-size:13.5px; margin:0 0 14px; max-width:76em; line-height:1.85; }

  .grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(82px, 1fr)); gap:9px; }
  figure { margin:0; background:var(--panel); border:1px solid var(--line); border-radius:8px;
           padding:8px 6px 6px; text-align:center; box-shadow:0 1px 2px rgba(0,0,0,.03); }
  figure:hover { border-color:var(--accent); box-shadow:0 2px 8px rgba(0,0,0,.06); }
  figure.flag { border-color:#d9c08a; background:#fdfaf2; }
  /* 所有源都取不到：红框 + 角标。别让「取不到」看起来像「这个字形是空的」。 */
  figure.failed { border-color:var(--warn); background:#fdf3f0; }
  .fail-note { color:var(--warn); font-size:10px; margin-top:2px; }
  figure a { display:block; }
  figure img { width:100%; height:64px; object-fit:contain; display:block; }
  figcaption { font-size:11.5px; color:var(--mute); margin-top:4px; white-space:nowrap;
               overflow:hidden; text-overflow:ellipsis; }
  figcaption b { color:var(--ink); font-weight:600; }
  figcaption i { font-style:normal; color:var(--accent2); }
  .empty { color:var(--mute); background:var(--panel); border:1px solid var(--line);
           border-radius:8px; padding:20px; max-width:60em; }
  .more { display:block; margin:18px auto; padding:9px 22px; border:1px solid var(--line);
          border-radius:6px; background:var(--panel); color:var(--mute); cursor:pointer;
          font:inherit; font-size:14px; }
  .more:hover { color:var(--accent); border-color:var(--accent); }
  .more[hidden] { display:none; }
  .boot { color:var(--mute); padding:30px 0; }
  .extcard { background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--accent);
             border-radius:8px; padding:18px 22px; max-width:62em;
             box-shadow:0 1px 2px rgba(0,0,0,.03); }
  .extcard p { margin:0 0 10px; }
  .extcard ul { margin:0 0 10px; padding-left:20px; color:var(--mute); }
  .extcard li { margin:4px 0; }
  .extcard b { color:var(--ink); }
  .extcard .why { color:var(--mute); font-size:12.5px; margin:0; }
  footer { padding:0 24px 30px; color:var(--mute); font-size:12px; }
  code { background:#f0ebe0; color:#6b5a3a; padding:1px 5px; border-radius:3px; font-size:.92em; }
</style>
</head>
<body>
<header>
  <h1>汉字字形库 <span class="latin">hanzi-glyphs-svg</span></h1>
  <p class="sub">只读预览 · 每一格都能追到出处</p>
  <p class="lede">
    字形文件在 <code>glyphs/</code>，每个字形一条出处记录在
    <code>glyphs/provenance/&lt;书体&gt;.jsonl</code>。
    甲骨文字形来源为
    <a href="https://zenodo.org/records/22467946" target="_blank" rel="noopener">Zenodo 10.5281/zenodo.22467946</a>，
    依 <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a>
    使用；金文、隶书、篆书、楚文字与甲骨拓片摹本来自汉典（zdic.net）「书法」实例，
    依其《服务条款》第四条以
    <a href="https://creativecommons.org/publicdomain/zero/1.0/" target="_blank" rel="noopener">CC0 1.0</a>
    释出；楷书、行书、草书、宋体、黑体六层是从 OFL 开源字体提取的轮廓，依
    <a href="https://openfontlicense.org" target="_blank" rel="noopener">SIL OFL 1.1</a>
    分发（许可全文与版权行在各层目录的 <code>OFL.txt</code>）。
    完整署名与改动声明见仓库 <code>THIRD_PARTY_NOTICES.md</code>。
  </p>
</header>
<nav id="tabs" role="tablist"></nav>
<main id="panels"><p class="boot">正在准备字形数据…</p></main>
<footer>
  页面由 <code>python src/build_viewer.py</code> 生成于 __GENERATED__；数据变更后需重跑。
  点任意字形可在新标签页打开原 SVG。
</footer>
<script id="glyph-data" type="application/json">__DATA__</script>
<script>
(function () {
  var DATA = JSON.parse(document.getElementById('glyph-data').textContent);
  var SCRIPTS = __SCRIPTS__;
  var tabs = document.getElementById('tabs');
  var panels = document.getElementById('panels');
  var LAYER_LABEL = { skeleton: '骨架', outline: '轮廓（可填充）' };

  // 一屏最多先画这么多字形，剩下的滚到底再画。
  // 全库 93,875 个字形一次性塞进 DOM 会把浏览器卡死（实测导航直接超时），
  // 所以这里必须分块：先画一小批，滚到了再接着画。
  var CHUNK = 400;

  // 字形目录的前缀。页面有几种放法，按顺序试，谁先成功用谁：
  //   1) glyphs/     —— 与页面同目录（旧的整目录部署）
  //   2) ../glyphs/  —— 仓库里的 viewer/index.html（本地双击）
  //   3) jsDelivr    —— GitHub Pages 只发布浏览页时，字形从 CDN 取
  //                    （cdn / fastly / gcore 三个主机名分属不同网络）
  //   4) raw.githubusercontent —— CDN 不可用时的兜底
  //
  // **本地优先**：工作区里可能有还没 push 的字形，本地预览必须看到
  // 工作区的那一份，而不是 CDN 上的旧版。所以相对路径排在网络地址前面。
  // **但重试时反过来**：相对路径在站点形态下必然 404，垫底。见 retryPlan()。
  var GLYPH_BASES = __GLYPH_BASES__;
  var glyphBase = null;

  // 只有绝对地址才算「网络源」。相对路径（glyphs/、../glyphs/）只在页面就放在
  // 仓库里时才有意义；部署到站点根（GitHub Pages）时它们必然 404，
  // 重试时不该再排在网络源前面——那等于每次失败都白等两轮。
  function isRemote(base) { return /^https?:\/\//i.test(base); }
  var REMOTE_BASES = GLYPH_BASES.filter(isRemote);

  // 仓库里的文档链接用**绝对地址**：页面在仓库里（viewer/index.html）和
  // 部署到站点根（index.html）时相对路径不一样，写死一种总会错一边。
  var REPO_BLOB = '__REPO_BLOB__';

  // 探测用哪个源取字形。**每个源试两次**：一次网络抖动就把整页的源选错，
  // 后面所有字形都要多绕两轮才显示出来——实测踩过这个坑。
  function probeBase(base, attempt) {
    attempt = attempt || 0;
    return new Promise(function (resolve) {
      var img = new Image();
      img.onload = function () { resolve(base); };
      img.onerror = function () {
        if (attempt < 1) { resolve(probeBase(base, attempt + 1)); }
        else { resolve(null); }
      };
      img.src = base + 'oracle/0001.svg';
    });
  }

  function detectBase() {
    var i = 0;
    function next() {
      if (i >= GLYPH_BASES.length) { return Promise.resolve(GLYPH_BASES[0]); }
      var base = GLYPH_BASES[i++];
      return probeBase(base).then(function (ok) { return ok || next(); });
    }
    return next();
  }

  // 一张图取不到时的**重试计划**（按顺序试）：
  //   1) 同一个源再来一次，但加一个查询串——绕开边缘节点与浏览器自己的负缓存。
  //      jsDelivr 刚回源取过这一份，第二次多半就成了。
  //   2) 换别的网络源。jsDelivr 有三个独立的主机名（cdn / fastly / gcore），
  //      分属不同网络；某个边缘节点缓存了坏响应时，换一个节点就能拿到。
  //      最后是 raw.githubusercontent。
  //   3) 最后才轮到相对路径：部署到站点根时它们必然 404，只是本地预览用得上。
  //
  // 为什么排这个序：2026-10-25 实测线上偶有字形取不到，原因是**兜底链本身**
  // 当时只有「相对路径 → raw.githubusercontent」两条路——前者必 404，后者在国内
  // 常常连不上，等于没有兜底，于是那格就永久空白。
  function retryPlan(rel) {
    var plan = [];
    if (isRemote(glyphBase)) { plan.push(glyphBase + rel + '?r=1'); }
    REMOTE_BASES.forEach(function (b) {
      if (b !== glyphBase) { plan.push(b + rel); }
    });
    GLYPH_BASES.forEach(function (b) {
      if (!isRemote(b)) { plan.push(b + rel); }
    });
    return plan;
  }

  // 所有源都试过了还是取不到：把格子**标出来**。
  // 「取不到」和「字形本来就是空的」必须一眼能分清——不然只能靠猜。
  function markFailed(img, rel) {
    var fig = img.closest ? img.closest('figure') : null;
    if (!fig || fig.querySelector('.fail-note')) { return; }
    fig.classList.add('failed');
    var note = document.createElement('div');
    note.className = 'fail-note';
    note.textContent = '取不到';
    note.title = rel;
    fig.appendChild(note);
  }

  function attachFallback(img) {
    var rel = img.getAttribute('data-g');
    var plan = retryPlan(rel);
    var n = 0;
    img.addEventListener('error', function () {
      if (n >= plan.length) { markFailed(img, rel); return; }
      img.src = plan[n];
      n += 1;
    });
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  // 层说明写在 Python 里，用的是 Markdown 的 **粗体**。
  // 页面里只支持这一种标记，别的按原样转义显示。
  function note(s) {
    return esc(s).replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  }

  function svgURL(script, file, layer) {
    return glyphBase + script + '/' + (layer === 'outline' ? 'outline/' : '') + file;
  }

  function tabCount(script) {
    var local = (DATA[script] || []).length;
    if (local) { return String(local); }
    var ext = DATA.__external && DATA.__external[script];
    return ext ? ext.codepoint_count + ' 外链' : '0';
  }

  function cellHTML(script, row, layer) {
    var url = svgURL(script, row.file, layer);
    // data-g 存的是「层/子目录/文件名」——换前缀重试时要用它拼路径。
    var rel = script + '/' + (layer === 'outline' ? 'outline/' : '') + row.file;
    var title = '#' + row.i + ' ' + (row.c || '（无对应现代汉字）') +
                '  U+' + (row.u || '—') + '  ' + (row.p || '') + '  [' + row.k + ']' +
                (row.t ? '  ' + row.t : '') +
                (row.s ? '  ' + row.s : '');
    return '<figure class="cell' + (row.flag ? ' flag' : '') + '" title="' + esc(title) + '">' +
           '<a href="' + url + '" target="_blank" rel="noopener">' +
           '<img loading="lazy" src="' + url + '" data-g="' + esc(rel) + '" alt="' + esc(title) + '"></a>' +
           '<figcaption><b>' + esc(row.i) + '</b> ' + esc(row.c || '—') +
           (row.t ? ' <i>' + esc(row.t) + '</i>' : '') + '</figcaption>' +
           '</figure>';
  }

  function buildPanel(script) {
    var meta = SCRIPTS.filter(function (s) { return s[0] === script; })[0];
    var rows = DATA[script] || [];
    var panel = document.createElement('section');
    panel.className = 'panel';
    panel.id = 'panel-' + script;
    panel.setAttribute('role', 'tabpanel');

    if (!rows.length) {
      var ex = DATA.__external && DATA.__external[script];
      if (ex) {
        panel.innerHTML =
          '<div class="extcard">' +
            '<p><b>' + esc(meta[1]) + '</b>（' + esc(meta[2]) + '）本层<b>未收录字形文件</b>，' +
            '只登记指向上游的映射。本页不内嵌、不复制上游字形。</p>' +
            '<ul>' +
              '<li>Unicode 18.0 篆书区块码位：<b>' + ex.codepoint_count + '</b></li>' +
              '<li>上游已有字形文件：<b>' + ex.codepoints_with_upstream + '</b>' +
                  '（另有 ' + (ex.codepoint_count - ex.codepoints_with_upstream) + ' 个码位上游尚无字形）</li>' +
              '<li>上游仓库：<a href="https://github.com/' + esc(ex.upstream_repo) + '" target="_blank" rel="noopener">' +
                  esc(ex.upstream_repo) + '</a>（钉住 commit <code>' + esc(ex.upstream_commit.slice(0, 12)) + '</code>）</li>' +
              '<li>登记表：<a href="' + REPO_BLOB + esc(ex.registry) + '" target="_blank" rel="noopener">' +
                  esc(ex.registry) + '</a>' +
                  '　说明：<a href="' + REPO_BLOB + esc(ex.readme) + '" target="_blank" rel="noopener">' +
                  esc(ex.readme) + '</a></li>' +
            '</ul>' +
            '<p class="why">未收录的原因：上游的授权语句只覆盖「output fonts」，其 <code>glyphs/**</code> ' +
            '未被明确标记为受 OFL 约束；仓库根目录也没有 LICENSE 文件。' +
            '（上游随附的 <code>OFL.txt</code> 并非 SIL 官方 OFL 1.1 文本：第 1、2 条与官方逐字相同，' +
            '第 3–9 条相似度最高 0.344、第 10 条 0.602，官方第 5 条「不得按其他许可分发」缺失。）' +
            '详见 <a href="' + REPO_BLOB + 'THIRD_PARTY_NOTICES.md" target="_blank" rel="noopener">' +
            'THIRD_PARTY_NOTICES.md</a>。' +
            '上游澄清后可用同一份登记表一次性导入。</p>' +
          '</div>';
        return panel;
      }
      panel.innerHTML = '<p class="empty"><b>' + esc(meta[1]) + '</b>（' + esc(meta[2]) +
                        '）尚未收录。<br>' + esc(meta[3]) + '</p>';
      return panel;
    }

    var hasOutline = !!(DATA.__outline && DATA.__outline[script]);
    var seg = '';
    if (hasOutline) {
      seg = '<div class="seg" role="group" aria-label="字形层">' +
            '<button type="button" data-layer="skeleton" aria-pressed="true">骨架</button>' +
            '<button type="button" data-layer="outline" aria-pressed="false">轮廓（可填充）</button>' +
            '</div>';
    }
    // 筛选：金文与隶书层「一字多形」，同一个字在不同时代各有一条，
    // 按时代筛才看得出字形怎么随时间变。
    // 楚文字层**没有时代**（题记里一个时代词都没有），改按出土文献筛。
    var eras = [];
    var seenEra = {};
    rows.forEach(function (r) {
      if (r.t && !seenEra[r.t]) { seenEra[r.t] = 1; eras.push(r.t); }
    });
    var filterKey = 't';
    var filterLabel = '按时代筛选';
    var filterAll = '全部时代';
    if (eras.length <= 1) {
      var books = [];
      var seenBook = {};
      rows.forEach(function (r) {
        if (r.s && !seenBook[r.s]) { seenBook[r.s] = 1; books.push(r.s); }
      });
      if (books.length > 1) {
        filterKey = 's';
        // 没有时代维度的层，筛的其实是另一件事：楚文字筛**出土文献**，
        // 傳抄古文筛**源书**——标签要说清楚筛的到底是什么。
        var labels = {
          chu: { label: '按出土文献筛选', all: '全部文献' },
          chuanchao: { label: '按源书筛选', all: '全部源书' }
        };
        var spec = labels[script] || { label: '按出处筛选', all: '全部出处' };
        filterLabel = spec.label;
        filterAll = spec.all;
        eras = books;
      }
    }
    var eraSelect = '';
    if (eras.length > 1) {
      var opts = ['<option value="">' + filterAll + '</option>'];
      eras.forEach(function (t) {
        var n = rows.filter(function (r) { return r[filterKey] === t; }).length;
        opts.push('<option value="' + esc(t) + '">' + esc(t) + '（' + n + '）</option>');
      });
      eraSelect = '<select class="era" aria-label="' + esc(filterLabel) + '">' + opts.join('') + '</select>';
    }
    panel.innerHTML =
      '<div class="toolbar">' + seg + eraSelect +
        '<input type="search" placeholder="搜索：编号 / 现代字 / 码位 / 拼音" aria-label="搜索字形">' +
        '<label class="chk"><input type="checkbox"> 只看待复核</label>' +
        '<span class="count"></span>' +
      '</div>' +
      '<p class="layer-note">' + note(meta[3]) + '</p>' +
      '<div class="grid"></div>' +
      '<button type="button" class="more" hidden>加载更多…</button>';

    var layer = 'skeleton';
    var grid = panel.querySelector('.grid');
    var moreBtn = panel.querySelector('.more');
    var countEl = panel.querySelector('.count');
    var search = panel.querySelector('input[type=search]');
    var onlyFlag = panel.querySelector('input[type=checkbox]');
    var eraBox = panel.querySelector('select.era');

    var shown = [];   // 当前筛选出来的字形
    var cursor = 0;   // 已经画到第几个

    function updateCount() {
      countEl.textContent = shown.length === rows.length
        ? '共 ' + rows.length + ' 个字形'
        : shown.length + ' / ' + rows.length + ' 个字形';
    }

    function drawChunk() {
      if (cursor >= shown.length) {
        moreBtn.hidden = true;
        return;
      }
      var slice = shown.slice(cursor, cursor + CHUNK);
      var before = grid.querySelectorAll('img').length;
      grid.insertAdjacentHTML('beforeend', slice.map(function (r) {
        return cellHTML(script, r, layer);
      }).join(''));
      // 给新加的图挂上「换前缀重试」的兜底（只处理这一批，不重扫全网格）。
      var imgs = grid.querySelectorAll('img');
      for (var i = before; i < imgs.length; i++) { attachFallback(imgs[i]); }
      cursor += slice.length;
      moreBtn.hidden = cursor >= shown.length;
      if (cursor < shown.length) {
        moreBtn.textContent = '加载更多…（已显示 ' + cursor + ' / ' + shown.length + '）';
      }
    }

    function render() {
      var q = search.value.trim().toLowerCase();
      var era = eraBox ? eraBox.value : '';
      shown = rows.filter(function (r) {
        if (onlyFlag.checked && !r.flag) { return false; }
        if (era && r[filterKey] !== era) { return false; }
        if (!q) { return true; }
        return (r.i + ' ' + r.c + ' ' + r.u + ' ' + r.p + ' ' + r.t).toLowerCase().indexOf(q) >= 0;
      });
      grid.innerHTML = '';
      cursor = 0;
      updateCount();
      drawChunk();
    }

    Array.prototype.forEach.call(panel.querySelectorAll('.seg button'), function (btn) {
      btn.addEventListener('click', function () {
        layer = btn.getAttribute('data-layer');
        Array.prototype.forEach.call(panel.querySelectorAll('.seg button'), function (b) {
          b.setAttribute('aria-pressed', String(b === btn));
        });
        render();
      });
    });
    search.addEventListener('input', render);
    onlyFlag.addEventListener('change', render);
    if (eraBox) { eraBox.addEventListener('change', render); }
    moreBtn.addEventListener('click', drawChunk);
    // 滚到底就接着画下一批，不用手动点。
    if (typeof IntersectionObserver === 'function') {
      new IntersectionObserver(function (entries) {
        if (entries[0].isIntersecting) { drawChunk(); }
      }, { rootMargin: '400px' }).observe(moreBtn);
    }
    // 第一次显示这个 Tab 时才画字形：还没点到的层不必先渲染几千张图。
    panel.__render = render;
    return panel;
  }

  function buildTabs() {
    panels.innerHTML = '';
    SCRIPTS.forEach(function (s, idx) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('role', 'tab');
      btn.setAttribute('aria-selected', String(idx === 0));
      btn.setAttribute('aria-controls', 'panel-' + s[0]);
      btn.innerHTML = esc(s[1]) + '<span class="n">' + tabCount(s[0]) + '</span>';
      btn.addEventListener('click', function () {
        Array.prototype.forEach.call(tabs.querySelectorAll('button'), function (b) {
          b.setAttribute('aria-selected', String(b === btn));
        });
        Array.prototype.forEach.call(panels.querySelectorAll('.panel'), function (p) {
          p.hidden = (p.id !== 'panel-' + s[0]);
        });
        var panel = document.getElementById('panel-' + s[0]);
        if (panel && panel.__render && !panel.__rendered) {
          panel.__rendered = true;
          panel.__render();
        }
      });
      tabs.appendChild(btn);

      var panel = buildPanel(s[0]);
      panel.hidden = (idx !== 0);
      panels.appendChild(panel);
      if (idx === 0) { panel.__rendered = true; }
    });
    // 默认层也要画
    var first = document.getElementById('panel-' + SCRIPTS[0][0]);
    if (first && first.__render) { first.__render(); }
  }

  detectBase().then(function (base) {
    glyphBase = base;
    buildTabs();
  });
})();
</script>
</body>
</html>
"""


def load_rows(index_path: Path) -> list[dict]:
    """把一处 index.csv 压成浏览页要用的紧凑记录。

    **篆书层的键不是 glyph_id，而是篆书区块码位**（``codepoint`` 列），
    所以这里的标识符与排序方式要跟着层走。
    """
    with index_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        raw = list(reader)
        fields = set(reader.fieldnames or [])
    # 只有甲骨层有「身份确认度」这一列；别的书体（每个实例都对着具体字与出处）
    # 不该被标成「待复核」。
    has_confidence = "identity_confidence" in fields
    keyed_by_codepoint = "codepoint" in fields
    rows = []
    for row in raw:
        confidence = (row.get("identity_confidence") or "").strip()
        ident = (row.get("glyph_id") if not keyed_by_codepoint
                 else row.get("codepoint") or "").strip()
        rows.append({
            "i": ident,
            "c": (row.get("modern_char") or "").strip(),
            "u": (row.get("unicode") or "").strip(),
            "p": (row.get("pinyin") or "").strip(),
            "t": (row.get("period") or "").strip(),
            "k": confidence if has_confidence else "",
            "s": (row.get("source_book") or row.get("variant")
                  or row.get("font_name") or "").strip(),
            # 只有「填了确认度但不是 high」才算待复核。同一层里别的来源
            # （甲骨层的汉典摹本）没有这一列，值是空的——那不是待复核。
            "flag": 1 if (has_confidence and confidence and confidence != "high") else 0,
            "file": row["file"],
        })
    if keyed_by_codepoint:
        rows.sort(key=lambda r: int(r["i"], 16))
    else:
        rows.sort(key=lambda r: int(r["i"]))
    return rows, keyed_by_codepoint


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生成静态浏览页")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--repo-slug", default=DEFAULT_REPO_SLUG,
                        help="GitHub 仓库 slug（owner/name），用来拼 CDN 与文档链接")
    parser.add_argument("--cdn-base", action="append", default=None,
                        help="字形的 CDN 前缀（可重复）。默认四条：jsDelivr 的 cdn / fastly / gcore "
                             "三个节点 + raw.githubusercontent 兜底")
    parser.add_argument("--no-cdn", action="store_true",
                        help="只用相对路径取字形，不联网（离线生成时用）")
    parser.add_argument("--out", type=Path, default=None,
                        help="写到哪里（默认 <repo-root>/viewer/index.html）。"
                             "要做「站点形态」的测试页时用得到——站点上页面在根目录，"
                             "相对路径 ../glyphs/ 必然 404，只能靠 CDN 取字形")
    args = parser.parse_args(argv)

    repo_root: Path = args.repo_root.resolve()
    glyphs_root = repo_root / "glyphs"

    # 字形前缀候选：**相对路径在前、网络地址在后**。
    # 本地双击时相对路径先命中——工作区里可能有还没 push 的字形，
    # 本地预览必须看到工作区的那一份，而不是 CDN 上的旧版。
    glyph_bases = ["glyphs/", "../glyphs/"]
    if not args.no_cdn:
        if args.cdn_base:
            glyph_bases.extend(args.cdn_base)
        else:
            glyph_bases.extend(b.format(slug=args.repo_slug) for b in DEFAULT_CDN_BASES)
    repo_blob = f"https://github.com/{args.repo_slug}/blob/main/"

    data: dict[str, list[dict]] = {}
    outline: dict[str, bool] = {}
    external: dict[str, dict] = {}
    total = 0

    # 只给「真的有这一层」的书体出标签页：没发布/没入库的层连 index.csv 都没有，
    # 画一个空标签页等于让读者以为库里有这一层。
    active = [s for s in SCRIPTS if (glyphs_root / s[0] / "index.csv").is_file()]

    for script, zh, _en, _note in active:
        index_path = glyphs_root / script / "index.csv"
        # 登记表（external.csv）可以和字形并存，所以有字形时也要读它。
        meta_path = glyphs_root / script / "external.meta.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["registry"] = f"glyphs/{script}/external.csv"
            meta["readme"] = f"glyphs/{script}/README.md"
            external[script] = meta
        rows, keyed_by_codepoint = load_rows(index_path)
        if not keyed_by_codepoint:
            expected = [str(n) for n in range(1, len(rows) + 1)]
            if [r["i"] for r in rows] != expected:
                print(f"警告：{script}/index.csv 的 glyph_id 不是 1..{len(rows)} 连续编号",
                      file=sys.stderr)
        for row in rows:
            if not (glyphs_root / script / row["file"]).is_file():
                raise SystemExit(f"缺字形文件：glyphs/{script}/{row['file']}")
        data[script] = rows
        outline[script] = (glyphs_root / script / "outline").is_dir()
        total += len(rows)

    payload_obj: dict[str, object] = dict(data)
    payload_obj["__outline"] = outline
    payload_obj["__external"] = external
    payload = json.dumps(payload_obj, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c")  # 数据里若出现 </script> 不会截断脚本

    page = (TEMPLATE
            .replace("__DATA__", payload)
            .replace("__GLYPH_BASES__", json.dumps(glyph_bases, ensure_ascii=False))
            .replace("__REPO_BLOB__", repo_blob)
            .replace("__SCRIPTS__", json.dumps(
                # 说明里的字数用**实际条数**填，不写死——写死的数字迟早过期，
                # 而过期数字比没有数字更坏：读者会拿它当依据。
                # 追加的说明按层里**实际有的内容**决定（见 extra_note）。
                [[s[0], s[1], s[2],
                  s[3].format(n=len(data.get(s[0], []))) + extra_note(glyphs_root, s[0])
                  + pending_note(glyphs_root, s[0])]
                 for s in active], ensure_ascii=False))
            .replace("__GENERATED__",
                     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))

    out_path = (args.out.resolve() if args.out
                else repo_root / "viewer" / "index.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # **布局关键声明的最小体检。**
    # CSS 里属性名写错，浏览器**静默丢弃**那条声明，不报错、不打日志——
    # 页面照常打开，只是布局悄悄变了（踩过：把 grid-template-columns 写成
    # grid-columns，字形网格就退化成块级堆叠，一列一行，页面上根本看不出来）。
    # 这类错误没有浏览器就查不出来，所以在这里钉几个「少了就会塌」的声明。
    for must in ("display:grid", "grid-template-columns", "object-fit:contain",
                 "nav button[aria-selected", "figure img", "figure.failed"):
        if must not in page:
            raise SystemExit(f"浏览页 CSS 少了关键声明 {must!r}——"
                             f"多半是属性名写错了（浏览器会静默丢弃）。")

    out_path.write_text(page, encoding="utf-8", newline="\n")

    print(f"写出     : {out_path}  ({out_path.stat().st_size} bytes)")
    print(f"字形总数 : {total}")
    print("字形前缀 : " + " → ".join(glyph_bases))
    for script, zh, _en, _note in active:
        rows = data[script]
        flag = sum(1 for r in rows if r["flag"])
        extra = "（有轮廓层）" if outline.get(script) else ""
        print(f"  {zh:<4} {len(rows):>5} 个，待复核 {flag} 个 {extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
