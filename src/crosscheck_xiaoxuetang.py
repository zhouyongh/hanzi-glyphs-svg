#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小学堂 × 漢典 楚系层的交叉比对。

用法::

    python src/crosscheck_xiaoxuetang.py --index tmp/xxt/chuwenzi/index.jsonl
                                           --out tmp/xxt/crosscheck

**比对锚点是「字形键」（字体号_PUA），不是字頭。** 理由：

- 漢典的 ``source_id`` 与小學堂的 ``font_id_PUA`` 是**同一套编号**
  （漢典 51–58 = 中研院楚系簡帛文字重文一…八）——两边同构，可逐键对齐；
- 小學堂的異體字是「標楷體外字集N」字体里的**槽位码位**（U+FBE2 之类，
  不是真实 Unicode 汉字），漢典的異體字是真 Unicode 汉字（弌 / 靝 / 兲）；
  两边没法按文本对齐；
- 字頭也不行：小學堂的楷書字頭有時是**私用區槽位**（实测 14% 的实例），
  漢典那边记的是異體字。

四类结果：

=================  ==========================================================
完全对上            字形键 + 出處簡號都一致
出處不一致          字形键一致、出處簡號两边列的不一样
现代字不一致        字形键一致，但两边记的现代字不同（漢典记異體字、小學堂记楷書字頭）
仅小学堂有          字形键在漢典里不存在（新增字形）
僅漢典有            字形键在小学堂这批抓取里没覆盖到
=================  ==========================================================

**「现代字不一致」不是错误**：層的键是「(现代字码位, 字形键)」，
同一个字形在漢典层同时挂着異體字与正字两条；小學堂给的是**楷書字頭（正字）**。
正字身份本身就是漢典层缺的那一条，所以这批要**新增**（unicode 不同，不撞键）。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_codes() -> list[str]:
    """已知文献标识（小學堂出處表簡稱 + 漢典 book_code）。"""
    codes: set[str] = set()
    for path, col in ((ROOT / "glyphs" / "chu" / "books_xxt.csv", "xxt_code"),
                      (ROOT / "glyphs" / "chu" / "books.csv", "code")):
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                code = (row.get(col) or "").strip()
                if code:
                    codes.add(code)
    return sorted(codes, key=len, reverse=True)


CODES = load_codes()


def strip_variant(v: str) -> str:
    """漢典 variant = 異體字（一个）+ 出處簡號 → 出處簡號。

    切分规则：**出處簡號 = 文獻標識 + 編號**，編號必以數字或點開頭。
    切點因此唯一確定。

    **坑：不能只取「最長的匹配標識」。** 標識表里既有「望1」也有「望」，
    出處簡號「望1卜」（望山一號墓的卜辭）用「望1」切，剩下「卜」不是編號；
    用「望」切，剩下「1卜」才是編號。所以要在**所有**能匹配的標識裡，
    挑「切完剩下的那截以數字或點開頭」的那個（同等長度取最長）。

    為什麼不能只看「已知標識前綴」：異體字本身也可能是漢字，而且可能**恰好**
    是一個文獻代號（異體字「上」+ 出處「帛乙6.4」= 「上帛乙6.4」）。
    """
    v = (v or "").strip()
    if not v:
        return ""
    for i in (0, 1):
        rest = v[i:]
        best = ""
        for c in CODES:
            if not rest.startswith(c):
                continue
            tail = rest[len(c):]
            if tail and not (tail[0].isdigit() or tail[0] == "."):
                continue
            if len(c) > len(best):
                best = c
        if best:
            return rest
    return v


def resolve_short(short: str) -> str:
    """小學堂出處簡號 → 文獻標識（最長前綴匹配）。"""
    best = ""
    for c in CODES:
        if short.startswith(c) and len(c) > len(best):
            best = c
    return best


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="小学堂 × 漢典 楚系层交叉比对")
    ap.add_argument("--index", required=True, type=Path, help="小学堂实例索引 index.jsonl")
    ap.add_argument("--zdic-index", type=Path, default=ROOT / "glyphs" / "chu" / "index.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "tmp" / "xxt" / "crosscheck")
    ap.add_argument("--sample", type=int, default=30, help="抽样多少个现代字列差异清单")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    # 漢典层：字形键 → 行
    z_by_shape: dict[str, list[dict]] = defaultdict(list)
    z_by_shape_short: dict[tuple[str, str], dict] = {}
    with args.zdic_index.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            short = strip_variant(row["variant"])
            row["_short"] = short
            z_by_shape[row["source_id"]].append(row)
            z_by_shape_short[(row["source_id"], short)] = row

    xxt = []
    with args.index.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            r["shape_key"] = "{}_{}".format(r.get("font_id", ""), r.get("pua", ""))
            xxt.append(r)

    matched, only_xxt, char_diff, src_diff = [], [], [], []
    for r in xxt:
        sid, short = r["shape_key"], r.get("source_short", "")
        zrow = z_by_shape_short.get((sid, short))
        if zrow is not None:
            matched.append((r, zrow))
            if r.get("modern_char") != zrow.get("modern_char"):
                char_diff.append((r, zrow))
            continue
        if sid in z_by_shape:
            src_diff.append((r, z_by_shape[sid]))
            continue
        only_xxt.append(r)

    xxt_shapes = {r["shape_key"] for r in xxt}
    only_z = [(sid, row) for sid, rows in z_by_shape.items()
              if sid not in xxt_shapes for row in rows]

    # 按现代字分组（现代字是「现代字码位 + 字形键」这对的另一半）
    by_char: dict[str, list[dict]] = defaultdict(list)
    for r in xxt:
        by_char[r.get("modern_char", "")].append(r)

    lines: list[str] = []
    lines.append("# 小学堂 × 漢典 楚系层交叉比对")
    lines.append("")
    lines.append(f"- 小学堂实例：**{len(xxt)}**（字形键 {len(xxt_shapes)} 个，"
                 f"字頭 {len(by_char)} 个）")
    lines.append(f"- 漢典层实例：**{len(z_by_shape_short)}**（字形键 {len(z_by_shape)} 个）")
    lines.append(f"- **完全对上**（字形键 + 出處簡號）：**{len(matched)}**")
    lines.append(f"- **现代字不一致**（字形键与出處都对上，但记的现代字不同）：**{len(char_diff)}**")
    lines.append(f"- **出處不一致**（字形键一致、出處簡號两边列的不一样）：**{len(src_diff)}**")
    lines.append(f"- **仅小学堂有**（字形键在漢典里不存在 → 新增字形）：**{len(only_xxt)}**")
    lines.append(f"- 僅漢典有（字形键在小学堂这批抓取里没覆盖到）：{len(only_z)}")
    lines.append("")
    lines.append("> 比对锚点 = **字形键**（字体号_PUA）。兩库的 `source_id` / `font_id_PUA`")
    lines.append("> 是同一套编号（漢典 51–58 = 中研院楚系簡帛文字重文一…八）。")
    lines.append("> **不用字頭对齐**：小學堂的異體字是「標楷體外字集N」的槽位码位")
    lines.append("> （U+FBE2 之类，不是真漢字），漢典的異體字是真 Unicode 汉字（弌/靝/兲）；")
    lines.append("> 小學堂的楷書字頭还有 14% 的实例是**私用區槽位**。")
    lines.append("")
    lines.append("## 现代字不一致的（抽样 %d 个现代字）" % args.sample)
    lines.append("")
    lines.append("> 這不是錯誤：層的键是「(现代字码位, 字形键)」。漢典层给同一个字形")
    lines.append("> 同时挂着**異體字**与**正字**两条；小學堂给的是**楷書字頭（正字）**。")
    lines.append("> 正字身份正是漢典层缺的那一条，所以这批**新增**（unicode 不同，不撞键）。")
    lines.append("")
    lines.append("| 小学堂字頭 | 小学堂出處 | 漢典 source_id | 漢典记的现代字 | 處置 |")
    lines.append("|---|---|---|---|---|")
    seen_chars: set[str] = set()
    for r, z in char_diff:
        ch = r.get("modern_char", "")
        if ch in seen_chars:
            continue
        seen_chars.add(ch)
        if len(seen_chars) > args.sample:
            break
        lines.append(f"| {ch or '（私用區槽位）'} | {r.get('source_short','')} | "
                     f"{z['source_id']} | {z.get('modern_char','')} | 新增正字身份 |")
    lines.append("")
    lines.append("## 出處不一致的（全部）")
    lines.append("")
    lines.append("| 字形键 | 小学堂出處 | 漢典出處 | 漢典现代字 |")
    lines.append("|---|---|---|---|")
    for r, zrows in src_diff:
        lines.append(f"| {r['shape_key']} | {r.get('source_short','')} | "
                     f"{'、'.join(sorted({z['_short'] for z in zrows}))} | "
                     f"{'、'.join(sorted({z.get('modern_char','') for z in zrows}))} |")
    lines.append("")
    lines.append("## 仅小学堂有（按文献分组，全部）")
    lines.append("")
    lines.append("| 文献 | 件数 |")
    lines.append("|---|---|")
    for k, n in Counter(resolve_short(r.get("source_short", "")) for r in only_xxt).most_common():
        lines.append(f"| {k or '（未解析）'} | {n} |")
    lines.append("")
    lines.append("## 逐字頭對照（按小学堂实例数前 40）")
    lines.append("")
    lines.append("| 字頭 | 实例 | 對上 | 现代字不同 | 僅小学堂 | 字形键 |")
    lines.append("|---|---|---|---|---|---|")
    m_by = Counter(r.get("modern_char", "") for r, _ in matched)
    c_by = Counter(r.get("modern_char", "") for r, _ in char_diff)
    o_by = Counter(r.get("modern_char", "") for r in only_xxt)
    s_by: dict[str, set[str]] = defaultdict(set)
    for r in xxt:
        s_by[r.get("modern_char", "")].add(r["shape_key"])
    for ch, n in sorted(Counter(r.get("modern_char", "") for r in xxt).items(),
                        key=lambda kv: -kv[1])[:40]:
        lines.append(f"| {ch or '（私用區槽位）'} | {n} | {m_by.get(ch,0)} | "
                     f"{c_by.get(ch,0)} | {o_by.get(ch,0)} | {len(s_by.get(ch,()))} |")
    (args.out / "crosscheck.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    with (args.out / "crosscheck.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for r, z in matched:
            fh.write(json.dumps({
                "kind": "matched", "shape_key": r["shape_key"],
                "xxt_source_short": r.get("source_short", ""),
                "xxt_zi_order": r.get("zi_order", ""),
                "xxt_modern_char": r.get("modern_char", ""),
                "xxt_modern_char_source": r.get("modern_char_source", ""),
                "xxt_modern_char_slot": r.get("modern_char_slot", ""),
                "zdic_source_id": z["source_id"], "zdic_source_short": z["_short"],
                "zdic_modern_char": z.get("modern_char", ""),
                "zdic_source_book": z.get("source_book", ""),
                "zdic_file": z.get("file", ""),
            }, ensure_ascii=False, sort_keys=True) + "\n")
        for r, zrows in src_diff:
            fh.write(json.dumps({
                "kind": "source_short_diff", "shape_key": r["shape_key"],
                "xxt_source_short": r.get("source_short", ""),
                "xxt_modern_char": r.get("modern_char", ""),
                "zdic_source_shorts": sorted({z["_short"] for z in zrows}),
                "zdic_modern_chars": sorted({z.get("modern_char", "") for z in zrows}),
            }, ensure_ascii=False, sort_keys=True) + "\n")
        for r in only_xxt:
            fh.write(json.dumps({
                "kind": "only_xxt", "shape_key": r["shape_key"],
                "xxt_source_short": r.get("source_short", ""),
                "xxt_zi_order": r.get("zi_order", ""),
                "xxt_modern_char": r.get("modern_char", ""),
                "xxt_modern_char_source": r.get("modern_char_source", ""),
                "literature": resolve_short(r.get("source_short", "")),
            }, ensure_ascii=False, sort_keys=True) + "\n")
        for sid, row in only_z:
            fh.write(json.dumps({
                "kind": "only_zdic", "zdic_source_id": sid,
                "zdic_source_short": row["_short"],
                "zdic_modern_char": row.get("modern_char", ""),
                "zdic_source_book": row.get("source_book", ""),
            }, ensure_ascii=False, sort_keys=True) + "\n")

    print("\n".join(lines[:12]))
    print(f"\n报告：{args.out / 'crosscheck.md'}")
    print(f"明细：{args.out / 'crosscheck.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
