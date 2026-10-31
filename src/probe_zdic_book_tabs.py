#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨栏探测：汉典某个「书法」文献代号属于哪个书体栏。

为什么需要它：汉典的字页（``https://www.zdic.net/hans/<字>/<kind>``）里，
**同一个字在不同书体栏下会给出不同实例**。汉典「楚系簡帛」栏里就混着
秦系简牘（《睡虎地秦簡文字編》《秦簡牘文字編》的底本）与傳抄古文
（《傳抄古文字編》的磚文）——这些材料不属于楚系。

判断归属不能靠猜书名，得看**证据**：同一个文献代号如果在别的书体栏里也出现，
那它的「家」就在那儿；只出现在楚系簡帛栏，才是楚系材料。

用法：

    python src/probe_zdic_book_tabs.py <代号> <现代字> [<代号> <现代字> ...]

例：

    python src/probe_zdic_book_tabs.py 天策 㒳 雨 之

输出逐个代号列出在各个别的书体栏里的命中条数与例句。
取样字要选**确实带该代号**的字，否则探不到东西——从题记里挑（见
``glyphs/<层>/index.csv`` 的 ``variant`` 列）。

只用标准库。请求之间有间隔，别把汉典当沙盒扫。
"""
from __future__ import annotations

import re
import sys
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

CAPTION_RE = re.compile(r'class="caption"[^>]*>(.*?)</div>', re.S)

# 别的书体栏（楚系簡帛是「本栏」，不查自己）。
# 隶书栏里有汉简与马王堆帛书，秦文字栏是秦系简牘，傳抄古文栏是徐在国系统。
OTHER_TABS = ("chuanchao", "qinwenzi", "lishu", "xiaozhuan",
               "jiaguwen", "jinwen")

DELAY = 0.25


def captions_of(char: str, kind: str) -> list[str]:
    """取某个字在某个书体栏下的全部题记。取不到返回空表。"""
    url = f"https://www.zdic.net/hans/{urllib.parse.quote(char)}/{kind}"
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "zh-CN,zh;q=0.9"})
    try:
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001 —— 探不到就当没有，别中断整批
        print(f"    ! {kind}: 取页失败 {exc!r}")
        return []
    out: list[str] = []
    for m in CAPTION_RE.finditer(html):
        text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if text:
            out.append(text)
    return out


def probe(code: str, char: str) -> dict[str, list[str]]:
    """在别的书体栏里找这个代号，返回 {栏名: 命中题记}。"""
    hits: dict[str, list[str]] = {}
    for kind in OTHER_TABS:
        matched = [c for c in captions_of(char, kind) if code in c]
        if matched:
            hits[kind] = matched
        time.sleep(DELAY)
    return hits


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) < 2 or len(args) % 2:
        print(__doc__)
        return 2
    for i in range(0, len(args), 2):
        code, char = args[i], args[i + 1]
        print(f"=== 代号「{code}」  取样字 {char} ===")
        hits = probe(code, char)
        if not hits:
            print("    别的书体栏都没有 —— 只在楚系簡帛栏出现")
        else:
            for kind, matched in hits.items():
                print(f"    {kind:12s} 命中 {len(matched)} 条，例：{matched[0]}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
