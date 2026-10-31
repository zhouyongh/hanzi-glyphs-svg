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
    LAYER_BUCKET_BY,
    LAYER_RULES,
    bucket_of_zdic_row,
    era_vocab_of,
    load_books_xxt,
    load_jsonl,
    norm_cp,
    resolve_literature,
    split_source_fields,
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


def load_zdic(manifest: Path, mode: str = "book", bucket_by: str = "doc") -> tuple[set[str], dict[str, str],
                                                                          dict[str, set[str]], dict[str, int]]:
    """讀漢典层的合并清单 → (字形键集合, 「现代字码位+桶键」→ 字形键,
    字形键 → 现代字码位集合, 现代字码位 → 层里已有条数)。

    清单里每条都有 ``source_id``（= 字形键，``字体号_码位``）与 ``book_code``
    （= 文献代号，与层的 books.csv 同一粒度）。这是「漢典层已经有了什么」的唯一权威来源。

    桶键按**层自己的分桶维度**算（``bucket_of_zdic_row``）：金文/隸書层按**时代**、
    甲骨层按**字形键**、文献分桶的层按**文献代号**。
    **写死成文献代号是不行的**——金文层的桶键是时代，桶键对不上，
    「漢典已覆盖该桶」恒为 0，计划会多选好几千条（实测 3,484 → 6,245）。

    最后一项（每字已有条数）**必须一起取**：每字上限是整层口径，
    漏了它就会算成「层里一个都没有」，上限松一档，合并后超限。
    """
    shapes: set[str] = set()
    buckets: dict[str, str] = {}
    shape_chars: dict[str, set[str]] = defaultdict(set)
    per_char: dict[str, int] = defaultdict(int)
    if not manifest.is_file():
        return shapes, buckets, shape_chars, per_char
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
            per_char[code] += 1
        bucket = bucket_of_zdic_row(g, mode, bucket_by)
        if code and bucket:
            buckets.setdefault(f"{code}\t{bucket}", sid)
    return shapes, buckets, shape_chars, per_char


def load_zdic_index(index_path: Path, mode: str, bucket_by: str = "doc") -> tuple[set[str], dict[str, str],
                                                                                  dict[str, set[str]], dict[str, int]]:
    """讀**现有层**的 index.csv → (字形键集合, 「现代字码位+桶键」→ 字形键,
    字形键 → 现代字码位集合, 现代字码位 → 层里已有条数)。

    现有层的 index.csv 就是「这一层已经有了什么」的权威来源：
    ``source_id`` 是字形键（``字体号_码位``，**两库槽位同构**），
    ``period`` / ``source_book`` 是分桶维度（见 ``LAYER_RULES``）。

    最后一项（每字已有条数）是**每字上限**的起点：上限是**整层**的口径，
    不是某一来源的口径——合并后一个字的条数不能超过现有层给它的上限。
    """
    shapes: set[str] = set()
    buckets: dict[str, str] = {}
    shape_chars: dict[str, set[str]] = defaultdict(set)
    per_char: dict[str, int] = defaultdict(int)
    with index_path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            sid = (row.get("source_id") or "").strip()
            code = (row.get("unicode") or "").strip()
            if code:
                per_char[code] += 1
            if not sid:
                continue
            shapes.add(sid)
            if not code:
                continue
            shape_chars[sid].add(code)
            bucket = bucket_of_zdic_row(row, mode, bucket_by)
            buckets.setdefault(f"{code}\t{bucket}", sid)
    return shapes, buckets, shape_chars, per_char


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
    ap.add_argument("--bucket", choices=("book", "era", "oracle"), default=None,
                    help="分桶维度：**与现有层同一套口径**（默认按层定，"
                         "见 build_xxt_manifest.LAYER_RULES）。"
                         "book = 每 (现代字, 文献) 1 条；"
                         "era = 每 (现代字, 时代) 1 条（clerical / bronze 层）；"
                         "oracle = 每 (现代字, 著錄號+組) 1 条（甲骨层）")
    ap.add_argument("--per-char", type=int, default=None,
                    help="每个现代字最多留几条（默认按层定：chu/傳抄/秦系/小篆 5，"
                         "clerical 6，bronze 8，oracle 8）")
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
    # 分桶维度与每字上限：**按现有层的实测口径**，不另定一套。
    rule_bucket, rule_per_char = LAYER_RULES.get(layer, ("book", 5))
    mode = args.bucket or rule_bucket
    per_char = args.per_char if args.per_char is not None else rule_per_char
    # 桶键按文献算还是按字形算：甲骨层按字形（同一著錄下可以有多条摹本）。
    bucket_by = LAYER_BUCKET_BY.get(layer, "doc")
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
        # 时代 / 著錄分桶**不靠出處表**（隸變库的出處表只列 31 种，
        # 靠它分桶会把九成实例丢掉）；文献分桶才必须要表。
        if mode == "book":
            raise SystemExit(f"出處表登记表读不出来：{books_xxt_path}")
        books_rows = {}

    identity_map: dict[int, str] = {}
    if identity_path.is_file():
        for rec in load_jsonl(identity_path):
            if rec.get("modern_char"):
                identity_map[int(rec["zi_order"])] = rec["modern_char"]

    z_shapes, z_buckets, z_shape_chars, z_per_char = (
        load_zdic(args.zdic_manifest, mode, bucket_by)
        if args.zdic_manifest else (set(), {}, {}, {}))
    if args.zdic_index and args.zdic_index.is_file() and not z_shapes:
        # 现有层的 index.csv：字形键 + 分桶维度 + 字形→现代字 + 每字已有条数，
        # 四样都是「这一层已经有了什么」的权威来源。
        z_shapes, z_buckets, z_shape_chars, z_per_char = load_zdic_index(
            args.zdic_index, mode, bucket_by)
    # 时代词表从现有层的 period 列取——两边用同一张表，才谈得上「规则统一」。
    era_vocab = era_vocab_of(args.zdic_index) if mode == "era" else []

    font_allow = [f.strip() for f in (args.font_allow or "").split(",") if f.strip()]

    instances = load_jsonl(index_path)
    stats = Counter()
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    per_char_buckets: dict[str, list[tuple[str, str]]] = defaultdict(list)
    # 每字上限是**整层**的口径：现有层已经给这个字几条，小學堂这边只能在剩下的额度里加。
    z_used = dict(z_per_char)
    # 层上限 = max(来源上限, 现有层每字的最大条数)——
    # 取大值是为了**不动已有记录**（甲骨层 JGW 与漢典两批叠起来每字最多 10 条，
    # 若按 8 算就得删掉旧记录），取来源上限是为了让新来源与旧来源同口径。
    layer_cap = max(per_char, max(z_used.values()) if z_used else 0)

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
        shape_key = f"{inst.get('font_id','')}_{inst['pua']}"
        if mode == "book":
            lit, book = resolve_literature(short, books_rows)
            if not lit or book is None:
                stats["出處對不上表"] += 1
                continue
            out_code = str(book.get("zdic_code", "") or "").strip() or lit
            bucket_code = out_code
        else:
            # **时代 / 著錄分桶**：桶键直接从簡號拆出来，不依赖出處表——
            # 隸變库的出處表只列 31 种，靠它分桶会把九成实例丢掉。
            doc, number, era, bucket_code = split_source_fields(short, mode, era_vocab)
            lit = doc
            book = {"code": doc, "corpus_full": doc, "zdic_code": doc}
            out_code = doc
        # **桶键按字形算还是按文献算**：甲骨层按字形——同一著錄下可以有多条摹本，
        # 按文献分桶会把它们并成一条（等于把合法的「一字多摹本」当成重复丢掉）。
        # 出處（book_code）与桶键分开记：桶键只管「一个桶留一条」，
        # 出處还得原样写进层里，读者才知道这条字形是从哪件东西上摹下来的。
        if bucket_by == "shape":
            bucket_code = shape_key
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
        inst["_out_code"] = out_code
        buckets[(ident, bucket_code)].append(inst)
        stats["实例"] += 1

    # 每个 (现代字, 桶键) 只留 1 条；每个现代字最多 --per-char 条。
    # 桶序按**页面顺序**（字頭號 → 出處簡號 → 字体号 → 码位），与漢典层
    # 「桶序用页面上的原始顺序」同口径。
    def inst_key(i: dict) -> tuple:
        return (int(i.get("zi_order") or 0), str(i.get("source_short", "")),
                int(i.get("font_id") or 999), str(i.get("pua", "")))

    ordered = sorted(buckets.items(), key=lambda kv: min(inst_key(i) for i in kv[1]))
    kept_buckets: list[tuple[tuple[str, str], list[dict]]] = []
    for bkey, lst in ordered:
        ident, bucket_code = bkey
        # 漢典层已经有「同一个身份 + 同一个桶」→ 这个桶**不新增**：
        # 层里那一条沿用漢典的矢量件（重叠处漢典优先）。
        if f"{ident}\t{bucket_code}" in z_buckets:
            stats["漢典已覆盖该桶"] += 1
            continue
        # **两条上限都要守**：
        #  ① 这一批自己每字不超过**来源上限**——批次不能自己堆出超过上限的条数
        #     （体检查的就是这一条：「批次「小学堂 …」有 N 个字超过每字上限 8」）；
        #  ② 合并后每字不超过**整层上限**（= max(来源上限, 现有层每字最大条数)），
        #     现有层已有的条数**先占额度**。
        if len(per_char_buckets[ident]) >= per_char:
            stats["超出来源每字上限"] += 1
            continue
        if z_used.get(ident, 0) + len(per_char_buckets[ident]) >= layer_cap:
            stats["超出每字上限"] += 1
            continue
        kept_buckets.append((bkey, lst))
        per_char_buckets[ident].append(bkey)

    # 选一个实例（= 一个字形）代表这个桶
    selection: list[dict] = []
    need_bitmaps: dict[str, dict] = {}

    def pair_known(shape_key: str, ident: str) -> bool:
        """漢典层**已经有这一对**（现代字, 字形）吗？

        **判据必须落到「这一对键」上，不能只看「这个字形在不在漢典」。**
        同一个字形在漢典层可能挂着好几个现代字（正字 + 異體字 + 重文，
        实测最多 11 个）。小學堂的楷書字頭给的是**正字**——
        那一对（正字, 字形）在漢典层**没有**，这就是「小學堂補缺口」的那一条。
        只看「字形在不在」就跳过抓图，这一类会**整条漏掉**。
        临时身份（槽位）没有码位可比，一律按「没有」处理。
        """
        if ident.startswith("slot:"):
            return False
        return (shape_key in z_shapes
                and ident in (z_shape_chars.get(shape_key) or set()))

    for (ident, bucket_code), lst in kept_buckets:
        lst = sorted(lst, key=inst_key)
        # 优先挑「漢典层已有这一对（现代字, 字形）」的实例——那一条不用再抓位图。
        known = [i for i in lst
                 if pair_known(f"{i.get('font_id','')}_{i['pua']}", ident)]
        if args.rule == "R2" and known:
            pick = known[0]
            reason = "R2-漢典已有这一对（现代字, 字形），沿用矢量件"
        else:
            pick = lst[0]
            reason = ("R1-字体号升序" if args.rule == "R1"
                      else ("R2-桶内無漢典字形，退回字体号升序" if known
                            else "R2-桶内無漢典字形"))
        shape_key = f"{pick.get('font_id','')}_{pick['pua']}"
        in_zdic = pair_known(shape_key, ident)
        rec = {
            "identity": ident, "identity_confidence": pick.get("_conf", ""),
            "modern_char": pick.get("modern_char", ""),
            "book_code": pick.get("_out_code", ""), "bucket_key": bucket_code,
            "shape_key": shape_key,
            "font_id": pick.get("font_id", ""), "font": pick.get("font", ""),
            "pua": pick["pua"], "source_short": pick.get("source_short", ""),
            "zi_order": pick.get("zi_order"),
            "bucket_size": len(lst), "rule": reason,
            "zdic_has_shape": shape_key in z_shapes,
            "zdic_has_pair": in_zdic,
            "zdic_has_bucket": f"{ident}\t{bucket_code}" in z_buckets,
        }
        selection.append(rec)
        if not in_zdic:
            need_bitmaps[shape_key] = pick
        stats["选中桶"] += 1
        if in_zdic:
            stats["沿用漢典矢量件"] += 1

    print(f"=== {args.db} → 层 {layer}")
    print(f"  分桶维度 {mode}（每 (现代字, 桶键) 1 条，桶键按"
          f"{'字形' if bucket_by == 'shape' else '文献/时代'}算）、"
          f"每字上限 {layer_cap}（来源上限 {per_char}）——与现有层同一套口径")
    print(f"  索引实例 {len(instances):,}；计入分桶 {stats['实例']:,}"
          f"（其他字体 {stats['其他字体']:,}、出處對不上表 {stats['出處對不上表']:,}）")
    print(f"  身份：反查補回 {stats['身份反查補回']:,}、"
          f"字形键定 {stats['身份由字形键定']:,}、"
          f"臨時身份 {stats['臨時身份']:,}")
    print(f"  (身份, 桶键) 桶 {len(buckets):,} → 漢典已覆盖 {stats['漢典已覆盖该桶']:,}、"
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
