#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把小學堂的抓取结果（实例索引 + 描摹清单）转成合并器要的清单格式。

输入（都是抓取阶段落的盘）::

    tmp/xxt/<库>/index.jsonl     一行一个**实例**（字頭 × 出處簡號 × 字形）
    tmp/xxt/<库>/traced.jsonl     一行一个**字形**（描摹出来的 SVG + 派生件记账）
    tmp/xxt/<库>/img/             位图（derived_from 的原件）

输出::

    tmp/xxt/<库>/manifest.json    合并器认的清单格式（glyphs 列表）

**为什么要单独一个适配器。** 抓取脚本的落盘格式是「实例索引 + 字形清单」两份，
因为位图按 (字体号, 码位) 缓存、同一字形被多个字頭复用；合并器要的却是一份
「一行一个待入库字形」的清单。两者之间要做的转换不只是改字段名，还包括
**决定每个字形算作哪个现代字**——这一步有讲究，见下面「异体字怎么定」。

**怎么判「層裡有沒有這條」（這是最容易錯的一步）。**

漢字「字形」與「现代字」不是一回事：同一个楚文字形可以释作不同的異體字，
漢典楚系层的 ``modern_char`` 记的就是**異體字**（弌 / 靝 / 兲 …，真 Unicode 汉字），
而小學堂的「字頭」是**楷書字**（一 / 天 / 元 …），異體字則放在「沙海隸外字集N」
字體的**槽位碼位**上（U+FBE2 之類，不是真漢字），兩邊沒法直接對文本。

層的鍵是 **(现代字码位, 字形鍵)**，所以判重要落到 unicode 這一維：

  1. 「这个现代字 + 这个字形」漢典层已有 → **不新增**，記 crosswalk
     （出處簡號也對上 = kind ``same``；對不上 = kind ``source_mismatch``）。
  2. 字形漢典层有，但这个**现代字身份**沒有 → **新增**。小學堂的楷書字頭是正字，
     正字身份本身就是漢典层缺的那一條——這就是「小學堂補缺口」。
     unicode 不同，所以**不撞鍵**。
  3. 字形連漢典层都沒有 → **新增**，现代字用小學堂的楷書字頭。

**小學堂的楷書字頭有時是私用區槽位**（實測 U+F3F2 ≈ 上、U+F407 ≈ 下），
不是真漢字，不能當 unicode 鍵。這類字形若漢典层已收錄，就由漢典那邊的記錄
（異體字名下）代表；漢典没有的則無法確定现代字身份，本層不收——
記進 crosswalk 的 ``pua_head``，留給人看。

出處簡號 → 文獻代號 / 全稱 / 編號 的對照用層目錄的 ``books_xxt.csv``
（小學堂出處表原樣 + 對應的漢典文獻代號）。**文獻代號對不上就不收**——
判斷「這是什麼材料」不能靠默認值。
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 小學堂各库的脚本名（合并/入库用的 script 字段）
DB_SCRIPT = {
    "chuwenzi": "chu",
    "qinwenzi": "qinwenzi",
    "chuanchao": "chuanchao",
    "jiaguwen": "oracle",
    "jinwen": "bronze",
    "lishu": "clerical",
    "xiaozhuan": "xiaozhuan",
}

ATTRIBUTION = ("字形图来自小学堂（中央研究院數位文化中心）古文字資料庫，"
               "依其《版權聲明》以 CC0 1.0 释出")


def norm_cp(raw: str) -> str:
    cp = (raw or "").strip().upper()
    if cp.startswith("U+"):
        cp = cp[2:]
    return cp.rjust(6, "0")


# 私用區（PUA）與代理區——这些码位**不是漢字**，不能當层键的 unicode 部分。
PUA_RANGES = (
    (0xE000, 0xF8FF),      # BMP 私用區
    (0xF0000, 0xFFFFD),    # 私用區 A
    (0x100000, 0x10FFFD),  # 私用區 B
)


def usable_modern_char(ch: str) -> bool:
    """这个「现代字」能不能当层键的 unicode 部分。

    小學堂頁面里的「楷書字頭」有時是**字體槽位碼位**（私用區）而不是真漢字——
    站點自己的字體把罕見字放在 PUA 上渲染（實測 U+F3F2、U+F407）。
    PUA 不是漢字，拿它当 unicode 会让层里出现「一个没有对应汉字的码位」。

    同样的道理：漢典层里的**異體字**是真漢字（弌 / 靝 / 兲 …），
    而小學堂的異體字是「沙海隸外字集N」的槽位碼位。两边对不上文本，
    所以交叉比对要用**字形鍵**（字体号_PUA）当锚点，不能用字頭对齐。
    """
    if not ch or len(ch) != 1:
        return False
    cp = ord(ch)
    if 0xD800 <= cp <= 0xDFFF:      # 代理區
        return False
    return not any(lo <= cp <= hi for lo, hi in PUA_RANGES)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def load_books_xxt(path: Path) -> tuple[dict[str, dict], list[str]]:
    """读小學堂出處表登记，返回 (簡稱 → 行, 所有簡稱按長度倒序)。

    **两种列名都认**：``xxt_code``（楚系层的 ``books_xxt.csv`` 用这个）
    与 ``code``（層自己的 ``books.csv`` 用这个）。新层（傳抄 / 秦系 / 小篆）
    没有漢典对照方，只有層自己的 ``books.csv``——那一张表就能兼当出處表用，
    不必再抄一份。
    """
    rows: dict[str, dict] = {}
    if not path.exists():
        return rows, []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = set(reader.fieldnames or [])
        col = "xxt_code" if "xxt_code" in fields else "code"
        for row in reader:
            code = (row.get(col) or "").strip()
            if code:
                rows[code] = row
    return rows, sorted(rows, key=len, reverse=True)


def resolve_literature(short: str, books_rows: dict[str, dict]) -> tuple[str, dict | None]:
    """出處簡號 → (文獻標識, 出處表那一行)。最長前綴匹配。

    「郭.老甲.4」→「郭.老甲」；「曾137」→「曾」；「新甲3.137」→「新」（表裡只有「新」）。
    對不上就回 (文獻標識, None)——調用方據此**不收**這條：判斷「這是什麼材料」
    不能靠默認值。
    """
    best = ""
    for c in books_rows:
        if short.startswith(c) and len(c) > len(best):
            best = c
    return best, books_rows.get(best)


def strip_variant(v: str, codes: list[str]) -> str:
    """漢典 variant = 異體字（一个）+ 出處簡號。

    出處簡號 = 文獻標識 + 編號，編號必以數字或點開頭。切點因此唯一確定。
    為什麼不能只看「已知標識前綴」：異體字本身也可能是漢字，而且可能**恰好**
    是一個文獻代號（異體字「上」+ 出處「帛乙6.4」= 「上帛乙6.4」）。
    """
    v = (v or "").strip()
    if not v:
        return ""
    for i in (0, 1):
        rest = v[i:]
        code = ""
        for c in codes:
            if rest.startswith(c) and len(c) > len(code):
                code = c
        if not code:
            continue
        tail = rest[len(code):]
        if tail == "" or tail[0].isdigit() or tail[0] == ".":
            return rest
    return v


def base_pages_of(references: list[str]) -> tuple[str, str]:
    """從「相關索引」裡拆出 (底本页.行, 底本清單)。

    底本页.行取《楚系簡帛文字編》那條——它是楚系層的**摹本底本**，粒度與漢典層的
    ``source_base_pages`` 一致（實測 53/53 逐條相同）。底本清單則是全部相關索引。
    """
    pages = ""
    refs = list(references)
    for item in references:
        if "楚系簡帛文字編" in item or "睡虎地秦簡文字編" in item:
            m = re.search(r"頁[.．]?行[：:]\s*([^\s，,；;]+)", item)
            if m:
                pages = m.group(1)
                break
    return pages, "；".join(refs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="小學堂抓取结果 → 合并器清单")
    ap.add_argument("--db", required=True, help="库名（chuwenzi / qinwenzi / …）")
    ap.add_argument("--index", required=True, type=Path, help="实例索引 index.jsonl")
    ap.add_argument("--traced", required=True, type=Path, help="描摹清单 traced.jsonl")
    ap.add_argument("--svg-dir", required=True, type=Path, help="描摹出来的 SVG 目录")
    ap.add_argument("--out", required=True, type=Path, help="输出 manifest.json")
    ap.add_argument("--books-xxt", type=Path, default=None,
                    help="小學堂出處表登记表（glyphs/<层>/books_xxt.csv）")
    ap.add_argument("--books", type=Path, default=None,
                    help="层的文献对照表（glyphs/<层>/books.csv）：用来把文献代号换成"
                         "与漢典层**同一粒度**的全称，避免两边的分桶口径不一致")
    ap.add_argument("--zdic-index", type=Path, default=None,
                    help="漢典层 index.csv：用来对齐異體字与识别重复")
    ap.add_argument("--identity-map", type=Path, default=None,
                    help="私用區身份反查表（resolve_pua_identity.py 的输出）："
                         "给私用區字頭补回真漢字碼位")
    ap.add_argument("--font-allow", default=None,
                    help="只收字体名以此开头的实例（逗号分隔多个）。"
                         "**书体由字体决定，不由材料决定**：隸變库里同時有"
                         "「中研院隸書重文」與「中研院秦系簡牘文字重文」兩種字体，"
                         "前者是隸書字形（歸隸書層），後者是秦系字形（歸秦系層）")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="字形文件输出目录（默认 <out 所在目录>/files）")
    args = ap.parse_args(argv)

    script = DB_SCRIPT.get(args.db)
    if not script:
        raise SystemExit(f"未知库：{args.db}")

    books_rows: dict[str, dict] = {}
    codes: list[str] = []
    if args.books_xxt:
        books_rows, codes = load_books_xxt(args.books_xxt.resolve())
        if not books_rows:
            raise SystemExit(f"出處表登记表读不出来：{args.books_xxt}")

    # 层的文献对照表（漢典口径的全称）：分桶要**两边同一粒度**，
    # 否则同一批文献会被拆成两个桶（「郭店楚簡」与「荊門郭店楚墓竹簡‧老子甲」）。
    books_csv: dict[str, str] = {}
    if args.books and args.books.is_file():
        with args.books.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                code = (row.get("code") or "").strip()
                if code:
                    books_csv[code] = (row.get("corpus_full") or "").strip()

    # 漢典层：字形键 → 行（用来定異體字、识别重复）
    z_by_shape: dict[str, list[dict]] = defaultdict(list)
    if args.zdic_index and args.zdic_index.is_file():
        with args.zdic_index.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                z_by_shape[row["source_id"]].append(row)

    instances = load_jsonl(args.index.resolve())
    traced = {r["shape_key"]: r for r in load_jsonl(args.traced.resolve())}

    # 字体闸门：**书体由字体决定**。同一库里可能混着不同书体的字形
    # （隸變库的「秦系簡牘」字体是秦系字形，不是隸書）。
    font_allow = [f.strip() for f in (args.font_allow or "").split(",") if f.strip()]

    # 私用區身份反查表：字頭號 → 现代字（路徑 D/A 見 resolve_pua_identity.py）
    identity_map: dict[int, dict] = {}
    if args.identity_map and args.identity_map.is_file():
        for rec in load_jsonl(args.identity_map.resolve()):
            if rec.get("modern_char"):
                identity_map[int(rec["zi_order"])] = rec

    out_dir = (args.out_dir or (args.out.resolve().parent / "files"))
    out_dir.mkdir(parents=True, exist_ok=True)

    glyphs: list[dict] = []
    crosswalk: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()
    stats = {"new_shape": 0, "new_source": 0, "dup": 0, "shape_known": 0,
             "no_traced": 0, "no_book": 0}

    for inst in instances:
        if font_allow and not any(inst.get("font", "").startswith(f)
                                  for f in font_allow):
            stats["other_font"] = stats.get("other_font", 0) + 1
            continue
        shape_key = f"{inst.get('font_id','')}_{inst['pua']}"
        short = inst.get("source_short", "")
        site_char = inst.get("modern_char", "")
        xxt_char = site_char

        # 私用區字頭 → 先試反查表補回真漢字身份。
        # 站点的楷書字頭只是**字體排版槽位**，不是 Unicode；
        # 反查（底本页.行 / 說文小篆槽位）能定回身份就用它，见 resolve_pua_identity.py。
        idrec = None
        zi = inst.get("zi_order")
        if not usable_modern_char(xxt_char) and zi is not None:
            idrec = identity_map.get(zi)
            if idrec:
                xxt_char = idrec["modern_char"]
                stats["identity_resolved"] = stats.get("identity_resolved", 0) + 1

        zrows = z_by_shape.get(shape_key, [])
        zchars = {z["modern_char"] for z in zrows}
        same = [z for z in zrows
                if strip_variant(z.get("variant", ""), codes) == short]

        # ---- 判「層裡有沒有這條」：看 **（现代字, 字形）** 這對鍵 ----
        #
        # 層的鍵是 (现代字码位, 字形鍵)。**不是** (字形, 出處)：
        # 漢字「字形」與「现代字」不是一回事——同一个字形可以释作不同的異體字，
        # 漢典层把異體字與正字**各记一条**（實測：同一字形在漢典层最多有 11 個现代字）。
        # 所以判重必须落到 unicode 这一维上。
        if usable_modern_char(xxt_char) and xxt_char in zchars:
            # 情形 1：漢典层已有「這個现代字 + 這個字形」→ 不新增字形。
            # 出處簡號對得上就是完全相同；對不上是著錄差異，要登記下來。
            stats["dup"] += 1
            crosswalk.append({
                "kind": "same" if same else "source_mismatch",
                "shape_key": shape_key, "source_short": short,
                "xxt_modern_char": xxt_char,
                "zdic_modern_char": same[0]["modern_char"] if same else "",
                "zdic_unicode": same[0]["unicode"] if same else "",
                "zdic_file": same[0].get("file", "") if same else "",
                "zdic_source_short": strip_variant(zrows[0].get("variant", ""), codes),
                "note": ("字形鍵與出處簡號都對上；層裡沿用漢典的矢量字形" if same else
                         "同一个现代字 + 同一个字形已由漢典层收录，但出處簡號對不上；"
                         "層鍵已被占，此處只登記差異，不新增"),
            })
            continue

        if not usable_modern_char(xxt_char):
            # **现代字身份不明**：小學堂的楷書字頭只給了**字體排版槽位碼位**（私用區），
            # 頁面沒有給 Unicode 漢字碼位。實測：字頭行里有三類圖——
            #   標楷體/沙海隸（字體號 0）→ 槽位是真 Unicode（多數字頭）
            #   北師大說文小篆（字體號 27）→ 多數是真 Unicode，罕見字落私用區
            #   標楷體外字集N（1..13）→ **全是私用區**（異體字與部分罕見正字）
            #
            # 處理：**不丟字形**。用槽位碼位當**臨時身份**進層，並明確標記
            # （identity_confidence = "pua-slot"、modern_char_slot = 字體號_碼位）。
            # 這個碼位**不是漢字碼位**，不得當漢字引用——所以必須標出來。
            #
            # 但若漢典层已收录這個字形（同一字形鍵），就**不再新增**：
            # 同一個字形已經有一份帶真漢字身份的矢量記錄，再塞一份臨時身份
            # 只會讓層里多出同一個字形的兩條記錄。
            if zrows:
                stats["shape_known"] += 1
                crosswalk.append({
                    "kind": "pua_head_known", "shape_key": shape_key,
                    "source_short": short,
                    "xxt_modern_char": xxt_char,
                    "xxt_modern_codepoint": ("U+%04X" % ord(xxt_char)) if xxt_char else "",
                    "zdic_modern_chars": "、".join(sorted(zchars)),
                    "note": "小學堂的楷書字頭是私用區槽位（現代字身份待考）；"
                            "漢典层已收录此字形，層裡沿用漢典的矢量記錄",
                })
                continue
            provisional = True
            modern_char = ""
            modern_source = "pua-slot"
        else:
            provisional = False
            # 身份是站点直接给的，还是反查补回来的？两者都要记进 provenance。
            modern_source = "xxt-head" if idrec is None else "reverse-lookup"

        tr = traced.get(shape_key)
        if not tr:
            stats["no_traced"] += 1
            continue
        lit, book = resolve_literature(short, books_rows)
        if not lit or book is None:
            stats["no_book"] += 1
            crosswalk.append({
                "kind": "unresolved_literature", "shape_key": shape_key,
                "source_short": short, "note": "出處簡號對不上出處表，未收",
            })
            continue

        # 新增：這對「现代字 + 字形」在漢典层沒有。
        # 字形在漢典层有（只是这个现代字身份沒有）時，小學堂的**楷書字頭是正字**，
        # 正字身份本身就是漢典层缺的那一條——這就是「小學堂補缺口」。
        if not provisional:
            modern_char = xxt_char
            if zrows:
                modern_source = "xxt-head(正字補缺)"
        else:
            # 臨時身份：现代字未知，但槽位碼位要留下來（它是這個字的唯一線索）。
            modern_char = ""
        # **临时身份条目的 unicode 留空**：槽位碼位是**私用區**，不是漢字碼位，
        # 拿它当 unicode 会让层里出现「一个没有对应汉字的码位」。
        # 照甲骨层既有先例（glyph_id 380/916）：modern_char=""、unicode=""，
        # 身份线索放在 identity_confidence + modern_char_slot 两个字段里。
        unicode = "" if provisional else norm_cp(f"{ord(xxt_char):04X}")
        key = (unicode, shape_key)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        svg_src = Path(str(tr.get("svg_path") or ""))
        if not svg_src.is_absolute():
            svg_src = (args.traced.resolve().parent / svg_src).resolve()
        if not svg_src.is_file():
            svg_src = (args.svg_dir.resolve() / (shape_key + ".svg"))
        if not svg_src.is_file():
            stats["no_traced"] += 1
            continue
        dest = out_dir / f"{unicode}-{shape_key}.svg"
        if not dest.is_file() or dest.read_bytes() != svg_src.read_bytes():
            shutil.copyfile(svg_src, dest)
        # 合并器按「清单所在目录 + file」找字形，所以这里要写**相对清单**的路径
        rel_file = os.path.relpath(dest.resolve(), args.out.resolve().parent).replace("\\", "/")

        book_code = book.get("zdic_code", "") or lit
        number = short[len(book_code):].lstrip(".")
        # 编号按**漢典文献代号**切，与漢典层同口径：
        # 「信2.018」→ 代号「信」→ 编号「2.018」；「郭.老甲.4」→ 代号「郭」→ 编号「老甲.4」。
        # （按小學堂的標識切會得到「018」，跟漢典層拼不起來。）
        # 全称优先取层的对照表（與漢典层同一粒度），對照表裡沒有才用出處表的全称
        corpus_full = books_csv.get(book_code) or book.get("corpus_full", "")
        pages, refs = base_pages_of(inst.get("base_pages", []))

        item = {
            "file": rel_file,
            "modern_char": modern_char,
            "unicode": unicode,
            "period": "",
            "variant": (f"{modern_char}{short}" if modern_source == "zdic-shape" else short),
            "source_book": corpus_full,
            "source_number": number,
            "source_id": shape_key,
            "book_code": book_code,
            "source_path": f"{args.db}/{shape_key}.png",
            "source_url": tr.get("source_url", ""),
            "source_page_url": tr.get("source_page_url", ""),
            # 两个 sha256 都要给：local 是「清单目录里这个 SVG」的校验值，
            # source 是「上游原件（位图）」的校验值。两者不同——本地是描摹件。
            "local_sha256": tr.get("svg_sha256", ""),
            "source_sha256": tr.get("source_sha256", ""),
            "source_base_pages": pages,
            "source_references": refs,
            "derived_from": tr.get("derived_from", ""),
            "derived_from_sha256": tr.get("derived_from_sha256", ""),
            "transform": tr.get("transform", ""),
            "tool": tr.get("tool", ""),
            # 位图描摹件的保真指标（本地 SVG 与上游位图的 IoU）。
            # 随记录进 provenance，发布后仍可复核「描摹件忠实于原字形」。
            "trace_iou": tr.get("iou"),
            # 现代字身份的可信度与来路。
            #   ""                      = 站点字頭直接给出真汉字
            #   "base-page"             = 由底本页.行反查（摹本一字一行，可靠）
            #   "seal-slot"             = 由說文小篆槽位反查
            #   "base-page+seal-slot"   = 两条路都给出且一致
            #   "base-page∩seal-slot"   = 页.行多候选，槽位落在候选里
            #   "pua-slot"              = 仍未定，临时身份（码位不是汉字码位）
            "identity_confidence": ("pua-slot" if provisional else
                                    (idrec.get("confidence", "") if idrec else "")),
            # 槽位碼位：身份未定时它是唯一線索；身份是反查来的，它是旁证。
            "modern_char_slot": (inst.get("modern_char_slot", "")
                                 if (provisional or idrec) else ""),
            "modifications": tr.get("modifications", ""),
            "literature": lit,
            "modern_char_source": modern_source,
            "xxt_zi_order": inst.get("zi_order", ""),
            # 逐条带上出处信息：合并后的清单里，上层字段只来自**第一份**清单，
            # 别的来源的字形若不带自己的署名，就会被安上别人的 attribution。
            "license": "CC0-1.0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "attribution": ATTRIBUTION,
            "source_dataset": f"小学堂 {args.db} 字形資料庫",
        }
        glyphs.append(item)
        stats["new_source" if zrows else "new_shape"] += 1

    manifest = {
        # kind = 上游库的栏目名（与漢典清单同名，合并器要求两边一致）
        "kind": args.db,
        # script = 本仓库的层名（入库时用；合并后的清单取**第一份**的顶层字段）
        "script": script,
        "layer": "outline",
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "attribution": ATTRIBUTION,
        "source_dataset": f"小学堂 {args.db} 字形資料庫",
        "glyphs": sorted(glyphs, key=lambda g: (g["unicode"], g["source_id"])),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    (args.out.parent / "crosswalk.jsonl").write_text(
        "".join(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n"
                for c in crosswalk), encoding="utf-8", newline="\n")

    print(f"{args.db}: 字形 {len(glyphs)} 个"
          f"（新增字形 {stats['new_shape']} / 新增出處 {stats['new_source']}）")
    print(f"  与漢典重复 {stats['dup']} / 字頭是私用區但漢典已收 {stats['shape_known']}"
          f" / 未描摹 {stats['no_traced']} / 文献对不上 {stats['no_book']}")
    kinds = Counter(c["kind"] for c in crosswalk)
    print(f"  差异登记 {dict(kinds)}")
    print(f"  清单 {args.out}；字形目录 {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
