#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成静态浏览页 viewer/index.html（零构建、零依赖、单文件、数据内联）。

用法::

    python src/build_viewer.py [--repo-root DIR]

为什么要内联数据而不是 fetch index.csv：``fetch()`` 读本地文件会被浏览器的同源策略
挡住，直接用 ``file://`` 打开页面时拿不到数据；内联后本地双击和 GitHub Pages 都能用，
代价是数据变了要重跑本脚本。

页面对外只读，只预览 ``glyphs/<书体>/`` 里的 SVG；不复制、不修改任何字形文件。
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
     "已收录 {n} 个字形，JGW 参数化矢量骨架（CC BY 4.0，DOI 10.5281/zenodo.22467946），"
     "有轮廓层可切换。"),
    ("bronze", "金文", "Bronze script",
     "已收录 {n} 个字形，源自汉典「书法」实例（CC0 1.0），逐条记出处作品、编号与时代；"
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
     "已收录 {n} 个字形，源自汉典「傳抄古文」实例（CC0 1.0），"
     "底本为徐在國《傳抄古文字編》；逐件记源书代号与位置，可按源书筛选。"),
]

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>汉字字形库 · 浏览</title>
<style>
  :root { --fg:#1c1c1e; --muted:#6b7280; --line:#e5e7eb; --bg:#fbfbfc; --accent:#8a1c1c; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font:14px/1.55 system-ui, -apple-system, "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; }
  header { padding:22px 24px 0; }
  h1 { font-size:20px; margin:0 0 6px; }
  .lede { color:var(--muted); margin:0 0 14px; max-width:70em; }
  .lede a { color:var(--accent); }
  nav { display:flex; gap:4px; border-bottom:1px solid var(--line); padding:0 24px; flex-wrap:wrap; }
  nav button { appearance:none; border:0; background:none; padding:9px 14px; cursor:pointer;
               font:inherit; color:var(--muted); border-bottom:2px solid transparent; }
  nav button[aria-selected="true"] { color:var(--fg); border-bottom-color:var(--accent); font-weight:600; }
  nav button .n { color:var(--muted); font-weight:400; font-size:12px; margin-left:5px; }
  main { padding:16px 24px 40px; }
  .panel[hidden] { display:none; }
  .toolbar { display:flex; gap:14px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
  .seg { display:inline-flex; border:1px solid var(--line); border-radius:7px; overflow:hidden; background:#fff; }
  .seg button { appearance:none; border:0; background:none; padding:6px 12px; cursor:pointer;
                font:inherit; color:var(--muted); }
  .seg button[aria-pressed="true"] { background:#f0eeee; color:var(--fg); font-weight:600; }
  input[type=search] { padding:6px 10px; border:1px solid var(--line); border-radius:7px;
                       font:inherit; background:#fff; min-width:210px; }
  select.era { padding:6px 10px; border:1px solid var(--line); border-radius:7px;
               font:inherit; background:#fff; color:var(--fg); }
  label.chk { display:inline-flex; gap:6px; align-items:center; color:var(--muted); cursor:pointer; }
  .count { color:var(--muted); margin-left:auto; }
  .layer-note { color:var(--muted); font-size:13px; margin:0 0 10px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(78px, 1fr)); gap:7px; }
  figure { margin:0; background:#fff; border:1px solid var(--line); border-radius:8px;
           padding:6px 5px 4px; text-align:center; }
  figure.flag { border-color:#d9a300; background:#fffdf4; }
  figure a { display:block; }
  figure img { width:100%; height:62px; object-fit:contain; display:block; }
  figcaption { font-size:11px; color:var(--muted); margin-top:3px; white-space:nowrap;
               overflow:hidden; text-overflow:ellipsis; }
  figcaption b { color:var(--fg); font-weight:600; }
  figcaption i { font-style:normal; color:#8a1c8a; }
  .empty { color:var(--muted); background:#fff; border:1px solid var(--line);
           border-radius:8px; padding:18px; max-width:60em; }
  .more { display:block; margin:16px auto; padding:8px 20px; border:1px solid var(--line);
          border-radius:8px; background:#fff; color:var(--muted); cursor:pointer; font:inherit; }
  .more:hover { color:var(--fg); border-color:#c9ccd2; }
  .more[hidden] { display:none; }
  .boot { color:var(--muted); padding:30px 0; }
  .extcard { background:#fff; border:1px solid var(--line); border-left:3px solid var(--accent);
             border-radius:8px; padding:16px 20px; max-width:62em; }
  .extcard p { margin:0 0 10px; }
  .extcard ul { margin:0 0 10px; padding-left:20px; color:var(--muted); }
  .extcard li { margin:3px 0; }
  .extcard b { color:var(--fg); }
  .extcard .why { color:var(--muted); font-size:12.5px; margin:0; }
  footer { padding:0 24px 28px; color:var(--muted); font-size:12px; }
  code { background:#f1f1f3; padding:1px 4px; border-radius:4px; }
</style>
</head>
<body>
<header>
  <h1>汉字字形库 · 浏览</h1>
  <p class="lede">
    古文字字形 SVG 只读预览。字形文件在 <code>glyphs/</code>，每个字形一条出处记录在
    <code>glyphs/provenance/&lt;书体&gt;.jsonl</code>。
    甲骨文字形来源为 Li, Qing-sheng &amp; Bian, Yu-lin,
    <a href="https://zenodo.org/records/22467946" target="_blank" rel="noopener">Oracle Bone Glyphs:
    Parametric Vector Dataset (v0.3)</a>（DOI 10.5281/zenodo.22467946），依
    <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a>
    使用：骨架与上游逐字节一致、未改动几何，轮廓层由本仓库脚本派生（同一许可）。
    篆书字形来自汉典（zdic.net）「书法」小篆实例，依其《服务条款》第四条以
    <a href="https://creativecommons.org/publicdomain/zero/1.0/" target="_blank" rel="noopener">CC0 1.0</a>
    释出。完整署名与改动声明见仓库 <code>THIRD_PARTY_NOTICES.md</code>。
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

  // 字形目录的前缀。页面有两种放法：
  //   仓库里的 viewer/index.html  → 字形在 ../glyphs/
  //   Actions 部署到站点根 index.html → 字形在 glyphs/
  // 用一个已知文件探测一次，之后所有图都用同一个前缀——
  // 每个图各试一遍的话，首屏就是几百个 404。
  var glyphBase = null;

  function detectBase() {
    return new Promise(function (resolve) {
      var probe = new Image();
      probe.onload = function () { resolve('glyphs/'); };
      probe.onerror = function () { resolve('../glyphs/'); };
      probe.src = 'glyphs/oracle/0001.svg';
    });
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
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
    var title = '#' + row.i + ' ' + (row.c || '（无对应现代汉字）') +
                '  U+' + (row.u || '—') + '  ' + (row.p || '') + '  [' + row.k + ']' +
                (row.t ? '  ' + row.t : '') +
                (row.s ? '  ' + row.s : '');
    return '<figure class="cell' + (row.flag ? ' flag' : '') + '" title="' + esc(title) + '">' +
           '<a href="' + url + '" target="_blank" rel="noopener">' +
           '<img loading="lazy" src="' + url + '" alt="' + esc(title) + '"></a>' +
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
              '<li>登记表：<a href="../' + esc(ex.registry) + '">' + esc(ex.registry) + '</a>' +
                  '　说明：<a href="../' + esc(ex.readme) + '">' + esc(ex.readme) + '</a></li>' +
            '</ul>' +
            '<p class="why">未收录的原因：上游的授权语句只覆盖「output fonts」，其 <code>glyphs/**</code> ' +
            '未被明确标记为受 OFL 约束；仓库根目录也没有 LICENSE 文件。' +
            '（上游随附的 <code>OFL.txt</code> 并非 SIL 官方 OFL 1.1 文本：第 1、2 条与官方逐字相同，' +
            '第 3–9 条相似度最高 0.344、第 10 条 0.602，官方第 5 条「不得按其他许可分发」缺失。）' +
            '详见 <a href="../THIRD_PARTY_NOTICES.md">THIRD_PARTY_NOTICES.md</a>。' +
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
      '<p class="layer-note">' + esc(meta[3]) + '</p>' +
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
      grid.insertAdjacentHTML('beforeend', slice.map(function (r) {
        return cellHTML(script, r, layer);
      }).join(''));
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
            "s": (row.get("source_book") or row.get("variant") or "").strip(),
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
    args = parser.parse_args(argv)

    repo_root: Path = args.repo_root.resolve()
    glyphs_root = repo_root / "glyphs"

    data: dict[str, list[dict]] = {}
    outline: dict[str, bool] = {}
    external: dict[str, dict] = {}
    total = 0

    # 只给「真的有这一层」的书体出标签页：没发布的层连 index.csv 都没有，
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
            .replace("__SCRIPTS__", json.dumps(
                # 说明里的字数用**实际条数**填，不写死——写死的数字迟早过期，
                # 而过期数字比没有数字更坏：读者会拿它当依据。
                [[s[0], s[1], s[2], s[3].format(n=len(data.get(s[0], [])))]
                 for s in active], ensure_ascii=False))
            .replace("__GENERATED__",
                     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))

    out_path = repo_root / "viewer" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8", newline="\n")

    print(f"写出     : {out_path}  ({out_path.stat().st_size} bytes)")
    print(f"字形总数 : {total}")
    for script, zh, _en, _note in active:
        rows = data[script]
        flag = sum(1 for r in rows if r["flag"])
        extra = "（有轮廓层）" if outline.get(script) else ""
        print(f"  {zh:<4} {len(rows):>5} 个，待复核 {flag} 个 {extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
