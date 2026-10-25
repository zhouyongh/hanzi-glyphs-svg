#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核验「宋体·简 / 宋体·繁」两层：它们到底是什么，差在哪。

**背景：这两个层是同一书体的两个地区变体，不是「简体字层 / 繁体字层」。**

| 层 | 源字体 | 地区规范 |
|----|--------|----------|
| `glyphs/songti/`（宋体·简） | Noto Serif SC（思源宋体·简） | **中国大陆**（简体地区）规范 |
| `glyphs/songti-tc/`（宋体·繁） | Noto Serif TC（思源宋体·繁） | **台湾、香港、澳门**（繁体地区）规范 |

两层的键都是现代字 Unicode 码位，所以**简体码位与繁体码位都在每一层里**——
愛 U+611B 与 爱 U+7231 是两个不同的码位，字体两个都要有。
层名里的「简 / 繁」指的是**地区变体**，不是「这一层只收简体 / 繁体字」。

这个脚本用三组可复跑的检查回答问题：

1. **层里装的是什么**（字符集事实）：常用繁体专属字、常用简体字各有多少在层里。
2. **两层差在哪**：共有码位里，路径串**逐字节相同**的有多少（这些画出来必然一样），
   其余的用 **FreeType 渲染成位图比墨迹**——差多少、肉眼能不能看出来。
3. **层是否忠实于源字体**（保真核验，需要字体文件）：**逐字节**比——
   直接复用 `src/extract_font_glyphs.py` 重跑这个字形，得到的路径串
   与层里文件里的路径串**完全一致**才算过。

⚠ **两处必须写下来的坑（本轮自己踩了）。**

1. **不能比 SVG 字节。** 每层的 viewBox 是**该层全部字形墨迹的并集**，
   两层画布不同（宋体·简 `1 -874 1006 992` / 宋体·繁 `1 -873 1004 990`），
   同一个字形落在不同坐标系里，**整个文件**的字节必然都不同——那样比会得到
   「全都不同」的假阳性。
2. **不能比控制点个数或点集。** 两个字体里的同一个字，轮廓的**分段方式**可能不同
   （同一段弧，一个字体存成 1 条二次曲线，另一个存成 2 条），控制点个数因此不一样。
   「比点数」与「比点集」都会误判成「字形不同」，而实际上画出来一模一样。
   **比像素**才对——像素比对分段方式免疫，它比的正是「画出来像不像」。

用法::

    python src/verify_songti_variants.py
    python src/verify_songti_variants.py --font-sc <NotoSerifSC.ttf> --font-tc <NotoSerifTC.ttf>
    python src/verify_songti_variants.py --markdown        # 出 Markdown 表格
    python src/verify_songti_variants.py --json out.json    # 机读结果

字体原件不在仓库里（各层 `SOURCE.md` 记了 sha256 与上游地址）。
第 2 项的视觉判据与第 3 项都需要它们；没有就只跑字符集事实与路径串比对。

退出码 0 = 全部通过；非 0 = 有检查没过。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLYPHS = ROOT / "glyphs"
sys.path.insert(0, str(ROOT / "src"))

SC_LAYER, TC_LAYER = "songti", "songti-tc"
LAYER_TITLE = {SC_LAYER: "宋体·简", TC_LAYER: "宋体·繁"}

# 墨迹不重合比例超过这个值，就算「肉眼看得出不同」。
# 2% 是在 96 px 渲染下取的：笔画粗细差一根线的量级就够明显了。
VISUAL_THRESHOLD = 0.02

# 常用「繁体专属」字：简体里没有对应字形，用来量「层里有多少繁体字」
TRAD_ONLY = (
    "愛國學語書話買賣車門長馬鳥魚龍鳳麗麥黃黑點齊鼓鼠鼻電靈顯體髮鬥鬧鮮鹽麵齒"
    "們個來這說時對開關間聞讀寫圖會發裡後過還邊遠運進連週達適選遞醫釋針釘銀銷錄"
    "錯鍵鏡鐵鑑靜韓項順預領頭題顏願類顧風飛飯飲飾養駕聯職聽臨舉舊艦藝蓮薈薑蘊蘿"
    "虧蟲蠟蠶蠻襯襲覆覽觀觸訂計認討讓訓議記講許論設訪證評識訴診詞譯試詩誠該"
    "詳誤請諸讀課誰調談謀謂謝謹變豐財貨貴費資賓賞質賴賽贈贏軍較載輔輕輛輝輪"
    "輸轉農違鄉鄧鄭車遙塗燈燒燦燭爐爛爭爺爾牆牽狀狹獄獅獨現環產畢異當疇疊療"
    "癡盜瞞磯礙礎礫祿禍禪離種稱積竊競筆筍節築篩簡籃籌籤籬粵糧紅紀紋納紐純紗"
    "紙級紛素紡索紫細組絕絞絡給統絲絹綁綏經綜綠綢維綱網緘線緝締緣編緩緯練縈縛"
    "縫縱總績織繕繞繡繩繳續纖罰罷羅習聳脅腸腎腦腫膚膠膽臉臟襖覓規覺訥"
)

# 上面那串里的简体对应字，用来量「层里有多少简体字」
SIMP_ONLY = (
    "爱国学语书话买卖车门长马鸟鱼龙凤丽麦黄黑点齐鼓鼠鼻电灵显体发斗闹鲜盐面齿"
    "们个来这说时对开关间闻读写图会发里后过还边远运进连周达适选递医释针钉银销录"
    "错键镜铁鉴静韩项顺预领头题颜愿类顾风飞饭饮饰养驾联职听临举旧舰艺莲荟姜蕴萝"
    "亏虫蜡蚕蛮衬袭覆览观触订计认讨让训议记讲许论设访证评识诉诊词译试诗诚该"
    "详误请诸读课谁调谈谋谓谢谨变丰财货贵费资宾赏质赖赛赠赢军较载辅轻辆辉轮"
    "输转农违乡邓郑车遥涂灯烧灿烛炉烂争爷尔墙牵状狭狱狮独现环产毕异当畴叠疗"
    "痴盗瞒矶碍础砾禄祸禅离种称积窃竞笔笋节筑筛简篮筹签篱粤粮红纪纹纳纽纯纱"
    "纸级纷素纺索紫细组绝绞络给统丝绢绑绥经综绿绸维纲网缄线缉缔缘编缓纬练萦缚"
    "缝纵总绩织缮绕绣绳缴续纤罚罢罗习耸胁肠肾脑肿肤胶胆脸脏袄觅规觉讷"
)

# Unicode 区块（用于分块统计差异分布）
BLOCKS = [
    ("扩展 A", 0x3400, 0x4DBF),
    ("基本区", 0x4E00, 0x9FFF),
    ("兼容表意", 0xF900, 0xFAFF),
    ("兼容补充", 0x2F800, 0x2FA1F),
    ("扩展 B", 0x20000, 0x2A6DF),
    ("扩展 C", 0x2A700, 0x2B73F),
    ("扩展 D", 0x2B740, 0x2B81F),
    ("扩展 E", 0x2B820, 0x2CEAF),
    ("扩展 F", 0x2CEB0, 0x2EBEF),
    ("扩展 G", 0x30000, 0x3134F),
]


def block_of(cp: int) -> str:
    for name, lo, hi in BLOCKS:
        if lo <= cp <= hi:
            return name
    return "其他"


def load_index(layer: str) -> dict[str, str]:
    """读层目录的 index.csv，返回 {codepoint: modern_char}。"""
    out: dict[str, str] = {}
    with (GLYPHS / layer / "index.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            cp = (row.get("codepoint") or "").strip()
            if cp:
                out[cp] = (row.get("modern_char") or "").strip()
    return out


def read_d(layer: str, cp: str) -> str:
    """读层里某个字形文件的路径串（`d="…"` 里的内容）。"""
    text = (GLYPHS / layer / f"{cp}.svg").read_text(encoding="utf-8")
    start = text.index('d="') + 3
    end = text.index('"', start)
    return text[start:end]


class FontSource:
    """源字体：按 `src/extract_font_glyphs.py` 的做法逐字形重跑路径串。

    **直接复用仓库自己的提取器**（`ntos` 与 `glyph_path`），
    免得「核验用的算法」与「入库用的算法」是两套。
    """

    def __init__(self, font_path: Path, location: str | None = "wght=400"):
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.ttLib import TTFont

        from extract_font_glyphs import glyph_path, ntos

        self._svg_pen_cls = SVGPathPen
        self._glyph_path = glyph_path
        self._ntos = ntos
        self.font = TTFont(font_path, lazy=True)
        loc = None
        if location:
            loc = {}
            for part in location.split(","):
                axis, value = part.split("=", 1)
                loc[axis.strip()] = float(value)
        self.glyph_set = self.font.getGlyphSet(location=loc) if loc else self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()

    def path_d(self, cp: int) -> str | None:
        """这个码位在源字体里的路径串（与层里文件的 `d` 应当逐字节相同）。"""
        name = self.cmap.get(cp)
        if name is None:
            return None
        pen = self._svg_pen_cls(self.glyph_set, ntos=self._ntos)
        return self._glyph_path(pen, self.glyph_set, name)


class Raster:
    """用 FreeType 渲染字形并比墨迹——「画出来像不像」的判据。

    为什么不用自己解析 SVG 再填充：TrueType 用**非零环绕**规则，
    而 PIL 的多边形填充是**偶奇**规则；字里有笔画交叠时，
    偶奇会把交叠处挖成白，肉眼根本不是那样。
    交给 FreeType 就没有这个问题——**它就是用户看到的那个渲染器**。
    """

    def __init__(self, font_path: Path, size: int = 96, location: str | None = "wght=400"):
        from PIL import ImageFont

        self.font = ImageFont.truetype(str(font_path), size)
        if location:
            axes = []
            for part in location.split(","):
                axis, value = part.split("=", 1)
                axes.append(float(value))
            try:
                self.font.set_variation_by_axes(axes)
            except Exception:       # noqa: BLE001 —— 字体不可变时没有变体轴
                pass
        self.size = size

    def ink(self, ch: str):
        """渲染一个字，返回墨迹掩码（PIL 'L' 模式，0 = 有墨）。"""
        from PIL import Image, ImageDraw

        box = int(self.size * 1.8)
        img = Image.new("L", (box, box), 255)
        ImageDraw.Draw(img).text((int(self.size * 0.4), int(self.size * 0.2)),
                                 ch, font=self.font, fill=0)
        return img

    @staticmethod
    def diff_ratio(a, b) -> float | None:
        """两张墨迹图的不重合比例（0 = 完全一样）。

        先二值化（<128 算有墨），再算 **异或 / 并集**：
        `ImageChops.difference` 给的是**绝对差**，两个值一样时差为 0——
        差为 255 才表示「一个有墨一个没墨」，别把这两个搞反。
        """
        from PIL import ImageChops

        ab = a.point(lambda v: 0 if v < 128 else 255)
        bb = b.point(lambda v: 0 if v < 128 else 255)
        union = ImageChops.darker(ab, bb)          # 并集：任一个有墨即为 0
        diff = ImageChops.difference(ab, bb)       # 异或：恰好一个有墨为 255
        n_union = union.tobytes().count(b"\x00")
        n_diff = diff.tobytes().count(b"\xff")
        if not n_union:
            return None
        return n_diff / n_union


def check_charset() -> dict:
    """第 1 项：层里到底装了什么字符。

    简体层有一条**不变量**：它装的是**整个 CJK 基本区**，所以常用繁体专属字
    与对应的简体字**都必须在**。少了就说明这层被当成了「简体字集合」——
    那正是本脚本要防住的误解。繁体层没有这条不变量：
    Noto Serif TC 的基本区只有 15,384 个码位，简体字本来就大多收不到。
    """
    sc = load_index(SC_LAYER)
    tc = load_index(TC_LAYER)
    sc_chars = set(sc.values())
    tc_chars = set(tc.values())
    sc_missing_trad = [c for c in sorted(set(TRAD_ONLY)) if c not in sc_chars]
    sc_missing_simp = [c for c in sorted(set(SIMP_ONLY)) if c not in sc_chars]
    return {
        "sc_codepoints": len(sc),
        "tc_codepoints": len(tc),
        "sc_trad_hit": sum(1 for c in set(TRAD_ONLY) if c in sc_chars),
        "sc_trad_total": len(set(TRAD_ONLY)),
        "sc_simp_hit": sum(1 for c in set(SIMP_ONLY) if c in sc_chars),
        "sc_simp_total": len(set(SIMP_ONLY)),
        "tc_trad_hit": sum(1 for c in set(TRAD_ONLY) if c in tc_chars),
        "tc_trad_total": len(set(TRAD_ONLY)),
        "tc_simp_hit": sum(1 for c in set(SIMP_ONLY) if c in tc_chars),
        "tc_simp_total": len(set(SIMP_ONLY)),
        "sc_missing_trad": sc_missing_trad,
        "sc_missing_simp": sc_missing_simp,
    }


def check_layer_difference(sample: int = 0,
                           source_sc: "FontSource | None" = None,
                           source_tc: "FontSource | None" = None,
                           raster_sc: "Raster | None" = None,
                           raster_tc: "Raster | None" = None,
                           visual_threshold: float = VISUAL_THRESHOLD) -> dict:
    """第 2 项：两层共有码位里，**画出来不一样**的有多少。

    **有字体时从字体比，没字体时才读层里的 SVG 文件。** 两种比法**等价**——
    第 3 项证明层里的路径串与源字体的路径串**逐字节相同**，
    所以从字体比出来的结论就是层的结论。区别只在代价：
    读 2 个字体文件 vs 读 3.2 万个 SVG 文件。

    判据分三档：
    - **路径串逐字节相同** → 画出来必然一样（连轮廓分段都一样）；
    - 否则**渲染成位图比墨迹**，不重合比例超过 `visual_threshold` 才算
      「肉眼看得出不同」；
    - 比阈值小的算「数值/分段差异，肉眼基本看不出」。
    """
    sc = load_index(SC_LAYER)
    tc = load_index(TC_LAYER)
    common = sorted(set(sc) & set(tc))
    if sample and len(common) > sample:
        step = len(common) // sample
        common = common[::step][:sample]
    identical = 0
    visual: list[str] = []
    subtle: list[str] = []
    ratios: dict[str, float] = {}
    buckets: dict[str, int] = {}
    for cp in common:
        if source_sc is not None and source_tc is not None:
            d_sc = source_sc.path_d(int(cp, 16))
            d_tc = source_tc.path_d(int(cp, 16))
            if d_sc is None or d_tc is None:
                continue
        else:
            d_sc = read_d(SC_LAYER, cp)
            d_tc = read_d(TC_LAYER, cp)
        if d_sc == d_tc:
            identical += 1
            continue
        if raster_sc is None or raster_tc is None:
            continue
        ch = sc.get(cp) or ""
        if not ch:
            continue
        ratio = Raster.diff_ratio(raster_sc.ink(ch), raster_tc.ink(ch))
        if ratio is None:
            continue
        ratios[cp] = ratio
        (visual if ratio >= visual_threshold else subtle).append(cp)
        key = ("<2%" if ratio < 0.02 else
               "2~5%" if ratio < 0.05 else
               "5~10%" if ratio < 0.10 else
               "10~20%" if ratio < 0.20 else
               "20~40%" if ratio < 0.40 else
               ">=40%")
        buckets[key] = buckets.get(key, 0) + 1
    same = identical + len(subtle)
    return {
        "common": len(common),
        "same": same,
        "diff": len(visual),
        "identical_path_string": identical,
        "subtle": len(subtle),
        "visual": bool(raster_sc and raster_tc),
        "visual_threshold": visual_threshold,
        "histogram": buckets,
        "diff_codepoints": visual,
        "diff_chars": {cp: sc[cp] for cp in visual},
        "worst": sorted(((v, k) for k, v in ratios.items()), reverse=True)[:60],
        "by_block": _by_block(common, visual),
    }


def _by_block(common: list[str], diff: list[str]) -> dict:
    """按 Unicode 区块统计：共有多少、字形不同多少。"""
    out: dict = {}
    diffset = set(diff)
    for cp in common:
        name = block_of(int(cp, 16))
        row = out.setdefault(name, {"common": 0, "diff": 0})
        row["common"] += 1
        if cp in diffset:
            row["diff"] += 1
    return out


def check_fidelity(source_sc: "FontSource | None", source_tc: "FontSource | None",
                   sample: int) -> dict:
    """第 3 项：层是否忠实于源字体——**逐字节**比路径串。

    判据：把仓库自己的提取器对源字体重跑一遍这个字形，
    得到的路径串与层里文件里的路径串**完全一致**。
    这比「外接盒罩住」强得多：罩住只说明形状对，字符串相同才说明**同源**。
    """
    result: dict = {"enabled": bool(source_sc and source_tc), "sc_checked": 0, "tc_checked": 0,
                    "sc_bad": [], "tc_bad": [], "missing": []}
    if not (source_sc and source_tc):
        return result
    for layer, source, bad_key, count_key in (
        (SC_LAYER, source_sc, "sc_bad", "sc_checked"),
        (TC_LAYER, source_tc, "tc_bad", "tc_checked"),
    ):
        index = load_index(layer)
        cps = sorted(index)
        if sample and len(cps) > sample:
            step = len(cps) // sample
            cps = cps[::step][:sample]
        for cp in cps:
            ref = source.path_d(int(cp, 16))
            if ref is None:
                result["missing"].append(f"{layer}/{cp}")
                continue
            if ref != read_d(layer, cp):
                result[bad_key].append(cp)
            result[count_key] += 1
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="核验宋体·简 / 宋体·繁 两层的性质与差异")
    ap.add_argument("--font-sc", type=Path, help="Noto Serif SC 字体路径")
    ap.add_argument("--font-tc", type=Path, help="Noto Serif TC 字体路径")
    ap.add_argument("--location", default="wght=400",
                    help="可变字体实例（默认 wght=400；**必须**与提取时一致）")
    ap.add_argument("--sample", type=int, default=0, help="保真核验的抽样数（0 = 全量）")
    ap.add_argument("--skip-fidelity", action="store_true",
                    help="跳过第 3 项保真核验（它要逐个读层里的字形文件，全量在慢盘上很慢）")
    ap.add_argument("--charset-only", action="store_true",
                    help="只跑第 1 项字符集事实（只读两个 index.csv，秒级；CI 用这个）")
    ap.add_argument("--diff-sample", type=int, default=0,
                    help="两层差异比对的抽样数（0 = 全量）")
    ap.add_argument("--markdown", action="store_true", help="输出 Markdown 表格")
    ap.add_argument("--json", type=Path, help="把结果写成 JSON")
    args = ap.parse_args(argv)

    source_sc = FontSource(args.font_sc, args.location) if args.font_sc else None
    source_tc = FontSource(args.font_tc, args.location) if args.font_tc else None
    raster_sc = Raster(args.font_sc, location=args.location) if args.font_sc else None
    raster_tc = Raster(args.font_tc, location=args.location) if args.font_tc else None

    out: dict = {"charset": check_charset()}
    if args.charset_only:
        out["difference"] = {"skipped": True}
        out["fidelity"] = {"enabled": False, "skipped": True, "sc_checked": 0, "tc_checked": 0,
                           "sc_bad": [], "tc_bad": [], "missing": []}
    else:
        out["difference"] = check_layer_difference(args.diff_sample, source_sc, source_tc,
                                                   raster_sc, raster_tc)
        out["fidelity"] = ({"enabled": False, "skipped": True, "sc_checked": 0, "tc_checked": 0,
                             "sc_bad": [], "tc_bad": [], "missing": []}
                            if args.skip_fidelity
                            else check_fidelity(source_sc, source_tc, args.sample))

    cs = out["charset"]
    df = out["difference"]
    fd = out["fidelity"]

    if args.markdown:
        print("| 检查 | 结果 |")
        print("|------|------|")
        print(f"| 简体层码位数 | {cs['sc_codepoints']:,} |")
        print(f"| 繁体层码位数 | {cs['tc_codepoints']:,} |")
        print(f"| 简体层里的常见繁体专属字 | {cs['sc_trad_hit']} / {cs['sc_trad_total']} |")
        print(f"| 简体层里的对应简体字 | {cs['sc_simp_hit']} / {cs['sc_simp_total']} |")
        print(f"| 繁体层里的常见繁体专属字 | {cs['tc_trad_hit']} / {cs['tc_trad_total']} |")
        print(f"| 繁体层里的对应简体字 | {cs['tc_simp_hit']} / {cs['tc_simp_total']} |")
        print(f"| 两层共有码位 | {df['common']:,} |")
        print(f"| 路径串逐字节相同 | {df['identical_path_string']:,} |")
        if df["visual"]:
            print(f"| 肉眼看不出差别 | {df['subtle']:,} |")
            print(f"| **肉眼看得出不同** | **{df['diff']:,}** |")
        if fd["enabled"]:
            print(f"| 简体层保真核验（路径串逐字节） | {fd['sc_checked'] - len(fd['sc_bad'])} / {fd['sc_checked']} 一致 |")
            print(f"| 繁体层保真核验（路径串逐字节） | {fd['tc_checked'] - len(fd['tc_bad'])} / {fd['tc_checked']} 一致 |")
    else:
        print("=== 1. 层里装的是什么（字符集事实） ===")
        print(f"  {LAYER_TITLE[SC_LAYER]} {cs['sc_codepoints']:,} 码位 / "
              f"{LAYER_TITLE[TC_LAYER]} {cs['tc_codepoints']:,} 码位")
        print(f"  常见繁体专属字在简体层：{cs['sc_trad_hit']} / {cs['sc_trad_total']}")
        print(f"  对应简体字在简体层　：{cs['sc_simp_hit']} / {cs['sc_simp_total']}")
        print(f"  常见繁体专属字在繁体层：{cs['tc_trad_hit']} / {cs['tc_trad_total']}")
        print(f"  对应简体字在繁体层　：{cs['tc_simp_hit']} / {cs['tc_simp_total']}")
        print("  → 简体码位与繁体码位**都在每一层里**（它们是不同码位，字体两个都要有）")
        print()
        print("=== 2. 两层差在哪 ===")
        if df.get("skipped"):
            print("  已跳过（--charset-only）")
        else:
            print(f"  共有码位 {df['common']:,}　路径串逐字节相同 {df['identical_path_string']:,}")
            if df["visual"]:
                print(f"  其余的：肉眼看不出差别 {df['subtle']:,}　"
                      f"**肉眼看得出不同** {df['diff']:,}"
                      f"（判据：墨迹不重合 ≥ {df['visual_threshold'] * 100:.0f}%）")
                print("  差异幅度分布（墨迹不重合比例）：")
                for key in ("<2%", "2~5%", "5~10%", "10~20%", "20~40%", ">=40%"):
                    n = df.get("histogram", {}).get(key, 0)
                    if n:
                        print(f"    {key:<8} {n:>6,}  ({n * 100.0 / df['common']:.1f}%)")
                for name, row in df.get("by_block", {}).items():
                    pct = row["diff"] * 100.0 / row["common"] if row["common"] else 0
                    print(f"    {name:<8} 共有 {row['common']:>6,}　不同 {row['diff']:>6,}（{pct:.1f}%）")
                if df["diff"]:
                    sample = df["diff_codepoints"][:40]
                    print("  不同的码位示例：" + " ".join(
                        f"U+{cp}({df['diff_chars'].get(cp, '')})" for cp in sample))
                    print("  差异最大的 15 个：")
                    for ratio, cp in df.get("worst", [])[:15]:
                        print(f"    U+{cp} {df['diff_chars'].get(cp, '')}  墨迹不重合 {ratio * 100:.1f}%")
            else:
                print("  （视觉判据需要字体文件：--font-sc / --font-tc）")
        print()
        print("=== 3. 保真核验（层 vs 源字体，路径串逐字节） ===")
        if not fd["enabled"]:
            print("  未提供字体文件，跳过。")
            print("  用法：--font-sc <NotoSerifSC.ttf> --font-tc <NotoSerifTC.ttf>")
        else:
            print(f"  简体层：{fd['sc_checked'] - len(fd['sc_bad'])} / {fd['sc_checked']} 一致")
            print(f"  繁体层：{fd['tc_checked'] - len(fd['tc_bad'])} / {fd['tc_checked']} 一致")
            if fd["sc_bad"]:
                print(f"  !! 简体层不一致：{fd['sc_bad'][:10]}")
            if fd["tc_bad"]:
                print(f"  !! 繁体层不一致：{fd['tc_bad'][:10]}")
            if fd["missing"]:
                print(f"  !! 字体里没有的码位：{fd['missing'][:10]}")
    if args.json:
        args.json.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结果已写入 {args.json}")

    ok = True
    # 简体层的不变量：常用繁简字都要在（这层装的是整个 CJK 基本区，
    # 不是「简体字集合」）。这条不需要字体，所以能进 CI。
    if cs["sc_missing_trad"] or cs["sc_missing_simp"]:
        ok = False
        print()
        print("!! 简体层缺了常用繁体字：", " ".join(cs["sc_missing_trad"][:30]))
        print("!! 简体层缺了对应简体字：", " ".join(cs["sc_missing_simp"][:30]))
    if fd["enabled"]:
        ok = ok and not (fd["sc_bad"] or fd["tc_bad"] or fd["missing"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
