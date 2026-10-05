#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 glyphs/provenance.jsonl 与实际字形文件是否对得上。

用法::

    python src/verify_provenance.py [--repo-root DIR] [--script oracle] [--quiet]

检查项:

1. 每行都是合法 JSON，且 ``path`` 不重复；
2. 必填字段齐全：``path`` / ``sha256`` / ``license``（AGENTS.md 第 2 条），
   时间字段 ``retrieved_at`` 或 ``generated_at`` 至少一个（派生层用后者），
   以及至少一个来源 URL 字段；
3. ``path`` 指向的文件存在；
4. 文件的 sha256 与记录一致（AGENTS.md 第 1 条：无出处不入库的机器可查版本）。

有任何一项不通过就以退出码 1 结束。本脚本不修改任何文件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REQUIRED_FIELDS = ("path", "sha256", "license")
TIME_FIELDS = ("retrieved_at", "generated_at")
URL_FIELDS = ("source_url", "source_record_url", "source_artifact_url",
              "source_page_url", "mirror_url")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 provenance.jsonl")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--script", default=None, help="只校验某个书体，如 oracle")
    parser.add_argument("--quiet", action="store_true", help="只输出汇总与错误")
    args = parser.parse_args(argv)

    repo_root: Path = args.repo_root.resolve()
    prov_path = repo_root / "glyphs" / "provenance.jsonl"
    if not prov_path.is_file():
        print(f"找不到 {prov_path}", file=sys.stderr)
        return 1

    problems: list[str] = []
    by_script: Counter[str] = Counter()
    by_license: Counter[str] = Counter()
    seen_paths: dict[str, int] = {}
    checked = 0

    for lineno, line in enumerate(prov_path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"{prov_path.name}:{lineno} 不是合法 JSON：{exc}")
            continue

        script = str(record.get("script", "") or "(no script)")
        if args.script and script != args.script:
            continue
        by_script[script] += 1
        by_license[str(record.get("license", "") or "(no license)")] += 1
        checked += 1

        for field in REQUIRED_FIELDS:
            if not record.get(field):
                problems.append(f"{prov_path.name}:{lineno} 缺必填字段 {field}")
        if not any(record.get(field) for field in TIME_FIELDS):
            problems.append(
                f"{prov_path.name}:{lineno} 缺时间字段（{'/'.join(TIME_FIELDS)} 至少要有一个）"
            )
        if not any(record.get(field) for field in URL_FIELDS):
            problems.append(
                f"{prov_path.name}:{lineno} 没有任何来源 URL 字段（{'/'.join(URL_FIELDS)}）"
            )

        rel = str(record.get("path", ""))
        if not rel:
            continue
        if rel in seen_paths:
            problems.append(f"{prov_path.name}:{lineno} path 与第 {seen_paths[rel]} 行重复：{rel}")
            continue
        seen_paths[rel] = lineno

        target = repo_root / rel
        if not target.is_file():
            problems.append(f"{prov_path.name}:{lineno} 文件不存在：{rel}")
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
