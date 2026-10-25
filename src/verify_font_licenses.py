#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐条款核验候选字体的 OFL 许可文本，产出可复核的证据表。

用法::

    python src/verify_font_licenses.py --license-dir glyphs/kaishu \
        [--reference src/licenses/OFL-1.1-official.txt] [--markdown]

**为什么要有这个脚本。** 「这个字体的许可是不是真的 OFL 1.1」不能靠记忆，
也不能靠「文件名就叫 OFL.txt」。这个脚本把四件事做成机器可查的：

1. **正文逐条款比对**：把上游 OFL.txt 的正文按 1)–5) 切成六段，
   逐段与 SIL 官方 OFL 1.1 原文比相似度（difflib），
   每一段都要达到阈值才算「是官方 OFL 1.1 正文」。
2. **RFN 检查（许可抬头）**：官方 OFL 1.1 的第 3 条要求「改作不得使用被保留的字体名」。
   抬头里若没有 ``with Reserved Font Name`` 行，就说明该字体**没有保留字体名**，
   改作层可以用自己的名字分发。
3. **RFN 检查（字体二进制 name 表）**：**只看 OFL.txt 会漏。**
   OFL 1.1 把「Reserved Font Name」定义为「版权声明里写明的名字」，
   而字体二进制的 name 表 copyright 字段**也算版权声明**。
   实测 `Noto Sans SC` / `Noto Sans TC` / `Noto Sans JP` 的 `OFL.txt` 抬头里
   **没有** RFN 声明，但字体 name 表的 copyright 写着
   ``(c) 2014-2021 Adobe (http://www.adobe.com/), with Reserved Font Name 'Source'.``
   ——只看许可文件会漏判，所以这里用 ``--font`` 把字体本体一起查。
   （`Noto Serif SC` / `Noto Serif TC` / `Noto Serif JP` 的 name 表**没有**这句。）
4. **版权行摘录**：OFL 第 2 条要求每份副本都带版权声明与许可全文，
   所以版权行要一字不差地抄进 attribution。

产出：一份 Markdown 表（可直接贴进方案文档）+ 一份 JSON（机读）。
本脚本只读文件，不改任何东西。
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

# 官方 OFL 1.1 正文与上游文本的相似度阈值。
# 逐条款比对必须几乎逐字相同：相似度低于 0.99 就说明条款被改过或缺了，
# 那就不能当「官方 OFL 1.1」用。
CLAUSE_THRESHOLD = 0.99

RFN_RE = re.compile(r"with\s+Reserved\s+Font\s+Name\s*(?P<names>[^\n]*)", re.IGNORECASE)
COPYRIGHT_RE = re.compile(r"^Copyright\b.*$", re.MULTILINE)
BODY_MARKER = "SIL OPEN FONT LICENSE Version 1.1"

# name 表里的 RFN 写法：**必须带 "with"**，否则会命中 OFL 正文里
# "'Reserved Font Name' refers to any names specified as such…" 这句**定义**。
# 那是 OFL 的条款原文，不是声明——每个官方 OFL.txt 里都有这句。
NAME_TABLE_RFN_RE = re.compile(
    r"with\s+Reserved\s+Font\s+Names?\s*[:：]?\s*(?P<names>[^\n]*)", re.IGNORECASE)

# 「排版分隔线」：整行只有 - 或 =（≥3 个）。
# 有些上游把 OFL 原文转成 Markdown，小节标题下面会多一条下划线
# （PREAMBLE / DEFINITIONS / TERMINATION / DISCLAIMER 各一条），
# 标题下的分隔线也可能从 ----- 变成 =====。
# **这属于排版，不是条款**——但正文里的 `-- in part or in whole --`
# 是条款原文，不在行首行尾，**不受影响**。
RULE_LINE_RE = re.compile(r"(?m)^[ \t]*[-=]{3,}[ \t]*$")


def strip_rule_lines(text: str) -> str:
    """删掉整行只有 - 或 = 的排版分隔线。"""
    return RULE_LINE_RE.sub("", text)


def norm(text: str) -> str:
    """归一化空白：比对的是条款文字，不是排版。"""
    return re.sub(r"\s+", " ", text).strip()


def norm_typographic(text: str) -> str:
    """再进一步：先删排版分隔线，再归一化空白。

    两份文本都过这个函数，所以「官方原文自己」与「上游原文」用的是同一把尺子。
    """
    return norm(strip_rule_lines(text))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_body(text: str) -> tuple[str, str]:
    """切成 (抬头, 正文)。正文从 OFL 标题行开始。"""
    idx = text.find(BODY_MARKER)
    if idx < 0:
        return text, ""
    return text[:idx], text[idx:]


def split_clauses(body: str) -> list[str]:
    """按 1)–5) 把正文切成六段。

    段 0 是 PREAMBLE + DEFINITIONS + 条件前言，
    段 1–5 是五条 PERMISSION & CONDITIONS，
    第 5 段尾部还带着 TERMINATION 与 DISCLAIMER。
    """
    marks = list(re.finditer(r"(?m)^(\d)\)\s", body))
    if not marks:
        return [body]
    parts = [body[:marks[0].start()]]
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        parts.append(body[mark.start():end])
    return parts


def compare(reference_body: str, body: str) -> dict:
    """逐条款比对两段正文。

    同时算两个数：
    - `min_similarity`：**只折叠空白**的比对结果（原始排版）；
    - `min_similarity_typographic`：再删掉整行只有 - 或 = 的**排版分隔线**后的结果。

    判定用后者（条款文字逐字相同即算官方 OFL 1.1），
    但前者也一并报出来——**差异不许被藏起来**。
    """
    ref_parts = split_clauses(reference_body)
    parts = split_clauses(body)
    if len(ref_parts) != len(parts):
        return {
            "clause_count_reference": len(ref_parts),
            "clause_count_actual": len(parts),
            "clauses": [],
            "min_similarity": 0.0,
            "min_similarity_typographic": 0.0,
            "identical": False,
            "note": "条款数不同，正文结构不是官方 OFL 1.1",
        }
    rows = []
    for i, (ref, act) in enumerate(zip(ref_parts, parts)):
        raw_ratio = difflib.SequenceMatcher(None, norm(ref), norm(act)).ratio()
        typo_ratio = difflib.SequenceMatcher(
            None, norm_typographic(ref), norm_typographic(act)).ratio()
        rows.append({"clause": i,
                     "similarity": round(typo_ratio, 4),
                     "similarity_raw": round(raw_ratio, 4),
                     "length": len(norm_typographic(act))})
    min_typo = round(min(r["similarity"] for r in rows), 4) if rows else 0.0
    min_raw = round(min(r["similarity_raw"] for r in rows), 4) if rows else 0.0
    note = ""
    if min_raw < CLAUSE_THRESHOLD <= min_typo:
        note = ("差异只在排版分隔线（整行只有 - 或 =）；条款文字逐字相同")
    elif min_typo < CLAUSE_THRESHOLD:
        note = "条款文字本身有差异，不是官方 OFL 1.1 正文"
    return {
        "clause_count_reference": len(ref_parts),
        "clause_count_actual": len(parts),
        "clauses": rows,
        "min_similarity": min_typo,
        "min_similarity_typographic": min_typo,
        "min_similarity_raw": min_raw,
        "identical": all(r["similarity"] >= CLAUSE_THRESHOLD for r in rows),
        "note": note,
    }


def inspect(path: Path, reference_body: str) -> dict:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"file": path.name, "error": "不是 UTF-8 文本（可能是二进制文件下错了名字）"}
    header, body = split_body(text)
    cmp_result = compare(reference_body, body)
    rfn = RFN_RE.findall(header)
    copyrights = [line.strip() for line in COPYRIGHT_RE.findall(header)]
    return {
        "file": path.name,
        "bytes": len(raw),
        "sha256": sha256_file(path),
        "header": norm(header),
        "copyright_lines": copyrights,
        "reserved_font_names": [name.strip() for name in rfn],
        "has_rfn_clause": bool(rfn),
        "body_sha256": hashlib.sha256(
            norm(body).encode("utf-8")).hexdigest(),
        **cmp_result,
    }


def inspect_font(path: Path) -> dict:
    """读字体二进制的 name 表，查出**字体本体**声明的 RFN 与版权行。

    为什么必须查字体本体：OFL 1.1 把 Reserved Font Name 定义为
    「copyright statement(s) 里写明的名字」。字体二进制的 name 表
    copyright 字段就是一份 copyright statement，所以 RFN 可能只写在
    字体里、没写在 OFL.txt 里（Noto Sans 系列就是这样）。

    fontTools 不可用时返回 error，其余检查照常。
    """
    out = {
        "font": path.name,
        "font_bytes": path.stat().st_size,
        "font_sha256": sha256_file(path),
        "family": "",
        "subfamily": "",
        "full_name": "",
        "version": "",
        "copyright": "",
        "name_table_rfn": [],
        "has_name_table_rfn": False,
        "error": "",
    }
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        out["error"] = "fontTools 不可用，跳过 name 表检查"
        return out
    try:
        font = TTFont(str(path), fontNumber=0, lazy=True)
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"读不出字体：{exc!r}"[:200]
        return out
    try:
        names: dict[int, str] = {}
        for rec in font["name"].names:
            if rec.platformID == 3 and rec.langID == 0x409:
                try:
                    names.setdefault(rec.nameID, rec.toUnicode())
                except Exception:  # noqa: BLE001
                    pass
    finally:
        font.close()
    out["family"] = names.get(1, "")
    out["subfamily"] = names.get(2, "")
    out["full_name"] = names.get(4, "")
    out["version"] = names.get(5, "")
    out["copyright"] = names.get(0, "")
    rfn = NAME_TABLE_RFN_RE.findall(out["copyright"])
    out["name_table_rfn"] = [n.strip() for n in rfn]
    out["has_name_table_rfn"] = bool(rfn)
    return out


def to_markdown(rows: list[dict]) -> str:
    out = ["| 文件 | 字节 | 条款文字相似度（最低） | 原始排版相似度（最低） | 是官方 OFL 1.1 正文 | RFN 声明 | 版权行 | sha256 |",
           "|------|------|------------------|--------------------|---------------------|----------|--------|--------|"]
    for r in rows:
        if r.get("error"):
            out.append(f"| `{r['file']}` | — | — | — | — | — | — | {r['error']} |")
            continue
        rfn = "有：" + "、".join(r["reserved_font_names"]) if r["has_rfn_clause"] else "无（未保留字体名）"
        cr = " / ".join(r["copyright_lines"]) or "（未找到）"
        raw = r.get("min_similarity_raw", r["min_similarity"])
        out.append(
            f"| `{r['file']}` | {r['bytes']} | {r['min_similarity']:.4f} | {raw:.4f} | "
            f"{'是' if r['identical'] else '否'} | {rfn} | {cr} | `{r['sha256'][:16]}…` |")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="逐条款核验 OFL 许可文本")
    parser.add_argument("--license-dir", required=True, type=Path,
                        help="装着 OFL.txt 的目录（层目录或采集目录）")
    parser.add_argument("--reference", type=Path,
                        default=Path(__file__).resolve().parent / "licenses" / "OFL-1.1-official.txt",
                        help="SIL 官方 OFL 1.1 原文，默认取 src/licenses/OFL-1.1-official.txt")
    parser.add_argument("--out-json", type=Path, default=None, help="把结果写成 JSON")
    parser.add_argument("--markdown", action="store_true", help="输出 Markdown 表")
    parser.add_argument("--font", nargs="*", default=[], type=Path,
                        help="可选：字体二进制本体（TTF/OTF）。给了就连 name 表一起查 RFN——"
                             "OFL.txt 抬头里没有 RFN 不等于字体没有 RFN")
    args = parser.parse_args(argv)

    if not args.reference.is_file():
        raise SystemExit(f"找不到官方原文：{args.reference}")
    ref_text = args.reference.read_text(encoding="utf-8")
    _ref_header, reference_body = split_body(ref_text)
    if not reference_body:
        raise SystemExit(f"官方原文 {args.reference} 里找不到 OFL 1.1 正文标记")

    # 「*OFL*.txt」已能命中 OFL.txt，追加第二路会把它数两遍——按路径去重。
    files = sorted(set(args.license_dir.glob("*OFL*.txt")) |
                   set(args.license_dir.glob("OFL.txt")))
    if not files:
        raise SystemExit(f"{args.license_dir} 里没有 OFL 文本文件")

    rows = []
    for path in files:
        row = inspect(path, reference_body)
        rows.append(row)
        if row.get("error"):
            print(f"{path.name}: {row['error']}")
            continue
        print(f"{path.name}: 条款文字最低相似度 {row['min_similarity']:.4f} "
              f"（原始排版 {row.get('min_similarity_raw', row['min_similarity']):.4f}，"
              f"逐条款 {'一致' if row['identical'] else '不一致'}），"
              f"RFN {'有' if row['has_rfn_clause'] else '无'}")
        if row["note"]:
            print(f"    ! {row['note']}")

    if args.markdown:
        print()
        print(to_markdown(rows))

    font_rows = []
    for fpath in args.font:
        if not fpath.is_file():
            print(f"字体不存在：{fpath}", file=sys.stderr)
            return 1
        frow = inspect_font(fpath)
        font_rows.append(frow)
        if frow["error"]:
            print(f"字体 {fpath.name}: {frow['error']}")
            continue
        rfn = ("有：" + "、".join(frow["name_table_rfn"])) if frow["has_name_table_rfn"] else "无"
        print(f"字体 {fpath.name}: family={frow['family']!r} version={frow['version']!r}")
        print(f"  name 表 RFN    : {rfn}")
        print(f"  name 表版权行  : {frow['copyright'][:200]}")
        print(f"  字体 sha256    : {frow['font_sha256']}")

    if args.out_json:
        payload = {"license_files": rows, "fonts": font_rows}
        args.out_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        print(f"\n已写出 {args.out_json}")

    bad = [r["file"] for r in rows if not r.get("identical")]
    if bad:
        print(f"\n注意：以下文件正文不是官方 OFL 1.1（不能按 OFL-1.1 入库）：{', '.join(bad)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
