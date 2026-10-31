#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 ``glyphs/chuanchao/books_xxt.csv``——傳抄层的小學堂出處表登記表。

**为什么要有这张表。** 傳抄层是**混合层**：同一批材料，漢典给矢量件、小學堂给位图。
两边的「文献代号」是**两套体系**，粒度也不一样：

    漢典傳抄栏的「汗目」「說籀」「石附」  → 小學堂出處表里**没有这三个代號**
    小學堂出處表的 119 个代號（多爲碑刻类）→ 漢典那一栏**根本没出现**

所以小學堂这一側不能複用 ``books.csv`` 的 code 去查 include；它有自己的鍵
（出處表簡號），另有一列指出它對應漢典哪個文獻代號（對不上就留空）。

**对上的依据是「两边指同一件材料」，不是「长得像」。**
對照時逐條比對兩邊的**文獻全稱**（上游原文）：全稱同一件材料的才连。
全稱對不上就留空——**不猜**。猜錯書名比留个代号更糟：讀者會照着錯的名字去找書，
找不到就以爲這條出處是編的。

**表分兩種行，用 ``row_kind`` 區分。**

- ``出處表``：小學堂出處表的**原樣**行（全稱、版本照抄，不改一字）。
- ``派生``：按**實測數據**補的行——出處表沒列、但字形單元里確實出現的簡號。

用法::

    python src/build_books_xxt_chuanchao.py
    python src/build_books_xxt_chuanchao.py --from-csv tmp/xxt/references/chuanchao/*.csv
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "glyphs" / "chuanchao" / "books_xxt.csv"

FIELDS = ["xxt_code", "corpus_full", "source_publication", "zdic_code",
          "row_kind", "note", "source_url", "retrieved_at"]

# 小學堂簡號 → 漢典文獻代號。**只認同材料。**
#
# 判据：兩邊的**文獻全稱**指向同一件材料。全稱對不上就留空。
# 這裡的每一條都附著理由（見 NOTES），複核時看理由不看對應結果。
EXPLICIT: dict[str, str] = {}

# 派生行：出處表裡沒有、但字形單元里確實出現的簡號。
# 每行都要寫明依據；沒核實過的全稱一律帶〔待考〕。
DERIVED: list[dict] = []

NOTES: dict[str, str] = {}

# 兜底聚合行：小學堂出處表按墓號/篇名列，這些是它們的**上位**文獻。
# 簡號沒帶墓號或篇名時歸到這裡。
FALLBACKS: list[tuple] = []

# 漢典傳抄層的清單：從裡面取每個代號的**文獻全稱**（上游原文）。
# 對照判據就是「兩邊的全稱指向同一件材料」——用全稱自動判，不用手寫映射表。
DEFAULT_ZDIC_MANIFEST = ROOT / "tmp" / "zdic" / "chuanchao-full" / "manifest.json"


def load_zdic_names(manifest: Path) -> dict[str, str]:
    """從漢典清單取「代號 → 文獻全稱」。

    同一代號有多条實例，它們的 ``source_book`` 應當一致（同一件材料）；
    不一致就取**出現最多**的那個，並記下分歧（見 NOTES）。
    回傳值是 {code: 全稱}。
    """
    if not manifest.is_file():
        return {}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    counts: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for g in data.get("glyphs", []):
        code = str(g.get("book_code") or "").strip()
        name = str(g.get("source_book") or "").strip()
        if code and name:
            counts[code][name] += 1
    out: dict[str, str] = {}
    for code, c in counts.items():
        out[code] = c.most_common(1)[0][0]
    return out


def same_corpus(a: str, b: str) -> bool:
    """两边的全称是否指向**同一件材料**。

    判据是**去掉标点与空白后逐字相同**——两边的全称都是上游原文，
    差别只在标点写法（「（」「，」的位置）。逐字相同是最严的判据；
    对不上就留空——**不猜**。
    """
    def norm(s: str) -> str:
        return "".join(ch for ch in s if ch not in "（）()、，。：:；;《》「」“”\"' \t\r\n　·-—")
    return norm(a) == norm(b) and bool(norm(a))


def zdic_code_for(code: str, corpus_full: str, zdic_names: dict[str, str]) -> str:
    """小學堂簡號 → 漢典文獻代號。

    **判据是「两边全称逐字相同」**：小學堂出處表的全稱與漢典清單里該代號的全稱，
    去掉标点空白后逐字相同才连上。对不上留空——猜錯書名比留个代号更糟。
    """
    if not corpus_full:
        return ""
    for zcode, zname in zdic_names.items():
        if zcode == code and same_corpus(corpus_full, zname):
            return zcode
        if same_corpus(corpus_full, zname):
            return zcode
    return ""


def load_source_rows(paths: list[Path]) -> list[dict]:
    """讀出處表：兩種來源都能吃。

    - 新抓的出處表 CSV：列為 ``code,corpus_full,source_publication,source_url,retrieved_at``
    - 倉內已有的 books_xxt.csv：列為本腳本的 ``FIELDS``，取 ``row_kind=出處表`` 的行
    """
    rows: list[dict] = []
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            fields = set(reader.fieldnames or [])
            for r in reader:
                if "xxt_code" in fields:
                    if (r.get("row_kind") or "").strip() != "出處表":
                        continue
                    rows.append({
                        "code": (r.get("xxt_code") or "").strip(),
                        "corpus_full": (r.get("corpus_full") or "").strip(),
                        "source_publication": (r.get("source_publication") or "").strip(),
                        "source_url": (r.get("source_url") or "").strip(),
                        "retrieved_at": (r.get("retrieved_at") or "").strip(),
                    })
                else:
                    rows.append({
                        "code": (r.get("code") or "").strip(),
                        "corpus_full": (r.get("corpus_full") or "").strip(),
                        "source_publication": (r.get("source_publication") or "").strip(),
                        "source_url": (r.get("source_url") or "").strip(),
                        "retrieved_at": (r.get("retrieved_at") or "").strip(),
                    })
    return [r for r in rows if r["code"]]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成傳抄层的小學堂出處表登記表 books_xxt.csv")
    ap.add_argument("--from-csv", type=Path, action="append", default=None,
                    help="出處表 CSV（列：code,corpus_full,source_publication,"
                         "source_url,retrieved_at）。可給多次。")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="输出路径")
    ap.add_argument("--zdic-manifest", type=Path, default=DEFAULT_ZDIC_MANIFEST,
                    help="漢典傳抄層的清單（取每個代號的文獻全稱用）")
    args = ap.parse_args(argv)

    if args.from_csv:
        srcs = list(args.from_csv)
    else:
        base = ROOT / "tmp" / "xxt" / "references" / "chuanchao"
        srcs = sorted(base.glob("*.csv")) if base.is_dir() else []
        if not srcs:
            raise SystemExit(f"找不到出處表快照：{base}；用 --from-csv 指定")
    base_rows = load_source_rows(srcs)

    # 漢典侧的「代號 → 文獻全稱」。对照判据是**两边全称逐字相同**。
    zdic_names = load_zdic_names(args.zdic_manifest.resolve())
    if not zdic_names:
        print(f"注意：读不到漢典清单（{args.zdic_manifest}），"
              f"zdic_code 只能全留空——对不上就留空，不猜。")

    out: list[dict] = []
    for r in base_rows:
        code = r["code"]
        zcode = zdic_code_for(code, r["corpus_full"], zdic_names)
        note = NOTES.get(code, "")
        if zcode:
            note = (note + " " if note else "") + \
                "对照依據：两边全称逐字相同（漢典代號「{}」）。".format(zcode)
        out.append({
            "xxt_code": code,
            "corpus_full": r["corpus_full"],
            "source_publication": r["source_publication"],
            "zdic_code": zcode,
            "row_kind": "出處表",
            "note": note,
            "source_url": r["source_url"],
            "retrieved_at": r["retrieved_at"],
        })

    have = {row["xxt_code"] for row in out}
    ref_url = next((row["source_url"] for row in out if row["source_url"]), "")
    for d in DERIVED:
        if d["xxt_code"] in have:
            continue
        out.append({
            "xxt_code": d["xxt_code"],
            "corpus_full": d["corpus_full"],
            "source_publication": "",
            "zdic_code": d["zdic_code"],
            "row_kind": "派生",
            "note": d["note"],
            "source_url": ref_url,
            "retrieved_at": "",
        })
        have.add(d["xxt_code"])
    for code, full, zc, note in FALLBACKS:
        if code in have:
            continue
        out.append({
            "xxt_code": code,
            "corpus_full": full,
            "source_publication": "",
            "zdic_code": zc,
            "row_kind": "兜底聚合",
            "note": note,
            "source_url": ref_url,
            "retrieved_at": "",
        })
        have.add(code)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)

    mapped = sum(1 for r in out if r["zdic_code"])
    print(f"寫入 {args.out}：{len(out)} 行（對上漢典代號 {mapped} 行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
