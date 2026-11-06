#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨层统一字形编号：生成 / 校验 / 查询（账本模式）。

用法::

    python src/build_glyph_ids.py                # 生成（账本合并：冻结已发布 ID）
    python src/build_glyph_ids.py --check        # CI：对账 + 逐字节复算 + 发布锚点体检
    python src/build_glyph_ids.py --char 一      # 查询一个字在所有书体的字形
    python src/build_glyph_ids.py --selftest     # 冻结政策自检（CI）
    python src/build_glyph_ids.py --redirects    # 身份迁移的 old→new 重定向表
    python src/build_glyph_ids.py --release stable --dry-run   # 发布预览（只算不写）

**规则全文见 AGENTS.md「统一字形编号（unified_id）」**。要点：

- ID = `<根码>-<书体码>-<序号>`，如 `004E00-0E00-000001` = 「一」的小篆第 1 件；
- 根码 = 现代字 Unicode 码位（6 位大写 hex）；
  书体码 = **4 位 base36**（`0` + 层键 A..M + **扩展位 2 位**，存量一律 `00`）；
  序号 =（根码, 层键）桶内 6 位十进制；
- **书体码 = 进制位(1) + 层键(1) + 扩展位(2)**：层键按序冻结、只增不改；
  扩展位是**层内不透明的分区句柄**，`00` = 默认分区，语义由
  `glyphs/glyph-ids-subcodes.csv`（**人工维护**）定义，只增不改、永不重定义。
  扩展位**不进桶**——桶仍是（根码, 层键），所以层内的学术序不被切开；
- **字母表 base36 `0-9A-Z`，不做 `I/L/O/U` 归一化**（存量层键含 `0I`/`0L`；
  归一化是 GID 的规则，套到可读编号上会让两个层撞成同一个串）；
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
  + `glyph-ids.meta.json`（schema_version、id_format 与计数）+ `export/<层>.csv`
  （宽表导出：账本 ⋈ index ⋈ provenance，下游免拼表）+ `export/FIELDS.md`
  （英文字段词典，手维护）；
- `glyph-ids-subcodes.csv` 是**人工维护**的扩展位登记表（**不属于**确定性产物族）：
  代码只**校验**它，绝不生成或覆盖；
- `glyph-ids-release.csv` 是**人工维护**的发布锚点（**不属于**确定性产物族）：
  记「哪一版已对外 + 那一版的已发布号集合指纹」。`--check` 拿它对账——
  改了任何一个已发布的号就红；新增字形（`release=draft`）不进指纹，
  等下一次发布再登记一行。这样「ID 铸发后冻结」是**机检**，不只是承诺；
- 身份迁移（临时身份补回正式 CJK）= 旧行退役 + 新根码铸发，`--redirects`
  按 (层, source_id) 血缘导出 old→new 重定向表，引用链不断。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
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
# 扩展位（分区码）登记表——**人工维护**，代码只校验、绝不生成或覆盖。
SUBCODES_PATH = ROOT / "glyphs" / "glyph-ids-subcodes.csv"
# 发布锚点——**人工维护**，代码只校验、绝不生成或覆盖。
# 记「哪一版已对外 + 那一版的已发布号集合指纹」，把「ID 铸发后冻结」从承诺变成机检。
RELEASES_PATH = ROOT / "glyphs" / "glyph-ids-release.csv"

SCHEMA_VERSION = 2
ID_FORMAT = "6-4-6"
SCRIPT_RESERVED = "00"          # 默认分区：每层第一批、也是绝大多数件的归属
SUBCODE_FIELDS = ("layer", "subcode", "meaning", "owner", "date")
RELEASE_FIELDS = ("release", "released_at", "stable_sha256", "ledger_sha256",
                  "id_format", "note")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 书体字母表（**按序冻结，只增不改**）——全文见 AGENTS.md「统一字形编号」。
# (书体码尾字, 层中文名, 目录, 键形态)；书体码 = "0" + 尾字 + 扩展位("00")。
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
# 4 位书体码 = 进制位(1) + 层键(1) + 扩展位(2)
SCRIPT_CODE = {dirname: f"0{tail}{SCRIPT_RESERVED}" for tail, _z, dirname, _k in SCRIPT_TABLE}
LAYER_KEYS = {dirname: tail for tail, _z, dirname, _k in SCRIPT_TABLE}

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


def to_v4(unified_id: str) -> str:
    """6-2-6 → 6-4-6：**在书体码后插入**扩展位（`00`）。已是 4 位则原样返回。

    幂等：已重铸过的号再过一次不变（`--check` 的逐字节复算靠这条）。
    """
    parts = (unified_id or "").split("-")
    if len(parts) != 3:
        return unified_id
    root, script, seq = parts
    if len(script) == 4:
        return unified_id
    if len(script) != 2:
        return unified_id
    return f"{root}-{script}{SCRIPT_RESERVED}-{seq}"


def load_subcode_registry() -> dict[tuple[str, str], dict]:
    """读扩展位登记表（**人工维护**）：(层, 分区码) → 行。

    文件不存在 = 还没有任何非默认分区（账本里只允许出现 `00`）。
    """
    reg: dict[tuple[str, str], dict] = {}
    if not SUBCODES_PATH.is_file():
        return reg
    with SUBCODES_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            layer = (row.get("layer") or "").strip()
            sub = (row.get("subcode") or "").strip()
            if layer and sub:
                reg[(layer, sub)] = row
    return reg


def check_subcode_registry() -> list[str]:
    """扩展位登记表体检：不得重复、meaning 不得为空、`00` 不得被改成别的含义。"""
    problems: list[str] = []
    if not SUBCODES_PATH.is_file():
        return problems
    seen: set[tuple[str, str]] = set()
    with SUBCODES_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh), start=2):
            layer = (row.get("layer") or "").strip()
            sub = (row.get("subcode") or "").strip()
            meaning = (row.get("meaning") or "").strip()
            if not layer or not sub:
                problems.append(f"{SUBCODES_PATH.name}:{i} 缺 layer 或 subcode")
                continue
            if len(sub) != 2 or not all(c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in sub):
                problems.append(f"{SUBCODES_PATH.name}:{i} 分区码必须 2 位 base36：{sub!r}")
            if (layer, sub) in seen:
                problems.append(f"{SUBCODES_PATH.name}:{i} 分区码重复：({layer}, {sub})")
            seen.add((layer, sub))
            if not meaning:
                problems.append(f"{SUBCODES_PATH.name}:{i} meaning 不得为空：({layer}, {sub})")
    return problems


def _git_blob_bytes(rev_path: str) -> bytes | None:
    """`git cat-file blob <rev>:<path>` 的原始字节。

    拿不到（git 不可用 / 对象不存在，如本地还没有那个 tag）返回 None——
    调用方据此**跳过**该项校验，而不是把「没 tag」当成「对不上」。
    """
    try:
        r = subprocess.run(["git", "cat-file", "blob", rev_path],
                           cwd=ROOT, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return r.stdout


def stable_fingerprint(rows: list[dict]) -> str:
    """**已发布**那部分号的集合指纹（sha256）。

    只吃 `unified_id`：**已发布的号永不改指**是本仓库的核心契约，而
    `file` / `status` / `source_id` 都允许随层现状变（合并重排只更新 file 列、
    退役保留 ID 与序号）。指纹若掺进这些字段，正常演进会被误判成破约。
    """
    ids = sorted(r["unified_id"] for r in rows if (r.get("release") or "") == "stable")
    h = hashlib.sha256()
    for i in ids:
        h.update(i.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def check_snapshot(anchor_name: str, line_no: int, rel: str,
                   snapshot: bytes, sha: str, lsha: str) -> list[str]:
    """拿**发布那一次的账本快照**体检一行锚点。

    快照 = 该 release 的 git tag 下那份 `glyphs/glyph-ids.csv` 的字节。两条对账：

    - 快照整份账本的 sha256 == 该行 `ledger_sha256`（发布那一刻的账本原样未动）；
    - 快照里 `release=stable` 那部分号的**集合指纹** == 该行 `stable_sha256`
      （这批号在发布那一刻就已定，且至今未改指）。

    **为什么必须是快照而不是当前账本**：当前账本含**后续**发布新增的号，拿它复算
    历史锚点的 stable_sha256 必然不符。快照是那一次的账本、它的 `release` 列就是
    当时的发布态，所以这个复算是**精确**的，不是近似。

    纯函数：不吃 git、不碰磁盘——selftest 直接拿合成快照就能验它。
    """
    problems: list[str] = []
    blob_sha = hashlib.sha256(snapshot).hexdigest()
    if blob_sha != lsha:
        problems.append(
            f"{anchor_name}:{line_no} ledger_sha256 {lsha[:12]}… 与 tag {rel!r} "
            f"下的账本 {blob_sha[:12]}… 不符")
    try:
        snap_rows = list(csv.DictReader(io.StringIO(snapshot.decode("utf-8"))))
    except UnicodeDecodeError:
        problems.append(f"{anchor_name}:{line_no} tag {rel!r} 下的账本不是 UTF-8")
        return problems
    if snap_rows and "unified_id" not in snap_rows[0]:
        problems.append(
            f"{anchor_name}:{line_no} tag {rel!r} 下的账本没有 unified_id 列")
        return problems
    if snap_rows:
        snap_fp = stable_fingerprint(snap_rows)
        if snap_fp != sha:
            problems.append(
                f"{anchor_name}:{line_no} stable_sha256 {sha[:12]}… 与 tag {rel!r} "
                f"下账本的已发布号集合 {snap_fp[:12]}… 不符")
    return problems


def check_release_record(rows: list[dict], path=None) -> list[str]:
    """发布锚点体检：最新一行的指纹必须等于当前账本的已发布号集合指纹。

    这一条把「ID 铸发后冻结」从**承诺**变成**机检**：改了任何一个已发布的号，
    指纹就变，CI 红。新增字形不受影响——新号是 `release=draft`，不进指纹；
    等下一次发布再登记一行锚点。

    **两条规则，堵住绕过的路**：
    - 锚点文件在 → **一律**要跟账本对账（哪怕账本里一个 stable 行都没有：
      那说明有人把已发布的号翻回了 draft，是对冻结的破坏，不是「还没发布」）；
    - 锚点文件不在 → 账本必须**一个 stable 行都没有**（= 还没发布过，
      铸发态不需要锚点）。

    **逐行体检**（每一行都查，不只最新一行）：
    - `release` 必填、**不重复**（它同时是 git tag 名）；
    - `released_at` 必须是 `YYYY-MM-DD`，且**不倒序**（后面的行不得早于前面的）；
    - `stable_sha256` / `ledger_sha256` 必须是 64 位十六进制，且**不得为空**；
    - `id_format` 不得与现行格式不符；
    - `ledger_sha256` 与 **git tag 下那份账本**逐字节对账——本地没有该 tag 时
      **跳过**（发布流程是「先提交、后打 tag」，CI 上 tag 可能还没推），不判失败。
    """
    problems: list[str] = []
    anchor = Path(path) if path is not None else RELEASES_PATH
    real = path is None          # 只有真锚点才打提示（selftest 用临时文件）
    n_stable = sum(1 for r in rows if (r.get("release") or "") == "stable")
    if not anchor.is_file():
        if n_stable:
            problems.append(f"{anchor.name}: 缺失（账本已有 {n_stable} 个已发布号，"
                            "发布锚点必须入库）")
        return problems
    with anchor.open("r", encoding="utf-8-sig", newline="") as fh:
        recs = list(csv.DictReader(fh))
    if not recs:
        problems.append(f"{anchor.name}: 空（至少要有一次发布的锚点行）")
        return problems
    seen_rel: dict[str, int] = {}
    prev_date = ""
    n_tag_checked = 0
    n_tag_skipped = 0
    for i, row in enumerate(recs, start=2):
        rel = (row.get("release") or "").strip()
        when = (row.get("released_at") or "").strip()
        sha = (row.get("stable_sha256") or "").strip().lower()
        lsha = (row.get("ledger_sha256") or "").strip().lower()
        fmt = (row.get("id_format") or "").strip()
        if not rel:
            problems.append(f"{anchor.name}:{i} 缺 release")
        elif rel in seen_rel:
            problems.append(f"{anchor.name}:{i} release {rel!r} 与第 {seen_rel[rel]} 行重复")
        else:
            seen_rel[rel] = i
        if not when:
            problems.append(f"{anchor.name}:{i} 缺 released_at")
        elif not DATE_RE.match(when):
            problems.append(f"{anchor.name}:{i} released_at 必须是 YYYY-MM-DD：{when!r}")
        elif prev_date and when < prev_date:
            problems.append(f"{anchor.name}:{i} released_at {when} 早于上一行 {prev_date}"
                            "（发布号不得倒序）")
        else:
            prev_date = when
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            problems.append(f"{anchor.name}:{i} stable_sha256 必须是 64 位十六进制")
        # ledger_sha256 = 发布那一刻整份账本的哈希（point-in-time 历史事实）。
        # 库往后会长，所以它**不**与工作区比对，而是与**该 release 的 git tag**
        # 下那份账本对账——本地没有那个 tag 时跳过（tag 可能还没推）。
        if not lsha:
            problems.append(f"{anchor.name}:{i} ledger_sha256 不得为空")
        elif len(lsha) != 64 or any(c not in "0123456789abcdef" for c in lsha):
            problems.append(f"{anchor.name}:{i} ledger_sha256 必须是 64 位十六进制")
        elif rel:
            blob = _git_blob_bytes(f"{rel}:glyphs/glyph-ids.csv")
            if blob is None:
                n_tag_skipped += 1
                if real:
                    print(f"  ⚠ {anchor.name}:{i} 本地没有 tag {rel!r}，**跳过**该行的 tag 对账"
                          "（发布流程是「先提交、后打 tag」；tag 推上去后才会真的对账）")
            else:
                n_tag_checked += 1
                problems.extend(
                    check_snapshot(anchor.name, i, rel, blob, sha, lsha))
        if fmt and fmt != ID_FORMAT:
            problems.append(f"{anchor.name}:{i} id_format {fmt!r} 与现行 {ID_FORMAT} 不符")
    last = recs[-1]
    want = stable_fingerprint(rows)
    got = (last.get("stable_sha256") or "").strip().lower()
    if got != want:
        problems.append(
            f"{anchor.name}: 最新发布 {last.get('release')!r} 的已发布号指纹 "
            f"{got[:12]}… 与当前账本 {want[:12]}… 不符——已发布的号不得改指；"
            "新增字形请留 release=draft，等下一次发布再登记锚点")
    if real:
        # 把 tag 对账的实际覆盖打进日志：CI 里要能一眼看出「核过了」还是
        # 「因为本地没有 tag 而跳过」——后者等于这条闸门没生效。
        print(f"  ✔ 发布锚点 tag 对账：{n_tag_checked} 行已核"
              + (f"，{n_tag_skipped} 行因本地缺 tag 跳过（该闸门未生效）"
                 if n_tag_skipped else "，无跳过"))
    return problems


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
                    # **桶 =（根码, 层键）**——扩展位不进桶，所以层内的学术序不被切开
                    "bucket": f"{root}-0{tail}",
                    # **号前缀 =（根码, 4 位书体码）**——扩展位在号里
                    "gid_prefix": f"{root}-0{tail}{SCRIPT_RESERVED}",
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
                 stats: dict, release_override: str = "") -> list[dict]:
    """账本合并：已发布的 ID 原样保留；新增取桶内最大已用号 + 1；消失行退役。

    `release_override` 非空 = 批量翻转发布态（发布流程用）；空 = 沿用账本里
    已有的发布态，不动。
    """
    used: dict[str, int] = {}   # 桶（root + 层键）→ 最大已用序号（含退役）
    for old in ledger.values():
        parts = (old.get("unified_id") or "").split("-")
        if len(parts) == 3 and parts[2].isdigit():
            # 桶只用书体码的**前两位**（进制位 + 层键）：扩展位不进桶，
            # 否则同一层里的学术序会在各分区内从 1 重排，序被切开。
            bucket = parts[0] + "-" + parts[1][:2]
            used[bucket] = max(used.get(bucket, 0), int(parts[2]))

    out: list[dict] = []
    seen_keys: set[tuple] = set()
    for row in current:
        key = row["ledger_key"]
        old = ledger.get(key)
        if old is not None:
            seen_keys.add(key)
            stats["kept"] += 1
            # 形状重铸：6-2-6 → 6-4-6（**序号与根码逐字不变**，只是扩展位补 "00"）。
            # 账本尚未发布，这是一次性格式迁移；to_v4 幂等，重跑不再动。
            gid = to_v4(old["unified_id"])
            release = release_override or old.get("release") or "draft"
        else:
            bucket = row["bucket"]
            seq = used.get(bucket, 0) + 1
            used[bucket] = seq
            stats["minted"] += 1
            gid = f"{row['gid_prefix']}-{seq:06d}"
            release = release_override or "draft"
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
            r["release"] = release_override or r.get("release") or "draft"
            r["status"] = "retired"
            r["unified_id"] = to_v4(r["unified_id"])   # 形状重铸（与 active 同步）
            out.append(r)
    out.sort(key=lambda r: r["unified_id"])
    return out


def assert_domains(rows: list[dict]) -> None:
    """根码域断言 + ID 唯一 + 语法（对 active 与 retired 都跑）。"""
    seen: set[str] = set()
    registry = load_subcode_registry()
    for r in rows:
        gid = r["unified_id"]
        if gid in seen:
            raise SystemExit(f"unified_id 重复：{gid}")
        seen.add(gid)
        parts = gid.split("-")
        # 6-4-6：根码 6 hex + 书体码 4 base36 + 序号 6 十进制
        if (len(parts) != 3 or len(parts[0]) != 6 or len(parts[1]) != 4
                or len(parts[2]) != 6
                or not all(c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in parts[1])):
            raise SystemExit(f"unified_id 语法错误：{gid}")
        script = parts[1]
        layer = r.get("layer") or ""
        key = LAYER_KEYS.get(layer)
        if key is None:
            raise SystemExit(f"{gid}: 未知层 {layer!r}")
        if script[1] != key:
            raise SystemExit(f"{gid}: 层键与层不符（{layer} 应为 {key}，号里是 {script[1]}）")
        sub = script[2:]
        if sub != SCRIPT_RESERVED and (layer, sub) not in registry:
            raise SystemExit(
                f"{gid}: 分区码 {sub!r} 未登记（见 glyphs/glyph-ids-subcodes.csv）")
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


def build_artifacts(release_override: str = "") -> tuple[dict[Path, str], dict]:
    """一次确定性构建全部产物：账本 + 排除清单 + 元数据 + 宽表导出。

    `release_override` 非空时**批量翻转发布态**（发布流程用）：账本里每一行
    的 `release` 列都改成该值。默认空 = 沿用账本里已有的发布态（不动）。
    """
    stats: dict = {"index_rows": 0, "current_rows": 0, "pua_root": 0,
                   "excluded_no_root": 0, "kept": 0, "minted": 0, "retired": 0}
    ledger = load_ledger(OUT_PATH)
    current = collect_current(stats)
    rows = merge_ledger(current, ledger, stats, release_override=release_override)
    assert_domains(rows)
    texts: dict[Path, str] = {OUT_PATH: _csv_text(FIELDS, rows)}
    texts[EXCLUDED_PATH] = _csv_text(EXCLUDED_FIELDS, stats.get("excluded_rows", []))
    export_texts = build_export_texts(rows)
    texts.update(export_texts)
    n_active = sum(1 for r in rows if r["status"] == "active")
    meta = {
        "schema_version": SCHEMA_VERSION,
        "id_format": ID_FORMAT,
        "script_reserved": SCRIPT_RESERVED,
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
    5. 身份迁移 → redirects() 导出 old→new 重定向；
    6. 形状重铸 to_v4 幂等（6-2-6 → 6-4-6，序号与根码逐字不变）；
    7. **扩展位不进桶**：同（根码, 层键）下换了分区位，序号继续排、不从 1 重来。
    """
    def row(gid, key, f, u="004E00"):
        return {"unified_id": gid, "status": "active", "release": "draft",
                "layer": "o", "modern_char": "一", "unicode": u, "file": f,
                "source_id": key, "identity_confidence": "", "modern_char_slot": ""}
    ledger = {
        ("o", "004E00", "s1"): row("004E00-0A00-000001", "s1", "f1.svg"),
        ("o", "004E00", "s2"): row("004E00-0A00-000002", "s2", "f2.svg"),
        ("o", "004E00", "s3"): row("004E00-0A00-000003", "s3", "f3.svg"),
        ("o", "004E01", "s4"): row("004E01-0A00-000001", "s4", "f4.svg", u="004E01"),
    }
    def make_cur(pairs, prefix="004E00-0A00"):
        out = []
        for key, f in pairs:
            out.append({"bucket": "004E00-0A", "gid_prefix": prefix, "layer": "o",
                        "modern_char": "一",
                        "unicode": "004E00", "file": f, "source_id": key,
                        "identity_confidence": "", "modern_char_slot": "",
                        "ledger_key": ("o", "004E00", key)})
        return out

    # 1. 桶内插入
    stats = {"kept": 0, "minted": 0, "retired": 0}
    cur = make_cur([("s1", "f1.svg"), ("s5", "f5.svg"), ("s2", "f2.svg"), ("s3", "f3.svg")])
    rows = merge_ledger(cur, ledger, stats)
    by = {r["source_id"]: r for r in rows if r["status"] == "active"}
    assert by["s1"]["unified_id"] == "004E00-0A00-000001"
    assert by["s2"]["unified_id"] == "004E00-0A00-000002"
    assert by["s3"]["unified_id"] == "004E00-0A00-000003"
    assert by["s5"]["unified_id"] == "004E00-0A00-000004", by["s5"]
    # 2+3. 删 s2（退役）→ 新件 s6 不复用 000002
    cur2 = make_cur([("s1", "f1.svg"), ("s3", "f3.svg"), ("s5", "f5.svg"), ("s6", "f6.svg")])
    rows2 = merge_ledger(cur2, ledger, stats)
    by2 = {r["source_id"]: r for r in rows2}
    assert by2["s2"]["status"] == "retired" and by2["s2"]["unified_id"] == "004E00-0A00-000002"
    assert by2["s6"]["unified_id"] == "004E00-0A00-000005", by2["s6"]
    assert by2["s5"]["unified_id"] == "004E00-0A00-000004"
    # 4. 同键回归 → 复活原 ID
    rows3 = merge_ledger(make_cur([("s1", "f1.svg"), ("s2", "f2.svg"), ("s3", "f3.svg")]),
                         ledger, stats)
    by3 = {r["source_id"]: r for r in rows3 if r["status"] == "active"}
    assert by3["s2"]["unified_id"] == "004E00-0A00-000002"
    # 5. 身份迁移重定向：s3 的读法变了（004E00 → 004E02），source_id 不变
    led4 = {
        ("o", "004E00", "s3"): row("004E00-0A00-000003", "s3", "f3.svg"),
        ("o", "004E02", "s3"): row("004E02-0A00-000001", "s3", "f3.svg", u="004E02"),
    }
    cur4 = [{"bucket": "004E02-0A", "gid_prefix": "004E02-0A00", "layer": "o",
             "modern_char": "一", "unicode": "004E02",
             "file": "f3.svg", "source_id": "s3", "identity_confidence": "",
             "modern_char_slot": "", "ledger_key": ("o", "004E02", "s3")}]
    stats4 = {"kept": 0, "minted": 0, "retired": 0}
    rows4 = merge_ledger(cur4, led4, stats4)
    red = redirects(rows4)
    assert red == [("004E00-0A00-000003", "004E02-0A00-000001")], red
    # 6. 形状重铸：6-2-6 → 6-4-6，序号与根码逐字不变；再过一次不变（幂等）
    assert to_v4("004E00-0E-000001") == "004E00-0E00-000001"
    assert to_v4("004E00-0E00-000001") == "004E00-0E00-000001"
    assert to_v4("003401-0I-000001") == "003401-0I00-000001"   # I 原样保留（不归一化）
    assert to_v4("003401-0L-000001") == "003401-0L00-000001"
    # 7. 扩展位不进桶：分区位换成 01，序号继续排（不从 1 重来）
    cur7 = make_cur([("s5", "f5.svg")], prefix="004E00-0A01")
    rows7 = merge_ledger(cur7, ledger, stats)
    by7 = {r["source_id"]: r for r in rows7 if r["status"] == "active"}
    assert by7["s5"]["unified_id"] == "004E00-0A01-000004", by7["s5"]
    # 8. 发布锚点指纹：只认「已发布的号」。新增 draft、退役都不改指纹；
    #    改一个已发布的号（或少一个）指纹必变——这就是「冻结」的机检。
    f_rows = [{"unified_id": "004E00-0A00-000001", "release": "stable"},
              {"unified_id": "004E00-0A00-000002", "release": "stable"},
              {"unified_id": "004E00-0A00-000003", "release": "draft"}]
    fp = stable_fingerprint(f_rows)
    assert fp == stable_fingerprint(list(reversed(f_rows))), "指纹与行序无关"
    assert fp == stable_fingerprint(f_rows + [
        {"unified_id": "004E00-0A00-000004", "release": "draft"}]), "新增 draft 不进指纹"
    retired_rows = [dict(r) for r in f_rows]
    retired_rows[1]["status"] = "retired"
    assert fp == stable_fingerprint(retired_rows), "退役保留号，不改指纹"
    assert fp != stable_fingerprint([r for r in f_rows
                                      if r["unified_id"] != "004E00-0A00-000001"]), \
        "少一个已发布的号 → 指纹必变"
    tampered = [dict(r) for r in f_rows]
    tampered[0]["unified_id"] = "004E00-0A00-000009"
    assert fp != stable_fingerprint(tampered), "改已发布的号 → 指纹必变"
    # 9. 发布锚点体检的两条规则：锚点在 → 一律对账（翻回 draft 也算破坏冻结）；
    #    锚点不在 → 账本必须一个已发布号都没有（= 还没发布过）
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        zeros = "0" * 64
        # 用一个**不存在的 tag 名**：ledger_sha256 的 tag 对账在本地没 tag 时跳过，
        # 这样 selftest 不依赖仓库里恰好有哪个 tag。
        fake = "v0.0.0-selftest"
        head = "release,released_at,stable_sha256,ledger_sha256,id_format,note\n"

        def write_anchor(name, body):
            p = Path(td) / name
            p.write_text(head + body, encoding="utf-8")
            return p

        good_anchor = write_anchor("good.csv",
                                   f"{fake},2026-11-06,{fp},{zeros},6-4-6,test\n")
        assert check_release_record(f_rows, good_anchor) == [], \
            check_release_record(f_rows, good_anchor)
        bad_anchor = write_anchor("bad.csv",
                                  f"{fake},2026-11-06,{zeros},{zeros},6-4-6,test\n")
        assert check_release_record(f_rows, bad_anchor), "指纹不符必须报错"
        missing_anchor = Path(td) / "nope.csv"
        assert check_release_record(f_rows, missing_anchor), \
            "有已发布号却没锚点 → 必须报错"
        all_draft = [dict(r, release="draft") for r in f_rows]
        assert check_release_record(all_draft, missing_anchor) == [], \
            "一个已发布号都没有 → 铸发态不需要锚点"
        assert check_release_record(all_draft, good_anchor), \
            "把已发布的号翻回 draft 是破坏冻结 → 必须报错"
        # 10. 逐行体检：ledger_sha256 不得为空 / released_at 必须是 YYYY-MM-DD /
        #     release 不得重复 / 日期不得倒序
        empty_lsha = write_anchor("empty_lsha.csv",
                                  f"{fake},2026-11-06,{fp},,6-4-6,test\n")
        assert check_release_record(f_rows, empty_lsha), "ledger_sha256 不得为空"
        bad_date = write_anchor("bad_date.csv",
                                f"{fake},2026/11/06,{fp},{zeros},6-4-6,test\n")
        assert check_release_record(f_rows, bad_date), "released_at 格式错必须报错"
        dup = write_anchor("dup.csv",
                           f"{fake},2026-11-06,{fp},{zeros},6-4-6,t\n"
                           f"{fake},2026-11-07,{fp},{zeros},6-4-6,t\n")
        assert check_release_record(f_rows, dup), "release 重复必须报错"
        back = write_anchor("back.csv",
                            f"{fake},2026-11-07,{fp},{zeros},6-4-6,t\n"
                            f"{fake}-b,2026-01-01,{fp},{zeros},6-4-6,t\n")
        assert check_release_record(f_rows, back), "released_at 倒序必须报错"
    # 11. tag 基复算：拿**发布那一次的账本快照**逐条对账。这是对**历史锚点**
    #     的精确复核路径（当前账本含后续发布的号，不能用它复算），
    #     也是本仓发布闸门的关键一环——必须有自检兜住，不能只在 CI 里靠真 tag。
    snap = ("unified_id,status,release,layer,modern_char,unicode,file,source_id\n"
            "004E00-0A00-000001,active,stable,oracle,一,004E00,0001.svg,s1\n"
            "004E01-0A00-000001,active,stable,oracle,丁,4E01,0002.svg,s2\n"
            "004E02-0A00-000001,active,draft,oracle,丂,4E02,0003.svg,s3\n")
    snap_b = snap.encode("utf-8")
    snap_sha = hashlib.sha256(snap_b).hexdigest()
    snap_fp = stable_fingerprint(list(csv.DictReader(io.StringIO(snap))))
    # 对得上 → 零问题（draft 行不进指纹，与主路径同规则）
    assert check_snapshot("a.csv", 2, "v1.0.0", snap_b, snap_fp, snap_sha) == [], \
        check_snapshot("a.csv", 2, "v1.0.0", snap_b, snap_fp, snap_sha)
    # 整份账本哈希写错一个字符 → 报错
    p = check_snapshot("a.csv", 2, "v1.0.0", snap_b, snap_fp, "0" + snap_sha[1:])
    assert p and any("ledger_sha256" in x for x in p), p
    # 已发布号集合指纹写错 → 报错
    p = check_snapshot("a.csv", 2, "v1.0.0", snap_b, "0" + snap_fp[1:], snap_sha)
    assert p and any("stable_sha256" in x for x in p), p
    # 快照里某个已发布的号被改指 → 集合指纹变 → 锚点那条必报
    tampered = snap.replace("004E00-0A00-000001",
                             "004E00-0A00-000009").encode("utf-8")
    p = check_snapshot("a.csv", 2, "v1.0.0", tampered, snap_fp, snap_sha)
    assert p and any("stable_sha256" in x for x in p), p
    # 快照不是 UTF-8 → 报错而不是崩
    p = check_snapshot("a.csv", 2, "v1.0.0", b"\xff\xfe\x00", snap_fp, snap_sha)
    assert p and any("UTF-8" in x for x in p), p
    # 快照缺 unified_id 列 → 报错而不是崩
    p = check_snapshot("a.csv", 2, "v1.0.0", b"a,b\n1,2\n", snap_fp, snap_sha)
    assert p and any("unified_id" in x for x in p), p
    print("selftest 通过：冻结 / 插入 max+1 / 退役保留 / 退役号不复用 / 同键复活 / "
          "迁移重定向 / 形状重铸幂等 / 扩展位不进桶 / 发布锚点指纹 / tag 基复算")
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
    ap.add_argument("--write-exports", action="store_true",
                    help="只写宽表导出 glyphs/export/*.csv（构建产物，不入库；CI/Pages 用）")
    ap.add_argument("--selftest", action="store_true",
                    help="冻结政策自检：插入 max+1 / 退役保留 / 退役号不复用 / 同键复活 / 迁移重定向")
    ap.add_argument("--redirects", action="store_true",
                    help="打印身份迁移重定向表（retired→active，CSV）")
    ap.add_argument("--char", default=None,
                    help="查询一个字（现代汉字）在所有书体的字形（只列 active）")
    ap.add_argument("--release", choices=("draft", "stable"), default=None,
                    help="批量翻转发布态（发布流程用）：把账本每一行的 release 列"
                         "改成该值。默认不动，沿用账本里已有的发布态")
    ap.add_argument("--dry-run", action="store_true",
                    help="只算不写：打印将要发生什么（翻转多少行、新的发布锚点行），"
                         "不落盘")
    ap.add_argument("--force", action="store_true",
                    help="配合 --release draft：发布锚点已存在时仍强行把已发布的号"
                         "翻回 draft（危险：必须同步更新发布锚点，否则 --check 会红）")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    # **fail-closed**：发布锚点已存在 = 已经发布过一次。已发布的号是**单向**的，
    # 翻回 draft 会与锚点矛盾——发布工具不该有「一键撤销」这条路。
    if args.release == "draft" and RELEASES_PATH.is_file() and not args.force:
        raise SystemExit(
            f"拒绝执行：发布锚点 {RELEASES_PATH.name} 已存在（已发布过），"
            "把已发布的号翻回 draft 会与锚点矛盾。\n"
            "  发布是**单向**的：已发布的号永不翻回。\n"
            "  若确需撤销发布，请显式加 --force，并**同步更新** "
            f"{RELEASES_PATH.name}（否则 --check 会红）。")

    before = None
    if OUT_PATH.is_file():
        before = list(csv.DictReader(io.StringIO(OUT_PATH.read_text(encoding="utf-8"))))

    texts, stats = build_artifacts(release_override=args.release or "")
    rows = list(csv.DictReader(io.StringIO(texts[OUT_PATH])))

    if args.write_exports:
        exports = {p: t for p, t in texts.items() if p.parent == EXPORT_DIR}
        write_all(exports)
        print(f"写出 {len(exports)} 个宽表导出到 {EXPORT_DIR.relative_to(ROOT)}")
        return 0

    if args.release:
        n_before = sum(1 for r in before or [] if (r.get("release") or "") == args.release)
        n_after = sum(1 for r in rows if (r.get("release") or "") == args.release)
        print(f"发布态 → {args.release}：{n_after} 行"
              f"（原 {n_before} 行；本轮 kept {stats['kept']} / minted {stats['minted']}）")
        if args.release == "draft" and args.force:
            print("  ⚠️ --force：这是破坏冻结的操作。必须同步更新发布锚点，否则 --check 会红。")
        if args.release == "stable":
            print(f"  已发布号集合指纹 stable_sha256 = {stable_fingerprint(rows)}")
            print(f"  账本文件哈希     ledger_sha256 = "
                  f"{hashlib.sha256(texts[OUT_PATH].encode('utf-8')).hexdigest()}")
            print(f"  → 追加这一行到 {RELEASES_PATH.name}（人工维护，代码不代写）：")
            print(f"     {','.join(RELEASE_FIELDS)}")
            print(f"     <发布号>,<YYYY-MM-DD>,{stable_fingerprint(rows)},"
                  f"{hashlib.sha256(texts[OUT_PATH].encode('utf-8')).hexdigest()},"
                  f"{ID_FORMAT},<说明>")

    if args.dry_run:
        print(f"[dry-run] 未写盘。将会写 {len(texts)} 个产物，账本 {len(rows)} 行。")
        return 0

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
        problems.extend(check_subcode_registry())
        problems.extend(check_release_record(rows))
        if problems:
            raise SystemExit("账本产物校验失败：\n  " + "\n  ".join(problems[:10]))
        n_active = sum(1 for r in rows if r["status"] == "active")
        n_stable = sum(1 for r in rows if (r.get("release") or "") == "stable")
        print(f"账本校验通过（schema_version={SCHEMA_VERSION}，id_format={ID_FORMAT}）："
              f"{len(rows)} 行"
              f"（active {n_active} / retired {len(rows) - n_active}；"
              f"已发布 {n_stable}）；"
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
