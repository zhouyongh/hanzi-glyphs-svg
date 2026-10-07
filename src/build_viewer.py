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
     "已收录 1,203 个字形，源自公开数据集（CC BY 4.0）。"),
    ("bronze", "金文", "Bronze script",
     "尚未收录。现有开放来源里没有许可干净、成规模的矢量字形库。"),
    ("seal", "篆书", "Seal script",
     "尚未收录。Unicode 18.0 已编码篆书区（U+3D000–U+3FC3F，11,328 码位），"
     "字形需从公版《说文》刻本自行描摹。"),
    ("clerical", "隶书", "Clerical script",
     "尚未收录。可用的开放来源基本是位图，需人工描摹。"),
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
  label.chk { display:inline-flex; gap:6px; align-items:center; color:var(--muted); cursor:pointer; }
  .count { color:var(--muted); margin-left:auto; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(78px, 1fr)); gap:7px; }
  figure { margin:0; background:#fff; border:1px solid var(--line); border-radius:8px;
           padding:6px 5px 4px; text-align:center; }
  figure.flag { border-color:#d9a300; background:#fffdf4; }
  figure a { display:block; }
  figure img { width:100%; height:62px; object-fit:contain; display:block; }
  figcaption { font-size:11px; color:var(--muted); margin-top:3px; white-space:nowrap;
               overflow:hidden; text-overflow:ellipsis; }
  figcaption b { color:var(--fg); font-weight:600; }
  .empty { color:var(--muted); background:#fff; border:1px solid var(--line);
           border-radius:8px; padding:18px; max-width:60em; }
  footer { padding:0 24px 28px; color:var(--muted); font-size:12px; }
  code { background:#f1f1f3; padding:1px 4px; border-radius:4px; }
</style>
</head>
<body>
<header>
  <h1>汉字字形库 · 浏览</h1>
  <p class="lede">
    古文字字形 SVG 只读预览。字形文件在 <code>glyphs/</code>，每个字形一条出处记录在
    <code>glyphs/provenance.jsonl</code>。
    甲骨文字形来源为
    <a href="https://zenodo.org/records/22467946" target="_blank" rel="noopener">Zenodo 10.5281/zenodo.22467946</a>，
    依 <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a>
    使用，署名见仓库 <code>THIRD_PARTY_NOTICES.md</code>。
  </p>
</header>
<nav id="tabs" role="tablist"></nav>
<main id="panels"></main>
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

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function svgURL(script, file, layer) {
    return '../glyphs/' + script + '/' + (layer === 'outline' ? 'outline/' : '') + file;
  }

  function cellHTML(script, row, layer) {
    var url = svgURL(script, row.file, layer);
    var title = '#' + row.i + ' ' + (row.c || '（无对应现代汉字）') +
                '  U+' + (row.u || '—') + '  ' + (row.p || '') + '  [' + row.k + ']';
    return '<figure class="cell' + (row.flag ? ' flag' : '') + '" title="' + esc(title) + '">' +
           '<a href="' + url + '" target="_blank" rel="noopener">' +
           '<img loading="lazy" src="' + url + '" alt="' + esc(title) + '"></a>' +
           '<figcaption><b>' + esc(row.i) + '</b> ' + esc(row.c || '—') + '</figcaption>' +
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
    panel.innerHTML =
      '<div class="toolbar">' + seg +
        '<input type="search" placeholder="搜索：编号 / 现代字 / 码位 / 拼音" aria-label="搜索字形">' +
        '<label class="chk"><input type="checkbox"> 只看待复核</label>' +
        '<span class="count"></span>' +
      '</div><div class="grid"></div>';

    var layer = 'skeleton';
    var grid = panel.querySelector('.grid');
    var countEl = panel.querySelector('.count');
    var search = panel.querySelector('input[type=search]');
    var onlyFlag = panel.querySelector('input[type=checkbox]');

    function render() {
      var q = search.value.trim().toLowerCase();
      var shown = rows.filter(function (r) {
        if (onlyFlag.checked && !r.flag) { return false; }
        if (!q) { return true; }
        return (r.i + ' ' + r.c + ' ' + r.u + ' ' + r.p).toLowerCase().indexOf(q) >= 0;
      });
      grid.innerHTML = shown.map(function (r) { return cellHTML(script, r, layer); }).join('');
      countEl.textContent = shown.length === rows.length
        ? '共 ' + rows.length + ' 个字形'
        : shown.length + ' / ' + rows.length + ' 个字形';
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
    render();
    return panel;
  }

  SCRIPTS.forEach(function (s, idx) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.setAttribute('role', 'tab');
    btn.setAttribute('aria-selected', String(idx === 0));
    btn.setAttribute('aria-controls', 'panel-' + s[0]);
    btn.innerHTML = esc(s[1]) + '<span class="n">' + ((DATA[s[0]] || []).length) + '</span>';
    btn.addEventListener('click', function () {
      Array.prototype.forEach.call(tabs.querySelectorAll('button'), function (b) {
        b.setAttribute('aria-selected', String(b === btn));
      });
      Array.prototype.forEach.call(panels.querySelectorAll('.panel'), function (p) {
        p.hidden = (p.id !== 'panel-' + s[0]);
      });
    });
    tabs.appendChild(btn);

    var panel = buildPanel(s[0]);
    panel.hidden = (idx !== 0);
    panels.appendChild(panel);
  });
})();
</script>
</body>
</html>
"""


def load_rows(index_path: Path) -> list[dict]:
    """把一处 index.csv 压成浏览页要用的紧凑记录。"""
    with index_path.open("r", encoding="utf-8", newline="") as handle:
        raw = list(csv.DictReader(handle))
    rows = []
    for row in raw:
        confidence = (row.get("identity_confidence") or "").strip()
        rows.append({
            "i": row["glyph_id"],
            "c": (row.get("modern_char") or "").strip(),
            "u": (row.get("unicode") or "").strip(),
            "p": (row.get("pinyin") or "").strip(),
            "k": confidence or "unidentified",
            "flag": 0 if confidence == "high" else 1,
            "file": row["file"],
        })
    rows.sort(key=lambda r: int(r["i"]))
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生成静态浏览页")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    repo_root: Path = args.repo_root.resolve()
    glyphs_root = repo_root / "glyphs"

    data: dict[str, list[dict]] = {}
    outline: dict[str, bool] = {}
    total = 0

    for script, zh, _en, _note in SCRIPTS:
        index_path = glyphs_root / script / "index.csv"
        if not index_path.is_file():
            data[script] = []
            outline[script] = False
            continue
        rows = load_rows(index_path)
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
    payload = json.dumps(payload_obj, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c")  # 数据里若出现 </script> 不会截断脚本

    page = (TEMPLATE
            .replace("__DATA__", payload)
            .replace("__SCRIPTS__", json.dumps(
                [[s[0], s[1], s[2], s[3]] for s in SCRIPTS], ensure_ascii=False))
            .replace("__GENERATED__",
                     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))

    out_path = repo_root / "viewer" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8", newline="\n")

    print(f"写出     : {out_path}  ({out_path.stat().st_size} bytes)")
    print(f"字形总数 : {total}")
    for script, zh, _en, _note in SCRIPTS:
        rows = data[script]
        flag = sum(1 for r in rows if r["flag"])
        extra = "（有轮廓层）" if outline.get(script) else ""
        print(f"  {zh:<4} {len(rows):>5} 个，待复核 {flag} 个 {extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
