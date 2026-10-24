#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洗掉汉典字形里的水印层，产出可直接入库的字形文件与清单。

用法::

    python src/clean_zdic_glyphs.py --manifest tmp/zdic/jinwen/manifest.json \
        --out tmp/zdic/jinwen-clean

为什么要有这一步。**汉典的金文（与篆书）字形 SVG 里带一层近白色的水印**：
一小组近白色（``#fafafb`` 一类）的小字，排在画布的角上，是汉典自己的标记。
它不是字形的一部分，却会跟着字形一起被分发、在深色背景上显形。

本脚本做的事只有一件：把「有效填充色接近纯白」的 ``<g>`` / ``<path>`` 元素
**整块删掉**，其余字节原样保留。所以与上游原件的差异是可逐行核对的，
不会牵动字形本身。

判定依据（2026-10-23 对 2,310 个金文字形实测）：

* 填充色只有两种：近黑 ``#000001``–``#010106`` 与近白 ``#fafafb``–``#fcfbfa``，
  **没有中间调**，所以「近白」与「字形笔画」不存在灰度边界上的歧义；
* 近白区域与主笔画的包围盒**零重叠**；
* 近白区域占画布面积 0.16%–0.46%，且总是贴着画布一角。

**许可上这样做没问题**：汉典依《服务条款》第四条以 CC0 1.0 释出这些书法字形，
CC0 不设任何条件，改与不改都行，也没有「相同方式共享」的要求。
本仓库把这一改动如实记进 ``provenance.jsonl`` 的 ``modifications`` 字段，
并把上游原件的 sha256 一并留下，好让人随时能对回去。

**位图闸门。** 汉典有个别实例不是矢量轮廓，而是把一张 PNG 以 base64 塞进
``<image xlink:href="data:image/png;base64,…">``（2026-10-23 实测：小篆「挈」「挂」
两字如此）。这类文件虽然是合法的 SVG，却不是**矢量字形**：下游转字体、缩放、
取轮廓都用不上；而且水印与笔画烤在同一张位图里，分不开，
``modifications`` 也就没法如实记。本库只收矢量字形，所以本脚本把它们**剔除**，
并在输出里点名报告。矢量与否由 ``check_glyphs.py`` 复核。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_zdic_glyphs import parse_caption_for_kind  # noqa: E402

# 近白判定：三个通道都 >= 这个值才算「水印色」。
# 实测上游只有 #000001–#010106 与 #fafafb/#fafbfa/#fafbfc/#fbfafa/#fbfafc/#fbfcfa/#fcfafa/#fcfbfa 两类，
# 取 235 留足余量。
NEAR_WHITE_MIN = 235

# 只处理这两类元素：汉典的字形只由 <g> 与 <path> 构成。
TAG_RE = re.compile(r"<(/?)(g|path)\b([^>]*?)(/?)>", re.S)
FILL_RE = re.compile(r"""\bfill\s*=\s*["']([^"']+)["']""", re.I)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_fill(value: str) -> tuple[int, int, int] | None:
    """把 fill 的值解析成 RGB；认不出就返回 None（当作「不是水印色」）。"""
    value = value.strip().lower()
    if value in ("none", "transparent"):
        return None
    if value.startswith("#"):
        h = value[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            try:
                return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            except ValueError:
                return None
        return None
    if value.startswith("rgb("):
        nums = re.findall(r"[\d.]+", value)
        if len(nums) >= 3:
            return int(float(nums[0])), int(float(nums[1])), int(float(nums[2]))
    return None


def is_watermark_fill(value: str | None) -> bool:
    if not value:
        return False
    rgb = parse_fill(value)
    if rgb is None:
        return False
    return min(rgb) >= NEAR_WHITE_MIN


def strip_watermark(text: str) -> tuple[str, int, list[str]]:
    """删掉水印元素。返回 (新文本, 删掉的元素数, 删掉元素的说明)。"""
    matches = list(TAG_RE.finditer(text))
    # 记录每个元素要删除的区间
    remove: list[tuple[int, int]] = []
    stack: list[dict] = []          # 未闭合的 <g>
    removed_notes: list[str] = []
    count = 0

    for m in matches:
        closing, name, attrs, self_closing = m.group(1), m.group(2), m.group(3), m.group(4)
        if closing:
            if name == "g" and stack:
                node = stack.pop()
                if node["remove"]:
                    remove.append((node["start"], m.end()))
                    removed_notes.append(f'<g fill="{node["fill"]}">…</g>')
                    count += 1
            continue
        own = FILL_RE.search(attrs)
        own_fill = own.group(1) if own else None
        inherited = stack[-1]["fill"] if stack else None
        effective = own_fill or inherited
        watermark = is_watermark_fill(effective)
        if name == "g":
            stack.append({
                "start": m.start(),
                "fill": own_fill or inherited,
                "remove": watermark,
            })
            if watermark and self_closing:
                remove.append((m.start(), m.end()))
                removed_notes.append(f'<g fill="{own_fill}"/>')
                count += 1
                stack.pop()
        else:  # path
            # 已经落在要整块删掉的 <g> 里，就不用再单独记一次了。
            if any(node["remove"] for node in stack):
                continue
            if watermark:
                end = m.end()
                if not self_closing:
                    # <path>…</path>：找到配对的结束标签
                    close = re.compile(r"</path\s*>", re.I).search(text, m.end())
                    end = close.end() if close else m.end()
                remove.append((m.start(), end))
                removed_notes.append(f'<path fill="{own_fill or inherited}"/>')
                count += 1

    if not remove:
        return text, 0, []
    # 区间可能嵌套（外层 <g> 与内层元素），先合并再切片，否则会切出乱序的碎片。
    remove.sort()
    merged: list[tuple[int, int]] = []
    for start, end in remove:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    out = []
    prev = 0
    for start, end in merged:
        out.append(text[prev:start])
        prev = end
    out.append(text[prev:])
    return "".join(out), count, removed_notes


def has_vector_path(data: bytes) -> bool:
    """这个 SVG 里有没有真正的矢量轮廓。

    汉典个别实例把 PNG 以 base64 塞在 ``<image xlink:href="data:image/png;base64,…">`` 里，
    那是位图不是字形。判定办法：找带非空 ``d`` 的 ``<path>``，
    或带非空 ``points`` 的 ``<polygon>`` / ``<polyline>``。
    解析失败时返回 True——宁可留给下游 ``check_glyphs.py`` 报错，
    也不在这里悄悄把一个可能正常的字形吞掉。
    """
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return True
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "path" and (element.get("d") or "").strip():
            return True
        if tag in ("polygon", "polyline") and (element.get("points") or "").strip():
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="洗掉汉典字形里的水印层")
    parser.add_argument("--manifest", required=True, type=Path,
                        help="抓取脚本产出的 manifest.json")
    parser.add_argument("--out", required=True, type=Path, help="清洗后字形的落盘目录")
    parser.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    parser.add_argument("--glyph-id-offset", type=int, default=0,
                        help="条目号从 offset+1 开始。同一层里已有别的来源占用了前一段"
                             "条目号时用这个错开——甲骨层 JGW 占 1..1203，"
                             "汉典那批从 1204 起。")
    args = parser.parse_args(argv)

    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"找不到清单：{manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    src_dir = manifest_path.parent
    out_dir = args.out.resolve()

    glyphs = manifest.get("glyphs") or []
    if not glyphs:
        raise SystemExit("清单里没有字形")

    touched = 0
    removed_paths = 0
    unchanged = 0
    raster_skipped: list[str] = []
    empty_skipped: list[str] = []
    new_glyphs = []
    for item in glyphs:
        rel = str(item.get("file") or "")
        src = src_dir / rel
        if not src.is_file():
            raise SystemExit(f"清单里的文件不存在：{rel}")
        raw = src.read_bytes()
        # 位图闸门：不是矢量轮廓的一律不入库（理由见模块 docstring）。
        if not has_vector_path(raw):
            raster_skipped.append(
                f"{rel}（{item.get('modern_char') or '?'}）")
            continue
        text = raw.decode("utf-8")
        cleaned, count, _notes = strip_watermark(text)
        if count == 0:
            unchanged += 1
            out_bytes = raw
        else:
            touched += 1
            removed_paths += count
            out_bytes = cleaned.encode("utf-8")
            # 清洗后必须仍是合法 SVG，且不能再有水印色
            try:
                ET.fromstring(out_bytes)
            except ET.ParseError as exc:
                raise SystemExit(f"{rel}: 清洗后不是合法 SVG：{exc}") from exc
            if any(is_watermark_fill(
                    (FILL_RE.search(a).group(1) if FILL_RE.search(a) else None))
                   for _c, _n, a, _s in TAG_RE.findall(cleaned)):
                raise SystemExit(f"{rel}: 清洗后仍有水印色元素")
        if not args.dry_run:
            (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
            (out_dir / rel).write_bytes(out_bytes)
        new = dict(item)
        new["local_sha256"] = sha256_bytes(out_bytes)
        new["source_sha256"] = item.get("source_sha256") or sha256_bytes(raw)
        # 出处说明重新拆一遍：器名与编号分列，时代补齐。
        #
        # **题记格式按书体走。** 楚文字与傳抄古文的题记没有时代，结构是
        # 「现代字 + 文献代号 + [篇名] + 位置」，用通用的「时代 + 编号」切法会错：
        # 「秦99.3反」里的「秦」是文献代号不是时代，会被当成时代；
        # 「香中大.4」这种三字代号也会被整段留在器名里。
        # 所以按书体分派到各自的解析器（parse_caption_for_kind）。
        kind = str(manifest.get("kind") or "")
        parts = parse_caption_for_kind(kind, str(item.get("variant") or ""),
                                       str(item.get("modern_char") or ""))
        new["period"] = parts["era"]
        new["source_book"] = parts["artifact"]
        new["source_number"] = parts["number"]
        if parts.get("book_code"):
            new["book_code"] = parts["book_code"]
        # 题记里代号的**后面那一段**。两层含义不同，分开存：
        # - 楚文字：篇名（「郭.語」的「語」）。换全称时会丢掉它，
        #   而它决定了「哪个文本的哪个字」——出处精度要留住这一层。
        # - 傳抄古文：尾注，是**该字形在来源书里所标注的引书名**
        #   （如「汗3.34說」里的「說」指《說文》），
        #   与 `source_book`（摹本底本 / 传抄本）是**两个层级**，不能混栏。
        #
        # **pop 要无条件做。** 放在 `if parts.get("part")` 里面的话，
        # 一旦改了解析规则（尾注不再提取），抓取阶段留下的旧字段就会残留，
        # 库里凭空多出一列语义串味的 `book_part`。
        if kind == "chuanchao":
            if parts.get("part"):
                new["source_cited_book"] = parts["part"]
            else:
                new.pop("source_cited_book", None)
            new.pop("book_part", None)
        elif parts.get("part"):
            new["book_part"] = parts["part"]
        else:
            new.pop("book_part", None)
        if count:
            new["modifications"] = (
                f"removed {count} near-white 汉典 watermark element(s)"
            )
        # 空字形闸门：洗完水印后如果一个字形都不剩，这个文件就不是字形。
        # 实测汉典有个别实例的 SVG 里**只有**那层近白水印、没有笔画
        # （如金文「𧾀」二十七年上守趞戈 集成11374），洗完就是空壳。
        if not has_vector_path(out_bytes):
            empty_skipped.append(
                f"{rel}（{item.get('modern_char') or '?'}）")
            continue
        new_glyphs.append(new)

    print(f"字形        : {len(glyphs)}")
    print(f"含水印      : {touched}（删掉 {removed_paths} 个元素）")
    print(f"无水印      : {unchanged}")
    if raster_skipped:
        print(f"位图剔除    : {len(raster_skipped)}（汉典给的是 PNG，不是矢量轮廓）")
        for note in raster_skipped[:10]:
            print(f"              {note}")
    if empty_skipped:
        print(f"空字形剔除  : {len(empty_skipped)}（洗掉水印后一个字形都不剩）")
        for note in empty_skipped[:10]:
            print(f"              {note}")
    if args.dry_run:
        print("dry-run：未写入任何文件")
        return 0

    manifest = dict(manifest)
    # 层键要确定：并发抓取时完成顺序随网络抖动而变。这里按
    # 「现代字码位 → 汉典字形编号 → 文件名」排序后重排，编号与抓取过程无关。
    new_glyphs.sort(key=lambda g: (str(g.get("unicode") or ""),
                                   str(g.get("source_id") or ""),
                                   str(g.get("file") or "")))
    for index, glyph in enumerate(new_glyphs, 1 + max(0, args.glyph_id_offset)):
        glyph["glyph_id"] = index
    manifest["glyphs"] = new_glyphs
    manifest["modifications"] = {
        "rule": "删除有效填充色接近纯白（各通道 >= 235）的 <g>/<path> 元素",
        "reason": "汉典字形里的近白色角标水印，不是字形的一部分",
        "license_basis": "汉典以 CC0 1.0 释出，无附加条件",
    }
    if raster_skipped:
        manifest["raster_gate"] = {
            "rule": "剔除没有矢量轮廓（<path d> / <polygon points>）的实例",
            "reason": "汉典个别实例把 PNG 以 base64 塞进 <image>，是位图不是矢量字形",
            "skipped": raster_skipped,
        }
    if empty_skipped:
        manifest["empty_gate"] = {
            "rule": "剔除洗掉水印后一个字形都不剩的实例",
            "reason": "这类上游文件里只有近白水印、没有笔画，洗完是空壳，不是字形",
            "skipped": empty_skipped,
        }
    manifest["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"写出       : {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
