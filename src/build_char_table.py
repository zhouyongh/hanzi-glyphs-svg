#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成抓取用的字表（``--chars-file``）。

用法::

    python src/build_char_table.py --out tmp/chars/expanded.txt
    python src/build_char_table.py --out tmp/chars/ext-a.txt --blocks ext-a

产出::

    每行「现代字 6 位大写十六进制码位」，按码位升序。
    空行与 # 开头的行会被抓取脚本跳过，可以放心加注释。

**为什么要有这一步。** 抓取脚本的 ``--from-seal-registry`` 给的字表是
**《说文》字表**（篆书登记表里的 11,231 个现代字）。说文是字书的字书，
收字以「可篆」为限，落在 CJK 基本区里的只有 7,388 个——
现代常用字里有一大截在它之外。金文、隶书、篆书三层靠这 11,231 个字就够，
但**楚文字与傳抄古文是摹本**，摹的是出土/传抄文本上的字，
覆盖的是「先秦两汉文献里出现过的字」，说文字表反而是窄的那一层。

实测（2026-10-23，300 字随机抽样，说文字表之外的 CJK 基本区字）：
傳抄古文命中率 32.0%（CI 27.0%–37.5%），楚文字 8.3%（CI 5.7%–12.0%）。
所以这两层重拓时**必须换字表**，否则就是把已有覆盖重抓一遍。

**字表必须包含原有那批字。** 层键（条目号）是「整层内容」的函数：
增删字形会让整层重排。重拓时若只给新字，下游按新清单导入会把旧字形
当成孤儿删掉。所以这里默认把说文登记表里的现代字**并进**字表——
既保留旧覆盖，又把新字加进来。

块的选择：

* ``basic``：CJK 基本区 U+4E00–U+9FFF 里 Unicode 5.x 已分配的汉字（20,992 个）。
* ``ext-a``：扩展 A 区 U+3400–U+4DBF（6,592 个）。
* 扩展 B 区及其以后没纳入：那些字的现代对应关系不明确，
  汉典页面上多以「𠀀」之类的兼容字出现，对不上号。

码位一律 6 位大写十六进制——登记表、合并脚本、index.csv 都是这个宽度，
不统一就会出现同一个字两条记录。
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from pathlib import Path

# Unicode 块：名字 -> (起始码位, 结束码位, 含不含)
BLOCKS: dict[str, tuple[int, int]] = {
    "basic": (0x4E00, 0x9FFF),
    "ext-a": (0x3400, 0x4DBF),
}


def seal_registry_chars(repo_root: Path) -> dict[str, str]:
    """读篆书登记表，返回 {现代字: 6 位大写十六进制现代字码位}。

    登记表（``glyphs/seal/external.csv``）里 ``unicode`` 列是**现代字的码位**，
    ``codepoint`` 列才是篆书区块码位。别读错列。
    """
    path = repo_root / "glyphs" / "seal" / "external.csv"
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            char = (row.get("modern_char") or "").strip()
            cp = (row.get("unicode") or "").strip().upper()
            if not char or not cp:
                continue
            if len(cp) < 6:
                cp = cp.rjust(6, "0")
            out.setdefault(char, cp)
    return out


def block_chars(start: int, end: int) -> list[str]:
    """块内已分配的汉字（Unicode 类别为 Lo 的码位）。

    扩展 A 区有一段**已分配但暂未公开**的区间（U+4DB6 之后有一批空位），
    用 ``unicodedata.category`` 判一下就不会把空位当成字。
    """
    out: list[str] = []
    for cp in range(start, end + 1):
        char = chr(cp)
        if unicodedata.category(char) == "Lo":
            out.append(char)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成抓取用的字表")
    parser.add_argument("--out", required=True, type=Path, help="字表落盘路径")
    parser.add_argument("--blocks", default="basic",
                        help="要取哪些 Unicode 块，逗号分隔：basic / ext-a")
    parser.add_argument("--repo-root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--no-seal-registry", action="store_true",
                        help="不并入说文登记表里的现代字（默认并入）")
    parser.add_argument("--only-new", action="store_true",
                        help="只留「说文登记表之外」的字：登记表里的现代字全部剔除。"
                             "增量重拓时用这个——已覆盖的字重抓一遍是白花请求，"
                             "而且可能把超出每字上限的实例塞进已有层。")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    chars: dict[str, str] = {}
    registry = seal_registry_chars(repo_root)
    if args.only_new:
        print(f"说文登记表 : {len(registry)} 字（已覆盖，全部剔除）")
    elif not args.no_seal_registry:
        # 先放登记表里的（保留原有覆盖），再放块里的新字。
        # 登记表优先：它给的是说文收字的规范现代字写法。
        for char, cp in registry.items():
            chars[char] = cp
        print(f"说文登记表 : {len(registry)} 字")

    for name in [x.strip() for x in args.blocks.split(",") if x.strip()]:
        if name not in BLOCKS:
            raise SystemExit(f"未知的块：{name}（可选：{', '.join(sorted(BLOCKS))}）")
        start, end = BLOCKS[name]
        found = block_chars(start, end)
        added = 0
        for char in found:
            if char in chars:
                continue
            if args.only_new and char in registry:
                continue
            chars[char] = f"{ord(char):06X}"
            added += 1
        print(f"{name:<11}: 块内 {len(found)} 字，新增 {added} 字")

    lines = [f"{char} {chars[char]}" for char in sorted(chars, key=lambda c: chars[c])]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"字表        : {len(lines)} 字 → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
