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

# 时代词表与时代归一**直接用漢典抓取器的那一套**（``fetch_zdic_glyphs``）——
# 两边用同一个函数，桶键才谈得上是同一个桶。不另抄一份正则。
from fetch_zdic_glyphs import canonical_era, find_era  # noqa: E402

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

# 各库的**摹本底本**（路线 D 反查身份时，底本页.行要认它）。
# 楚系层的摹本底本是《楚系簡帛文字編》，傳抄層是《傳抄古文字編》——
# 两者的页.行体系不同（前者「頁.行」，后者「冊頁.行」帶冊次），不能混用。
DB_BASE_BOOK = {
    "chuwenzi": "楚系簡帛文字編",
    "chuanchao": "傳抄古文字編",
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


# 出處簡號末尾的時代詞。隸變庫的寫法是「曹全碑 東漢」這類「碑名 + 时代」。
# 「孫吳」「新莽」「三國吳」实测也出现在隸變庫的簡號裡（「吳谷朗碑 孫吳」「新嘉量 新莽」），
# 漏了它們時代後缀就剥不掉，文档名帶著後缀去對方层永遠對不上。
ERA_SUFFIX_RE = re.compile(
    r"\s+(東漢至魏晉|三國吳|孫吳|東漢|西漢|新莽|東晉|西晉|曹魏|蜀漢|戰國|秦|漢|晉|魏|隋|唐|宋|元|明|清)\s*$")
# 編號：末尾的數字 / 點 / 字母組合（「秦51」「上351.2」「日甲131背」）。
NUM_TAIL_RE = re.compile(r"^(.*?)((?:\d+)?[.．]?[0-9A-Za-z]*[上下正反]?)$")


def split_source_short(short: str) -> tuple[str, str, str]:
    """出處簡號 → (文獻名, 編號, 時代)。

    拆不出編號時**編號留空**——不猜。用途是拿「文獻名」去**对方层**找同名的文献：
    隸變庫的出處表只列 33 種，碑刻类一个没有，但漢典 clerical 层記的就是碑名本身。
    """
    s = (short or "").strip()
    era = ""
    m = ERA_SUFFIX_RE.search(s)
    if m:
        era = m.group(1)
        s = s[:m.start()].strip()
    m2 = NUM_TAIL_RE.match(s)
    if m2 and m2.group(1):
        return m2.group(1).strip(), m2.group(2), era
    return s, "", era


def match_zdic_book(name: str, number: str,
                    zdic_books: dict[str, str]) -> tuple[str, str]:
    """在**对方层**的 ``source_book`` 里找同一件材料，返回 (文献名, 对方层的原始值)。

    两边是**同一套簡號体系**——小學堂的「睡.封95 秦」与漢典 clerical 层的「睡.封95」
    指同一条；差在三处：对方常不带時代后缀、编号写法偶有出入、部分号对方没收。
    所以接合点依次是：

    1. 把编号拼回去**全等**（「定縣竹簡13」→ 「定縣竹簡13」）；
    2. 编号拼回去对不上、但文献名本身在对方层（对方没收那一号）；
    3. 文献名是对方某个 source_book 的**前缀**（「定縣竹簡」← 「定縣竹簡10」）——
       这时取回对方那条、把它的编号剥掉，得到**文献名级**的出处。

    「对不上」多数不是缺出处，而是**粒度不同**：对方层记的是逐条编号，
    小學堂给的簡號只到文献名。实测隸變庫 24,841 條里，这样能接上 23,786 條（95.8%）。
    """
    if number:
        for cand in (name + number, name + "." + number):
            if cand in zdic_books:
                return name, zdic_books[cand]
    if name in zdic_books:
        return name, zdic_books[name]
    hit = ""
    for k in zdic_books:
        if k.startswith(name) and (not hit or len(k) < len(hit)):
            hit = k
    if hit:
        # 对方那条带编号（「定縣竹簡10」）→ 剥掉编号，留文献名级出处。
        m = NUM_TAIL_RE.match(hit)
        doc = m.group(1).strip() if (m and m.group(1)) else hit
        return doc, zdic_books[hit]
    return "", ""


# ---------------------------------------------------------------------------
# 分桶维度：**与现有层同一套口径**
#
# 现有层是怎么分桶的（实测 glyphs/<层>/index.csv）：
#
#   clerical / bronze → 每 (现代字, **时代**) 1 条，每字 6 / 8 条
#                       時代值就是 index.csv 的 period 列
#                       （bronze 25 种、clerical 11 种 + 空）
#   oracle            → 每 (现代字, **著錄號+組**) 1 条，每字 8 条
#                       也就是 source_book 列（「菁3.1 賓組」）
#   chu / chuanchao / qinwenzi → 每 (现代字, **文献**) 1 条，每字 ≤5 条
#
# 小學堂的簡號与漢典层是**同一套体系**，所以能拆到同一个桶键：
#   clerical：「曹全碑 東漢」                → 时代「東漢」
#   bronze ：「毛公鼎 西周晚期 集成2841」    → 时代「西周晚期」、编号「集成2841」
#   oracle ：「菁3.1 合10405 賓組」          → 著錄號+組「菁3.1 賓組」、编号「合10405」
#
# 时代词表**从现有层的 period 列取**，不另抄一份——两边用同一张表，
# 才谈得上「规则统一」。
# ---------------------------------------------------------------------------

BUCKET_MODES = ("book", "era", "oracle")

#: 描摹保真的**单条**门槛：低于这个 IoU 的描摹件判失败，不进层。
#: 与 ``src/check_glyphs.py --trace-fidelity`` 的判据一致（那里也是硬闸）。
TRACE_IOU_FAIL = 0.93

#: 层名 → (分桶维度, 每字上限)。**与现有层同一套**。
LAYER_RULES: dict[str, tuple[str, int]] = {
    "chu": ("book", 5),
    "chuanchao": ("book", 5),
    "qinwenzi": ("book", 5),
    "xiaozhuan": ("book", 5),
    "clerical": ("era", 6),
    "bronze": ("era", 8),
    "oracle": ("oracle", 8),
}

#: 层 → 桶键按什么算：``doc`` = 按文献（时代 / 著錄號+組 / 文献代号）；
#: ``shape`` = 按**字形键**。
#:
#: 甲骨层是 ``shape``——实测它同一著錄下**可以有多条摹本**
#: （「菁1.1合6057賓組」有两个字形：42_F4F2 与 42_F4F3），
#: 它的唯一键是 **(现代字, 字形键)**（10,213 条漢典记录里 0 重复），
#: 每字最多 8 条。按文献分桶会把这些摹本误判成重复。
LAYER_BUCKET_BY: dict[str, str] = {
    "oracle": "shape",
}

#: 金文簡號末尾的「集成NNNN」（《殷周金文集成》著錄號）。
JICHENG_RE = re.compile(r"\s*集成\s*\d+\s*$")
#: 甲骨簡號中间的「合NNNN」（《甲骨文合集》著錄號）。
HE_RE = re.compile(r"\s+合\s*\d+")


def era_vocab_of(index_path: Path | None) -> list[str]:
    """现有层的 ``period`` 列 → 时代词表（长度倒序，最长优先匹配）。"""
    vocab: list[str] = []
    if not index_path or not index_path.is_file():
        return vocab
    with index_path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            p = (row.get("period") or "").strip()
            if p and p not in vocab:
                vocab.append(p)
    vocab.sort(key=len, reverse=True)
    return vocab


def split_source_fields(short: str, mode: str, era_vocab: list[str]) -> tuple[str, str, str, str]:
    """出處簡號 → (文献名, 编号, 时代, 分桶键)。**按层同一套口径**。

    - ``book``   → (简号原文, "", "", "")：文献与分桶由文献代号表决定
    - ``era``    → 金文「毛公鼎 西周晚期 集成2841」→ ("毛公鼎", "集成2841", "西周晚期", "西周晚期")
    - ``oracle`` → 甲骨「菁3.1 合10405 賓組」→ ("菁3.1 賓組", "合10405", "", "菁3.1 賓組")

    时代认不出来就退到**文献名本身**当桶键（漢典那边叫「器名 + 编号」）：
    印谱（《漢印徵》）、器名紧贴时代没切开的那批都落在这儿。

    **时代怎么认。** 先用漢典抓取器的 ``find_era``（它认的是「最后一段就是时代」
    或「时代后面跟着编号」这两种形状）；它认不出的时候退到**词元比对**——
    拿现有层 ``period`` 列里的时代词表逐个词元比，认得出就用。
    词表从现有层取，两边用同一张表，才谈得上「规则统一」。
    """
    s = (short or "").strip()
    if mode == "book":
        return s, "", "", ""
    if mode == "oracle":
        m = HE_RE.search(s)
        number = ""
        if m:
            number = m.group(0).strip()
            s = HE_RE.sub(" ", s)
        doc = re.sub(r"\s+", " ", s).strip()
        return doc, number, "", doc
    # mode == "era"
    span = _find_era_span(s, era_vocab)
    if span is None:
        return s, "", "", _material(s, "")
    era_raw, start, end = span
    era = canonical_era(era_raw)
    doc = s[:start].strip()
    number = s[end:].strip()
    return doc, number, era, (era or _material(doc, number))


def _material(doc: str, number: str) -> str:
    """文献名 + 编号 → **材料键**（去掉所有空白，两边的写法差异就抹平了）。

    漢典的题记里没有空格（「㐭老子乙前93下西漢」），小學堂的簡號有
    （「老子甲5 西漢」）；去掉空白之后两边才能对上。
    """
    return re.sub(r"\s+", "", (doc or "") + (number or ""))


def _find_era_span(s: str, era_vocab: list[str]) -> tuple[str, int, int] | None:
    """在簡號里定位时代 → (原样时代, 起点, 终点)。找不到返回 None。"""
    hit = find_era(s)
    if hit:
        return hit
    if not era_vocab:
        return None
    # 词元比对：整个词元就是时代，或词元以某个时代开头（「東漢至魏晉」）。
    offset = 0
    for token in s.split(" "):
        start = s.find(token, offset)
        if start < 0:
            continue
        offset = start + len(token)
        if token in era_vocab:
            return token, start, start + len(token)
        for e in era_vocab:
            if len(e) >= 2 and token.startswith(e):
                return e, start, start + len(e)
    return None


def bucket_of_zdic_row(row: dict, mode: str, bucket_by: str = "doc") -> str:
    """现有层的一行 → 它的桶键（与 ``split_source_fields`` 的第四项同一口径）。

    **与漢典抓取器的 ``era_bucket`` 同一个规则**：有时代就用归一后的时代，
    没有时代就退到「器名 + 编号」。时代归一也用同一个 ``canonical_era``。

    ``bucket_by="shape"`` 时桶键改用**字形键**（``source_id``）——
    甲骨层是这一档：同一著錄下**可以有多条摹本**
    （「菁1.1合6057賓組」有两个字形：42_F4F2 与 42_F4F3），
    它的唯一键是 **(现代字, 字形键)**，按文献分桶会把这些摹本误判成重复。
    """
    if bucket_by == "shape":
        return (row.get("source_id") or "").strip()
    if mode == "era":
        period = (row.get("period") or "").strip()
        if period:
            return canonical_era(period)
        return ((row.get("source_book") or "").strip()
                + (row.get("source_number") or "").strip())
    if mode == "oracle":
        return (row.get("source_book") or "").strip()
    return (row.get("book_code") or "").strip()


def _confidence_of(sel: dict | None, idrec: dict | None, provisional: bool) -> str:
    """这条记录的身份可信度（写进 provenance 的 ``identity_confidence``）。

    词表见 AGENTS.md：``""`` / ``base-page`` / ``seal-slot`` /
    ``base-page+seal-slot`` / ``base-page∩seal-slot`` / ``shape-key`` / ``pua-slot``。

    - 临时身份 → ``pua-slot``；
    - 由反查表补回 → 用反查表那一档（``base-page`` 等）；
    - 由**字形键**定出（漢典层这个字形只挂一个现代字）→ ``shape-key``。
    """
    if provisional:
        return "pua-slot"
    if idrec:
        return str(idrec.get("confidence", "") or "")
    if sel and str(sel.get("identity_confidence") or "") == "shape-key":
        return "shape-key"
    return ""


def strip_variant(v: str, codes: list[str]) -> str:
    """漢典 variant = 異體字（一个）+ 出處簡號。    為什麼不能只看「已知標識前綴」：異體字本身也可能是漢字，而且可能**恰好**
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


def base_pages_of(references: list[str], base_book: str = "") -> tuple[str, str]:
    """從「相關索引」裡拆出 (底本页.行, 底本清單)。

    底本页.行取**该层的摹本底本**那條——楚系層是《楚系簡帛文字編》，
    傳抄層是《傳抄古文字編》。粒度與漢典層的 ``source_base_pages`` 一致
    （實測 53/53 逐條相同）。底本清單則是全部相關索引。

    ``base_book`` 留空時按楚系底本處理（老接口的默認值）。

    **只认指定底本那一条。** 同一份字頭的相關索引里还列着《睡虎地秦簡文字編》
    《傳抄古文字編》等别的底本，粒度不同，混进来会错配：
    實測楚系層有 14 條字頭的相關索引里《睡虎地秦簡文字編》排在《楚系簡帛文字編》
    之前，取錯了就配不上漢典層（漢典層的 ``source_base_pages`` 从不出现那些值）。
    """
    pages = ""
    refs = list(references)
    books = (base_book,) if base_book else ("楚系簡帛文字編",)
    for item in references:
        if any(b in item for b in books):
            m = re.search(r"冊?頁[.．]?行[：:]\s*([^\s，,；;]+)", item)
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
                    help="漢典层 index.csv：用来对齐異體字与识别重复。"
                         "**优先用 --zdic-manifest**（合并时用的同一份基线）——"
                         "拿层现在的 index.csv 当基线会把上一轮并进来的小學堂批次"
                         "判成重复，清单就空了")
    ap.add_argument("--zdic-manifest", type=Path, default=None,
                    help="漢典侧的**基线清单**（重建清单或抓取器的原始输出）："
                         "判「层里有没有这一条」用它，与合并阶段同一份")
    ap.add_argument("--identity-map", type=Path, default=None,
                    help="私用區身份反查表（resolve_pua_identity.py 的输出）："
                         "给私用區字頭补回真漢字碼位")
    ap.add_argument("--selection", type=Path, default=None,
                    help="取图阶段的选取记录（plan_xxt_fetch.py --out-selection）："
                         "**按同一份选择走**——分桶规则与每字上限是在取图阶段算的，"
                         "清单阶段不再另挑一遍；记录里的身份也直接沿用")
    ap.add_argument("--font-allow", default=None,
                    help="只收字体名以此开头的实例（逗号分隔多个）。"
                         "**书体由字体决定，不由材料决定**：隸變库里同時有"
                         "「中研院隸書重文」與「中研院秦系簡牘文字重文」兩種字体，"
                         "前者是隸書字形（歸隸書層），後者是秦系字形（歸秦系層）")
    ap.add_argument("--bucket", choices=BUCKET_MODES, default=None,
                    help="分桶维度（默认按层定，见 LAYER_RULES）："
                         "book = 每 (现代字, 文献) 1 条；"
                         "era = 每 (现代字, 时代) 1 条（clerical / bronze 层）；"
                         "oracle = 每 (现代字, 著錄號+組) 1 条（甲骨层）。"
                         "era / oracle 两种**不从出處表取文献**，"
                         "而是把簡號自己拆成 (文献名, 编号, 时代)——"
                         "隸變库的出處表只列 31 种，靠它分桶会把九成实例丢掉")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="字形文件输出目录（默认 <out 所在目录>/files）")
    ap.add_argument("--layer", default=None,
                    help="目标层名（默认按库名推断）。一个库可能喂多个层"
                         "（隸變库按字体拆成隸書层与秦系层），"
                         "层名决定**分桶维度与每字上限**（见 LAYER_RULES）")
    args = ap.parse_args(argv)

    script = DB_SCRIPT.get(args.db)
    if not script:
        raise SystemExit(f"未知库：{args.db}")

    # 分桶维度：**按现有层同一套口径**（LAYER_RULES）。
    layer_name = args.layer or script
    bucket_mode = args.bucket or LAYER_RULES.get(layer_name, ("book", 5))[0]
    era_vocab = era_vocab_of(args.zdic_index) if bucket_mode == "era" else []

    books_rows: dict[str, dict] = {}
    codes: list[str] = []
    if args.books_xxt:
        books_rows, codes = load_books_xxt(args.books_xxt.resolve())
        if not books_rows and bucket_mode == "book":
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
    # 漢典层的**文献名 → 全称**：自己的出處表對不上时的兜底。
    # 隸變库的出處表只列 33 種（碑刻类一个没有），但漢典 clerical 层记的就是碑名本身。
    zdic_books: dict[str, str] = {}
    if args.zdic_manifest and args.zdic_manifest.is_file():
        # **基线用漢典那份清单**（合并时用的同一份）。
        #
        # 为什么不能拿「层现在的 index.csv」当基线：**层里已经含有上一轮并进来的
        # 小學堂批次**。拿它判「层里有没有这一条」，小學堂那批会把自己
        # 判成重复 → 清单出来是空的（实测：20,674 条的层，重跑清单得 0 条）。
        #
        # 基线必须是**合并前的那份漢典清单**：
        #   - 现有层（oracle / bronze / clerical）：重建清单（tmp/zdic/<层>-rebuilt）；
        #   - 新层（傳抄）：抓取器的原始输出（tmp/zdic/chuanchao-full）。
        # 合并阶段用的也是同一份，两边口径一致。
        data = json.loads(args.zdic_manifest.read_text(encoding="utf-8"))
        for g in data.get("glyphs", []):
            sid = str(g.get("source_id") or "").strip()
            if not sid:
                continue
            z_by_shape[sid].append(g)
            name = str(g.get("source_book") or "").strip()
            if name and name not in zdic_books:
                zdic_books[name] = name
    elif args.zdic_index and args.zdic_index.is_file():
        with args.zdic_index.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                # 字形键为空的那几行（JGW 批当年就是这么记的）**不归到空键下**——
                # 空键会把上千行堆在一起，看着像「一个字形挂着上千个现代字」。
                sid = (row.get("source_id") or "").strip()
                if sid:
                    z_by_shape[sid].append(row)
                name = (row.get("source_book") or "").strip()
                if name and name not in zdic_books:
                    zdic_books[name] = name

    instances = load_jsonl(args.index.resolve())
    traced = {r["shape_key"]: r for r in load_jsonl(args.traced.resolve())}

    # **取图阶段的选取记录**（plan_xxt_fetch.py --out-selection）。
    #
    # 为什么必须用它：**分桶规则与每字上限是在取图阶段算的**——
    # 「每 (现代字, 桶键) 留一条」「每字不超过上限」「重叠处漢典优先」，
    # 这三条都在那张表里定死了。清单阶段若自己再算一遍，两边的口径就会分家
    # （分桶维度、时代归一、每字上限都得各自维护一份），合并出来的层
    # 就可能超限或重复。**按同一份选择走**，抓的时候选一套、入库用同一套。
    #
    # 表里同时记了每个字形的**身份**（现代字码位，或临时身份的槽位），
    # 清单阶段直接用它，不再各算各的。
    selection: dict[str, dict] = {}
    if args.selection and args.selection.is_file():
        for rec in load_jsonl(args.selection.resolve()):
            sk = str(rec.get("shape_key") or "").strip()
            if sk:
                selection[sk] = rec

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

        # **取图阶段的选取结果说了算**：没被选中的字形不进这一层。
        #
        # 分桶规则（「每 (现代字, 桶键) 留一条」）与每字上限是在取图阶段算的；
        # 清单阶段若自己再挑一遍，两边的口径就会分家，层里可能出现超限或重复。
        sel = selection.get(shape_key)
        if selection and sel is None:
            stats["not_selected"] = stats.get("not_selected", 0) + 1
            continue
        sel_slot = ""
        if sel is not None:
            # 选取记录里的身份是**现代字码位**（或临时身份的槽位）。
            ident = str(sel.get("identity") or "").strip()
            if ident.startswith("slot:"):
                # 临时身份：现代字未知，槽位是唯一线索。
                xxt_char = ""
                sel_slot = ident[5:]
            elif ident:
                try:
                    xxt_char = chr(int(ident, 16))
                except ValueError:
                    xxt_char = ""

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
        # **描摹保真不合格的件不入库**。
        #
        # 单条门槛（AGENTS.md）：IoU ≥ 0.97 合格、0.93–0.97 警戒、< 0.93 判失败。
        # 判失败的件**不进这一层**——发布一件自己都测不出忠实度的描摹件，
        # 等于把「忠实于原字形」这句承诺打折。层级门槛（p05 ≥ 0.96、失败率 ≤ 1%）
        # 是另一道闸：它管的是整层的成色，不替代单条闸。
        iou = tr.get("iou")
        if iou is not None and float(iou) < TRACE_IOU_FAIL:
            stats["trace_iou_failed"] = stats.get("trace_iou_failed", 0) + 1
            continue
        lit, book = resolve_literature(short, books_rows)
        src_number = ""
        src_era = ""
        if bucket_mode == "book":
            if not lit or book is None:
                # **自己的出處表對不上，先查对方层。**
                #
                # 「對不上表」不等于「没出處」——隸變库实测：13,403 条對不上小學堂那 31 種的表，
                # 但两边是**同一套簡號体系**（「睡.封95」两边写法一样），差的是粒度：
                # 漢典 clerical 层记的是逐条编号（「定縣竹簡10」），小學堂的簡號只到文献名。
                # 實測 24,841 條里这样能接上 23,786 條（95.8%），真正两边都沒有的只有 1,055 條。
                # **兩邊都沒有才是不收**——那時登记在 crosswalk 里备查。
                name, number, era = split_source_short(short)
                doc, zbook = match_zdic_book(name, number, zdic_books)
                if doc:
                    lit = doc
                    book = {"code": doc, "corpus_full": doc, "zdic_code": doc}
                    stats["book_from_zdic"] = stats.get("book_from_zdic", 0) + 1
                else:
                    stats["no_book"] += 1
                    crosswalk.append({
                        "kind": "unresolved_literature", "shape_key": shape_key,
                        "source_short": short,
                        "note": "出處簡號對不上出處表，且对方层也没有同名文献，未收",
                    })
                    continue
        else:
            # **时代 / 著錄分桶**：文献、编号、时代都从簡號自己拆——
            # 与 plan_xxt_fetch.py 的分桶用的是同一个函数（split_source_fields），
            # 抓哪几张位图与入库时怎么记，必须是同一套口径。
            doc, src_number, src_era, _bucket = split_source_fields(short, bucket_mode,
                                                                   era_vocab)
            if not doc:
                stats["no_book"] += 1
                continue
            lit = doc
            book = {"code": doc, "corpus_full": doc, "zdic_code": doc}

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
        if bucket_mode != "book":
            # 时代 / 著錄分桶：编号与时代都从簡號拆出来的，不按文献代号切。
            number = src_number
        # 编号按**漢典文献代号**切，与漢典层同口径：
        # 「信2.018」→ 代号「信」→ 编号「2.018」；「郭.老甲.4」→ 代号「郭」→ 编号「老甲.4」。
        # （按小學堂的標識切會得到「018」，跟漢典層拼不起來。）
        # 全称优先取层的对照表（與漢典层同一粒度），對照表裡沒有才用出處表的全称
        corpus_full = books_csv.get(book_code) or book.get("corpus_full", "")
        pages, refs = base_pages_of(inst.get("base_pages", []),
                                    DB_BASE_BOOK.get(args.db, ""))

        item = {
            "file": rel_file,
            "modern_char": modern_char,
            "unicode": unicode,
            "period": src_era,
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
            #   "shape-key"             = 由字形键定出（漢典层这个字形只挂一个现代字）
            #   "pua-slot"              = 仍未定，临时身份（码位不是汉字码位）
            "identity_confidence": _confidence_of(sel, idrec, provisional),
            # 槽位碼位：身份未定时它是唯一線索；身份是反查来的，它是旁证。
            "modern_char_slot": ((sel_slot or str(inst.get("modern_char_slot") or ""))
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
        # kind = **书体（层名）**：与漢典清单同名，合并器要求两边一致。
        # **不是库名**——库名与层名不是一回事（「jinwen」这个库喂的是「bronze」层，
        # 「lishu」喂的是「clerical」层）。写错合并器会直接报错：
        # 「要合并的清单书体不一致」。
        "kind": layer_name,
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
