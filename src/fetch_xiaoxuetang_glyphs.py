#!/usr/bin/env python3
"""从小学堂（中央研究院）抓取字形实例、出處表与许可声明快照。

用法::

    # 1. 许可声明快照（进 src/licenses/）
    python src/fetch_xiaoxuetang_glyphs.py --mode license

    # 2. 各库规模快照（首页「最新消息」栏的页数与日期）
    python src/fetch_xiaoxuetang_glyphs.py --mode stats

    # 3. 各库出處表快照（机器可读的三列对照表）
    python src/fetch_xiaoxuetang_glyphs.py --mode references

    # 4. 字形实例（字頭枚举 + 位图取回）
    python src/fetch_xiaoxuetang_glyphs.py --mode glyphs --db chuwenzi \
        --out tmp/xxt/chuwenzi --size 400 --delay 4.0

为什么这样写
------------
1. **只走两条路**。检索走 ``POST /<db>/PageResult/PageResult``（ASP.NET MVC 的表单 action）；
   取图走 ``char.iis.sinica.edu.tw`` 的 ICS 渲染 API。DB 页自己的字体服务器
   ``/ImageText2/ShowImage.ashx`` 在部分地区被 ASCDC 地区封锁，本仓库不依赖它。
2. **四种拦截分别识别**。ASCDC 会用四种不同的响应挡人，含义完全不同，恢复方式也不同：

   ==========================  ==========================================  ==============
   响应                        含义                                        处置
   ==========================  ==========================================  ==============
   405 / 302 → /block.html     边缘层软拒（突发流量）                       指数退避，最长 30 min
   页面含 Access Blocked        **IP 级**封锁（"Your IP address has been   冷却 >= 300 s
                                blocked for security reasons"）            后从断点续
   页面含 Access Restricted     **地区级**封锁（"current country or        该路径不可用；
                                region is not yet open"）                  换路径或换出口
   200 + GIF / HTML            正常                                          继续
   ==========================  ==========================================  ==============
3. **不装第三方库**。本机只有 PIL / numpy / lxml（与 ``src/outline_oracle.py`` 的前提一致）。
4. **断点续跑 + 指纹**。解析逻辑或选取规则的源码哈希进缓存指纹；解析器一改，
   旧缓存自动失效重抓——否则旧清单会静默过期。
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
HOST = "https://xiaoxue.iis.sinica.edu.tw"
RENDER_HOST = "https://char.iis.sinica.edu.tw"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

LICENSE_ID = "CC0-1.0"
LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
LICENSE_STATEMENT_URL = f"{HOST}/License/License"

# 各库：路径名、页面标题、字頭数、字形数、以及「本库古文字字体」的判定前缀。
# 字頭数与字形数取自各库首页「最新消息」栏（页面自带 2026/10/30 的日期），
# 字形数用来做枚举完整性自检：各出處代号命中数之和应当等于它。
# 小学堂把古文字做成了自制字型（font= 中研院…），字頭则用標楷體 / 北師大說文小篆 渲染——
# 那两种不是本库的字形，必须按字体名过滤掉，否则会把楷体字頭当成古文字收进来。
DBS: dict[str, dict] = {
    "jiaguwen": {"label": "甲骨文", "heads": 2548, "glyphs": 24701, "title": "小學堂甲骨文"},
    "jinwen": {"label": "金文", "heads": 3953, "glyphs": 38837, "title": "小學堂金文"},
    "chuwenzi": {"label": "楚系簡帛文字", "heads": 3281, "glyphs": 37614, "title": "小學堂楚系簡帛文字"},
    "qinwenzi": {"label": "秦系簡牘文字", "heads": 1760, "glyphs": 3904, "title": "小學堂秦系簡牘文字"},
    "chuanchao": {"label": "傳抄古文字", "heads": 8381, "glyphs": 29039, "title": "小學堂傳抄古文字"},
    "xiaozhuan": {"label": "小篆", "heads": 9831, "glyphs": 11101, "title": "小學堂小篆"},
    "lishu": {"label": "隸變", "heads": 5058, "glyphs": 25107, "title": "小學堂隸變"},
}

# 本库字形用的字体前缀（实测：甲骨/金文/楚系/秦系/傳抄/隸變都是「中研院」开头）。
#
# **小篆库是例外**：它的字形用「北師大說文小篆」渲染——那正是《說文》小篆字体，
# 與漢典篆书层的 ``source_id``（``27_<槽位>``）是**同一套槽位**。
# 早先按「中研院」一刀切过滤，小篆库因此一个实例都出不来。
GLYPH_FONT_PREFIX = "中研院"
GLYPH_FONT_PREFIXES: dict[str, str] = {
    "xiaozhuan": "北師大",
}

# ---------------------------------------------------------------- 拦截识别

BLOCK_IP = "ip-blocked"          # IP 级封锁：冷却可解
BLOCK_GEO = "geo-blocked"        # 地区级封锁：该路径不可用
BLOCK_SOFT = "soft-blocked"      # 边缘软拒：退避即可


class Blocked(Exception):
    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


def classify(status: int, ctype: str, body: bytes, location: str) -> str | None:
    """返回拦截类型；正常返回 None。"""
    if status == 405:
        return BLOCK_SOFT
    if status in (301, 302, 303, 307, 308) and "/block.html" in (location or ""):
        return BLOCK_SOFT
    if status == 200 and ctype.startswith("text/html"):
        head = body[:6000].decode("utf-8", "replace")
        if "Your IP address has been blocked" in head or "Access Blocked" in head:
            return BLOCK_IP
        if "current country or region is not yet open" in head or "Access Restricted" in head:
            return BLOCK_GEO
    return None


def http(url: str, *, data: bytes | None = None, referer: str | None = None,
         timeout: int = 45) -> tuple[int, str, bytes, str]:
    headers = {"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9"}
    if referer:
        headers["Referer"] = referer
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (resp.status, resp.headers.get("Content-Type", ""),
                    resp.read(), resp.headers.get("Location", "") or "")
    except urllib.error.HTTPError as exc:
        return (exc.code, exc.headers.get("Content-Type", ""),
                exc.read(), exc.headers.get("Location", "") or "")
    except Exception as exc:  # noqa: BLE001
        raise Blocked(BLOCK_SOFT, f"network: {exc}") from exc


class Fetcher:
    """带限速与退避的抓取器。"""

    def __init__(self, delay: float, retries: int = 6, log=print):
        self.delay = delay
        self.retries = retries
        self.log = log
        self.last = 0.0
        self.blocked_until = 0.0
        self.block_count = 0

    def _wait_turn(self) -> None:
        gap = self.delay * random.uniform(0.6, 1.4)
        wait = self.last + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()

    def get(self, url: str, referer: str | None = None, expect: str | None = None):
        """取一次；expect='html'/'gif' 时校验内容类型。返回 (ctype, bytes)。"""
        for attempt in range(self.retries):
            self._wait_turn()
            status, ctype, body, loc = http(url, referer=referer)
            kind = classify(status, ctype, body, loc)
            if kind is None:
                if status != 200:
                    raise Blocked(BLOCK_SOFT, f"HTTP {status}")
                if expect == "html" and not ctype.startswith("text/html"):
                    raise Blocked(BLOCK_SOFT, f"期望 HTML，实得 {ctype}")
                if expect == "gif" and not ctype.startswith("image/gif"):
                    raise Blocked(BLOCK_SOFT, f"期望 GIF，实得 {ctype}")
                self.block_count = 0
                return ctype, body
            self._on_block(kind, url, attempt)
        raise Blocked(BLOCK_SOFT, f"重试 {self.retries} 次仍失败：{url}")

    def post(self, url: str, fields: dict[str, object], referer: str | None = None):
        body = urllib.parse.urlencode(fields).encode()
        for attempt in range(self.retries):
            self._wait_turn()
            status, ctype, raw, loc = http(url, data=body, referer=referer)
            kind = classify(status, ctype, raw, loc)
            if kind is None:
                if status != 200:
                    raise Blocked(BLOCK_SOFT, f"HTTP {status}")
                self.block_count = 0
                return raw.decode("utf-8", "replace")
            self._on_block(kind, url, attempt)
        raise Blocked(BLOCK_SOFT, f"重试 {self.retries} 次仍失败：{url}")

    def _on_block(self, kind: str, url: str, attempt: int) -> None:
        self.block_count += 1
        if kind == BLOCK_GEO:
            raise Blocked(BLOCK_GEO, f"地区封锁，换路径或换出口：{url}")
        if kind == BLOCK_IP:
            # 实测冷却 300 s 后 render.aspx 立即恢复。
            wait = min(300.0 * (attempt + 1), 1800.0)
            self.log(f"  ! IP 级封锁，冷却 {wait:.0f}s 后重试（{url[:70]}）")
            self.blocked_until = time.time() + wait
            time.sleep(wait)
            return
        wait = min(5.0 * (2 ** attempt), 1800.0)
        self.log(f"  ! 软拒 {kind}，退避 {wait:.0f}s（第 {attempt + 1} 次）")
        time.sleep(wait)


# ---------------------------------------------------------------- 解析

IMG_RE = re.compile(
    r'<img[^>]*src="(/ImageText2/ShowImage\.ashx\?[^"]+)"[^>]*alt="&[^;"]*?([0-9A-Fa-f]+);"')
ALT_RE = re.compile(r'alt="&(\d+)\.([0-9A-Fa-f]+);"')
# 站点的 </td> 是坏的：一个字形单元写成
#   <td class="VariantListA"><img …/><br />帛甲2.3<td>
# 没有闭合 </td>。所以不能按 </td> 切，要按「下一个 <td」切。
# 字形单元用**两个** class（实测一页 50 个字形：VariantListA 40 + VariantListB 10）。
CELL_START_RE = re.compile(r'<td[^>]*class="VariantList[AB]"[^>]*>')
ALT_FONTID_RE = re.compile(r"^&(\d+)\.([0-9A-Fa-f]+);$")
# 在 <img ...> 标签里找 alt（不带锚点）
ALT_IN_TAG_RE = re.compile(r'alt="&(\d+)\.([0-9A-Fa-f]+);"')
BR_RE = re.compile(r"<br\s*/?>(.*)", re.S)
TAG_RE = re.compile(r"<[^>]+>")
HITS_RE = re.compile(r"共搜尋到\s*([\d,]+)\s*字")
PAGES_RE = re.compile(r"共搜尋到[^/]*?／\s*([\d,]+)\s*頁")
STARTORDER_RE = re.compile(r'id="StartOrder"[^>]*>\s*(\d+)\s*</span>')
# 「相關索引」＝该字頭在底本里的页.行出处。**按字頭给，不按实例给**：
# 同一个字頭的所有页这段完全一样（实测「一」字頭 7 页逐字相同），
# 但每个实例的「出處簡號」里已经带了它自己的编号（帛乙7.21 / 包2.273）。
BASE_INDEX_RE = re.compile(r"相關索引.*?<ul[^>]*>(.*?)</ul>", re.S)
# 分页噪声：从这里开始的文字不是出處簡號
NOISE_RE = re.compile(r"(最初頁|下一頁|最末頁|\(點選字形可取得字形編輯資訊\))")
FONT_RE = re.compile(r"[?&]font=([^&\"]+)")


def decode_font(raw: str) -> str:
    return urllib.parse.unquote(raw)


HEAD_IMG_RE = re.compile(r"<img\b[^>]*>")

# 私用區（PUA）與代理區——这些码位**不是漢字**。
PUA_RANGES = (
    (0xE000, 0xF8FF),      # BMP 私用區
    (0xF0000, 0xFFFFD),    # 私用區 A
    (0x100000, 0x10FFFD),  # 私用區 B
)

# 能当「现代字」的码位范围：基本区、扩展 A/B/C…、兼容表意。
HAN_RANGES = (
    (0x3400, 0x4DBF),      # 扩展 A
    (0x4E00, 0x9FFF),      # 基本区
    (0xF900, 0xFAFF),      # 兼容表意
    (0x20000, 0x3134A),    # 扩展 B..G
)


def usable_modern_char(ch: str) -> bool:
    """这个码位能不能当「现代字」。

    小學堂的 alt 記的是**各字体自己的槽位码位**，不一定是真汉字：
    標楷體外字集N（異體字）、北師大說文小篆的罕見字、部件字都落在**私用區**。
    私用區码位不能当现代字——它是排版槽位，不是汉字。
    """
    if not ch or len(ch) != 1:
        return False
    cp = ord(ch)
    if 0xD800 <= cp <= 0xDFFF:      # 代理區
        return False
    if any(lo <= cp <= hi for lo, hi in PUA_RANGES):
        return False
    return any(lo <= cp <= hi for lo, hi in HAN_RANGES)


def _head_items(head_region: str) -> list[dict]:
    """字頭行的图片清单。

    字頭行的結構是【楷書字頭（北大楷…字體）】（【隸書字頭（沙海隸）】、
    【異體字（沙海隸外字集N）】）——括號是單獨的無 alt 圖片。所以要**按字體名**
    分類，不能只看 alt 裡的碼位。

    異體字的碼位是**字體槽位**（U+FBE2 之類，不是真實 Unicode 漢字），
    這裡記成 "字体号_码位"，跟字形鍵同一套命名空間。
    """
    items: list[dict] = []
    for m in HEAD_IMG_RE.finditer(head_region):
        tag = m.group(0)
        alt = ALT_IN_TAG_RE.search(tag)
        if not alt:
            continue
        font = ""
        src = re.search(r'src="([^"]*)"', tag)
        if src:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(src.group(1)).query)
            font = decode_font((q.get("font") or [""])[0])
        ch = ""
        try:
            ch = chr(int(alt.group(2), 16))
        except (ValueError, OverflowError):
            ch = ""
        items.append({"font": font, "font_id": alt.group(1),
                      "codepoint": alt.group(2).upper(), "char": ch})
    return items


def parse_result_page(html: str) -> dict:
    """解析一页检索结果。

    返回::

        {
          "hits": 187, "pages": 5,
          "heads": [{"zi_order": 3260, "modern_char": "子", "variants": [...]}],
          "glyphs": [{"pua": "E00E", "font": "中研院楚系簡帛文字重文四",
                       "source_short": "帛甲2.3", "zi_order": 3260}],
        }
    """
    hits_m = HITS_RE.search(html)
    pages_m = PAGES_RE.search(html)
    hits = int(hits_m.group(1).replace(",", "")) if hits_m else 0
    pages = int(pages_m.group(1).replace(",", "")) if pages_m else 0

    heads: list[dict] = []
    glyphs: list[dict] = []
    # 底本页.行（字頭级）
    base_pages: list[str] = []
    bm = BASE_INDEX_RE.search(html)
    if bm:
        for li in re.findall(r"<li>(.*?)</li>", bm.group(1), re.S):
            txt = re.sub(r"\s+", " ", TAG_RE.sub(" ", li)).strip()
            if txt:
                base_pages.append(txt)
    marks = [(m.start(), m.group(1)) for m in STARTORDER_RE.finditer(html)]
    marks.append((len(html), None))

    for idx in range(len(marks) - 1):
        start, zi_order = marks[idx]
        end = marks[idx + 1][0]
        block = html[start:end]

        # 字頭：在第一个字形单元之前的那一段里，取 alt 里的字符（楷書字頭 + 异体）
        first_cell = CELL_START_RE.search(block)
        head_region = block[:first_cell.start()] if first_cell else block
        head_items = _head_items(head_region)
        variants: list[str] = []
        lishu = ""
        for it in head_items:
            if "外字集" in it["font"] or "部件" in it["font"]:
                # 异体字：存在「標楷體外字集N」字体的槽位码位上（如 U+E631），
                # **不是**真实 Unicode 汉字，只是小學堂用来排版的槽位。
                # 「部件」同理（部件字也是槽位）。
                if "外字集" in it["font"]:
                    variants.append(f"{it['font_id']}_{it['codepoint']}")
                continue
            if not lishu and it["char"]:
                lishu = it["char"]
        # **现代字不能直接取第一个字頭圖。**
        #
        # 字頭行里有多张圖：標楷體（楷書字頭）、北師大說文小篆（字頭的小篆寫法）、
        # 標楷體外字集N（異體字）、標楷體部件外字（部件）。它們的 alt 記的是
        # **各字体自己的槽位码位**，而这些码位**不都是真汉字**：
        #
        #   標楷體（字體號 0）      → 真實 Unicode（實測 301 條全是真的）
        #   北師大說文小篆（字體號 27）→ 多數是真的，罕見字落在**私用區**（U+F3F2 ≈ 上）
        #   標楷體外字集N（1..13）  → **全是私用區**（異體字的排版槽位）
        #   標楷體部件外字          → 私用區（部件字）
        #
        # 以前直接取 head_items[0]，遇到「小篆字頭是私用區」的字頭就取错了——
        # 試點裡 **1,107 條實例（18%）** 的现代字身份是错的。
        # 規則改成：**取槽位码位是真實漢字的那一項**；有多項時優先字體號 0。
        modern, modern_src = "", ""
        modern_slot = ""
        for it in head_items:
            if it["font_id"] != "0" and modern:
                continue
            if not usable_modern_char(it["char"]):
                continue
            modern, modern_src = it["char"], (it["font"] or f"字體{it['font_id']}")
            modern_slot = f"{it['font_id']}_{it['codepoint']}"
            if it["font_id"] == "0":
                break
        if not modern:
            # 全是私用區槽位 → 现代字身份不明（少数）。记下槽位，留给人看。
            if head_items:
                modern = head_items[0]["char"]
                modern_slot = f"{head_items[0]['font_id']}_{head_items[0]['codepoint']}"
            modern_src = "pua-slot"
        heads.append({"zi_order": int(zi_order), "modern_char": modern,
                      "modern_char_source": modern_src,
                      "modern_char_slot": modern_slot,
                      "lishu_char": lishu, "variants": variants})
        # 字形单元：按「下一个 <td」切
        pos = 0
        cells: list[str] = []
        while True:
            m = CELL_START_RE.search(block, pos)
            if not m:
                break
            nxt = block.find("<td", m.end())
            cells.append(block[m.end(): nxt if nxt != -1 else len(block)])
            pos = m.end()
        for cell in cells:
            img = IMG_RE.search(cell)
            if not img:
                continue
            query = urllib.parse.parse_qs(urllib.parse.urlparse(img.group(1)).query)
            font = decode_font((query.get("font") or [""])[0])
            text = urllib.parse.unquote((query.get("text") or [""])[0])
            pua = None
            font_id = ""
            for fid, hexcp in ALT_RE.findall(img.group(0)):
                pua = hexcp.upper()
                font_id = fid
                break
            if pua is None and text:
                pua = "".join(f"{ord(c):X}" for c in text)
            if not pua:
                continue
            br = BR_RE.search(cell)
            short = ""
            if br:
                tail = br.group(1)
                noise = NOISE_RE.search(tail)
                if noise:
                    tail = tail[:noise.start()]
                short = re.sub(r"\s+", " ", TAG_RE.sub(" ", tail)).strip()
                short = short.replace("&nbsp;", " ").strip()
            glyphs.append({
                "pua": pua,
                "font_id": font_id,
                "font": font,
                "source_short": short,
                "zi_order": int(zi_order),
                "text": text,
            })
    return {"hits": hits, "pages": pages, "heads": heads, "glyphs": glyphs,
            "base_pages": base_pages}


def instance_key(rec: dict) -> tuple:
    """一个字形**实例**的身份：字頭 + 出處簡號 + 字体号 + 码位。

    实例与字形要分清：
      * 字形（shape） = (字体号, 码位)——同一个字形会被多个字頭 / 出處复用，
        位图只取一次，描摹也只做一次；
      * 实例          = 字頭 + 出處簡號 + 字形——楚系层收「一字多形」，
        分桶维度是**出土文献**，所以出處簡號必须进实例身份，
        否则同一个字形在两件出土文献里的两次出现会被当成一条，出處就丢了。
    """
    return (rec.get("zi_order"), rec.get("source_short", ""),
            rec.get("font_id", ""), rec.get("pua"))


def image_url(pua: str, font: str, size: int) -> str:
    """字形图的取图地址（text 传真正的 PUA 字符，不是十六进制字符串）。

    别自己先 quote 再 urlencode——那样会编码两遍，text 变成 %25EE%2582%25A9。
    """
    word = "".join(chr(int(c, 16)) for c in pua.split(","))
    q = urllib.parse.urlencode({"text": word, "font": font, "size": str(size),
                                "style": "regular", "color": "#000000"})
    return f"{HOST}/ImageText2/ShowImage.ashx?{q}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# 解析器的**语义版本**：解析面变了就手动 +1。
# 改了下面 PARSER_FUNCS 里的函数或那几条正则，也要 +1。
PARSER_VERSION = "2026-10-31-r1"

# 参与指纹的**解析面**：只有「怎么把页面解析成实例」这一面进了指纹。
#
# 早先的写法是整个文件的哈希，结果调一下取图参数（延迟、批量、并发）
# 就要把十几万条索引全部作废重解析——几十小时的活，白白重来。
# 现在改成只哈希解析面：抓取驱动、位图阶段、清单阶段怎么改都不影响索引。
PARSER_FUNCS = ("parse_result_page", "_head_items", "parse_reference_table", "decode_font")


def fingerprint() -> str:
    """把**解析面**的哈希进指纹——解析器一改，旧索引自动失效。

    指纹 = ``PARSER_VERSION`` + 下面这些解析函数的源码 + 正则 + 字体前缀表。
    **不哈希整个文件**：与「怎么解析」无关的改动（取图延迟、批量、并发、
    错误处理）不该让已经抓好的索引作废。
    """
    digest = hashlib.sha256()
    digest.update(f"|version:{PARSER_VERSION}".encode("utf-8"))
    for name in PARSER_FUNCS:
        digest.update(f"|fn:{name}".encode("utf-8"))
        digest.update(inspect.getsource(globals()[name]).encode("utf-8"))
    digest.update(b"|filters:")
    digest.update(GLYPH_FONT_PREFIX.encode("utf-8"))
    for db, prefix in sorted(GLYPH_FONT_PREFIXES.items()):
        digest.update(f"|{db}:{prefix}".encode("utf-8"))
    digest.update(b"|regex:")
    for rx in (IMG_RE.pattern, ALT_RE.pattern, CELL_START_RE.pattern,
               BR_RE.pattern, HITS_RE.pattern, PAGES_RE.pattern,
               STARTORDER_RE.pattern, NOISE_RE.pattern):
        digest.update(rx.encode("utf-8"))
    return digest.hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- 各 mode

class PageFetcher:
    """页面侧传输器：借 PowerShell（Windows 原生 SChannel TLS）取 xiaoxue.iis.sinica.edu.tw。

    为什么要绕这一道：实测同一份请求，**PowerShell / .NET（SChannel）正常返回，
    Python 与 curl（OpenSSL）一律被 nginx 以 405 挡在门外**；用裸 socket 逐字节复刻
    PowerShell 的请求头、请求体与头序，仍然 405——判别发生在 TLS 层，不在 HTTP 层。
    而取图那侧（char.iis.sinica.edu.tw 的 ICS 渲染 API）对 Python 是放开的，
    所以只有「页面」这一侧需要 PowerShell。
    """

    PS = ROOT / "src" / "fetch_xiaoxuetang_pages.ps1"

    def __init__(self, delay: float = 4.0, log=print):
        self.delay = delay
        self.log = log
        self.last = 0.0

    def _wait_turn(self) -> None:
        wait = self.last + self.delay * random.uniform(0.7, 1.3) - time.time()
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()

    def _run_ps(self, args: list[str]) -> subprocess.CompletedProcess:
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
               "-File", str(self.PS)] + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

    def run_ps(self, args: list[str]) -> subprocess.CompletedProcess:
        """直接调 PowerShell 传输器（不解释退出码）。"""
        return self._run_ps(args)

    def search_page(self, db: str, per_page: int, cache: Path,
                    zi_order: int = 0, page_to: int = 1,
                    reference: str = "", reuse: bool = True) -> str:
        """取检索结果页，返回 HTML 文本。

        ``zi_order`` 是字號（0 表示不查），``page_to`` 是字頭内页号，
        ``reference`` 是出處代号。**PageNo 一律留空**——见 ``stage_pages`` 的说明。

        ``reuse``：缓存里已有这一页就直接用，不再发请求。全量跑几万页时，
        断点续跑靠的就是这个——重解析旧页不重新下载。
        """
        cache.parent.mkdir(parents=True, exist_ok=True)
        if reuse and cache.exists() and cache.stat().st_size > 0:
            return cache.read_text(encoding="utf-8")
        self._wait_turn()
        args = ["-Mode", "search", "-Database", db,
                "-ZiOrder", str(zi_order), "-PageTo", str(page_to),
                "-PerPage", str(per_page), "-Out", str(cache)]
        if reference:
            args += ["-Reference", reference]
        proc = self._run_ps(args)
        code = proc.returncode
        if code == 3:
            raise Blocked(BLOCK_GEO, "PowerShell 报地区封锁")
        if code == 4:
            raise Blocked(BLOCK_IP, "PowerShell 报 IP 封锁")
        if code != 0:
            out = (proc.stdout or "") + (proc.stderr or "")
            raise Blocked(BLOCK_SOFT, f"PowerShell 退出码 {code}：{out.strip()[:200]}")
        if not cache.exists():
            raise Blocked(BLOCK_SOFT, f"PowerShell 说存了但文件不在：{cache}")
        return cache.read_text(encoding="utf-8")

    def one_page(self, mode: str, db: str, out: Path) -> str:
        """取单个页面（license / stats）。"""
        self._wait_turn()
        args = ["-Mode", mode, "-Database", db, "-Out", str(out)]
        proc = self._run_ps(args)
        code = proc.returncode
        if code == 3:
            raise Blocked(BLOCK_GEO, "PowerShell 报地区封锁")
        if code == 4:
            raise Blocked(BLOCK_IP, "PowerShell 报 IP 封锁")
        if code != 0 or not out.exists():
            out_msg = (proc.stdout or "") + (proc.stderr or "")
            raise Blocked(BLOCK_SOFT, f"PowerShell 退出码 {code}：{out_msg.strip()[:200]}")
        return out.read_text(encoding="utf-8")

    def reference_pages(self, db: str, out_dir: Path) -> list[Path]:
        """取某库的出處表（可能有多张）。

        **该库没有出處表页**不算错误：实测金文（/jinwen）与小篆（/xiaozhuan）
        的首页根本没有出處表链接，路径返回 404。退出码 6 就是这个情况，
        返回空列表即可——归属闸门改走别的依据。
        """
        self._wait_turn()
        out_dir.mkdir(parents=True, exist_ok=True)
        proc = self._run_ps(["-Mode", "references", "-Database", db, "-Out", str(out_dir)])
        code = proc.returncode
        if code == 3:
            raise Blocked(BLOCK_GEO, "PowerShell 报地区封锁")
        if code == 4:
            raise Blocked(BLOCK_IP, "PowerShell 报 IP 封锁")
        if code == 6:
            print(f"  {db}: 该库无出處表页（实测如此：金文 / 小篆）")
            return []
        if code != 0:
            out_msg = (proc.stdout or "") + (proc.stderr or "")
            raise Blocked(BLOCK_SOFT, f"PowerShell 退出码 {code}：{out_msg.strip()[:200]}")
        return sorted(out_dir.glob("*.html"))


def mode_license(pages: PageFetcher, args) -> int:
    out_dir = ROOT / "src" / "licenses"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "xiaoxuetang-CC0-1.0-statement.html"
    text = pages.one_page("license", "", html_path)
    m = re.search(r'<div class="About">(.*?)</div>', text, re.S)
    quote = ""
    if m:
        quote = re.sub(r"\s+", " ", TAG_RE.sub("", m.group(1))).strip()
    md = f"""# 小学堂《版權聲明》快照（CC0 1.0）

- 来源：<{LICENSE_STATEMENT_URL}>
- 取回时刻：{now_iso()}（UTC）
- 原文副本：`xiaoxuetang-CC0-1.0-statement.html`（逐字节）
- 许可标识：`{LICENSE_ID}` · <{LICENSE_URL}>

## 原文

> {quote}

## 为什么留这份快照

汉典《服务条款》第四条是「本站字词、古籍、诗词、书法诸作」一句笼统的归公宣告；
小学堂这份声明**点名了权利人、对象与范围**：通过查询界面取得的「各解析度『字形圖片』」
与「字形屬性資訊」被明示以 CC0 1.0 拋棄。本仓库的字形 SVG 与逐条出处记录正落在
这两类对象里，所以这份声明是本仓库古文字各层的直接授权依据。

**注意**：CC0 只处置中研院自己那部分权利，不消灭**摹本底本**（《甲骨文編》
《楚系簡帛文字編》《傳抄古文字編》《睡虎地秦簡文字編》等在版出版物）的著作权。
底本链条在 `THIRD_PARTY_NOTICES.md` 逐层说明。
"""
    (out_dir / "xiaoxuetang-CC0-1.0-statement.md").write_text(md, encoding="utf-8", newline="\n")
    print(f"许可快照已写入 {out_dir}")
    print(f"  原文引用：{quote[:140]}…")
    return 0


def _parse_scale(text: str) -> tuple[int, int, str]:
    """从库首页的「最新消息」栏解析「字頭 N 個，字形 M 個。（日期）」。

    站点混用简繁（「个」与「個」），且隸變庫写的是「收錄字頭 N 個，篆、隸字形 M 個」，
    所以这里逐项独立找，不写死整句。
    """
    heads = re.search(r"字頭\s*([\d,]+)\s*[个個]", text)
    glyphs = re.search(r"字形\s*([\d,]+)\s*[个個]", text)
    date = re.search(r"（\s*(\d{4}/\d{1,2}/\d{1,2})\s*）", text)
    return (
        int(heads.group(1).replace(",", "")) if heads else 0,
        int(glyphs.group(1).replace(",", "")) if glyphs else 0,
        date.group(1) if date else "?",
    )


def mode_stats(pages: PageFetcher, args) -> int:
    out_dir = Path(args.out) if args.out else ROOT / "tmp" / "xxt" / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for db, meta in DBS.items():
        html_path = out_dir / f"{db}-home.html"
        text = pages.one_page("stats", db, html_path)
        heads, glyphs, date = _parse_scale(text)
        rows.append((db, meta["label"], heads, glyphs, date))
        print(f"  {db:10s} 字頭 {heads:>6}  字形 {glyphs:>6}  ({date})")
    md = ["# 小学堂各库规模快照", "", f"取回时刻：{now_iso()}（UTC）", "",
          "| 库 | 路径 | 字頭 | 字形 | 页面日期 |", "|---|---|---:|---:|---|"]
    for db, label, heads, glyphs, date in rows:
        md.append(f"| {label} | `/{db}` | {heads:,} | {glyphs:,} | {date} |")
    (out_dir / "stats.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"规模快照已写入 {out_dir}")
    return 0


REF_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
REF_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)


def parse_reference_table(text: str) -> list[dict]:
    """解析出處表。

    各库的出處表**列数与列序不一样**：楚系是「全稱｜簡稱｜出處」三列，
    甲骨是「簡稱｜全稱」两列（而且「全稱」格里塞的是《甲骨文編》的引書全称与版本）。
    所以先读表头认出每一列是什么，再按位置取值，不写死列序。
    """
    rows: list[dict] = []
    header: list[str] = []
    for tr in REF_ROW_RE.findall(text):
        cells = [re.sub(r"\s+", " ", TAG_RE.sub("", c)).strip()
                 for c in REF_CELL_RE.findall(tr)]
        if not cells:
            continue
        if not header:
            if any("簡稱" in c or "全稱" in c for c in cells):
                header = cells
            continue
        rec: dict[str, str] = {}
        for name, value in zip(header, cells):
            rec[name] = value
        if rec.get("簡稱") or rec.get("全稱"):
            rows.append(rec)
    return rows


def mode_references(pages: PageFetcher, args) -> int:
    out_dir = Path(args.out) if args.out else ROOT / "tmp" / "xxt" / "references"
    out_dir.mkdir(parents=True, exist_ok=True)
    for db in (args.db_list or sorted(DBS)):
        files = pages.reference_pages(db, out_dir / db)
        for html_file in files:
            text = html_file.read_text(encoding="utf-8", errors="replace")
            clean = parse_reference_table(text)
            csv = html_file.with_suffix(".csv")
            with csv.open("w", encoding="utf-8", newline="") as fh:
                fh.write("code,corpus_full,source_publication,source_url,retrieved_at\n")
                for rec in clean:
                    code = rec.get("簡稱", "")
                    full = rec.get("全稱", "")
                    pub = rec.get("出處", "")
                    # URL 要还原成站点上的真实路径：文件名是「路径各段用 - 拼」的
                    # （chuwenzi-Reference-Reference → /chuwenzi/Reference/Reference）
                    src_url = f"{HOST}/{html_file.stem.replace('-', '/')}"
                    fh.write(f'"{code}","{full}","{pub}","{src_url}","{now_iso()}"\n')
            print(f"  {db:10s} {html_file.name:44s} -> {len(clean)} 行")
    return 0


def stage_pages(pages: PageFetcher, args) -> int:
    """阶段一：按字號（ZiOrder）枚举检索结果页，落盘并解析出「字形索引」。

    请求形状（实测，这是唯一稳定可用的形状）::

        POST {ZiOrder: <字號>, PageNo: '', PageTo: <页号>,
              EudcFontChar: '', Reference: '', PaginalZiNum: 50}

    三条实测结论：

    1. **PageNo 必须留空**。填 1 会让 ZiOrder 检索整体失效——ZiOrder=2 / 100 /
       3260 一律 0 命中；留空则 ZiOrder=2 → 5 命中、ZiOrder=3260 → 187 命中，
       与该字頭的字形数一致（子字頭，order=3260）。
    2. **PageTo 是字頭内页号**。字頭「一」有 319 个字形 / 7 页，PageTo=1..7
       内容各不相同，PageTo=8 为空。
    3. **每页自带该字頭的字形总数与页数**（页面顶部的「共搜尋到 N 字／M 頁」），
       所以枚举完可以直接对账：各字頭的字形数之和应当等于该库宣称的字形总数。

    出處代号（Reference）那一轴也能查，但只有 PageNo=1 时才响应，且「共搜尋到 N 字」
    的含义随匹配到的字頭数变化，用它做完整性校验不可靠。ZiOrder 这一轴对七个库
    一视同仁——金文、小篆根本没有出處表页，只有这条轴能走通。
    """
    db = args.db
    out_dir = Path(args.out)
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.jsonl"

    fp = fingerprint()
    seen: set[tuple] = set()
    if index_path.exists() and not args.restart:
        # 只保留当前指纹的记录。解析器一改，指纹就变，旧记录作废——
        # 但它们不能留在文件里，否则新旧记录混在一起，索引就成了两套的叠加。
        lines = [ln for ln in index_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        kept: list[str] = []
        for line in lines:
            rec = json.loads(line)
            if rec.get("fingerprint") == fp:
                kept.append(line)
                seen.add(instance_key(rec))
        if len(kept) != len(lines):
            index_path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    else:
        index_path.unlink(missing_ok=True)

    hits_total = 0
    heads_done = 0
    glyph_font_prefix = GLYPH_FONT_PREFIXES.get(db, GLYPH_FONT_PREFIX)
    fh = index_path.open("a", encoding="utf-8", newline="\n")
    try:
        zi_to = args.zi_to or DBS[db]["heads"]
        for zi in range(args.zi_from, zi_to + 1):
            page = 1
            total_pages = 1
            while page <= total_pages:
                cache = pages_dir / f"zi{zi:06d}-p{page:03d}-n{args.per_page}.html"
                html = pages.search_page(db, args.per_page, cache,
                                         zi_order=zi, page_to=page)
                info = parse_result_page(html)
                if page == 1:
                    total_pages = max(1, info["pages"])
                    hits_total += info["hits"]
                    heads_done += 1
                    if heads_done % args.progress_every == 0 or zi <= args.zi_from + 2:
                        head_txt = "".join(h["modern_char"] for h in info["heads"]) or "?"
                        print(f"  zi={zi} 字頭={head_txt!r} 字形 {info['hits']} 個 / "
                              f"{total_pages} 頁（累计 {hits_total:,}）")
                for g in info["glyphs"]:
                    if not g["font"].startswith(glyph_font_prefix):
                        continue
                    # 实例的身份 = (字頭, 出處簡號, 字体号, 码位)
                    #
                    # **不能只按 pua 去重**：同一个字形会在多个字頭 / 出處下复用
                    # （试点 20 个字頭 960 个实例，唯一 pua 只有 572 个），
                    # 按 pua 去重会把「同一字形、不同出處」的第二条实例丢掉——
                    # 等于把楚系层「按出土文献分桶」这个维度砍掉一半。
                    # 也不能只按 (字体号, 码位) 去重：PUA 是**按字体分命名空间**的，
                    # 同一个码位在不同字体下是不同的字形。
                    inst = (g["zi_order"], g["source_short"], g.get("font_id", ""), g["pua"])
                    if inst in seen:
                        continue
                    seen.add(inst)
                    fh.write(json.dumps({
                        "db": db, "pua": g["pua"], "font_id": g.get("font_id", ""),
                        "font": g["font"],
                        "source_short": g["source_short"], "zi_order": g["zi_order"],
                        "modern_char": next((h["modern_char"] for h in info["heads"]
                                             if h["zi_order"] == g["zi_order"]), ""),
                        # 现代字是从哪一项取来的（標楷體 / 北師大說文小篆 / 私用區槽位），
                        # 记下来才能判断这个身份可不可信。
                        "modern_char_source": next((h.get("modern_char_source", "")
                                                   for h in info["heads"]
                                                   if h["zi_order"] == g["zi_order"]), ""),
                        # 字頭取自哪个槽位（字体号_码位）。取不到真汉字时，
                        # 这个槽位就是**临时身份**的依据，必须记下来。
                        "modern_char_slot": next((h.get("modern_char_slot", "")
                                                  for h in info["heads"]
                                                  if h["zi_order"] == g["zi_order"]), ""),
                        # 字頭的异体字清单（楷書字頭 + 各異體）。漢典层的 modern_char
                        # 记的就是**異體字**（弌 / 靝 / 兲 …），不是楷書字頭；
                        # 有了这份清单才能把两边的字頭口径对齐。
                        "variants": next((h.get("variants", []) for h in info["heads"]
                                          if h["zi_order"] == g["zi_order"]), []),
                        "base_pages": info.get("base_pages", []),
                        "page_url": f"{HOST}/{db}/PageResult/PageResult",
                        "fingerprint": fp,
                    }, ensure_ascii=False, sort_keys=True) + "\n")
                fh.flush()
                page += 1
                if args.max_pages and page > args.max_pages:
                    break
    finally:
        fh.close()
    claim = DBS[db]["glyphs"]
    print(f"  {db}: 字頭 {heads_done} 个，索引累计 {len(seen)} 个实例")
    print(f"  {db}: 字形数合计 {hits_total:,} / 宣称 {claim:,}"
          f"（差 {hits_total - claim:+,}）")
    return 0


def stage_images(pages: PageFetcher, args) -> int:
    """阶段二：按索引取位图。

    取图端点是站点自己的 ``/ImageText2/ShowImage.ashx``，**必须走 PowerShell**：
    Python 直连会被地区规则挡回 36 KB 的 HTML（"current country or region is not yet
    open"）。两个参数上的坑（都是实测踩出来的）：

    1. ``text`` 要传**真正的 PUA 字符**（URL 编码），不能传十六进制字符串。
       传 ``E0A9`` 会被当成四个字面字符，渲染出一张写着 "E0A9" 的图。
    2. ``font`` 是**必须**的。PUA 码位按字体分命名空间：同一个 E0A9，在
       「中研院楚系簡帛文字重文一」里是「一」的楚文字，在「…重文五」里是「天」。
       少带或带错字体，取回来的就是别的字。

    图片按 (字体号, 码位) 缓存——同一个 (字体, 码位) 会在多个字頭下复用，
    取一次即可，描摹也只做一次。
    """
    db = args.db
    out_dir = Path(args.out)
    img_dir = out_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.jsonl"
    index_path = out_dir / "index.jsonl"
    if not index_path.exists():
        raise SystemExit(f"先跑 --stage pages：{index_path} 不存在")

    # **尺寸闸门**：位图按 (字体号, 码位) 缓存，缓存里**不记尺寸**，
    # 所以换尺寸重抓时会**复用旧图**——而描摹参数（Douglas-Peucker 的 eps 是
    # **像素**）是按尺寸定的，尺寸混用会让轮廓过平滑或过毛刺。
    # 这里把本次用的尺寸记在 img_meta.json 里，与已记的不一致就**直接报错**，
    # 要换尺寸就换个目录（或先清掉 img/）。
    meta_path = out_dir / "img_meta.json"
    if meta_path.is_file():
        try:
            old = json.loads(meta_path.read_text(encoding="utf-8")).get("size")
        except (OSError, ValueError):
            old = None
        if old is not None and int(old) != int(args.size):
            raise SystemExit(
                f"位图目录里已缓存的是 {old}px 的图，本次要 {args.size}px——"
                f"混用会让描摹参数对不上。请换个 --out 目录，或先清掉 {img_dir}。")
    meta_path.write_text(json.dumps({"db": db, "size": int(args.size),
                                     "note": "位图按 (字体号,码位) 缓存，不记尺寸；换尺寸必须换目录"},
                                    ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    fp = fingerprint()
    recs: list[dict] = []
    seen_inst: set[tuple] = set()
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("fingerprint") != fp:
            continue
        k = instance_key(rec)
        if k in seen_inst:
            continue
        seen_inst.add(k)
        recs.append(rec)
    if not recs:
        raise SystemExit("索引里没有当前指纹的记录，先跑 --stage pages")

    # 唯一 (字体号, 码位)
    shapes: dict[str, dict] = {}
    for rec in recs:
        key = f"{rec.get('font_id', '')}_{rec['pua']}"
        if key not in shapes:
            shapes[key] = {"pua": rec["pua"], "font": rec["font"], "font_id": rec.get("font_id", "")}
    # **只取层真正要用的那些字形**。
    #
    # 小學堂一个库动辄三万多个字形，但层的规则是「每个 (现代字, 文献) 留 1 条、
    # 每个现代字最多 5 条」，筛完再扣掉漢典层已有的字形，真正要抓的往往只有两成
    # （楚系：37,180 → 2,558）。清单由 src/plan_xxt_fetch.py 生成，一行一个字形键。
    want: set[str] | None = None
    if args.shape_list:
        sp = Path(args.shape_list)
        if not sp.is_file():
            raise SystemExit(f"字形清单不存在：{sp}")
        want = {ln.strip() for ln in sp.read_text(encoding="utf-8").splitlines() if ln.strip()}
        shapes = {k: v for k, v in shapes.items() if k in want}
    todo = [(k, v) for k, v in shapes.items()
            if not (img_dir / f"{k}.png").exists() or (img_dir / f"{k}.png").stat().st_size == 0]
    if args.limit:
        todo = todo[:args.limit]
    print(f"  {db}: 字形实例 {len(recs)}，唯一字形 {len(shapes)}，待取 {len(todo)}"
          + (f"（清单限定 {len(want):,} 个字形）" if want is not None else ""))

    if todo:
        list_path = out_dir / "images-list.tsv"
        batch = max(1, args.batch)
        lanes = max(1, args.lanes)
        rounds = max(1, args.rounds)
        lock = threading.Lock()
        state = {"done": 0}

        def have(key: str) -> bool:
            p = img_dir / f"{key}.png"
            return p.exists() and p.stat().st_size > 0

        def run_batch(items: list[tuple[str, dict]], tag: str) -> None:
            """跑一批。

            **一批坏了不影响别的批**：早期版本一遇到非零退出码就 break，
            结果 2,600/11,190 之后整轮停摆，后面八千多张白等。
            现在只记一笔，继续下一批；剩下的由外层的重试轮兜底。
            """
            part = list_path.with_name(f"images-list-{tag}.tsv")
            with part.open("w", encoding="utf-8", newline="\n") as fh:
                for key, v in items:
                    dest = (img_dir / f"{key}.png").resolve()
                    fh.write(f"{v['pua']}\t{v['font']}\t{dest}\n")
            proc = pages.run_ps(["-Mode", "images", "-Database", db,
                                 "-ListFile", str(part.resolve()),
                                 "-Size", str(args.size), "-Delay", str(args.delay)])
            if proc.returncode != 0:
                print(f"  ! 取图批次失败（退出码 {proc.returncode}）：{(proc.stdout or '')[-200:]}")
                return
            part.unlink(missing_ok=True)
            with lock:
                state["done"] += len(items)
                print(f"  … 已取 {state['done']}/{len(todo)}（{tag}）")

        def run_lane(items: list[tuple[str, dict]], lane: int, rnd: int) -> None:
            for start in range(0, len(items), batch):
                run_batch(items[start:start + batch], f"r{rnd}l{lane}s{start:06d}")

        for rnd in range(1, rounds + 1):
            missing = [(k, v) for k, v in todo if not have(k)]
            if not missing:
                break
            if rnd > 1:
                print(f"  ⟳ 第 {rnd} 轮重试：还差 {len(missing)} 张")
            # 交错分片：各路的图在站点侧是均匀铺开的，不会一路打在同一批码位上。
            chunks = [missing[i::lanes] for i in range(lanes)]
            threads = []
            for li, chunk in enumerate(chunks):
                if not chunk:
                    continue
                t = threading.Thread(target=run_lane, args=(chunk, li, rnd), daemon=True)
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
        still = [k for k, _ in todo if not have(k)]
        if still:
            print(f"  ! 仍有 {len(still)} 张没取到（{rounds} 轮之后）：{still[:5]}")
        else:
            print(f"  ✓ 全部取到：{len(todo)} 张")

    # 清单：按实例记（一个实例 = 一个字頭下的一个字形）
    with manifest_path.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in recs:
            key = f"{rec.get('font_id', '')}_{rec['pua']}"
            img = img_dir / f"{key}.png"
            if not img.exists():
                continue
            data = img.read_bytes()
            fh.write(json.dumps({
                "db": db, "pua": rec["pua"], "font_id": rec.get("font_id", ""),
                "font": rec["font"], "shape_key": key,
                "source_short": rec["source_short"], "zi_order": rec["zi_order"],
                "modern_char": rec.get("modern_char", ""),
                "base_pages": rec.get("base_pages", []),
                "source_url": image_url(rec["pua"], rec["font"], args.size),
                "source_page_url": rec.get("page_url", ""),
                "sha256": sha256_bytes(data), "bytes": len(data),
                "size": args.size, "retrieved_at": now_iso(),
                "fingerprint": fp,
            }, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"  {db}: 清单写入 {manifest_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="抓取小学堂字形实例 / 出處表 / 许可快照")
    ap.add_argument("--mode", required=True,
                    choices=("glyphs", "references", "license", "stats"),
                    help="要抓什么")
    ap.add_argument("--db", default="chuwenzi", choices=sorted(DBS), help="目标库")
    ap.add_argument("--db-list", default=None,
                    help="--mode references 时抓哪几个库，逗号分隔（默认全部）")
    ap.add_argument("--stage", default="all", choices=("pages", "images", "all"),
                    help="--mode glyphs 的阶段：pages 枚举字頭页面 / images 取位图")
    ap.add_argument("--out", default=None, help="落盘目录（--mode glyphs 默认 tmp/xxt/<db>）")
    ap.add_argument("--size", type=int, default=200,
                    help="取图尺寸（像素，实测 800 可用、1200 报 400）")
    ap.add_argument("--batch", type=int, default=200,
                    help="--stage images 每个 PowerShell 进程取多少张（省进程启动开销）")
    ap.add_argument("--delay", type=float, default=4.0, help="两次请求之间的间隔秒数（默认 4.0）")
    ap.add_argument("--lanes", type=int, default=1,
                    help="--stage images 同时开几路取图（默认 1）。"
                         "实测：两路并发时端点延迟不劣化（1,015–1,073 ms），"
                         "单路 1 秒间隔 ≈ 2.02 s/张，两路 ≈ 1 s/张")
    ap.add_argument("--rounds", type=int, default=3,
                    help="--stage images 最多重试几轮（默认 3）。"
                         "单张图失败不中断整批，剩下的交给下一轮")
    ap.add_argument("--shape-list", default=None,
                    help="--stage images 只取这些字形（每行一个「字体号_码位」）。"
                         "清单由 src/plan_xxt_fetch.py 生成：按层的选取规则筛过、"
                         "再扣掉漢典层已有的字形")
    ap.add_argument("--per-page", type=int, default=400,
                    help="每页字形数（实测 400 可用；与 50/页 逐实例一致，请求数少约一成）")
    ap.add_argument("--image-size", type=int, default=36, help="页面上的字形显示大小（站点 16–72）")
    ap.add_argument("--max-pages", type=int, default=0, help="最多翻几页（调试用，0 = 不限）")
    ap.add_argument("--progress-every", type=int, default=50, help="每取多少个打印一次进度")
    ap.add_argument("--zi-from", type=int, default=1, help="字號起始（--stage pages）")
    ap.add_argument("--zi-to", type=int, default=0, help="字號結束（0 = 到该库字頭数上限）")
    ap.add_argument("--limit", type=int, default=0, help="--stage images 只取前 N 个（调试用）")
    ap.add_argument("--restart", action="store_true", help="忽略已有清单，从头再来")
    args = ap.parse_args(argv)

    args.db_list = [x.strip() for x in (args.db_list or "").split(",") if x.strip()] or None

    if args.mode == "glyphs" and not args.out:
        args.out = str(ROOT / "tmp" / "xxt" / args.db)

    pages = PageFetcher(delay=args.delay)
    print(f"模式 {args.mode}；间隔 {args.delay}s")
    if args.mode == "license":
        return mode_license(pages, args)
    if args.mode == "stats":
        return mode_stats(pages, args)
    if args.mode == "references":
        return mode_references(pages, args)
    if args.stage in ("pages", "all"):
        stage_pages(pages, args)
    if args.stage in ("images", "all"):
        stage_images(pages, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
