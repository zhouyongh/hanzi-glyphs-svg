# -*- coding: utf-8 -*-
"""候选字体的**增量评测**：相对本仓现在的十二层，这个字体还能补多少新码位？

回答三个问题：

1. 这个字体覆盖多少 CJK 码位？
2. 其中有多少是**本仓现在完全没有**的？
3. 多出来的是什么（扩展 B/C/D…），以及**能收进来的**有多少？

用法：

    python src/eval_candidate.py <字体路径> [字体名]

**为什么要按「相对本仓」算，而不是按字体自身覆盖量算。**
拿字体的覆盖量去比，会把「两个字体之间的覆盖量之差」误当成「本仓的增量」——
Chiron Hei HK 比宋体·简层多 3,801 个码位，看着很多，但其中 1,876 个才是本仓真正缺的。
**增量必须相对本仓现状算。**

**两个坑，脚本里都处理了：**

- **码位必须归一化。** 字体层的 `index.csv` 写 6 位（`004E00`），汉典层按
  `modern_char` 反查出来是 4 位（`4E00`）——直接当字符串比，同一个字会被当成两个，
  「本仓没有」的数量就虚高了。统一归一化成 `int(cp):X`。
- **非字体层要用 `modern_char` 反查。** 甲骨 / 金文 / 隶书 / 楚文字 / 傳抄古文的主键是
  条目号，篆书层的主键是**篆书区块码位**——把它当现代字码位，覆盖数会虚高。

**能收进来的净增量**要扣掉两个区块：CJK 兼容表意（F900–FAFF）与兼容补充
（2F800–2FA1F）。抽取器**有意不收**它们——字形与统一表意文字重复，收了会让
「一个现代字一个码位」变成一对多。

结果同时写到 `tmp/eval_<字体名>.json`（`tmp/` 不入库），便于逐次比对。
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
GLYPHS = ROOT / "glyphs"
OUT_DIR = ROOT / "tmp"

# 键就是现代字 Unicode 码位的层：直接读 index.csv 的 codepoint 列
LAYERS_WITH_CP = (
    "kaishu", "xingshu", "caoshu", "songti", "songti-tc", "heiti-hk",
)
# 键是条目号或篆书区块码位的层：按 modern_char 列反查 ord()
LAYERS_WITH_MODERN = ("oracle", "bronze", "clerical", "seal", "chu", "chuanchao")

BLOCKS = [
    ("基本区", 0x4E00, 0x9FFF), ("扩展A", 0x3400, 0x4DBF),
    ("扩展B", 0x20000, 0x2A6DF), ("扩展C", 0x2A700, 0x2B73F),
    ("扩展D", 0x2B740, 0x2B81F), ("扩展E", 0x2B820, 0x2CEAF),
    ("扩展F", 0x2CEB0, 0x2EBEF), ("扩展G", 0x30000, 0x3134A),
    ("兼容表意", 0xF900, 0xFAFF), ("兼容补充", 0x2F800, 0x2FA1F),
]

# **抽取器有意不收**的两个区块：字形与统一表意文字重复，
# 收了会让「一个现代字一个码位」变成一对多。算「能收进来的净增量」要扣掉它们。
COMPAT_BLOCKS = {"兼容表意", "兼容补充"}


def norm_cp(cp):
    """码位归一化：**统一成不带前导零的大写十六进制**。

    传 int 或 str 都行。
    """
    return f"{int(cp):X}" if isinstance(cp, int) else f"{int(cp, 16):X}"


def repo_codepoints():
    """本仓十二层覆盖的现代字 Unicode 码位集合。"""
    out = set()
    for layer in LAYERS_WITH_CP:
        p = GLYPHS / layer / "index.csv"
        if not p.is_file():
            continue
        with p.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                cp = (row.get("codepoint") or "").strip()
                if cp:
                    out.add(norm_cp(cp))
    for layer in LAYERS_WITH_MODERN:
        p = GLYPHS / layer / "index.csv"
        if not p.is_file():
            continue
        with p.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                ch = (row.get("modern_char") or "").strip()
                if len(ch) == 1:
                    out.add(norm_cp(ord(ch)))
    return out


def block_of(cp):
    v = int(cp, 16)
    for name, lo, hi in BLOCKS:
        if lo <= v <= hi:
            return name
    return "其他"


def font_codepoints(path):
    """字体的 CJK 码位集合，以及 name 表里的家族名 / 版本 / 版权行。"""
    font = TTFont(path, fontNumber=0, lazy=True)
    cmap = font.getBestCmap()
    names = {r.nameID: r.toUnicode() for r in font["name"].names
             if r.platformID == 3 and r.langID == 0x409}
    family = names.get(1, "")
    version = names.get(5, "")
    copyright_line = names.get(0, "")
    font.close()
    cjk = set()
    for cp in cmap:
        if any(lo <= cp <= hi for _n, lo, hi in BLOCKS):
            cjk.add(norm_cp(cp))
    return cjk, family, version, copyright_line


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("font", help="候选字体文件路径")
    ap.add_argument("label", nargs="?", help="显示用名字（默认取文件名）")
    ap.add_argument("--out", help="结果 JSON 的输出路径（默认 tmp/eval_<label>.json）")
    args = ap.parse_args(argv)

    path = Path(args.font)
    label = args.label or path.stem

    repo = repo_codepoints()
    cjk, family, version, copyright_line = font_codepoints(path)

    print(f"=== {label} ===")
    print(f"字体        : {family}")
    print(f"版本        : {version}")
    print(f"name 表版权 : {copyright_line[:120]}")
    print(f"版权行有 RFN: {'是' if 'Reserved Font Name' in copyright_line else '否'}")

    by_block_font = Counter(block_of(cp) for cp in cjk)
    print(f"\n本仓十二层覆盖的现代字码位：{len(repo)}")
    print(f"该字体覆盖的 CJK 码位    ：{len(cjk)}")
    print("  字体自身按区块：")
    for name, _lo, _hi in BLOCKS:
        if by_block_font.get(name):
            print(f"    {name:8s} {by_block_font[name]:>6}")

    new = cjk - repo
    dup = cjk & repo
    print(f"  已有（重叠）           ：{len(dup)}")
    print(f"  **本仓没有（净增量）** ：{len(new)}")

    by_block = Counter(block_of(cp) for cp in new)
    collectable = {cp for cp in new if block_of(cp) not in COMPAT_BLOCKS}
    print("\n净增量按区块：")
    for b, n in by_block.most_common():
        mark = "" if b in COMPAT_BLOCKS else "  ← 抽取器会收"
        print(f"  {b:8s} {n:>6}{mark}")
    print(f"\n  净增量合计            ：{len(new)}")
    print(f"  **能收进来的**（扣掉兼容区）：{len(collectable)}")

    if collectable:
        print("\n样例：")
        for cp in sorted(collectable)[:10]:
            print(f"  U+{cp}  {chr(int(cp, 16))}")

    result = {
        "label": label, "family": family, "version": version,
        "copyright": copyright_line,
        "name_table_has_rfn": "Reserved Font Name" in copyright_line,
        "repo_codepoints": len(repo), "font_codepoints": len(cjk),
        "overlap": len(dup), "new": len(new),
        "new_collectable": len(collectable),
        "new_by_block": dict(by_block),
        "font_by_block": dict(by_block_font),
    }

    out = Path(args.out) if args.out else (OUT_DIR / f"eval_{label}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
