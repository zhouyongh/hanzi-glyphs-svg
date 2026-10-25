#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字形库的统计汇总——把《字形获取与出处 - 过程.md》里的数字算出来。

用法::

    python src/glyph_stats.py            # 逐层打印
    python src/glyph_stats.py --json     # 机读输出（一个 JSON 对象）
    python src/glyph_stats.py --layer chu

**为什么要有这个脚本。** 过程文档里的每个数字都应当能被第三方复算，
而不是只能相信文档。这个脚本只读 `glyphs/provenance/*.jsonl` 与各层 `index.csv`，
不写任何东西；输出与文档 §5.3、§4.4、§9.2 的表一一对应。

「记录条数」与「不同上游原件数」是**两个数**：汉典对异体/别名给的是同一份实例，
一份上游原件会挂在几个现代字名下，所以按 ``source_id`` 去重才是「字形个数」。
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import sys
from pathlib import Path

# 仓库承认的层名。统计本身按 provenance 里的 (script, layer) 分组，
# 这份清单只是给读代码的人一个「现在有哪些层」的参照。
LAYERS = ("oracle", "bronze", "clerical", "seal", "chu", "chuanchao",
          "kaishu", "xingshu", "caoshu", "songti", "songti-tc", "heiti-hk")


def load_records(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def index_rows(repo_root: Path, layer: str) -> list[dict]:
    path = repo_root / "glyphs" / layer / "index.csv"
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def summarize(repo_root: Path, only: str | None = None) -> dict:
    prov_dir = repo_root / "glyphs" / "provenance"
    records: list[dict] = []
    for path in sorted(prov_dir.glob("*.jsonl")):
        records.extend(load_records(path))

    groups: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for rec in records:
        groups[(str(rec.get("script") or ""), str(rec.get("layer") or "skeleton"))].append(rec)

    result: dict = {"total_records": len(records), "layers": []}

    for (script, layer), recs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if only and script != only:
            continue
        licenses = collections.Counter(str(r.get("license") or "") for r in recs)
        source_ids = {r.get("source_id") for r in recs if r.get("source_id")}
        source_urls = {r.get("source_url") for r in recs if r.get("source_url")}
        modern = {r.get("modern_char") for r in recs if r.get("modern_char")}
        periods = {r.get("period") for r in recs if r.get("period")}
        with_period = sum(1 for r in recs if r.get("period"))
        mods = collections.Counter(str(r.get("modifications") or "") for r in recs)
        stamps = sorted(str(r.get("retrieved_at") or r.get("generated_at") or "") for r in recs)
        stamps = [s for s in stamps if s]
        entry = {
            "script": script,
            "layer": layer,
            "records": len(recs),
            "licenses": dict(licenses),
            "distinct_source_ids": len(source_ids),
            "distinct_source_urls": len(source_urls),
            "distinct_modern_chars": len(modern),
            "with_period": with_period,
            "distinct_periods": len(periods),
            "period_buckets": len(periods) + (1 if periods and with_period < len(recs) else 0),
            "book_codes": len({r.get("book_code") for r in recs if r.get("book_code")}),
            "book_parts": sum(1 for r in recs if r.get("book_part")),
            "cited_books": sum(1 for r in recs if r.get("source_cited_book")),
            "with_source_references": sum(1 for r in recs if r.get("source_references")),
            "modifications": dict(mods),
            "retrieved_at_first": stamps[0] if stamps else "",
            "retrieved_at_last": stamps[-1] if stamps else "",
            "index_rows": len(index_rows(repo_root, script)) if layer == "skeleton" else 0,
        }
        result["layers"].append(entry)

    result["licenses_total"] = dict(
        collections.Counter(
            str(r.get("license") or "")
            for rs in groups.values() for r in rs
            if not only or r.get("script") == only))
    return result


def print_text(data: dict) -> None:
    print(f"provenance 记录总数: {data['total_records']}")
    print(f"许可分布            : {data['licenses_total']}")
    for e in data["layers"]:
        print()
        print(f"-- script={e['script']} layer={e['layer']}  {e['records']} 条")
        print(f"   许可              : {e['licenses']}")
        print(f"   不同上游原件(source_id): {e['distinct_source_ids']}")
        print(f"   不同来源 URL          : {e['distinct_source_urls']}")
        print(f"   不同现代字            : {e['distinct_modern_chars']}")
        print(f"   带时代 {e['with_period']} 条、{e['distinct_periods']} 种取值 → "
              f"{e['period_buckets']} 个桶")
        print(f"   文献代号 {e['book_codes']} 种；篇名 {e['book_parts']} 条；"
              f"引书名 {e['cited_books']} 条；摹本出处 {e['with_source_references']} 条")
        print(f"   index.csv 行数        : {e['index_rows']}")
        print(f"   取回时刻              : {e['retrieved_at_first']} .. {e['retrieved_at_last']}")
        print(f"   改动分布              : {e['modifications']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="字形库统计汇总")
    parser.add_argument("--repo-root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--layer", default=None, help="只看某层（oracle/bronze/…）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    data = summarize(args.repo_root.resolve(), args.layer)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_text(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
