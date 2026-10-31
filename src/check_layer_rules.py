#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""层的**不变量**体检：规则统一、无重复字、字正确、相关信息更新正确。

``src/verify_provenance.py`` 管的是「有出处、文件在不在、校验值对不对」，
``src/check_glyphs.py`` 管的是「SVG 本身合不合法」。两者都不管**层自己的规矩**——
同一层里会不会出现两条一样的字、两个一样的桶、一个字多记了几条、
「现代字」和它的码位对不对得上。这一层的不变量在这里查。

四条不变量
----------

1. **规则统一**——每层的分桶维度与每字上限与 ``LAYER_RULES`` 一致；
   层内「(现代字, 桶键)」在**同一来源批次内**唯一；
   每个现代字的条数不超过该层的上限。
2. **无重复字**——「(现代字, 字形键)」唯一；同一现代字的同一个出處不重复登记。
3. **字正确**——``unicode`` 必须等于 ``modern_char`` 的码位；
   临时身份条目（``modern_char`` 与 ``unicode`` 都空）必须留 ``modern_char_slot``；
   **私用區码位不得当汉字码位**写进 ``unicode`` 列。
4. **相关信息更新正确**——index.csv 行数与 provenance 记录数对得上；
   ``glyph_id`` 连续 1..N；index 的每一行都能在 provenance 里找到对应记录，
   反之亦然。

用法::

    python src/check_layer_rules.py --repo-root .
    python src/check_layer_rules.py --layer clerical
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from build_xxt_manifest import LAYER_RULES  # noqa: E402
from fetch_zdic_glyphs import canonical_era  # noqa: E402

#: 层 → (分桶维度, 每字上限, 桶键取自哪一列, 桶键按什么算)
#:
#: 桶键那一列与 ``LAYER_RULES`` 的分桶维度对应：
#: ``era`` 取 ``period``（时代），``oracle`` 取 ``source_book``（著錄號+組），
#: ``book`` 取 ``source_book``（文献）。
#:
#: 第四项是「桶键按文献算还是按字形算」——甲骨层是 ``shape``：
#: 同一著錄下**可以有多条摹本**（「菁1.1合6057賓組」有两个字形：42_F4F2 与 42_F4F3），
#: 它的唯一键是 **(现代字, 字形键)**。按文献分桶会把这些摹本误判成重复，
#: 所以这一层**不查文献桶**，只查 (现代字, 字形键)。
LAYER_BUCKET: dict[str, tuple[str, int, str, str]] = {
    "clerical": ("era", 6, "period", "doc"),
    "bronze": ("era", 8, "period", "doc"),
    "oracle": ("oracle", 8, "source_id", "shape"),
    "chu": ("book", 5, "source_book", "doc"),
    "chuanchao": ("book", 5, "source_book", "doc"),
    "qinwenzi": ("book", 5, "source_book", "doc"),
}

#: 层 → 键模式。``glyph_id`` 层的文件名是本仓库条目号；篆书层用篆书区块码位，
#: 字体层用现代字码位——这两类的键**本身就是唯一键**，不另查条目号。
KEY_MODE: dict[str, str] = {
    "oracle": "glyph_id", "bronze": "glyph_id", "clerical": "glyph_id",
    "chu": "glyph_id", "chuanchao": "glyph_id", "qinwenzi": "glyph_id",
    "seal": "seal_codepoint",
    "kaishu": "unicode_codepoint", "xingshu": "unicode_codepoint",
    "caoshu": "unicode_codepoint", "songti": "unicode_codepoint",
    "songti-tc": "unicode_codepoint", "heiti-hk": "unicode_codepoint",
}

#: 私用區区段——**不得**当汉字码位写进 unicode 列。
PUA_START, PUA_END = 0xE000, 0xF8FF


def load_provenance(path: Path) -> dict[str, dict]:
    """path → 记录（同一路径有多条时保留 skeleton 那一层）。"""
    out: dict[str, dict] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        p = str(rec.get("path") or "")
        if not p:
            continue
        prev = out.get(p)
        if prev is None or (str(rec.get("layer", "")) == "skeleton"
                            and str(prev.get("layer", "")) != "skeleton"):
            out[p] = rec
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="层的规则与不变量体检")
    ap.add_argument("--repo-root", type=Path, default=ROOT)
    ap.add_argument("--layer", default=None, help="只查某一层")
    args = ap.parse_args(argv)
    root = args.repo_root.resolve()

    problems: list[str] = []
    layers = sorted(p.name for p in (root / "glyphs").iterdir()
                    if p.is_dir() and (p / "index.csv").is_file())
    if args.layer:
        layers = [x for x in layers if x == args.layer]

    for layer in layers:
        index_path = root / "glyphs" / layer / "index.csv"
        prov_path = root / "glyphs" / "provenance" / f"{layer}.jsonl"
        with index_path.open("r", encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        prov = load_provenance(prov_path)

        # ---- 4. 相关信息更新正确 ----
        key_mode = KEY_MODE.get(layer, "glyph_id")
        gid_seen: set[int] = set()
        if key_mode == "glyph_id":
            for i, row in enumerate(rows, 2):
                gid = row.get("glyph_id", "")
                if not gid.isdigit():
                    problems.append(f"{layer}/index.csv:{i} glyph_id 不是数字：{gid!r}")
                    continue
                n = int(gid)
                if n in gid_seen:
                    problems.append(f"{layer}/index.csv:{i} glyph_id 重复：{n}")
                gid_seen.add(n)
            if gid_seen and sorted(gid_seen) != list(range(1, len(gid_seen) + 1)):
                missing = sorted(set(range(1, max(gid_seen) + 1)) - gid_seen)
                problems.append(f"{layer}/index.csv: glyph_id 不是连续的 1..N，缺 {missing[:10]}")

        idx_paths = set()
        for i, row in enumerate(rows, 2):
            rel = f"glyphs/{layer}/{row.get('file', '')}"
            idx_paths.add(rel)
            if rel not in prov:
                problems.append(f"{layer}/index.csv:{i} 这一行在 provenance 里没有记录：{rel}")
        # provenance 里同一路径可能还有**派生件**（甲骨的 outline/ 在子目录里）——
        # 那些不在 index.csv 里是正常的，只查层目录下的直接文件。
        extra = {p for p in prov if "/" not in p[len(f"glyphs/{layer}/"):]
                 and p not in idx_paths}
        if extra:
            problems.append(f"{layer}: provenance 有 {len(extra)} 条不在 index 里，"
                            f"例如 {sorted(extra)[:3]}")
        n_prov_layer = sum(1 for p in prov if "/" not in p[len(f"glyphs/{layer}/"):])
        if len(rows) != n_prov_layer:
            problems.append(f"{layer}: index {len(rows)} 行 vs provenance {n_prov_layer} 条"
                            f"（对不上）")

        # ---- 3. 字正确 ----
        for i, row in enumerate(rows, 2):
            ch = (row.get("modern_char") or "").strip()
            cp = (row.get("unicode") or "").strip()
            if not ch and not cp:
                # 临时身份条目：必须留槽位线索。
                rec = prov.get(f"glyphs/{layer}/{row.get('file', '')}", {})
                if not str(rec.get("modern_char_slot") or "").strip():
                    problems.append(f"{layer}/index.csv:{i} 临时身份条目没有 modern_char_slot")
                continue
            if not ch or not cp:
                problems.append(f"{layer}/index.csv:{i} modern_char 与 unicode 只空了一个："
                                f"{ch!r} / {cp!r}")
                continue
            if len(ch) != 1:
                problems.append(f"{layer}/index.csv:{i} modern_char 不是单字：{ch!r}")
                continue
            # 现代字码位一律写成 **6 位大写十六进制**（AGENTS.md 的口径）。
            want = f"{ord(ch):06X}"
            if cp != want:
                problems.append(f"{layer}/index.csv:{i} unicode {cp} 与 modern_char "
                                f"{ch}（应为 {want}）对不上")
            n = int(cp, 16)
            if PUA_START <= n <= PUA_END:
                problems.append(f"{layer}/index.csv:{i} unicode {cp} 落在私用區——"
                                f"私用區码位不是汉字码位，不得当身份用")

        # ---- 1 & 2. 规则统一 / 无重复字 ----
        spec = LAYER_BUCKET.get(layer)
        if not spec:
            continue
        mode, cap, bucket_col, bucket_by = spec
        if LAYER_RULES.get(layer, (mode, cap))[1] != cap:
            problems.append(f"{layer}: 每字上限与 LAYER_RULES 对不上")

        def r_bucket(row: dict) -> str:
            """这一行的桶键——与 build_xxt_manifest.bucket_of_zdic_row 同一口径。"""
            if bucket_by == "shape":
                # 按字形分桶：桶键就是字形键（source_id）。
                return (row.get("source_id") or "").strip()
            if mode == "era":
                period = (row.get("period") or "").strip()
                if period:
                    return canonical_era(period)
                return ((row.get("source_book") or "").strip()
                        + (row.get("source_number") or "").strip())
            return (row.get(bucket_col) or "").strip()
        # **每字上限的计数键 = 现代字码位**（没有码位的临时身份条目用槽位）。
        # 与 plan_xxt_fetch.py 同一口径：那边按 ``unicode`` 统计层里已有的条数，
        # 这边就按 ``unicode`` 统计——两边不同口径，合并时就会算出两个上限。
        # （甲骨层的 JGW 異體字是**不同的码位**：同一个现代字可以有两个码位，
        #   按现代字算会多算一条，按码位算才是层里真实的条数。）
        def id_key(row: dict) -> str:
            cp = (row.get("unicode") or "").strip()
            if cp:
                return cp
            slot = (row.get("modern_char_slot") or "").strip()
            if slot:
                return "slot:" + slot
            return (row.get("modern_char") or "").strip()

        # 同一来源批次内，「(现代字, 桶键)」唯一；每字条数不超过上限。
        by_batch: dict[str, list[dict]] = collections.defaultdict(list)
        for row in rows:
            rec = prov.get(f"glyphs/{layer}/{row.get('file', '')}", {})
            batch = str(rec.get("source_dataset") or "?")
            by_batch[batch].append(row)

        # **整层口径的每字上限**（只在层里已有小学堂批次时才查）：
        #
        # 每字上限是**取图/入库时**的规则：上限 = max(来源上限, 现有层每字最大条数)，
        # 也就是「合并时不给已经满额的字再加」。合并后能不能验，就看这一条：
        # 「其它批次（= 合并前的既有事实）」里这个字最多有几条，
        # 合并后总条数就不能超过 max(来源上限, 那个最大值)。
        layer_cap_note = ""
        xst_batches = {b for b in by_batch if b.startswith("小学堂 ")}
        if xst_batches:
            pre = collections.Counter()
            for batch, brows in by_batch.items():
                if batch in xst_batches:
                    continue
                for row in brows:
                    k = id_key(row)
                    if k:
                        pre[k] += 1
            layer_cap_total = max(cap, max(pre.values()) if pre else 0)
            final = collections.Counter()
            for brows in by_batch.values():
                for row in brows:
                    k = id_key(row)
                    if k:
                        final[k] += 1
            over_total = {k: v for k, v in final.items() if v > layer_cap_total}
            if over_total:
                layer_cap_note = (
                    f"{layer}: 合并后有 {len(over_total)} 个字超过每字上限 {layer_cap_total}"
                    f"（整层口径），例如 {list(over_total.items())[:3]}")
        for batch, brows in by_batch.items():
            seen_bucket: dict[tuple[str, str], int] = {}
            seen_shape: dict[tuple[str, str], int] = {}
            # 这一批不用分桶维度（比如甲骨层的 JGW 批：它按自己的条目号记，
            # bucket 那一列整列是空的）→ 不查桶键。
            uses_bucket = any((r.get(bucket_col) or "").strip() for r in brows)
            # **按字形分桶的层不查文献桶**：桶键就是字形键，
            # (现代字, 桶键) 与 (现代字, 字形键) 是同一个检查，查两遍只会重复报。
            if bucket_by == "shape":
                uses_bucket = False
            for row in brows:
                ch = (row.get("modern_char") or "").strip()
                sid = (row.get("source_id") or "").strip()
                if not ch:
                    # 临时身份条目：现代字身份还没定出来，没有「字」可分桶，
                    # 它的唯一线索是 modern_char_slot（由「字正确」那组检查管）。
                    if sid:
                        skey = ("<临时身份>", sid)
                        if skey in seen_shape:
                            problems.append(f"{layer}: 同一个字形键 {sid!r} 出现两次"
                                            f"（临时身份条目）")
                        else:
                            seen_shape[skey] = int(row.get("glyph_id") or 0)
                    continue
                bucket = (r_bucket(row) if uses_bucket else "")
                key = (ch, bucket)
                if uses_bucket and key in seen_bucket:
                    problems.append(f"{layer}: 同一个 (现代字 {ch!r}, 桶键 {bucket!r}) "
                                    f"在批次「{batch}」里出现两次（glyph_id "
                                    f"{seen_bucket[key]} 与 {row.get('glyph_id')}）")
                elif uses_bucket:
                    seen_bucket[key] = int(row.get("glyph_id") or 0)
                if sid:
                    skey = (ch, sid)
                    if skey in seen_shape:
                        problems.append(f"{layer}: 同一个 (现代字 {ch!r}, 字形键 {sid!r}) "
                                        f"在批次「{batch}」里出现两次")
                    else:
                        seen_shape[skey] = int(row.get("glyph_id") or 0)
            per_char = collections.Counter(
                k for k in (id_key(r) for r in brows) if k)
            over = {k: v for k, v in per_char.items() if v > cap}
            if over:
                problems.append(f"{layer}: 批次「{batch}」有 {len(over)} 个字超过每字上限 "
                                f"{cap}，例如 {list(over.items())[:3]}")

        # **整层口径的每字上限**：上限是 max(来源上限, 该字在层里最多的那条批次的条数)
        # ——后者就是「不动已有记录」的意思。一个字可以超过来源上限，
        # 但那必须是因为**某一批次本来就有这么多条**，不能是合并时新堆上去的。
        if layer_cap_note:
            problems.append(layer_cap_note)

    print(f"检查层        : {len(layers)} 个（{', '.join(layers)}）")
    if problems:
        cats = collections.Counter(p.split("：")[0].split(":")[0] for p in problems)
        print(f"问题          : {len(problems)} 项")
        for c, n in cats.most_common():
            print(f"  - {c}：{n} 项")
        for p in problems[:20]:
            print("    ·", p)
        if len(problems) > 20:
            print(f"    … 还有 {len(problems) - 20} 项")
        return 1
    print("问题          : 0 项")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
