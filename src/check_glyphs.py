#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字形体检：XML 是否合法、路径是否退化、字形是否落在画布内。

用法::

    python src/check_glyphs.py glyphs/bronze glyphs/clerical
    python src/check_glyphs.py --repo-root .          # 检查全部书体层

检查项：

1. 文件是合法 XML，根元素是 ``svg``，有 ``viewBox``；
2. 至少有一条非空 ``path``；
3. 路径算出来的外接盒**落在 viewBox 内**（允许 2% 溢出，描摹件常有轻微越界）；
4. 外接盒不退化（宽高都大于画布的 2%），避免存进一堆空白或碎点。

只看几何，不判断字形「像不像」——那要人眼看（浏览页就是给人看的）。
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

NUM = re.compile(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?")
# 允许的溢出比例
BLEED = 0.02
# 外接盒最小占比（相对画布）
MIN_SIZE = 0.02


def parse_path(d: str) -> tuple[float, float, float, float] | None:
    """算一条 path 的外接盒。相对指令要累加当前点，曲线取控制点与端点的极值。

    只求外接盒，所以曲线用控制点近似即可（控制点在曲线包围盒内，
    真正的曲线不会超出控制点包围盒——对三次贝塞尔成立）。
    """
    tokens = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?", d)
    xs: list[float] = []
    ys: list[float] = []
    cx = cy = 0.0          # 当前点
    sx = sy = 0.0          # 子路径起点
    i = 0
    cmd = ""
    n = len(tokens)

    def take(k: int) -> list[float]:
        nonlocal i
        vals = []
        for _ in range(k):
            if i < n:
                try:
                    vals.append(float(tokens[i]))
                except ValueError:
                    pass
                i += 1
        return vals

    while i < n:
        token = tokens[i]
        if re.match(r"[A-Za-z]", token):
            cmd = token
            i += 1
            if cmd in "Zz":
                cx, cy = sx, sy
                continue
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            v = take(2)
            if len(v) < 2:
                break
            cx, cy = (cx + v[0], cy + v[1]) if rel else (v[0], v[1])
            sx, sy = cx, cy
            xs.append(cx)
            ys.append(cy)
            cmd = "l" if rel else "L"      # 后续坐标按直线段处理
        elif c == "L":
            v = take(2)
            if len(v) < 2:
                break
            cx, cy = (cx + v[0], cy + v[1]) if rel else (v[0], v[1])
            xs.append(cx)
            ys.append(cy)
        elif c == "H":
            v = take(1)
            if not v:
                break
            cx = cx + v[0] if rel else v[0]
            xs.append(cx)
            ys.append(cy)
        elif c == "V":
            v = take(1)
            if not v:
                break
            cy = cy + v[0] if rel else v[0]
            xs.append(cx)
            ys.append(cy)
        elif c in ("C", "S", "Q", "T"):
            k = {"C": 6, "S": 4, "Q": 4, "T": 2}[c]
            v = take(k)
            if len(v) < k:
                break
            pts = [(v[0], v[1]), (v[2], v[3]), (v[4], v[5])] if c in ("C", "Q") else \
                  [(v[0], v[1]), (v[2], v[3])]
            if rel:
                pts = [(cx + px, cy + py) for px, py in pts]
            for px, py in pts:
                xs.append(px)
                ys.append(py)
            cx, cy = pts[-1]
        elif c == "A":
            v = take(7)
            if len(v) < 7:
                break
            cx, cy = (cx + v[5], cy + v[6]) if rel else (v[5], v[6])
            xs.append(cx)
            ys.append(cy)
        else:
            i += 1
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def check_file(path: Path) -> str | None:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return f"XML 不合法：{exc}"
    except OSError as exc:
        return f"读不了：{exc}"
    if not root.tag.endswith("svg"):
        return f"根元素不是 svg：{root.tag}"
    viewbox = root.get("viewBox")
    if not viewbox:
        return "缺 viewBox"
    try:
        vx, vy, vw, vh = (float(x) for x in viewbox.replace(",", " ").split())
    except ValueError:
        return f"viewBox 解析不了：{viewbox}"
    if vw <= 0 or vh <= 0:
        return f"viewBox 尺寸非正：{viewbox}"

    boxes = []
    for el in root.iter():
        if el.tag.endswith("path") and (el.get("d") or "").strip():
            box = parse_path(el.get("d") or "")
            if box:
                boxes.append(box)
    if not boxes:
        return "没有可解析的 path"

    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    if x0 < vx - BLEED * vw or x1 > vx + vw + BLEED * vw or \
       y0 < vy - BLEED * vh or y1 > vy + vh + BLEED * vh:
        return (f"超出 viewBox：x[{x0:.0f},{x1:.0f}] y[{y0:.0f},{y1:.0f}] "
                f"viewBox[{vx:.0f},{vy:.0f},{vw:.0f},{vh:.0f}]")
    # 只有两个方向同时退化才算问题：单笔的横/竖画（如「一」）在一个方向上天然是 0。
    if (x1 - x0) < MIN_SIZE * vw and (y1 - y0) < MIN_SIZE * vh:
        return f"外接盒退化：{x1 - x0:.0f}×{y1 - y0:.0f}（画布 {vw:.0f}×{vh:.0f}）"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="字形体检：画布、路径、退化")
    parser.add_argument("dirs", nargs="*", type=Path, help="要检查的字形目录")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="配合 --repo-root 检查全部书体层")
    args = parser.parse_args(argv)

    dirs = list(args.dirs)
    if not dirs:
        root = args.repo_root.resolve() / "glyphs"
        dirs = sorted(p for p in root.iterdir() if p.is_dir() and p.name != "oracle") if root.is_dir() else []
        dirs += [args.repo_root.resolve() / "glyphs" / "oracle"]
    total_bad = 0
    for d in dirs:
        if not d.is_dir():
            continue
        files = sorted(d.glob("*.svg"))
        if not files:
            continue
        bad = []
        for f in files:
            issue = check_file(f)
            if issue:
                bad.append(f"{f.name}: {issue}")
        total_bad += len(bad)
        print(f"{d}: 检查 {len(files)} 个，问题 {len(bad)} 个")
        for item in bad[:10]:
            print("   !!", item)
        if len(bad) > 10:
            print(f"   ... 另有 {len(bad) - 10} 个")
    print()
    print(f"合计问题 : {total_bad}")
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
