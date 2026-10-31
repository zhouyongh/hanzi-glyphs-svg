#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 ``glyphs/chu/books_xxt.csv``——小學堂楚系庫的出處表登記表。

用法::

    python src/build_books_xxt.py                      # 用仓内已有的出處表行重算
    python src/build_books_xxt.py --from-csv <出處表.csv>  # 用新抓的出處表重算

**为什么要有这张表。** ``glyphs/chu/books.csv`` 是**漢典那一栏**的归属闸门——
漢典「楚系簡帛」栏里混着秦系與傳抄，所以有 ``磚`` / ``秦`` 两行 ``include=no``。
小學堂的楚系庫是**按庫劃定**的（庫里就是《楚系簡帛文字編》的材料），同一串簡號
在两边的含义还不一样：

    漢典 chuwenzi 栏的「磚」 = 傳抄古文字編的宋古文磚   → **不屬楚系**
    小學堂 chuwenzi 庫的「磚370」 = 江陵磚瓦廠370號墓竹簡 → **屬楚系**

    漢典 chuwenzi 栏的「秦」 = 睡虎地秦簡文字編           → **不屬楚系**
    小學堂 chuwenzi 庫的「秦1/13/99」 = 江陵秦家嘴1/13/99號墓竹簡 → **屬楚系**

所以小學堂这一側不能複用 books.csv 的 code 去查 include；它有自己的鍵
（出處表簡號），另有一列指出它對應漢典哪個文獻代號（對不上就留空）。

**表分两種行，用 ``row_kind`` 區分。**

- ``出處表``：小學堂出處表的**原樣**行（全稱、版本照抄，不改一字）。
- ``派生``：腳本按**實測數據**補的行——出處表沒列、但字形單元里確實出現的簡號。

派生行不是「編造」：每行都寫明它依據什麼（見 note 列），並保留出處表 URL
與取回時刻。**全稱〔待考〕的行必須原樣保留〔待考〕標記**——
沒核實過的全稱不能當成已核實。

**對不上漢典代號的行一律留空**，由調用方決定收不收；判斷「這是什麼材料」
不能靠默認值。
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "glyphs" / "chu" / "books_xxt.csv"

FIELDS = ["xxt_code", "corpus_full", "source_publication", "zdic_code",
          "row_kind", "note", "source_url", "retrieved_at"]

# 小學堂簡號 → 漢典文獻代號。**只認同材料。**
#
# 三處必須留空（實測：漢典那一欄的同名簡號是**另一件材料**）：
#   磚370  漢典「磚」= 傳抄古文字編的宋古文磚
#   秦1/13/99  漢典「秦」= 睡虎地秦簡文字編
#   新     漢典分「新甲/新乙/新零」三組，單靠「新」對不到組（另派生三行）
#   帛殘   漢典層沒有這個簡號（〔殘片〕不分篇）
EXPLICIT = {
    "牌406": "牌",
    "仰25": "仰",
    "常2": "常",
    "天卜": "天卜",
    "天策": "天策",
    "香中大": "香中大",
    "雨21": "雨",
    "馬1": "馬",
    "范27": "范",
    "包2": "包",
    "包牘": "包牘",
    "包簽": "包簽",
    "信1": "信",
    "信2": "信",
    "曾": "曾",
    "帛甲": "帛甲",
    "帛乙": "帛乙",
    "帛丙": "帛丙",
    "帛殘": "",
    "望1": "望",
    "望2": "望",
    "九.56": "九",
    "九.621": "九",
    "新": "",
    "磚370": "",
    "秦1": "",
    "秦13": "",
    "秦99": "",
}

# 按前綴對應的（出處表里篇名級的簡號）
PREFIX_RULES = (
    ("郭.", "郭"),
    ("上(1).", "上(1)"),
    ("上(2).", "上(2)"),
)

NOTES = {
    "磚370": "小學堂的「磚370」= 江陵磚瓦廠370號墓竹簡（楚系出土竹簡），"
             "與漢典 chuwenzi 栏的「磚」（傳抄古文字編的宋古文磚）**不是同一件材料**；"
             "此處歸楚系，故 zdic_code 留空。",
    "秦1": "小學堂的「秦1/秦13/秦99」= 江陵秦家嘴1/13/99號墓竹簡（楚系出土竹簡），"
           "與漢典 chuwenzi 栏的「秦」（睡虎地秦簡文字編）**不是同一件材料**；"
           "此處歸楚系，故 zdic_code 留空。",
    "新": "小學堂只作「新」（新蔡葛陵楚墓竹簡），漢典分「新甲/新乙/新零」三組；"
          "此處只能對到「新」這一級，另派生三行按組切。",
    "九.56": "「九.56」「九.621」= 江陵九店56/621號墓竹簡。",
    "望1": "「望1」「望2」= 江陵望山1/2號墓竹簡。",
    "信1": "「信1」「信2」= 信陽1號墓竹書簡／遣策簡。",
}

# 派生行：出處表裡沒有、但字形單元里確實出現的簡號。
# 每行都要寫明依據；沒核實過的全稱一律帶〔待考〕。
DERIVED = [
    {
        "xxt_code": "新甲", "zdic_code": "新甲",
        "corpus_full": "新蔡葛陵楚簡·甲組",
        "note": "派生行：小學堂出處表只列「新」（墓），但字形單元的出處簡號帶組前綴"
                "（如「新甲3.137」）；漢典層分甲/乙/零三組，故按組切，"
                "與漢典層的編號粒度（組.簡號，如 3.137）一致。",
    },
    {
        "xxt_code": "新乙", "zdic_code": "新乙",
        "corpus_full": "新蔡葛陵楚簡·乙組",
        "note": "派生行：同「新甲」，按漢典層的三組切分。",
    },
    {
        "xxt_code": "新零", "zdic_code": "新零",
        "corpus_full": "新蔡葛陵楚簡·零組",
        "note": "派生行：同「新甲」，按漢典層的三組切分。",
    },
    {
        "xxt_code": "郭.殘", "zdic_code": "郭",
        "corpus_full": "郭店楚簡",
        "note": "派生行：小學堂出處表只列篇名（郭.老甲…郭.語4），"
                "字形單元裡還有「郭.殘.6」「郭.殘.9」這類殘簡簡號（實測），故補一行兜底。",
    },
    {
        "xxt_code": "上(1)", "zdic_code": "上(1)",
        "corpus_full": "上海博物館藏戰國楚竹書（一）",
        "note": "派生行：出處表按篇列（上(1).孔 / 上(1).䊷 / 上(1).性），"
                "簡號未帶篇名時按冊歸屬。",
    },
    {
        "xxt_code": "上(2)", "zdic_code": "上(2)",
        "corpus_full": "上海博物館藏戰國楚竹書（二）",
        "note": "派生行：同「上(1)」。",
    },
    {
        "xxt_code": "常1", "zdic_code": "常",
        "corpus_full": "常德市德山夕陽坡1號墓竹簡〔待考〕",
        "note": "派生行：**小學堂出處表未列此條**（表里只有「常2」）。"
                "但漢典層的「常」桶**同時含 1 號墓與 2 號墓**"
                "（實測：編號首段 1 有 26 條、2 有 9 條，題記作「常1」「常2.1」），"
                "故按「常N → 夕陽坡N號墓」的編號規律推定；全稱〔待考〕——不得當作已核實。",
    },
]

# 兜底聚合行：小學堂出處表按墓號/篇名列，這些是它們的**上位**文獻。
# 簡號沒帶墓號或篇名時歸到這裡（漢典那一側的代號就是它們）。
FALLBACKS = [
    ("郭", "郭店楚簡", "郭", "郭店楚簡（篇名見郭.老甲…郭.語4 各行）"),
    ("包", "包山楚簡", "包", "包山楚簡（冊/類別見包2 / 包牘 / 包簽 各行）"),
    ("望", "江陵望山楚簡", "望", "江陵望山楚簡（墓號見望1 / 望2 各行）"),
    ("信", "信陽長臺關楚簡", "信", "信陽1號墓竹書簡／遣策簡（見信1 / 信2 各行）"),
    ("九", "九店楚簡", "九", "九店楚簡（墓號見九.56 / 九.621 各行）"),
    ("常", "常德市德山夕陽坡1、2號墓竹簡", "常",
     "常德市德山夕陽坡1、2號墓竹簡（漢典層的「常」桶同時含兩座墓）"),
    ("雨", "江陵雨臺山21號墓竹律管墨書文字", "雨", "見雨21 一行"),
    ("范", "江陵范家坡27號墓竹簡", "范", "見范27 一行"),
    ("馬", "江陵馬山1號墓竹簡", "馬", "見馬1 一行"),
    ("牌", "五里牌楚簡", "牌", "見牌406 一行"),
    ("仰", "仰天湖楚簡", "仰", "見仰25 一行"),
]


def zdic_code_for(code: str) -> str:
    """小學堂簡號 → 漢典文獻代號（對不上就留空）。"""
    if code in EXPLICIT:
        return EXPLICIT[code]
    for prefix, target in PREFIX_RULES:
        if code.startswith(prefix):
            return target
    return ""


def load_source_rows(path: Path) -> list[dict]:
    """讀出處表：兩種來源都能吃。

    - 新抓的出處表 CSV：列為 ``code,corpus_full,source_publication,source_url,retrieved_at``
    - 仓内已有的 books_xxt.csv：列為本腳本的 ``FIELDS``，取 ``row_kind=出處表`` 的行
    """
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = set(reader.fieldnames or [])
        rows = []
        for r in reader:
            if "xxt_code" in fields:
                # 旧版文件没有 row_kind 列，整表当出處表行处理；
                # 新版按 row_kind 分，派生行不重复引入。
                if "row_kind" in fields and (r.get("row_kind") or "").strip() != "出處表":
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
    ap = argparse.ArgumentParser(description="生成小學堂出處表登記表 books_xxt.csv")
    ap.add_argument("--from-csv", type=Path, default=None,
                    help="出處表 CSV（列：code,corpus_full,source_publication,"
                         "source_url,retrieved_at）。默认读仓内 books_xxt.csv 的出處表行。")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="输出路径")
    args = ap.parse_args(argv)

    src = args.from_csv or DEFAULT_OUT
    if not src.is_file():
        raise SystemExit(f"找不到出處表來源：{src}")
    base_rows = load_source_rows(src)

    out: list[dict] = []
    for r in base_rows:
        code = r["code"]
        out.append({
            "xxt_code": code,
            "corpus_full": r["corpus_full"],
            "source_publication": r["source_publication"],
            "zdic_code": zdic_code_for(code),
            "row_kind": "出處表",
            "note": NOTES.get(code, ""),
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
            "row_kind": "派生",
            "note": "兜底聚合行：" + note,
            "source_url": ref_url,
            "retrieved_at": "",
        })
        have.add(code)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)

    kinds = {}
    for row in out:
        kinds[row["row_kind"]] = kinds.get(row["row_kind"], 0) + 1
    unmatched = [r["xxt_code"] for r in out if not r["zdic_code"]]
    print(f"写入 {args.out}：{len(out)} 行（{kinds}）")
    print(f"對不上漢典代號（zdic_code 留空）{len(unmatched)} 個：{unmatched}")
    print("→ zdic_code 留空不代表不收：它表示**這件材料漢典那一欄沒有對應**，")
    print("  收不收由層自己的 books.csv 決定。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
