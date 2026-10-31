#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从汉典（zdic.net）抓取某一书体的书法字形实例，落成本地字形 + 清单。

用法::

    python src/fetch_zdic_glyphs.py --script jinwen --chars-file <字表.txt> --out tmp/zdic/jinwen
    python src/fetch_zdic_glyphs.py --script lishu --from-seal-registry --out tmp/zdic/lishu
    python src/fetch_zdic_glyphs.py --script jinwen --from-seal-registry --out tmp/zdic/jinwen \
        --per-char 8 --max-per-era 1

产出::

    <out>/<码位>-<来源编号>.svg   逐字节副本（单 path 填充轮廓，viewBox 0 0 400 400）
    <out>/manifest.json           给 src/import_glyph_layer.py 用的清单

**为什么是汉典。** 汉典《服务条款》第四条：「汉典奉行 CC0 1.0 公约，将本站字词、
古籍、诗词、**书法诸作**，悉数贡献天下，放弃著作专权及邻接法益，任人取用，以公无穷。」
（<https://www.zdic.net/terms/>，2026-10-30 核验）。每个字有一页「书法」实例，
逐件标注**出处作品 + 编号 + 时代**，例如「日 戈厚作兄日辛簋 集成3665 商代晚期」。

**一字多形，所以按实例选，不按字选。** 同一字在汉典有十几个到几十个实例
（甲骨文的「日」有 41 件，隶书的「日」有 47 件），分属不同时代与器物。
选取规则是**每个时代最多取 1 个实例**（``--max-per-era 1``），
时代桶按年代顺序**均匀**取（不是从头取，否则晚期整段被砍）。
实例的来源信息（作品、编号、时代）全部写进清单，落到 provenance 里。

**题记配对按 DOM 块，不按出现顺序。** 异体字页给两条 caption，
按出现顺序配对会整体错位一格（见 ``parse_instances`` 的说明）。

**已知残余风险（要如实写进 THIRD_PARTY_NOTICES.md）。** 汉典的这些字形本身是
「摹本 + 矢量化」的产物，底本多为现代出版物（《殷周金文集成》《睡虎地秦简文字编》
《秦汉魏晋篆隶字形表》等），这些书的著作权不因汉典的 CC0 宣告而消灭。本仓库的做法
与甲骨层一致：**接受并如实标注这条链条**，逐条记清底本与编号。
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import inspect
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HOST = "img." + "zdic.net"          # 拆开写，免得被当成网络共享路径
REFERER = "https://www.zdic.net/"

LICENSE = "CC0-1.0"
LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
TERMS_URL = "https://www.zdic.net/terms/"
ATTRIBUTION = (
    "字形来自汉典（zdic.net）「书法」字形，依其《服务条款》第四条以 CC0 1.0 释出"
)

# 各书体在汉典的实例页路径。
KIND_PATHS = {
    "jinwen": "jinwen",
    "lishu": "lishu",
    "xiaozhuan": "xiaozhuan",
    "jiaguwen": "jiaguwen",
    "chuanchao": "chuanchao",
    "chuwenzi": "chuwenzi",
    "qinwenzi": "qinwenzi",
}

# 抓取用的书体名 → 仓库里的层目录名。
# 两者不是一回事：汉典叫「chuwenzi」，本仓库叫「chu」（目录名用短名）。
LAYER_DIRS = {
    "jinwen": "bronze",
    "lishu": "clerical",
    "xiaozhuan": "seal",
    "jiaguwen": "oracle",
    "chuwenzi": "chu",
    "chuanchao": "chuanchao",
    "qinwenzi": "qinwenzi",
}

# 各书体的时代偏好（按顺序命中）。同字多实例时取第一个命中的。
# 注意：汉典的出处说明用**繁体**时代名（東漢、西漢、戰國），简体写法匹配不上，
# 所以偏好表里两种写法都列。
DEFAULT_PREFERENCE = {
    "jinwen": "西周中期,西周早期,西周晚期,商代晚期,商代中期,春秋,戰國,战国",
    "lishu": "東漢,东汉,西漢,西汉,魏晉,魏晋,曹魏,新,秦,晉,晋,魏,漢,汉",
    "xiaozhuan": "",
    "jiaguwen": "商代晚期,商代中期,西周早期,西周",
    "chuanchao": "",
    "chuwenzi": "",
    "qinwenzi": "",
}

# 各书体偏好的**出处片段**，先于时代偏好匹配。
# 小篆页上同一个字常有「說文‧X部」（正篆）与「說文古文」（古文）两个实例，
# 正篆才是《说文》该字条目的写法，古文是另一个形式——取错会让字形对不上码位。
DEFAULT_CAPTION_PREFERENCE = {
    "xiaozhuan": ["說文‧", "說文·"],
}

CAPTION_RE = re.compile(r'class="caption"[^>]*>(.*?)</div>', re.S)
IMAGE_RE_TMPL = r"{host}/zy/{kind}/([A-Za-z0-9_]+)\.svg"
# 每个字形实例块的起始标记。图与题记的配对靠它分块，不能靠出现顺序。
GLYPH_ITEM_MARKER = '<div class="glyph-item">'
# 页面底部的「参考文献」段：摹本底本 + 页.行（底本著作权链条的证据）。
REF_SECTION_RE = re.compile(r'<div class="ref-section">(.*?)</ol>', re.S)
REF_ITEM_RE = re.compile(r"<li>(.*?)</li>", re.S)

# 决定「选哪些实例」的函数。改了这几个里的任何一个，选出来的实例就变了，
# 续跑缓存必须作废（见 selection_fingerprint）。
SELECTION_FUNCTIONS = (
    "parse_instances", "pick_instances", "canonical_era", "era_bucket",
    "parse_caption", "find_era", "parse_era",
)

# 同样决定选取的**常量**：时代表、时代正则、编号正则、题记正则、分块标记。
# 少了它们，改了规则续跑还会沿用旧缓存——已查过的字不按新规则重选。
SELECTION_CONSTANTS = (
    "ERA_CHRONOLOGY", "ERA_QUALIFIERS", "ERA_SIMPLIFIED", "ERA_RE",
    "ERA_TAIL_RE", "NUMBER_RE", "CAPTION_RE", "IMAGE_RE_TMPL",
    "GLYPH_ITEM_MARKER", "DEFAULT_PREFERENCE", "DEFAULT_CAPTION_PREFERENCE",
)

# 汉典的出处说明形如「一曶鼎 集成2838 西周中期」：现代字 + 器物名 + 编号 + 时代。
# 字与器名之间有没有空格取决于 HTML 里两个元素之间有没有空白，
# 所以按「时代」和「编号」这两个有固定形状的部分来切，比按空格切可靠。
ERA_RE = re.compile(
    r"(?:商代|西周|春秋|戰國|戰国|秦|西漢|西汉|東漢|东汉|魏晉|魏晋|曹魏|蜀漢|蜀汉|東吴|東吳|孫吴|孫吳"
    r"|西晉|西晋|東晉|東晋|新莽|漢|汉|魏|晉|晋|新|三國|三国"
    r"|隋|唐|宋|元|明|清)"
    r"(?:晚期|早期|中期|前期|後期|后期|偏晚|偏早|末年|初年"
    r"|或(?:西周|春秋|戰國|戰国|商代|秦|漢|汉)?(?:早期|中期|晚期)?"
    r"|(?:早期|中期|晚期)或(?:西周|春秋|戰國|戰国|商代)?(?:早期|中期|晚期)?)*"
)
# 编号：集成/页/卷/第…这类「集合号 + 序号」。
# 编号：集成/页/卷/第…这类「集合号 + 序号」。
# 甲骨文的合号（「合1285」，《甲骨文合集》编号）也算；拓片号（「乙3400」「前2.40.7」）
# 留在器物说明里——它跟卜辞组别（「賓組」）是一体的，一起当器物说明更合适。
NUMBER_RE = re.compile(
    r"(?:集成|页|頁|第|卷|图|圖|编|編|册|冊|冊頁|帖|新收|新著|續|续|補|补|合)"
    r"\s*[0-9０-９]+(?:\s*[-–—~至]\s*[0-9０-９]+)*"
)
# 时代后面通常紧跟编号或结束，用来排除器名里的误命中（如「秦公簋」）。
# 也允许「书名+页」的形式（如「首陽114頁」）。
# 丛书编号的写法很多（「三代八／五十一」「總集06.4800」「考古96.9」「周金三／四十一」
# 「上博七」「中國歷史文物06.3」），都要认，否则时代会整段留在器物名里。
ERA_TAIL_RE = re.compile(
    r"^(?:集成|页|頁|第|卷|图|圖|编|編|册|冊|帖|新收|新著|續|续|補|补"
    r"|總集|总集|考古|文博|文物|近出|上博|周金|三代|中國歷史文物|中国历史文物"
    r"|考古與文物|考古与文物|考古學報|考古学报|集成叢書|集成丛书"
    r"|[0-9０-９]"
    r"|[^ ]*頁|[^ ]*页|$)"
)


def find_era(text: str) -> tuple[str, int, int] | None:
    """找出时代，并给出它在文本中的位置。

    先看最后一个空格分段（多数情况时代就是最后一段），再退到全文检索。
    检索时要求时代后面跟着编号或到头，避免把器名里的「秦」「汉」当成时代。

    返回 (时代, 起点, 终点)，起点终点是相对 ``text`` 的下标；找不到就返回 None。
    """
    tokens = text.split()
    if tokens:
        last = tokens[-1]
        if ERA_RE.fullmatch(last):
            idx = text.rfind(last)
            return last, idx, idx + len(last)
    for match in ERA_RE.finditer(text):
        if ERA_TAIL_RE.match(text[match.end():].strip()):
            return match.group(0), match.start(), match.end()
    return None


def parse_era(caption: str) -> str:
    hit = find_era(flat(caption))
    return hit[0] if hit else ""


# 时代的年代顺序。「一字多形」时按这个顺序取时代，先取早的、再取晚的，
# 拼出来才是一条演变链而不是一堆同代字形。
ERA_CHRONOLOGY = {
    "jinwen": ["商代中期", "商代晚期", "西周早期", "西周", "西周中期", "西周晚期",
               "春秋早期", "春秋", "春秋中期", "春秋晚期",
               "戰國早期", "戰國", "戰國中期", "戰國晚期"],
    "lishu": ["秦", "新莽", "西漢", "東漢", "曹魏", "孫吳", "西晉", "晉", "魏晉"],
}

# 「A或B」「A偏晚」这类复合时代归到 A：「或」是断代区间，取最早的那一段；
# 「偏晚/偏早/末年/初年」只是同一段里的更细，仍算同一段。
ERA_QUALIFIERS = ("偏晚", "偏早", "前期", "後期", "后期", "末年", "初年")

# 时代名有简繁两写。年代顺序表里只有繁体，简体名不归一就会排到桶序末尾，
# 名额一满先被砍掉。汉字时代名就这几个字，映射写死即可。
ERA_SIMPLIFIED = {
    "战国": "戰國", "西汉": "西漢", "东汉": "東漢", "魏晋": "魏晉",
    "西晋": "西晉", "东晋": "東晉", "蜀汉": "蜀漢", "东吴": "東吳",
    "孙吴": "孫吳", "三国": "三國", "汉": "漢", "晋": "晉", "吴": "吳",
}


def canonical_era(era: str) -> str:
    """把复合时代归一到一个标准时代。"""
    if not era:
        return ""
    if "或" in era:
        era = era.split("或")[0]
    for qualifier in ERA_QUALIFIERS:
        if era.endswith(qualifier):
            era = era[: -len(qualifier)]
            break
    return ERA_SIMPLIFIED.get(era, era)


def era_bucket(detail: str, modern_char: str = "") -> str:
    """字形实例的时代分组键。

    有时代就用归一后的时代；没有时代（印谱、器名紧贴时代没切开的），
    退到「器名 + 编号」——出处说明总以现代字开头，去掉它就是器物说明。
    同一件器物（编号相同）落进同一个桶，《漢印徵》那种没编号的十几个实例
    也会落进同一个桶；而金文里「集成」号不同的两件器物是两个桶，
    因为那本来就是两件不同的器物、两种不同的写法。
    """
    era = canonical_era(parse_era(detail))
    if era:
        return era
    rest = detail
    if modern_char and rest.startswith(modern_char):
        rest = rest[len(modern_char):].strip()
    return rest or detail


def parse_caption(caption: str, modern_char: str) -> dict[str, str]:
    """把出处说明拆成「器名 / 编号 / 时代」三段。

    汉典的说明串里现代字总是第一个字（后面可能直接接器名，如「一曶鼎」），
    所以先摘掉这个字，再按编号与时代的固定形状切剩下的部分。

    **按位置切，不按字符串替换。** 器名里可能本来就含时代字（「秦公簋」），
    用 ``replace`` 会打散器名；这里按区间删除，删完剩下的就是器名。
    """
    text = flat(caption)
    offset = len(modern_char) if modern_char and text.startswith(modern_char) else 0
    rest = text[offset:].strip()

    hit = find_era(text)
    era = hit[0] if hit else ""

    spans: list[tuple[int, int]] = []
    if hit:
        start, end = hit[1] - offset, hit[2] - offset
        if 0 <= start < end <= len(rest):
            spans.append((start, end))

    number = ""
    number_match = NUMBER_RE.search(rest)
    if number_match:
        number = flat(number_match.group(0))
        spans.append((number_match.start(), number_match.end()))

    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    pieces: list[str] = []
    prev = 0
    for start, end in merged:
        pieces.append(rest[prev:start])
        prev = end
    pieces.append(rest[prev:])
    artifact = flat("".join(pieces))
    return {"artifact": artifact, "number": number, "era": era}


def parse_references(html: str) -> list[str]:
    """取页面底部的「参考文献」段：这份字形所依据的**摹本底本 + 页.行**。

    汉典在每个「书法」实例页底部列了这一段，例如楚文字的「月」字：

    - 《楚系簡帛文字編》（增訂本）（湖北教育出版社），頁.行：655.9、658.10
    - 《睡虎地秦簡文字編》（文物出版社）頁.行：106.2
    - 《秦簡牘文字編》（福建人民出版社）頁：202
    - 《戰國古文字典：戰國古文聲系》（中華書局）冊頁：下911、上816

    **这一段是底本著作权链条的证据**：汉典的 CC0 放弃的是汉典自己的权利，
    不消灭这些摹本底本的著作权。逐条记下来，才谈得上「如实标注链条」。
    """
    section = REF_SECTION_RE.search(html)
    if not section:
        return []
    out: list[str] = []
    for item in REF_ITEM_RE.findall(section.group(1)):
        text = flat(re.sub(r"<[^>]+>", " ", item))
        if text:
            out.append(text)
    return out


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_char(caption: str, modern_char: str) -> str:
    """去掉题记开头的现代字。

    汉典的题记总以现代字开头（主 caption）或以器物说明开头（副 caption），
    副 caption 正好等于主 caption 去掉现代字前缀——这条不变量用来判断
    「这个实例取自双 caption 页，取的是第一条」。
    """
    text = flat(caption)
    if modern_char and text.startswith(modern_char):
        return text[len(modern_char):].strip()
    return text


# 楚文字的题记格式与其它书体不同：没有时代，结构是
# 「现代字 + 出土文献代码 + [册号/篇名] + 位置编号」，例如
#   「橎新甲3.318」   → 文献代码「新甲」，位置 3.318
#   「𠅞郭.語2.26」   → 文献代码「郭」，篇名「語」，位置 2.26
#   「上(1).性.28」   → 文献代码「上」，册号 (1)，篇名「性」，位置 28
#   「日帛甲7.10」   → 文献代码「帛甲」，位置 7.10
#   「𠅞天策」       → 文献代码「天策」，无位置
# 所以不能用「时代 + 编号」的切法，单独一个解析器。
# **文献代码一律按上游原文记**，不替它猜是哪部书；对照表在 glyphs/chu/books.csv。
#
# 代码取「开头 1~2 个汉字 + 后面紧跟数字/括号/点」：
#   「包2.273」→包（1 字，后面是数字）；「包牘1」→包牘（2 字，后面是数字）。
# 万一代码后面跟的是汉字（「香中大.1」），退回取开头连续的汉字（最多 4 个）。
CHU_TAIL_RE = re.compile(r"^([\u3400-\u9fff]{1,2}?)(?=[0-9.(（]|$)")
CHU_TAIL_FALLBACK_RE = re.compile(r"^([\u3400-\u9fff]{1,4})")
CHU_PART_RE = re.compile(r"^(\([^)]*\))?\.?([\u3400-\u9fff]+)?")


# 摹本底本的页.行定位。
#
# 汉典字页底部的「参考文献」段是**逐字**的，不是逐实例的：同一个字在汉典
# 各书体栏下用到的底本各记一条，页.行是那个字在那本书里的位置。原文形如
#   「《楚系簡帛文字編》（增訂本）（湖北教育出版社），頁.行：559.2；《睡虎地秦簡文字編》……」
# 楚系簡帛栏的字形，摹本底本就是《楚系簡帛文字編》（增訂本），所以把那条
# 单独抽出来记成 `source_base_pages`：
#   —— 这条字形的摹本底本定位（**字级**：同字有多个实例时含各实例的页）。
# 其余条目属于汉典别的书体栏（秦系簡牘 / 傳抄古文 / 隸書 / 篆書），
# 留在 `source_references` 里备查，**不能**当成这条字形的底本定位。
CHU_BASE_BOOK = "《楚系簡帛文字編》"
CHU_BASE_PAGES_RE = re.compile(r"頁[.．]?\s*行[：:]\s*([^；]+)")


def chu_base_pages(references: str) -> str:
    """从字级参考书目里取出《楚系簡帛文字編》那一条的页.行。

    找不到就返回空串——不猜。取不到说明这个字在楚系摹本底本里没有定位，
    空着比编一个页码诚实。
    """
    if not references:
        return ""
    for entry in str(references).split("；"):
        if CHU_BASE_BOOK not in entry:
            continue
        m = CHU_BASE_PAGES_RE.search(entry)
        if m:
            return m.group(1).strip()
    return ""


# 傳抄古文的源书代号表。
#
# **代号没有统一形状**：「海」「四」是一个字，「京一」「汗目」「說籀」是两个，
# 「大嚮記碑」是四个——所以不能按字数切，只能靠**已知代号表**从长到短试。
# 表是实测 3,410 条题记得到的（见 tmp/research/qin-chuanchao.md）。
# 各代号具体指哪部书**未证实**，按仓库惯例一律按上游原文记，不替它猜。
CHUANCHAO_BOOK_CODES = (
    "大嚮記碑", "說籀", "汗目", "京一", "京二", "石附", "石補",
    "海", "四", "汗", "石", "三", "碧", "陰", "隸", "說", "合",
    "陽", "磚", "施", "所", "宋", "金",
)

# 位置编号：数字（可带小数点），可跟一个方位字（上下正反）。
CHUANCHAO_LOC_RE = re.compile(r"^\d+(?:\.\d+)*[上下正反]?")
# 汉字之间的空格是 HTML 排版留下的（「丠汗 目」），不是题记的一部分。
CJK_SPACE_RE = re.compile(r"(?<=[\u3400-\u9fff]) +(?=[\u3400-\u9fff])")


def parse_caption_chuanchao(caption: str, modern_char: str) -> dict[str, str]:
    """把傳抄古文题记切成「源书代号 / 位置编号 / 尾注」。

    与其它书体不同，傳抄古文题记里**没有时代**——它是「漢以後歷代輾轉抄寫的
    先秦文字」，本身就没有单一时代，汉典也没标。所以 ``era`` 一律为空，
    分类维度是**源书代号**。

    题记的形状是「现代字 + 源书代号 + [位置编号] + [尾注]」：

    - ``日汗3.34說``  → 代号「汗」，位置「3.34」，尾注「說」
    - ``日海5.9``     → 代号「海」，位置「5.9」
    - ``日石8上``     → 代号「石」，位置「8上」（方位字算位置的一部分）
    - ``日四3.22孝（說）`` → 代号「四」，位置「3.22」，尾注「孝（說）」
    - ``㪤碧``        → 代号「碧」，无位置

    **尾注原样保留。** 末尾那个字（老 / 孝 / 尚 / 說 / 裴…）语义未证实，
    可能是同源书的篇名或上下文标记；不解释、不丢掉，原样存进 ``book_part``。
    """
    text = flat(caption)
    offset = len(modern_char) if modern_char and text.startswith(modern_char) else 0
    rest = CJK_SPACE_RE.sub("", text[offset:].strip())
    if not rest:
        return {"artifact": "", "number": "", "era": "", "book_code": "", "part": ""}

    # 代号：从长到短试已知代号表。
    code = ""
    for candidate in CHUANCHAO_BOOK_CODES:
        if rest.startswith(candidate):
            code = candidate
            break
    if not code:
        # 表里没有：按「开头连续的汉字」兜底，最多 3 个。
        # 记成原文代码，不猜是哪部书。
        head = re.match(r"^([\u3400-\u9fff]{1,3})", rest)
        code = head.group(1) if head else rest
    tail = rest[len(code):]

    loc_match = CHUANCHAO_LOC_RE.match(tail)
    number = loc_match.group(0) if loc_match else ""
    part = tail[len(number):].strip()
    # 去掉尾部标点：上游偶有「海1.2.」这种多一个句点的（实测 1 例），
    # 句点是题记的标点，不是「引书名」的一部分。
    part = re.sub(r"[.、\s]+$", "", part)
    return {"artifact": code, "number": number, "era": "",
            "book_code": code, "part": part}


def parse_caption_chu(caption: str, modern_char: str) -> dict[str, str]:
    """把楚文字题记切成「出土文献 / 篇名 / 位置编号」。

    与其它书体不同，楚文字题记里**没有时代**——传世楚简都是战国中晚期的，
    汉典也没给时代标注。所以 ``era`` 一律为空，分类维度是**出土文献**。

    切法（按位置切，不按字符串替换）：

    1. 摘掉现代字前缀（上游的题记总以现代字开头）；
    2. 开头连续的汉字是**文献代码**（「包」「新甲」「郭」「上」「帛甲」…）；
    3. 紧接着可选的 ``(册号)`` 与 ``.篇名`` 归到文献的一部分；
    4. 剩下的数字段是**位置编号**（「3.318」「2.26」「28」「119」）。
    """
    text = flat(caption)
    offset = len(modern_char) if modern_char and text.startswith(modern_char) else 0
    rest = text[offset:].strip()
    match = CHU_TAIL_RE.match(rest)
    if match:
        code = match.group(1)
        tail = rest[match.end():]
    else:
        fallback = CHU_TAIL_FALLBACK_RE.match(rest)
        if not fallback:
            return {"artifact": rest, "number": "", "era": "",
                    "book_code": rest, "part": ""}
        code = fallback.group(1)
        tail = rest[fallback.end():]
    part_match = CHU_PART_RE.match(tail)
    paren = part_match.group(1) or ""
    part = part_match.group(2) or ""
    tail = tail[part_match.end():] if part_match else tail
    book = code + paren + ("." + part if part else "")
    number = tail.strip().lstrip(".")
    return {"artifact": book, "number": number, "era": "",
            "book_code": code, "part": part}


def http_get(url: str, referer: str | None = None, timeout: int = 30,
             retries: int = 3) -> tuple[int, bytes]:
    headers = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
    if referer:
        headers["Referer"] = referer
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return resp.status, raw
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise
            last = exc
            if exc.code == 429:
                # 限流：退避要长得多。3 次 × 1.5 秒退避扛不住 429，
                # 重试耗尽就抛出去，那个字的实例会整个丢掉。
                time.sleep(8.0 * (attempt + 1) + random.random() * 3)
                continue
        except Exception as exc:      # 网络抖动：退避重试
            last = exc
        time.sleep(1.5 * (attempt + 1) + random.random())
    raise last if last else RuntimeError("unknown error")


def renumber(manifest: dict) -> None:
    """按确定性规则重排层键。

    并发抓取时完成顺序随网络抖动而变，若按完成顺序编号，同一份字表跑两次
    会得到不同的编号，整层立刻失去可追溯性（AGENTS.md 的硬规则）。
    规则：按「现代字码位 → 汉典字形编号 → 文件名」排序后重排为 1..N。

    **每次落盘前都要重排。** 增量落盘是给中断续跑用的；
    如果落盘的是完成序编号，中断一次，整层的键就永久依赖网络时序了。
    """
    manifest["glyphs"].sort(key=lambda g: (str(g.get("unicode") or ""),
                                           str(g.get("source_id") or ""),
                                           str(g.get("file") or "")))
    for index, glyph in enumerate(manifest["glyphs"], 1):
        glyph["glyph_id"] = index


def selection_fingerprint(args, kind: str, preference: list[str],
                         caption_preference: list[str]) -> str:
    """算出「本次选择逻辑」的指纹。

    指纹 = **选择相关的几个函数的源码** + 选取相关参数。
    改了解析器、改了 --per-char / --max-per-era / 偏好表，选出来的实例就变了，
    续跑缓存必须作废。

    只哈希这几个函数，不哈希整个文件：改错误处理、加日志这类与选择无关的改动
    不该把缓存作废（一次作废就是几十分钟的重复抓取）。
    """
    parts = []
    for name in SELECTION_FUNCTIONS:
        func = globals().get(name)
        if func is None:
            continue
        try:
            parts.append(inspect.getsource(func))
        except OSError:
            parts.append(name)
    for name in SELECTION_CONSTANTS:
        parts.append(f"{name}={globals().get(name)!r}")
    if kind == "chuwenzi":
        # 楚文字有单独的题记解析器。改了它必须作废缓存——
        # 否则旧字不按新规则重解析，题记静默过期。
        # 只在抓楚文字时算进来：别让楚文字的改动把金文/隶书/甲骨的缓存也作废。
        for name in ("parse_caption_chu",):
            func = globals().get(name)
            if func is None:
                continue
            try:
                parts.append(inspect.getsource(func))
            except OSError:
                parts.append(name)
        for name in ("CHU_TAIL_RE", "CHU_TAIL_FALLBACK_RE", "CHU_PART_RE"):
            parts.append(f"{name}={globals().get(name)!r}")
    if kind == "chuanchao":
        # 傳抄古文同理：单独的解析器 + 单独的源书代号表。
        # 代号表改了，切出来的代号就变了，旧字形必须重解析。
        for name in ("parse_caption_chuanchao",):
            func = globals().get(name)
            if func is None:
                continue
            try:
                parts.append(inspect.getsource(func))
            except OSError:
                parts.append(name)
        for name in ("CHUANCHAO_BOOK_CODES", "CHUANCHAO_LOC_RE", "CJK_SPACE_RE"):
            parts.append(f"{name}={globals().get(name)!r}")
    payload = b"\x00".join([
        "\x00".join(parts).encode("utf-8"),
        kind.encode("utf-8"),
        repr(preference).encode("utf-8"),
        repr(caption_preference).encode("utf-8"),
        repr([args.per_char, args.max_per_era, args.max_per_book]).encode("utf-8"),
    ])
    return hashlib.sha256(payload).hexdigest()


def parse_instances(html: str, kind: str) -> list[dict[str, str]]:
    """从实例页里按 DOM 结构配对「字形编号」与「出处说明」。

    汉典的每个字形实例是一个 ``<div class="glyph-item">`` 块：**一张图 + 一到两条 caption**。
    异体字页面会给两条——主 caption 带现代字前缀（「㢴小臣逋鼎西周早期集成2581」），
    副 caption 只有器物说明（「小臣逋鼎西周早期集成2581」）。

    **所以不能按出现顺序把图和 caption 一一配对。** 那样会在这种页面上整体错位一格：
    第 2 个实例配到第 1 个实例的副 caption，第 3 个配到第 2 个的主 caption……
    记下来的器物、编号、时代全都成了别件器物的（实测「㢴」字 22 个实例错位 21 个，
    「㢴伯戈冬簋 集成4115 西周中期」被记成「㢴小臣逋鼎 集成2581 西周早期」）。
    这里按 glyph-item 块配对，取块里的第一条 caption（主 caption）。

    只认 caption 里带编号的条目，免得把站点自己的图标、占位图也抓进来。
    """
    pattern = IMAGE_RE_TMPL.format(host=re.escape(HOST), kind=re.escape(kind))
    out: list[dict[str, str]] = []
    for chunk in html.split(GLYPH_ITEM_MARKER)[1:]:
        match = re.search(pattern, chunk)
        if not match:
            continue
        caps = [flat(re.sub(r"<[^>]+>", "", c)) for c in CAPTION_RE.findall(chunk)]
        caps = [c for c in caps if c]
        if not caps:
            continue
        caption = caps[0]
        # **不要按第一个空格切。** 题记有三段式（「㐭老子乙前93下 西漢」），
        # 按空格切会把器物名一起切掉；现代字前缀由 era_bucket 自己去掉。
        out.append({"image_id": match.group(1), "caption": caption, "detail": caption,
                    "alt_caption": caps[1] if len(caps) > 1 else ""})
    return out


def parse_caption_for_kind(kind: str, caption: str, modern_char: str) -> dict[str, str]:
    """按书体分派题记解析器。

    **题记格式按书体走**，不能用一套切法套所有书体：
    通用切法按「时代 + 编号」位置切，会把文献代号当时代
    （楚文字的「秦99.3反」里「秦」是代号；傳抄古文压根没有时代）。
    """
    if kind == "chuwenzi":
        return parse_caption_chu(caption, modern_char)
    if kind == "chuanchao":
        return parse_caption_chuanchao(caption, modern_char)
    return parse_caption(caption, modern_char)


def _pick_by_bucket(buckets: dict[str, list[dict[str, str]]], order: list[str],
                    limit: int, cap: int, take, chosen: list[dict[str, str]]
                    ) -> list[dict[str, str]]:
    """按桶取实例：每个桶最多 ``cap`` 个，桶比名额多时沿桶序**均匀**取。

    均匀取而不是从头取，是因为从头取会让排在后面的桶整段被砍掉
    （前面的桶先占满名额），演变链只剩前半截。

    轮转取：第 0 轮每个桶取第 1 个，第 1 轮取第 2 个……
    每桶的上限是硬的：没有更多桶就不再补同一桶的实例。

    ``take`` 负责把选中的实例追加进 ``chosen``（去重与名额上限都在它那里），
    这里只管「按什么顺序取哪个桶」。
    """
    selected = order
    if len(order) > limit:
        if limit <= 1:
            selected = order[:1]
        else:
            step = (len(order) - 1) / (limit - 1)
            idxs = sorted({int(round(i * step)) for i in range(limit)})
            selected = [order[i] for i in idxs]
    for round_index in range(cap):
        for key in selected:
            items = buckets[key]
            if round_index < len(items):
                take([items[round_index]])
                if len(chosen) >= limit:
                    return chosen
    return chosen


def pick_instances(instances: list[dict[str, str]], preference: list[str],
                   limit: int = 1,
                   caption_preference: list[str] | None = None,
                   max_per_era: int = 0,
                   kind: str = "",
                   modern_char: str = "",
                   max_per_book: int = 0) -> list[dict[str, str]]:
    """按出处片段、时代偏好挑出最多 ``limit`` 个实例。

    出处片段优先（例如小篆的「說文‧」表示正篆，「說文古文」是另一个形式）；
    其次按时代偏好从早到晚取；剩下的名额用页面上的原始顺序补。
    同一个字形的不同实例是同一件器物上的不同写法，属于**变体**，
    与甲骨层「一字多条」的记法一致。

    **``max_per_era`` > 0 时，每个时代最多取这么多个**，且这个上限是硬的。

    这是「一字多形」的关键：``--per-char 8 --max-per-era 1`` 拿到的是
    **不同代各一个**（商代晚期 / 西周早期 / 西周中期 / 西周晚期 / 春秋 / 戰國……），
    拼起来才是一条演变链；而 ``--per-char 8``（不限时代）拿到的是同一时代里的八个，
    对「看字形怎么变」没有价值。

    时代分桶用归一后的时代名（「西周中期或晚期」并进「西周中期」）；
    桶按年代顺序排列（见 ``ERA_CHRONOLOGY``），年代顺序表里没有的桶按页面顺序排后面。

    **``max_per_book`` > 0 时，每个分桶维度最多取这么多个。**
    给**没有时代维度**的书体用：它按时代分桶会退化成「每字只取一个」
    （题记里没有时代词，``era_bucket`` 只好拿「器名+编号」当桶，一个字一个桶），
    按自己的维度分桶才有「一字多形」的意思——同字在不同来源里的不同写法。
    **分桶维度按书体走**：楚文字按**出土文献**（《楚系简帛文字编》的文献代码），
    傳抄古文按**源书代号**（徐在国《传抄古文字编》的代号）。
    """
    if not instances:
        return []
    chosen: list[dict[str, str]] = []
    seen: set[str] = set()

    def take(candidates: list[dict[str, str]]) -> None:
        for inst in candidates:
            if len(chosen) >= limit:
                return
            if inst["image_id"] in seen:
                continue
            seen.add(inst["image_id"])
            chosen.append(inst)

    for frag in caption_preference or []:
        take([inst for inst in instances if frag in inst["detail"]])
        if len(chosen) >= limit:
            return chosen

    if max_per_book > 0:
        # 按**分桶维度**分桶。**维度按书体走**：
        # - 楚文字（chuwenzi）：分桶维度是**出土文献**（《楚系简帛文字编》的文献代码，
        #   如「郭」「包」「上」「新甲」）。同一个字在不同简上写法不同，
        #   这才拼得出演变链。
        # - 傳抄古文（chuanchao）：分桶维度是**源书代号**（徐在国《传抄古文字编》的代号）。
        # 两者题记格式不同、解析器也不同，用错解析器会把代号切错。
        if kind == "chuwenzi":
            def bucket_of(inst: dict[str, str]) -> str:
                return parse_caption_chu(inst["detail"], modern_char)["book_code"]
        elif kind == "chuanchao":
            def bucket_of(inst: dict[str, str]) -> str:
                return parse_caption_chuanchao(inst["detail"], modern_char)["book_code"]
        else:
            raise SystemExit(
                f"--max-per-book 对书体 {kind!r} 不适用："
                "只有楚文字（按出土文献）与傳抄古文（按源书）有可分桶的维度。")
        # 桶序用页面上的原始顺序（没有年代序可用）。
        buckets: dict[str, list[dict[str, str]]] = {}
        for inst in instances:
            buckets.setdefault(bucket_of(inst) or "(未切出)", []).append(inst)
        order = list(buckets)
        return _pick_by_bucket(buckets, order, limit, max_per_book, take, chosen)

    if max_per_era > 0:
        buckets: dict[str, list[dict[str, str]]] = {}
        for inst in instances:
            buckets.setdefault(era_bucket(inst["detail"], modern_char), []).append(inst)
        order: list[str] = []
        for era in ERA_CHRONOLOGY.get(kind, []):
            if era in buckets and era not in order:
                order.append(era)
        for key in buckets:
            if key not in order:
                order.append(key)
        return _pick_by_bucket(buckets, order, limit, max_per_era, take, chosen)

    if preference:
        for era in preference:
            take([inst for inst in instances if era in inst["detail"]])
            if len(chosen) >= limit:
                return chosen
    take(instances)
    return chosen


def load_book_map(repo_root: Path, script: str = "chuwenzi") -> dict[str, str]:
    """读层目录下的「文献代号 → 全称」对照表（可选）。

    楚文字层的表在 ``glyphs/chu/books.csv``，傳抄古文层的在
    ``glyphs/chuanchao/books.csv``。**没有这张表也照样抓**——只是 ``source_book``
    记上游原文的代号，不替它猜是哪部书。猜错书名比留个代号更糟：
    读者会照着错的名字去找书，找不到就以为这条出处是编的。
    """
    import csv

    path = repo_root / "glyphs" / LAYER_DIRS.get(script, script) / "books.csv"
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            code = (row.get("code") or "").strip()
            name = (row.get("corpus_full") or "").strip()
            if code and name:
                out[code] = name
    return out


def load_chars(args: argparse.Namespace) -> list[tuple[str, str]]:
    """返回 [(现代字, 6 位大写十六进制码位)]。"""
    if args.chars_file:
        out = []
        for line in Path(args.chars_file).read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            char = parts[0]
            # 码位一律 6 位大写十六进制：登记表、合并脚本、index.csv 都是这个宽度，
            # 不统一就会出现「4E04」与「004E04」两条记录指向同一个字。
            cp = parts[1].upper() if len(parts) > 1 else f"{ord(char):06X}"
            if len(cp) < 6:
                cp = cp.rjust(6, "0")
            out.append((char, cp))
        return out
    if args.from_seal_registry:
        import csv
        path = Path(args.repo_root) / "glyphs" / "seal" / "external.csv"
        seen: dict[str, str] = {}
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                char = (row.get("modern_char") or "").strip()
                cp = (row.get("unicode") or "").strip().upper()
                if char and cp and char not in seen:
                    seen[char] = cp
        return sorted(seen.items())
    raise SystemExit("需要 --chars-file 或 --from-seal-registry")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从汉典抓取书法字形实例")
    parser.add_argument("--script", required=True, choices=sorted(KIND_PATHS),
                        help="书体：jinwen 金文 / lishu 隶书 / xiaozhuan 小篆 / jiaguwen 甲骨文 …")
    parser.add_argument("--out", required=True, type=Path, help="落盘目录")
    parser.add_argument("--chars-file", type=Path, default=None,
                        help="字表：每行「现代字 [码位]」")
    parser.add_argument("--from-seal-registry", action="store_true",
                        help="用 glyphs/seal/external.csv 里的现代字做字表")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--per-char", type=int, default=1,
                        help="每个字取几个实例（默认 1）")
    parser.add_argument("--max-per-era", type=int, default=0,
                        help="每个时代最多取几个实例（默认 0 = 不限）。"
                             "配合 --per-char 用：--per-char 6 --max-per-era 1 "
                             "就是「六个不同时代各取一个」，而不是同一时代取六个。")
    parser.add_argument("--max-per-book", type=int, default=0,
                        help="每个**分桶维度**最多取几个实例（默认 0 = 不限）。"
                             "给没有时代维度的书体用："
                             "楚文字按**出土文献**分桶（每个出土文献最多 1 条），"
                             "傳抄古文按**源书代号**分桶；"
                             "按时代分桶会退化成「每字只取一个」。")
    parser.add_argument("--preference", default=None,
                        help="时代偏好，逗号分隔，按顺序命中（默认按书体内置）")
    parser.add_argument("--caption-preference", default=None,
                        help="出处片段偏好，逗号分隔，先于时代偏好匹配"
                             "（默认按书体内置；小篆用「說文‧」表示正篆）")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 个字（调试用）")
    parser.add_argument("--delay", type=float, default=0.05,
                        help="每个字之间的间隔秒数（限速用）")
    parser.add_argument("--workers", type=int, default=6, help="并发请求数")
    parser.add_argument("--max-per-host-errors", type=int, default=20,
                        help="连续失败到这么多就停手")
    parser.add_argument("--backfill", action="store_true",
                        help="不联网：按出处说明重算清单里的 period/source_book 后重写清单。"
                             "用来给旧清单补上结构化的时代与器名。")
    parser.add_argument("--source-dataset", default=None,
                        help="给这批字形起个数据集名，写进清单的 source_dataset 字段。"
                             "同一层里有多个来源时靠它区分批次（导入时用 --provenance-scope）。")
    parser.add_argument("--refresh-captions", action="store_true",
                        help="只刷题记：忽略续跑缓存，把所有字的实例页重新解析一遍，"
                             "更新清单里的题记字段。**已经存在的字形文件不重下**——"
                             "文件名按「码位-来源编号」定，重下只会浪费带宽、多一倍请求。\n"
                             "只能在选择参数与当初一致时用（参数变了会直接报错）：\n"
                             "改参数就重跑，让它全表重抓，否则清单会混进两套规则的字形。\n"
                             "注意：上游增删实例会改变选中集合，层键编号随之重排，"
                             "改完要重跑 src/import_glyph_layer.py 入库。")
    args = parser.parse_args(argv)

    kind = KIND_PATHS[args.script]
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"

    if args.backfill:
        if args.refresh_captions:
            print("注意：--backfill 已在联网前返回，--refresh-captions 不会执行。"
                  "（要刷题记就别给 --backfill。）")
        if not manifest_path.is_file():
            raise SystemExit(f"找不到清单：{manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        changed = 0
        # 题记格式按书体走：楚文字、傳抄古文的题记没有时代，
        # 结构是「文献代号 + 位置」，用通用的「时代 + 编号」切法会把代号当时代。
        kind_name = str(manifest.get("kind") or "")
        no_era = kind_name in ("chuwenzi", "chuanchao")
        for item in manifest.get("glyphs", []):
            parts = parse_caption_for_kind(kind_name, str(item.get("variant") or ""),
                                           str(item.get("modern_char") or ""))
            if no_era:
                # 文献代号与位置分列，时代留空。
                book = parts["artifact"]
                # **尾注字段按书体分派。** 楚文字的尾注是「篇名」（`book_part`），
                # 傳抄古文的尾注是「引书名」（`source_cited_book`）——
                # 两者层级不同，写错字段名会让库里多出一列语义串味的同名列。
                part_field = ("source_cited_book" if kind_name == "chuanchao"
                              else "book_part")
                other_field = ("book_part" if kind_name == "chuanchao"
                               else "source_cited_book")
                if (item.get("period") != "" or item.get("source_book") != book
                        or item.get("source_number") != parts["number"]
                        or item.get("book_code") != parts.get("book_code", "")
                        or item.get(part_field, "") != parts.get("part", "")
                        or item.get(other_field, "")):
                    changed += 1
                item["period"] = ""
                item["source_book"] = book
                item["source_number"] = parts["number"]
                item["book_code"] = parts.get("book_code") or ""
                item[part_field] = parts.get("part") or ""
                item.pop(other_field, None)
                if kind_name == "chuwenzi":
                    # 摹本底本页.行：从已有的字级书目里派生，纯本地推导，不联网。
                    base = chu_base_pages(str(item.get("source_references") or ""))
                    if base != str(item.get("source_base_pages") or ""):
                        changed += 1
                    if base:
                        item["source_base_pages"] = base
                    else:
                        item.pop("source_base_pages", None)
                continue
            book = flat(" ".join(x for x in (parts["artifact"], parts["number"]) if x))
            if item.get("period") != parts["era"] or item.get("source_book") != book:
                changed += 1
            item["period"] = parts["era"]
            item["source_book"] = book
        renumber(manifest)
        manifest["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
        with_era = sum(1 for g in manifest["glyphs"] if g.get("period"))
        print(f"清单 {manifest_path}：{len(manifest.get('glyphs', []))} 条，"
              f"补出时代 {with_era} 条，改动 {changed} 条。")
        return 0

    chars = load_chars(args)
    if args.limit:
        chars = chars[: args.limit]
    books = load_book_map(Path(args.repo_root).resolve(), args.script)
    if books:
        print(f"文献对照表: {len(books)} 条（glyphs/{LAYER_DIRS.get(args.script, args.script)}/books.csv）")
    preference = ([x.strip() for x in args.preference.split(",") if x.strip()]
                  if args.preference is not None
                  else [x.strip() for x in DEFAULT_PREFERENCE.get(args.script, "").split(",") if x.strip()])
    caption_preference = ([x.strip() for x in args.caption_preference.split(",") if x.strip()]
                          if args.caption_preference is not None
                          else list(DEFAULT_CAPTION_PREFERENCE.get(args.script, [])))

    manifest_path = out_dir / "manifest.json"
    manifest: dict = {"script": args.script, "kind": kind, "license": LICENSE,
                      "license_url": LICENSE_URL, "terms_url": TERMS_URL,
                      "attribution": ATTRIBUTION, "glyphs": []}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    # 续跑进已有目录时，书体必须对得上：把金文和隶书混进同一份清单，
    # 下游合并时才发现，脏数据已经写下去了。
    old_kind = str(manifest.get("kind") or "").strip()
    if old_kind and old_kind != kind:
        raise SystemExit(
            f"{out_dir} 里已有一份 {old_kind!r} 的清单，与本次的 {kind!r} 不是同一书体。\n"
            f"      请换一个输出目录，否则两批字形会混在一份清单里。")
    # 「已存在的字形」**以文件系统为准**，不以清单为准。
    # 清单里可能有条目但文件已被删（人工清理、拷贝中断、磁盘事故）——
    # 那时按清单判断会以为文件还在，结果字形永远补不回来，
    # 清单与磁盘长期脱节，下游导入直接卡在「清单里这些文件不存在」。
    # 所以先把「清单说有、磁盘没有」的条目**剔出清单**，让它们跟着页面重新抓回来。
    on_disk = {g["file"] for g in manifest.get("glyphs", [])
               if (out_dir / g["file"]).is_file()}
    dropped = len(manifest.get("glyphs", [])) - len(on_disk)
    if dropped:
        manifest["glyphs"] = [g for g in manifest.get("glyphs", [])
                              if g["file"] in on_disk]
        print(f"清理清单  : {dropped} 条在磁盘上已不存在，剔出清单待重抓", flush=True)
    done = set(on_disk)
    # 文件名 -> 清单条目。重跑时已存在的文件要**更新题记**，不能跳过——
    # 否则改了配对逻辑重跑，旧记录里的错配题记永远改不掉。
    by_file = {g["file"]: g for g in manifest.get("glyphs", [])}

    # 续跑缓存：记下「哪些字已经查过了」。
    # 清单里只存选中的字形，没实例的字不留痕，所以中断后重跑会把整张字表
    # 的页面重新抓一遍——上次金文抓取就在 6,800 字处断了，白花半小时重抓。
    #
    # 缓存必须跟「选择逻辑」绑定：改了脚本或改了参数，选出来的实例就变了，
    # 沿用旧缓存会漏掉该重选的字。所以指纹 = 脚本源码 + 选取相关参数。
    # 指纹对不上就当没有缓存，重新全抓。
    fingerprint = selection_fingerprint(args, kind, preference, caption_preference)
    visited: list[str] = []
    stored_fingerprint = str(manifest.get("selection_fingerprint") or "")
    if args.refresh_captions:
        # 「只刷题记」的前提是**选择规则不变**。改了参数还来刷新，
        # 清单里就会混进两套规则选出来的字形，而且层键编号会整体错位——
        # 比不刷更糟。所以这里直接拒绝。
        if stored_fingerprint and stored_fingerprint != fingerprint:
            raise SystemExit(
                "--refresh-captions 只能在选择参数与当初一致时使用。\n"
                f"      清单里的指纹 {stored_fingerprint[:12]} 与本次参数算出的 "
                f"{fingerprint[:12]} 不同。\n"
                "      刷新会让清单里混进两套规则选出来的字形，层键编号也会整体错位。\n"
                "      要改选择参数就别加 --refresh-captions，直接重跑（会全表重抓）。")
        print("刷题记    : 忽略续跑缓存，全部字重新解析（已存在的字形文件不重下）")
    elif stored_fingerprint == fingerprint:
        visited = [str(c) for c in manifest.get("visited") or []]
    else:
        if manifest.get("visited"):
            print("选择逻辑变了（脚本或参数与上次不同），忽略续跑缓存，全表重抓。")
    visited_set = set(visited)
    if visited_set:
        print(f"续跑      : 跳过已查过的 {len(visited_set)} 字")

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    errors = 0
    no_instance = 0
    # 题记变了的条数（刷新模式下用来报「刷动了多少」）
    caption_changed = 0
    # 双 caption 页里「副题记 ≠ 主题记去掉现代字前缀」的异常条目。
    # 回源抽样 571 个实例零例外，所以这几乎永远是空的；一旦不为空，
    # 说明上游改了题记结构，必须人工看一眼。
    alt_mismatch: list[str] = []
    # 上游页面上列了、但图文件 404 的实例。记下来，最后报个数。
    missing_images: list[str] = []

    def fetch_one(item: tuple[str, str]) -> tuple[str, str, list[tuple[dict, bytes]]]:
        """取一个字的所有实例页 + 选中的那几张字形。返回 (char, cp, [(实例, SVG 字节)])。

        **已经存在的字形文件不下载。** 文件名按「码位-来源编号」定，内容是上游原件的
        逐字节副本——重下既费带宽，又多一倍请求（429 的暴露面直接翻倍）。
        题记照常从页面上解析，所以「只刷题记」这条路径是成立的。
        """
        char, cp = item
        page = f"https://www.zdic.net/hans/{urllib.parse.quote(char)}/{kind}"
        try:
            _, raw = http_get(page)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return char, cp, []
            raise
        html = raw.decode("utf-8", errors="replace")
        instances = parse_instances(html, kind)
        if not instances:
            return char, cp, []
        # 摹本底本（页底「参考文献」段）是**逐字**的，不是逐实例的，
        # 所以挂在这个字的每个实例上，入库时写进 provenance 的 source_references。
        references = parse_references(html)
        if references:
            for inst in instances:
                inst["references"] = references
        picked = pick_instances(instances, preference, max(1, args.per_char),
                                caption_preference, args.max_per_era, kind, char,
                                args.max_per_book)
        out: list[tuple[dict, bytes]] = []
        for chosen in picked:
            svg_name = f"{cp}-{chosen['image_id'].replace('_', '-')}.svg"
            if svg_name in done:
                # 已有文件：只更新题记，字节不动。
                out.append((chosen, b""))
                continue
            svg_url = f"https://{HOST}/zy/{kind}/{chosen['image_id']}.svg"
            try:
                status, body = http_get(svg_url, referer=REFERER)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    # 汉典页面上列了这个实例，但对应的图文件不在（页面与图片目录
                    # 不同步）。这不该算整批失败——那会让这个字的其他实例白丢。
                    # 记一笔，继续取这个字的其余实例。
                    missing_images.append(f"{char} {chosen['image_id']}")
                    continue
                raise
            if status != 200 or not body.lstrip().startswith(b"<svg"):
                # 取到了东西但不是 SVG（状态异常、或返回了占位内容）。
                # 同样不该让这个字的其余实例一起陪葬。
                missing_images.append(f"{char} {chosen['image_id']} (状态 {status}，不是 SVG)")
                continue
            out.append((chosen, body))
        # **限速在 worker 里做。** 原来这个 sleep 放在主线程消费结果的地方，
        # 而 worker 是并发跑的、结果进的是无界队列——所以它压根没限住请求速率，
        # `--delay` 写多少都一样。放到 worker 里，每个 worker 自己按间隔发请求，
        # 速率才是 workers/delay 那个量级。
        time.sleep(args.delay)
        return char, cp, out

    todo = [(c, cp) for c, cp in chars if c not in visited_set]
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(fetch_one, item): item for item in todo}
        for index, future in enumerate(as_completed(futures), 1):
            char, cp = futures[future]
            try:
                char, cp, picked = future.result()
            except Exception as exc:
                errors += 1
                if errors <= 10:
                    # 失败要看得见：只报「失败 N 次」不知道是限流还是网络抖动。
                    print(f"  ! {char} 取不到：{type(exc).__name__}: {exc}", flush=True)
                if errors >= args.max_per_host_errors:
                    print(f"失败 {errors} 次，停止。")
                    for pending in futures:
                        pending.cancel()
                    break
                continue
            visited.append(char)
            if not picked:
                no_instance += 1
                continue
            for inst, body in picked:
                image_id = inst["image_id"]
                name = f"{cp}-{image_id.replace('_', '-')}.svg"
                parts = parse_caption_for_kind(kind, inst["caption"], char)
                if name in done:
                    # 文件已经在，但题记可能变了（换了配对逻辑、或上游改了说明）。
                    # 只更新题记相关的字段，不重下文件。
                    old = by_file.get(name)
                    if old is not None:
                        if old.get("variant") != inst["caption"]:
                            caption_changed += 1
                        old["variant"] = inst["caption"]
                        old["period"] = parts["era"]
                        old["source_book"] = parts["artifact"]
                        old["source_number"] = parts["number"]
                        if parts.get("book_code"):
                            old["book_code"] = parts["book_code"]
                        if parts.get("part"):
                            old["book_part"] = parts["part"]
                        else:
                            old.pop("book_part", None)
                        if inst.get("references"):
                            old["source_references"] = "；".join(inst["references"])
                            if kind == "chuwenzi":
                                old["source_base_pages"] = chu_base_pages(old["source_references"])
                        # 双 caption 页：副题记按上游原文与「主题记去掉现代字前缀」
                        # 完全一致（回源抽样 571 个实例，58 个双 caption 页零例外），
                        # 所以只记**页面上是双 caption** 这一个事实，不重复存一遍文本。
                        if inst.get("alt_caption"):
                            old["dual_caption"] = True
                            if inst["alt_caption"] != strip_char(inst["caption"], char):
                                # 推导不成立：说明上游的副题记不是简单的前缀关系，
                                # 这时把原文记下来，并记进清单的异常清单。
                                old["alt_caption"] = inst["alt_caption"]
                                alt_mismatch.append(f"{char} {name}")
                        else:
                            old.pop("dual_caption", None)
                            old.pop("alt_caption", None)
                    continue
                (out_dir / name).write_bytes(body)
                record = {
                    "glyph_id": len(manifest["glyphs"]) + 1,
                    "file": name,
                    "modern_char": char,
                    "unicode": cp,
                    "variant": inst["caption"],
                    "period": parts["era"],
                    "source_id": image_id,
                    "source_book": parts["artifact"],
                    "source_number": parts["number"],
                    "source_path": f"zy/{kind}/{image_id}.svg",
                    "source_url": f"https://{HOST}/zy/{kind}/{image_id}.svg",
                    "source_page_url": f"https://www.zdic.net/hans/{urllib.parse.quote(char)}/{kind}",
                    "source_sha256": hashlib.sha256(body).hexdigest(),
                    "license": LICENSE,
                    "retrieved_at": fetched_at,
                }
                if parts.get("book_code"):
                    # 楚文字 / 傳抄古文：文献代号按上游原文记，全称在 books.csv 里查。
                    record["book_code"] = parts["book_code"]
                    mapped = books.get(parts["book_code"], "")
                    if mapped:
                        record["source_book"] = mapped
                if parts.get("part"):
                    # 篇名 / 尾注（如「郭.語」的「語」）。换全称时会丢掉它，
                    # 而它决定「哪个文本的哪个字」——出处精度要留住这一层。
                    record["book_part"] = parts["part"]
                if inst.get("references"):
                    # 字级参考书目：汉典字页底部的「参考文献」段是这个字
                    # 在各书体栏下用到的全部底本，**不是**这一条实例的底本定位。
                    # 摹本底本的页.行另记在 source_base_pages。
                    record["source_references"] = "；".join(inst["references"])
                    if kind == "chuwenzi":
                        record["source_base_pages"] = chu_base_pages(record["source_references"])
                # 双 caption 页：副题记按上游原文与「主题记去掉现代字前缀」
                # 完全一致（回源抽样 571 个实例，58 个双 caption 页零例外），
                # 所以只记**页面上是双 caption** 这一个事实，不重复存一遍文本。
                if inst.get("alt_caption"):
                    record["dual_caption"] = True
                    if inst["alt_caption"] != strip_char(inst["caption"], char):
                        record["alt_caption"] = inst["alt_caption"]
                        alt_mismatch.append(f"{char} {name}")
                manifest["glyphs"].append(record)
                by_file[name] = record
                done.add(name)
            if index % 50 == 0:
                print(f"  … {index}/{len(todo)}  字形 {len(manifest['glyphs'])}  "
                      f"无实例 {no_instance}  失败 {errors}", flush=True)
                # 增量落盘：中断后重跑不丢号，也不重下已抓到的字形。
                # 落盘前先按确定性规则重排编号——落完成序编号的话，
                # 中断一次整层的键就永久依赖网络时序了。
                renumber(manifest)
                manifest["visited"] = sorted(set(visited))
                manifest["selection_fingerprint"] = fingerprint
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")

    # 层键要确定：并发抓取时完成顺序随网络抖动而变。这里按
    # 「现代字码位 → 汉典字形编号 → 文件名」排序后重排，编号 1..N 与抓取过程无关。
    renumber(manifest)
    # --limit 只处理前 N 个字，但**不能**把续跑缓存截断成这 N 个——
    # 否则下一次普通跑会以为其余的字没查过，白重抓一遍。
    keep = set(visited)
    if args.limit:
        keep |= {str(c) for c in (manifest.get("visited") or [])}
    manifest["visited"] = sorted(keep)
    manifest["selection_fingerprint"] = fingerprint

    manifest["script"] = args.script
    manifest["kind"] = kind
    manifest["license"] = LICENSE
    manifest["license_url"] = LICENSE_URL
    manifest["attribution"] = ATTRIBUTION
    if args.source_dataset:
        # 同层多来源时靠这个字段区分批次（导入时用 --provenance-scope）。
        manifest["source_dataset"] = args.source_dataset
    manifest["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")

    print()
    print(f"书体      : {args.script}（{kind}）")
    print(f"字表      : {len(chars)} 字")
    print(f"抓到字形  : {len(manifest['glyphs'])}")
    print(f"无实例    : {no_instance} 字")
    print(f"失败      : {errors}")
    if args.refresh_captions:
        print(f"题记改动  : {caption_changed} 条（上游题记与清单里存的不一致）")
    if alt_mismatch:
        print(f"副题记异常: {len(alt_mismatch)} 条（副题记 ≠ 主题记去掉现代字前缀，"
              f"上游题记结构可能变了）")
        for note in alt_mismatch[:10]:
            print(f"            {note}")
        manifest["alt_caption_mismatch"] = sorted(alt_mismatch)
    if missing_images:
        print(f"图文件缺失: {len(missing_images)}（上游页面列了、图 404）")
        for note in missing_images[:10]:
            print(f"            {note}")
        manifest["missing_images"] = sorted(missing_images)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    print(f"清单      : {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
