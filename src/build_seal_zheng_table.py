#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「现代字 → 正篆码位」反查表（篆书层入库的第二步）。

用法::

    python src/build_seal_zheng_table.py --out tmp/research/seal-modern-to-zheng.txt

**这张表解决什么问题。** 篆书区块的键是 Unicode 篆书区块码位（U+3D000–U+3FC3F），
但字形来源（汉典）给的是**现代汉字**。同一个现代字在篆书区块里可能有多个码位
（正篆 + 重文 / 异体），必须挑一个当键，挑哪个就是这张表说了算。

**正篆判定规则（R）**：

1. 《说文》**主序列**优先（``kSEAL_THXSrc`` 为 ``TH-#####``），
   附录（``TH-X###`` / ``TH-Y###``）靠后；
2. 同组内比**四本《说文》收录此字的次数**（``kSEAL_CCZSrc`` / ``DYCSrc`` /
   ``QJZSrc`` / ``THXSrc`` 各算一次），收录多的在前；
3. 再比**码位大小**，小的在前。

规则 1、3 与 Unicode 核心规范 §18.14 的篆书码位排序规则（按 540 部、组内依
THX 原书顺序）一致。

**分组依据是 OpenCC 的 ``SealCharacters.txt``，不是 Unicode 的 ``kSEAL_MCJK``。**
Unicode 把篆书码位 U+3D06D 记成「王」，但同一份文件里的 ``kSEAL_Rad``
（``6.3D06D``，说文第 6 部「玉」部的部首字）自相矛盾；按 OpenCC 的分组，
U+3D06D 归「玉」。详见 ``glyphs/seal/README.md``。

**自检。** 脚本会拿 OpenCC 自己的反查首选（``# @reverse-prefer:`` 指令与
首选项）跟规则 R 的结果逐个对拍，多码位字全部一致才算通过——
这是对规则的一次独立交叉验证，不是循环论证。

数据来源（两者都可公开复核）：

* Unicode 18.0 ``SealSources.txt`` — <https://www.unicode.org/Public/18.0.0/ucd/SealSources.txt>
  （Unicode License v3）
* OpenCC ``SealCharacters.txt`` — <https://cdn.jsdelivr.net/gh/BYVoid/OpenCC@master/data/dictionary/SealCharacters.txt>
  （Apache-2.0）
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SEAL_SOURCES_URL = "https://www.unicode.org/Public/18.0.0/ucd/SealSources.txt"
SEAL_CHARACTERS_URL = (
    "https://cdn.jsdelivr.net/gh/BYVoid/OpenCC@master/data/dictionary/SealCharacters.txt")

# 说文四本的流水号属性，每个属性命中即算「收录一次」。
EDITION_PROPS = ("kSEAL_THXSrc", "kSEAL_CCZSrc", "kSEAL_QJZSrc", "kSEAL_DYCSrc")


def fetch(url: str, attempts: int = 4) -> bytes:
    """下载一次，失败重试。

    这两个来源都是公开 CDN，偶尔会直接重置连接（实测 jsDelivr 出现过
    ``WinError 10054``），重试几次即可。
    """
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "hanzi-glyphs-svg/0.1"})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except Exception as exc:      # noqa: BLE001 - 网络异常一律重试
            last = exc
            print(f"  下载失败（第 {attempt} 次）：{exc}", file=sys.stderr)
            if attempt < attempts:
                time.sleep(2 * attempt)
    raise SystemExit(f"下载 {url} 失败：{last}")


def load_seal_sources(path: Path) -> dict[str, dict[str, str]]:
    """读 SealSources.txt：篆书码位 → {属性: 值}。"""
    props: dict[str, dict[str, str]] = collections.defaultdict(dict)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        codepoint = parts[0].strip().upper()
        if codepoint.startswith("U+"):
            codepoint = codepoint[2:]
        props[codepoint][parts[1]] = parts[2]
    return dict(props)


def load_seal_characters(path: Path) -> tuple[dict[int, str], dict[str, str]]:
    """读 OpenCC 的 ``SealCharacters.txt``。

    返回 (篆书码位 → 现代字, 反查首选的现代字 → 篆书字形字符)。

    文件每行是「**篆书字形字符** \\t 现代字 …」（值可能用空格列多个，取第一个）；
    另有 ``# @reverse-prefer: <现代字> <篆书字形字符>`` 指令指定某个现代字的首选篆书字形。
    """
    mapping: dict[int, str] = {}
    prefs: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# @reverse-prefer:"):
            fields = line[len("# @reverse-prefer:"):].split()
            if len(fields) == 2:
                prefs[fields[0]] = fields[1]
            continue
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("\t")
        if not key or not value:
            continue
        modern = value.split(" ")[0]
        if not modern:
            continue
        mapping.setdefault(ord(key), modern)
    return mapping, prefs


def thx_kind(value: str) -> str:
    """说文流水号的序列类型：主序列 / 附录 X / 附录 Y / 其它。"""
    if re.fullmatch(r"TH-\d{5}", value or ""):
        return "MAIN"
    if re.fullmatch(r"TH-X\d{3}", value or ""):
        return "APPX-X"
    if re.fullmatch(r"TH-Y\d{3}", value or ""):
        return "APPX-Y"
    return "OTHER"


def editions(props: dict[str, str]) -> int:
    return sum(1 for name in EDITION_PROPS if name in props)


def pick_zheng(codepoints: list[str], rows: dict[str, dict[str, str]]) -> str:
    """规则 R：主序列优先 → 收录版本多者 → 码位小者。"""
    return max(codepoints, key=lambda cp: (
        thx_kind(rows[cp].get("kSEAL_THXSrc", "")) == "MAIN",
        editions(rows[cp]),
        -int(cp, 16),
    ))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成现代字 → 正篆码位反查表")
    parser.add_argument("--out", required=True, type=Path, help="输出 TSV 路径")
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="上游数据缓存目录，默认 <repo>/tmp/seal-table")
    parser.add_argument("--refresh", action="store_true", help="忽略缓存重新下载")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    cache = (args.cache_dir or repo_root / "tmp" / "seal-table").resolve()
    cache.mkdir(parents=True, exist_ok=True)

    sources_path = cache / "SealSources.txt"
    characters_path = cache / "SealCharacters.txt"
    if args.refresh:
        for target in (sources_path, characters_path):
            if target.is_file():
                target.unlink()
    if not sources_path.is_file():
        print(f"拉取 {SEAL_SOURCES_URL}")
        sources_path.write_bytes(fetch(SEAL_SOURCES_URL))
    if not characters_path.is_file():
        print(f"拉取 {SEAL_CHARACTERS_URL}")
        characters_path.write_bytes(fetch(SEAL_CHARACTERS_URL))

    rows = load_seal_sources(sources_path)
    ocmap, prefs = load_seal_characters(characters_path)

    # 篆书字形字符 → 篆书码位（5 位十六进制字符串，与候选集同宽，便于比较）
    char_to_codepoint: dict[str, str] = {}
    for codepoint, modern in ocmap.items():
        char_to_codepoint.setdefault(chr(codepoint), f"{codepoint:05X}")

    # 现代字 → 该字的全部篆书码位
    groups: dict[str, list[str]] = collections.defaultdict(list)
    for codepoint, props in rows.items():
        modern = ocmap.get(int(codepoint, 16))
        if modern is None:
            continue
        groups[modern].append(codepoint)
    for values in groups.values():
        values.sort()

    multi = {char: cps for char, cps in groups.items() if len(cps) > 1}
    zheng = {char: pick_zheng(cps, rows) for char, cps in groups.items()}

    # 交叉验证：OpenCC 自己的反查首选（reverse-prefer 指令 + 首项）是否与规则 R 一致
    opencc_first: dict[str, str] = {}
    for char, cps in groups.items():
        first = cps[0]
        prefer = prefs.get(char)
        if prefer is not None:
            wanted = char_to_codepoint.get(prefer)
            if wanted is not None and wanted in cps:
                first = wanted
        opencc_first[char] = first
    agree = sum(1 for char in multi if opencc_first[char] == zheng[char])
    print(f"多码位现代字 : {len(multi)}")
    print(f"规则 R 与 OpenCC 反查首选一致 : {agree} / {len(multi)}")
    if multi and agree != len(multi):
        print("警告：交叉验证未全数一致，请复核后再入库。", file=sys.stderr)

    header = ["modern_cp", "modern_char", "zheng_cp", "zheng_cp_repo5", "seal_char",
              "rule", "fallback_cp", "candidates", "note"]
    lines = ["\t".join(header)]
    for char in sorted(groups, key=lambda c: zheng[c]):
        codepoints = groups[char]
        picked = zheng[char]
        notes = []
        if char == "玉":
            notes.append("opencc-deviation:U+3D06D-mapped-to-玉-not-王")
        if len(codepoints) > 1:
            notes.append(f"multi:{len(codepoints)}")
        lines.append("\t".join([
            f"{ord(char):06X}", char, f"{int(picked, 16):06X}", picked,
            chr(int(picked, 16)), "zheng-reverse-prefer" if char in prefs else "zheng",
            f"{int(codepoints[0], 16):06X}",
            " ".join(f"{int(c, 16):06X}" for c in codepoints), ";".join(notes),
        ]))

    out_path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"写出 : {out_path}  （{len(lines) - 1} 行）")
    print(f"生成于 : {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
