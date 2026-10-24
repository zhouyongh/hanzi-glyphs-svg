#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给汉典小篆字形清单指派 Unicode 篆书区块码位。

用法::

    python src/assign_seal_codepoints.py \
        --manifest tmp/zdic/xiaozhuan-clean/manifest.json \
        --out tmp/zdic/xiaozhuan-seal/manifest.json \
        [--zheng-table tmp/research/seal-modern-to-zheng.txt]

为什么需要这一步。**汉典的小篆是按现代字给的，篆书区块是按码位给的**，
两边的键不一样。Unicode 的 ``SealSources.txt`` 里，每个篆书区块码位都带一个
``kSEAL_MCJK`` 属性，指向对应的现代汉字码位——这就是转换表（11,328 个码位
对应 11,230 个现代字）。

**一个现代字可能对应多个篆书码位**（正篆与重文）：Unicode 登记表里 94 个现代字
对应多个码位（90 个 ×2、4 个 ×3）。汉典每个现代字只给一个小篆字形，填不满这些码位。
本脚本按 ``--zheng-table`` 指定的正篆优先规则选一个码位，其余码位留空，
并在清单里记明「这个字还有哪些码位没填、为什么」。

没有正篆表时，兜底取码位最小者，并在 ``seal_note`` 字段注明是兜底。

输出目录里会带上字形文件本身：清单的 ``file`` 字段是相对清单目录的路径，
``src/import_glyph_layer.py`` 照这个相对路径找文件，所以清单目录必须自带字形。
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path


def normalize_cp(raw: str) -> str:
    """把码位统一成仓库用的 5 位大写十六进制（篆书区块 U+3D000–U+3FC3F）。

    Unicode 的 ``SealSources.txt`` 与 OpenCC 的反查表一个写 6 位（``03D000``）、
    一个写 5 位（``3D000``），同一块地方两种宽度，直接比字符串会全部判不等。
    """
    cp = (raw or "").strip().upper()
    if cp.startswith("U+"):
        cp = cp[2:]
    if len(cp) == 6 and cp.startswith("0"):
        cp = cp[1:]
    return cp


def split_candidates(raw: str) -> list[str]:
    """切分候选码位列表。

    正篆反查表的 ``candidates`` 列用**空格**分隔（``03D8EE 03D8F0``），
    逗号分隔是另一种写法；两种都收，免得换一份表就全判成单候选。
    """
    out: list[str] = []
    for part in (raw or "").replace(",", " ").split():
        cp = normalize_cp(part)
        if cp and cp not in out:
            out.append(cp)
    return out


def load_registry(repo_root: Path) -> tuple[dict[str, list[str]], dict[str, str]]:
    """从 glyphs/seal/external.csv 读「现代字码位 → 篆书区块码位列表」。

    同时返回「篆书码位 → 现代字码位」的逆表，用于统计篆书区块的覆盖率。
    """
    path = repo_root / "glyphs" / "seal" / "external.csv"
    out: dict[str, list[str]] = {}
    reverse: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            modern_cp = (row.get("unicode") or "").strip().upper()
            codepoint = normalize_cp(row.get("codepoint") or "")
            if not modern_cp or not codepoint:
                continue
            out.setdefault(modern_cp, []).append(codepoint)
            reverse.setdefault(codepoint, modern_cp)
    for cps in out.values():
        cps.sort()
    return out, reverse


def load_zheng_table(path: Path) -> dict[str, dict[str, str]]:
    """读「现代字码位 → 正篆码位」表。

    表头驱动：取 ``modern_cp``、``zheng_cp_repo5``（5 位仓库实形）、``candidates``
    （该字的所有候选篆书码位）、``note`` 四列。
    没有 5 位列时退回 ``zheng_cp``（6 位），此时会去掉多余的 0。

    这张表来自 OpenCC 的 ``SealCharacters.txt`` 反查字典，与 Unicode 核心规范
    §18.14 的码位排序规则（按 540 部、组内依 THX 原书顺序）一致；它还修正了
    Unicode ``SealSources.txt`` 把「玉」记成「王」的那处偏差。
    """
    out: dict[str, dict[str, str]] = {}
    header: list[str] | None = None
    idx: dict[str, int] = {}

    def find(*wants: str) -> int | None:
        for want in wants:
            if want in idx:
                return idx[want]
        return None

    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("\t") if "\t" in line else line.split()
            if header is None:
                header = [p.strip() for p in parts]
                lowered = [h.lower() for h in header]
                idx = {h: i for i, h in enumerate(lowered)}
                if find("modern_cp", "modern", "unicode") is None \
                        or find("zheng_cp_repo5", "zheng_cp", "seal_codepoint") is None:
                    raise SystemExit(
                        f"{path}: 表头里找不到 modern_cp / zheng_cp 列（表头：{header}）")
                continue
            modern_idx = find("modern_cp", "modern", "unicode")
            zheng_idx = find("zheng_cp_repo5", "zheng_cp", "seal_codepoint")
            cand_idx = find("candidates")
            note_idx = find("note")
            if modern_idx is None or zheng_idx is None or len(parts) <= max(modern_idx, zheng_idx):
                continue
            modern = parts[modern_idx].strip().upper()
            zheng = normalize_cp(parts[zheng_idx])
            if not modern or not zheng:
                continue
            candidates = split_candidates(parts[cand_idx]) if cand_idx is not None \
                and len(parts) > cand_idx else []
            note = parts[note_idx].strip() if note_idx is not None and len(parts) > note_idx else ""
            out[modern] = {"zheng": zheng, "candidates": candidates, "note": note}
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="给字形清单指派篆书区块码位")
    parser.add_argument("--manifest", required=True, type=Path, help="汉典小篆清单")
    parser.add_argument("--out", required=True, type=Path, help="输出清单的落盘目录")
    parser.add_argument("--repo-root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--zheng-table", type=Path, default=None,
                        help="「现代字码位 → 正篆码位」表；没有就用码位最小者兜底")
    args = parser.parse_args(argv)

    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"找不到清单：{manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    registry, reverse = load_registry(args.repo_root.resolve())
    zheng = load_zheng_table(args.zheng_table.resolve()) if args.zheng_table else {}
    if args.zheng_table and not zheng:
        raise SystemExit(f"正篆表是空的：{args.zheng_table}")

    out_glyphs: list[dict] = []
    no_codepoint = 0
    fallback = 0
    multi = 0
    from_registry = 0

    for item in manifest.get("glyphs", []):
        # 清单里的现代字码位可能没补零（「4E04」），登记表与反查表都是 6 位
        # （「004E04」）。查表前统一补零，回写时也用 6 位，与金文/隶书层的
        # index.csv 保持同一口径。
        modern_cp = str(item.get("unicode") or "").strip().upper().rjust(6, "0")
        table = zheng.get(modern_cp)
        # 候选集：正篆反查表优先；表里没有这个字才退回 Unicode 登记表。
        candidates = list((table or {}).get("candidates") or [])
        if not candidates:
            candidates = list(registry.get(modern_cp, []))
            if candidates:
                from_registry += 1
        if not candidates:
            no_codepoint += 1
            continue
        if len(candidates) > 1:
            multi += 1

        notes: list[str] = []
        if table and table.get("note"):
            notes.append(table["note"].strip())

        if table and table["zheng"] in candidates:
            # 正篆码位取自反查表，落在候选集内 → 这是《说文》正字的位置。
            chosen = table["zheng"]
            if len(candidates) > 1:
                rest = [c for c in candidates if c != chosen]
                notes.append(
                    f"该字另有 {len(rest)} 个篆书区块码位（重文/异体：{', '.join(rest)}），"
                    "本次只填正篆码位")
        else:
            # 兜底：取候选里最小的码位（Unicode §18.14 的组内排序也是码位升序）。
            chosen = sorted(candidates)[0]
            fallback += 1
            notes.append(
                f"篆书区块码位取最小者（{len(candidates)} 个候选：{', '.join(sorted(candidates))}）")

        new = dict(item)
        new["unicode"] = modern_cp
        new["codepoint"] = chosen
        new["seal_candidates"] = ",".join(sorted(candidates))
        if notes:
            new["seal_note"] = "；".join(notes)
        out_glyphs.append(new)

    out_glyphs.sort(key=lambda g: (str(g.get("codepoint") or ""),
                                   str(g.get("source_id") or "")))
    for index, glyph in enumerate(out_glyphs, 1):
        glyph["glyph_id"] = index

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = dict(manifest)
    manifest["glyphs"] = out_glyphs
    manifest["key_note"] = (
        "键 = Unicode 篆书区块码位（5 位十六进制）；现代字 → 码位的映射来自 Unicode 18.0 "
        "SealSources.txt 的 kSEAL_MCJK 属性（经 glyphs/seal/external.csv 整理），"
        "正篆/重文的取舍依 OpenCC SealCharacters.txt 反查表。"
    )

    # 字形文件一并复制到输出目录：**清单里的 file 是相对清单目录的路径**，
    # 而 import_glyph_layer.py 就是照这个相对路径找文件的。清单目录必须自带
    # 字形，否则下一步导入会报「文件不存在」。
    src_root = manifest_path.parent
    copied = 0
    for glyph in out_glyphs:
        rel = str(glyph.get("file") or "").strip()
        if not rel:
            raise SystemExit(f"清单里有一条记录缺 file 字段：{glyph.get('unicode')}")
        src = (src_root / rel).resolve()
        if not src.is_file():
            raise SystemExit(f"找不到字形文件：{src}")
        dest = out_dir / Path(rel).name
        if not dest.is_file() or dest.read_bytes() != src.read_bytes():
            shutil.copyfile(src, dest)
        glyph["file"] = dest.name
        copied += 1

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    used = {g["codepoint"] for g in out_glyphs}
    block_total = len(reverse)
    print(f"清单字形        : {len(manifest.get('glyphs', []))}")
    print(f"指派到码位      : {len(out_glyphs)}")
    print(f"现代字无篆书码位: {no_codepoint}")
    print(f"候选来自登记表  : {from_registry}")
    print(f"多码位的字      : {multi}（其余码位留空）")
    print(f"兜底取最小码位  : {fallback}")
    print(f"篆书区块覆盖率  : {len(used)} / {block_total}"
          f"（{len(used) * 100.0 / max(1, block_total):.1f}%）")
    print(f"字形文件        : 复制 {copied} 个到 {out_dir}")
    print(f"写出            : {out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
