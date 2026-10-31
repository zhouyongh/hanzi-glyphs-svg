#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字形体检：XML 是否合法、路径是否退化、字形是否落在画布内。

用法::

    python src/check_glyphs.py glyphs/bronze glyphs/clerical
    python src/check_glyphs.py --repo-root .          # 检查全部书体层
    python src/check_glyphs.py --trace-fidelity       # 描摹保真检查（另说）

检查项：

1. 文件是合法 XML，根元素是 ``svg``，有 ``viewBox``；
2. 至少有一条非空 ``path``；
3. 路径算出来的外接盒**落在 viewBox 内**（允许 2% 溢出，描摹件常有轻微越界）；
4. 外接盒不退化（宽高都大于画布的 2%），避免存进一堆空白或碎点。

只看几何，不判断字形「像不像」——那要人眼看（浏览页就是给人看的）。

**描摹保真检查**（``--trace-fidelity``）是另一件事：位图描摹出来的 SVG 是派生件，
上游原件是位图，「像不像」可以**机检**——回光栅化后与上游位图的墨迹掩膜算 IoU。
每件的 IoU 记在 provenance 的 ``trace_iou`` 里，这里按单条与层级两道门槛判定。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

NUM = re.compile(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?")
# 允许的溢出比例
BLEED = 0.02
# 外接盒最小占比（相对画布）
MIN_SIZE = 0.02


def _arc_points(x1: float, y1: float, rx: float, ry: float, phi_deg: float,
                large_arc: int, sweep: int, x2: float, y2: float) -> list[tuple[float, float]]:
    """圆弧上落在弧段内的极值点。

    按 SVG 规范的「端点 → 圆心」换算求出圆心与起止参数角，
    再取椭圆上 x / y 极值所在的四个方向；落在弧段内的方向才计入。
    算不出合法圆弧时退回端点。
    """
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        return [(x2, y2)]
    rx, ry = abs(rx), abs(ry)
    phi = math.radians(phi_deg)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p = cos_p * dx + sin_p * dy
    y1p = -sin_p * dx + cos_p * dy
    lam = x1p * x1p / (rx * rx) + y1p * y1p / (ry * ry)
    if lam > 1:
        scale = math.sqrt(lam)
        rx *= scale
        ry *= scale
    denom = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    num = rx * rx * ry * ry - denom
    coef = math.sqrt(max(0.0, num / denom)) if denom else 0.0
    if large_arc == sweep:
        coef = -coef
    cxp = coef * rx * y1p / ry
    cyp = -coef * ry * x1p / rx
    cx = cos_p * cxp - sin_p * cyp + (x1 + x2) / 2.0
    cy = sin_p * cxp + cos_p * cyp + (y1 + y2) / 2.0

    def vector_angle(ux: float, uy: float, vx: float, vy: float) -> float:
        norm = math.hypot(ux, uy) * math.hypot(vx, vy)
        if norm == 0:
            return 0.0
        cos_a = max(-1.0, min(1.0, (ux * vx + uy * vy) / norm))
        angle = math.acos(cos_a)
        return -angle if (ux * vy - uy * vx) < 0 else angle

    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    theta1 = vector_angle(1.0, 0.0, ux, uy)
    delta = vector_angle(ux, uy, vx, vy)
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi
    theta2 = theta1 + delta

    def in_range(theta: float) -> bool:
        lo, hi = (theta1, theta2) if theta2 >= theta1 else (theta2, theta1)
        return lo - 1e-9 <= theta <= hi + 1e-9

    points: list[tuple[float, float]] = []
    for theta in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
        if not in_range(theta):
            continue
        ex = rx * math.cos(theta)
        ey = ry * math.sin(theta)
        points.append((cos_p * ex - sin_p * ey + cx, sin_p * ex + cos_p * ey + cy))
    points.append((x2, y2))
    return points


def parse_path(d: str) -> tuple[float, float, float, float] | None:
    """算一条 path 的外接盒。相对指令要累加当前点，曲线取控制点与端点的极值。

    只求外接盒，所以曲线用控制点近似即可（控制点在曲线包围盒内，
    真正的曲线不会超出控制点包围盒——对三次贝塞尔成立）。

    **S / T 的隐含控制点要算进来。** S 的第一个控制点是上一个三次曲线
    控制点关于当前点的镜像，T 的控制点是上一个二次曲线控制点关于
    当前点的镜像；不补这两个点，外接盒会偏小，
    字形贴边时会被误判成「超出 viewBox」。
    """
    tokens = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?", d)
    xs: list[float] = []
    ys: list[float] = []
    cx = cy = 0.0          # 当前点
    sx = sy = 0.0          # 子路径起点
    cubic_ctrl: tuple[float, float] | None = None    # 上一个三次曲线的末控制点
    quad_ctrl: tuple[float, float] | None = None     # 上一个二次曲线的控制点
    i = 0
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

    def put(x: float, y: float) -> None:
        xs.append(x)
        ys.append(y)

    while i < n:
        token = tokens[i]
        if re.match(r"[A-Za-z]", token):
            cmd = token
            i += 1
            if cmd in "Zz":
                cx, cy = sx, sy
                cubic_ctrl = quad_ctrl = None
                continue
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            v = take(2)
            if len(v) < 2:
                break
            cx, cy = (cx + v[0], cy + v[1]) if rel else (v[0], v[1])
            sx, sy = cx, cy
            put(cx, cy)
            cmd = "l" if rel else "L"      # 后续坐标按直线段处理
            cubic_ctrl = quad_ctrl = None
        elif c == "L":
            v = take(2)
            if len(v) < 2:
                break
            cx, cy = (cx + v[0], cy + v[1]) if rel else (v[0], v[1])
            put(cx, cy)
            cubic_ctrl = quad_ctrl = None
        elif c == "H":
            v = take(1)
            if not v:
                break
            cx = cx + v[0] if rel else v[0]
            put(cx, cy)
            cubic_ctrl = quad_ctrl = None
        elif c == "V":
            v = take(1)
            if not v:
                break
            cy = cy + v[0] if rel else v[0]
            put(cx, cy)
            cubic_ctrl = quad_ctrl = None
        elif c == "C":
            v = take(6)
            if len(v) < 6:
                break
            pts = [(v[0], v[1]), (v[2], v[3]), (v[4], v[5])]
            if rel:
                pts = [(cx + px, cy + py) for px, py in pts]
            for px, py in pts:
                put(px, py)
            cx, cy = pts[-1]
            cubic_ctrl = (pts[1][0], pts[1][1])
            quad_ctrl = None
        elif c == "S":
            v = take(4)
            if len(v) < 4:
                break
            pts = [(v[0], v[1]), (v[2], v[3])]
            if rel:
                pts = [(cx + px, cy + py) for px, py in pts]
            # 第一个控制点 = 上一个三次曲线末控制点关于当前点的镜像
            if cubic_ctrl is None:
                first = (cx, cy)
            else:
                first = (2 * cx - cubic_ctrl[0], 2 * cy - cubic_ctrl[1])
            put(first[0], first[1])
            for px, py in pts:
                put(px, py)
            cx, cy = pts[-1]
            cubic_ctrl = (pts[0][0], pts[0][1])
            quad_ctrl = None
        elif c == "Q":
            v = take(4)
            if len(v) < 4:
                break
            pts = [(v[0], v[1]), (v[2], v[3])]
            if rel:
                pts = [(cx + px, cy + py) for px, py in pts]
            for px, py in pts:
                put(px, py)
            cx, cy = pts[-1]
            quad_ctrl = (pts[0][0], pts[0][1])
            cubic_ctrl = None
        elif c == "T":
            v = take(2)
            if len(v) < 2:
                break
            end = (cx + v[0], cy + v[1]) if rel else (v[0], v[1])
            # 控制点 = 上一个二次曲线控制点关于当前点的镜像
            if quad_ctrl is None:
                ctrl = (cx, cy)
            else:
                ctrl = (2 * cx - quad_ctrl[0], 2 * cy - quad_ctrl[1])
            put(ctrl[0], ctrl[1])
            put(end[0], end[1])
            cx, cy = end
            quad_ctrl = ctrl
            cubic_ctrl = None
        elif c == "A":
            v = take(7)
            if len(v) < 7:
                break
            rx, ry, rot, large_arc, sweep = v[0], v[1], v[2], int(v[3]), int(v[4])
            end = (cx + v[5], cy + v[6]) if rel else (v[5], v[6])
            for px, py in _arc_points(cx, cy, rx, ry, rot, large_arc, sweep,
                                      end[0], end[1]):
                put(px, py)
            cx, cy = end
            cubic_ctrl = quad_ctrl = None
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


def check_trace_fidelity(repo_root: Path) -> int:
    """**描摹保真检查**：位图描摹出来的 SVG 是否忠实于上游位图。

    位图 → SVG 的描摹件是**派生件**，上游原件是位图。仓库里记着每件的
    ``trace_iou``（本地 SVG 回光栅化后与上游位图墨迹掩膜的 IoU），
    这里按单条与层级两道门槛判定。

    门槛（与 ``src/trace_xiaoxuetang_glyphs.py`` 的自检一致）：

    - 单条：IoU ≥ 0.97 合格；0.93–0.97 记 warning；< 0.93 判失败；
    - 层级：IoU 的 p05 ≥ 0.96，失败率 ≤ 1%。

    **只查位图描摹件**（``transform`` 里带 marching-squares 的那些）。
    甲骨层的 JGW 轮廓是**矢量转轮廓**，不是描摹件，没有 IoU 可言；
    把它们混进来会把「没有指标」误判成「指标不合格」。
    """
    prov_dir = repo_root / "glyphs" / "provenance"
    layers: dict[str, list[float]] = {}
    missing: list[str] = []
    for path in sorted(prov_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("layer") != "outline":
                    continue
                transform = str(rec.get("transform") or "")
                if "marching-squares" not in transform:
                    continue      # 不是位图描摹件（如 JGW 的矢量转轮廓）
                script = str(rec.get("script") or path.stem)
                raw = rec.get("trace_iou")
                if raw in (None, ""):
                    missing.append(f"{script} {rec.get('path', '')}")
                    continue
                layers.setdefault(script, []).append(float(raw))

    if not layers and not missing:
        print("描摹保真      : 没有位图描摹件（仓库里还没这批数据）")
        return 0

    total_bad = 0
    for script, scores in sorted(layers.items()):
        scores.sort()
        n = len(scores)
        p05 = scores[max(0, int(round(0.05 * (n - 1))))]
        worst = scores[0]
        fails = [s for s in scores if s < 0.93]
        warns = [s for s in scores if 0.93 <= s < 0.97]
        bad = []
        if worst < 0.93:
            bad.append(f"最低 IoU={worst:.4f} < 0.93")
        if p05 < 0.96:
            bad.append(f"p05={p05:.4f} < 0.96")
        if n and len(fails) / n > 0.01:
            bad.append(f"失败率 {len(fails)}/{n} = {len(fails) / n:.2%} > 1%")
        total_bad += len(bad)
        print(f"{script}: 描摹件 {n} 个；最低 IoU={worst:.4f} p05={p05:.4f} "
              f"中位={scores[n // 2]:.4f}；警戒 {len(warns)} / 失败 {len(fails)}")
        for item in bad:
            print("   !!", item)
    if missing:
        total_bad += len(missing)
        print(f"!! 有 {len(missing)} 件描摹件**没有记 trace_iou**，无法核验保真度")
        for item in missing[:10]:
            print("   !!", item)
        if len(missing) > 10:
            print(f"   ... 另有 {len(missing) - 10} 件")
    return total_bad


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="字形体检：画布、路径、退化")
    parser.add_argument("dirs", nargs="*", type=Path, help="要检查的字形目录")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="配合 --repo-root 检查全部书体层")
    parser.add_argument("--trace-fidelity", action="store_true",
                        help="只跑描摹保真检查：读 provenance 里的 trace_iou，"
                             "按单条/层级门槛判定位图描摹件是否忠实于上游位图")
    args = parser.parse_args(argv)

    if args.trace_fidelity:
        bad = check_trace_fidelity(args.repo_root.resolve())
        print()
        print(f"合计问题 : {bad}")
        return 1 if bad else 0

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
