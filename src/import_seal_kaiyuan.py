#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「開元小篆」上游的字形导入 glyphs/seal/。

用法::

    python src/import_seal_kaiyuan.py --upstream-dir <上游仓库目录> [--verify-only]
    python src/import_seal_kaiyuan.py --upstream-dir <上游仓库目录> --license-cleared

产出::

    glyphs/seal/<篆书码位>.svg   与上游逐字节一致的副本（3D000.svg = U+3D000）
    glyphs/seal/index.csv        篆书码位 / 现代字 / 《说文》流水号 → 文件 的反查表
    glyphs/provenance/<书体>.jsonl  每个字形一条记录（合并写入，不覆盖其他书体）

**文件键用篆书区块码位，不是现代字码位。** Unicode 18.0 的篆书区块
（U+3D000–U+3FC3F）里同一个现代字有多个码位（正篆 + 重文）：登记表中
10,980 个有字形的码位只对应 10,933 个现代字，47 个现代字出现两次以上。
按现代字码位命名会撞车；按篆书区块自己的码位命名则一一对应，这也正是
AGENTS.md「只有小篆在 Unicode 里有自己的码位」那句理由的含义。现代字码位放在
index.csv 里反查。

**先验后写。** 每个文件都比对上游 git blob SHA-1（登记表里已钉住），
不一致即中止——这样「我们指向的到底是哪几个字节」永远可复算。

**许可闸门。** 本仓库此前对这一层的立场是「只登记、不复制」（上游的授权语句只
覆盖 output fonts，glyphs/** 未被明确标记）。默认只做校验；真正落盘需要显式
加 ``--license-cleared``，并在 provenance 里如实记录依据。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_NAME = "seal"

UPSTREAM = {
    "name": "Kaiyuan Small Seal Font (開元小篆)",
    "repo_url": "https://github.com/frankslin/kaiyuan-small-seal-font",
    "license": "OFL-1.1",
    "license_url": "https://scripts.sil.org/OFL",
}

INDEX_HEADER = (
    "seal_codepoint", "unicode", "modern_char", "radical_no", "radical_cp",
    "ccz", "dyc", "qjz", "thx", "upstream_path", "upstream_blob_sha1", "file", "sha256",
)

# 上游逐字形出处表（版本 / Commons 文件 / 页码 / 裁切框 / 状态）。
# 上游 AGENTS.md 写的是 data/provenance/glyphs.csv；字段名以实际文件为准。
UPSTREAM_PROV = "data/provenance/glyphs.csv"
# 上游 CSV 列 → 本仓库 provenance 字段名。
UPSTREAM_PROV_MAP = {
    "edition": "upstream_edition",
    "sequence": "upstream_sequence",
    "commons_title": "upstream_commons_title",
    "page": "upstream_page",
    "side": "upstream_side",
    "juan": "upstream_juan",
    "radical": "upstream_radical",
    "kind": "upstream_kind",
    "similarity": "upstream_similarity",
    "status": "upstream_status",
}
# SVG 根元素里内嵌的出处属性（每个文件自带，比 CSV 更靠近字形本身）。
SVG_ATTR_RE = re.compile(r'(data-source|data-crop|data-source-height|data-units-per-source-pixel)="([^"]*)"')


def svg_embedded_source(path: Path) -> dict[str, str]:
    """读出 SVG 根元素内嵌的出处属性。

    上游每个字形文件都带 ``data-source``（版本 + 流水号）与 ``data-crop``
    （Commons 文件名、页码、版心、裁切框、旋转角），这是最贴近字形本身的出处。
    """
    head = path.read_text(encoding="utf-8", errors="replace")[:2000]
    return {k: v.strip() for k, v in SVG_ATTR_RE.findall(head)}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha1(path: Path) -> str:
    """算 git blob 的 SHA-1：sha1("blob <长度>\\0" + 内容)。

    与 `git hash-object` 等价，但不需要 git 可执行文件。
    """
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def read_registry(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_upstream_provenance(upstream_dir: Path) -> dict[str, dict[str, str]]:
    """读上游逐字形出处表，按篆书码位建索引。文件不在就返回空。"""
    prov_path = upstream_dir / UPSTREAM_PROV
    if not prov_path.is_file():
        return {}
    out: dict[str, dict[str, str]] = {}
    with prov_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = ""
            for field in ("codepoint", "cp", "code_point"):
                if (row.get(field) or "").strip():
                    key = (row[field]).strip().upper().replace("U+", "")
                    break
            if not key:
                continue
            out[key] = row
    return out


def merge_provenance(path: Path, new_records: list[dict]) -> tuple[int, int]:
    """把新记录并进 provenance.jsonl，只替换本脚本负责的 layer="skeleton" 记录。

    返回 (保留的旧记录数, 写入后的总记录数)。甲骨文骨架/轮廓的记录不受影响。
    """
    kept: list[dict] = []
    if path.exists():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno} 不是合法 JSON：{exc}") from exc
            same_layer = (
                record.get("script") == SCRIPT_NAME
                and record.get("layer", "skeleton") == "skeleton"
            )
            if not same_layer:
                kept.append(record)

    merged = kept + new_records
    merged.sort(key=lambda r: (str(r.get("script", "")), str(r.get("path", ""))))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in merged:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return len(kept), len(merged)


def upstream_head(upstream_dir: Path) -> str | None:
    """读上游当前 HEAD（不是 git 就返回 None）。"""
    if not (upstream_dir / ".git").is_dir():
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(upstream_dir), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, encoding="utf-8",
        )
        return proc.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def upstream_blob_map(upstream_dir: Path, commit: str) -> dict[str, str]:
    """用 git tree 对象列出上游全部字形文件的 blob SHA-1。

    只取 tree、不取 blob，所以不需要把上游的几十 MB 内容拉到本地就能对账：
    ``git ls-tree`` 读的是 tree 对象里的哈希，与文件内容无关。
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(upstream_dir), "ls-tree", "-r", commit, "--", "glyphs"],
            check=True, capture_output=True, text=True, encoding="utf-8",
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SystemExit(f"读上游 tree 失败：{exc}") from exc
    out: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        meta = parts[0].split()
        if len(meta) != 3 or meta[1] != "blob":
            continue
        out[parts[1].strip()] = meta[2].lower()
    return out


def verify_against_tree(registry: list[dict[str, str]], blobs: dict[str, str]) -> int:
    """把登记表逐条与上游 tree 对账。返回不一致的条数。"""
    matched = 0
    problems: list[str] = []
    for row in registry:
        path = (row.get("upstream_path") or "").strip()
        if not path:
            continue
        expected = (row.get("upstream_blob_sha1") or "").strip().lower()
        actual = blobs.get(path)
        if actual is None:
            problems.append(f"上游没有 {path}")
        elif expected and actual != expected:
            problems.append(f"{path}: 登记 {expected[:12]} ≠ 上游 {actual[:12]}")
        else:
            matched += 1
    extra = sorted(set(blobs) - {
        (r.get("upstream_path") or "").strip() for r in registry
        if (r.get("upstream_path") or "").strip()
    })
    print(f"上游字形文件   : {len(blobs)}")
    print(f"登记有指向     : {sum(1 for r in registry if (r.get('upstream_path') or '').strip())}")
    print(f"blob SHA-1 一致: {matched}")
    if extra:
        print(f"上游多出        : {len(extra)} 个未登记（例：{', '.join(extra[:5])}）")
    if problems:
        print(f"不一致          : {len(problems)} 条")
        for item in problems[:10]:
            print(f"  !! {item}")
        return 1
    print("不一致          : 0 条")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导入開元小篆篆书字形")
    parser.add_argument("--upstream-dir", required=True, type=Path,
                        help="上游仓库目录（需停在 external.meta.json 钉住的 commit）")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="仓库根目录，默认取本脚本的上一级")
    parser.add_argument("--verify-tree", action="store_true",
                        help="用 git tree 对象对账：只比 blob SHA-1，不需要把字形下载到本地")
    parser.add_argument("--verify-only", action="store_true",
                        help="只校验登记表与上游是否对得上，不写任何文件")
    parser.add_argument("--dry-run", action="store_true",
                        help="校验并准备导入，但一个文件也不写")
    parser.add_argument("--license-cleared", action="store_true",
                        help="确认本层许可已澄清（上游明确授权 glyphs/**，或维护者拍板），"
                             "否则只做校验、不复制字形")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    upstream_dir = args.upstream_dir.resolve()
    if not upstream_dir.is_dir():
        raise SystemExit(f"找不到上游目录：{upstream_dir}")

    # 许可闸门必须挡在任何写盘动作之前。曾经它放在拷贝循环之后，于是「默认不复制」时
    # 10,980 个字形文件照样落进了 glyphs/seal/，只是没有 provenance 与 index.csv——
    # 等于「无出处不入仓库」被绕开。闸门现在先于一切落盘动作。
    if not (args.verify_tree or args.verify_only or args.dry_run) \
            and not args.license_cleared:
        raise SystemExit(
            "本层许可尚未澄清，默认不复制字形（一个字形文件也不会写）。\n"
            "  上游的授权语句只覆盖 output fonts，glyphs/** 未被明确标记为受 OFL 约束，\n"
            "  仓库根目录也没有 LICENSE 文件。\n"
            "  确认已澄清（或维护者拍板按 OFL 1.1 归档）后，加 --license-cleared 重新运行。\n"
            "  只想校验上游对账，用 --verify-tree（零下载）。"
        )

    meta_path = repo_root / "glyphs" / "seal" / "external.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    pinned_commit = meta["upstream_commit"]

    head = upstream_head(upstream_dir)
    if head and head != pinned_commit:
        print(f"注意：上游 HEAD {head[:12]} 与登记表钉住的 {pinned_commit[:12]} 不同；"
              "逐文件 blob SHA-1 仍会逐一核对。")

    registry = read_registry(repo_root / "glyphs" / "seal" / "external.csv")
    upstream_prov = read_upstream_provenance(upstream_dir)

    if args.verify_tree:
        print(f"上游 commit     : {pinned_commit[:12]}")
        print("对账方式        : git tree 对象的 blob SHA-1（不下载字形内容）")
        blobs = upstream_blob_map(upstream_dir, pinned_commit)
        return verify_against_tree(registry, blobs)

    out_dir = repo_root / "glyphs" / SCRIPT_NAME
    prov_path = repo_root / "glyphs" / "provenance" / f"{SCRIPT_NAME}.jsonl"
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 许可闸门已在上方拦住任何落盘动作，这里不再重复检查。
    records: list[dict] = []
    index_rows: list[dict] = []
    missing: list[str] = []
    blob_mismatch: list[str] = []
    modern_chars: dict[str, int] = {}
    dup_modern = 0

    for row in registry:
        upstream_path = (row.get("upstream_path") or "").strip()
        if not upstream_path:
            continue
        codepoint = (row.get("codepoint") or "").strip().upper()
        hex_cp = codepoint[2:] if codepoint.startswith("U+") else codepoint
        src = upstream_dir / upstream_path
        if not src.is_file():
            missing.append(upstream_path)
            continue

        expected_blob = (row.get("upstream_blob_sha1") or "").strip().lower()
        actual_blob = git_blob_sha1(src)
        if expected_blob and actual_blob != expected_blob:
            blob_mismatch.append(f"{upstream_path}: 登记 {expected_blob[:12]} ≠ 实际 {actual_blob[:12]}")
            continue

        source_sha = sha256_file(src)
        name = f"{hex_cp}.svg"
        dest = out_dir / name
        if not (args.verify_only or args.dry_run):
            out_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            dest_sha = sha256_file(dest)
            if dest_sha != source_sha:
                raise SystemExit(f"{dest}: 复制后 sha256 不一致（{dest_sha} != {source_sha}）")
        else:
            dest_sha = source_sha

        modern_cp = (row.get("unicode") or "").strip().upper()
        modern_char = (row.get("modern_char") or "").strip()
        modern_chars[modern_cp] = modern_chars.get(modern_cp, 0) + 1
        if modern_chars[modern_cp] == 2:
            dup_modern += 1

        source_url = (
            f"{UPSTREAM['repo_url']}/blob/{pinned_commit}/{upstream_path}"
        )
        record = {
            "path": f"glyphs/{SCRIPT_NAME}/{name}",
            "sha256": dest_sha,
            "script": SCRIPT_NAME,
            "layer": "skeleton",
            "glyph_id": int(hex_cp, 16),
            "codepoint": codepoint,
            "modern_char": modern_char,
            "unicode": modern_cp,
            "radical_no": (row.get("radical_no") or "").strip(),
            "source_dataset": UPSTREAM["name"],
            "source_url": source_url,
            "source_path": upstream_path,
            "source_sha256": source_sha,
            "source_commit": pinned_commit,
            "source_blob_sha1": actual_blob,
            "mirror_url": UPSTREAM["repo_url"],
            "license": UPSTREAM["license"],
            "license_url": UPSTREAM["license_url"],
            "attribution": (
                "Kaiyuan Small Seal Font Contributors (開元小篆), "
                f"{UPSTREAM['repo_url']} @ {pinned_commit[:12]}"
            ),
            "retrieved_at": retrieved_at,
            "modifications": "none (byte-identical copy)",
        }
        for field in ("ccz", "dyc", "qjz", "thx"):
            value = (row.get(field) or "").strip()
            if value:
                record[field] = value

        # 上游的逐字形出处（版本 / Commons 文件 / 页码 / 裁切框 / 状态）。
        up_row = upstream_prov.get(hex_cp)
        if up_row:
            for field, out_field in UPSTREAM_PROV_MAP.items():
                value = (up_row.get(field) or "").strip()
                if value:
                    record[out_field] = value
            crop = " ".join(
                str(up_row.get(k) or "").strip()
                for k in ("x", "y", "w", "h", "rotation")
            ).strip()
            if crop:
                record["upstream_crop_box"] = crop
        # 文件内嵌的出处属性（最贴近字形本身，优先于 CSV）。
        embedded = svg_embedded_source(src)
        if embedded.get("data-source"):
            record["upstream_data_source"] = embedded["data-source"]
        if embedded.get("data-crop"):
            record["upstream_data_crop"] = embedded["data-crop"]
        records.append(record)

        index_rows.append({
            "seal_codepoint": codepoint,
            "unicode": modern_cp,
            "modern_char": modern_char,
            "radical_no": (row.get("radical_no") or "").strip(),
            "radical_cp": (row.get("radical_cp") or "").strip(),
            "ccz": (row.get("ccz") or "").strip(),
            "dyc": (row.get("dyc") or "").strip(),
            "qjz": (row.get("qjz") or "").strip(),
            "thx": (row.get("thx") or "").strip(),
            "upstream_path": upstream_path,
            "upstream_blob_sha1": actual_blob,
            "file": name,
            "sha256": dest_sha,
        })

    if missing:
        raise SystemExit(
            f"上游缺 {len(missing)} 个登记在册的字形，例如：{', '.join(missing[:5])}"
        )
    if blob_mismatch:
        raise SystemExit(
            f"blob SHA-1 对不上 {len(blob_mismatch)} 个：\n  " + "\n  ".join(blob_mismatch[:10])
        )

    print(f"上游 commit     : {pinned_commit[:12]}（HEAD {head[:12] if head else 'n/a'}）")
    print(f"登记码位        : {len(registry)}")
    print(f"上游有字形      : {len(records)}")
    print(f"blob SHA-1 核对 : 全部一致")
    print(f"对应现代字      : {len(modern_chars)} 个（其中 {dup_modern} 个对应多个码位）")
    print(f"上游逐字形出处  : {'已并入 ' + str(sum(1 for r in records if 'upstream_edition' in r)) + ' 条' if upstream_prov else '上游表不可用，未并入'}")

    if args.verify_only:
        print("verify-only：未写入任何文件")
        return 0
    if args.dry_run:
        print("dry-run：未写入任何文件")
        return 0

    index_path = out_dir / "index.csv"
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(index_rows)
    kept, total = merge_provenance(prov_path, records)
    print(f"provenance.jsonl: 保留其他记录 {kept} 条，写入后共 {total} 条")
    print(f"完成：glyphs/{SCRIPT_NAME}/ 写入 {len(records)} 个字形 + index.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
