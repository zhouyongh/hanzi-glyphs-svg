#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨层统一字形编号：生成 / 校验 / 查询（账本模式）。

用法::

    python src/build_glyph_ids.py                # 生成（账本合并：冻结已发布 ID）
    python src/build_glyph_ids.py --check        # CI：对账 + 逐字节复算
    python src/build_glyph_ids.py --char 一      # 查询一个字在所有书体的字形
    python src/build_glyph_ids.py --selftest     # 冻结政策自检（CI）
    python src/build_glyph_ids.py --redirects    # 身份迁移的 old→new 重定向表

**规则全文见 AGENTS.md「统一字形编号（unified_id）」**。要点：

- ID = `<根码>-<书体码>-<序号>`，如 `004E00-0E-000001` = 「一」的小篆第 1 件；
- 根码 = 现代字 Unicode 码位（6 位大写 hex）；书体码 = 2 位层键（0A..0M，冻结）；
  序号 =（根码, 书体）桶内 6 位十进制；
- **冻结政策（2026-11-05）**：ID 一经发布永不重排。账本键 = (层, 读法, source_id)，
  全仓实测 0 碰撞。现行行 status=active；消失行 status=retired（ID 保留、序号
  永不复用）；新增行取桶内最大已用号 + 1。初始分配才用逐层学术序
  （era_sequence.py：小篆=说文序、金文/隶书=时代序、楚=文献年代序、
  其余=条目号数值序），铸发之后不再重排；
- **release 列**与 status 正交：`draft` = 铸发未对外；`stable` = 已随某次发布
  对外（由发布流程批量翻转）。账本管生命周期，发布态单列——「号已铸、
  尚未对外」由此表达；
- 产物族（全部确定性生成，`--check` 逐字节复算）：
  `glyph-ids.csv`（账本）+ `glyph-ids-excluded.csv`（无根码排除清单）
  + `glyph-ids.meta.json`（schema_version 与计数）+ `export/<层>.csv`
  （宽表导出：账本 ⋈ index ⋈ provenance，下游免拼表）+ `export/FIELDS.md`
  （英文字段词典，手维护）；
- 身份迁移（临时身份补回正式 CJK）= 旧行退役 + 新根码铸发，`--redirects`
  按 (层, source_id) 血缘导出 old→new 重定向表，引用链不断。
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from era_sequence import (BRONZE_ERA_RANK, CHU_CORPUS_YEAR,  # noqa: E402
                          CLERICAL_ERA_RANK, era_rank, sort_key_with_year)

OUT_PATH = ROOT / "glyphs" / "glyph-ids.csv"
EXCLUDED_PATH = ROOT / "glyphs" / "glyph-ids-excluded.csv"
META_PATH = ROOT / "glyphs" / "glyph-ids.meta.json"
EXPORT_DIR = ROOT / "glyphs" / "export"

SCHEMA_VERSION = 1

# 书体字母表（**按序冻结，只增不改**）——全文见 AGENTS.md「统一字形编号」。
# (书体码尾字, 层中文名, 目录, 键形态)；书体码 = "0" + 尾字。
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

LAYER_ZH = {dirname: zh for _t, zh, dirname, _k in SCRIPT_TABLE}
SCRIPT_CODE = {dirname: f"0{tail}" for tail, _z, dirname, _k in SCRIPT_TABLE}

FIELDS = ("unified_id", "status", "release", "layer", "modern_char", "unicode",
          "file", "source_id", "identity_confidence", "modern_char_slot")

EXCLUDED_FIELDS = ("layer", "file", "source_id", "modern_char_slot", "reason")

# 宽表导出列（**稳定 schema，schema_version 钉住**；字段词典 export/FIELDS.md）。
# 列取各层 index 的并集口径：古层有 period/source_book，字体层这两列为空——
# 宽表统一带上，下游不用再关心层的差异。
EXPORT_FIELDS = ("unified_id", "status", "release", "layer", "layer_zh", "script_code",
                 "modern_char", "unicode", "file", "sha256", "source_id",
                 "identity_confidence", "modern_char_slot", "license",
                 "source_dataset", "source_url", "period", "source_book")

# 根码域断言：真汉字根码必须落 CJK 统一表意区块；临时身份根码必须落私用区。
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
        for rec in recs:
            u = norm6(rec.get("unicode") or "")
            if u:
                root = u
            else:
                # 临时身份：根码取槽位私用区码位（身份未定由 identity_confidence 列明示）。
                root = slot_codepoint(rec.get("modern_char_slot") or "")
                if not root:
                    stats.setdefault("excluded_rows", []).append({
                        "layer": dirname,
                        "file": (rec.get("file") or "").strip(),
                        "source_id": (rec.get("source_id") or "").strip(),
                        "modern_char_slot": (rec.get("modern_char_slot") or "").strip(),
                        "reason": "no-root（unicode 与槽位码位皆缺，见 AGENTS.md 扩展矩阵）",
                    })
                    stats["excluded_no_root"] += 1
                    print(f"  ⚠️ {layer}: 无根码可写（unicode 与槽位码位皆缺），不入账本："
                          f"file={rec.get('file', '')} slot={rec.get('modern_char_slot', '')}")
                    continue
                stats["pua_root"] += 1
            buckets.setdefault(root, []).append(rec)

        def sort_key(rec: dict):
            """桶内初始排序——**逐层取最硬的学术序**（原则见 AGENTS.md）。"""
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
            release = old.get("release") or "draft"
        else:
            bucket = row["bucket"]
            seq = used.get(bucket, 0) + 1
            used[bucket] = seq
            stats["minted"] += 1
            gid = f"{bucket}-{seq:06d}"
            release = "draft"
        out.append({
            "unified_id": gid,
            "status": "active",
            "release": release,
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
            r = dict(old)
            r.setdefault("release", "draft")
            r["status"] = "retired"
            out.append(r)
    out.sort(key=lambda r: r["unified_id"])
    return out


def assert_domains(rows: list[dict]) -> None:
    """根码域断言 + ID 唯一 + 语法（对 active 与 retired 都跑）。"""
    seen: set[str] = set()
    for r in rows:
        gid = r["unified_id"]
        if gid in seen:
            raise SystemExit(f"unified_id 重复：{gid}")
        seen.add(gid)
        parts = gid.split("-")
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


def redirects(rows: list[dict]) -> list[tuple[str, str]]:
    """身份迁移重定向：按 (层, source_id) 血缘配对 retired→active。

    临时身份补回正式 CJK 时，账本键里的读法变了（PUA 根 → CJK 根）、source_id
    不变——所以 (层, source_id) 相同而 ID 不同的 retired/active 对就是迁移链。
    """
    active_by_ls: dict[tuple, str] = {}
    for r in rows:
        if r["status"] == "active":
            active_by_ls[(r["layer"], (r["source_id"] or "").strip())] = r["unified_id"]
    out: list[tuple[str, str]] = []
    for r in rows:
        if r["status"] != "retired":
            continue
        succ = active_by_ls.get((r["layer"], (r["source_id"] or "").strip()))
        if succ and succ != r["unified_id"]:
            out.append((r["unified_id"], succ))
    return sorted(out)


def _csv_text(fields, rows) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(fields), lineterminator="\n",
                       extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def _load_prov(path: Path) -> dict[str, dict]:
    prov: dict[str, dict] = {}
    if not path.is_file():
        return prov
    for line in path.open("r", encoding="utf-8"):
        if line.strip():
            rec = json.loads(line)
            prov.setdefault(rec.get("path", ""), rec)
    return prov


def build_export_texts(ledger_rows: list[dict]) -> dict[Path, str]:
    """宽表导出：账本 ⋈ index ⋈ provenance → export/<层>.csv。

    稳定 schema（EXPORT_FIELDS，schema_version 钉住）：列取各层并集口径，
    字体层没有的 period/source_book 留空——下游不用关心层间差异。
    """
    by_pair = {(r["layer"], r["file"]): r for r in ledger_rows
               if r["status"] == "active"}
    texts: dict[Path, str] = {}
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    for _tail, layer, dirname, _km in SCRIPT_TABLE:
        with (ROOT / "glyphs" / dirname / "index.csv").open(
                "r", encoding="utf-8-sig", newline="") as fh:
            index_rows = list(csv.DictReader(fh))
        prov = _load_prov(ROOT / "glyphs" / "provenance" / f"{dirname}.jsonl")
        out_rows: list[dict] = []
        for rec in index_rows:
            f = (rec.get("file") or "").strip()
            lid = by_pair.get((dirname, f))
            if lid is None:
                continue  # 无根码排除件（在 glyph-ids-excluded.csv 里）
            p = prov.get(f"glyphs/{dirname}/{f}", {})
            out_rows.append({
                "unified_id": lid["unified_id"],
                "status": lid["status"],
                "release": lid.get("release") or "draft",
                "layer": dirname,
                "layer_zh": LAYER_ZH[dirname],
                "script_code": SCRIPT_CODE[dirname],
                "modern_char": (rec.get("modern_char") or "").strip(),
                "unicode": norm6(rec.get("unicode") or ""),
                "file": f,
                "sha256": (rec.get("sha256") or "").strip(),
                "source_id": (rec.get("source_id") or "").strip(),
                "identity_confidence": (rec.get("identity_confidence") or "").strip(),
                "modern_char_slot": (rec.get("modern_char_slot") or "").strip(),
                "license": (p.get("license") or "").strip(),
                "source_dataset": (p.get("source_dataset") or "").strip(),
                "source_url": (p.get("source_url") or "").strip(),
                "period": (rec.get("period") or "").strip(),
                "source_book": (rec.get("source_book") or "").strip(),
            })
        out_rows.sort(key=lambda r: r["unified_id"])
        texts[EXPORT_DIR / f"{dirname}.csv"] = _csv_text(EXPORT_FIELDS, out_rows)
    return texts


def build_artifacts() -> tuple[dict[Path, str], dict]:
    """一次确定性构建全部产物：账本 + 排除清单 + 元数据 + 宽表导出。"""
    stats: dict = {"index_rows": 0, "current_rows": 0, "pua_root": 0,
                   "excluded_no_root": 0, "kept": 0, "minted": 0, "retired": 0}
    ledger = load_ledger(OUT_PATH)
    current = collect_current(stats)
    rows = merge_ledger(current, ledger, stats)
    assert_domains(rows)
    texts: dict[Path, str] = {OUT_PATH: _csv_text(FIELDS, rows)}
    texts[EXCLUDED_PATH] = _csv_text(EXCLUDED_FIELDS, stats.get("excluded_rows", []))
    export_texts = build_export_texts(rows)
    texts.update(export_texts)
    n_active = sum(1 for r in rows if r["status"] == "active")
    meta = {
        "schema_version": SCHEMA_VERSION,
        "counts": {"active": n_active, "retired": stats["retired"],
                   "excluded_no_root": stats["excluded_no_root"]},
        "artifacts": sorted(str(p.relative_to(ROOT / "glyphs")).replace("\\", "/")
                            for p in texts if p != META_PATH),
    }
    texts[META_PATH] = json.dumps(meta, ensure_ascii=False, indent=1,
                                  sort_keys=True) + "\n"
    for p in texts:
        p.parent.mkdir(parents=True, exist_ok=True)
    return texts, stats


def write_all(texts: dict[Path, str]) -> None:
    for p, text in texts.items():
        p.write_text(text, encoding="utf-8", newline="")


def selftest() -> int:
    """账本冻结政策的机检：扩展场景逐个断言（合成数据，不碰真登记表）。

    1. 桶内插入 → 旧 ID 全部冻结、新件取 max+1（不重排）；
    2. 删行 → status=retired、ID 保留；
    3. 新件加入 → **不复用退役号**（取历史 max+1）；
    4. 同键回归 → 复活原 ID（引用不断链）；
    5. 身份迁移 → redirects() 导出 old→new 重定向。
    """
    def row(gid, key, f, u="004E00"):
        return {"unified_id": gid, "status": "active", "release": "draft",
                "layer": "o", "modern_char": "一", "unicode": u, "file": f,
                "source_id": key, "identity_confidence": "", "modern_char_slot": ""}
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
    # 5. 身份迁移重定向：s3 的读法变了（004E00 → 004E02），source_id 不变
    led4 = {
        ("o", "004E00", "s3"): row("004E00-0A-000003", "s3", "f3.svg"),
        ("o", "004E02", "s3"): row("004E02-0A-000001", "s3", "f3.svg", u="004E02"),
    }
    cur4 = [{"bucket": "004E02-0A", "layer": "o", "modern_char": "一", "unicode": "004E02",
             "file": "f3.svg", "source_id": "s3", "identity_confidence": "",
             "modern_char_slot": "", "ledger_key": ("o", "004E02", "s3")}]
    stats4 = {"kept": 0, "minted": 0, "retired": 0}
    rows4 = merge_ledger(cur4, led4, stats4)
    red = redirects(rows4)
    assert red == [("004E00-0A-000003", "004E02-0A-000001")], red
    print("selftest 通过：冻结 / 插入 max+1 / 退役保留 / 退役号不复用 / 同键复活 / 迁移重定向")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Windows 默认 gbk 控制台打不出 ⚠️ 等符号会 UnicodeEncodeError——
    # 贡献者会误判为账本坏了。工具自己把 stdout 钉成 UTF-8。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="跨层统一字形编号账本")
    ap.add_argument("--check", action="store_true",
                    help="CI：全部产物（账本/排除清单/元数据/宽表导出）逐字节复算")
    ap.add_argument("--selftest", action="store_true",
                    help="冻结政策自检：插入 max+1 / 退役保留 / 退役号不复用 / 同键复活 / 迁移重定向")
    ap.add_argument("--redirects", action="store_true",
                    help="打印身份迁移重定向表（retired→active，CSV）")
    ap.add_argument("--char", default=None,
                    help="查询一个字（现代汉字）在所有书体的字形（只列 active）")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    texts, stats = build_artifacts()
    rows = list(csv.DictReader(io.StringIO(texts[OUT_PATH])))

    if args.char:
        ch = args.char.strip()
        want = f"{ord(ch):06X}" if len(ch) == 1 else norm6(ch)
        hits = [r for r in rows if r["unicode"] == want and r["status"] == "active"]
        print(f"{'unified_id':18} {'layer':10} {'file':16} source_id")
        for r in hits:
            print(f"{r['unified_id']:18} {r['layer']:10} {r['file']:16} {r['source_id']}")
        print(f"共 {len(hits)} 件")
        return 0

    if args.redirects:
        red = redirects(rows)
        print("old_unified_id,new_unified_id")
        for old, new in red:
            print(f"{old},{new}")
        print(f"共 {len(red)} 条（0 条 = 尚无身份迁移）")
        return 0

    if args.check:
        problems: list[str] = []
        for p, text in texts.items():
            if not p.is_file():
                problems.append(f"产物缺失：{p}")
            elif p.read_bytes() != text.encode("utf-8"):
                problems.append(f"产物与重建结果不一致：{p}")
        if problems:
            raise SystemExit("账本产物校验失败：\n  " + "\n  ".join(problems[:10]))
        n_active = sum(1 for r in rows if r["status"] == "active")
        print(f"账本校验通过（schema_version={SCHEMA_VERSION}）：{len(rows)} 行"
              f"（active {n_active} / retired {len(rows) - n_active}）；"
              f"产物 {len(texts)} 个全部逐字节一致")
        return 0

    write_all(texts)
    n_active = sum(1 for r in rows if r["status"] == "active")
    print(f"写出 {len(texts)} 个产物：账本 {len(rows)} 行（active {n_active} / "
          f"retired {len(rows) - n_active}）；宽表导出 glyphs/export/<层>.csv；"
          f"排除清单与元数据随附。本轮 kept {stats['kept']} / minted {stats['minted']}。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
