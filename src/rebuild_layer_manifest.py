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
from merge_glyph_manifests import normalize_cp as norm_cp  # noqa: E402

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
    """glyph_id → provenance 记录（**只取骨架件**）。

    一层的 provenance 里可能有同一个 glyph_id 的多条记录（骨架件 + 派生件，
    比如甲骨的 ``layer=outline``）。这里**按 layer 分开取**，索引里的行对应的是
    ``skeleton``（层目录直接下的字形）。

    **只有派生件记录的行不在这里出现**——它们是上一轮并进来的小學堂批次，
    不是漢典侧的东西。重建清单是**合并时的漢典侧基线**，把小學堂那批放进去，
    合并器就会把它判成自己的重复（AGENTS.md 记的实测：20,444 条的层重跑清单得 0 条）。
    甲骨层的 1,203 个 JGW 骨架件**骨架与轮廓各有一条记录**，按骨架记录取，不会被误删。
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


def _own_id(prov: dict, row: dict) -> str:
    """来源**自己**给这个字形的条目号（当层的 ``source_id`` 那一列是空的时候）。

    ``source_id`` 这一列的含义是「这个来源自己怎么认这个字形」：
    漢典那几批写的是「字体号_码位」（两库槽位同构，可以跨库比对）；
    甲骨层的 JGW 批当年写的是空的——它的字形在 JGW 数据集里有自己的条目号
    （``data/svg_polyline/0001.svg``），拿那个当 ``source_id`` 才既唯一又可追。

    **为什么必须补**：合并器的键是「(现代字, 字形键)」。``source_id`` 空着的时候，
    JGW 那 34 个各有两条的字就会撞键——后来的把先来的顶掉，34 个字形直接丢。
    """
    path = str(prov.get("source_path") or "").strip()
    if path:
        return Path(path).stem
    return Path(str(row.get("file") or "")).stem


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
    ap.add_argument("--exclude-font", default=None,
                        help="排除某个字体的字形（逗号分隔多个字体号，如 71）。"
                             "**书体由字体决定，不由材料决定**：漢典的「隶书」栏里"
                             "混着秦系字形（字体 71 = 中研院秦系簡牘文字重文*），"
                             "它们属于秦系层，留在隶书层里就是归类错误。"
                             "字体号取自 source_id 的前缀（「字体号_码位」）。")
    ap.add_argument("--out", required=True, type=Path, help="输出目录（清单写这里）")
    args = ap.parse_args(argv)

    index_path = args.index or (ROOT / "glyphs" / args.layer / "index.csv")
    prov_path = args.provenance or (ROOT / "glyphs" / "provenance" / f"{args.layer}.jsonl")
    if not index_path.is_file():
        raise SystemExit(f"找不到 index.csv：{index_path}")
    if not prov_path.is_file():
        raise SystemExit(f"找不到 provenance：{prov_path}")

    # **按字体剔除**：字体号取自 source_id 的前缀（「字体号_码位」）。
    exclude_fonts = {f.strip() for f in (args.exclude_font or "").split(",") if f.strip()}

    def font_of(sid: str) -> str:
        return sid.split("_")[0] if "_" in sid else ""

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
    derived_only = 0
    skipped_by_font: dict[str, int] = {}
    with index_path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            gid = int(row["glyph_id"])
            p = prov.get(gid, {})
            if not p:
                # **只有派生件记录的行**：上一轮并进来的小學堂批次，不是漢典侧的东西。
                # 重建清单是合并时的漢典侧基线，放进去会被判成自己的重复。
                derived_only += 1
                continue
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
                # 现代字码位一律 **6 位大写十六进制**（AGENTS.md 的口径）。
                # 甲骨层的 JGW 批当年写的是 4 位（"4E00"）——重建时补齐，
                # 合并器重排后写回的 index.csv 就是统一口径了。
                #
                # **空码位要保持空**：``norm_cp("")`` 会补成 "000000"——
                # 那是 U+000000，**根本不存在的码位**，比拿私用區码位冒充还糟。
                # 临时身份条目（甲骨层 JGW 的 380/916）本就该是空的。
                "unicode": norm_cp((row.get("unicode") or "").strip())
                           if (row.get("unicode") or "").strip() else "",
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
                # **字形键**：这一列是「这个来源自己怎么认这个字形」。
                # 漢典那几批是「字体号_码位」（两库槽位同构，可跨库比对）；
                # 甲骨层的 JGW 批当年这列是空的——**空的会让合并器的
                # 「(现代字, 字形键)」键撞车**：JGW 有 34 个字各两条记录，
                # 键相同 → 后来的把先来的顶掉，**34 个字形就丢了**。
                # 所以这里补上**来源自己的条目号**（JGW 的 ``data/svg_polyline/NNNN.svg``）。
                "source_id": (row.get("source_id", "").strip()
                              or _own_id(p, row)),
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
            # **临时身份条目**（现代字身份未定）：unicode 留空，但**必须留
            # ``modern_char_slot``**——合并器拿它当去重键（"slot:<槽位>"），
            # 缺了就直接报错。甲骨层 JGW 的 380/916 两条就是这样：
            # 一条是作者检索未果、一条只留了个历史 PUA 码位，都不是汉字码位。
            # 槽位取**来源自己的条目号**（JGW 的 data/svg_polyline/NNNN.svg），
            # 它唯一、可追，且不含任何冒充汉字的码位。
            if not item["unicode"]:
                slot = (row.get("modern_char_slot") or "").strip() \
                       or str(p.get("modern_char_slot") or "").strip()
                if not slot:
                    slot = "JGW_" + _own_id(p, row)
                item["modern_char_slot"] = slot
                item["identity_confidence"] = (item.get("identity_confidence")
                                               or "pua-slot")
            # **层专有列**（甲骨层 JGW 批那几列）：从 index.csv 带回来。
            # 轮廓层（``glyphs/oracle/outline/``）靠 ``char_form`` 认出哪些行是
            # JGW 的——只有那一批是 polyline 骨架，能转成填充轮廓。
            # 重建清单时丢了它，合并重排之后就再也重建不出轮廓了。
            for col in ("char_form", "encoding_status", "pinyin", "n_points",
                        "n_strokes", "n_source_variants", "identity_confidence"):
                val = (row.get(col) or "").strip() or str(p.get(col) or "").strip()
                if val:
                    item[col] = val
            # **来源 URL 与 DOI**：入档脚本要求每条至少有一个可回源的 URL
            # （``source_url`` / ``source_record_url`` / ``source_artifact_url`` /
            # ``mirror_url`` 任一）。甲骨层的 JGW 批当年记的是
            # ``source_record_url`` + ``source_artifact_url`` + ``mirror_url``，
            # **没有** ``source_url``——这里不带走的话，重建清单里的那 1,203 条
            # 一条 URL 都没有，入库就会报「缺少来源 URL 字段」。
            for col in ("source_url", "source_record_url", "source_artifact_url",
                        "source_page_url", "mirror_url", "source_doi", "mirror_commit",
                        "source_artifact_md5", "alt_caption", "dual_caption",
                        "rendering"):
                val = str(p.get(col) or "").strip()
                if val:
                    item[col] = val
            if exclude_fonts:
                fid = font_of(str(item.get("source_id") or ""))
                if fid and fid in exclude_fonts:
                    skipped_by_font[fid] = skipped_by_font.get(fid, 0) + 1
                    continue
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
    for fid, n in sorted(skipped_by_font.items()):
        print(f"  已剔除字体 {fid} 的 {n} 条（该书体归别的层）")
    if missing:
        print(f"  ⚠️ {missing} 条缺 license（provenance 里没有对应记录？）")
    if derived_only:
        print(f"  已排除 {derived_only} 条只有派生件记录的行（上一轮并进来的小學堂批次）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
