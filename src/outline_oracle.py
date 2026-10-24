#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把甲骨文笔画骨架（glyphs/oracle/*.svg）转成可填充的轮廓。

用法::

    python src/outline_oracle.py [--repo-root DIR] [--check] [--preview N] [--dry-run]

产出::

    glyphs/oracle/outline/<glyph_id>.svg   与骨架同名、同 viewBox 的填充轮廓
    glyphs/provenance/oracle.jsonl         追加 layer="outline" 的派生记录

为什么不用第三方库：本机只有 PIL / numpy / lxml。上游骨架的 ``d`` 只含 ``M``/``L``
（直线段），所以描边区域可以精确拆成**每段一个「体育场」轮廓**（线段两侧平行边 +
两端半圆帽）。所有轮廓同向，用 ``fill-rule="nonzero"`` 填充即为并集，无需布尔运算。

轮廓恒等于 ``stroke-linecap="round" stroke-linejoin="round"`` 的描边区域，因此
与骨架在几何上逐像素对应；本脚本的 ``--check`` 会用独立实现验证这一点。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"
NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
TOKEN_RE = re.compile(r"[A-Za-z]|" + NUM)
VIEWBOX_RE = re.compile(r"^\s*" + NUM + r"\s+" + NUM + r"\s+" + NUM + r"\s+" + NUM + r"\s*$")


# ---------------------------------------------------------------- 读取骨架

def parse_skeleton(path: Path) -> tuple[list[float], list[tuple[list[tuple[float, float]], float]]]:
    """返回 (viewBox, [(折线点列, 半宽), ...])。

    ``d`` 里出现 M/L 以外的命令就直接报错，绝不静默错解。
    """
    root = ET.parse(path).getroot()
    viewbox_attr = root.get("viewBox")
    if not viewbox_attr or not VIEWBOX_RE.match(viewbox_attr):
        raise SystemExit(f"{path}: viewBox 缺失或不是 4 个数字：{viewbox_attr!r}")
    viewbox = [float(v) for v in viewbox_attr.split()]

    strokes: list[tuple[list[tuple[float, float]], float]] = []
    for el in root.iter(f"{{{SVG_NS}}}path"):
        d = el.get("d", "")
        if not d:
            continue
        if re.search(r"[A-Za-z]", re.sub(r"[MLZmlz]", "", d)):
            raise SystemExit(f"{path}: d 含 M/L 以外的命令，本脚本不支持：{d[:80]!r}")
        tokens = TOKEN_RE.findall(d)
        points: list[tuple[float, float]] = []
        expect_point = False
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in ("M", "L"):
                expect_point = True
                index += 1
                continue
            if not expect_point:
                raise SystemExit(f"{path}: d 里出现游离坐标：{d[:80]!r}")
            points.append((float(tokens[index]), float(tokens[index + 1])))
            index += 2
        half = float(el.get("stroke-width", "1")) / 2.0
        if half <= 0:
            raise SystemExit(f"{path}: stroke-width 非正")
        if len(points) >= 2:
            strokes.append((points, half))
        elif len(points) == 1:
            strokes.append((points, half))  # 退化成点 → 一个圆
    if not strokes:
        raise SystemExit(f"{path}: 没有可用的描边路径")
    return viewbox, strokes


# ---------------------------------------------------------------- 生成轮廓

def circle_subpath(cx: float, cy: float, r: float, f) -> str:
    return (f"M {f(cx + r)} {f(cy)} "
            f"A {f(r)} {f(r)} 0 0 0 {f(cx - r)} {f(cy)} "
            f"A {f(r)} {f(r)} 0 0 0 {f(cx + r)} {f(cy)} Z")


def stadium_subpath(a: tuple[float, float], b: tuple[float, float],
                    r: float, f) -> str:
    """线段 a→b、半宽 r 的描边区域（圆角矩形 / 体育场），一个闭合子路径。

    两处圆弧都用 sweep-flag=0（角度递减方向），使弧从线段两端朝「外侧」鼓出；
    所有子路径方向一致，nonzero 填充即为并集。
    """
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length == 0:
        return circle_subpath(ax, ay, r, f)
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    p1 = (ax + nx * r, ay + ny * r)
    p2 = (bx + nx * r, by + ny * r)
    p3 = (bx - nx * r, by - ny * r)
    p4 = (ax - nx * r, ay - ny * r)
    rr = f(r)
    return (f"M {f(p1[0])} {f(p1[1])} L {f(p2[0])} {f(p2[1])} "
            f"A {rr} {rr} 0 0 0 {f(p3[0])} {f(p3[1])} "
            f"L {f(p4[0])} {f(p4[1])} "
            f"A {rr} {rr} 0 0 0 {f(p1[0])} {f(p1[1])} Z")


def build_outline(strokes, viewbox, precision: int = 3):
    """返回 (d 字符串, 轮廓包围盒)。"""
    f = lambda v: f"{v:.{precision}f}".rstrip("0").rstrip(".") or "0"
    subpaths: list[str] = []
    xs: list[float] = []
    ys: list[float] = []
    for points, r in strokes:
        for i in range(len(points) - 1):
            subpaths.append(stadium_subpath(points[i], points[i + 1], r, f))
        if len(points) == 1:
            subpaths.append(circle_subpath(points[0][0], points[0][1], r, f))
        for x, y in points:
            xs.extend((x - r, x + r))
            ys.extend((y - r, y + r))
    return " ".join(subpaths), (min(xs), min(ys), max(xs), max(ys))


def render_svg(viewbox, d: str) -> str:
    vx, vy, vw, vh = viewbox
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vx:.2f} {vy:.2f} {vw:.2f} {vh:.2f}">\n'
        f'<path d="{d}" fill="#111" fill-rule="nonzero" stroke="none"/>\n'
        "</svg>\n"
    )


# ------------------------------------------- 独立校验：按 W3C 规范展开圆弧

def arc_points(x1, y1, rx, ry, phi_deg, large_arc, sweep, x2, y2, steps=32):
    """把 SVG 圆弧端点式参数转成折线（W3C SVG 1.1 附录 F.6 的实现）。"""
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    phi = math.radians(phi_deg)
    cosp, sinp = math.cos(phi), math.sin(phi)
    dx2, dy2 = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p = cosp * dx2 + sinp * dy2
    y1p = -sinp * dx2 + cosp * dy2
    rx, ry = abs(rx), abs(ry)
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        scale = math.sqrt(lam)
        rx *= scale
        ry *= scale
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coefficient = math.sqrt(max(num / den, 0.0))
    if large_arc == sweep:
        coefficient = -coefficient
    cxp = coefficient * rx * y1p / ry
    cyp = -coefficient * ry * x1p / rx
    cx = cosp * cxp - sinp * cyp + (x1 + x2) / 2.0
    cy = sinp * cxp + cosp * cyp + (y1 + y2) / 2.0

    def angle(ux, uy, vx, vy):
        dot = ux * vx + uy * vy
        norm = math.hypot(ux, uy) * math.hypot(vx, vy)
        value = max(-1.0, min(1.0, dot / norm))
        sign = -1.0 if (ux * vy - uy * vx) < 0 else 1.0
        return sign * math.acos(value)

    theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    delta = angle((x1p - cxp) / rx, (y1p - cyp) / ry,
                  (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if sweep == 0 and delta > 0:
        delta -= 2 * math.pi
    elif sweep == 1 and delta < 0:
        delta += 2 * math.pi

    out = []
    for i in range(1, steps + 1):
        theta = theta1 + delta * i / steps
        ex, ey = rx * math.cos(theta), ry * math.sin(theta)
        out.append((cx + cosp * ex - sinp * ey, cy + sinp * ex + cosp * ey))
    return out


def flatten_path(d: str, steps: int = 32) -> list[list[tuple[float, float]]]:
    """把生成的 d 展开成多边形列表（用于校验）。"""
    tokens = TOKEN_RE.findall(d)
    polygons: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    cursor = (0.0, 0.0)
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in ("M", "L"):
            i += 1
            point = (float(tokens[i]), float(tokens[i + 1]))
            i += 2
            if token == "M":
                if len(current) > 2:
                    polygons.append(current)
                current = [point]
            else:
                current.append(point)
            cursor = point
        elif token == "A":
            rx, ry = float(tokens[i + 1]), float(tokens[i + 2])
            rot = float(tokens[i + 3])
            large, sweep = int(float(tokens[i + 4])), int(float(tokens[i + 5]))
            end = (float(tokens[i + 6]), float(tokens[i + 7]))
            i += 8
            current.extend(arc_points(cursor[0], cursor[1], rx, ry, rot, large, sweep,
                                      end[0], end[1], steps))
            cursor = end
        elif token in ("Z", "z"):
            i += 1
            if len(current) > 2:
                polygons.append(current)
            current = []
        else:
            raise SystemExit(f"展开 d 时遇到意外记号：{token!r}")
    if len(current) > 2:
        polygons.append(current)
    return polygons


# ------------------------------------------------------------ 光栅化对比

def rasterize(polys, viewbox, size: int):
    import numpy as np
    from PIL import Image, ImageDraw

    vx, vy, vw, vh = viewbox
    scale = size / max(vw, vh)
    width = max(1, int(round(vw * scale)))
    height = max(1, int(round(vh * scale)))
    image = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(image)
    for poly in polys:
        pts = [((x - vx) * scale, (y - vy) * scale) for x, y in poly]
        if len(pts) >= 3:
            draw.polygon(pts, fill=1)
    return np.array(image, dtype=bool), scale


def rasterize_skeleton(strokes, viewbox, size: int):
    """独立参照：沿中心线密铺圆盘（圆角描边的数学定义 = 中心线与圆盘的闵可夫斯基和）。

    刻意**不用** PIL 的粗线：它的 width 取整、且对偶数宽度会整体偏移半个像素，
    在只有几个像素粗的细线上会凭空吃掉两成 IoU，把参照物本身变成误差源。
    """
    import numpy as np
    from PIL import Image, ImageDraw

    vx, vy, vw, vh = viewbox
    scale = size / max(vw, vh)
    width = max(1, int(round(vw * scale)))
    height = max(1, int(round(vh * scale)))
    image = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(image)

    def disk(cx, cy, rp):
        draw.ellipse([cx - rp, cy - rp, cx + rp, cy + rp], fill=1)

    for points, r in strokes:
        rp = max(r * scale, 0.5)
        pts = [((x - vx) * scale, (y - vy) * scale) for x, y in points]
        step = max(rp / 3.0, 0.5)
        if len(pts) == 1:
            disk(pts[0][0], pts[0][1], rp)
            continue
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            span = math.hypot(x2 - x1, y2 - y1)
            count = max(1, int(span / step) + 1)
            for k in range(count + 1):
                t = k / count
                disk(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, rp)
    return np.array(image, dtype=bool)


def iou(a, b) -> float:
    union = (a | b).sum()
    return float((a & b).sum()) / float(union) if union else 1.0


# ------------------------------------------------------------------- 主流程

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def merge_provenance(path: Path, new_records: list[dict], layer: str) -> tuple[int, int]:
    kept = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("script") == "oracle" and record.get("layer") == layer:
                continue
            kept.append(record)
    merged = kept + new_records
    merged.sort(key=lambda r: (str(r.get("script", "")), str(r.get("path", ""))))
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in merged:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return len(kept), len(merged)


def selftest() -> int:
    """自检：轮廓是否真的等于圆角描边区域。"""
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str) -> None:
        print(("  PASS  " if ok else "  FAIL  ") + name + "  —  " + detail)
        if not ok:
            failures.append(name)

    vb = [0.0, 0.0, 30.0, 8.0]

    # 1) 单段：面积应等于解析值 2rL + πr²（能同时抓住帽型算错与自交）
    #    光栅化会把边界像素吃掉/吐出，固有偏差约「一像素周长」，判据里要放行这一项。
    a, b, r = (4.0, 4.0), (26.0, 4.0), 0.525
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    d, _ = build_outline([([a, b], r)], vb)
    mask, scale = rasterize(flatten_path(d, 64), vb, 1024)
    expect = 2 * r * length + math.pi * r * r
    expect_px = expect * scale * scale
    err_px = abs(float(mask.sum()) - expect_px)
    allowed_px = (2 * length + 2 * math.pi * r) * scale  # 一像素边界
    check("单段面积 vs 解析值 2rL+πr²", err_px < allowed_px,
          f"raster={float(mask.sum()) / scale / scale:.4f}  expect={expect:.4f}  "
          f"偏差={err_px / expect_px * 100:.2f}%（允许 {allowed_px / expect_px * 100:.2f}% 边界偏差）")

    # 2) 折线：与「中心线密铺圆盘」这一独立定义对比
    strokes = [([(3.0, 3.0), (14.0, 3.0), (20.0, 9.0), (26.0, 20.0)], 0.6)]
    d2, _ = build_outline(strokes, vb)
    mask2, _ = rasterize(flatten_path(d2, 64), vb, 256)
    score = iou(mask2, rasterize_skeleton(strokes, vb, 256))
    check("折线 vs 圆盘参照 IoU ≥ 0.97", score >= 0.97, f"IoU={score:.4f}")

    # 3) 所有子路径必须同向，nonzero 填充才等于并集
    signs = set()
    for poly in flatten_path(d2, 64):
        total = 0.0
        for i in range(len(poly)):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % len(poly)]
            total += x1 * y2 - x2 * y1
        signs.add(1 if total > 0 else -1)
    check("所有轮廓同向", len(signs) == 1, f"方向集合={signs}（轮廓数={len(flatten_path(d2, 64))}）")

    # 4) 退化：零长线段应得到一个圆，面积 πr²（同样放行一像素边界偏差）
    r4 = 0.75
    d4, _ = build_outline([([(10.0, 4.0), (10.0, 4.0)], r4)], vb)
    mask4, scale4 = rasterize(flatten_path(d4, 64), vb, 1024)
    expect4 = math.pi * r4 * r4
    expect4_px = expect4 * scale4 * scale4
    err4_px = abs(float(mask4.sum()) - expect4_px)
    allowed4_px = (2 * math.pi * r4) * scale4
    check("零长线段 → 圆，面积 πr²", err4_px < allowed4_px,
          f"raster={float(mask4.sum()) / scale4 / scale4:.4f}  expect={expect4:.4f}  "
          f"偏差={err4_px / expect4_px * 100:.2f}%（允许 {allowed4_px / expect4_px * 100:.2f}%）")

    print("自检结果   : " + ("全部通过" if not failures else f"{len(failures)} 项失败"))
    return 1 if failures else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="甲骨文骨架 → 可填充轮廓")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--precision", type=int, default=3, help="坐标小数位")
    parser.add_argument("--check", action="store_true", help="光栅化对比骨架，报告 IoU")
    parser.add_argument("--check-size", type=int, default=256)
    parser.add_argument("--selftest", action="store_true", help="跑几何自检后退出")
    parser.add_argument("--preview", type=int, default=0, help="输出前 N 个对照 PNG 到 tmp/")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    repo_root: Path = args.repo_root.resolve()
    src_dir = repo_root / "glyphs" / "oracle"
    out_dir = src_dir / "outline"
    prov_path = repo_root / "glyphs" / "provenance" / "oracle.jsonl"

    with (src_dir / "index.csv").open("r", encoding="utf-8", newline="") as handle:
        index = {row["glyph_id"]: row for row in csv.DictReader(handle)}

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records = []
    expanded_viewbox = []
    scores = []
    previews = []

    for glyph_id in sorted(index, key=int):
        row = index[glyph_id]
        # 轮廓层是 JGW 参数化矢量的派生件：它靠骨架的 polyline 结构生成可填充轮廓。
        # 同层里别的来源（汉典拓片摹本）没有这套结构，跳过。
        if not (row.get("char_form") or "").strip():
            continue
        src = src_dir / row["file"]
        viewbox, strokes = parse_skeleton(src)
        d, (x0, y0, x1, y1) = build_outline(strokes, viewbox, args.precision)

        vx, vy, vw, vh = viewbox
        if x0 < vx - 1e-9 or y0 < vy - 1e-9 or x1 > vx + vw + 1e-9 or y1 > vy + vh + 1e-9:
            viewbox = [min(vx, x0), min(vy, y0),
                       max(vx + vw, x1) - min(vx, x0), max(vy + vh, y1) - min(vy, y0)]
            expanded_viewbox.append(glyph_id)

        svg_text = render_svg(viewbox, d)
        dest = out_dir / row["file"]

        if args.check:
            polys = flatten_path(d)
            outline_mask, _ = rasterize(polys, viewbox, args.check_size)
            skeleton_mask = rasterize_skeleton(strokes, viewbox, args.check_size)
            score = iou(outline_mask, skeleton_mask)
            scores.append((score, glyph_id))
            if args.preview and len(previews) < args.preview:
                previews.append((glyph_id, row["modern_char"], outline_mask, skeleton_mask))

        if not args.dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)
            dest.write_text(svg_text, encoding="utf-8", newline="")
        dest_sha = hashlib.sha256(svg_text.encode("utf-8")).hexdigest()

        record = {
            "path": f"glyphs/oracle/outline/{row['file']}",
            "sha256": dest_sha,
            "script": "oracle",
            "layer": "outline",
            "glyph_id": int(glyph_id),
            "modern_char": row["modern_char"],
            "unicode": row["unicode"],
            "derived_from": f"glyphs/oracle/{row['file']}",
            "derived_from_sha256": row["sha256"],
            "transform": ("stroke-to-outline: 每个描边路径替换为其描边区域"
                          "（round cap/join）构成的显式填充轮廓；viewBox 与骨架一致"),
            "tool": "src/outline_oracle.py",
            "source_dataset": "Oracle Bone Glyphs: Parametric Vector Dataset (v0.3)",
            "source_doi": "10.5281/zenodo.22467946",
            "source_record_url": "https://zenodo.org/records/22467946",
            "source_artifact_url": (
                "https://zenodo.org/api/records/22467946/files/"
                "aylqs2025/oracle-bone-jgw-1203-v0.3.zip/content"
            ),
            "source_artifact_md5": "7764c7f5b0feb8f0052c36233ddf8d4b",
            "license": "CC-BY-4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "attribution": row.get("attribution", "") or (
                "Li, Qing-sheng & Bian, Yu-lin (2026), "
                "'Oracle Bone Glyphs: Parametric Vector Dataset (v0.3)', "
                "doi:10.5281/zenodo.22467946"),
            "generated_at": generated_at,
        }
        records.append(record)

    if not args.dry_run:
        kept, total = merge_provenance(prov_path, records, "outline")
        print(f"provenance.jsonl: 保留其他记录 {kept} 条，写入后共 {total} 条")

    print(f"轮廓文件   : {len(records)} 个 -> glyphs/oracle/outline/<glyph_id>.svg")
    print(f"扩过 viewBox: {len(expanded_viewbox)} 个"
          + (f" {expanded_viewbox[:8]}" if expanded_viewbox else ""))

    if scores:
        scores.sort()
        values = [s for s, _ in scores]
        below = [(s, g) for s, g in scores if s < 0.90]
        print(f"骨架/轮廓 IoU: min={values[0]:.4f} median={values[len(values)//2]:.4f} "
              f"mean={sum(values)/len(values):.4f} max={values[-1]:.4f}")
        print(f"低于 0.90  : {len(below)} 个" + (f" 最差 {below[:5]}" if below else ""))

    if previews:
        import numpy as np
        from PIL import Image, ImageDraw

        tile = args.check_size
        sheet = Image.new("RGB", (tile * len(previews), tile + 18), "white")
        draw = ImageDraw.Draw(sheet)
        draw.text((4, 4), "红=仅轮廓  蓝=仅描边  黑=两者重合（几何一致的判据）", fill="black")
        for i, (glyph_id, char, outline_mask, skeleton_mask) in enumerate(previews):
            rgb = np.full(outline_mask.shape + (3,), 255, dtype=np.uint8)
            rgb[outline_mask & ~skeleton_mask] = (220, 30, 30)
            rgb[skeleton_mask & ~outline_mask] = (30, 90, 220)
            rgb[outline_mask & skeleton_mask] = (40, 40, 40)
            sheet.paste(Image.fromarray(rgb), (i * tile, 18))
            draw.text((i * tile + tile - 46, tile + 4), f"{glyph_id} {char}", fill="black")
        preview_path = repo_root / "tmp" / "outline-preview.png"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(preview_path)
        print(f"对照图     : {preview_path}")

    print("dry-run：未写入任何文件" if args.dry_run else "完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
