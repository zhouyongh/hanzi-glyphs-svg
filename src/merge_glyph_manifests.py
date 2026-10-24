#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并多个汉典字形清单，产出一份统一的清单 + 字形目录。

用法::

    python src/merge_glyph_manifests.py \
        --manifest tmp/zdic/xiaozhuan-clean/manifest.json \
        --manifest tmp/zdic/xz-fix-clean/manifest.json \
        --out tmp/zdic/xiaozhuan-final

**合并语义（默认）：每个现代字只留一个实例，后面的清单覆盖前面的。**

汉典对同一个字可能给多个字形实例（《说文》正篆、古文、籀文、或体……），
一层书体只收一个最典型的。分批抓取时，后面的批次往往是对前面批次的**修正**
（例如正篆优先重抓），所以「后覆盖前」是对的。

**``--keep-multi``：同一现代字保留多个实例，键改成「现代字码位 + 汉典字形编号」。**

金文/隶书层要的是「一字多形」——同一个字在不同器物、不同朝代各有一条字形，
拼起来才是演变链。这时候一个现代字只能留一条的规则会把扩量成果抹掉，
所以要换一套键：``(unicode, source_id)``。同一对键重复出现时仍然是后覆盖前。

两种模式都要保证**层键与抓取过程无关**：合并后统一按
``(unicode, source_id)`` 排序重排 1..N。

**为什么键要统一补零。** 抓取脚本按 ``ord(char)`` 的十六进制给字形文件命名，
宽度不统一：``4E04``（4 位）与 ``0053E1``（6 位）都出现过。合并时如果直接拿
``unicode`` 字段当键，同一个字会出现两条记录（一条 ``4E04``、一条 ``004E04``），
字形重复入库、码位指派时也会漏。本脚本统一把现代字码位补成 6 位大写十六进制，
与 ``glyphs/*/index.csv`` 的 ``unicode`` 列一致。

产出::

    <out>/<字形文件>     各批次字形文件的副本
    <out>/manifest.json  合并后的清单，glyph_id 按 (unicode, source_id) 排序后重排 1..N
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def normalize_cp(raw: str) -> str:
    """现代字码位统一成 6 位大写十六进制。"""
    cp = (raw or "").strip().upper()
    if cp.startswith("U+"):
        cp = cp[2:]
    return cp.rjust(6, "0")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="合并多个汉典字形清单")
    parser.add_argument("--manifest", required=True, action="append", type=Path,
                        help="清单 JSON，可重复给；后面的覆盖前面的")
    parser.add_argument("--out", required=True, type=Path, help="输出目录")
    parser.add_argument("--keep-multi", action="store_true",
                        help="同一现代字保留多个实例（键 = 现代字码位 + 汉典字形编号）。"
                             "金文/隶书层的一字多形用这个模式；默认每个现代字只留一个实例。")
    args = parser.parse_args(argv)

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    base: dict = {}
    merged: dict[str, dict] = {}
    sources: list[str] = []
    raster_skipped: list[str] = []
    kinds: set[str] = set()

    for manifest_path in args.manifest:
        path = manifest_path.resolve()
        if not path.is_file():
            raise SystemExit(f"找不到清单：{path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        sources.append(path.name)
        kind = str(data.get("kind") or "").strip()
        if kind:
            kinds.add(kind)
        if not base:
            base = {k: v for k, v in data.items() if k != "glyphs"}
        gate = data.get("raster_gate")
        if isinstance(gate, dict):
            raster_skipped.extend(gate.get("skipped") or [])
        root = path.parent
        for item in data.get("glyphs", []):
            key = normalize_cp(item.get("unicode") or "")
            if not key:
                raise SystemExit(f"{path}: 有一条记录缺 unicode 字段")
            item = dict(item)
            item["unicode"] = key
            rel = str(item.get("file") or "").strip()
            if not rel:
                raise SystemExit(f"{path}: {key} 缺 file 字段")
            src = (root / rel).resolve()
            if not src.is_file():
                raise SystemExit(f"{path}: {key} 的字形文件不存在：{src}")
            dest = out_dir / Path(rel).name
            if dest.is_file() and dest.read_bytes() != src.read_bytes():
                # 同名不同内容：后来的悄悄盖掉前面的，两条记录都会指向同一个文件。
                raise SystemExit(
                    f"{path}: {key} 的字形 {dest.name} 与前面的批次同名但内容不同，"
                    f"不能合并（否则两条记录指向同一个文件）")
            if not dest.is_file():
                shutil.copyfile(src, dest)
            item["file"] = dest.name
            source_id = str(item.get("source_id") or "").strip()
            if args.keep_multi and not source_id:
                raise SystemExit(
                    f"{path}: {key} 缺 source_id。一字多形模式靠 "
                    f"「现代字码位 + source_id」区分同一个字的多个实例，缺了就并不掉。")
            # 一字多形模式下，同一个现代字的多个实例靠 source_id 区分。
            if args.keep_multi:
                merged[f"{key}\t{source_id}"] = item
            else:
                merged[key] = item

    # 合并进来的必须都是同一书体：金文和隶书混在一起的话，合并出来的清单
    # 会被整个导进第一份清单对应的层里。
    if len(kinds) > 1:
        raise SystemExit(f"要合并的清单书体不一致：{sorted(kinds)}")

    glyphs = sorted(merged.values(), key=lambda g: (g["unicode"], str(g.get("source_id") or "")))
    for index, glyph in enumerate(glyphs, 1):
        glyph["glyph_id"] = index

    base["glyphs"] = glyphs
    base["merge_note"] = "合并清单：" + "、".join(sources)
    if args.keep_multi:
        base["merge_rule"] = ("同一现代字保留多个实例，键 = 现代字码位 + 汉典字形编号；"
                              "同一对键后面的清单覆盖前面的")
    else:
        base["merge_rule"] = "每个现代字只留一个实例，后面的清单覆盖前面的；键为 6 位大写十六进制"
    if raster_skipped:
        base["raster_gate"] = {
            "rule": "剔除没有矢量轮廓（<path d> / <polygon points>）的实例",
            "reason": "汉典个别实例把 PNG 以 base64 塞进 <image>，是位图不是矢量字形",
            "skipped": raster_skipped,
        }
    (out_dir / "manifest.json").write_text(
        json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"输入清单      : {len(sources)} 份（{'、'.join(sources)}）")
    print(f"合并后字形    : {len(glyphs)}")
    if raster_skipped:
        print(f"位图剔除      : {len(raster_skipped)}")
    print(f"输出目录      : {out_dir}")
    print(f"清单          : {out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
