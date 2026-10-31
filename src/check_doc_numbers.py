#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档里的层件数与层里实际件数对不对得上。

**为什么要它**：层的规模一变，README 里的层表就得跟着改。
手工改总会漏一处，而漏掉的数字比没有数字更坏——读者会拿它当依据。

**判据只认一种写法**（其余一律跳过，避免误报）：
README 顶层那张层表里的

    | 中文名 English | `glyphs/<层>/` | **N** 个字形 | ... |

即：层目录在第二格、件数紧跟在下一格且写作「N 个字形」。
**别处的数字不查**——它们多是**子集数**（如「JGW 批 1,203」）、
**分批数**（「漢典矢量件 12,975 + 描摹件 7,469」）或**合计数**
（现代书体六层 97,349），那些数字没有「等于层规模」这层含义，认了就是误报。

用法::

    python src/check_doc_numbers.py --repo-root .
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

# README 顶层层表的一行：`| 名字 | `glyphs/层/` | **N** 个字形 | ... |
RE_ROW = re.compile(
    r"\|\s*`glyphs/(?P<layer>[A-Za-z0-9_.-]+)/`\s*\|\s*"
    r"\*{0,2}(?P<n>\d{1,3}(?:,\d{3})+|\d+)\*{0,2}\s*个字形")


def layer_counts(repo_root: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    glyphs = repo_root / "glyphs"
    for d in sorted(glyphs.iterdir()):
        if not d.is_dir():
            continue
        idx = d / "index.csv"
        if not idx.is_file():
            continue
        with idx.open("r", encoding="utf-8-sig", newline="") as fh:
            out[d.name] = sum(1 for _ in csv.DictReader(fh))
    return out


def check(repo_root: Path) -> int:
    counts = layer_counts(repo_root)
    readme = repo_root / "README.md"
    problems: list[str] = []
    checked = 0
    if readme.is_file():
        for i, line in enumerate(readme.read_text(encoding="utf-8").splitlines(), 1):
            m = RE_ROW.search(line)
            if not m:
                continue
            layer = m.group("layer")
            if layer not in counts:
                continue
            said = int(m.group("n").replace(",", ""))
            real = counts[layer]
            checked += 1
            if said != real:
                problems.append(f"README.md:{i}: 写着 {layer} 有 {said:,} 个，"
                                f"层里实际 {real:,} 个")
    print(f"检查层        : {len(counts)} 个")
    print(f"对到的数字    : {checked} 处（README 顶层层表）")
    if problems:
        print(f"问题          : {len(problems)} 项")
        for p in problems:
            print("  ·", p)
        return 1
    print("问题          : 0 项")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="文档里的层件数与实际件数对账")
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = ap.parse_args(argv)
    return check(args.repo_root.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
