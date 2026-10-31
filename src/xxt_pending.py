#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小學堂批次的**待补清单**：计划要收、但上游位图取不到的那些字形。

为什么要有这个
--------------
小學堂批次的字形是**位图描摹**件：上游给的是位图，本地 SVG 是自动描摹的派生件。
位图取不到，这一层的字形就做不出来——但这不等于「这个字不存在」。

上游的取图端点 ``/ImageText2/ShowImage.ashx`` 由中研院 ASCDC 提供，历史上受过
两类拦截（见 ``src/fetch_xiaoxuetang_glyphs.py`` 的四种响应表）：

- **地区级封锁**（``Access Restricted``，「current country or region is not yet open」）：
  ``xiaoxue.iis.sinica.edu.tw`` 全站挡回，这一层所在地区的出口取不到任何路径；
- **接口下线**（``404 Not Found | ASCDC``）：``char.iis.sinica.edu.tw`` 改版成
  Blazor 之后，旧渲染路由 ``/ImageText2/ShowImage.ashx`` 已经不存在。

这两件事都**不在本仓库的控制范围内**，所以「取不到」这件事必须**记在仓里**，
而不是烂在 ``tmp/`` 里（``tmp/`` 是 gitignore 的，清一次就没了）。
本清单就是那份记录：每一行给出字形键、出处、以及**可直接打开的上游取图地址**，
等端点恢复（或换个能访问的出口）时，按清单补抓即可，不必重新推演选哪些。

用法::

    # 生成/更新某一层的待补清单
    python src/xxt_pending.py --layer clerical --db lishu \
        --selection tmp/xxt/lishu/fetch-selection.jsonl \
        --img-dir tmp/xxt/lishu/img \
        --out glyphs/clerical/pending-xxt.csv

    # 体检（CI 用；不依赖 tmp/，只查仓内可验证的部分）
    python src/xxt_pending.py --check --repo-root .

清单与层的分工
--------------
**待补清单里的字形一个都不在层里**——层是「已入库的」，清单是「知道存在但还没做出来」。
体检会查这条：清单里若有字形已经在层里，说明清单过期了，该删。
反方向（层里该有却没有）需要 ``tmp/`` 里的选取记录才查得了，本地模式会查。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 上游取图端点（小学堂自己的字体服务器）。字形图按 (字体号, 码位) 定位，
#: ``font`` 参数**必须**带：PUA 码位按字体分命名空间，同一个码位在不同字体里是不同字。
RENDER_ENDPOINT = "https://xiaoxue.iis.sinica.edu.tw/ImageText2/ShowImage.ashx"

#: 取图尺寸。描摹参数（Douglas-Peucker 的 eps 是**像素**）是按尺寸定的，
#: 尺寸混用会让轮廓过平滑或过毛刺，所以清单里写死这个值，与 ``--size 400`` 一致。
IMAGE_SIZE = 400

#: 清单的列。列名用英文，与各层的 index.csv / staged.csv 一致。
COLUMNS = [
    "shape_key", "font_id", "font", "pua",
    "modern_char", "unicode", "identity_confidence",
    "book_code", "bucket_key", "source_short",
    "image_url", "reason",
]

#: 「取不到」的理由写进每一行，短码 + 说明在本文档与 AGENTS.md 里。
REASON = "upstream-image-unavailable"

#: 私用區区段——不得当汉字码位写进 unicode 列。
PUA_START, PUA_END = 0xE000, 0xF8FF


def image_url(pua: str, font: str, size: int = IMAGE_SIZE) -> str:
    """上游取图地址。

    ``text`` 要传**真正的 PUA 字符**（URL 编码），不能传十六进制字符串——
    传 ``E0A9`` 会被当成四个字面字符，渲染出一张写着 "E0A9" 的图。
    """
    word = "".join(chr(int(c, 16)) for c in pua.split(","))
    q = urllib.parse.urlencode({"text": word, "font": font, "size": str(size),
                                "style": "regular", "color": "#000000"})
    return f"{RENDER_ENDPOINT}?{q}"


def normalize_unicode(identity: str, confidence: str) -> str:
    """把选取记录里的身份写成 unicode 列。

    **私用區码位不是汉字码位**——临时身份条目（``pua-slot``）的 unicode 列必须留空，
    否则清单里会出现「一个没有对应汉字的码位」。
    """
    if not identity or confidence == "pua-slot":
        return ""
    try:
        cp = int(identity, 16)
    except ValueError:
        return ""
    if PUA_START <= cp <= PUA_END:
        return ""
    return f"{cp:06X}"


def read_selection(path: Path) -> list[dict]:
    if not path.is_file():
        raise SystemExit(f"选取记录不存在：{path}")
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def layer_pairs(root: Path, layer: str) -> set[tuple[str, str]]:
    """本层**已经入库**的「(字形键, 现代字)」对。

    合并的键是 **(现代字, 字形键)**，重叠处**漢典矢量优先**（``layer=skeleton``
    盖过 ``layer=outline``）——所以只要层里已经有这一对，小學堂那一份就**不会**被收进来，
    也不该进待补清单。

    **必须连现代字一起比**：字形键只是「字体号_码位」，而**字体号按来源各自编号**——
    漢典的 ``91_E234`` 与小學堂的 ``91_E234`` 是两个不同字体的槽位，
    码位相同纯属巧合（实测 194 例）。只比字形键会把它们误判成「已经入库」。
    """
    prov = root / "glyphs" / "provenance" / f"{layer}.jsonl"
    pairs: set[tuple[str, str]] = set()
    if not prov.is_file():
        return pairs
    for line in prov.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        sid = str(rec.get("source_id") or "")
        if "_" not in sid:
            continue
        pairs.add((sid, str(rec.get("modern_char") or "")))
    return pairs


def missing_keys(selection: list[dict], img_dir: Path,
                 shipped: set[tuple[str, str]]) -> list[str]:
    """选取记录里**做不出来**的字形键（保持选取记录的顺序，去重）。

    两道筛：

    1. **层里已经有的那一对**（见 :func:`layer_pairs`）——合并时会被漢典矢量顶掉，
       做出来也是重复，不算待补；
    2. **本地没有位图**——位图是描摹件的原料，没有原料就没有字形。
    """
    seen: set[str] = set()
    out: list[str] = []
    for rec in selection:
        key = rec.get("shape_key") or f"{rec.get('font_id', '')}_{rec.get('pua', '')}"
        if key in seen:
            continue
        seen.add(key)
        if (key, str(rec.get("modern_char") or "")) in shipped:
            continue
        png = img_dir / f"{key}.png"
        if png.is_file() and png.stat().st_size > 0:
            continue
        out.append(key)
    return out


def build_rows(selection: list[dict], img_dir: Path,
               shipped: set[tuple[str, str]]) -> list[dict]:
    want = set(missing_keys(selection, img_dir, shipped))
    rows: list[dict] = []
    for rec in selection:
        key = rec.get("shape_key") or f"{rec.get('font_id', '')}_{rec.get('pua', '')}"
        if key not in want:
            continue
        font = rec.get("font", "")
        pua = rec.get("pua", "")
        rows.append({
            "shape_key": key,
            "font_id": rec.get("font_id", ""),
            "font": font,
            "pua": pua,
            "modern_char": rec.get("modern_char", ""),
            "unicode": normalize_unicode(rec.get("identity", ""),
                                         rec.get("identity_confidence", "")),
            "identity_confidence": rec.get("identity_confidence", ""),
            "book_code": rec.get("book_code", ""),
            "bucket_key": rec.get("bucket_key", ""),
            "source_short": rec.get("source_short", ""),
            "image_url": image_url(pua, font) if pua and font else "",
            "reason": REASON,
        })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)




def check_pending(root: Path, problems: list[str], quiet: bool) -> int:
    """体检仓内的待补清单。"""
    checked = 0
    for csv_path in sorted((root / "glyphs").glob("*/pending-xxt.csv")):
        layer = csv_path.parent.name
        with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            rows = list(reader)
        checked += len(rows)
        if header != COLUMNS:
            problems.append(f"{csv_path.as_posix()}: 列名不对：{header}")
            continue
        shipped = layer_pairs(root, layer)
        seen: set[str] = set()
        for i, row in enumerate(rows, start=2):
            key = (row.get("shape_key") or "").strip()
            mc = (row.get("modern_char") or "").strip()
            if not key:
                problems.append(f"{csv_path.as_posix()}:{i} shape_key 为空")
                continue
            if key in seen:
                problems.append(f"{csv_path.as_posix()}:{i} shape_key 重复：{key}")
            seen.add(key)
            if (key, mc) in shipped:
                problems.append(
                    f"{csv_path.as_posix()}:{i} {key}「{mc}」已经在层里入库了，待补清单过期")
            uni = (row.get("unicode") or "").strip()
            if uni:
                if len(uni) != 6 or any(c not in "0123456789ABCDEF" for c in uni):
                    problems.append(
                        f"{csv_path.as_posix()}:{i} unicode 不是 6 位大写十六进制：{uni}")
                else:
                    cp = int(uni, 16)
                    if PUA_START <= cp <= PUA_END:
                        problems.append(
                            f"{csv_path.as_posix()}:{i} unicode 是私用區码位，不得当汉字码位")
            elif (row.get("identity_confidence") or "").strip() != "pua-slot":
                problems.append(
                    f"{csv_path.as_posix()}:{i} unicode 为空，但身份不是临时身份")
            url = (row.get("image_url") or "").strip()
            if not url.startswith(RENDER_ENDPOINT + "?"):
                problems.append(f"{csv_path.as_posix()}:{i} image_url 不是上游取图地址")
            if (row.get("reason") or "").strip() != REASON:
                problems.append(f"{csv_path.as_posix()}:{i} reason 不是 {REASON}")
        if not quiet:
            print(f"  {layer}: 待补 {len(rows)} 条")
    return checked


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="小學堂批次待补清单：生成与体检")
    ap.add_argument("--repo-root", type=Path, default=ROOT)
    ap.add_argument("--layer", default=None, help="层名，如 clerical")
    ap.add_argument("--db", default=None, help="小學堂库名，如 lishu")
    ap.add_argument("--selection", type=Path, default=None,
                    help="选取记录 fetch-selection.jsonl")
    ap.add_argument("--img-dir", type=Path, default=None,
                    help="位图目录（本地已缓存的位图）")
    ap.add_argument("--out", type=Path, default=None,
                    help="待补清单输出路径")
    ap.add_argument("--shape-list", type=Path, default=None,
                    help="从待补清单导出字形键清单（一行一个「字体号_码位」），"
                         "供 fetch_xiaoxuetang_glyphs.py --shape-list 补抓用")
    ap.add_argument("--check", action="store_true", help="只体检，不写文件")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    root = args.repo_root.resolve()

    # ---- 只导出字形键清单：从**仓内**的待补清单读，不依赖 tmp/ ----
    if args.shape_list and not args.layer:
        raise SystemExit("--shape-list 要配 --layer")
    if args.shape_list:
        layer = args.layer
        src = root / "glyphs" / layer / "pending-xxt.csv"
        if not src.is_file():
            raise SystemExit(f"待补清单不存在：{src}")
        with src.open("r", encoding="utf-8-sig", newline="") as fh:
            keys = [row["shape_key"] for row in csv.DictReader(fh)]
        args.shape_list.parent.mkdir(parents=True, exist_ok=True)
        args.shape_list.write_text("\n".join(keys) + "\n", encoding="utf-8", newline="\n")
        print(f"{layer}: 导出 {len(keys)} 个字形键 → {args.shape_list}")
        return 0

    if args.check:
        problems: list[str] = []
        checked = check_pending(root, problems, args.quiet)
        if problems:
            print(f"待补清单体检：{len(problems)} 个问题", file=sys.stderr)
            for p in problems[:40]:
                print(f"  ! {p}", file=sys.stderr)
            return 1
        print(f"待补清单体检：{checked} 条，0 问题")
        return 0

    # ---- 生成 ----
    layer = args.layer
    db = args.db
    if not layer or not db:
        raise SystemExit("生成模式要同时给 --layer 与 --db")
    selection_path = args.selection or (root / "tmp" / "xxt" / db / "fetch-selection.jsonl")
    img_dir = args.img_dir or (root / "tmp" / "xxt" / db / "img")
    out_path = args.out or (root / "glyphs" / layer / "pending-xxt.csv")
    selection = read_selection(selection_path)
    shipped = layer_pairs(root, layer)
    rows = build_rows(selection, img_dir, shipped)
    write_csv(out_path, rows)
    print(f"{layer}: 选取 {len(selection)} 条，待补 {len(rows)} 条 → "
          f"{out_path.relative_to(root).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
