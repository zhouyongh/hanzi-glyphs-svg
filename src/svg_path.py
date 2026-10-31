#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用 SVG path 解析：把 ``d`` 展开成折线（多边形）列表。

**为什么自己写**：仓里 `outline_oracle.flatten_path` 只认自家 JGW 骨架用的
绝对 ``M/L/A/Z``；漢典与小學堂的件用相对指令（``m/c/l/z``…），解析不了。
描摹件与拓片件都是这后一种。

支持的指令：``M m L l H h V v C c S s Q q T t A a Z z``，
隐式重复（``m`` 之后多对坐标按 ``l`` 处理）按 SVG 规范来。

用法::

    from svg_path import parse_svg_paths
    viewbox, contours = parse_svg_paths(Path("glyphs/bronze/11000.svg"))
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

NUM = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def tokenize(d: str) -> list:
    """切成「命令字母 + 数字」的序列。"""
    out: list = []
    i, n = 0, len(d)
    while i < n:
        ch = d[i]
        if ch in "MmZzLlHhVvCcSsQqTtAa":
            out.append(ch)
            i += 1
        elif ch in " ,\t\r\n":
            i += 1
        else:
            m = NUM.match(d, i)
            if not m:
                raise ValueError(f"无法解析的字符 {ch!r} @ {i}")
            out.append(float(m.group()))
            i = m.end()
    return out


def _arc(cx: float, cy: float, rx: float, ry: float, phi_deg: float,
         large: int, sweep: int, x: float, y: float) -> list[tuple[float, float]]:
    """SVG 椭圆弧 → 折线点（端点参数化 → 圆心参数化）。"""
    if rx == 0 or ry == 0:
        return [(x, y)]
    phi = math.radians(phi_deg)
    cosp, sinp = math.cos(phi), math.sin(phi)
    dx2, dy2 = (cx - x) / 2.0, (cy - y) / 2.0
    x1p = cosp * dx2 + sinp * dy2
    y1p = -sinp * dx2 + cosp * dy2
    rx, ry = abs(rx), abs(ry)
    lam = x1p * x1p / (rx * rx) + y1p * y1p / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        co = -co
    cxp = co * rx * y1p / ry
    cyp = -co * ry * x1p / rx
    cxx = cosp * cxp - sinp * cyp + (cx + x) / 2.0
    cyy = sinp * cxp + cosp * cyp + (cy + y) / 2.0

    def ang(ux: float, uy: float, vx: float, vy: float) -> float:
        dot = ux * vx + uy * vy
        ln = math.hypot(ux, uy) * math.hypot(vx, vy)
        a = math.acos(max(-1.0, min(1.0, dot / ln))) if ln else 0.0
        return -a if ux * vy - uy * vx < 0 else a

    th1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dth = ang((x1p - cxp) / rx, (y1p - cyp) / ry,
              (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dth > 0:
        dth -= 2 * math.pi
    elif sweep and dth > 0:
        dth += 2 * math.pi
    elif sweep and dth < 0:
        dth += 2 * math.pi
    steps = max(6, int(abs(dth) / (math.pi / 18)) + 2)
    pts = []
    for i in range(1, steps + 1):
        t = th1 + dth * i / steps
        ex, ey = rx * math.cos(t), ry * math.sin(t)
        pts.append((cxx + cosp * ex - sinp * ey, cyy + sinp * ex + cosp * ey))
    return pts


def _cubic(p0, p1, p2, p3, steps: int) -> list[tuple[float, float]]:
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        a = mt * mt * mt
        b = 3 * mt * mt * t
        c = 3 * mt * t * t
        d = t * t * t
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def _quad(p0, p1, p2, steps: int) -> list[tuple[float, float]]:
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        a = mt * mt
        b = 2 * mt * t
        c = t * t
        pts.append((a * p0[0] + b * p1[0] + c * p2[0],
                    a * p0[1] + b * p1[1] + c * p2[1]))
    return pts


def flatten(d: str, steps: int = 16) -> list[list[tuple[float, float]]]:
    """``d`` → 折线列表（每个子路径一条，首尾相接视为闭合）。"""
    toks = tokenize(d)
    subpaths: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    pos = (0.0, 0.0)
    start = (0.0, 0.0)
    last_cubic_ctrl = None
    last_quad_ctrl = None
    cmd = None
    i = 0
    n = len(toks)

    def flush():
        nonlocal cur
        if len(cur) > 2:
            subpaths.append(cur)
        cur = []

    while i < n:
        if isinstance(toks[i], str):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                flush()
                pos = start
                last_cubic_ctrl = last_quad_ctrl = None
                continue
        if cmd is None:
            raise ValueError("路径没有起始命令")
        rel = cmd.islower()
        c = cmd.upper()

        if c == "M":
            x, y = toks[i], toks[i + 1]
            i += 2
            if rel:
                x, y = pos[0] + x, pos[1] + y
            flush()
            pos = (x, y)
            start = pos
            cur = [pos]
            last_cubic_ctrl = last_quad_ctrl = None
            cmd = "l" if rel else "L"      # 后续数对是隐式 lineto
        elif c == "L":
            x, y = toks[i], toks[i + 1]
            i += 2
            if rel:
                x, y = pos[0] + x, pos[1] + y
            pos = (x, y)
            cur.append(pos)
            last_cubic_ctrl = last_quad_ctrl = None
        elif c == "H":
            x = toks[i]
            i += 1
            if rel:
                x = pos[0] + x
            pos = (x, pos[1])
            cur.append(pos)
            last_cubic_ctrl = last_quad_ctrl = None
        elif c == "V":
            y = toks[i]
            i += 1
            if rel:
                y = pos[1] + y
            pos = (pos[0], y)
            cur.append(pos)
            last_cubic_ctrl = last_quad_ctrl = None
        elif c == "C":
            x1, y1, x2, y2, x, y = toks[i:i + 6]
            i += 6
            if rel:
                x1, y1 = pos[0] + x1, pos[1] + y1
                x2, y2 = pos[0] + x2, pos[1] + y2
                x, y = pos[0] + x, pos[1] + y
            cur.extend(_cubic(pos, (x1, y1), (x2, y2), (x, y), steps))
            last_cubic_ctrl = (x2, y2)
            last_quad_ctrl = None
            pos = (x, y)
        elif c == "S":
            x2, y2, x, y = toks[i:i + 4]
            i += 4
            if rel:
                x2, y2 = pos[0] + x2, pos[1] + y2
                x, y = pos[0] + x, pos[1] + y
            if last_cubic_ctrl:
                x1, y1 = 2 * pos[0] - last_cubic_ctrl[0], 2 * pos[1] - last_cubic_ctrl[1]
            else:
                x1, y1 = pos
            cur.extend(_cubic(pos, (x1, y1), (x2, y2), (x, y), steps))
            last_cubic_ctrl = (x2, y2)
            last_quad_ctrl = None
            pos = (x, y)
        elif c == "Q":
            x1, y1, x, y = toks[i:i + 4]
            i += 4
            if rel:
                x1, y1 = pos[0] + x1, pos[1] + y1
                x, y = pos[0] + x, pos[1] + y
            cur.extend(_quad(pos, (x1, y1), (x, y), steps))
            last_quad_ctrl = (x1, y1)
            last_cubic_ctrl = None
            pos = (x, y)
        elif c == "T":
            x, y = toks[i], toks[i + 1]
            i += 2
            if rel:
                x, y = pos[0] + x, pos[1] + y
            if last_quad_ctrl:
                x1, y1 = 2 * pos[0] - last_quad_ctrl[0], 2 * pos[1] - last_quad_ctrl[1]
            else:
                x1, y1 = pos
            cur.extend(_quad(pos, (x1, y1), (x, y), steps))
            last_quad_ctrl = (x1, y1)
            last_cubic_ctrl = None
            pos = (x, y)
        elif c == "A":
            rx, ry, rot, large, sweep, x, y = toks[i:i + 7]
            i += 7
            if rel:
                x, y = pos[0] + x, pos[1] + y
            cur.extend(_arc(pos[0], pos[1], rx, ry, rot, int(large), int(sweep), x, y))
            pos = (x, y)
            last_cubic_ctrl = last_quad_ctrl = None
        else:
            raise ValueError(f"未知命令 {cmd!r}")
    flush()
    return subpaths


def parse_svg_paths(path: Path) -> tuple[tuple[float, float, float, float],
                                        list[list[tuple[float, float]]]]:
    """读 SVG → (viewBox, 折线列表)。viewBox 缺省按 0 0 400 400。"""
    root = ET.parse(path).getroot()
    vb = root.get("viewBox") or "0 0 400 400"
    x0, y0, w, h = (float(v) for v in vb.replace(",", " ").split())
    contours: list[list[tuple[float, float]]] = []
    for el in root.iter():
        if el.tag.endswith("path"):
            d = el.get("d")
            if d:
                contours.extend(flatten(d))
    return (x0, y0, w, h), contours


def signed_area(contour: list[tuple[float, float]]) -> float:
    """有向面积（鞋带公式）。正 = 逆时针，负 = 顺时针。"""
    s = 0.0
    n = len(contour)
    for i in range(n):
        x0, y0 = contour[i]
        x1, y1 = contour[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def bbox(contour: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in contour]
    ys = [p[1] for p in contour]
    return (min(xs), min(ys), max(xs), max(ys))


def point_in_polygon(pt: tuple[float, float],
                     poly: list[tuple[float, float]]) -> bool:
    """射线法：点是否在多边形内（边界算在内）。"""
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xin = (x1 - x0) * (y - y0) / (y1 - y0) + x0
            if x < xin:
                inside = not inside
    return inside
