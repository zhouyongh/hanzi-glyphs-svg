#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""算清楚「这一批到底要抓哪些位图」——**按层的选取规则先筛，再扣掉漢典层已有的**。

为什么要有这个脚本
------------------

小學堂一个库动辄三万多个实例（楚系 37,204 个 = 8 套「重文」字体 × 同一批摹本），
但**层不是照单全收**：层的规则是「每个 (现代字, 出土文献) 最多 1 条、每个现代字最多 5 条」
（漢典层当年就是这么选的，见 ``src/fetch_zdic_glyphs.py --max-per-book 1 --per-char 5``）。
按规则筛完只剩一万来个桶，再扣掉**漢典层已经有的字形**（那一半直接沿用漢典的矢量件，
不必重描摹），真正要抓的位图往往只有全部字形的两成。

这一步直接决定抓取要跑几天：全抓 37,180 张 × 2 s ≈ 20 小时／路，
按规则筛完 + 扣掉漢典已有的是 5,952 张 ≈ 3.3 小时／路（双路 1.7 小时）。

选取规则（两个候选，都是确定性的）
----------------------------------

- **R1 字体号升序**（重文一 → 重文八）：确定，但武断——等于默认「第一套字体最好」。
- **R2 漢典字形优先**：同一个桶里如果有一个字形键在漢典层已经有了，
  就选它——合并后那一条直接沿用漢典的矢量件，层里不会出现
  「同一条被换成描摹件」的不一致；桶里没有漢典对应时才退回 R1。

实测（楚系）：R1 选中 11,181 个字形、其中漢典已有 4,679；
R2 选中 11,179、其中漢典已有 **5,227**——R2 多保住 548 个已有字形，
而且这 548 个**不用抓位图也不用描摹**。默认用 R2。

用法
----

::

    python src/plan_xxt_fetch.py --db chuwenzi --layer chu \\
        --zdic-manifest tmp/zdic/chu-rebuilt/manifest.json \\
        --out-keys tmp/xxt/chuwenzi/fetch-keys.txt \\
        --out-list tmp/xxt/chuwenzi/fetch-list.tsv

产出
----

- ``--out-keys``：一个字形键一行（``字体号_码位``），给
  ``src/fetch_xiaoxuetang_glyphs.py --stage images --shape-list`` 用；
- ``--out-list``：给 PowerShell 取图器用的清单（``码位\\t字体名\\t落盘路径``）；
- ``--out-selection``：逐桶的选取记录（JSONL），Phase 4 合并时**按同一份选择**走，
  免得抓的时候选一套、合并的时候又选一套。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from build_xxt_manifest import (  # noqa: E402
    load_books_xxt,
    load_jsonl,
    norm_cp,
    resolve_literature,
    usable_modern_char,
)

# 库 → 层名（與 run_xxt_pipeline.py 的 DBS 對齊）
DB_LAYER = {
    "chuwenzi": "chu",
    "qinwenzi": "qinwenzi",
    "chuanchao": "chuanchao",
    "xiaozhuan": "xiaozhuan",
    "jiaguwen": "oracle",
    "jinwen": "bronze",
    "lishu": "clerical",
}


def load_zdic(manifest: Path) -> tuple[set[str], dict[str, str], dict[str, set[str]]]:
    """讀漢典层的合并清单 → (字形键集合, 「现代字码位+文献代号」→ 字形键, 字形键 → 现代字码位集合)。

    清单里每条都有 ``source_id``（= 字形键，``字体号_码位``）与 ``book_code``
    （= 文献代号，与层的 books.csv 同一粒度）。这是「漢典层已经有了什么」的唯一权威来源。
    """
    shapes: set[str] = set()
    buckets: dict[str, str] = {}
    shape_chars: dict[str, set[str]] = defaultdict(set)
    if not manifest.is_file():
        return shapes, buckets, shape_chars
    data = json.loads(manifest.read_text(encoding="utf-8"))
    for g in data.get("glyphs", []):
        sid = str(g.get("source_id") or "").strip()
        if not sid:
            continue
        shapes.add(sid)
        code = str(g.get("unicode") or "").strip()
        book = str(g.get("book_code") or "").strip()
        if code:
            shape_chars[sid].add(code)
        if code and book:
            buckets.setdefault(f"{code}\t{book}", sid)
    return shapes, buckets, shape_chars


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="算出要抓哪些位图")
    ap.add_argument("--db", required=True, help="库名（chuwenzi / jinwen / …）")
    ap.add_argument("--layer", default=None, help="层名（默认按库名推断）")
    ap.add_argument("--index", type=Path, default=None,
                    help="实例索引（默认 tmp/xxt/<库>/index.jsonl）")
    ap.add_argument("--books-xxt", type=Path, default=None,
                    help="出處表登记表（默认 glyphs/<层>/books_xxt.csv，没有就用 books.csv）")
    ap.add_argument("--books", type=Path, default=None,
                    help="层的文献对照表（默认 glyphs/<层>/books.csv）")
    ap.add_argument("--zdic-manifest", type=Path, default=None,
                    help="漢典层的合并清单（tmp/zdic/<层>-rebuilt/manifest.json）")
    ap.add_argument("--zdic-index", type=Path, default=None,
                    help="漢典层的 index.csv（没有清单时用它取字形键集合）")
    ap.add_argument("--identity-map", type=Path, default=None,
                    help="私用區身份反查表（默认 tmp/xxt/<库>/identity_map.jsonl）")
    ap.add_argument("--font-allow", default=None,
                    help="只收字体名以此开头的实例（逗号分隔）。"
                         "**书体由字体决定**：隸變库里「中研院秦系簡牘」是秦系字形")
    ap.add_argument("--rule", choices=("R1", "R2"), default="R2",
                    help="R1 字体号升序 / R2 漢典字形优先（默认 R2）")
    ap.add_argument("--per-char", type=int, default=5,
                    help="每个现代字最多留几条（与漢典层 --per-char 5 同口径）")
    ap.add_argument("--img-dir", type=Path, default=None,
                    help="位图落盘目录（默认 tmp/xxt/<库>/img）")
    ap.add_argument("--out-keys", type=Path, default=None, help="输出：字形键清单")
    ap.add_argument("--out-list", type=Path, default=None,
                    help="输出：PowerShell 取图清单（码位\\t字体名\\t路径）")
    ap.add_argument("--out-selection", type=Path, default=None,
                    help="输出：逐桶选取记录（JSONL）")
    ap.add_argument("--dry-run", action="store_true", help="只算不写")
    args = ap.parse_args(argv)

    layer = args.layer or DB_LAYER.get(args.db)
    if not layer:
        raise SystemExit(f"不知道 {args.db} 归哪一层，用 --layer 指定")
    out_dir = ROOT / "tmp" / "xxt" / args.db
    index_path = args.index or (out_dir / "index.jsonl")
    books_csv_path = args.books or (ROOT / "glyphs" / layer / "books.csv")
    books_xxt_path = args.books_xxt
    if books_xxt_path is None:
        candidate = ROOT / "glyphs" / layer / "books_xxt.csv"
        books_xxt_path = candidate if candidate.is_file() else books_csv_path
    identity_path = args.identity_map or (out_dir / "identity_map.jsonl")
    img_dir = args.img_dir or (out_dir / "img")

    if not index_path.is_file():
        raise SystemExit(f"实例索引不存在：{index_path}")

    books_rows, _ = load_books_xxt(books_xxt_path)
    if not books_rows:
        raise SystemExit(f"出處表登记表读不出来：{books_xxt_path}")

    identity_map: dict[int, str] = {}
    if identity_path.is_file():
        for rec in load_jsonl(identity_path):
            if rec.get("modern_char"):
                identity_map[int(rec["zi_order"])] = rec["modern_char"]

    z_shapes, z_buckets, z_shape_chars = (load_zdic(args.zdic_manifest)
                                           if args.zdic_manifest else (set(), {}, {}))
    if args.zdic_index and args.zdic_index.is_file() and not z_shapes:
        with args.zdic_index.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("source_id"):
                    z_shapes.add(row["source_id"])

    font_allow = [f.strip() for f in (args.font_allow or "").split(",") if f.strip()]

    instances = load_jsonl(index_path)
    stats = Counter()
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    per_char_buckets: dict[str, list[tuple[str, str]]] = defaultdict(list)

    # ---- 身份：一条实例的现代字身份从哪来 ----
    #
    # ① 站点直接给出真漢字（標楷體 / 北師大說文小篆）→ 用它；
    # ② 反查表（底本页.行 / 說文小篆槽位）→ 用它；
    # ③ **字形键**：这个字形（字体号+槽位）在漢典层已有，而漢典只给了**一个**
    #    现代字 → 那个字就是它的身份（同一套字体槽位 = 同一个字）。
    #    多义时（漢典同一字形最多有 11 个现代字）不猜，走 ④；
    # ④ 都不成立 → 临时身份：槽位（``modern_char_slot``）就是唯一线索。
    #
    # **为什么 ③ 要「只留一个」**：一个槽位在漢典层可能挂着好几个现代字
    # （正字 + 異體字 + 重文），那是**字形身份**的歧义，不是这一条的歧义——
    # 多义时宁可留临时身份，也不要替字頭认一个可能错的字。
    for inst in instances:
        if font_allow and not any(inst.get("font", "").startswith(f) for f in font_allow):
            stats["其他字体"] += 1
            continue
        short = inst.get("source_short", "")
        lit, book = resolve_literature(short, books_rows)
        if not lit or book is None:
            stats["出處對不上表"] += 1
            continue
        code = str(book.get("zdic_code", "") or "").strip() or lit
        shape_key = f"{inst.get('font_id','')}_{inst['pua']}"
        ch = inst.get("modern_char", "")
        if usable_modern_char(ch):
            ident, conf = norm_cp(f"{ord(ch):04X}"), "xxt-head"
        else:
            ch = identity_map.get(inst.get("zi_order"), "")
            if usable_modern_char(ch):
                ident, conf = norm_cp(f"{ord(ch):04X}"), "reverse-lookup"
                stats["身份反查補回"] += 1
            else:
                zs = z_shape_chars.get(shape_key) or set()
                if len(zs) == 1:
                    ident, conf = next(iter(zs)), "shape-key"
                    stats["身份由字形键定"] += 1
                else:
                    ident = "slot:" + (inst.get("modern_char_slot") or shape_key)
                    conf = "pua-slot"
                    stats["臨時身份"] += 1
        inst["_ident"] = ident
        inst["_conf"] = conf
        buckets[(ident, code)].append(inst)
        stats["实例"] += 1

    # 每个 (现代字, 文献) 只留 1 条；每个现代字最多 --per-char 条。
    # 桶序按**页面顺序**（字頭號 → 出處簡號 → 字体号 → 码位），与漢典层
    # 「桶序用页面上的原始顺序」同口径。
    def inst_key(i: dict) -> tuple:
        return (int(i.get("zi_order") or 0), str(i.get("source_short", "")),
                int(i.get("font_id") or 999), str(i.get("pua", "")))

    ordered = sorted(buckets.items(), key=lambda kv: min(inst_key(i) for i in kv[1]))
    kept_buckets: list[tuple[tuple[str, str], list[dict]]] = []
    for bkey, lst in ordered:
        ident, code = bkey
        # 漢典层已经有「同一个身份 + 同一篇文献」→ 这个桶**不新增**：
        # 层里那一条沿用漢典的矢量件（重叠处漢典优先）。
        if ident in z_buckets and f"{ident}\t{code}" in z_buckets:
            stats["漢典已覆盖该桶"] += 1
            continue
        if len(per_char_buckets[ident]) >= args.per_char:
            stats["超出每字上限"] += 1
            continue
        kept_buckets.append((bkey, lst))
        per_char_buckets[ident].append(bkey)

    # 选一个实例（= 一个字形）代表这个桶
    selection: list[dict] = []
    need_bitmaps: dict[str, dict] = {}
    for (ident, code), lst in kept_buckets:
        lst = sorted(lst, key=inst_key)
        known = [i for i in lst
                 if f"{i.get('font_id','')}_{i['pua']}" in z_shapes]
        if args.rule == "R2" and known:
            pick = known[0]
            reason = "R2-漢典已有此字形（沿用矢量件）"
        else:
            pick = lst[0]
            reason = ("R1-字体号升序" if args.rule == "R1"
                      else ("R2-桶内無漢典字形，退回字体号升序" if known
                            else "R2-桶内無漢典字形"))
        shape_key = f"{pick.get('font_id','')}_{pick['pua']}"
        in_zdic = shape_key in z_shapes
        rec = {
            "identity": ident, "identity_confidence": pick.get("_conf", ""),
            "modern_char": pick.get("modern_char", ""),
            "book_code": code, "shape_key": shape_key,
            "font_id": pick.get("font_id", ""), "font": pick.get("font", ""),
            "pua": pick["pua"], "source_short": pick.get("source_short", ""),
            "zi_order": pick.get("zi_order"),
            "bucket_size": len(lst), "rule": reason,
            "zdic_has_shape": in_zdic,
            "zdic_has_bucket": f"{ident}\t{code}" in z_buckets,
        }
        selection.append(rec)
        if not in_zdic:
            need_bitmaps[shape_key] = pick
        stats["选中桶"] += 1
        if in_zdic:
            stats["沿用漢典矢量件"] += 1

    print(f"=== {args.db} → 层 {layer}")
    print(f"  索引实例 {len(instances):,}；计入分桶 {stats['实例']:,}"
          f"（其他字体 {stats['其他字体']:,}、出處對不上表 {stats['出處對不上表']:,}）")
    print(f"  身份：反查補回 {stats['身份反查補回']:,}、"
          f"字形键定 {stats['身份由字形键定']:,}、"
          f"臨時身份 {stats['臨時身份']:,}")
    print(f"  (身份, 文献) 桶 {len(buckets):,} → 漢典已覆盖 {stats['漢典已覆盖该桶']:,}、"
          f"每字上限砍掉 {stats['超出每字上限']:,} → 留 {len(kept_buckets):,} 条")
    print(f"  规则 {args.rule}：选中 {len(selection):,} 条，"
          f"其中字形在漢典层已有 {stats['沿用漢典矢量件']:,} 条（不用抓位图）")
    all_shapes = {f"{i.get('font_id','')}_{i['pua']}" for i in instances}
    print(f"  **真正要抓的位图 {len(need_bitmaps):,} 张**"
          f"（全部唯一字形 {len(all_shapes):,} 张的 {len(need_bitmaps)/max(len(all_shapes),1):.1%}）")

    if args.dry_run:
        return 0

    if args.out_keys:
        args.out_keys.parent.mkdir(parents=True, exist_ok=True)
        args.out_keys.write_text("".join(f"{k}\n" for k in sorted(need_bitmaps)),
                                 encoding="utf-8")
        print(f"  → 字形键清单：{args.out_keys}")
    if args.out_list:
        args.out_list.parent.mkdir(parents=True, exist_ok=True)
        with args.out_list.open("w", encoding="utf-8", newline="\n") as fh:
            for key in sorted(need_bitmaps):
                v = need_bitmaps[key]
                dest = (img_dir / f"{key}.png").resolve()
                fh.write(f"{v['pua']}\t{v['font']}\t{dest}\n")
        print(f"  → 取图清单：{args.out_list}")
    if args.out_selection:
        args.out_selection.parent.mkdir(parents=True, exist_ok=True)
        with args.out_selection.open("w", encoding="utf-8", newline="\n") as fh:
            for rec in selection:
                fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"  → 选取记录：{args.out_selection}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
