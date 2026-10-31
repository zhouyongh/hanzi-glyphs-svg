#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拓片件反转成标准字形（黑笔画、透明底），逐件质检；不合格的保留拓片原样。

**问题**：小學堂的拓片位图是「石面黑、刻痕白」，描摹器照着描，得到的
是一块黑板 + 白字洞——在页面上就是「黑底白字」，不是标准字形。

**做法**（全矢量，不栅格化，输出即源件的洞轮廓）：
1. 找「板」——拓片里的石面是这样一整块。**两档**：
   - **严格档**：实心度 ≥ 0.75、面积 ≥ 画布 65%、包围盒覆盖画布宽高各 80%；
   - **放宽档**：实心度 ≥ 0.50、面积 ≥ 画布 30%、包围盒覆盖 ≥ 65%
     ——石面被啃缺边缘时严格档会漏（实测 bronze/0007、0008：实心度只有
     0.76/0.63、面积只占画布 53%/48%）。放宽档只是**候选**；
2. 板上被包住的轮廓 = 「洞」= 拓片里白刻的笔画（外加石面噪点）；
3. 去噪：两条规则——面积小**且**不细长的是石面麻点；面积不到本件
   **最大洞 5%** 的也是麻点（只靠绝对阈值清不干净大字里的麻点）；
4. 逐件质检：笔画太少、太碎、不成形 → **不出反转件**，这一件保留拓片原样；
5. **「黑场」闸门**（分清拓片与**正片**的关键，源件级）：拓片与正片在矢量结构上
   分不开——都是「一条大轮廓 + 若干洞」。分得开的是**那条大轮廓是什么**：
   拓片的是**石面**（铺满画面、轮廓是实的、白刻笔画只占小头）；
   正片的是**字的笔画团**（不铺满画面、轮廓不实、里面是字的**空腔**）。
   所以量三个量——石面占画布比、石面轮廓实心度、白刻笔画占石面面积——
   三条同时成立才算拓片，否则这一件保留原样（源件多半是摹本，
   它本来就是标准字形）。

**质检指标**（五条，任一不过就保留拓片原样）：

============  ==============================================  ==========
指标          含义                                          判据
============  ==============================================  ==========
``ink``       笔画占画布比：太少=没字，太多=残留黑块          0.004 ~ 0.35
``parts``     连通块数：太碎=没成形                          ≤ 30
``body``      最大块占画布比：主体得有点分量                  ≥ 0.010
``fill``      墨迹外接框填充率：墨迹铺得太散=不成字           ≥ 0.13
``solid``     最大块实心度：太高=一整块实心，不是字            < 0.72
``chunk``     实心方块占墨迹比：太高=反转出来是字腔不是刻痕     ≤ 0.30
============  ==============================================  ==========

**「黑场」闸门**（在源件上量，三条缺一不可）：

===================  ==============================================  ==========
指标                  含义                                          判据
===================  ==============================================  ==========
``slab_cover``      石面占画布比：正片的笔画团铺不满画面            ≥ 0.70
``slab_solid``      石面轮廓实心度：正片的笔画团不是实心矩形        ≥ 0.75
``hole_sum``        白刻笔画占石面面积：正片里那是字的空腔          ≤ 0.30
===================  ==============================================  ==========

``fill`` 是分「成字」与「散点」最有效的那个指标：字是**在一方天地里
排布笔画**，填充率高；麻点是**铺满整块画布**，外接框大得离谱，填充率
就低（实测：成字的 ≥ 0.14，散点的 ≤ 0.13）。

``solid`` 挡的是另一类错：字形**本身**是个方框（「口」「日」「田」「目」这类
笔画很粗的字），或拓片的石面是个方框——这时「板」认成了字的外框，
反转出来是一整块实心，不是字（实测好件最高 0.710、坏件最低 0.722）。

**为什么不用「最大块占笔画总量」**：它对**多部件对称字**有偏——
「亞」「銜」这类字由几块大小相当的笔画组成，最大块只占两成多，
按这条判会误拒（实测误拒了 9845、13397 这类字）。它只作指标记录。

**为什么全矢量**：反转件直接由源件的洞轮廓组成，不重新描摹，
「输出件的每条轮廓都来自源件」这条性质可以用机检证明，边缘也不被重采样。

用法::

    # 体检：哪些件是拓片型、反转后过不过质检（不写文件）
    python src/invert_rubbing_glyphs.py --repo-root . --mode scan --layer bronze

    # 生成反转层（glyphs/<层>/inverted/）+ 逐件报告
    python src/invert_rubbing_glyphs.py --repo-root . --mode convert --layer bronze

    # 复核已生成的反转层
    python src/invert_rubbing_glyphs.py --repo-root . --mode check --layer bronze
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from svg_path import (bbox, parse_svg_paths, point_in_polygon,  # noqa: E402
                      signed_area)
from trace_xiaoxuetang_glyphs import loops_to_path, rasterize_loops, render_svg  # noqa: E402

# ---------------------------------------------------------------- 判据（可调）
SLAB_SOLID_MIN = 0.75      # 轮廓自身：面积/包围盒（实心板接近 1，粗笔画 0.4 左右）
SLAB_COVER_MIN = 0.65      # 轮廓面积/画布面积（板要铺满大部分画布）
SLAB_BBOX_MIN = 0.80       # 轮廓包围盒覆盖画布宽、高的比例

# **放宽档**：石面被啃缺边缘时，严格档会漏掉（实测 bronze/0007、0008：
# 石面实心度只有 0.63/0.76、面积只占画布 48%/53%）。放宽档只是**候选**——
# 还要过「黑是底」闸门（GROUND_COVER_MIN）才算拓片。
RELAX_SOLID_MIN = 0.50     # 轮廓自身：面积/包围盒
RELAX_COVER_MIN = 0.30     # 轮廓面积/画布面积
RELAX_BBOX_MIN = 0.65      # 轮廓包围盒覆盖画布宽、高的比例

# **「板是实心石面」闸门**（把「器物图」挡在外面）。
#
# 小學堂的金文库里还有一类图：**整件器物的拓图**——圆形器盖、方框、饰带、
# 三角纹装饰（实测 bronze/10801 是三角纹面板、2120 是圆盖图、chuanchao/0934 是圈）。
# 它们的「板」是**器形轮廓**不是石面，板里最大的白区是器物的空白，
# 反转出来是三角形、圆环这类**根本不是字**的图形。
#
# 拓片的板是**实心石面**，里面的白区都是细刻痕——
# 所以「板内最大的白区」不能超过板自身面积的这一半。
# 门槛 0.50 是实测定的（探索期 4,651 件候选的交叉表）：这条线挡下 86 件正片类，
# 也挡下 15~17 件器物图；代价是 21 件真拓片（保守损失，保留拓片原样）。
#
# 分母用板的 shoelace 面积（轮廓面积）。自交轮廓的 shoelace 面积会算小，
# 那样只会让这个比值偏大、闸门偏严——方向是保守的，可以接受。
SLAB_HOLE_MAX = 0.50

# **「黑场」闸门**（源件级，来源无关）——**本层最关键的一条**。
#
# 拓片与正片在**矢量结构上分不开**：两者都是「一条大轮廓 + 若干洞」。
# 分得开的是「那条大轮廓**是什么**」：
# - **拓片**：大轮廓是**石面**——铺满画面、轮廓本身是实的、白刻笔画只占小头；
# - **正片**：大轮廓是**字的笔画团**——不铺满画面、轮廓不实、
#   里面的白区是字的**空腔**、占掉一大半。
#
# 三条一起量（都在源件上算，与来源无关）：
#   石面占画布比 ≥ 0.70 · 石面轮廓实心度 ≥ 0.75 · 白刻笔画占石面面积 ≤ 0.30
#
# 实测（143 件目检标签：115 件反转变体像字、28 件不像）：三条同时成立时，
# 28 件错件**一件都漏不进来**；代价是 115 件好件只收 42 件——
# 收不进来的那些，源件本来就是**摹本**（白底黑字），它已经是标准字形，
# 保留原样即可（这正是「效果不好的保留拓片原效果」这条要求）。
#
# 门槛的来历（目检标注集上的网格搜索，见 tmp/eval_field4.py）：
#   石面占画布 0.70 + 石面实心度 0.75 + 白刻占比 0.30 → 漏放 0、误挡 73
#   放宽白刻占比到 0.45 → 开始漏放正片（實測 4 件）
FIELD_COVER_MIN = 0.70
FIELD_SOLID_MIN = 0.75
FIELD_HOLE_MAX = 0.30

# **「是不是字」闸门**（分清拓片与**正片**的关键）——量在**反转变体**上。
#
# 拓片与正片在**矢量结构上分不开**：两者都是「一条大轮廓 + 若干洞」。
# 拓片的大轮廓是石面（洞是白刻笔画），正片的大轮廓是字的轮廓（洞是字的空腔）。
#
# 早先的「黑是底」闸门量的是「墨迹总外接框占 viewBox 的比例」，**实测不成立**：
# - 对**小學堂**描摹件，这个量**恒为 ~0.99**（描摹件的 viewBox 就是墨迹外接框），
#   对**漢典**件**系统性偏低**（石面内缩，viewBox 是 0 0 400 400），
#   于是它实际上只放行小學堂件——漢典批里约 900 件真拓片被误挡在层外；
# - 反过来它对**正片**一点保护力都没有：1,765 件已转换件里有 41 件是**错件**
#   （小學堂隸書/甲骨批里混着「黑字白底」的件），它们照样过关。
#
# 现在改量**反转出来的东西**：正片反转出来是字的**空腔**——一块块**实心方块**；
# 拓片反转出来是**刻痕**——细长的笔画。
# 所以量「实心方块（块面积/块自身包围盒 ≥ 0.80）占全部墨迹的比例」。
# 门槛 0.30：实测 1,739 件拓片类里 99% 是 0，最高的几件也在 0.30 以下，
# 而正片类（1,755 件里挑出的 41 件错件）是 0.7~1.0。
#
# **这条现在是兜底**：主判据是上面的「黑场闸门」，它把正片挡在层外，
# 根本走不到这里。保留它是为了将来有新数据时还有一道网。
CHUNK_SOLID_MIN = 0.80
CHUNK_RATIO_MAX = 0.30

SPECK_AREA_MAX = 0.0006    # 洞面积占画布比：小于此视为「小块」
SPECK_ELONG_MIN = 2.0      # 细长比：小于此（小块且不细长）= 麻点；细长 = 笔画断段
SPECK_REL_MIN = 0.05       # 相对显著性：面积不到本件最大洞的这个比例 = 麻点
SPECK_REL_ABS_MAX = 0.02   # 相对阈值的上限（占画布比）：最大洞异常大时不至于把字抹掉

QC_MIN_INK = 0.004         # 反转后笔画占比下限（太少 = 没字）
QC_MAX_INK = 0.35          # 上限（太多 = 残留黑块）
QC_MAX_PARTS = 30          # 连通块数上限（太碎 = 没成形）
QC_MIN_BODY = 0.010        # 最大块占画布下限（主体得有点分量）
QC_MIN_FILL = 0.13         # 墨迹外接框填充率下限（不成字 = 墨迹铺得太散）
QC_MAX_BLOB_SOLID = 0.72   # 最大块实心度上限（太高 = 一整块实心，不是字）
QC_MIN_BLOB_AREA = 0.05    # 且最大块占画布这么多才判「实心块」

QC_SIZE = 200              # 质检栅格尺寸

# **拓片只可能出现在摹本层**。
#
# 甲骨、金文、隶书、傳抄古文字——这四层的字形是刻在石头、甲骨、青铜器、
# 碑上的字的**摹本**，上游给的位图是「石面黑、刻痕白」，反转有意义。
#
# 现代书体六层是从 OFL 字体提取的**轮廓**，篆书层是漢典的小篆矢量实例，
# **都不是拓片**。硬跑一遍会出真错：黑体·港里有几个带方框的字（U+211BB 等），
# 那个方框会被当成「石面板」，框里的整块空白被当成「刻痕」——
# 反转出来是「黑底反白的字」，看着像字，其实是把字形本身画反了。
# 这种误判几何上分不开（真拓片里也有「石面 + 大块白刻区」这种结构），
# 分得开的是**材料**：是不是摹本。故按层划定范围。
#
# **楚文字层不收**：该层 11,039 件全是漢典矢量件（零描摹件），实测无一件拓片。
# **秦系简牘层不收**：该层是竹简——简上墨书黑字，本来就是正片；
# 145 件「有板形」的候选逐件目检**全是正片**，无一例外。
# 拓片只可能出现在**小學堂的拓片位图批次**（甲骨/金文/隸書/傳抄）。
RUBBING_LAYERS = ("oracle", "bronze", "clerical", "chuanchao")


# ---------------------------------------------------------------- 几何工具
def contour_stats(contour, viewbox):
    """一条轮廓的面积、包围盒、实心度、覆盖率。"""
    x0, y0, w, h = viewbox
    canvas = w * h
    a = signed_area(contour)
    bx0, by0, bx1, by1 = bbox(contour)
    bw = max(bx1 - bx0, 1e-9)
    bh = max(by1 - by0, 1e-9)
    return {
        "area": a,
        "abs_area": abs(a),
        "bbox": (bx0, by0, bx1, by1),
        "solid": abs(a) / (bw * bh),
        "cover": abs(a) / canvas,
        "cover_w": bw / w,
        "cover_h": bh / h,
        "elong": max(bw, bh) / min(bw, bh),
    }


def find_slabs(stats, viewbox):
    """板（严格档）：实心、铺满、覆盖画布——拓片里的石面。"""
    out = []
    for i, st in enumerate(stats):
        if (st["solid"] >= SLAB_SOLID_MIN and st["cover"] >= SLAB_COVER_MIN
                and st["cover_w"] >= SLAB_BBOX_MIN and st["cover_h"] >= SLAB_BBOX_MIN):
            out.append(i)
    return out


def relaxed_slab(stats):
    """板（放宽档）：石面被啃缺边缘时，严格档认不出，但确实是拓片。

    只作**候选**——用不用它，要过「黑是底」闸门（GROUND_COVER_MIN）才算数。
    取面积最大的那条合候选。
    """
    best = None
    for i, st in enumerate(stats):
        if st["abs_area"] <= 0:
            continue
        if (st["solid"] >= RELAX_SOLID_MIN and st["cover"] >= RELAX_COVER_MIN
                and st["cover_w"] >= RELAX_BBOX_MIN and st["cover_h"] >= RELAX_BBOX_MIN):
            if best is None or st["abs_area"] > stats[best]["abs_area"]:
                best = i
    return best


def ground_cover(contours, viewbox):
    """墨迹总外接框占 viewBox 的比例（纯几何，不栅格化）。

    拓片的石面铺满整幅拓片 → 接近 1；正片的笔画散在画面中间 → 明显小。
    门槛 GROUND_COVER_MIN，见文件头的说明。
    """
    x0, y0, w, h = viewbox
    if not contours or w <= 0 or h <= 0:
        return 0.0
    boxes = [bbox(c) for c in contours]
    bx0 = min(b[0] for b in boxes)
    by0 = min(b[1] for b in boxes)
    bx1 = max(b[2] for b in boxes)
    by1 = max(b[3] for b in boxes)
    return (bx1 - bx0) * (by1 - by0) / (w * h)


def find_holes(contours, stats, slabs):
    """洞：几何上被板包住的轮廓（拓片里白刻的笔画 + 石面麻点）。"""
    holes = []
    for i, st in enumerate(stats):
        if i in slabs:
            continue
        for s in slabs:
            if stats[s]["abs_area"] * 1.02 < st["abs_area"]:
                continue
            if point_in_polygon(contours[i][0], contours[s]):
                holes.append(i)
                break
    return holes


def split_noise(holes, stats, viewbox):
    """分出「笔画」与「麻点」，两条规则缺一不可。

    - **绝对下限**：面积小于画布 0.06% **且**不细长的，是石面麻点。
      绝对阈值只认「小」，不认「相对这个字有多大」。
    - **相对显著性**：面积不到本件**最大洞** 5% 的，也是麻点。
      同一件里相对最小的那些几乎全是石面麻点；只靠绝对阈值，
      「大字里的麻点」清不干净（它们的面积本来就大），
      「小字里的麻点」又可能误伤笔画。

    两条一起用，效果是：字形保留完整，麻点基本清空（实测见
    ``tmp/denoise_compare.png`` 与 ``tmp/denoise_hi.png``）。
    """
    x0, y0, w, h = viewbox
    canvas = w * h
    a1 = max((stats[i]["abs_area"] for i in holes), default=0.0)
    # 相对阈值封顶：万一最大洞是块很大的空白（石面崩了一块），
    # 按比例一刀切会把字抹光——所以阈值不超过画布的 2%。
    rel_abs = min(a1 * SPECK_REL_MIN, SPECK_REL_ABS_MAX * canvas)
    keep, drop = [], []
    for i in holes:
        st = stats[i]
        area = st["abs_area"] / canvas
        small_round = area < SPECK_AREA_MAX and st["elong"] < SPECK_ELONG_MIN
        insignificant = a1 > 0 and st["abs_area"] < rel_abs
        if small_round or insignificant:
            drop.append(i)
        else:
            keep.append(i)
    return keep, drop


def rasterize(contours, viewbox, size=QC_SIZE):
    """轮廓 → 掩膜（nonzero 填充，与仓库其余各层同一口径）。"""
    x0, y0, w, h = viewbox
    if not contours or w <= 0 or h <= 0:
        return np.zeros((size, size), dtype=bool)
    scale = size / max(w, h)
    scaled = [[(px * scale, py * scale) for px, py in lp] for lp in contours]
    return rasterize_loops(scaled, size, size, offset=(-x0 * scale, -y0 * scale))


def components(mask):
    """连通块：行游程 + 并查集。返回 [(像素数, 包围盒)]，按面积降序。"""
    h, w = mask.shape
    parent: list[int] = []

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> int:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
        return min(ra, rb)

    prev: list[tuple[int, int, int]] = []
    runs: list[tuple[int, int, int, int]] = []          # (label, y, x0, x1)
    for y in range(h):
        row = mask[y]
        cur: list[tuple[int, int, int]] = []
        x = 0
        while x < w:
            if row[x]:
                x0 = x
                while x < w and row[x]:
                    x += 1
                label = None
                for px0, px1, plabel in prev:
                    if px0 <= x - 1 and x0 <= px1:
                        if label is None:
                            label = plabel
                        else:
                            label = union(label, plabel)
                if label is None:
                    label = len(parent)
                    parent.append(label)
                cur.append((x0, x - 1, label))
            else:
                x += 1
        for rx0, rx1, rlabel in cur:
            runs.append((rlabel, y, rx0, rx1))
        prev = cur

    agg: dict[int, list[int]] = {}
    for rlabel, y, rx0, rx1 in runs:
        root = find(rlabel)
        n = rx1 - rx0 + 1
        box = agg.get(root)
        if box is None:
            agg[root] = [n, rx0, rx1, y, y]
        else:
            box[0] += n
            if rx0 < box[1]:
                box[1] = rx0
            if rx1 > box[2]:
                box[2] = rx1
            if y < box[3]:
                box[3] = y
            if y > box[4]:
                box[4] = y
    out = [(v[0], (v[1], v[3], v[2] + 1, v[4] + 1)) for v in agg.values()]
    out.sort(key=lambda t: -t[0])
    return out


def shape_metrics(mask):
    """由掩膜算质检指标。

    返回 ``ink``（笔画占画布比）、``parts``（连通块数）、
    ``largest``（最大块占笔画总量）、``body``（最大块占画布）、
    ``top3``（前三大块占笔画总量）、``fill``（墨迹外接框的填充率）。
    """
    h, w = mask.shape
    canvas = h * w
    comps = components(mask)
    total = sum(c[0] for c in comps)
    if not comps or not total:
        return {"ink": 0.0, "parts": 0, "largest": 0.0, "body": 0.0,
                "top3": 0.0, "fill": 0.0}
    biggest = comps[0][0]
    top3 = sum(c[0] for c in comps[:3])
    # **填充率**：墨迹占自己外接框的比例。字是「在一方天地里排布笔画」，
    # 填充率高；散落的麻点是「铺满整块画布」，外接框大得离谱，填充率就低。
    # 这是分「成字」与「散点」最有效的一个指标（实测：成字的 ≥ 0.14，
    # 散点的 ≤ 0.13）。
    ys, xs = np.nonzero(mask)
    if len(xs):
        bw = int(xs.max() - xs.min() + 1)
        bh = int(ys.max() - ys.min() + 1)
        fill = total / (bw * bh)
    else:
        fill = 0.0
    # **最大块的实心度**：块面积 / 块自身包围盒。字是笔画，细长、分散，
    # 实心度低；**实心块**（字形本身是个方框、或石面上一大块空白）实心度高。
    # 这是判「反转出来的是不是一个字」的另一条独立信号。
    # **实心方块占比**：块的实心度（面积/自身包围盒）≥ CHUNK_SOLID_MIN 的块，
    # 占全部墨迹多少。正片反转出来是字的空腔（一块块方块），占比接近 1；
    # 拓片反转出来是刻痕（细长笔画），占比几乎为 0。
    chunk = 0
    for n, (bx0, by0, bx1, by1) in comps:
        bw = max(bx1 - bx0, 1)
        bh = max(by1 - by0, 1)
        if n / (bw * bh) >= CHUNK_SOLID_MIN:
            chunk += n
    chunk_ratio = chunk / total if total else 0.0
    box = comps[0][1]
    cbw = max(box[2] - box[0], 1)
    cbh = max(box[3] - box[1], 1)
    solid = biggest / (cbw * cbh)
    return {
        "ink": total / canvas,
        "parts": len(comps),
        "largest": biggest / total,
        "body": biggest / canvas,
        "top3": top3 / total,
        "fill": fill,
        "solid": solid,
        "chunk": chunk_ratio,
    }


# ---------------------------------------------------------------- 单件处理
def analyze(path: Path):
    """一件的判定与指标。"""
    viewbox, contours = parse_svg_paths(path)
    x0, y0, w, h = viewbox
    stats = [contour_stats(c, viewbox) for c in contours]
    slabs = find_slabs(stats, viewbox)
    res = {
        "path": path,
        "viewbox": viewbox,
        "n_contours": len(contours),
        "n_slab": len(slabs),
        "n_hole": 0,
        "n_keep": 0,
        "n_drop": 0,
        "decision": "not-rubbing",
        "reason": "",
        "ink": 0.0,
        "parts": 0,
        "largest": 0.0,
        "body": 0.0,
        "top3": 0.0,
        "fill": 0.0,
        "solid": 0.0,
        "chunk": 0.0,
        "ground_cover": 0.0,
        "slab_hole": 0.0,
        "slab_cover": 0.0,
        "slab_solid": 0.0,
        "hole_sum": 0.0,
        "slab_kind": "",
    }
    if not slabs:
        cand = relaxed_slab(stats)
        if cand is None:
            res["reason"] = "无板轮廓（不是拓片型）"
            return res, None
        slabs = [cand]
        res["slab_kind"] = "放宽"
    else:
        res["slab_kind"] = "严格"
    # **只作记录，不作判据**：墨迹总外接框占 viewBox 的比例。
    # 它对小學堂恒为 ~0.99、对漢典系统性偏低（石面内缩），量不到「黑是底」，
    # 当判据会误挡漢典批的真拓片（详见文件头 CHUNK_SOLID_MIN 的说明）。
    res["ground_cover"] = ground_cover(contours, viewbox)
    holes = find_holes(contours, stats, slabs)
    res["n_hole"] = len(holes)
    if not holes:
        res["decision"] = "no-hole"
        res["reason"] = "板内没有洞（拓片上没有白刻笔画）"
        return res, None
    # **「黑场」闸门**：那条大轮廓是**石面**（拓片）还是**笔画团**（正片）。
    # 三条同时成立才算拓片，否则保留原样（详见文件头 FIELD_* 的说明）。
    slab_i = max(slabs, key=lambda s: stats[s]["abs_area"])
    slab_area = stats[slab_i]["abs_area"]
    hole_area_sum = sum(stats[i]["abs_area"] for i in holes)
    res["slab_cover"] = stats[slab_i]["cover"]
    res["slab_solid"] = stats[slab_i]["solid"]
    res["hole_sum"] = hole_area_sum / slab_area if slab_area > 0 else 0.0
    if (res["slab_cover"] < FIELD_COVER_MIN
            or res["slab_solid"] < FIELD_SOLID_MIN
            or res["hole_sum"] > FIELD_HOLE_MAX):
        res["decision"] = "not-field"
        res["reason"] = (f"不是黑场拓片（石面占画布 {res['slab_cover']:.2f}、"
                         f"实心度 {res['slab_solid']:.2f}、白刻占石面 "
                         f"{res['hole_sum']:.2f}），源件多半是摹本，保留原样")
        return res, None
    # **「板是实心石面」闸门**：板内最大的白区不能过半。
    # 拓片的板是实心石面（白区都是细刻痕）；器物图的板是圈/框，
    # 里面最大的白区是器物的空白——反转出来不是字。
    biggest_hole = max(stats[i]["abs_area"] for i in holes)
    res["slab_hole"] = biggest_hole / slab_area if slab_area > 0 else 0.0
    if res["slab_hole"] >= SLAB_HOLE_MAX:
        res["decision"] = "not-solid"
        res["reason"] = (f"板不是实心石面（板内最大的白区占板面积 "
                         f"{res['slab_hole']:.3f}，像器物图不是拓片），保留原样")
        return res, None
    keep, drop = split_noise(holes, stats, viewbox)
    res["n_keep"] = len(keep)
    res["n_drop"] = len(drop)
    if not keep:
        res["decision"] = "all-noise"
        res["reason"] = "洞全是噪点"
        return res, None
    kept_contours = [contours[i] for i in keep]
    mask = rasterize(kept_contours, viewbox)
    m = shape_metrics(mask)
    res.update(m)
    # 质检：成形了就出反转件，没成形就保留拓片原样
    if m["ink"] < QC_MIN_INK:
        res["decision"] = "qc-fail"
        res["reason"] = f"笔画太少（占比 {m['ink']:.4f}）"
    elif m["ink"] > QC_MAX_INK:
        res["decision"] = "qc-fail"
        res["reason"] = f"笔画过密（占比 {m['ink']:.3f}，像残留黑块）"
    elif m["parts"] > QC_MAX_PARTS:
        res["decision"] = "qc-fail"
        res["reason"] = f"太碎（{m['parts']} 块）"
    elif m["body"] < QC_MIN_BODY:
        res["decision"] = "qc-fail"
        res["reason"] = (f"主体太小（最大块只占画布 {m['body']:.3f}，"
                         f"像残点）")
    elif m["fill"] < QC_MIN_FILL:
        res["decision"] = "qc-fail"
        res["reason"] = (f"不成字（墨迹铺得太散，外接框填充率只有 "
                         f"{m['fill']:.3f}）")
    elif (m["solid"] >= QC_MAX_BLOB_SOLID and m["body"] >= QC_MIN_BLOB_AREA):
        res["decision"] = "qc-fail"
        res["reason"] = (f"实心块（最大块实心度 {m['solid']:.2f}，"
                         f"反转出来是一整块，不是字）")
    elif m["chunk"] > CHUNK_RATIO_MAX:
        # **「是不是字」闸门**：反转出来是一块块实心方块——那是**正片**的
        # 字腔（黑字白底反过来的空腔），不是拓片上的白刻笔画。
        res["decision"] = "not-glyph"
        res["reason"] = (f"反转出来是一堆实心方块（占墨迹 {m['chunk']:.2f}），"
                         f"是字腔不是刻痕，保留原样")
    else:
        res["decision"] = "converted"
        res["reason"] = (f"板 {len(slabs)} 块，洞 {len(holes)} 个"
                         f"（去噪 {len(drop)}），笔画占比 {m['ink']:.3f}，"
                         f"{m['parts']} 块，最大块占 {m['largest']:.2f}"
                         f"/画布 {m['body']:.3f}，填充率 {m['fill']:.3f}")
    return res, kept_contours


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def layers_of(repo_root: Path) -> list[str]:
    glyphs = repo_root / "glyphs"
    out = []
    for d in sorted(glyphs.iterdir()):
        if d.is_dir() and (d / "index.csv").is_file():
            out.append(d.name)
    return out


# 复核时要重跑算法的判定（其余的「不是拓片型」不需要重跑）。
CHECKED_DECISIONS = ("converted", "qc-fail", "no-hole", "not-solid",
                     "not-field", "not-glyph", "all-noise")

REPORT_FIELDS = ["file", "decision", "reason", "slab_kind", "ground_cover",
                 "slab_hole", "slab_cover", "slab_solid", "hole_sum",
                 "contours", "slabs", "holes", "kept", "dropped",
                 "ink_ratio", "parts", "largest_share", "body_share",
                 "top3_share", "fill_ratio", "blob_solid", "chunk_ratio"]


# 反转变体的出处记账（与描摹件同一套规矩：说清从哪来、怎么变的、用什么变的）
TRANSFORM_DESC = (
    "拓片反转（黑底白字 → 黑笔画透明底）：全矢量取洞——"
    "先找石面板轮廓（严格档：实心度≥0.75、面积≥画布65%、包围盒覆盖画布宽高各80%；"
    "石面被啃缺边缘时用放宽档：实心度≥0.50、面积≥画布30%、包围盒覆盖≥65%），"
    "过「黑场」闸门（石面占画布≥0.70、石面轮廓实心度≥0.75、"
    "白刻笔画占石面面积≤0.30——挡住黑字白底的摹本，那种件反转出来是字的空腔，"
    "不是刻痕）与「板是实心石面」闸门（板内最大的白区占板面积<0.50，排除器物图），"
    "然后取被板包住的洞轮廓，去掉面积小于画布0.06%且细长比小于2的麻点，"
    "其余洞轮廓按 nonzero 填充重绘；"
    "最后过「是不是字」兜底闸门（实心方块占墨迹比≤0.30）；viewBox 与源件一致"
)


def provenance_path(repo_root: Path, script: str) -> Path:
    return repo_root / "glyphs" / "provenance" / f"{script}.jsonl"


def read_provenance(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def write_provenance(path: Path, records: list[dict]) -> None:
    """写出 provenance（按 path 排序，键排序，与仓里既有格式一致）。"""
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")


def sync_provenance(repo_root: Path, script: str, rows: list[dict], out_subdir: str,
                    generated_at: str) -> tuple[int, list[str]]:
    """把反转变体的出处记录写进本层的 provenance（替换上一轮的同层记录）。

    反转变体是**派生变体**：它不是上游原件，所以不覆盖源件的记录，
    而是另起一条（``layer="inverted"``），记清派生自哪个文件、用的什么算法。
    源件的出处（作品、编号、页.行、URL、许可）原样继承——反转不改变来源。
    """
    prov = provenance_path(repo_root, script)
    records = read_provenance(prov)
    by_path = {str(r.get("path") or ""): r for r in records}
    keep = [r for r in records if str(r.get("layer") or "") != "inverted"]
    added, problems = 0, []
    for row in rows:
        if row["decision"] != "converted":
            continue
        file = row["file"]
        src_rel = f"glyphs/{script}/{file}"
        out_rel = f"glyphs/{script}/{out_subdir}/{file}"
        src = by_path.get(src_rel)
        if src is None:
            problems.append(f"{out_rel}：源件没有出处记录（{src_rel}）")
            continue
        out_file = repo_root / out_rel
        if not out_file.is_file():
            problems.append(f"{out_rel}：文件不存在")
            continue
        rec = dict(src)
        rec.update({
            "path": out_rel,
            "layer": "inverted",
            "derived_from": src_rel,
            "derived_from_sha256": str(src.get("sha256") or "").lower(),
            "sha256": sha256_file(out_file),
            "transform": TRANSFORM_DESC,
            "tool": "src/invert_rubbing_glyphs.py",
            "generated_at": generated_at,
            "modifications": "拓片黑底反转为标准字形（黑笔画、透明底）",
        })
        keep.append(rec)
        added += 1
    keep.sort(key=lambda r: str(r.get("path") or ""))
    write_provenance(prov, keep)
    return added, problems


def check_layer(repo_root: Path, script: str, out_subdir: str, report_name: str,
                recheck: bool) -> list[str]:
    """复核反转变体层：报告、目录、文件内容三者必须对得上。"""
    problems: list[str] = []
    report = repo_root / "glyphs" / script / report_name
    out_dir = repo_root / "glyphs" / script / out_subdir
    if not report.is_file():
        return [f"{script}：没有逐件报告 {report_name}"]
    rows = list(csv.DictReader(report.open(encoding="utf-8")))
    want = {r["file"] for r in rows if r["decision"] == "converted"}
    have = {p.name for p in out_dir.glob("*.svg")} if out_dir.is_dir() else set()
    for name in sorted(want - have):
        problems.append(f"{script}/{name}：报告说已转换，但没有反转件")
    for name in sorted(have - want):
        problems.append(f"{script}/{name}：有反转件，但报告里不是 converted")
    if not recheck:
        return problems
    # 重跑一遍算法：判定必须一致，且文件必须与当前算法跑出来的**逐字节相同**。
    for row in rows:
        if row["decision"] not in CHECKED_DECISIONS:
            continue
        src = repo_root / "glyphs" / script / row["file"]
        try:
            res, kept = analyze(src)
        except Exception as exc:                            # noqa: BLE001
            problems.append(f"{script}/{row['file']}：重跑失败 {type(exc).__name__}: {exc}")
            continue
        if res["decision"] != row["decision"]:
            problems.append(f"{script}/{row['file']}：判定变了（报告 "
                             f"{row['decision']} → 现在 {res['decision']}）")
            continue
        if row["decision"] != "converted":
            continue
        expect = render_svg(res["viewbox"], loops_to_path(kept))
        got = (out_dir / row["file"]).read_text(encoding="utf-8")
        if expect != got:
            problems.append(f"{script}/{row['file']}：反转件与当前算法跑出来的不一致")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="拓片件反转成标准字形")
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--layer", action="append", default=None,
                    help="要处理的层（可给多次；默认全部层）")
    ap.add_argument("--mode", choices=["scan", "convert", "check", "provenance"],
                    default="scan")
    ap.add_argument("--recheck", action="store_true",
                    help="复核时重跑一遍算法（判定是否一致、文件是否逐字节相同）")
    ap.add_argument("--out-subdir", default="inverted",
                    help="反转件放在层目录下的哪个子目录（默认 inverted）")
    ap.add_argument("--report-name", default="rubbing-invert.csv",
                    help="逐件报告的文件名（放在层目录下）")
    args = ap.parse_args(argv)

    repo_root = args.repo_root.resolve()
    asked = args.layer or list(RUBBING_LAYERS)
    layers = []
    for script in asked:
        if script in RUBBING_LAYERS:
            layers.append(script)
        else:
            print(f"跳过 {script}：不是摹本层（拓片只出现在 "
                  f"{'、'.join(RUBBING_LAYERS)}）")

    # 复核与出处记账都不跑算法的一轮，直接读报告与磁盘上的文件。
    if args.mode == "check":
        problems: list[str] = []
        for script in layers:
            if not (repo_root / "glyphs" / script).is_dir():
                continue
            problems += check_layer(repo_root, script, args.out_subdir,
                                    args.report_name, args.recheck)
        # 不在范围内的层里**不该有**反转变体：那些层不是摹本层，
        # 硬跑一遍会出「把字形本身画反」的错件（见 RUBBING_LAYERS）。
        for script in layers_of(repo_root):
            if script in RUBBING_LAYERS:
                continue
            stray = repo_root / "glyphs" / script / args.out_subdir
            if stray.is_dir() and any(stray.glob("*.svg")):
                problems.append(f"{script}/{args.out_subdir}/：不是摹本层，"
                                f"不该有反转变体")
        for item in problems[:50]:
            print("  !!", item)
        if len(problems) > 50:
            print(f"  ... 另有 {len(problems) - 50} 项")
        print(f"复核 {len(layers)} 层：问题 {len(problems)} 项")
        return 1 if problems else 0

    if args.mode == "provenance":
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        bad = 0
        # 层被移出范围后，上一轮留下的 `layer="inverted"` 记录指向的文件已经没了
        # （校验会报「文件不存在」）。这里先把它们清掉。
        for script in layers_of(repo_root):
            if script in RUBBING_LAYERS:
                continue
            prov = provenance_path(repo_root, script)
            if not prov.is_file():
                continue
            records = read_provenance(prov)
            keep = [r for r in records if str(r.get("layer") or "") != "inverted"]
            if len(keep) != len(records):
                write_provenance(prov, keep)
                print(f"{script:12} 清掉 {len(records) - len(keep)} 条过期的反转变体记录")
        for script in layers:
            report = repo_root / "glyphs" / script / args.report_name
            if not report.is_file():
                continue
            rows = list(csv.DictReader(report.open(encoding="utf-8")))
            added, problems = sync_provenance(repo_root, script, rows,
                                              args.out_subdir, generated_at)
            bad += len(problems)
            for item in problems[:20]:
                print("  !!", item)
            print(f"{script:12} 出处记录 +{added} 条")
        print(f"合计：问题 {bad} 项")
        return 1 if bad else 0

    total: dict[str, int] = {}
    rows: list[dict] = []

    for script in layers:
        layer_dir = repo_root / "glyphs" / script
        if not layer_dir.is_dir():
            continue
        out_dir = layer_dir / args.out_subdir
        report_path = layer_dir / args.report_name
        converted = 0
        layer_rows: list[dict] = []
        for svg in sorted(layer_dir.glob("*.svg")):
            try:
                res, kept = analyze(svg)
            except Exception as exc:                       # noqa: BLE001
                res = {"path": svg, "decision": "error",
                       "reason": f"{type(exc).__name__}: {exc}",
                       "n_contours": 0, "n_slab": 0, "n_hole": 0, "n_keep": 0,
                       "n_drop": 0, "ink": 0.0, "parts": 0, "largest": 0.0,
                       "body": 0.0, "top3": 0.0, "fill": 0.0, "solid": 0.0,
                       "chunk": 0.0,
                       "ground_cover": 0.0, "slab_hole": 0.0, "slab_kind": "",
                       "slab_cover": 0.0, "slab_solid": 0.0, "hole_sum": 0.0}
                kept = None
            total[res["decision"]] = total.get(res["decision"], 0) + 1
            if res["decision"] == "converted":
                converted += 1
            rows.append({
                "file": svg.name,
                "decision": res["decision"],
                "reason": res["reason"],
                "slab_kind": res.get("slab_kind", ""),
                "ground_cover": f"{res.get('ground_cover', 0.0):.4f}",
                "slab_hole": f"{res.get('slab_hole', 0.0):.4f}",
                "slab_cover": f"{res.get('slab_cover', 0.0):.4f}",
                "slab_solid": f"{res.get('slab_solid', 0.0):.4f}",
                "hole_sum": f"{res.get('hole_sum', 0.0):.4f}",
                "contours": res["n_contours"],
                "slabs": res["n_slab"],
                "holes": res["n_hole"],
                "kept": res["n_keep"],
                "dropped": res["n_drop"],
                "ink_ratio": f"{res['ink']:.5f}",
                "parts": res["parts"],
                "largest_share": f"{res['largest']:.3f}",
                "body_share": f"{res['body']:.4f}",
                "top3_share": f"{res['top3']:.3f}",
                "fill_ratio": f"{res['fill']:.4f}",
                "blob_solid": f"{res['solid']:.3f}",
                "chunk_ratio": f"{res.get('chunk', 0.0):.4f}",
            })
            layer_rows.append(rows[-1])
            if args.mode == "convert" and kept is not None and res["decision"] == "converted":
                out_dir.mkdir(parents=True, exist_ok=True)
                d = loops_to_path(kept)
                svg_text = render_svg(res["viewbox"], d)
                (out_dir / svg.name).write_text(svg_text, encoding="utf-8", newline="\n")

        if args.mode == "convert":
            # 只留转换过的件：没通过质检的不出文件
            if out_dir.is_dir():
                keep_names = {r["file"] for r in layer_rows
                              if r["decision"] == "converted"}
                for old in sorted(out_dir.glob("*.svg")):
                    if old.name not in keep_names:
                        old.unlink()
            # 逐件报告只记**拓片型件**。全层的件有九万多个，
            # 绝大多数跟拓片无关（写一行「不是拓片」没有信息量，
            # 还会把报告撑成几十兆）。非拓片件的数量在汇总行里给。
            # 「positive」（板形像拓片、但黑是笔画不是底）也留档——
            # 读者问「这一件为什么没反转」，答案就在报告里。
            rubbing_rows = [r for r in layer_rows if r["decision"] != "not-rubbing"]
            if rubbing_rows:
                with report_path.open("w", encoding="utf-8", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=REPORT_FIELDS)
                    w.writeheader()
                    for r in rubbing_rows:
                        w.writerow(r)
            elif report_path.is_file():
                report_path.unlink()
        kinds: dict[str, int] = {}
        for r in layer_rows:
            kinds[r["decision"]] = kinds.get(r["decision"], 0) + 1
        print(f"{script:12} 共 {len(layer_rows):6} 件  "
              + "  ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
        if args.mode == "convert":
            print(f"{'':12} → {converted} 件写入 {out_dir.relative_to(repo_root)}"
                  f"，报告 {report_path.relative_to(repo_root)}")

    print("\n合计：", "，".join(f"{k} {v}" for k, v in total.items() if v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
