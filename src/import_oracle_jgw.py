#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把甲骨文字形数据集 jgw-1203 v0.3 导入 glyphs/oracle/。

用法::

    python src/import_oracle_jgw.py --dataset-dir <解包后的数据集目录> \
                                    [--zenodo-dir <Zenodo 原件解包目录>] [--dry-run]

产出::

    glyphs/oracle/<glyph_id:04d>.svg   与上游逐字节一致的副本
    glyphs/oracle/index.csv            现代字/码位 → 文件 的反查表
    glyphs/provenance.jsonl            每个字形一条记录（合并写入，不覆盖其他书体）

三个设计决定（理由见 AGENTS.md）:

1. **文件键用 ``glyph_id``**（上游源字库条目号 1..1203）。甲骨文在 Unicode 里
   没有自己的码位，且 33 个现代字各对应两个条目，``glyphs/oracle/<Unicode>.svg``
   无法表达。
2. **只导入 ``data/svg_polyline/``**。它是保真的折线描迹；``data/svg_parametric/``
   是解析重建后的光滑化版本，按 AGENTS.md 第 4 条不作为正式字形。
3. **逐字节复制**，不重新编码、不归一化 viewBox，这样 sha256 可以直接对回上游。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_NAME = "oracle"
SOURCE_SUBDIR = "data/svg_polyline"

# 数据集固定信息。改动前必须重新核实（AGENTS.md 第 3 条：禁止编造链接）。
DATASET = {
    "name": "Oracle Bone Glyphs: Parametric Vector Dataset (v0.3)",
    "doi": "10.5281/zenodo.22467946",
    "record_url": "https://zenodo.org/records/22467946",
    "file_url": (
        "https://zenodo.org/api/records/22467946/files/"
        "aylqs2025/oracle-bone-jgw-1203-v0.3.zip/content"
    ),
    "artifact_md5": "7764c7f5b0feb8f0052c36233ddf8d4b",
    "mirror_url": "https://github.com/aylqs2025/oracle-bone-jgw-1203/tree/v0.3",
    "mirror_commit": "5496ad559f81ae8632f3915e8ec2beb705c64ba3",
    "license": "CC-BY-4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "attribution": (
        "Li, Qing-sheng & Bian, Yu-lin (2026), "
        "'Oracle Bone Glyphs: Parametric Vector Dataset (v0.3)', "
        "doi:10.5281/zenodo.22467946"
    ),
}

# 中间文件列（jgw_1203_labeled.csv 里的 stroke 列很大，本脚本不读它）。
LABEL_FIELDS = ("modern_char", "unicode", "char_form", "encoding_status", "pinyin")
PROV_FIELDS = (
    "identity_confidence",
    "identity_note",
    "composition_note",
    "n_source_variants",
    "pua_legacy",
    "previous_label_v0_2",
)

INDEX_HEADER = (
    "glyph_id", "modern_char", "unicode", "char_form", "encoding_status",
    "pinyin", "n_points", "n_strokes", "identity_confidence",
    "n_source_variants", "file", "sha256",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> dict[str, dict[str, str]]:
    """读 CSV，按 glyph_id 建索引。用 utf-8-sig 兼容可能存在的 BOM。"""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        key = (row.get("glyph_id") or "").strip()
        if not key:
            raise SystemExit(f"{path}: 存在没有 glyph_id 的行")
        if key in out:
            raise SystemExit(f"{path}: glyph_id {key} 重复")
        out[key] = row
    return out


def merge_provenance(path: Path, new_records: list[dict]) -> tuple[int, int]:
    """把新记录并进 provenance.jsonl，只替换本脚本负责的 layer="skeleton" 记录。

    返回 (保留的旧记录数, 写入的总记录数)。这样 outline 之类的派生层
    （由 src/outline_oracle.py 写，layer="outline"）不会被重跑导入时删掉，
    将来 seal/bronze 的导入脚本也不会互相覆盖。
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导入 jgw-1203 甲骨文字形")
    parser.add_argument("--dataset-dir", required=True, type=Path,
                        help="解包后的数据集目录（含 data/ 与 src/ 的那一层）")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="仓库根目录，默认取本脚本的上一级")
    parser.add_argument("--zenodo-dir", type=Path, default=None,
                        help="可选的 Zenodo 原件解包目录，用于逐文件对拍")
    parser.add_argument("--dry-run", action="store_true", help="只检查，不写任何文件")
    args = parser.parse_args(argv)

    dataset_dir: Path = args.dataset_dir.resolve()
    repo_root: Path = args.repo_root.resolve()
    src_dir = dataset_dir / SOURCE_SUBDIR
    if not src_dir.is_dir():
        raise SystemExit(f"找不到源字形目录：{src_dir}")

    labels = read_csv(dataset_dir / "data" / "jgw_1203_labeled.csv")
    provenance = read_csv(dataset_dir / "data" / "provenance_manifest.csv")
    # 只校验清单里的 svg 名字，实际以 data/svg_polyline/ 下的文件为准。
    manifest = read_csv(dataset_dir / "data" / "svg_polyline_manifest.csv")

    glyph_ids = sorted(labels, key=int)
    expected = [str(i) for i in range(1, len(glyph_ids) + 1)]
    if glyph_ids != expected:
        raise SystemExit(
            f"glyph_id 不是连续的 1..{len(expected)}（实际 {len(glyph_ids)} 条）"
        )
    for table_name, table in (("provenance_manifest", provenance),
                              ("svg_polyline_manifest", manifest)):
        if sorted(table, key=int) != glyph_ids:
            raise SystemExit(f"{table_name}.csv 的 glyph_id 集合与 labeled.csv 不一致")

    # 可选：与 Zenodo 原件逐文件对拍。
    zenodo_dir = args.zenodo_dir.resolve() if args.zenodo_dir else None
    if zenodo_dir:
        if not zenodo_dir.is_dir():
            raise SystemExit(f"--zenodo-dir 不是目录：{zenodo_dir}")
        if not any(zenodo_dir.rglob(SOURCE_SUBDIR)):
            raise SystemExit(f"{zenodo_dir} 下找不到 {SOURCE_SUBDIR}")

    out_dir = repo_root / "glyphs" / SCRIPT_NAME
    prov_path = repo_root / "glyphs" / "provenance.jsonl"
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    records: list[dict] = []
    index_rows: list[dict] = []
    mismatched_zenodo: list[str] = []
    stats = {"confidence": {}, "char_form": {}, "encoding_status": {}, "pua": 0}

    for glyph_id in glyph_ids:
        label = labels[glyph_id]
        prov = provenance[glyph_id]
        name = f"{int(glyph_id):04d}.svg"
        src = src_dir / name
        if not src.is_file():
            raise SystemExit(f"缺源文件：{src}")
        if (manifest[glyph_id].get("svg") or "").strip() != name:
            raise SystemExit(
                f"glyph {glyph_id}: 清单记的 svg 名是 "
                f"{manifest[glyph_id].get('svg')!r}，期望 {name!r}"
            )

        source_sha = sha256_file(src)
        if zenodo_dir:
            other = next(iter(zenodo_dir.rglob(SOURCE_SUBDIR))) / name
            if not other.is_file() or sha256_file(other) != source_sha:
                mismatched_zenodo.append(name)

        dest = out_dir / name
        if not args.dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            dest_sha = sha256_file(dest)
            if dest_sha != source_sha:
                raise SystemExit(f"{dest}: 复制后 sha256 不一致（{dest_sha} != {source_sha}）")
        else:
            dest_sha = source_sha

        unicode_hex = (label.get("unicode") or "").strip().upper()
        record = {
            "path": f"glyphs/{SCRIPT_NAME}/{name}",
            "sha256": dest_sha,
            "script": SCRIPT_NAME,
            "layer": "skeleton",
            "glyph_id": int(glyph_id),
            "modern_char": label.get("modern_char", "").strip(),
            "unicode": unicode_hex,
            "char_form": label.get("char_form", "").strip(),
            "encoding_status": label.get("encoding_status", "").strip(),
            "pinyin": label.get("pinyin", "").strip(),
            "identity_confidence": prov.get("identity_confidence", "").strip(),
            "n_source_variants": prov.get("n_source_variants", "").strip(),
            "source_dataset": DATASET["name"],
            "source_doi": DATASET["doi"],
            "source_record_url": DATASET["record_url"],
            "source_artifact_url": DATASET["file_url"],
            "source_artifact_md5": DATASET["artifact_md5"],
            "source_path": f"{SOURCE_SUBDIR}/{name}",
            "source_sha256": source_sha,
            "mirror_url": DATASET["mirror_url"],
            "mirror_commit": DATASET["mirror_commit"],
            "license": DATASET["license"],
            "license_url": DATASET["license_url"],
            "attribution": DATASET["attribution"],
            "retrieved_at": retrieved_at,
            "modifications": "none (byte-identical copy)",
        }
        # 只在有值时写入，避免 1203 行里塞满空字段。
        for field in PROV_FIELDS:
            value = (prov.get(field) or "").strip()
            if value:
                record[field] = value
        if zenodo_dir and not mismatched_zenodo:
            record["zenodo_original_verified_identical"] = True
        records.append(record)

        index_rows.append({
            "glyph_id": int(glyph_id),
            "modern_char": record["modern_char"],
            "unicode": unicode_hex,
            "char_form": record["char_form"],
            "encoding_status": record["encoding_status"],
            "pinyin": record["pinyin"],
            "n_points": (labels[glyph_id].get("n_points") or "").strip(),
            "n_strokes": (labels[glyph_id].get("n_strokes") or "").strip(),
            "identity_confidence": record["identity_confidence"],
            "n_source_variants": record["n_source_variants"],
            "file": name,
            "sha256": dest_sha,
        })

        for key, value in (("confidence", record["identity_confidence"] or "(empty)"),
                           ("char_form", record["char_form"] or "(empty)"),
                           ("encoding_status", record["encoding_status"] or "(empty)")):
            stats[key][value] = stats[key].get(value, 0) + 1
        if record.get("pua_legacy"):
            stats["pua"] += 1

    if mismatched_zenodo:
        raise SystemExit(
            f"与 Zenodo 原件对拍失败 {len(mismatched_zenodo)} 个："
            + ", ".join(mismatched_zenodo[:10])
        )

    if not args.dry_run:
        index_path = out_dir / "index.csv"
        with index_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=INDEX_HEADER, lineterminator="\n")
            writer.writeheader()
            writer.writerows(index_rows)
        kept, total = merge_provenance(prov_path, records)
        print(f"provenance.jsonl: 保留其他记录 {kept} 条，写入后共 {total} 条")

    print(f"字形文件 : {len(records)} 个 -> glyphs/{SCRIPT_NAME}/<glyph_id:04d>.svg")
    print(f"无码位    : {sum(1 for r in records if not r['unicode'])} 个"
          f" -> {[r['glyph_id'] for r in records if not r['unicode']]}")
    print(f"一字多形  : {len({r['unicode'] for r in records if r['unicode']})} 个不同码位"
          f" / {sum(1 for r in records if r['unicode'])} 条有条目码位")
    for key, label in (("confidence", "identity_confidence"),
                       ("char_form", "char_form"),
                       ("encoding_status", "encoding_status")):
        pairs = "  ".join(f"{k}={v}" for k, v in sorted(stats[key].items()))
        print(f"{label:<18}: {pairs}")
    if stats["pua"]:
        print(f"pua_legacy        : {stats['pua']} 条（旧私用区码位，仅历史留痕）")
    if zenodo_dir:
        print("Zenodo 原件对拍   : 逐文件一致（写入 provenance 已标注）")
    print("dry-run：未写入任何文件" if args.dry_run else "完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
