#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从**已入库的层**重建一份合并器清单（漢典侧那一半）。

**为什么需要它。** 小学堂批次是**增量**：甲骨/金文/隶书/楚文四层已经入库，
新抓来的小学堂字形要**并进已有的层**。而入库脚本是「整层替换」——
条目号是整层内容的函数（见 AGENTS.md），层里增删字形会整体重排，
所以新层必须由「旧记录 + 新记录」重新合出来。

合并器要的两份清单是「小学堂的」和「漢典的」。漢典那份原本是抓取时落下的
``tmp/zdic/<层>/manifest.json``，但那些临时目录早被清掉了。
**重新抓一遍漢典要再下十几万个 SVG**——没必要：层里已经有这些字形，
出处也逐条写在 ``glyphs/provenance/<层>.jsonl`` 里。

所以这个脚本把「层里已有的东西」重新拼成清单：
``index.csv``（现代字 / 码位 / 文献 / 来源编号 / 字形文件）+
``provenance/<层>.jsonl``（许可 / 署名 / 底本页.行 / 上游校验值）→ 清单。

用法::

    python src/rebuild_layer_manifest.py --layer clerical --out tmp/zdic/clerical-rebuilt
    python src/rebuild_layer_manifest.py --layer chu --out tmp/zdic/chu-rebuilt
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# 「異體字 + 出處簡號」的切法与小学堂清单共用同一套规则——
# 切错了会把「上(1)」切成「上」，文献桶就会从 26 个退化成 25 个。
from build_xxt_manifest import strip_variant  # noqa: E402

# 清单里要带的字段。合并器与入库脚本用到的那些。
FIELDS = (
    "file", "modern_char", "unicode", "period", "variant",
    "source_book", "book_code", "book_part", "source_number", "source_id",
    "source_path", "source_url", "source_page_url",
    "source_sha256", "local_sha256", "source_base_pages", "source_references",
    "retrieved_at", "layer", "license", "license_url", "attribution",
    "source_dataset", "modifications",
)


def load_provenance(path: Path) -> dict[int, dict]:
    """glyph_id → provenance 记录。

    一层的 provenance 里可能有同一个 glyph_id 的多条记录（骨架件 + 派生件，
    比如甲骨的 ``layer=outline``）。这里**按 layer 分开取**，索引里的行对应的是
    ``skeleton``（层目录直接下的字形）。
    """
    by_id: dict[int, dict] = {}
    if not path.is_file():
        return by_id
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        gid = rec.get("glyph_id")
        if gid is None:
            continue
        if rec.get("layer") in (None, "", "skeleton"):
            by_id[int(gid)] = rec
    return by_id


def resolve_book_code(short: str, codes: list[str]) -> str:
    """出處簡號 → 文獻代号（**最长前缀**匹配）。

    合并器的收录闸门按 ``book_code`` 判，所以这一列的粒度必须与小学堂那边一致：
    小学堂的清单里 ``book_code`` 是**文献代号**（「郭」「包」这样的简号），
    不是带编号的整条出處簡號（「郭.老甲.4」）。重建清单要按同一口径切，
    否则同一件材料在两边的代号不同，闸门会把整层挡掉。
    """
    best = ""
    for c in codes:
        if short.startswith(c) and len(c) > len(best):
            best = c
    return best


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="从已入库的层重建合并器清单")
    ap.add_argument("--layer", required=True, help="层名（oracle / bronze / clerical / chu）")
    ap.add_argument("--index", type=Path, default=None, help="层目录下的 index.csv")
    ap.add_argument("--provenance", type=Path, default=None, help="provenance/<层>.jsonl")
    ap.add_argument("--books", type=Path, default=None,
                    help="层的文献对照表：用来把出處簡號切成**文献代号**（收录闸门按它判）")
    ap.add_argument("--out", required=True, type=Path, help="输出目录（清单写这里）")
    args = ap.parse_args(argv)

    index_path = args.index or (ROOT / "glyphs" / args.layer / "index.csv")
    prov_path = args.provenance or (ROOT / "glyphs" / "provenance" / f"{args.layer}.jsonl")
    if not index_path.is_file():
        raise SystemExit(f"找不到 index.csv：{index_path}")
    if not prov_path.is_file():
        raise SystemExit(f"找不到 provenance：{prov_path}")

    prov = load_provenance(prov_path)
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # 文献代号表：收录闸门按 book_code 判，粒度要与小学堂那边一致
    book_codes: list[str] = []
    if args.books and args.books.is_file():
        with args.books.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                code = (row.get("code") or "").strip()
                if code:
                    book_codes.append(code)
        book_codes.sort(key=len, reverse=True)

    glyphs: list[dict] = []
    missing = 0
    with index_path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            gid = int(row["glyph_id"])
            p = prov.get(gid, {})
            # 字形文件：清单所在目录 → 层目录的相对路径
            rel = Path("../../..") / "glyphs" / args.layer / row["file"]
            short = row.get("source_book", "")
            book_code = p.get("book_code") or ""
            if not book_code and book_codes:
                book_code = resolve_book_code(short, book_codes)
            if not book_code:
                book_code = short

            # **文献代号要带册次**（「上(1)」「上(2)」不能并成「上」）。
            #
            # 层里的 ``source_book`` 记的是**全称**（导入时从对照表换的），
            # 直接拿它去对照表里查是查不到的——全称不是代号。
            # 代号要从**题记原文**（``variant`` = 異體字 + 出處簡號）切出来：
            # 去掉異體字前缀得到出處簡號（「上(1).䊷.22」），再按最长前缀
            # 取文献代号（「上(1)」）。少了这一步，文献桶会从 26 个退化成 25 个
            # （上博藏戰國楚竹書的（一）（二）两册被并成一册）。
            variant = row.get("variant", "") or p.get("variant", "")
            ref = strip_variant(variant, book_codes) if (variant and book_codes) else ""
            fine_code = resolve_book_code(ref, book_codes) if ref else ""

            item = {
                "file": str(rel).replace("\\", "/"),
                "modern_char": row.get("modern_char", ""),
                "unicode": (row.get("unicode") or "").strip(),
                "period": row.get("period", ""),
                "variant": variant,
                # **source_book 放代号**：入库脚本按它去对照表换全称。
                # 放全称会换不回来（上博那两册就是活例子）。
                "source_book": fine_code or short,
                "book_code": book_code,
                # 篇名（「郭.語」「上(1).孔」里的「語」「孔」）：层里单独一列，
                # 重建时必须带回来，否则导入会把篇名丢掉。
                "book_part": row.get("book_part", "") or p.get("book_part", ""),
                "source_number": row.get("source_number", ""),
                "source_id": row.get("source_id", ""),
                "source_path": p.get("source_path", "") or row.get("source_path", ""),
                "source_url": p.get("source_url", "") or row.get("source_url", ""),
                "source_page_url": p.get("source_page_url", ""),
                # 两个 sha256：local 是层里这个文件的校验值，source 是上游原件的。
                "source_sha256": p.get("source_sha256", ""),
                "local_sha256": row.get("sha256", "") or p.get("sha256", ""),
                "source_base_pages": p.get("source_base_pages", ""),
                "source_references": p.get("source_references", ""),
                "retrieved_at": p.get("retrieved_at", ""),
                "layer": p.get("layer", "skeleton") or "skeleton",
                "license": p.get("license", ""),
                "license_url": p.get("license_url", ""),
                "attribution": p.get("attribution", ""),
                "source_dataset": p.get("source_dataset", ""),
                "modifications": p.get("modifications", ""),
            }
            if not item["license"]:
                missing += 1
            glyphs.append(item)

    manifest = {
        "script": args.layer,
        "kind": args.layer,
        "layer": "skeleton",
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "attribution": "",
        "source_dataset": f"已入库层 {args.layer}（重建清单）",
        "generated_at": "",
        "glyphs": glyphs,
        "merge_note": "由 src/rebuild_layer_manifest.py 从层里的 index.csv + provenance 重建；"
                      "字形文件即层里那一份，没有重新下载。",
    }
    out_path = out_dir / "manifest.json"
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8", newline="\n")
    print(f"{args.layer}: {len(glyphs)} 条 → {out_path}")
    if missing:
        print(f"  ⚠️ {missing} 条缺 license（provenance 里没有对应记录？）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
