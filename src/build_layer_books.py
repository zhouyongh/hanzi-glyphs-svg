#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按小學堂的**出處表**生成某层的文献对照表 ``glyphs/<层>/books.csv``。

用法::

    python src/build_layer_books.py --db qinwenzi
    python src/build_layer_books.py --db chuanchao --from-csv tmp/xxt/references/...csv

表的列与仓里既有的 ``glyphs/chu/books.csv`` 一致：

    code, corpus_full, script_belong, include, reason, evidence

- ``code``：小學堂出處表里的**簡稱**（也是出處簡號的前缀），如「睡.編」；
- ``corpus_full``：出處表给的**全称**，照抄不改一字；
- ``script_belong``：本层名；
- ``include``：本层是否收录这批材料。新层只有小學堂一个来源 → 全 yes；
- ``reason``：为什么不收 / 归属依据（留空也要写清楚「没有例外」）；
- ``evidence``：**出處表 URL + 取回时刻**——这是这张表唯一的上游证据。

**为什么每条都要带 evidence。** 归属要靠证据，不靠猜书名：出處表是上游自己
给的「簡稱 → 全稱」对照，它就是证据。没取回过、没记时刻的条目不许写进来。

**底本（摹本）与出處表是两回事。** 出處表记的是「这个字出自哪本书」，
而字形本身是对**摹本底本**的摹写（如《楚系簡帛文字編》《傳抄古文字編》）。
底本链条记在每条字形的 ``source_references`` 里，不在本表。
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 库 → (层名, 出處表快照目录, 底本说明)
DBS = {
    "qinwenzi": ("qinwenzi", "qinwenzi",
                 "摹本底本为《睡虎地秦簡文字編》（徐在國主編，文物出版社，1999）；"
                 "出處表列的是《睡虎地秦墓竹簡》各篇的全稱。"),
    "chuanchao": ("chuanchao", "chuanchao",
                  "摹本底本為徐在國《傳抄古文字編》（綫裝書局，2006）；"
                  "出處表列的是《傳抄古文字編》所引書目與《汗簡》《古文四聲韻》"
                  "字形的出處簡稱。"),
    "xiaozhuan": ("xiaozhuan", "xiaozhuan",
                  "摹本底本為《說文解字》；**小學堂小篆庫沒有出處表頁**（實測首頁無該鏈接），"
                  "故本表只能靠 ZiOrder 枚舉 + 字頭信息建立，須另行設計歸屬依據。"),
}

FIELDS = ["code", "corpus_full", "script_belong", "include", "reason", "evidence"]

#: **漢典那边有、小學堂出處表没有**的源書代号。
#:
#: 傳抄层的收录闸门按 `book_code` 判，两边的代号是两套体系：
#: 漢典「傳抄古文字」栏的 21 个代号里，「說籀」「汗目」「石附」「石補」
#: **小學堂出處表一个都没有**（其余 17 个两边对得上）。
#: 这四个是漢典对《傳抄古文字編》所引書目的代号，收录闸门不认识它们
#: 就得把 839 条矢量件全部挡在层外——那是**误挡**，不是该挡的。
#:
#: **各代号具体指哪部书未证实**（见 `src/fetch_zdic_glyphs.py` 的
#: `CHUANCHAO_BOOK_CODES` 注释），按仓库惯例**一律按上游原文记**，
#: 不替它猜：`corpus_full` 留空，层里的 `source_book` 就保留这个代号
#: （见 `import_glyph_layer.py` 的 `load_book_map`）。
#: 「查不到就不编」比「编一个像样的书名」好。
EXTRA_BOOKS: dict[str, list[tuple[str, str]]] = {
    "chuanchao": [
        ("說籀", "https://www.zdic.net/hans/%E3%91%82/chuanchao"),
        ("汗目", "https://www.zdic.net/hans/%E3%90%BA/chuanchao"),
        ("石附", "https://www.zdic.net/hans/%E7%9F%B3/chuanchao"),
        ("石補", "https://www.zdic.net/hans/%E7%9F%B3/chuanchao"),
    ],
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="按小學堂出處表生成层的文献对照表")
    ap.add_argument("--db", required=True, choices=sorted(DBS))
    ap.add_argument("--from-csv", type=Path, action="append", default=None,
                    help="出處表 CSV（列：code,corpus_full,source_publication,"
                         "source_url,retrieved_at）。可给多次。"
                         "默认读抓取阶段落在 tmp/xxt/references/<库>/ 下的全部快照。")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    layer, db, base_note = DBS[args.db]
    if args.from_csv:
        srcs = list(args.from_csv)
    else:
        base = ROOT / "tmp" / "xxt" / "references" / db
        srcs = sorted(base.glob("*.csv")) if base.is_dir() else []
        if not srcs:
            raise SystemExit(f"找不到出處表快照（{base}）；用 --from-csv 指定")
    out = args.out or (ROOT / "glyphs" / layer / "books.csv")

    rows: list[dict] = []
    by_code: dict[str, dict] = {}
    for src in srcs:
        with src.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                code = (row.get("code") or "").strip()
                if not code:
                    continue
                url = (row.get("source_url") or "").strip()
                at = (row.get("retrieved_at") or "").strip()
                entry = {
                    "code": code,
                    "corpus_full": (row.get("corpus_full") or "").strip(),
                    "script_belong": layer,
                    "include": "yes",
                    "reason": base_note,
                    "evidence": f"{url}（{at} 取回）" if url else "",
                }
                if code in by_code:
                    # 同一个簡稱出现在两张表里：材料是**同一件**（實測傳抄库的
                    # 「汗」「石」「碧」「說」「陰」），只是详略不同——
                    # 保留先到那张（更全）的全稱，另一张的简称记进 reason。
                    prev = by_code[code]
                    if entry["corpus_full"] and not prev["corpus_full"]:
                        prev["corpus_full"] = entry["corpus_full"]
                    prev["reason"] += f"；另一张出處表作「{entry['corpus_full']}」"
                    continue
                by_code[code] = entry
                rows.append(entry)

    # 漢典那边有、小學堂出處表没有的代号：补进来，否则收录闸门会误挡。
    for code, url in EXTRA_BOOKS.get(db, []):
        if code in by_code:
            continue
        entry = {
            "code": code,
            "corpus_full": "",
            "script_belong": layer,
            "include": "yes",
            "reason": (base_note + "漢典「傳抄古文字」栏的源書代号，"
                       "小學堂出處表没有这一项；各代号具体指哪部书未证实，"
                       "按上游原文记代号，不代它猜"),
            "evidence": f"{url}（2026-10-31 取回）",
        }
        by_code[code] = entry
        rows.append(entry)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"写入 {out}：{len(rows)} 行（来源：{'、'.join(s.name for s in srcs)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
