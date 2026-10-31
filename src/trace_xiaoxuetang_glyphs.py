#!/usr/bin/env python3
"""把小学堂的字形位图描摹成 SVG。

用法::

    # 单个/整目录描摹 + 保真核验
    python src/trace_xiaoxuetang_glyphs.py --input tmp/xxt/chuwenzi/gif --out tmp/xxt/chuwenzi/svg
    # 几何自检（不联网）
    python src/trace_xiaoxuetang_glyphs.py --selftest

为什么这样写
------------
1. **不装第三方库**。本机只有 PIL / numpy（与 ``src/outline_oracle.py`` 的前提一致），
   所以轮廓追踪自己实现：marching squares 提取亚像素等值线 → Douglas–Peucker 简化
   → Chaikin 平滑。不引 VTracer / potrace。
2. **在灰度场上取等值线，而不是先二值化再走边界**。上游 GIF 是 256 色抗锯齿图，
   直接在灰度场上取 0.5 等值线能吃到抗锯齿带来的亚像素边缘；先二值化会把边缘
   量化成整像素台阶，IoU 会掉一截。
3. **填充规则用 nonzero**（与仓库其余各层一致）。marching squares 的方向约定
   （背景在左 ⇒ 墨在右）已经保证了外轮廓与洞的绕向相反，nonzero 直接对上；
   evenodd 在**两笔在一点相接**的字形上会翻车——轮廓自接触，evenodd 的奇偶性
   在接触点两侧相反，一侧的笔画就被挖空了（实测「乎」字 IoU 掉到 0.83，
   笔画中间出现白洞）。nonzero 下自接触处绕数一致，两侧都填实。
   注意 SVG 文件里的 `fill-rule` 必须与核验用的光栅化规则**一致**，否则
   「自检算出的 IoU」与「浏览器渲染出来的样子」不是一回事。
4. **保真有机器判据**：把生成的 path 光栅化回原分辨率，与原图墨迹掩膜算 IoU。
   单条门槛 0.97，层级 p05 门槛 0.96，低于 0.93 判失败重描。

派生件记账
----------
字形是**派生件**：上游是位图，本地是矢量。provenance 必须记
``derived_from``（位图 URL）、``derived_from_sha256``、``transform``、``tool``，
否则「出处的字形」与「入库的字形」就对不上号。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from PIL import Image

TOOL = "src/trace_xiaoxuetang_glyphs.py"
# 记录在 provenance 的 transform 字段里
TRANSFORM = ("png(黑墨+alpha)→合成到白底→灰度→marching-squares(等值线 level=0.5，"
             "画布四周补一圈背景)→chaikin({smooth})→douglas-peucker(eps={eps})"
             "→nonzero 填充 path；viewBox 取墨迹包围盒加 1px 留白，坐标与原图像素一致")

IOU_PASS = 0.97      # 单条合格
IOU_WARN = 0.93      # 低于此值判失败


# ---------------------------------------------------------------- 读图

def load_gray(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """读位图，返回 (灰度场 [0,1], 透明掩膜 bool)。

    **必须做 alpha 合成**：上游是黑墨 + 变 alpha 的 PNG，直接取 RGB 均值的话，
    半透明像素的 RGB 是 (0,0,0)，会被当成全墨，轮廓就系统性外扩半像素——
    描出来的字比原字胖一圈。合成到白底之后，灰度 = 覆盖率，0.5 等值线正好落在
    抗锯齿边缘的半覆盖处，这才是位图矢量化该有的边。
    """
    with Image.open(path) as im:
        im = im.convert("RGBA")
        arr = np.asarray(im).astype(np.float32) / 255.0
    alpha = arr[..., 3]
    ink = arr[..., :3].mean(axis=2)
    gray = ink * alpha + (1.0 - alpha)
    return gray, alpha > 0


def ink_mask(gray: np.ndarray, level: float) -> np.ndarray:
    return gray < level


# ---------------------------------------------------------------- marching squares

# 角点编号：1=左上(a) 2=右上(b) 4=右下(c) 8=左下(d)
# 索引位序与上面一致：index = (a>=L) | (b>=L)<<1 | (c>=L)<<2 | (d>=L)<<3
#
# 注意 bit=1 表示的是**背景**（灰度 >= level；墨是深色，灰度反而小）。
# 每个 case 给出两条边的配对（边名：T 上 / R 右 / B 下 / L 左），
# 方向取「背景（bit=1）在左侧」。
#
# 这条方向约定很要紧：互补的两个 case（01↔14、02↔13、03↔12、04↔11、
# 06↔09、07↔08）方向必须正好相反，轮廓才能在格子共用的顶点处首尾相接。
# 早期版本前四对没取反，轮廓在这些顶点处接不上，描摹结果碎成几十段
# （实测圆盘碎成 18 条：主环 136 点 + 17 个 4~6 点的碎片）。
# （历史值，保留作对照：case 10 的「中心为背景」分支曾写成
#   [("L","T"), ("R","B")]——两条弧都终止于同一交点，链断、字被描成蝴蝶结。
#   现在这一格由推导给出 [("T","L"), ("B","R")]。）

# ---------------------------------------------------------------- case 表推导
#
# case 表**不手写**，由 `_derive_case_table()` 按几何推导出来：
# 弧的方向由「楔形侧（弧切下来的那一块）在行进方向的哪一侧」唯一确定，
# 鞍点（case 5 / 10）的配对由中心值决定。手写过一次就翻过一次车——
# case 10 的「中心为背景」分支两条弧都写成 L→T / R→B，于是在共享边上
# 两条弧**都终止**于同一交点，轮廓链断开，字形被描成自交的蝴蝶结、
# 笔画中间挖出白洞（实测「51_E134」IoU 掉到 0.83）。现在表由推导生成，
# 不可能再漂。
#
# 推导规则：
#   * 交点落在「两侧角色不同」的边上；
#   * 弧的楔形侧若是背景 → 必须在行进方向左侧；若是墨 → 必须在右侧；
#     屏幕坐标 y 向下时，点在左侧 ⟺ 叉积 (p1-p0)×(pt-p0) < 0；
#   * 鞍点：中心值 ≥ 阈值 → 背景角经中心连通 → 弧切下另外两个角；
#     中心值 < 阈值 → 墨角连通 → 弧切下背景的那两个角。
_CORNERS = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (1.0, 1.0), "d": (0.0, 1.0)}
_EDGE_MID = {"T": (0.5, 0.0), "R": (1.0, 0.5), "B": (0.5, 1.0), "L": (0.0, 0.5)}
_EDGE_CORNERS = {"T": ("a", "b"), "R": ("b", "c"), "B": ("c", "d"), "L": ("d", "a")}
# 鞍点的两种配对：切下哪两个角，中间带里剩哪两个角
_SADDLE_PAIRINGS = {
    "ac": (("T", "L"), ("R", "B")),   # 切下 a、c，中间带 b、d
    "bd": (("T", "R"), ("L", "B")),   # 切下 b、d，中间带 a、c
}
_CUT_CORNER = {("T", "L"): "a", ("R", "B"): "c", ("T", "R"): "b", ("L", "B"): "d"}


def _on_left(p0: tuple[float, float], p1: tuple[float, float],
             pt: tuple[float, float]) -> bool:
    """屏幕坐标（y 向下）下 pt 是否在 p0→p1 的左侧。"""
    cross = ((p1[0] - p0[0]) * (pt[1] - p0[1])
             - (p1[1] - p0[1]) * (pt[0] - p0[0]))
    return cross < 0


def _derive_case_table() -> tuple[dict[int, list[tuple[str, str]]],
                                  dict[int, dict[str, list[tuple[str, str]]]]]:
    """按「背景在左」约定推导 case 表。返回 (普通 case 表, 鞍点表)。"""
    segs: dict[int, list[tuple[str, str]]] = {}
    saddle: dict[int, dict[str, list[tuple[str, str]]]] = {}

    def orient(e0: str, e1: str, wedge_is_bg: bool,
               wedge_pt: tuple[float, float]) -> tuple[str, str]:
        """给出 (起始边, 终止边)，使楔形侧落在约定的一侧。"""
        p0, p1 = _EDGE_MID[e0], _EDGE_MID[e1]
        if _on_left(p0, p1, wedge_pt) == wedge_is_bg:
            return (e0, e1)
        return (e1, e0)

    for code in range(16):
        bg = {cn for i, cn in enumerate("abcd") if code & (1 << i)}
        crossed = [e for e in ("T", "R", "B", "L")
                   if (_EDGE_CORNERS[e][0] in bg) != (_EDGE_CORNERS[e][1] in bg)]
        if not crossed:
            segs[code] = []
            continue
        if len(crossed) == 2:
            # 非鞍点：背景角必定同侧，取其一作楔形代表
            e0, e1 = crossed
            segs[code] = [orient(e0, e1, True, _CORNERS[next(iter(bg))])]
            continue
        # 鞍点：四条边都有交点
        saddle[code] = {}
        for center_bg in (True, False):
            connected = bg if center_bg else (set("abcd") - bg)
            pick = "ac" if connected == {"b", "d"} else "bd"
            arcs: list[tuple[str, str]] = []
            for e0, e1 in _SADDLE_PAIRINGS[pick]:
                w = _CUT_CORNER[(e0, e1)]
                arcs.append(orient(e0, e1, w in bg, _CORNERS[w]))
            saddle[code]["bg" if center_bg else "ink"] = arcs
    return segs, saddle


_DERIVED_SEGS, _DERIVED_SADDLE = _derive_case_table()
CASE_SEGMENTS = {k: v for k, v in _DERIVED_SEGS.items()}
CASE_5 = _DERIVED_SADDLE[5]
CASE_10 = _DERIVED_SADDLE[10]


def _interp(v0: float, v1: float, level: float) -> float:
    if v1 == v0:
        return 0.5
    return (level - v0) / (v1 - v0)


def marching_squares(gray: np.ndarray, level: float,
                     stats: dict | None = None) -> list[list[tuple[float, float]]]:
    """在灰度场上取 level 等值线，返回闭合轮廓列表（像素坐标，y 向下）。

    位图四周补一圈背景（值 1.0）：贴着画布边缘的字形，其轮廓在图外那一侧没有
    采样点，不补边就闭合不上（实测横笔画 IoU 直接掉到 0）。补边带来的 1 像素
    偏移在返回前减回去。
    """
    padded = np.pad(gray, 1, mode="constant", constant_values=1.0)
    segs: list[tuple[tuple[float, float], tuple[float, float]]] = []

    a_all = padded[:-1, :-1]
    b_all = padded[:-1, 1:]
    c_all = padded[1:, 1:]
    d_all = padded[1:, :-1]
    idx = ((a_all >= level).astype(np.uint8)
           | ((b_all >= level).astype(np.uint8) << 1)
           | ((c_all >= level).astype(np.uint8) << 2)
           | ((d_all >= level).astype(np.uint8) << 3))

    rows, cols = np.nonzero(idx)
    for i, j in zip(rows.tolist(), cols.tolist()):
        a = float(padded[i, j]); b = float(padded[i, j + 1])
        c = float(padded[i + 1, j + 1]); d = float(padded[i + 1, j])
        # 中心值：鞍点消歧用
        center = (a + b + c + d) / 4.0
        code = int(idx[i, j])
        pairs = CASE_SEGMENTS.get(code)
        if pairs is None:
            key = "bg" if center >= level else "ink"
            pairs = (CASE_5 if code == 5 else CASE_10)[key]
        if not pairs:
            continue
        edges = {
            # 数组索引 → 像素中心坐标：(i, j) 的中心在 (j+0.5, i+0.5)
            "T": (j + _interp(a, b, level) + 0.5, i + 0.5),
            "R": (j + 1.0 + 0.5, i + _interp(b, c, level) + 0.5),
            "B": (j + _interp(d, c, level) + 0.5, i + 1.0 + 0.5),
            "L": (j + 0.5, i + _interp(a, d, level) + 0.5),
        }
        for e0, e1 in pairs:
            p0 = edges[e0]; p1 = edges[e1]
            segs.append((p0, p1))

    loops, n_open = _chain(segs)
    if stats is not None:
        stats["open_chains"] = n_open
    return [[(x - 1.0, y - 1.0) for (x, y) in lp] for lp in loops]


def _chain(segs: list[tuple[tuple[float, float], tuple[float, float]]]
           ) -> tuple[list[list[tuple[float, float]]], int]:
    """把线段串成闭合轮廓。

    返回 (轮廓列表, **断链数**)。断链 = 走到某个交点找不到下一段线段，
    轮廓没闭合。这样的链描出来是碎段而不是字，IoU 可能看着还行——
    所以单独计数报出来，别让它悄悄过去。

    按**线段下标**串联，不按坐标值反查线段——鞍点处多个格子会算出同一个坐标，
    按值查找会指到已经用过的段上，轮廓就碎成几十段（实测圆盘碎成 18 条）。

    **自接触点要多走一步判断**：两笔在一点相接时（如「乎」字上半的两笔交于一点），
    那个点上会有**两条**出边，分别通向两个笔画。此时若随手取第一条，轮廓就会
    从一个笔画跳到另一个笔画上，围出一个自交的「蝴蝶结」，填充后笔画中间被挖空
    （实测该字 IoU 掉到 0.83）。正确的走法是取与来向**最直**的那条——
    轮廓在自接触处是平滑通过的。
    """
    def key(p: tuple[float, float]) -> tuple[int, int]:
        return (round(p[0] * 64), round(p[1] * 64))

    outgoing: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, s in enumerate(segs):
        outgoing[key(s[0])].append(i)

    def direction(idx: int) -> tuple[float, float]:
        s = segs[idx]
        return (s[1][0] - s[0][0], s[1][1] - s[0][1])

    loops: list[list[tuple[float, float]]] = []
    used: set[int] = set()
    n_open = 0
    for si in range(len(segs)):
        if si in used:
            continue
        used.add(si)
        loop = [segs[si][0]]
        end = segs[si][1]
        prev = direction(si)
        closed = False
        while True:
            loop.append(end)
            cands = [i for i in outgoing.get(key(end), ()) if i not in used]
            if not cands:
                closed = key(end) == key(loop[0])
                break
            if len(cands) == 1:
                nxt = cands[0]
            else:
                best, best_dot = cands[0], -2.0
                for idx in cands:
                    d = direction(idx)
                    n1 = math.hypot(*prev) or 1.0
                    n2 = math.hypot(*d) or 1.0
                    dot = (prev[0] * d[0] + prev[1] * d[1]) / (n1 * n2)
                    if dot > best_dot:
                        best, best_dot = idx, dot
                nxt = best
            used.add(nxt)
            prev = direction(nxt)
            end = segs[nxt][1]
        if not closed:
            n_open += 1
        # 闭合的环首尾同点，去掉重复的末点（后续一律按「隐式闭合」处理）
        if len(loop) >= 2 and loop[0] == loop[-1]:
            loop = loop[:-1]
        if len(loop) >= 4:
            loops.append(loop)
    return loops, n_open


# ---------------------------------------------------------------- 简化与平滑

def rdp(points: list[tuple[float, float]], eps: float) -> list[tuple[float, float]]:
    """Douglas–Peucker 简化。"""
    if len(points) < 3 or eps <= 0:
        return points
    # 迭代实现，避免深递归
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        s, e = stack.pop()
        if e <= s + 1:
            continue
        ax, ay = points[s]
        bx, by = points[e]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        best = -1.0
        bi = -1
        for i in range(s + 1, e):
            px, py = points[i]
            if norm == 0:
                dist = math.hypot(px - ax, py - ay)
            else:
                dist = abs(dy * px - dx * py + bx * ay - by * ax) / norm
            if dist > best:
                best = dist
                bi = i
        if best > eps and bi > 0:
            keep[bi] = True
            stack.append((s, bi))
            stack.append((bi, e))
    return [p for p, k in zip(points, keep) if k]


def rdp_closed(points: list[tuple[float, float]], eps: float) -> list[tuple[float, float]]:
    """闭合环的 Douglas–Peucker 简化。

    直接把闭合环当开放折线简化，起终点之间那根弦会把整环的偏差都算大，
    简化几乎不起作用。这里先找一对离得最远的顶点把环切成两半，各自简化
    再拼回去。
    """
    n = len(points)
    if n < 4 or eps <= 0:
        return points
    p0 = points[0]
    m = max(range(1, n),
            key=lambda i: (points[i][0] - p0[0]) ** 2 + (points[i][1] - p0[1]) ** 2)
    a = rdp(points[:m + 1], eps)
    b = rdp(points[m:] + [points[0]], eps)
    return a[:-1] + b[:-1]


def chaikin(points: list[tuple[float, float]], iterations: int) -> list[tuple[float, float]]:
    """Chaikin 切角平滑：去掉 marching squares 的阶梯感。"""
    for _ in range(iterations):
        if len(points) < 4:
            break
        out: list[tuple[float, float]] = []
        n = len(points)
        for i in range(n):
            p0 = points[i]
            p1 = points[(i + 1) % n]
            out.append((0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1]))
            out.append((0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1]))
        points = out
    return points


def signed_area(points: list[tuple[float, float]]) -> float:
    s = 0.0
    n = len(points)
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def sample_gray(gray: np.ndarray, x: float, y: float) -> float:
    """取图像坐标 (x, y) 处的灰度（最近邻）。

    坐标约定与 marching squares 一致：像素 (i, j) 的中心在 (j+0.5, i+0.5)，
    像素 (i, j) 覆盖 x∈[j, j+1)、y∈[i, i+1)。
    """
    h, w = gray.shape
    j = min(max(int(math.floor(x)), 0), w - 1)
    i = min(max(int(math.floor(y)), 0), h - 1)
    return float(gray[i, j])


def orient_loops_by_field(loops: list[list[tuple[float, float]]], gray: np.ndarray,
                          level: float) -> int:
    """按「墨在右」校正每条轮廓的绕向，返回被翻转的条数。

    marching squares 的方向约定（背景在左 ⇒ 墨在右）本身已经保证外轮廓与洞
    绕向相反，nonzero 填充直接成立；这层只是**兜底**，防止个别轮廓方向反了
    把洞填实。

    判据不用「嵌套深度」：那要假设轮廓是简单多边形，而字形轮廓常是**自接触**
    的（两笔在一点相交），深度算错就会把一条轮廓翻反、连带把洞填实。
    改用**局部判据**：在轮廓各边中点沿法向两侧各取一点，看哪边是墨——
    墨必须在行进方向的右侧。投票要够多数才翻，避免细笔画上偶发的一次误判
    把一条本来正确的轮廓翻掉。
    """
    flipped = 0
    for lp in loops:
        n = len(lp)
        if n < 3:
            continue
        votes = 0
        sampled = 0
        for i in range(n):
            x0, y0 = lp[i]
            x1, y1 = lp[(i + 1) % n]
            dx, dy = x1 - x0, y1 - y0
            length = math.hypot(dx, dy)
            if length < 1e-9:
                continue
            nx, ny = -dy / length, dx / length      # 右法线（屏幕坐标 y 向下）
            mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            right = sample_gray(gray, mx + nx * 0.5, my + ny * 0.5)
            left = sample_gray(gray, mx - nx * 0.5, my - ny * 0.5)
            if right < level and left >= level:
                votes += 1
            elif right >= level and left < level:
                votes -= 1
            sampled += 1
        if sampled == 0:
            continue
        # 墨在右 → 多数边应满足 votes > 0；方向反了则是 votes < 0
        if votes < 0 and -votes >= max(3, int(sampled * 0.6)):
            lp.reverse()
            flipped += 1
    return flipped


# ---------------------------------------------------------------- 输出

def fmt(v: float, precision: int = 3) -> str:
    s = f"{v:.{precision}f}".rstrip("0").rstrip(".")
    return s or "0"


def loops_to_path(loops: list[list[tuple[float, float]]], precision: int = 3) -> str:
    parts = []
    for lp in loops:
        if len(lp) < 3:
            continue
        head = f"M {fmt(lp[0][0], precision)} {fmt(lp[0][1], precision)}"
        rest = " ".join(f"L {fmt(x, precision)} {fmt(y, precision)}" for x, y in lp[1:])
        parts.append(f"{head} {rest} Z")
    return " ".join(parts)


def render_svg(viewbox: tuple[float, float, float, float], d: str) -> str:
    vx, vy, vw, vh = viewbox
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vx:.2f} {vy:.2f} {vw:.2f} {vh:.2f}">\n'
        f'<path d="{d}" fill="#111" fill-rule="nonzero" stroke="none"/>\n'
        "</svg>\n"
    )


def trace_loops(gray: np.ndarray, *, level: float = 0.5, eps: float = 0.35,
                smooth: int = 1,
                stats: dict | None = None) -> list[list[tuple[float, float]]]:
    """灰度场 → 简化平滑后的闭合轮廓列表（填充前的几何真相）。

    顺序是「**先平滑后简化**」，不能反。Chaikin 切角的角度与**边长**成正比：
    先 RDP 把一条 160 px 长的直边压成 4 个顶点，再 Chaikin 就会在两端各啃掉
    1/4 边长的三角形——细笔画的 IoU 直接掉到 0.88。先 Chaikin（此时边长只有
    1 px 量级，切角可以忽略）再 RDP，切角就没了。

    ``stats`` 可选：回填 ``open_chains``（没闭合的链数）与 ``flipped``
    （被翻转绕向的轮廓数）。**open_chains > 0 是严重信号**——说明轮廓链在
    某个交点处断了，描出来的东西是碎段而不是字。
    """
    raw_stats: dict = {}
    raw = marching_squares(gray, level, stats=raw_stats)
    out: list[list[tuple[float, float]]] = []
    for lp in raw:
        s = lp
        if smooth:
            s = chaikin(s, smooth)
        s = rdp_closed(s, eps)
        if len(s) < 3:
            continue
        out.append(s)
    flipped = orient_loops_by_field(out, gray, level)
    if stats is not None:
        stats["open_chains"] = raw_stats.get("open_chains", 0)
        stats["flipped"] = flipped
        stats["raw_loops"] = len(raw)
    return out


def bbox_of(loops: list[list[tuple[float, float]]], pad: float = 1.0
            ) -> tuple[float, float, float, float]:
    """轮廓包围盒（加 pad 留白）。"""
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    vx, vy = min(xs) - pad, min(ys) - pad
    vw, vh = (max(xs) - min(xs)) + 2 * pad, (max(ys) - min(ys)) + 2 * pad
    return (vx, vy, vw, vh)


def trace_gray(gray: np.ndarray, *, level: float = 0.5, eps: float = 0.35,
               smooth: int = 1) -> tuple[str, tuple[float, float, float, float]]:
    """灰度场 → (path d, viewBox)。"""
    simplified = trace_loops(gray, level=level, eps=eps, smooth=smooth)
    if not simplified:
        return "", (0.0, 0.0, 1.0, 1.0)
    d = loops_to_path(simplified)
    return d, bbox_of(simplified)


# ---------------------------------------------------------------- 光栅化与 IoU

def rasterize_loops(loops: list[list[tuple[float, float]]], width: int, height: int,
                    offset: tuple[float, float] = (0.0, 0.0),
                    rule: str = "nonzero") -> np.ndarray:
    """扫描线填充。

    默认 **nonzero**（与仓库其余各层一致）：按绕向累加绕数，绕数非零处填充。
    早先用 evenodd，在**两笔在一点相接**的字形上会翻车——轮廓自接触，
    evenodd 的奇偶性在接触点两侧相反，一侧的笔画就被挖空了
    （实测「乎」字 IoU 掉到 0.83，笔画中间出现白洞）。nonzero 下自接触处
    绕数一致，两侧都填实。
    """
    mask = np.zeros((height, width), dtype=bool)
    edges: list[tuple[float, float, float, float]] = []
    for lp in loops:
        ox, oy = offset
        n = len(lp)
        for i in range(n):
            x0, y0 = lp[i]
            x1, y1 = lp[(i + 1) % n]
            edges.append((x0 + ox, y0 + oy, x1 + ox, y1 + oy))
    if not edges:
        return mask
    ymin = max(0, int(math.floor(min(min(e[1], e[3]) for e in edges))))
    ymax = min(height - 1, int(math.ceil(max(max(e[1], e[3]) for e in edges))))
    ex0 = np.array([e[0] for e in edges])
    ey0 = np.array([e[1] for e in edges])
    ex1 = np.array([e[2] for e in edges])
    ey1 = np.array([e[3] for e in edges])
    for y in range(ymin, ymax + 1):
        yc = y + 0.5
        hit = ((ey0 <= yc) & (ey1 > yc)) | ((ey1 <= yc) & (ey0 > yc))
        if not hit.any():
            continue
        xs = ex0[hit] + (yc - ey0[hit]) * (ex1[hit] - ex0[hit]) / (ey1[hit] - ey0[hit])
        if rule == "evenodd":
            xs = np.sort(xs)
            for k in range(0, len(xs) - 1, 2):
                xa = int(math.ceil(xs[k] - 0.5))
                xb = int(math.floor(xs[k + 1] - 0.5))
                if xb >= xa:
                    mask[y, max(0, xa):min(width, xb + 1)] = True
            continue
        # nonzero：按绕向累加
        direction = np.where(ey1[hit] > ey0[hit], 1, -1)
        order = np.argsort(xs)
        xs = xs[order]
        direction = direction[order]
        winding = 0
        for k in range(len(xs) - 1):
            winding += int(direction[k])
            if winding == 0:
                continue
            xa = int(math.ceil(xs[k] - 0.5))
            xb = int(math.floor(xs[k + 1] - 0.5))
            if xb >= xa:
                mask[y, max(0, xa):min(width, xb + 1)] = True
    return mask


def iou(a: np.ndarray, b: np.ndarray) -> float:
    union = int((a | b).sum())
    if union == 0:
        return 1.0
    return float((a & b).sum()) / float(union)


# ---------------------------------------------------------------- 主流程

def trace_file(src: Path, dst: Path, *, level: float, eps: float, smooth: int,
               check: bool) -> dict:
    gray, alpha = load_gray(src)
    truth = ink_mask(gray, level)
    stats: dict = {}
    simplified = trace_loops(gray, level=level, eps=eps, smooth=smooth, stats=stats)
    if not simplified:
        return {"src": str(src), "status": "empty", "iou": 0.0,
                "open_chains": stats.get("open_chains", 0)}
    d = loops_to_path(simplified)
    viewbox = bbox_of(simplified)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(render_svg(viewbox, d), encoding="utf-8", newline="\n")

    score = None
    if check:
        h, w = gray.shape
        raster = rasterize_loops(simplified, w, h)
        score = iou(truth, raster)
    return {"src": str(src), "dst": str(dst), "iou": score, "status": "ok",
            "viewbox": viewbox, "path_len": len(d),
            "loops": len(simplified),
            "points": sum(len(lp) for lp in simplified),
            "open_chains": stats.get("open_chains", 0),
            "flipped": stats.get("flipped", 0)}


def selftest() -> int:
    """自检：合成形状 → 描摹 → 光栅化 → IoU。

    两点讲究：

    1. 合成场的 0.5 等值线**故意错开像素中心**。8 位灰度里不存在恰好 0.5 的
       灰度值，真图不会出现「等值线正好压在像素中心」的退化情形；合成图若压在
       中心上，像素中心正好落在轮廓边界上，「中心在多边形内」与光栅化的半开
       区间判定会对不上，测出来的是约定差异而不是算法误差。
    2. 顺带断言**轮廓条数**：圆盘应得 1 条、圆环应得 2 条（外廓 + 洞）。早期
       版本轮廓碎成 18 条，IoU 掉到 0.13——只看 IoU 看不出是「碎」还是「偏」。
    """
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str) -> None:
        print(("  PASS  " if ok else "  FAIL  ") + name + "  —  " + detail)
        if not ok:
            failures.append(name)

    def make_disk(size: int, r: float) -> np.ndarray:
        # 与真实图一致：**墨是深色**（值小），背景亮（值大）
        yy, xx = np.mgrid[0:size, 0:size]
        d = np.hypot(xx - size / 2 + 0.5, yy - size / 2 + 0.5)
        return np.clip((d - r) / 1.2 + 0.5, 0.0, 1.0).astype(np.float32)

    def make_stroke(size: int, w: float) -> np.ndarray:
        # 中心挪 0.25 px，使等值线不压在像素中心上
        yy, xx = np.mgrid[0:size, 0:size]
        d = np.abs(yy - size / 2 + 0.75) - w / 2
        return np.clip(d / 1.2 + 0.5, 0.0, 1.0).astype(np.float32)

    def make_diag(size: int, w: float) -> np.ndarray:
        # 斜笔画会大量触发鞍点（case 5 / 10）
        yy, xx = np.mgrid[0:size, 0:size]
        d = np.abs((yy + 0.25) - (xx + 0.25)) / math.sqrt(2.0) - w / 2
        return np.clip(d / 1.2 + 0.5, 0.0, 1.0).astype(np.float32)

    cases = [
        # 名字, 场, IoU 门槛, 期望轮廓条数
        ("实心圆盘 r=60 @160", make_disk(160, 60.0), 0.97, 1),
        ("实心圆盘 r=25 @160", make_disk(160, 25.0), 0.95, 1),
        ("横笔画 w=8 @160（贴画布左右边）", make_stroke(160, 8.0), 0.95, 1),
        ("横笔画 w=3 @160（细笔）", make_stroke(160, 3.0), 0.90, 1),
        ("斜笔画 w=10 @160（走鞍点 case 5/10）", make_diag(160, 10.0), 0.90, 1),
    ]
    for name, field, need, need_loops in cases:
        truth = field < 0.5
        stats: dict = {}
        simplified = trace_loops(field, level=0.5, eps=0.35, smooth=1, stats=stats)
        h, w = field.shape
        raster = rasterize_loops(simplified, w, h)
        score = iou(truth, raster)
        ok = (score >= need and len(simplified) == need_loops
              and stats.get("open_chains", 0) == 0)
        check(name, ok,
              f"IoU={score:.4f}（门槛 {need}）轮廓 {len(simplified)} 条（期望 {need_loops}）"
              f"断链 {stats.get('open_chains', 0)}")

    # 洞：圆环。场要写成 max：外侧亮、洞内亮、环带暗 → 0.5 等值线是两条圆。
    # （写成 min 会得到「洞里暗、环带亮」，等值线还是两条圆，但墨在环外，
    #   轮廓同样只有一条外廓——早期版本就是这里写错，测出来「只有 1 条轮廓」。）
    yy, xx = np.mgrid[0:200, 0:200]
    dist = np.hypot(xx - 100, yy - 100)
    outer = np.clip((dist - 60.0) / 1.2 + 0.5, 0.0, 1.0)
    inner = np.clip((30.0 - dist) / 1.2 + 0.5, 0.0, 1.0)
    ring = np.maximum(outer, inner).astype(np.float32)
    truth = ring < 0.5
    stats: dict = {}
    simplified = trace_loops(ring, level=0.5, eps=0.35, smooth=1, stats=stats)
    raster = rasterize_loops(simplified, 200, 200)
    score = iou(truth, raster)
    ok = score >= 0.95 and len(simplified) == 2 and stats.get("open_chains", 0) == 0
    check("圆环（带洞）", ok,
          f"IoU={score:.4f}（门槛 0.95）轮廓 {len(simplified)} 条（期望 2）"
          f"断链 {stats.get('open_chains', 0)}")

    # 随机圆块回归：随机形状会大量触发 case 5 / 10 鞍点与**自接触**轮廓，
    # 正是 case 表方向写反时会「链断 → 碎成几十段」的地方。这里盯两件事：
    #   * 断链数必须为 0（链断了就说明有交点接不上）；
    #   * 填充结果必须与原场一致（IoU 高）。
    # 这条测试是有来历的：case 10「中心为背景」分支的方向反了以后，
    # 圆盘/圆环这些规整形状照样全绿（它们几乎不触发该分支），
    # 只有真实字形与随机形状才会露馅。
    rng = np.random.default_rng(20240607)
    worst_iou = 1.0
    worst_open = 0
    for trial in range(12):
        size = 140
        field = np.ones((size, size), dtype=np.float32)
        for _ in range(int(rng.integers(4, 10))):
            cx = float(rng.uniform(15, size - 15))
            cy = float(rng.uniform(15, size - 15))
            r = float(rng.uniform(5, 26))
            yy, xx = np.mgrid[0:size, 0:size]
            d = np.hypot(xx - cx, yy - cy)
            field = np.minimum(field, np.clip((d - r) / 1.2 + 0.5, 0.0, 1.0))
        truth = field < 0.5
        st: dict = {}
        loops = trace_loops(field, level=0.5, eps=0.35, smooth=1, stats=st)
        raster = rasterize_loops(loops, size, size)
        score = iou(truth, raster)
        worst_iou = min(worst_iou, score)
        worst_open = max(worst_open, st.get("open_chains", 0))
    ok = worst_open == 0 and worst_iou >= 0.97
    check("随机圆块 ×12（大量鞍点 + 自接触）", ok,
          f"最低 IoU={worst_iou:.4f}（门槛 0.97）最大断链 {worst_open}")

    print("自检结果   : " + ("全部通过" if not failures else f"{len(failures)} 项失败"))
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="小学堂位图 → SVG 描摹")
    ap.add_argument("--input", type=Path, default=None, help="位图目录或单文件")
    ap.add_argument("--out", type=Path, default=None, help="SVG 落盘目录")
    ap.add_argument("--level", type=float, default=0.5, help="等值线阈值（默认 0.5）")
    ap.add_argument("--eps", type=float, default=0.35, help="Douglas-Peucker 容差（像素）")
    ap.add_argument("--smooth", type=int, default=1, help="Chaikin 平滑轮数")
    ap.add_argument("--check", action="store_true", help="回光栅化算 IoU")
    ap.add_argument("--selftest", action="store_true", help="跑几何自检后退出")
    ap.add_argument("--manifest", type=Path, default=None,
                    help="抓取清单；描摹后另存一份带 provenance 字段的清单")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    if not args.input or not args.out:
        ap.error("需要 --input 与 --out（或用 --selftest）")

    srcs: list[Path]
    if args.input.is_dir():
        srcs = sorted(args.input.glob("*.png")) + sorted(args.input.glob("*.gif"))
    else:
        srcs = [args.input]
    if not srcs:
        raise SystemExit(f"{args.input} 里没有 .png / .gif")

    records: list[dict] = []
    scores: list[tuple[float, Path]] = []
    for src in srcs:
        dst = args.out / (src.stem + ".svg")
        rec = trace_file(src, dst, level=args.level, eps=args.eps,
                         smooth=args.smooth, check=args.check)
        records.append(rec)
        if rec.get("iou") is not None:
            scores.append((rec["iou"], src))
        if len(records) % 100 == 0:
            print(f"  … 已描摹 {len(records)}/{len(srcs)}")

    if scores:
        vals = sorted(s for s, _ in scores)
        p05 = vals[max(0, int(len(vals) * 0.05) - 1)]
        below = [(s, p.name) for s, p in scores if s < IOU_WARN]
        warn = [(s, p.name) for s, p in scores if IOU_PASS > s >= IOU_WARN]
        broken = [(r["src"], r.get("open_chains", 0)) for r in records
                  if r.get("open_chains", 0)]
        print(f"描摹 {len(scores)} 件：IoU 最低 {vals[0]:.4f} / p05 {p05:.4f} / 中位 {vals[len(vals) // 2]:.4f}")
        print(f"  合格(≥{IOU_PASS}) {len(vals) - len(below) - len(warn)} 件"
              f" / 警戒 {len(warn)} 件 / 失败(<{IOU_WARN}) {len(below)} 件")
        for s, name in below[:20]:
            print(f"    FAIL {name} IoU={s:.4f}")
        if broken:
            # 断链 = 轮廓在某个交点处接不上，描出来的是碎段而不是字。
            # 这是严重信号：IoU 可能还行，但字形已经不对了。
            print(f"  !! 断链 {len(broken)} 件（轮廓未闭合，需重查 case 表 / 串接规则）")
            for path, n in broken[:20]:
                print(f"    BROKEN {Path(path).name} 断链 {n}")

    if args.manifest:
        # 抓取清单（manifest.jsonl）是一行一个**实例**（字頭 × 出處），
        # 而描摹是按**字形**做的：同一个 (字体号, 码位) 会被多个字頭复用。
        # 所以这里按 shape_key 归并——清单里同 shape 的实例合并成一条描摹记录，
        # 实例→字形的对应关系留给后面合并时按 shape_key join。
        meta: dict[str, dict] = {}
        for line in args.manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            key = rec.get("shape_key") or rec["pua"]
            meta.setdefault(key, rec)
        out_path = args.manifest.with_name("traced.jsonl")
        with out_path.open("w", encoding="utf-8", newline="\n") as fh:
            for rec in records:
                src = Path(rec["src"])
                key = src.stem
                base = meta.get(key, {})
                svg_path = Path(rec.get("dst", ""))
                svg_bytes = svg_path.read_bytes() if svg_path.exists() else b""
                fh.write(json.dumps({
                    "shape_key": key,
                    "db": base.get("db", ""),
                    "font_id": base.get("font_id", ""),
                    "font": base.get("font", ""),
                    "pua": base.get("pua", ""),
                    "source_short": base.get("source_short", ""),
                    "zi_order": base.get("zi_order", ""),
                    "modern_char": base.get("modern_char", ""),
                    "source_url": base.get("source_url", ""),
                    "source_page_url": base.get("source_page_url", ""),
                    "source_sha256": base.get("sha256", ""),
                    "source_bytes": base.get("bytes", 0),
                    "svg_path": str(svg_path).replace("\\", "/"),
                    "svg_sha256": hashlib.sha256(svg_bytes).hexdigest() if svg_bytes else "",
                    "svg_bytes": len(svg_bytes),
                    "derived_from": base.get("source_url", ""),
                    "derived_from_sha256": base.get("sha256", ""),
                    "transform": TRANSFORM.format(eps=args.eps, smooth=args.smooth),
                    "tool": TOOL,
                    "modifications": "上游为位图，本地 SVG 由自动描摹生成（非上游矢量原件）",
                    "iou": rec.get("iou"),
                }, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"描摹清单已写入 {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
