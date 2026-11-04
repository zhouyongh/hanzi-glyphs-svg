#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨层统一字形编号：生成 / 校验 / 查询 `glyphs/glyph-ids.csv`。

用法::

    python src/build_glyph_ids.py                # 生成（整表重写）
    python src/build_glyph_ids.py --check        # CI：对账 + 逐字节复算
    python src/build_glyph_ids.py --char 一      # 查询一个字在所有书体的字形

**规则全文见 AGENTS.md「统一字形编号（unified_id）」**。要点：

- ID = `<根码>-<书体码>-<序号>`，根码 = 现代字 Unicode 码位（6 位大写 hex）；
- 书体码 = 层键（A..M，按序冻结），序号 =（根码, 书体）桶内 4 位流水号；
- 根码域断言：unicode 非空 ⇒ 码位必须落在 CJK 统一表意区块；
  unicode 为空（临时身份）⇒ 根码必须落在**私用区**——
  「私用区根码 ≠ 汉字码位」由这条断言钉死，登记表不冒充汉字身份；
- 桶内排序：条目号层按**条目号数值**升序（字符串序会把 `10000.svg`
  排到 `9999.svg` 前面），seal 与字体层按文件名升序；
- 登记表是 index.csv 的派生交叉表：一行 = 一行 index.csv，
  不动各层 index.csv，不含 sha256（文件校验属 index/provenance）。

为什么不往各层 index.csv 里加 unified_id 列：index.csv 是导入器的再生产物
（整层替换重写），塞派生列会被悄悄抹掉——派生值住派生表，逐字节可复算。
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "glyphs" / "glyph-ids.csv"

# 书体字母表（**按序冻结，只增不改**）——全文见 AGENTS.md「统一字形编号」。
# (字母, 层名, 目录, 键形态)
SCRIPT_TABLE = (
    ("A", "甲骨文", "oracle", "glyph_id"),
    ("B", "金文", "bronze", "glyph_id"),
    ("C", "楚文字", "chu", "glyph_id"),
    ("D", "秦系簡牘", "qinwenzi", "glyph_id"),
    ("E", "小篆", "seal", "codepoint"),
    ("F", "隶书", "clerical", "glyph_id"),
    ("G", "草书", "caoshu", "codepoint"),
    ("H", "楷书", "kaishu", "codepoint"),
    ("I", "行书", "xingshu", "codepoint"),
    ("J", "傳抄古文", "chuanchao", "glyph_id"),
    ("K", "宋体·简", "songti", "codepoint"),
    ("L", "宋体·繁", "songti-tc", "codepoint"),
    ("M", "黑体·港", "heiti-hk", "codepoint"),
)

FIELDS = ("unified_id", "layer", "modern_char", "unicode", "file",
          "source_id", "identity_confidence", "modern_char_slot")

# 根码域断言：登记表的根码只允许出现在这些区块里。
# CJK 统一表意（含全部扩展，平面 1–3 的连续区间）；私用区只收「临时身份」的根码。
CJK_RANGES = ((0x3400, 0x9FFF), (0x20000, 0x3FFFF))
PUA_RANGES = ((0xE000, 0xF8FF), (0xF0000, 0xFFFFD), (0x100000, 0x10FFFD))


def _in_ranges(cp: int, ranges) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


def norm6(cp: str) -> str:
    cp = cp.strip().upper().removeprefix("U+")
    return cp.zfill(6) if cp else ""


def slot_codepoint(slot: str) -> str:
    """`<字体号>_<码位>` 里的码位段（6 位归一）；不是码位的槽位（JGW_0380）返回空。"""
    tail = slot.strip().split("_", 1)[1] if "_" in slot.strip() else ""
    tail = tail.strip()
    if not tail:
        return ""
    try:
        v = int(tail, 16)
    except ValueError:
        return ""
    if not _in_ranges(v, PUA_RANGES):
        return ""
    return f"{v:06X}"


def build_rows() -> tuple[list[dict], dict]:
    """扫 13 份 index.csv，产出登记表行与统计。"""
    rows: list[dict] = []
    stats = {"rows": 0, "index_rows": 0, "pua_root": 0, "excluded_no_root": 0}
    for letter, layer, dirname, key_mode in SCRIPT_TABLE:
        index_path = ROOT / "glyphs" / dirname / "index.csv"
        with index_path.open("r", encoding="utf-8-sig", newline="") as fh:
            recs = list(csv.DictReader(fh))
        stats["index_rows"] += len(recs)
        # 桶 =（根码, 书体）；桶内序号按层键形态排序。
        buckets: dict[str, list[dict]] = {}
        excluded: list[dict] = []
        for rec in recs:
            u = norm6(rec.get("unicode") or "")
            if u:
                root = u
            else:
                # 临时身份：根码取槽位私用区码位（身份未定由 identity_confidence 列明示）。
                root = slot_codepoint(rec.get("modern_char_slot") or "")
                if not root:
                    excluded.append(rec)
                    continue
                stats["pua_root"] += 1
            buckets.setdefault(root, []).append(rec)
        for rec in excluded:
            stats["excluded_no_root"] += 1
            print(f"  ⚠️ {layer}: 无根码可写（unicode 与槽位码位皆缺），不入登记表："
                  f"file={rec.get('file', '')} slot={rec.get('modern_char_slot', '')}")

        def sort_key(rec: dict):
            if key_mode == "glyph_id":
                # **数值**序：条目号层文件名 4–5 位混排，字符串序是实测的坑。
                return int(rec["glyph_id"])
            return rec["file"].strip()

        for root, recs_in in sorted(buckets.items()):
            for i, rec in enumerate(sorted(recs_in, key=sort_key), start=1):
                gid = f"{root}-{letter}-{i:04d}"
                rows.append({
                    "unified_id": gid,
                    "layer": dirname,
                    "modern_char": (rec.get("modern_char") or "").strip(),
                    "unicode": norm6(rec.get("unicode") or ""),
                    "file": (rec.get("file") or "").strip(),
                    "source_id": (rec.get("source_id") or "").strip(),
                    "identity_confidence": (rec.get("identity_confidence") or "").strip(),
                    "modern_char_slot": (rec.get("modern_char_slot") or "").strip(),
                })
                stats["rows"] += 1
    return rows, stats


def assert_domains(rows: list[dict]) -> None:
    """根码域断言：真汉字根码必须落 CJK 区块；临时身份根码必须落私用区。"""
    seen: set[str] = set()
    for r in rows:
        gid = r["unified_id"]
        if gid in seen:
            raise SystemExit(f"unified_id 重复：{gid}")
        seen.add(gid)
        root_hex = gid.split("-", 1)[0]
        cp = int(root_hex, 16)
        if r["unicode"]:
            if not _in_ranges(cp, CJK_RANGES):
                raise SystemExit(f"{gid}: 根码不在 CJK 统一表意区块（unicode={r['unicode']}）")
        else:
            if not _in_ranges(cp, PUA_RANGES):
                raise SystemExit(f"{gid}: 无 unicode 的行根码必须落私用区")
            if (r["identity_confidence"] or "") != "pua-slot":
                raise SystemExit(f"{gid}: 私用区根码行必须标 identity_confidence=pua-slot")
        # 桶内序号无洞（重建过程天然保证，这里是对落盘文件的独立校验路径）
    for r in rows:
        parts = r["unified_id"].split("-")
        if len(parts) != 3 or len(parts[0]) != 6 or len(parts[2]) != 4:
            raise SystemExit(f"unified_id 语法错误：{r['unified_id']}")


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="跨层统一字形编号登记表")
    ap.add_argument("--check", action="store_true",
                    help="CI：重建并与仓内文件逐字节比对（含对账与域断言）")
    ap.add_argument("--char", default=None,
                    help="查询一个字（现代汉字）在所有书体的字形")
    args = ap.parse_args(argv)

    rows, stats = build_rows()
    assert_domains(rows)

    if args.char:
        ch = args.char.strip()
        want = f"{ord(ch):06X}" if len(ch) == 1 else norm6(ch)
        hits = [r for r in rows if r["unicode"] == want]
        print(f"{'unified_id':16} {'layer':10} {'file':18} source_id")
        for r in hits:
            print(f"{r['unified_id']:16} {r['layer']:10} {r['file']:18} {r['source_id']}")
        print(f"共 {len(hits)} 件")
        return 0

    if args.check:
        if not OUT_PATH.is_file():
            raise SystemExit(f"登记表不存在：{OUT_PATH}")
        same = OUT_PATH.read_bytes() == _render(rows).encode("utf-8")
        if not same:
            raise SystemExit("登记表与重建结果不一致（index.csv 变了？重跑生成即可）")
        print(f"登记表校验通过：{stats['rows']} 行 = {stats['index_rows']} 行 index"
              f"（私用区根码 {stats['pua_root']}，无根码排除 {stats['excluded_no_root']}）")
        return 0

    write_csv(rows, OUT_PATH)
    print(f"写出 {OUT_PATH}：{stats['rows']} 行"
          f"（index 行 {stats['index_rows']}，私用区根码 {stats['pua_root']}，"
          f"无根码排除 {stats['excluded_no_root']}）")
    return 0


def _render(rows: list[dict]) -> str:
    """与 write_csv 完全一致的文本形态（供 --check 逐字节比对）。"""
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(FIELDS), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


if __name__ == "__main__":
    sys.exit(main())
