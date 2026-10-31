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

**按文献代号筛选（``--books-csv``）。** 一层只收某一类材料时，用它把不该进这一层的
字形**拦在门外但不删掉**：被拦下的字形连同登记表（现代字、题记、上游 URL、sha256、
未收录原因）写到 ``--staged-out`` 指定的目录，供将来的层直接取用。
「未收录」不是「没有出处」——它们照样有出处，只是归属别的书体层
（楚文字层里的秦简条目、傳抄古文条目）。

**为什么要有这一步。** 汉典的「楚系簡帛」栏目里混着秦系简帛、傳抄古文与砖石刻文字：
它们在汉典归在同一个栏目下，但**不是楚文字**。不加闸门，这一层就会变成杂烩，
而且与将来的 ``qinwenzi`` / ``chuanchao`` 层重复收录同一批摹本。
筛选按**文献代号**做（代号来自题记，如「郭」「包」「磚」），对照表在层目录的
``books.csv`` 里；表里没有登记的代号一律**不收**并单独报出来——
新代号出现时不会被悄悄放进来。

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
import csv
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


def load_books(path: Path, include_column: str) -> tuple[set[str], dict[str, str]]:
    """读文献代号对照表，返回（收录的代号集合，未收录原因）。

    表结构（列名固定）：``code`` / ``corpus_full`` / ``script_belong`` / ``include`` /
    ``reason``。``include`` 取 yes/true/1/是 的算收录。

    **表里没有的代号不收。** 新代号出现时它会被拦下并单独报出来，
    不会被悄悄放进层里——判断「这是什么材料」不能靠默认值。
    """
    included: set[str] = set()
    reasons: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            code = (row.get("code") or "").strip()
            if not code:
                continue
            flag = str(row.get(include_column) or "").strip().lower()
            reason = (row.get("reason") or "").strip()
            belong = (row.get("script_belong") or "").strip()
            if flag in ("yes", "true", "1", "是", "y"):
                included.add(code)
            else:
                reasons[code] = reason or (f"归属 {belong}，不进本层" if belong
                                           else "对照表标为不收录")
    return included, reasons


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="合并多个汉典字形清单")
    parser.add_argument("--manifest", required=True, action="append", type=Path,
                        help="清单 JSON，可重复给；后面的覆盖前面的")
    parser.add_argument("--out", required=True, type=Path, help="输出目录")
    parser.add_argument("--keep-multi", action="store_true",
                        help="同一现代字保留多个实例（键 = 现代字码位 + 汉典字形编号）。"
                             "金文/隶书层的一字多形用这个模式；默认每个现代字只留一个实例。")
    parser.add_argument("--books-csv", type=Path, default=None,
                        help="文献代号对照表（CSV）。**表里登记为收录的代号才进这一层**；"
                             "表里没有的代号一律不收并单独报出来。")
    parser.add_argument("--include-column", default="include",
                        help="对照表里判定收录的列名（默认 include，取 yes/true/1/是）")
    parser.add_argument("--staged-out", type=Path, default=None,
                        help="未收录字形的落盘目录：字形副本 + staged.csv 登记表。"
                             "不给就只报数量，不另存（**不删原始文件**）。")
    parser.add_argument("--staged-csv-out", type=Path, default=None,
                        help="把未收录登记表再写一份到这个路径（如 glyphs/chu/staged.csv）。"
                             "**只登记表，字形本体不进层**——将来另立层时按登记表回源取用即可。")
    parser.add_argument("--clean", action="store_true",
                        help="合并前先清空输出目录里的旧字形文件。输出目录是**本轮合并的产物目录**，"
                             "上一轮的残留会让「同名不同内容」的判定把旧文件当成这一轮的字形——"
                             "判错一次就是一次假冲突（反过来说，把旧文件当成同一件字形放行更糟："
                             "两条记录会指向同一个文件）。")
    args = parser.parse_args(argv)

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.clean:
        removed = 0
        for old in out_dir.glob("*.svg"):
            old.unlink()
            removed += 1
        if removed:
            print(f"清理输出目录: 删除 {removed} 个上一轮的字形文件（--clean）")

    base: dict = {}
    merged: dict[str, dict] = {}
    sources: list[str] = []
    raster_skipped: list[str] = []
    conflicts: list[dict] = []
    kinds: set[str] = set()

    included_codes: set[str] | None = None
    book_reasons: dict[str, str] = {}
    if args.books_csv:
        books_path = args.books_csv.resolve()
        if not books_path.is_file():
            raise SystemExit(f"找不到文献对照表：{books_path}")
        included_codes, book_reasons = load_books(books_path, args.include_column)
        print(f"文献对照表  : {books_path.name}（收录 {len(included_codes)} 个代号）")

    # 未收录的字形：**不删**，登记下来留给将来的层。
    staged: list[dict] = []
    staged_dir = args.staged_out.resolve() if args.staged_out else None
    if staged_dir:
        staged_dir.mkdir(parents=True, exist_ok=True)

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
            item = dict(item)
            raw_unicode = str(item.get("unicode") or "").strip()
            # **空 unicode = 临时身份条目**：现代字身份未定，只有私用區槽位这一条线索。
            # 注意**不能**直接把空串交给 normalize_cp——那会补成 "000000"，
            # 变成一个根本不存在的码位（U+000000），比拿 PUA 码位冒充还糟。
            key = normalize_cp(raw_unicode) if raw_unicode else ""
            if not key:
                # 槽位**不是漢字碼位**，不能写进 unicode 列（照甲骨层 glyph_id 380/916
                # 的先例：modern_char=""、unicode=""）。
                # 合并的键改用槽位（"slot:<字体号>_<码位>"），只作去重与排序用，
                # **不进 index.csv 的 unicode 列**。
                slot = str(item.get("modern_char_slot") or "").strip()
                if not slot:
                    raise SystemExit(
                        f"{path}: 有一条记录既缺 unicode 也缺 modern_char_slot——"
                        "临时身份条目必须留 modern_char_slot 作为身份线索")
                key = f"slot:{slot}"
                item["unicode"] = ""
                item["identity_key"] = key
            else:
                item["unicode"] = key
            # 逐条补上**本清单自己的**许可与署名。合并后的清单顶层字段只来自
            # 第一份清单，而入库脚本是「逐条取 attribution，缺了才用顶层的」——
            # 不在这里补上，别的来源的字形会被安上第一份清单的署名。
            for field in ("license", "license_url", "attribution", "source_dataset"):
                if not str(item.get(field) or "").strip():
                    value = str(data.get(field) or "").strip()
                    if value:
                        item[field] = value
            # 层也要逐条带：一份清单里可能混着骨架件（上游逐字节副本）与描摹件，
            # 顶层只有一个 layer 字段会把其中一种盖错。
            if not str(item.get("layer") or "").strip():
                item["layer"] = str(data.get("layer") or "skeleton").strip() or "skeleton"
            rel = str(item.get("file") or "").strip()
            if not rel:
                raise SystemExit(f"{path}: {key} 缺 file 字段")
            src = (root / rel).resolve()
            if not src.is_file():
                raise SystemExit(f"{path}: {key} 的字形文件不存在：{src}")
            # 收录判定：**先看文献代号，再谈别的**。代号不在收录集合里的，
            # 连字形文件都不往本层拷——它们属于别的书体层（秦系、傳抄古文等）。
            if included_codes is not None:
                code = str(item.get("book_code") or "").strip()
                if code and code in included_codes:
                    pass
                else:
                    reason = book_reasons.get(code) or (
                        "题记里没有文献代号" if not code else
                        f"代号「{code}」未登记在文献对照表里")
                    staged.append({
                        "modern_char": item.get("modern_char") or "",
                        "unicode": key,
                        "book_code": code,
                        "caption": item.get("variant") or "",
                        "source_url": item.get("source_url") or "",
                        "source_sha256": item.get("source_sha256") or "",
                        "source_references": item.get("source_references") or "",
                        "reason": reason,
                        "file": src.name,
                    })
                    if staged_dir:
                        shutil.copyfile(src, staged_dir / src.name)
                    continue
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
                merge_key = f"{key}\t{source_id}"
            else:
                merge_key = key
            prev = merged.get(merge_key)
            if prev is not None:
                # **同一个键来了两条记录**——这在混合层里是**要出事的**：
                # 两条记录指向同一个「现代字 + 字形」，层里只能留一条。
                #
                # 规则：**漢典的矢量件優先**（layer=skeleton），小學堂的描摹件
                # （layer=outline）只在漢典沒有這條時才進來。這是「重疊五層保留
                # 漢典矢量為主源、小學堂補缺口」的定案——不能靠清單順序決定。
                #
                # 舊行為是「後覆蓋前」，那會讓清單順序悄悄決定層里留的是哪家的字形。
                prev_layer = str(prev.get("layer") or "skeleton")
                new_layer = str(item.get("layer") or "skeleton")
                if prev_layer == "skeleton" and new_layer == "outline":
                    conflicts.append({
                        "key": merge_key, "unicode": key, "source_id": source_id,
                        "kept": "skeleton", "dropped": "outline",
                        "kept_source": prev.get("source_dataset", ""),
                        "dropped_source": item.get("source_dataset", ""),
                        "reason": "漢典矢量件優先；小學堂描摹件只補缺口",
                    })
                    merged[merge_key] = prev      # 保留漢典那條，不覆蓋
                    continue
                conflicts.append({
                    "key": merge_key, "unicode": key, "source_id": source_id,
                    "kept": new_layer, "dropped": prev_layer,
                    "kept_source": item.get("source_dataset", ""),
                    "dropped_source": prev.get("source_dataset", ""),
                    "reason": "同一键两条记录，按清单顺序后者覆盖前者",
                })
            merged[merge_key] = item

    # 合并进来的必须都是同一书体：金文和隶书混在一起的话，合并出来的清单
    # 会被整个导进第一份清单对应的层里。
    if len(kinds) > 1:
        raise SystemExit(f"要合并的清单书体不一致：{sorted(kinds)}")

    # 排序键：临时身份条目没有 unicode，用它的 identity_key（槽位）排——
    # 否则空 unicode 会把它们全排到最前面，层里的顺序就没有意义了。
    glyphs = sorted(merged.values(),
                     key=lambda g: (g.get("identity_key") or g["unicode"],
                                    str(g.get("source_id") or "")))
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
    if conflicts:
        # 撞键必须留痕：层里只留了一条，另一条去哪了要说得清。
        base["merge_conflicts"] = {
            "rule": "同一「现代字 + 字形」键来了多条记录：漢典矢量件（layer=skeleton）優先，"
                    "小學堂描摹件（layer=outline）只補缺口；其余按清单顺序后者覆盖前者",
            "count": len(conflicts),
            "conflicts": conflicts,
        }
    (out_dir / "manifest.json").write_text(
        json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if included_codes is not None:
        # 未收录的字形登记成一张表：**不删，也不发布**。
        # 「未收录」必须能逐条追问「为什么」——所以表里带原因与上游指针。
        by_code: dict[str, int] = {}
        for row in staged:
            by_code[row["book_code"] or "(无代号)"] = \
                by_code.get(row["book_code"] or "(无代号)", 0) + 1
        base["staged_note"] = {
            "rule": "按文献代号对照表筛选：不进本层的字形不删除，登记在 staged.csv",
            "excluded_count": len(staged),
            "excluded_by_code": by_code,
        }
        (out_dir / "manifest.json").write_text(
            json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staged_fields = [
            "modern_char", "unicode", "book_code", "caption",
            "source_url", "source_sha256", "source_references", "reason", "file"]

        def write_registry(path: Path) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=staged_fields)
                writer.writeheader()
                for row in staged:
                    writer.writerow(row)

        # 登记表随层再写一份：字形本体不发布，登记表要能查。
        if args.staged_csv_out:
            write_registry(args.staged_csv_out.resolve())
            print(f"未收录登记表  : {args.staged_csv_out}")
        if staged_dir:
            write_registry(staged_dir / "staged.csv")
            (staged_dir / "README.md").write_text(
                "# 未收录字形登记\n\n"
                f"这些字形来自汉典「楚系簡帛」栏目，但**不属于楚文字**：{len(staged)} 个。\n\n"
                "**它们没有被删除**，只是没有发布到 `glyphs/chu/`——\n"
                "归属别的书体层（秦系简帛、傳抄古文、砖石刻），留给将来的层直接取用。\n\n"
                "`staged.csv` 逐条记着：现代字、码位、文献代号、题记、上游 URL、\n"
                "上游原件 sha256、摹本底本与页.行（`source_references`）、以及未收录原因。\n",
                encoding="utf-8", newline="\n")

    print(f"输入清单      : {len(sources)} 份（{'、'.join(sources)}）")
    print(f"合并后字形    : {len(glyphs)}")
    if conflicts:
        print(f"撞键          : {len(conflicts)}（详见清单的 merge_conflicts）")
        for c in conflicts[:5]:
            print(f"    {c['unicode']} {c['source_id']}  留 {c['kept']} / 棄 {c['dropped']}"
                  f"  — {c['reason']}")
    if raster_skipped:
        print(f"位图剔除      : {len(raster_skipped)}")
    if included_codes is not None:
        print(f"未收录（不删）: {len(staged)}")
        for code, n in sorted(base["staged_note"]["excluded_by_code"].items(),
                              key=lambda kv: -kv[1]):
            reason = next((r["reason"] for r in staged
                           if (r["book_code"] or "(无代号)") == code), "")
            print(f"    {code:8s} {n:5d}  {reason[:44]}")
        if staged_dir:
            print(f"未收录落盘    : {staged_dir}")
    print(f"输出目录      : {out_dir}")
    print(f"清单          : {out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
