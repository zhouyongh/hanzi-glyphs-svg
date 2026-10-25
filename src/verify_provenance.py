#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 glyphs/provenance/*.jsonl 与实际字形文件是否对得上。

用法::

    python src/verify_provenance.py [--repo-root DIR] [--script oracle] [--quiet]

检查项:

1. 每行都是合法 JSON，且 ``path`` 不重复；
2. 必填字段齐全：``path`` / ``sha256`` / ``license``（AGENTS.md 第 2 条），
   时间字段 ``retrieved_at`` 或 ``generated_at`` 至少一个（派生层用后者），
   以及至少一个来源 URL 字段；
3. ``license`` 的取值必须在允许名单内（ND / NC / 无许可一律不许在库里）——
   导入期有闸门，这里再查一遍，让这条随时可查；
4. ``path`` 指向的文件存在；
5. 文件的 sha256 与记录一致（AGENTS.md 第 1 条：无出处不入库的机器可查版本）；
6. 每层的 ``index.csv`` 与 provenance 对得上：索引里的每个文件都有出处记录、
   sha256 一致，且本层每条骨架层记录都在索引里。

有任何一项不通过就以退出码 1 结束。本脚本不修改任何文件。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REQUIRED_FIELDS = ("path", "sha256", "license")
TIME_FIELDS = ("retrieved_at", "generated_at")
URL_FIELDS = ("source_url", "source_record_url", "source_artifact_url",
              "source_page_url", "mirror_url")

# 允许出现在 provenance 里的许可标识。与 import_glyph_layer.py 的
# DEFAULT_ALLOWED 保持一致（那边是导入期的闸门，这里是事后复核）。
# **不放 CC BY-ND / CC BY-NC / 无许可**：矢量化与重绘都属于「改作」，
# ND 直接禁止；NC 与本库公开供引用的目的冲突（AGENTS.md 硬规则）。
# 也不放 CC BY-SA：ShareAlike 会给下游附加「相同方式共享」的义务。
ALLOWED_LICENSES = (
    "CC0-1.0",
    "PD",
    "PD-1.0",
    "PUBLIC-DOMAIN",
    "OFL-1.1",
    "CC-BY-4.0",
    "CC-BY-3.0",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_index_files(repo_root: Path, script_filter: str | None,
                      prov_by_path: dict[str, dict],
                      problems: list[str]) -> int:
    """对账各层的 index.csv 与 provenance。

    **为什么要有这一项。** provenance 说「这个文件有出处」，index.csv 说
    「这个文件是第几号、下游怎么引用它」。两本账各写各的，就会出现
    「文件在、出处也在，但索引里查不到」——下游按 index.csv 解析，
    查不到就当这字形不存在，等于白入库。

    对三个东西：**主键**（codepoint / glyph_id）、**文件名**、**sha256**。
    只对后两个是不够的：主键写错、文件名与 sha 都不动时，
    下游按码位取字形会拿到指向另一个文件的行。
    """
    checked_rows = 0
    for index_path in sorted((repo_root / "glyphs").glob("*/index.csv")):
        script = index_path.parent.name
        if script_filter and script != script_filter:
            continue
        try:
            with index_path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = reader.fieldnames or []
                rows = list(reader)
        except OSError as exc:
            problems.append(f"{index_path.name}: 读不了：{exc}")
            continue
        # 主键列：篆书层是 codepoint，其余层是 glyph_id。
        key_col = "codepoint" if "codepoint" in fieldnames else "glyph_id"
        indexed: dict[str, str] = {}
        seen_keys: dict[str, str] = {}
        for lineno, row in enumerate(rows, 2):
            name = (row.get("file") or "").strip()
            if not name:
                problems.append(f"{index_path.name}:{lineno} 索引行缺 file 列")
                continue
            rel = f"glyphs/{script}/{name}"
            if rel in indexed:
                problems.append(f"{index_path.name}:{lineno} 索引行重复：{name}")
            indexed[rel] = (row.get("sha256") or "").strip().lower()
            if not indexed[rel]:
                # 空 sha256 = 这一格没写。这层保护就是靠它比对上游的，
                # 空着等于把整行校验静默关掉。
                problems.append(
                    f"{index_path.name}:{lineno} {name} 的 sha256 是空的，"
                    f"索引没法和 provenance 对账")
            record = prov_by_path.get(rel)
            if record is None:
                problems.append(
                    f"{index_path.name}:{lineno} 索引里的 {name} 在 provenance 里没有出处记录")
                continue
            recorded = str(record.get("sha256", "")).lower()
            if indexed[rel] and recorded != indexed[rel]:
                problems.append(
                    f"{index_path.name}:{lineno} {name} 的 sha256 与 provenance 不符："
                    f"索引 {indexed[rel][:12]}，provenance {recorded[:12]}")
            # 主键对账：索引里的层键必须与 provenance 里的一致。
            index_key = (row.get(key_col) or "").strip()
            prov_key = str(record.get(key_col) or "").strip()
            if not prov_key and key_col == "codepoint":
                # 篆书层的 provenance 同时留着 codepoint（十六进制串）与
                # glyph_id（十进制数）；codepoint 才是这一层的主键。
                prov_key = str(record.get("codepoint") or "").strip()
            if index_key and prov_key and index_key.upper() != prov_key.upper():
                problems.append(
                    f"{index_path.name}:{lineno} {name} 的 {key_col} 与 provenance 不符："
                    f"索引 {index_key}，provenance {prov_key}")
            if index_key:
                if index_key in seen_keys:
                    problems.append(
                        f"{index_path.name}:{lineno} {key_col} 重复：{index_key}"
                        f"（{seen_keys[index_key]} 与 {name}）")
                seen_keys[index_key] = name
        # 反向：本层骨架层的每条出处记录都应该在索引里。
        for rel, record in prov_by_path.items():
            if record.get("script") != script or record.get("layer") != "skeleton":
                continue
            if rel not in indexed:
                problems.append(
                    f"{index_path.name}: provenance 里的 {rel} 不在索引中（下游按索引解析）")
        checked_rows += len(rows)
    return checked_rows


def iter_records(prov_files: list[Path], problems: list[str]):
    """逐层读出出处记录，带上「哪个文件第几行」。

    provenance 按书体拆成 ``glyphs/provenance/<书体>.jsonl``：一层一个文件，
    这样某一层的许可状态变化时，整层可以连同它的出处记录一起移除。
    """
    for path in prov_files:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                problems.append(f"{path.name}:{lineno} 不是合法 JSON：{exc}")
                continue
            yield path.name, lineno, record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 glyphs/provenance/*.jsonl")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--script", default=None, help="只校验某个书体，如 oracle")
    parser.add_argument("--quiet", action="store_true", help="只输出汇总与错误")
    args = parser.parse_args(argv)

    repo_root: Path = args.repo_root.resolve()
    prov_dir = repo_root / "glyphs" / "provenance"
    prov_files = sorted(prov_dir.glob("*.jsonl")) if prov_dir.is_dir() else []
    if not prov_files:
        print(f"找不到 {prov_dir}/*.jsonl", file=sys.stderr)
        return 1

    problems: list[str] = []
    by_script: Counter[str] = Counter()
    by_license: Counter[str] = Counter()
    seen_paths: dict[str, int] = {}
    prov_by_path: dict[str, dict] = {}
    checked = 0

    for prov_name, lineno, record in iter_records(prov_files, problems):
        script = str(record.get("script", "") or "(no script)")
        # 文件名必须等于书体名：否则「整层移除」时会漏掉记错文件的那几条。
        if script != prov_name[:-len(".jsonl")]:
            problems.append(
                f"{prov_name}:{lineno} 记录的书体 {script!r} 与文件名不一致"
                f"（逐层 provenance 要求文件名 = 书体名）")
        if args.script and script != args.script:
            continue
        by_script[script] += 1
        by_license[str(record.get("license", "") or "(no license)")] += 1
        checked += 1

        for field in REQUIRED_FIELDS:
            if not record.get(field):
                problems.append(f"{prov_name}:{lineno} 缺必填字段 {field}")
        license_id = str(record.get("license") or "").strip()
        if license_id and license_id not in ALLOWED_LICENSES:
            # 导入期有闸门，这里再查一遍：闸门是「入库那一刻」的事，
            # 这一条让「库里现在没有 ND/NC/无许可的东西」**随时可查**。
            problems.append(
                f"{prov_name}:{lineno} 许可 {license_id!r} 不在允许名单内"
                f"（允许：{', '.join(ALLOWED_LICENSES)}）")
        if not any(record.get(field) for field in TIME_FIELDS):
            problems.append(
                f"{prov_name}:{lineno} 缺时间字段（{'/'.join(TIME_FIELDS)} 至少要有一个）"
            )
        if not any(record.get(field) for field in URL_FIELDS):
            problems.append(
                f"{prov_name}:{lineno} 没有任何来源 URL 字段（{'/'.join(URL_FIELDS)}）"
            )

        rel = str(record.get("path", ""))
        if not rel:
            continue
        if rel in seen_paths:
            problems.append(f"{prov_name}:{lineno} path 与第 {seen_paths[rel]} 行重复：{rel}")
            continue
        seen_paths[rel] = lineno
        prov_by_path[rel] = record

        target = repo_root / rel
        if not target.is_file():
            problems.append(f"{prov_name}:{lineno} 文件不存在：{rel}")
            continue
        actual = sha256_file(target)
        expected = str(record.get("sha256", "")).lower()
        if actual != expected:
            problems.append(f"{rel} sha256 不符：实际 {actual}，记录 {expected}")
        elif not args.quiet:
            print(f"  ok  {rel}  {script}")

    print()
    print(f"检查记录数 : {checked}")
    print("按书体     : " + ("  ".join(f"{k}={v}" for k, v in sorted(by_script.items())) or "(空)"))
    print("按许可     : " + ("  ".join(f"{k}={v}" for k, v in sorted(by_license.items())) or "(空)"))

    # 索引对账：index.csv 是下游解析入口，必须和 provenance 对得上。
    index_rows = check_index_files(repo_root, args.script, prov_by_path, problems)
    print(f"索引对账   : {index_rows} 行")

    # 反向检查：目录里的字形文件是不是都有出处记录。
    # 前面查的是「记录 → 文件」，这一条查的是「文件 → 记录」——
    # 少一个方向，就会漏掉「文件在、出处不在」的孤儿字形，
    # 那正是 AGENTS.md 硬规则 1「无出处，不入仓库」要防的事。
    if not args.script:
        recorded = set(seen_paths)
        glyphs_dir = repo_root / "glyphs"
        orphans = []
        for svg in sorted(glyphs_dir.rglob("*.svg")):
            rel = svg.relative_to(repo_root).as_posix()
            if rel not in recorded:
                orphans.append(rel)
        if orphans:
            print(f"孤儿字形   : {len(orphans)} 个（文件在、出处记录不在）")
            for rel in orphans[:20]:
                print(f"  !! {rel}")
            if len(orphans) > 20:
                print(f"  ... 另有 {len(orphans) - 20} 个")
            problems.append(f"{len(orphans)} 个字形文件没有出处记录")
        else:
            print("孤儿字形   : 0 个")

    if problems:
        print(f"问题       : {len(problems)} 项")
        for item in problems[:50]:
            print(f"  !! {item}")
        if len(problems) > 50:
            print(f"  ... 另有 {len(problems) - 50} 项")
        return 1
    print("问题       : 0 项")
    return 0


if __name__ == "__main__":
    sys.exit(main())
