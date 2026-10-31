#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字形比对：把两批 SVG 字形归一化后按形状找重复。

**为什么需要它。** 层里判重用的是「(现代字, 字形键)」这一对键。字形键是
**来源自己给的编号**——汉典的字形键与小學堂的槽位**部分同构**（同源时对得上，
不同源时各编各的）。所以「键不同」不等于「字形不同」：同一件甲骨摹本，
汉典编成 ``41_EBC2``、小學堂编成 ``41_E172``，键对不上，字形却是一回事。
不比对形状就会把同一件字形收两遍（一份带真汉字身份、一份挂着空码位），
那正是「无重复字」要禁止的。

**做法**：把每个字形按**墨迹包围盒**归一化到同一张 N×N 网格上，
再算 IoU（交并比）。归一化抹掉尺寸与留白，只留形状。

**用法**::

    python src/compare_glyph_shapes.py --refs glyphs/oracle/1204.svg \\
        --queries tmp/xxt/jiaguwen/svg/41_E153.svg --out tmp/matches.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trace_xiaoxuetang_glyphs import rasterize_loops  # noqa: E402

# 曲线离散段数：够细又不至于把 path 点数撑爆。
CURVE_STEPS = 12
# 归一化网格边长（像素）。
GRID = 64
# 归一化后四周留的空白（像素）。
MARGIN = 2

RE_PATH_D = re.compile(r'<path[^>]*\bd="([^"]*)"', re.I)
RE_SVG_VIEWBOX = re.compile(r'\bviewBox="([^"]*)"', re.I)
RE_SVG_TAG = re.compile(r"<svg[^>]*>", re.I)

# path 的命令字母。**必须列全**（含 A/a 弧指令）：漏一个字母，
# 那条指令会被整段吞掉，后面的数字被当成别的命令的参数，字形就解析成乱线团。
PATH_COMMANDS = "MmLlHhVvCcSsQqTtZzAa"


# ---------------------------------------------------------------- path 解析

def _tokenize(d: str) -> list[str]:
    return re.findall(rf"[{PATH_COMMANDS}]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", d)


def _bezier3(p0, p1, p2, p3, steps: int) -> list[tuple[float, float]]:
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt * mt * mt * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t * t * t * p3[0]
        y = mt * mt * mt * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t * t * t * p3[1]
        out.append((x, y))
    return out


def _bezier2(p0, p1, p2, steps: int) -> list[tuple[float, float]]:
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0]
        y = mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]
        out.append((x, y))
    return out


def _arc(p0, rx, ry, phi, large_arc, sweep, p1, steps: int) -> list[tuple[float, float]]:
    """椭圆弧（SVG 的 ``A``/``a``）-> 折线点列。

    按 SVG 规范转成中心参数化再采样。**弧不能忽略**：JGW 那批字形的
    轮廓带圆角（笔画端点用 A 指令画半圆），漏掉它会把一个字形解析成乱线团。
    """
    x0, y0 = p0
    x1, y1 = p1
    if rx == 0 or ry == 0:
        return [p1]
    rx, ry = abs(rx), abs(ry)
    rad = math.radians(phi % 360.0)
    cos_r, sin_r = math.cos(rad), math.sin(rad)
    dx2 = (x0 - x1) / 2.0
    dy2 = (y0 - y1) / 2.0
    x1p = cos_r * dx2 + sin_r * dy2
    y1p = -sin_r * dx2 + cos_r * dy2
    # 半径太小要按规范放大
    lam = x1p * x1p / (rx * rx) + y1p * y1p / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx *= s
        ry *= s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    if den == 0:
        return [p1]
    coef = math.sqrt(max(num / den, 0.0))
    if large_arc == sweep:
        coef = -coef
    cxp = coef * rx * y1p / ry
    cyp = -coef * ry * x1p / rx
    cx = cos_r * cxp - sin_r * cyp + (x0 + x1) / 2.0
    cy = sin_r * cxp + cos_r * cyp + (y0 + y1) / 2.0

    def angle(ux, uy, vx, vy):
        dot = ux * vx + uy * vy
        n = math.hypot(ux, uy) * math.hypot(vx, vy)
        if n == 0:
            return 0.0
        a = math.acos(max(-1.0, min(1.0, dot / n)))
        return -a if (ux * vy - uy * vx) < 0 else a

    ux = (x1p - cxp) / rx
    uy = (y1p - cyp) / ry
    vx = (-x1p - cxp) / rx
    vy = (-y1p - cyp) / ry
    theta1 = angle(1.0, 0.0, ux, uy)
    dtheta = angle(ux, uy, vx, vy)
    if not sweep and dtheta > 0:
        dtheta -= 2 * math.pi
    elif sweep and dtheta < 0:
        dtheta += 2 * math.pi
    out = []
    for i in range(1, steps + 1):
        th = theta1 + dtheta * i / steps
        px = cx + rx * math.cos(th) * cos_r - ry * math.sin(th) * sin_r
        py = cy + rx * math.cos(th) * sin_r + ry * math.sin(th) * cos_r
        out.append((px, py))
    return out


def parse_path(d: str) -> list[list[tuple[float, float]]]:
    """SVG path d -> 闭合轮廓列表（曲线已离散成折线）。

    只处理**填充**语义：轮廓必须是闭合的，开放子路径按直线闭合。
    相对指令累加当前点；``S`` / ``T`` 的隐含控制点按规范推导。
    """
    toks = _tokenize(d)
    loops: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    x = y = 0.0
    start = (0.0, 0.0)
    prev_c2 = None      # 上一个三次曲线的第二个控制点（S 用）
    prev_q1 = None      # 上一个二次曲线的控制点（T 用）
    cmd = None
    i = 0
    num = 0

    def flush() -> None:
        nonlocal cur
        if len(cur) >= 3:
            loops.append(cur)
        cur = []

    while i < len(toks):
        t = toks[i]
        if re.match(r"[A-Za-z]", t):
            cmd = t
            i += 1
            if cmd in "Zz":
                if len(cur) >= 3:
                    cur.append(start)
                    flush()
                x, y = start
                prev_c2 = prev_q1 = None
                continue
        if cmd is None:
            break
        rel = cmd.islower()
        c = cmd.upper()

        def take(n: int) -> list[float]:
            nonlocal i, num
            vals = []
            for _ in range(n):
                if i >= len(toks) or re.match(r"[A-Za-z]", toks[i]):
                    break
                vals.append(float(toks[i]))
                i += 1
            return vals

        if c == "M":
            v = take(2)
            if len(v) < 2:
                break
            if rel:
                x += v[0]; y += v[1]
            else:
                x, y = v[0], v[1]
            if cur:
                flush()
            start = (x, y)
            cur = [(x, y)]
            cmd = "l" if rel else "L"
            prev_c2 = prev_q1 = None
            continue
        if c == "L":
            v = take(2)
            if len(v) < 2:
                break
            if rel:
                x += v[0]; y += v[1]
            else:
                x, y = v[0], v[1]
            cur.append((x, y))
            prev_c2 = prev_q1 = None
            continue
        if c == "H":
            v = take(1)
            if not v:
                break
            x = x + v[0] if rel else v[0]
            cur.append((x, y))
            prev_c2 = prev_q1 = None
            continue
        if c == "V":
            v = take(1)
            if not v:
                break
            y = y + v[0] if rel else v[0]
            cur.append((x, y))
            prev_c2 = prev_q1 = None
            continue
        if c == "C":
            v = take(6)
            if len(v) < 6:
                break
            if rel:
                p1 = (x + v[0], y + v[1]); p2 = (x + v[2], y + v[3]); p3 = (x + v[4], y + v[5])
            else:
                p1 = (v[0], v[1]); p2 = (v[2], v[3]); p3 = (v[4], v[5])
            cur.extend(_bezier3((x, y), p1, p2, p3, CURVE_STEPS))
            prev_c2, prev_q1 = p2, None
            x, y = p3
            continue
        if c == "S":
            v = take(4)
            if len(v) < 4:
                break
            if rel:
                p2 = (x + v[0], y + v[1]); p3 = (x + v[2], y + v[3])
            else:
                p2 = (v[0], v[1]); p3 = (v[2], v[3])
            if prev_c2 is None:
                p1 = (x, y)
            else:
                p1 = (2 * x - prev_c2[0], 2 * y - prev_c2[1])
            cur.extend(_bezier3((x, y), p1, p2, p3, CURVE_STEPS))
            prev_c2, prev_q1 = p2, None
            x, y = p3
            continue
        if c == "Q":
            v = take(4)
            if len(v) < 4:
                break
            if rel:
                p1 = (x + v[0], y + v[1]); p2 = (x + v[2], y + v[3])
            else:
                p1 = (v[0], v[1]); p2 = (v[2], v[3])
            cur.extend(_bezier2((x, y), p1, p2, CURVE_STEPS))
            prev_q1, prev_c2 = p1, None
            x, y = p2
            continue
        if c == "A":
            v = take(7)
            if len(v) < 7:
                break
            rx, ry, phi, large, sweep = v[0], v[1], v[2], int(v[3]), int(v[4])
            if rel:
                p1 = (x + v[5], y + v[6])
            else:
                p1 = (v[5], v[6])
            cur.extend(_arc((x, y), rx, ry, phi, large, sweep, p1, CURVE_STEPS))
            x, y = p1
            prev_c2 = prev_q1 = None
            continue
        if c == "T":
            v = take(2)
            if len(v) < 2:
                break
            if rel:
                p2 = (x + v[0], y + v[1])
            else:
                p2 = (v[0], v[1])
            if prev_q1 is None:
                p1 = (x, y)
            else:
                p1 = (2 * x - prev_q1[0], 2 * y - prev_q1[1])
            cur.extend(_bezier2((x, y), p1, p2, CURVE_STEPS))
            prev_q1, prev_c2 = p1, None
            x, y = p2
            continue
        # 未知指令：跳过一个数，避免死循环
        v = take(1)
        if not v:
            break
        num += 1
    flush()
    return loops


# ---------------------------------------------------------------- SVG 读取

def svg_loops(path: Path) -> list[list[tuple[float, float]]]:
    """读 SVG，取所有 <path> 的轮廓。

    **只处理填充路径**：描摹件与汉典摹本都是填充的（``fill`` 缺省即黑）。
    ``fill="none"`` 的纯骨架（JGW 批的 polyline）在这里会被跳过——
    那些是**参数化规范字形**，与摹本形态不同，不参与形状判重。
    """
    text = path.read_text(encoding="utf-8")
    loops: list[list[tuple[float, float]]] = []
    for tag in re.finditer(r"<path\b[^>]*>", text, re.I):
        attrs = tag.group(0)
        if re.search(r'\bfill\s*=\s*"none"', attrs, re.I):
            continue
        dm = re.search(r'\bd="([^"]*)"', attrs, re.I)
        if not dm:
            continue
        loops.extend(parse_path(dm.group(1)))
    return loops


def normalize(loops: list[list[tuple[float, float]]], grid: int = GRID,
              margin: int = MARGIN) -> list[list[tuple[float, float]]]:
    """按墨迹包围盒等比缩放并居中到 grid×grid 网格。

    等比缩放保持形状（不拉伸），居中让两个同样形状的件在同一位置。
    """
    pts = [p for lp in loops for p in lp]
    if not pts:
        return []
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    w = max(x1 - x0, 1e-6)
    h = max(y1 - y0, 1e-6)
    inner = grid - 2 * margin
    scale = inner / max(w, h)
    # 墨迹中心对齐到网格中心
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    ox = grid / 2 - cx * scale
    oy = grid / 2 - cy * scale
    out = []
    for lp in loops:
        out.append([(p[0] * scale + ox, p[1] * scale + oy) for p in lp])
    return out


def mask_of(path: Path, grid: int = GRID) -> np.ndarray:
    """SVG -> 归一化掩膜（bool [grid, grid]）。"""
    loops = svg_loops(path)
    if not loops:
        return np.zeros((grid, grid), dtype=bool)
    loops = normalize(loops, grid)
    return rasterize_loops(loops, grid, grid, rule="nonzero")


def pack(mask: np.ndarray) -> np.ndarray:
    """掩膜 -> 打包位（uint8，每字节 8 位）。"""
    return np.packbits(mask.reshape(-1))


def iou_matrix(refs: np.ndarray, ref_counts: np.ndarray,
               query: np.ndarray, query_count: int) -> np.ndarray:
    """一批 ref 与一个 query 的 IoU。

    refs: (R, ceil(grid*grid/8)) uint8 打包位
    ref_counts: (R,) 每件墨迹像素数
    query: 打包位
    """
    inter = np.bitwise_count(np.bitwise_and(refs, query[None, :])).sum(axis=1)
    union = ref_counts + query_count - inter
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(union > 0, inter / np.maximum(union, 1), 0.0)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="字形形状比对（判重）")
    ap.add_argument("--refs", nargs="+", type=Path, required=True, help="参照字形（重复写多组）")
    ap.add_argument("--ref-list", type=Path, default=None, help="参照字形清单（每行一个路径）")
    ap.add_argument("--queries", nargs="+", type=Path, default=None, help="待查字形")
    ap.add_argument("--query-list", type=Path, default=None, help="待查字形清单")
    ap.add_argument("--out", type=Path, default=None, help="匹配结果（JSONL）")
    ap.add_argument("--threshold", type=float, default=0.70, help="判定为同一个字形的 IoU 门槛")
    ap.add_argument("--grid", type=int, default=GRID)
    args = ap.parse_args(argv)

    ref_paths: list[Path] = list(args.refs)
    if args.ref_list:
        ref_paths += [Path(l.strip()) for l in args.ref_list.read_text(encoding="utf-8").splitlines()
                      if l.strip()]
    query_paths: list[Path] = list(args.queries or [])
    if args.query_list:
        query_paths += [Path(l.strip()) for l in args.query_list.read_text(encoding="utf-8").splitlines()
                        if l.strip()]
    if not ref_paths or not query_paths:
        raise SystemExit("需要 --refs/--ref-list 与 --queries/--query-list")

    packed: list[np.ndarray] = []
    counts: list[int] = []
    keep: list[Path] = []
    for p in ref_paths:
        if not p.is_file():
            continue
        m = mask_of(p, args.grid)
        if not m.any():
            continue
        packed.append(pack(m))
        counts.append(int(m.sum()))
        keep.append(p)
    ref_matrix = np.array(packed, dtype=np.uint8)
    ref_counts = np.array(counts, dtype=np.int64)
    print(f"参照字形 {len(keep)} 件（已光栅化）")

    out_fh = args.out.open("w", encoding="utf-8", newline="\n") if args.out else None
    hits = 0
    for q in query_paths:
        if not q.is_file():
            continue
        m = mask_of(q, args.grid)
        if not m.any():
            continue
        qp = pack(m)
        ious = iou_matrix(ref_matrix, ref_counts, qp, int(m.sum()))
        k = int(np.argmax(ious))
        best = float(ious[k])
        if best >= args.threshold:
            hits += 1
        rec = {"query": str(q), "best_iou": round(best, 4),
               "best_ref": str(keep[k]) if len(keep) else "",
               "same_shape": best >= args.threshold}
        if out_fh:
            out_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        else:
            print(json.dumps(rec, ensure_ascii=False))
    if out_fh:
        out_fh.close()
    print(f"待查 {len(query_paths)} 件，命中（IoU ≥ {args.threshold}）{hits} 件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
