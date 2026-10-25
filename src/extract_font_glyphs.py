#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从开源书法字体（OFL-1.1）提取汉字轮廓，生成 SVG 字形层与导入清单。

用法::

    python src/extract_font_glyphs.py --font <字体.ttf> --layer kaishu --out <目录> \
        --font-name "Ma Shan Zheng" --source-path "ofl/mashanzheng/MaShanZheng-Regular.ttf" \
        --source-url "https://github.com/google/fonts/blob/main/ofl/mashanzheng/OFL.txt" \
        --license-file <OFL.txt> [--attribution "…"] [--blocks basic,extA]

产出::

    <目录>/<6 位大写十六进制码位>.svg   每个汉字一条轮廓
    <目录>/manifest.json                 给 import_glyph_layer.py 用的清单

**为什么是「提取」而不是「描摹」。** 字形就是字体里的轮廓本身，
直接取轮廓是**逐点保真**的：没有目视重画、没有近似，
符合 AGENTS.md 硬规则 4「正式字形须贴近原字形」。

**为什么 viewBox 全层统一。** 字形是按字面大小排布的：
「一」横贯画布、「丨」纵贯画布，若按每个字的外接盒各自裁切，
同层字形的视觉大小会乱掉。画布按**该层全部字形墨迹的并集**定，
全层共用一个 —— 与汉典层固定 400×400 同理，保证整层比例一致。
（不用 em 框：有的字笔画会冲出降部，画布定死会把笔画切掉。）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

# 外接盒算法复用仓库自己的 check_glyphs.py，避免「提取时算的框」与
# 「体检时算的框」两套标准。可重定位的嵌入式 Python 不会把脚本目录
# 放进 sys.path，所以这里自己加。
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fontTools import version as fonttools_version
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

# 要收录的 Unicode 区块。CJK 兼容表意文字（F900–FAFF）不收：
# 它们的字形与统一表意文字重复，收了会让「一个现代字一个码位」变成一对多。
BLOCKS = {
    "basic": (0x4E00, 0x9FFF),      # CJK 统一表意文字（基本区）：简体与繁体都在这里
    "extA": (0x3400, 0x4DBF),       # CJK 扩展 A
    "extB": (0x20000, 0x2A6DF),     # CJK 扩展 B
    "extC": (0x2A700, 0x2B73F),     # CJK 扩展 C
    "extD": (0x2B740, 0x2B81F),     # CJK 扩展 D
    "extE": (0x2B820, 0x2CEAF),     # CJK 扩展 E
    "extF": (0x2CEB0, 0x2EBEF),     # CJK 扩展 F
    "extG": (0x30000, 0x3134A),     # CJK 扩展 G（Unicode 15.1 新增）
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ntos(value: float) -> str:
    """坐标保留到 0.01 个字体单位。

    1000 upem 的字体里，0.01 单位 = 字面的万分之一，比任何显示器的
    像素还细；再多的位数只是让文件变大。
    """
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def font_metrics(font: TTFont) -> tuple[int, int, int]:
    """取 (upem, ascender, descender)。

    优先用 hhea 的行高度量：CJK 字体的 OS/2 typo 度量常被设成 0，
    那样 em 框会退化成一条线。
    """
    upem = int(font["head"].unitsPerEm)
    hhea = font["hhea"]
    ascender, descender = int(hhea.ascender), int(hhea.descender)
    if ascender - descender < upem * 0.5:
        os2 = font["OS/2"]
        if int(os2.sTypoAscender) - int(os2.sTypoDescender) >= upem * 0.5:
            ascender, descender = int(os2.sTypoAscender), int(os2.sTypoDescender)
    if ascender - descender < upem * 0.5:
        ascender, descender = upem, 0
    return upem, ascender, descender


def glyph_path(pen: SVGPathPen, glyph_set, name: str) -> str:
    """把一个字形画进 pen，返回路径串。

    复合字形（部件拼合）由 fontTools 的字形集自行展开，
    不会漏笔画。
    """
    glyph = glyph_set[name]
    transform = TransformPen(pen, (1, 0, 0, -1, 0, 0))   # 字体 y 向上 → SVG y 向下
    glyph.draw(transform)
    return pen.getCommands()


def path_bbox(d: str) -> tuple[float, float, float, float] | None:
    """算路径的外接盒。

    复用的就是仓库体检脚本那一份算法（`src/check_glyphs.py`），
    免得「提取时算的框」与「体检时算的框」两套标准。
    """
    from check_glyphs import parse_path
    return parse_path(d)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从 OFL 字体提取汉字轮廓为 SVG")
    parser.add_argument("--font", required=True, type=Path, help="字体文件（TTF/OTF）")
    parser.add_argument("--layer", required=True, help="目标书体层名，如 kaishu / xingshu / caoshu")
    parser.add_argument("--out", required=True, type=Path, help="产出目录")
    parser.add_argument("--font-name", required=True, help="字体家族名")
    parser.add_argument("--font-version", default="", help="字体版本串")
    parser.add_argument("--source-path", required=True, help="上游仓库内的相对路径")
    parser.add_argument("--source-url", required=True, help="上游仓库页 URL")
    parser.add_argument("--source-binary-url", default="", help="字体二进制本身的 URL")
    parser.add_argument("--license-file", required=True, type=Path, help="上游许可文本")
    parser.add_argument("--license", default="OFL-1.1")
    parser.add_argument("--license-url", default="https://openfontlicense.org")
    parser.add_argument("--attribution", default="")
    parser.add_argument("--retrieved-at", default="", help="上游取回时刻（UTC ISO）")
    parser.add_argument("--blocks", default="basic,extA",
                        help="要收录的区块，逗号分隔：" + ",".join(BLOCKS))
    parser.add_argument("--location", default="",
                        help="可变字体的实例位置，如 wght=400；"
                             "不给就用字体的默认实例（可变字体的默认实例可能不是 Regular）")
    parser.add_argument("--limit", type=int, default=0, help="只取前 N 个（调试用）")
    parser.add_argument("--no-write", action="store_true", help="只统计不落盘")
    args = parser.parse_args(argv)

    font_path = args.font.resolve()
    if not font_path.is_file():
        raise SystemExit(f"找不到字体：{font_path}")
    license_path = args.license_file.resolve()
    if not license_path.is_file():
        raise SystemExit(f"找不到许可文本：{license_path}")

    wanted = {name.strip() for name in args.blocks.split(",") if name.strip()}
    unknown = wanted - set(BLOCKS)
    if unknown:
        raise SystemExit(f"未知区块：{', '.join(sorted(unknown))}")
    ranges = [BLOCKS[name] for name in sorted(wanted)]

    font = TTFont(font_path, fontNumber=0, lazy=True)
    upem, ascender, descender = font_metrics(font)
    cmap = font.getBestCmap()
    location = None
    if args.location:
        location = {}
        for part in args.location.split(","):
            if "=" not in part:
                raise SystemExit(f"--location 的格式是「轴=值」，收到 {part!r}")
            axis, value = part.split("=", 1)
            location[axis.strip()] = float(value)
    glyph_set = font.getGlyphSet(location=location) if location else font.getGlyphSet()

    # em 框只作参考：画布最终按实际墨迹并集定（见下）。
    em_box = f"0 {-ascender} {upem} {ascender - descender}"

    codepoints = sorted(
        cp for cp in cmap
        if any(lo <= cp <= hi for lo, hi in ranges)
    )
    if args.limit:
        codepoints = codepoints[:args.limit]

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    retrieved_at = args.retrieved_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 上游原件（字体二进制）的 sha256 与变换说明。
    # **每条字形的 `source_sha256` 都要指回这个字体文件**——它就是这份字形的
    # 上游原件；字形自己的 sha256 记在 `local_sha256`。
    font_sha = sha256_file(font_path)
    transform = (
        "font-outline-to-svg: 用 fontTools 的 SVGPathPen 取字体轮廓路径，"
        "y 轴翻转（字体坐标 y 向上 → SVG y 向下），坐标四舍五入到 0.01 字体单位；"
        + (f"可变字体按 location={args.location} 取实例；" if location else "")
        + "viewBox 取该层全部字形墨迹的并集外扩 1%，全层共用同一个画布，"
        "字形之间的相对比例与字体里一致"
    )

    # **先取全部字形的墨迹并集，再定画布。**
    # 不能直接用 em 框（ascender/descender）：有的字笔画会冲出降部
    # （实测 Ma Shan Zheng 有 20/6,763 个字的下端到 y=150，而 em 框下沿在 120），
    # 画布定死就会把这些字切掉一截。画布按**实际墨迹并集**定，
    # 再留 1% 余量，全层共用同一个画布，字形之间的相对比例不变。
    paths: list[tuple[int, str, str]] = []       # (码位, 字形名, 路径)
    boxes: list[tuple[float, float, float, float]] = []
    skipped_blank = []
    for cp in codepoints:
        name = cmap[cp]
        pen = SVGPathPen(glyph_set, ntos=ntos)
        try:
            d = glyph_path(pen, glyph_set, name)
        except Exception as exc:  # noqa: BLE001
            skipped_blank.append((cp, repr(exc)[:80]))
            continue
        d = (d or "").strip()
        if not d:
            skipped_blank.append((cp, "空轮廓"))
            continue
        box = path_bbox(d)
        if box is None:
            skipped_blank.append((cp, "算不出外接盒"))
            continue
        paths.append((cp, name, d))
        boxes.append(box)

    if not paths:
        raise SystemExit("没有取到任何有轮廓的字形")

    min_x = min(b[0] for b in boxes)
    min_y = min(b[1] for b in boxes)
    max_x = max(b[2] for b in boxes)
    max_y = max(b[3] for b in boxes)
    span = max(max_y - min_y, max_x - min_x, 1.0)
    margin = span * 0.01
    vx = math.floor(min_x - margin)
    vy = math.floor(min_y - margin)
    vw = math.ceil(max_x + margin) - vx
    vh = math.ceil(max_y + margin) - vy
    view_box = f"{vx} {vy} {vw} {vh}"

    glyphs = []
    for cp, name, d in paths:
        hexcp = f"{cp:06X}"
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}">'
            f'<path d="{d}"/></svg>'
        )
        filename = f"{hexcp}.svg"
        if not args.no_write:
            (out_dir / filename).write_text(svg, encoding="utf-8", newline="\n")
        glyphs.append({
            "glyph_id": cp,
            "file": filename,
            "modern_char": chr(cp),
            "unicode": hexcp,
            "codepoint": hexcp,
            "font_name": args.font_name,
            "font_version": args.font_version,
            "source_id": name,
            "source_path": args.source_path,
            "source_url": args.source_url,
            # 上游原件是那个字体二进制，不是这个 SVG
            "source_sha256": font_sha,
            "modifications": transform,
            "retrieved_at": retrieved_at,
            "local_sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest(),
        })

    font.close()

    manifest = {
        "script": args.layer,
        "layer": "skeleton",
        "license": args.license,
        "license_url": args.license_url,
        "attribution": args.attribution,
        "source_dataset": f"{args.font_name}（{args.source_path}）",
        "source_url": args.source_url,
        "source_artifact_url": args.source_binary_url or args.source_url,
        "source_path": args.source_path,
        "source_sha256": font_sha,
        "derived_from": args.source_binary_url or args.source_path,
        "derived_from_sha256": font_sha,
        "transform": transform,
        "modifications": transform,
        "tool": f"fontTools {fonttools_version} (SVGPathPen) + src/extract_font_glyphs.py",
        "font_name": args.font_name,
        "font_version": args.font_version,
        "glyphs": glyphs,
    }
    if not args.no_write:
        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

    print(f"字体        : {args.font_name} {args.font_version}")
    print(f"字形        : {len(glyphs)} 个 -> {out_dir}")
    print(f"viewBox     : {view_box}（墨迹并集；em 框为 {em_box}）")
    print(f"空轮廓      : {len(skipped_blank)} 个")
    for cp, why in skipped_blank[:10]:
        print(f"  !! U+{cp:04X} {chr(cp)}：{why}")
    print(f"总字节      : {sum(len(g['local_sha256']) for g in glyphs)} sha256 已算")
    return 0


if __name__ == "__main__":
    sys.exit(main())
