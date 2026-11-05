#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小學堂小篆批 → seal 层码位键清单（小篆批并入漢典篆书层的合并清单）。

用法::

    python src/build_xiaozhuan_seal_manifest.py \
        --zheng-table tmp/research/seal-modern-to-zheng.txt \
        --pairs-iou tmp/seal-merge-pairs-iou.jsonl \
        --out tmp/zdic/xiaozhuan-seal-fills/manifest.json

**解决什么问题。** glyphs/xiaozhuan/（小學堂「小篆」庫描摹件，条目号键）要并入
glyphs/seal/（漢典《說文》系小篆，键 = Unicode 篆书区块码位）。两层材料不同
（同一說文槽位两边各自绘制），合并按「(现代字, 槽位)」判重，**重复取漢典矢量件**
（仓库既有规则），小學堂件只补漢典的缺口。本脚本把 7,284 件逐一判定：

    并入（fills）/ 重复取漢典 / 放弃（按原因）

三部分合计必须恰等于 7,284（对账断言），判定逐条写入 crosswalk。

**码位怎么定（不新造码位）。** seal 层的键空间是 registry（`glyphs/seal/external.csv`）
登记的全部 11,328 个码位，每个码位 = 一个《說文》字形位。小學堂件按其**现代字**
路由到 registry 里属于这个字的码位：

- **部別桶**（``說文‧X部`` = 正篆位）→ 目标 = 正篆表（``build_seal_zheng_table.py``
  生成，规则与 Unicode §18.14 一致）里这个字的**正篆码位**；
- **重文桶**（說文古文/籀文/或體/篆文/俗字/奇字 = 变体位）→ 目标 = 这个字在 registry
  里的**变体码位**；只有「恰好一个空位」时才收（无歧义闸——两个以上空位时无从知道
  这件描摹的是哪个重文，不猜）。

**四道闸**（任一不过就不并入，crosswalk 记原因）：

1. **重复闸**：槽位与 seal 重叠、且现代字与 seal 那条一致 → 重复，取漢典矢量件
   （形状一致性由 `compare_glyph_shapes.py --pairs` 的同槽位 IoU 佐证，随 crosswalk 记录）；
2. **占位闸**：目标码位已被 seal 占用（同字已在层里，哪怕槽位不同）→ 不重复收；
3. **registry 一致性闸**：目标码位在 external.csv 里的现代字必须与本件现代字一致——
   对不上说明路由错了，宁可漏收；
4. **无歧义闸**：重文位必须恰好一个空位。

**槽位相同、现代字不同不是重复**：漢典把该槽位的字形记作异体读法、小學堂记的是
楷書正字，两边各记一条（AGENTS.md 混合层既有规则，楚系层实测同款现象）——
这种件照常走码位路由。

**identity_confidence="pua-slot" 的件**（现代字未知）无法路由码位，全部不并入。

输出：

- ``--out``：seal 码位键清单（item 带 ``codepoint`` 字段，``layer=outline``、
  ``source_dataset=小学堂``、``trace_iou`` 等派生字段逐条继承小學堂 provenance）；
  ``file`` 写**相对清单目录**的路径（合并器按「清单所在目录 + file」找字形）；
- ``--crosswalk``：7,284 条逐件判定。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 小學堂的重文類別桶（source_book 的这些值 = 变体位；其余「說文‧X部」= 正篆位）。
VARIANT_BUCKETS = {"說文古文", "說文籀文", "說文或體", "說文篆文", "說文俗字", "說文奇字"}


def norm6(cp: str) -> str:
    return cp.strip().upper().removeprefix("U+")


def norm5(cp: str) -> str:
    """6 位 → 5 位（篆书区块文件名形态）。registry/正篆表记 6 位补零（03D000），
    seal 文件名 5 位（3D000）。"""
    cp = norm6(cp)
    if len(cp) == 6 and cp.startswith("0"):
        cp = cp[1:]
    return cp


def load_zheng(path: Path) -> dict[str, dict]:
    """正篆表：现代字码位（6 位）→ 行。"""
    out: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            cp = norm6(row.get("modern_cp") or "")
            if cp:
                out[cp] = row
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="小學堂小篆批并入 seal 层的合并清单")
    ap.add_argument("--xz-index", type=Path, default=ROOT / "glyphs/xiaozhuan/index.csv")
    ap.add_argument("--xz-provenance", type=Path,
                    default=ROOT / "glyphs/provenance/xiaozhuan.jsonl")
    ap.add_argument("--seal-index", type=Path, default=ROOT / "glyphs/seal/index.csv")
    ap.add_argument("--registry", type=Path, default=ROOT / "glyphs/seal/external.csv")
    ap.add_argument("--zheng-table", type=Path,
                    default=ROOT / "tmp/research/seal-modern-to-zheng.txt")
    ap.add_argument("--pairs-iou", type=Path, default=ROOT / "tmp/seal-merge-pairs-iou.jsonl",
                    help="compare_glyph_shapes.py --pairs 的输出（同槽位 IoU 佐证）")
    ap.add_argument("--out", type=Path, default=ROOT / "tmp/zdic/xiaozhuan-seal-fills/manifest.json")
    ap.add_argument("--crosswalk", type=Path,
                    default=ROOT / "tmp/xxt/xiaozhuan/merge-crosswalk.jsonl")
    ap.add_argument("--published-csv", type=Path,
                    default=ROOT / "glyphs/seal/xiaozhuan-merge-crosswalk.csv",
                    help="发布版逐件判定表（进仓，供读者查「这件小學堂描摹件为什么没进"
                         "seal 层/放在哪个码位」；tmp 的 JSONL 是 gitignore 的，清一次就没了）")
    args = ap.parse_args(argv)

    # ---- seal 侧现状 ----
    seal_rows_by_slot: dict[str, list[dict]] = defaultdict(list)
    occupied: dict[str, dict] = {}
    for row in csv.DictReader(args.seal_index.open("r", encoding="utf-8-sig")):
        cp = norm5(row.get("codepoint") or "")
        sid = (row.get("source_id") or "").strip()
        if cp:
            occupied[cp] = row
        if sid:
            seal_rows_by_slot[sid].append(row)
    seal_unicodes = {norm6(r.get("unicode") or "") for r in occupied.values()}

    # registry：码位 → 行；现代字 → 码位组
    registry: dict[str, dict] = {}
    by_modern: dict[str, list[str]] = defaultdict(list)
    for row in csv.DictReader(args.registry.open("r", encoding="utf-8-sig")):
        cp = norm5(row.get("codepoint") or "")
        if not cp:
            continue
        registry[cp] = row
        by_modern[norm6(row.get("unicode") or "")].append(cp)

    zheng = load_zheng(args.zheng_table)

    iou_by_slot: dict[str, float] = {}
    if args.pairs_iou.is_file():
        for line in args.pairs_iou.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("iou") is not None:
                iou_by_slot[rec["slot"]] = float(rec["iou"])

    prov_by_path = {}
    with args.xz_provenance.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rec = json.loads(line)
                prov_by_path[rec.get("path", "")] = rec

    out_dir = args.out.resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    args.crosswalk.parent.mkdir(parents=True, exist_ok=True)

    fills: list[dict] = []
    crosswalk: list[dict] = []
    claimed_cp: dict[str, str] = {}
    stats: dict[str, int] = defaultdict(int)

    rows = list(csv.DictReader(args.xz_index.open("r", encoding="utf-8-sig")))
    for row in rows:
        sid = (row.get("source_id") or "").strip()
        u = norm6(row.get("unicode") or "")
        mc = (row.get("modern_char") or "").strip()
        book = (row.get("source_book") or "").strip()
        gid = (row.get("glyph_id") or "").strip()
        xz_file = f"glyphs/xiaozhuan/{(row.get('file') or '').strip()}"
        base = {"glyph_id_xz": gid, "slot": sid, "modern_char": mc, "unicode": u,
                "source_book": book}

        if not u:
            # pua-slot：现代字未知 → 无法路由码位。
            stats["pua_no_identity"] += 1
            crosswalk.append({**base, "kind": "dropped", "reason": "pua_no_identity",
                              "note": "现代字身份未定（identity_confidence=pua-slot），"
                                      "无法路由到篆书区块码位，不并入"})
            continue

        if u not in zheng:
            stats["char_not_in_registry"] += 1
            crosswalk.append({**base, "kind": "dropped", "reason": "char_not_in_registry",
                              "note": "现代字不在篆书区块 registry/正篆表里，无处可放"})
            continue

        is_variant = book in VARIANT_BUCKETS
        zrow = zheng[u]
        zheng_cp = norm5(zrow.get("zheng_cp_repo5") or zrow.get("zheng_cp") or "")

        if is_variant:
            # 变体位：这个字在 registry 里除正篆外的码位；只收「恰好一个空位」。
            cands = [norm5(c) for c in (zrow.get("candidates") or "").split() if c]
            empty = [c for c in cands if c != zheng_cp and c not in occupied]
            if len(empty) == 0:
                stats["variant_no_empty_slot"] += 1
                crosswalk.append({**base, "kind": "dropped", "reason": "variant_no_empty_slot",
                                  "note": "重文位无空码位（该字重文位已被占或未登记），"
                                          "seal 层每字只落正篆，不并入"})
                continue
            if len(empty) > 1:
                stats["variant_ambiguous"] += 1
                crosswalk.append({**base, "kind": "dropped", "reason": "variant_ambiguous",
                                  "note": f"该字有 {len(empty)} 个空重文码位"
                                          f"（{'、'.join(empty)}），无从确定本件对应哪个，不猜"})
                continue
            target = empty[0]
            seal_note = (f"本码位为该字的重文/变体位，由小學堂描摹件补缺"
                         f"（桶={book}，槽位={sid}）；正篆码位 {zheng_cp or '（未登记）'} 另有处理")
        else:
            target = zheng_cp
            if not target or target not in registry:
                stats["zheng_missing"] += 1
                crosswalk.append({**base, "kind": "dropped", "reason": "zheng_missing",
                                  "note": "正篆表未给出可用的正篆码位"})
                continue
            seal_note = ""

        # 占位闸 + registry 一致性闸
        if target in occupied:
            stats["target_occupied"] += 1
            iou = iou_by_slot.get(sid)
            crosswalk.append({**base, "kind": "duplicate", "reason": "target_occupied",
                              "target_codepoint": target,
                              "iou_same_slot": iou,
                              "note": f"目标码位 {target} 已有漢典矢量件（同字），"
                                      f"重复取漢典"
                                      + (f"；同槽位 IoU={iou:.4f}" if iou is not None else "")})
            continue
        if norm6(registry[target].get("unicode") or "") != u:
            stats["registry_mismatch"] += 1
            crosswalk.append({**base, "kind": "dropped", "reason": "registry_mismatch",
                              "target_codepoint": target,
                              "note": f"registry 里 {target} 的现代字与本事由不一致"
                                      f"（{registry[target].get('modern_char', '')} vs {mc}），不并入"})
            continue
        if target in claimed_cp:
            stats["target_claimed_twice"] += 1
            crosswalk.append({**base, "kind": "dropped", "reason": "target_claimed_twice",
                              "target_codepoint": target,
                              "note": f"目标码位已被本批另一件（{claimed_cp[target]}）占用"})
            continue

        # ---- 并入 ----
        prov = prov_by_path.get(xz_file, {})
        if not prov:
            stats["no_provenance"] += 1
            crosswalk.append({**base, "kind": "dropped", "reason": "no_provenance",
                              "note": "provenance 记录缺失"})
            continue
        claimed_cp[target] = gid
        rel_file = os.path.relpath((ROOT / xz_file).resolve(), out_dir).replace("\\", "/")
        item = {
            "file": rel_file,
            "codepoint": target,
            "modern_char": mc,
            "unicode": u,
            "period": (row.get("period") or "").strip(),
            "variant": (row.get("variant") or "").strip() or book,
            "source_book": book,
            "source_number": "",
            "source_id": sid,
            "source_path": (prov.get("source_path") or "").strip(),
            "source_url": (prov.get("source_url") or "").strip(),
            "source_page_url": (prov.get("source_page_url") or "").strip(),
            # 两个 sha256 都要给：local 是「清单目录里这个 SVG」的校验值，
            # source 是「上游原件（位图）」的校验值。字段名对齐 build_xxt_manifest——
            # 入库脚本先验 local_sha256，缺了才退回验 source_sha256（那是位图的，
            # 与描摹件必然不同，会误报不符）。
            "local_sha256": (prov.get("sha256") or "").strip(),
            "source_sha256": (prov.get("source_sha256") or "").strip(),
            "derived_from": (prov.get("derived_from") or "").strip(),
            "derived_from_sha256": (prov.get("derived_from_sha256") or "").strip(),
            "transform": (prov.get("transform") or "").strip(),
            "tool": (prov.get("tool") or "").strip(),
            "trace_iou": prov.get("trace_iou"),
            "identity_confidence": (prov.get("identity_confidence") or "").strip(),
            "modern_char_slot": (prov.get("modern_char_slot") or "").strip(),
            "modifications": (prov.get("modifications") or "").strip(),
            "source_base_pages": prov.get("source_base_pages", []),
            "source_references": prov.get("source_references", []),
            "layer": "outline",
            "license": prov.get("license") or "CC0-1.0",
            "license_url": prov.get("license_url")
                           or "https://creativecommons.org/publicdomain/zero/1.0/",
            "attribution": prov.get("attribution") or "",
            "source_dataset": prov.get("source_dataset") or "小学堂 xiaozhuan 字形資料庫",
            "retrieved_at": (prov.get("retrieved_at") or "").strip(),
            "seal_note": seal_note,
        }
        fills.append(item)
        stats["fill_zheng" if not is_variant else "fill_variant"] += 1
        crosswalk.append({**base, "kind": "fill", "target_codepoint": target,
                          "note": seal_note or "正篆位空缺，小學堂描摹件补缺"})

    # ---- 对账 + 落盘 ----
    # 每件输入恰产生一条 crosswalk（fill / duplicate / dropped 三种之一），
    # fills 与 crosswalk 里 kind=fill 的行必须一致。
    total = len(rows)
    if len(crosswalk) != total:
        raise SystemExit(f"对账失败：crosswalk {len(crosswalk)} != 输入 {total}")
    n_fill = sum(1 for c in crosswalk if c["kind"] == "fill")
    if n_fill != len(fills):
        raise SystemExit(f"对账失败：fills {len(fills)} != crosswalk fill {n_fill}")

    manifest = {
        "kind": "seal",
        "script": "seal",
        "layer": "outline",
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "attribution": "字形图来自小学堂（中央研究院數位文化中心）小篆資料庫，"
                       "依其《版權聲明》以 CC0 1.0 释出；本地 SVG 为自动描摹的派生件",
        "source_dataset": "小学堂 xiaozhuan 字形資料庫",
        "glyphs": fills,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    with args.crosswalk.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in crosswalk:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")

    # 发布版：一行一件，读者按槽位/条目号能查到每一件的去向。
    pub_fields = ["glyph_id_xz", "slot", "modern_char", "unicode", "source_book",
                  "kind", "reason", "target_codepoint", "iou_same_slot", "note"]
    args.published_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.published_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=pub_fields, lineterminator="\n")
        w.writeheader()
        for rec in crosswalk:
            w.writerow({k: rec.get(k, "") for k in pub_fields})

    print(f"输入 {total} 件：")
    print(f"  并入 fills     : {len(fills)}"
          f"（正篆位 {stats['fill_zheng']} + 重文位 {stats['fill_variant']}）")
    dup = sum(1 for c in crosswalk if c["kind"] == "duplicate")
    print(f"  重复取漢典     : {dup}")
    dropped = len(crosswalk) - dup
    print(f"  放弃（不并入） : {dropped}，按原因：")
    reasons = defaultdict(int)
    for c in crosswalk:
        if c["kind"] == "dropped":
            reasons[c["reason"]] += 1
    for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"    {reason:24s} {n}")
    print(f"清单 {args.out}")
    print(f"crosswalk {args.crosswalk}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
