#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字体层漏收审计：OFL 源字体里有的码位，本仓对应的层是不是都收了。

用法::

    python src/audit_font_coverage.py --font-dir tmp/fonts_probe
    python src/audit_font_coverage.py --font songti=NotoSerifSC.ttf --font heiti-hk=ChironHeiHK.ttf
    python src/audit_font_coverage.py --font-dir D:\\fonts --json tmp/coverage.json

**为什么要有这个脚本。**
「某个字体层收全了」这类结论必须能被复算，不能只靠印象。本脚本把
**层里的码位集合**与**源字体的 cmap**逐块对照，报四件事：

1. **漏收**（要命的）：字体在收字区块里有、层里没有的码位。
   这是「层不完整」，必须补。
2. **多收**：层里有、字体里没有的码位。说明索引与字体的实际覆盖对不上，
   多半是提取时用了别的字体实例或别的版本。
3. **有意不收**：CJK 兼容表意（F900–FAFF）与兼容补充（2F800–2FA1F）。
   它们的字形与统一表意文字重复，收了会让「一个现代字一个码位」变成一对多。
   抽取器 ``src/extract_font_glyphs.py`` 就有意不收这两块。
4. **区块外但属 CJK 范畴的码位**：康熙部首（U+2F00–2FDF）、CJK 部首补充
   （U+2E80–2EFF）等。**它们不算漏收**——收字区块本来就不含这些块——
   但要报出来，因为「要不要把它们也收进来」是一个需要人拍板的口径问题。

**收字区块从哪儿来。** 直接 import 抽取器的 ``BLOCKS``，不另抄一份：
审计和提取若各写一份区块表，迟早会漂移，漂移之后审计就白做了。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract_font_glyphs import BLOCKS  # noqa: E402  (同目录脚本，需先加路径)

# 层 → 默认的字体文件名。字体不在仓库里（版权与体积），要自己指路。
LAYER_FONTS = {
    "kaishu": "MaShanZheng.ttf",
    "xingshu": "ZhiMangXing.ttf",
    "caoshu": "LiuJianMaoCao.ttf",
    "songti": "NotoSerifSC.ttf",
    "songti-tc": "NotoSerifTC.ttf",
    "heiti-hk": "ChironHeiHK.ttf",
}

# 有意不收的区块。抄自抽取器的说明，不另造口径。
NOT_COLLECTED = (
    ("CJK 兼容表意 F900-FAFF", 0xF900, 0xFAFF),
    ("兼容补充 2F800-2FA1F", 0x2F800, 0x2FA1F),
)

# 区块外、但仍属 CJK 范畴的码位范围。报出来供人决定要不要收。
CJK_ELSEWHERE = (
    ("CJK 部首补充 U+2E80-2EFF", 0x2E80, 0x2EFF),
    ("康熙部首 U+2F00-2FDF", 0x2F00, 0x2FDF),
    ("迭代记号 U+3005-3007", 0x3005, 0x3007),
    ("杭州数字 U+3021-3029", 0x3021, 0x3029),
    ("杭州数字 U+3038-303B", 0x3038, 0x303B),
    ("带圈表意补充 U+1F200-1F2FF", 0x1F200, 0x1F2FF),
)


def load_layer_codepoints(index_path: Path) -> set[int]:
    """读一层 index.csv 里的码位集合（字体层的键就是 Unicode 码位）。"""
    out: set[int] = set()
    with index_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get("unicode") or row.get("codepoint") or "").strip()
            if raw:
                out.add(int(raw, 16))
    return out


def font_codepoints(font_path: Path) -> set[int]:
    """读一个 TrueType/OpenType 字体的 cmap（要 fontTools）。"""
    from fontTools.ttLib import TTFont

    with TTFont(str(font_path), fontNumber=0, lazy=True) as font:
        return set(font.getBestCmap())


def ranges_of(codepoints: set[int]) -> list[tuple[int, int, int]]:
    """把码位集合压成连续区间，好读。"""
    out: list[tuple[int, int, int]] = []
    for cp in sorted(codepoints):
        if out and cp == out[-1][1] + 1:
            out[-1] = (out[-1][0], cp, out[-1][2] + 1)
        else:
            out.append((cp, cp, 1))
    return out


def audit_layer(layer: str, font_path: Path, layer_cps: set[int]) -> dict:
    """核一层：漏收、多收、有意不收、区块外的 CJK 码位。"""
    fc = font_codepoints(font_path)
    in_blocks: set[int] = set()
    for lo, hi in BLOCKS.values():
        in_blocks |= {c for c in fc if lo <= c <= hi}

    missing = in_blocks - layer_cps          # 字体有、层里没有
    extra = layer_cps - fc                  # 层里有、字体没有
    skipped: dict[str, int] = {}
    for name, lo, hi in NOT_COLLECTED:
        n = len({c for c in fc if lo <= c <= hi})
        if n:
            skipped[name] = n
    elsewhere: dict[str, int] = {}
    for name, lo, hi in CJK_ELSEWHERE:
        n = len({c for c in fc if lo <= c <= hi and c not in in_blocks})
        if n:
            elsewhere[name] = n

    return {
        "layer": layer,
        "font": str(font_path),
        "layer_codepoints": len(layer_cps),
        "font_codepoints": len(fc),
        "missing": sorted(missing),
        "extra": sorted(extra),
        "skipped": skipped,
        "cjk_elsewhere": elsewhere,
        "cjk_elsewhere_ranges": [
            [f"U+{lo:05X}", f"U+{hi:05X}", n]
            for lo, hi, n in ranges_of(
                {c for c in fc
                 if any(lo2 <= c <= hi2 for _n, lo2, hi2 in CJK_ELSEWHERE)
                 and c not in in_blocks})
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="字体层漏收审计")
    parser.add_argument("--repo-root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--font-dir", type=Path, default=None,
                        help="字体文件所在目录（按 LAYER_FONTS 的默认文件名找）")
    parser.add_argument("--font", action="append", default=[],
                        metavar="层=字体文件",
                        help="指定某层的字体，可重复；也可直接给字体文件路径")
    parser.add_argument("--layer", action="append", default=[],
                        help="只查这一层，可重复")
    parser.add_argument("--json", type=Path, default=None, help="另存机读结果")
    args = parser.parse_args(argv)

    repo_root: Path = args.repo_root.resolve()

    # 层 → 字体路径
    fonts: dict[str, Path] = {}
    for item in args.font:
        if "=" in item:
            layer, name = item.split("=", 1)
            fonts[layer.strip()] = Path(name)
        else:
            path = Path(item)
            for layer, default in LAYER_FONTS.items():
                if path.name.lower() == default.lower():
                    fonts[layer] = path
            if not fonts:
                print(f"看不出这是哪一层的字体：{item}；用 --font 层=文件名 指定",
                      file=sys.stderr)
                return 2
    if args.font_dir:
        for layer, default in LAYER_FONTS.items():
            candidate = args.font_dir / default
            if candidate.is_file():
                fonts.setdefault(layer, candidate)

    wanted = args.layer or list(LAYER_FONTS)
    layers = [l for l in wanted if l in LAYER_FONTS]
    if not layers:
        print("没有可查的层", file=sys.stderr)
        return 2

    results: list[dict] = []
    total_missing = 0
    for layer in layers:
        index_path = repo_root / "glyphs" / layer / "index.csv"
        if not index_path.is_file():
            print(f"跳过 {layer}：没有 {index_path}")
            continue
        font_path = fonts.get(layer)
        if font_path is None or not Path(font_path).is_file():
            print(f"跳过 {layer}：找不到源字体（用 --font-dir 或 --font 指定）")
            continue
        result = audit_layer(layer, Path(font_path), load_layer_codepoints(index_path))
        results.append(result)
        total_missing += len(result["missing"])

        print("=" * 72)
        print(f"{layer}　源字体 {Path(font_path).name}　层内 {result['layer_codepoints']} 个码位")
        if result["missing"]:
            print(f"   漏收 {len(result['missing'])} 个：")
            for lo, hi, n in ranges_of(set(result["missing"]))[:10]:
                print(f"      U+{lo:05X}-U+{hi:05X}  {n} 个")
        else:
            print("   漏收：0")
        if result["extra"]:
            print(f"   多收 {len(result['extra'])} 个（层里有、字体里没有）：")
            for cp in result["extra"][:10]:
                print(f"      U+{cp:05X} {unicodedata.name(chr(cp), '?')}")
        for name, n in result["skipped"].items():
            print(f"   [有意不收] {name}：字体 {n} 个")
        for name, n in result["cjk_elsewhere"].items():
            print(f"   [收字区块之外] {name}：字体 {n} 个（不算漏收；要收需另开口径）")

    print("=" * 72)
    print(f"合计「收字区块内漏收」：{total_missing}")
    print("说明：收字区块外的 CJK 码位（康熙部首等）不是漏收——"
          "抽取器的收字区块本来就不含它们；要收进来是另一个口径决定。")

    if args.json:
        args.json.write_text(
            json.dumps({"results": results, "missing_total": total_missing},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"机读结果：{args.json}")

    return 0 if total_missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
