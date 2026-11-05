#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨层统一字形编号：生成 / 校验 / 查询 `glyphs/glyph-ids.csv`（账本模式）。

用法::

    python src/build_glyph_ids.py                # 生成（账本合并：冻结已发布 ID）
    python src/build_glyph_ids.py --check        # CI：对账 + 逐字节复算
    python src/build_glyph_ids.py --char 一      # 查询一个字在所有书体的字形

**规则全文见 AGENTS.md「统一字形编号（unified_id）」**。要点：

- ID = `<根码>-<书体码>-<序号>`，如 `004E00-0E-000001` = 「一」的小篆第 1 件；
- 根码 = 现代字 Unicode 码位（6 位大写 hex）；
- 书体码 = **2 位**层键（当前 0A..0M，按序冻结；0 段用完后 10、11… 顺延，
  共 1,296 个位置），0E = 小篆；
- 序号 =（根码, 书体）桶内 **6 位**十进制流水（000001 起）；
- **冻结政策（2026-11-05）**：ID 一经发布**永不重排**——登记表是账本，
  账本键 = (层, 读法 unicode|槽位, source_id)，全仓实测 0 碰撞。
  现行行 status=active；行集合里消失的行 status=retired（ID 保留、
  序号永不复用）；新增行取桶内**最大已用号 + 1**。
  初始分配才用桶内排序（条目号层按条目号**数值**升序——字符串序会把
  `10000.svg` 排到 `9999.svg` 前面；seal 与字体层按文件名升序），
  分配之后不再重排。临时身份件身份补回后根码会变（私用区 → CJK），
  那是数据变更：旧行退役、新行按新根码铸发，不偷改旧 ID；
- 根码域断言：unicode 非空 ⇒ 码位必须落在 CJK 统一表意区块；
  unicode 为空（临时身份）⇒ 根码必须落在**私用区**——
  「私用区根码 ≠ 汉字码位」由这条断言钉死，登记表不冒充汉字身份；
- 登记表是 index.csv 的派生**账本**：active 行与 index 一一对应，
  不动各层 index.csv（sha256 不入表，文件校验属 index/provenance）。

为什么做成账本而不是纯派生：定位符升级为**可引用的持久标识符**，
前提是「铸发一次、永不改变」——纯派生在桶内插字形时会重排，引用即断。
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from era_sequence import (BRONZE_ERA_RANK, CHU_CORPUS_YEAR,  # noqa: E402
                          CLERICAL_ERA_RANK, era_rank, sort_key_with_year)

OUT_PATH = ROOT / "glyphs" / "glyph-ids.csv"

# 书体字母表（**按序冻结，只增不改**）——全文见 AGENTS.md「统一字形编号」。
# (书体码尾字, 层名, 目录, 键形态)；书体码 = "0" + 尾字。
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

FIELDS = ("unified_id", "status", "layer", "modern_char", "unicode", "file",
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


def ledger_key(layer: str, unicode_: str, slot: str, source_id: str) -> tuple:
    """账本键：(层, 读法 unicode|槽位, source_id)。全仓实测 0 碰撞。"""
    u = norm6(unicode_)
    return (layer, u or slot.strip(), (source_id or "").strip())


def load_ledger(path: Path) -> dict[tuple, dict]:
    """读旧账本（无文件 = 首次运行，返回空账）。"""
    ledger: dict[tuple, dict] = {}
    if not path.is_file():
        return ledger
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            key = ledger_key(row.get("layer", ""), row.get("unicode", ""),
                             row.get("modern_char_slot", ""), row.get("source_id", ""))
            ledger[key] = row
    return ledger


def collect_current(stats: dict) -> list[dict]:
    """扫 13 份 index.csv，产出**现行行**（带账本键与桶，不带最终序号）。"""
    current: list[dict] = []
    for tail, layer, dirname, key_mode in SCRIPT_TABLE:
        index_path = ROOT / "glyphs" / dirname / "index.csv"
        with index_path.open("r", encoding="utf-8-sig", newline="") as fh:
            recs = list(csv.DictReader(fh))
        stats["index_rows"] += len(recs)
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
            """桶内初始排序——**逐层取最硬的学术序**（原则见 AGENTS.md）：
            有时代/文献序的层按学术序、条目号平局判定；没有的层保持条目号
            （甲骨质记混杂、秦系同批、傳抄不可断代——诚实，不编造）。"""
            if dirname == "bronze":
                return sort_key_with_year(era_rank(BRONZE_ERA_RANK, rec.get("period") or ""),
                                          int(rec["glyph_id"]))
            if dirname == "clerical":
                return sort_key_with_year(era_rank(CLERICAL_ERA_RANK, rec.get("period") or ""),
                                          int(rec["glyph_id"]))
            if dirname == "chu":
                return sort_key_with_year(era_rank(CHU_CORPUS_YEAR, rec.get("source_book") or ""),
                                          int(rec["glyph_id"]))
            if key_mode == "glyph_id":
                # **数值**序：条目号层文件名 4–5 位混排，字符串序是实测的坑。
                return int(rec["glyph_id"])
            return rec["file"].strip()

        for root, recs_in in sorted(buckets.items()):
            for rec in sorted(recs_in, key=sort_key):
                current.append({
                    "bucket": f"{root}-0{tail}",
                    "layer": dirname,
                    "modern_char": (rec.get("modern_char") or "").strip(),
                    "unicode": norm6(rec.get("unicode") or ""),
                    "file": (rec.get("file") or "").strip(),
                    "source_id": (rec.get("source_id") or "").strip(),
                    "identity_confidence": (rec.get("identity_confidence") or "").strip(),
                    "modern_char_slot": (rec.get("modern_char_slot") or "").strip(),
                    "ledger_key": ledger_key(dirname, rec.get("unicode") or "",
                                             rec.get("modern_char_slot") or "",
                                             rec.get("source_id") or ""),
                })
                stats["current_rows"] += 1
    return current


def merge_ledger(current: list[dict], ledger: dict[tuple, dict],
                 stats: dict) -> list[dict]:
    """账本合并：已发布的 ID 原样保留；新增取桶内最大已用号 + 1；消失行退役。"""
    used: dict[str, int] = {}   # 桶（root-script）→ 最大已用序号（含退役）
    for old in ledger.values():
        parts = (old.get("unified_id") or "").split("-")
        if len(parts) == 3 and parts[2].isdigit():
            bucket = parts[0] + "-" + parts[1]
            used[bucket] = max(used.get(bucket, 0), int(parts[2]))

    out: list[dict] = []
    seen_keys: set[tuple] = set()
    for row in current:
        key = row["ledger_key"]
        old = ledger.get(key)
        if old is not None:
            seen_keys.add(key)
            stats["kept"] += 1
            gid = old["unified_id"]
        else:
            bucket = row["bucket"]
            seq = used.get(bucket, 0) + 1
            used[bucket] = seq
            stats["minted"] += 1
            gid = f"{bucket}-{seq:06d}"
        out.append({
            "unified_id": gid,
            "status": "active",
            "layer": row["layer"],
            "modern_char": row["modern_char"],
            "unicode": row["unicode"],
            "file": row["file"],
            "source_id": row["source_id"],
            "identity_confidence": row["identity_confidence"],
            "modern_char_slot": row["modern_char_slot"],
        })
    for key, old in ledger.items():
        if key not in seen_keys:
            stats["retired"] += 1
            out.append({**old, "status": "retired"})
    out.sort(key=lambda r: r["unified_id"])
    return out


def assert_domains(rows: list[dict]) -> None:
    """根码域断言 + ID 唯一 + 语法。对 active 与 retired 都跑（退役件铸发时也必须合法）。"""
    seen: set[str] = set()
    for r in rows:
        gid = r["unified_id"]
        if gid in seen:
            raise SystemExit(f"unified_id 重复：{gid}")
        seen.add(gid)
        parts = gid.split("-")
        # 根码 6 位 hex + 书体码 2 位（数字开头，当前 0 段）+ 序号 6 位十进制。
        if (len(parts) != 3 or len(parts[0]) != 6 or len(parts[1]) != 2
                or len(parts[2]) != 6 or not parts[1][0].isdigit()):
            raise SystemExit(f"unified_id 语法错误：{gid}")
        cp = int(parts[0], 16)
        if r["unicode"]:
            if not _in_ranges(cp, CJK_RANGES):
                raise SystemExit(f"{gid}: 根码不在 CJK 统一表意区块（unicode={r['unicode']}）")
        else:
            if not _in_ranges(cp, PUA_RANGES):
                raise SystemExit(f"{gid}: 无 unicode 的行根码必须落私用区")
            if (r["identity_confidence"] or "") != "pua-slot":
                raise SystemExit(f"{gid}: 私用区根码行必须标 identity_confidence=pua-slot")


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def selftest() -> int:
    """账本冻结政策的机检：扩展场景逐个断言（合成数据，不碰真登记表）。

    1. 桶内插入 → 旧 ID 全部冻结、新件取 max+1（不重排）；
    2. 删行 → status=retired、ID 保留；
    3. 新件加入 → **不复用退役号**（取历史 max+1）；
    4. 同键回归 → 复活原 ID（引用不断链）。
    """
    def row(gid, key, f, u="004E00"):
        parts = gid.split("-")
        return {"unified_id": gid, "status": "active", "layer": "o",
                "modern_char": "一", "unicode": u, "file": f, "source_id": key,
                "identity_confidence": "", "modern_char_slot": "",
                "_key": ("o", u, key)}
    ledger = {
        ("o", "004E00", "s1"): row("004E00-0A-000001", "s1", "f1.svg"),
        ("o", "004E00", "s2"): row("004E00-0A-000002", "s2", "f2.svg"),
        ("o", "004E00", "s3"): row("004E00-0A-000003", "s3", "f3.svg"),
        ("o", "004E01", "s4"): row("004E01-0A-000001", "s4", "f4.svg", u="004E01"),
    }
    def make_cur(pairs):
        out = []
        for key, f in pairs:
            out.append({"bucket": "004E00-0A", "layer": "o", "modern_char": "一",
                        "unicode": "004E00", "file": f, "source_id": key,
                        "identity_confidence": "", "modern_char_slot": "",
                        "ledger_key": ("o", "004E00", key)})
        return out

    # 1. 桶内插入
    stats = {"kept": 0, "minted": 0, "retired": 0}
    cur = make_cur([("s1", "f1.svg"), ("s5", "f5.svg"), ("s2", "f2.svg"), ("s3", "f3.svg")])
    rows = merge_ledger(cur, ledger, stats)
    by = {r["source_id"]: r for r in rows if r["status"] == "active"}
    assert by["s1"]["unified_id"] == "004E00-0A-000001"
    assert by["s2"]["unified_id"] == "004E00-0A-000002"
    assert by["s3"]["unified_id"] == "004E00-0A-000003"
    assert by["s5"]["unified_id"] == "004E00-0A-000004", by["s5"]
    # 2+3. 删 s2（退役）→ 新件 s6 不复用 000002
    cur2 = make_cur([("s1", "f1.svg"), ("s3", "f3.svg"), ("s5", "f5.svg"), ("s6", "f6.svg")])
    rows2 = merge_ledger(cur2, ledger, stats)
    by2 = {r["source_id"]: r for r in rows2}
    assert by2["s2"]["status"] == "retired" and by2["s2"]["unified_id"] == "004E00-0A-000002"
    assert by2["s6"]["unified_id"] == "004E00-0A-000005", by2["s6"]
    assert by2["s5"]["unified_id"] == "004E00-0A-000004"
    # 4. 同键回归 → 复活原 ID
    rows3 = merge_ledger(make_cur([("s1", "f1.svg"), ("s2", "f2.svg"), ("s3", "f3.svg")]),
                         ledger, stats)
    by3 = {r["source_id"]: r for r in rows3 if r["status"] == "active"}
    assert by3["s2"]["unified_id"] == "004E00-0A-000002"
    print("selftest 通过：冻结 / 插入 max+1 / 退役保留 / 退役号不复用 / 同键复活")
    return 0


def _render(rows: list[dict]) -> str:
    """与 write_csv 完全一致的文本形态（供 --check 逐字节比对）。"""
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(FIELDS), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="跨层统一字形编号账本")
    ap.add_argument("--check", action="store_true",
                    help="CI：账本合并 + 对账 + 逐字节复算")
    ap.add_argument("--selftest", action="store_true",
                    help="冻结政策自检：插入 max+1 / 退役保留 / 退役号不复用 / 同键复活")
    ap.add_argument("--char", default=None,
                    help="查询一个字（现代汉字）在所有书体的字形（只列 active）")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    stats: dict = {"index_rows": 0, "current_rows": 0, "pua_root": 0,
                   "excluded_no_root": 0, "kept": 0, "minted": 0, "retired": 0}
    ledger = load_ledger(OUT_PATH)
    current = collect_current(stats)
    rows = merge_ledger(current, ledger, stats)
    assert_domains(rows)

    if args.char:
        ch = args.char.strip()
        want = f"{ord(ch):06X}" if len(ch) == 1 else norm6(ch)
        hits = [r for r in rows if r["unicode"] == want and r["status"] == "active"]
        print(f"{'unified_id':18} {'layer':10} {'file':16} source_id")
        for r in hits:
            print(f"{r['unified_id']:18} {r['layer']:10} {r['file']:16} {r['source_id']}")
        print(f"共 {len(hits)} 件")
        return 0

    if args.check:
        if not OUT_PATH.is_file():
            raise SystemExit(f"登记表不存在：{OUT_PATH}")
        same = OUT_PATH.read_bytes() == _render(rows).encode("utf-8")
        if not same:
            raise SystemExit("账本与重建结果不一致（index.csv 或账本被改动？重跑生成即可）")
        active = sum(1 for r in rows if r["status"] == "active")
        print(f"账本校验通过：{len(rows)} 行（active {active} / retired "
              f"{len(rows) - active}）；本轮 kept {stats['kept']} / minted "
              f"{stats['minted']} / retired {stats['retired']}；"
              f"index 行 {stats['index_rows']}（排除无根码 {stats['excluded_no_root']}）")
        return 0

    write_csv(rows, OUT_PATH)
    print(f"写出 {OUT_PATH}：{len(rows)} 行（active "
          f"{sum(1 for r in rows if r['status'] == 'active')} / retired "
          f"{stats['retired']}）；本轮 kept {stats['kept']} / minted {stats['minted']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
