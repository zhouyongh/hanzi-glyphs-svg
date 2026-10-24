#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按「清单」导入一个字形层：字形文件 + index.csv + provenance 记录。

用法::

    python src/import_glyph_layer.py --manifest <清单.json> [--dry-run]

清单（JSON）长这样::

    {
      "script": "bronze",
      "layer": "skeleton",
      "license": "CC0-1.0",
      "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
      "attribution": "…",
      "source_dataset": "…",
      "source_url": "https://…",
      "source_commit": "…",
      "glyphs": [
        {
          "glyph_id": 1,
          "file": "日-bronze.svg",          # 相对清单所在目录
          "modern_char": "日",
          "unicode": "0065E5",
          "period": "western-zhou",
          "variant": "",
          "source_file": "File:日-bronze.svg",
          "source_id": "b09941",
          "source_sha256": "…",
          "source_book": "金文編"
        }
      ]
    }

产出::

    glyphs/<script>/<glyph_id:04d>.svg   与来源逐字节一致的副本
    glyphs/<script>/index.csv            反查表
    glyphs/provenance/<书体>.jsonl      每个字形一条记录（合并写入，不覆盖其他书体）

**为什么要有这层通用导入。** 字形的来源各不相同（Zenodo 数据集、Commons 描摹件、
开元小篆的仓库……），但入库动作完全一样：抄一份、算 sha256、写一条出处记录、
生成反查表。来源相关的部分（怎么找、怎么下载、怎么画）留在各自的脚本里，
入库这件事在这里统一做，规则只有一份。

**许可闸门。** 每条字形的许可必须是 ``--allowed-licenses`` 里的一个（默认见
``DEFAULT_ALLOWED``）；不在名单里就跳过并计入「未入库」。这是 ``AGENTS.md``
「CC BY-ND / CC BY-NC / 无许可的来源不得入库」的机器实现——不靠记性。
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

# 允许入库的许可标识。改动前请先核实条款原文（AGENTS.md 第 3 条）。
# 不含 CC BY-SA：ShareAlike 会给下游附加「相同方式共享」的义务，与本仓库
# 统一的 CC BY 4.0 口径冲突；确有需要时应先改 AGENTS.md 的许可地图。
DEFAULT_ALLOWED = (
    "CC0-1.0",
    "PD",
    "PD-1.0",
    "PUBLIC-DOMAIN",
    "OFL-1.1",
    "CC-BY-4.0",
    "CC-BY-3.0",
)

# 本仓库承认的书体层名。层名会拼进落盘路径，不能是任意字符串。
SCRIPT_WHITELIST = ("oracle", "bronze", "clerical", "seal", "chu", "chuanchao")

# index.csv 的列。index.csv 的第一列永远是 glyph_id。
INDEX_EXTRA_COLUMNS = (
    "modern_char", "unicode", "period", "variant",
    "source_book", "source_number", "source_id",
    "source_path", "source_url", "file", "sha256",
)

# 只在**确实有值**时才加进表头的列。
# - 楚文字的题记带篇名（「郭.語」里的「語」），换全称时会丢掉这一层，
#   所以单独存一列 `book_part`。
# - 傳抄古文的题记带尾注，是该字形在来源书里标注的**引书名**（「汗3.34說」的「說」），
#   与 `source_book`（摹本底本 / 传抄本）是两个层级，所以另立 `source_cited_book`。
# 其余层没有这些维度，就不要多出一列空列。
OPTIONAL_INDEX_COLUMNS = ("book_part", "source_cited_book")

# 篆书层的键是 Unicode 篆书区块码位，不是本仓库的条目号。
# seal_candidates / seal_note 两列说明这个字还有哪些篆书码位（重文 / 异体）没填、
# 以及为什么——篆书区块里一个现代字常对应多个码位，下游要按码位取字形时需要知道。
SEAL_KEY_COLUMNS = (
    "codepoint", "modern_char", "unicode", "period", "variant",
    "source_book", "source_number", "source_id",
    "source_path", "source_url", "file", "sha256",
    "seal_candidates", "seal_note",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def owned_paths(path: Path, script: str, layer: str,
                scope: tuple[str, str] | None) -> set[str]:
    """列出 provenance 里属于本层（按 scope 限定）的记录的文件路径。

    用来在落盘前做孤儿体检：**这一层自己原来有哪些文件**，是有据可查的，
    不用靠「目录里多出来的就是孤儿」这种猜法。
    """
    out: set[str] = set()
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("script") != script:
            continue
        if record.get("layer", "skeleton") != layer:
            continue
        if scope is not None:
            field, value = scope
            if str(record.get(field) or "") != value:
                continue
        out.add(str(record.get("path") or ""))
    return out


def load_book_map(script: str) -> dict[str, str]:
    """读层目录下的「代码 → 全称」对照表（可选）。

    楚文字层的题记只给出出土文献的**代码**（「郭」「上」「新甲」「帛甲」…），
    这张表把它换成可查的文献全称，表在 ``glyphs/chu/books.csv``。
    **表里没有的代码就按原文留着**——编一个书名比留个代码更糟。
    """
    path = Path(__file__).resolve().parents[1] / "glyphs" / script / "books.csv"
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            code = (row.get("code") or "").strip()
            name = (row.get("corpus_full") or "").strip()
            if code and name:
                out[code] = name
    return out


def lookup_book(books: dict[str, str], source_book: str, book_code: str) -> str:
    """按「代码」在对照表里找文献全称。

    题记里的代码可能带**册号/篇名**后缀：「上(1).性」「郭.語」——
    对照表里的代码是「上(1)」「郭」。所以按由长到短的顺序试：
    整串 → 第一个「.」之前的部分 → 原始代码。
    """
    for candidate in (source_book, book_code):
        if not candidate:
            continue
        if candidate in books:
            return books[candidate]
        head = candidate.split(".")[0]
        if head in books:
            return books[head]
    return ""


def layer_key(record: dict) -> str:
    """记录所占的层键（统一成数字串）。

    篆书模式的层键是 Unicode 篆书区块码位，非篆书模式是条目号；
    两种模式在记录里都同时留着 ``codepoint`` 与 ``glyph_id``，
    统一取数字形式比较，跨模式撞键也认得出来。
    """
    codepoint = str(record.get("codepoint") or "").strip()
    if codepoint:
        try:
            return f"n:{int(codepoint, 16)}"
        except ValueError:
            return f"cp:{codepoint.upper()}"
    glyph_id = record.get("glyph_id")
    if glyph_id is None:
        return ""
    try:
        return f"n:{int(glyph_id)}"
    except (TypeError, ValueError):
        return f"id:{glyph_id}"


def other_scope_claims(prov_path: Path, script: str, layer: str,
                       scope: tuple[str, str] | None
                       ) -> tuple[dict[str, dict], dict[str, dict]]:
    """列出**别的来源批次**已经占用的文件路径与层键。

    同层多来源时（甲骨层 JGW 占 1..1203、汉典占 1204..），两个批次各占一段层键。
    这次导入如果跟别家撞了层键或路径，就会**静默覆盖**别家的字形文件：
    两次导入都报「完成」，但别家那条 provenance 的 sha256 变成了假话——
    那比报错严重得多，因为校验要到事后才发现。
    所以导入期就要拦。
    """
    paths: dict[str, dict] = {}
    keys: dict[str, dict] = {}
    if scope is None:
        # 不限定 scope = 本次导入独占整层，别家的记录本来就要被替换掉。
        return paths, keys
    field, value = scope
    if not prov_path.is_file():
        return paths, keys
    with prov_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("script") != script:
                continue
            if str(record.get("layer", "skeleton")) != layer:
                continue
            if str(record.get(field) or "") == value:
                continue                      # 自己这个批次
            paths[str(record.get("path") or "")] = record
            key = layer_key(record)
            if key:
                keys[key] = record
    return paths, keys


def merge_provenance(path: Path, script: str, layer: str,
                     new_records: list[dict],
                     scope: tuple[str, str] | None = None
                     ) -> tuple[int, int, set[str]]:
    """把新记录并进 provenance.jsonl，只替换本层（script + layer）的旧记录。

    ``scope`` 形如 ``("source_dataset", "汉典（zdic.net）甲骨文字形")``：
    只替换**同时**满足 script、layer 和这个字段值的旧记录。
    甲骨层有两个来源（JGW 的参数化矢量、汉典的拓片摹本），都用 script=oracle、
    layer=skeleton，靠这个字段区分批次——不然一个来源的导入会把另一个来源的
    出处记录整层抹掉。

    返回 (保留的旧记录数, 写入后的总记录数, 本次导入所拥有的旧记录路径)。
    """
    kept: list[dict] = []
    owned: set[str] = set()
    if path.exists():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno} 不是合法 JSON：{exc}") from exc
            same = (
                record.get("script") == script
                and record.get("layer", "skeleton") == layer
            )
            if same and scope is not None:
                field, value = scope
                same = str(record.get(field) or "") == value
            if same:
                owned.add(str(record.get("path") or ""))
            else:
                kept.append(record)

    merged = kept + new_records
    merged.sort(key=lambda r: (str(r.get("script", "")), str(r.get("path", ""))))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in merged:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return len(kept), len(merged), owned


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按清单导入一个字形层")
    parser.add_argument("--manifest", required=True, type=Path, help="清单 JSON")
    parser.add_argument("--layer", default=None,
                        help="目标书体层名（覆盖清单里的 script）。"
                             "仓库用 bronze/clerical/seal/oracle 这套目录名，"
                             "而来源可能叫 jinwen/lishu/xiaozhuan。")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="仓库根目录，默认取本脚本的上一级")
    parser.add_argument("--allowed-licenses", default=",".join(DEFAULT_ALLOWED),
                        help="允许入库的许可标识，逗号分隔")
    parser.add_argument("--dry-run", action="store_true", help="只检查，不写任何文件")
    parser.add_argument("--prune", action="store_true",
                        help="把目录里不在本次清单里的旧字形删掉。"
                             "默认是报错不删——留着就是「有文件、无出处记录」的孤儿。")
    parser.add_argument("--provenance-scope", default=None,
                        help="本次导入只拥有层内某个来源批次，格式「字段名=值」，"
                             "例如 source_dataset=汉典（zdic.net）甲骨文字形。"
                             "只替换该批次自己的旧出处记录与索引行，别的来源原样保留。"
                             "不给就是独占整层。")
    parser.add_argument("--key-mode", choices=("glyph_id", "seal_codepoint"),
                        default="glyph_id",
                        help="文件名用什么做键。glyph_id = 本仓库条目号（4 位十进制）；"
                             "seal_codepoint = Unicode 篆书区块码位（5 位大写十六进制，"
                             "取清单项的 codepoint 字段），篆书层用后者。")
    args = parser.parse_args(argv)

    scope: tuple[str, str] | None = None
    if args.provenance_scope:
        if "=" not in args.provenance_scope:
            raise SystemExit("--provenance-scope 的格式是「字段名=值」")
        field, value = args.provenance_scope.split("=", 1)
        field = field.strip()
        value = value.strip()
        if not field or not value:
            raise SystemExit("--provenance-scope 的格式是「字段名=值」，两边都不能空")
        scope = (field, value)

    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"找不到清单：{manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    script = str(args.layer or manifest.get("script") or "").strip()
    layer = str(manifest.get("layer") or "skeleton").strip()
    if not script:
        raise SystemExit("清单缺 script 字段，且没有给 --layer")
    if script not in SCRIPT_WHITELIST:
        raise SystemExit(
            f"未知的书体层名 {script!r}。本仓库承认的层名：{', '.join(SCRIPT_WHITELIST)}"
        )
    if layer != "skeleton":
        raise SystemExit(f"本脚本只导入骨架层，layer={layer!r} 请另找对应脚本")

    license_id = str(manifest.get("license") or "").strip()
    allowed = {x.strip() for x in args.allowed_licenses.split(",") if x.strip()}
    if not license_id:
        raise SystemExit("清单缺少 license 字段（无出处不入库）")
    if license_id not in allowed:
        raise SystemExit(
            f"清单的许可 {license_id!r} 不在允许名单内，未入库。\n"
            f"  允许的：{', '.join(sorted(allowed))}\n"
            "  若确认该许可允许改作与再分发，先核实条款原文，再显式加 --allowed-licenses。"
        )
    repo_root = args.repo_root.resolve()
    source_root = manifest_path.parent
    out_dir = repo_root / "glyphs" / script
    prov_path = repo_root / "glyphs" / "provenance" / f"{script}.jsonl"
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    glyphs = manifest.get("glyphs") or []
    records: list[dict] = []
    index_rows: list[dict] = []
    skipped: list[str] = []
    missing: list[str] = []
    seen_ids: set[int] = set()
    seen_names: set[str] = set()
    books = load_book_map(script)
    # provenance 里记的 layer 键（条目号 / 篆书码位）也必须唯一。
    # 清单里的 glyph_id 唯一不等于落盘后的键唯一：篆书模式下键是码位，
    # 两条清单条目可能指向同一个码位（文件名会撞，但撞的是同一个键）。
    seen_record_ids: set[int] = set()

    # **先全量校验，再统一落盘。** 之前是一个字形一个字形地拷，拷到一半发现
    # 清单里有坏路径就直接报错退出，于是目录里留下一堆「有文件、无出处记录」的
    # 孤儿字形——那正是硬规则 1「无出处，不入仓库」要防的事。
    plan: list[tuple[dict, Path, str, str, str, int]] = []

    for item in glyphs:
        glyph_id = int(item["glyph_id"])

        # 每条字形可以用自己的许可（清单级是默认值）；不在允许名单里的直接不入库。
        item_license = str(item.get("license") or license_id).strip()
        if item_license not in allowed:
            skipped.append(f"{glyph_id}: 许可 {item_license!r} 不在允许名单内")
            continue

        if glyph_id in seen_ids:
            raise SystemExit(f"清单里 glyph_id 重复：{glyph_id}")
        seen_ids.add(glyph_id)

        if args.key_mode == "seal_codepoint":
            codepoint = str(item.get("codepoint") or "").strip().upper()
            if not codepoint:
                raise SystemExit(f"glyph {glyph_id}: key-mode=seal_codepoint 需要 codepoint 字段")
            codepoint = codepoint[2:] if codepoint.startswith("U+") else codepoint
            # 篆书区块是 U+3D000–U+3FC3F，十六进制恰好 5 位（如 3D000）。
            if len(codepoint) != 5 or any(c not in "0123456789ABCDEF" for c in codepoint):
                raise SystemExit(f"glyph {glyph_id}: codepoint {codepoint!r} 不是 5 位十六进制")
            name = f"{codepoint}.svg"
            record_id = int(codepoint, 16)
        else:
            name = f"{glyph_id:04d}.svg"
            record_id = glyph_id
        if name in seen_names:
            raise SystemExit(f"清单里文件名重复：{name}")
        seen_names.add(name)
        if record_id in seen_record_ids:
            raise SystemExit(
                f"清单里层键重复：{record_id}（{name}）"
                + ("（篆书模式下层键是 Unicode 篆书区块码位）" if args.key_mode == "seal_codepoint" else "")
            )
        seen_record_ids.add(record_id)

        rel = str(item.get("file") or "").strip()
        src = (source_root / rel).resolve() if rel else None
        if src is None or not src.is_file():
            missing.append(f"{glyph_id}: {rel}")
            continue

        local_sha = sha256_file(src)
        # 清单可以给两种 sha256：local_sha256 是「清单目录里这个文件」的校验值，
        # source_sha256 是「上游原件」的校验值。经清洗的字形两者会不同。
        declared_local = str(item.get("local_sha256") or "").strip().lower()
        declared_source = str(item.get("source_sha256") or "").strip().lower()
        if declared_local:
            if declared_local != local_sha:
                raise SystemExit(
                    f"glyph {glyph_id}: 清单记的 local_sha256 {declared_local[:12]} "
                    f"与实际 {local_sha[:12]} 不符"
                )
        elif declared_source and declared_source != local_sha:
            raise SystemExit(
                f"glyph {glyph_id}: 清单记的 source_sha256 {declared_source[:12]} "
                f"与实际 {local_sha[:12]} 不符"
            )
        upstream_sha = declared_source or local_sha
        plan.append((item, src, local_sha, upstream_sha, name, record_id))

    if missing:
        raise SystemExit("清单里这些文件不存在：\n  " + "\n  ".join(missing[:20]))
    if not plan:
        raise SystemExit("清单里没有可入库的字形")

    # 孤儿体检要**在落盘之前**做：目录里多出来的旧文件（上一版清单有、这一版没有）
    # 留着就是「文件在、出处记录不在」——AGENTS.md 的硬规则是「无出处，不入仓库」。
    # 所以默认直接报错；要删就显式给 --prune。
    #
    # 「这一层原来有哪些文件」从 provenance 查，不靠猜：
    # - 不给 --provenance-scope 时，本次导入独占整层，目录里任何不在清单里的字形都算多余；
    # - 给了 scope 时（同层多来源），只有本批次原来那些算多余，别家来源的字形只报告。
    expected_names = {entry[4] for entry in plan}
    owned = owned_paths(prov_path, script, layer, scope)
    owned_names = {Path(p).name for p in owned if p}

    # **跨来源批次的层键/路径撞车检查**（落盘之前）。
    # 同层多来源时，别家批次占的层键不能被这次导入覆盖——
    # 覆盖了就是「文件被换掉、别家的 provenance 的 sha256 变成假话」。
    other_paths, other_keys = other_scope_claims(prov_path, script, layer, scope)
    if other_paths or other_keys:
        clashes: list[str] = []
        for item, _src, _ls, _us, name, record_id in plan:
            rel = f"glyphs/{script}/{name}"
            if rel in other_paths:
                clashes.append(f"路径 {rel} 已被别的来源批次占用")
            key = layer_key({"codepoint": item.get("codepoint"),
                             "glyph_id": record_id})
            if key in other_keys:
                clashes.append(f"层键 {key}（{name}）已被别的来源批次占用")
        if clashes:
            listing = "\n      ".join(clashes[:10])
            raise SystemExit(
                f"本次导入会覆盖**别的来源批次**的字形（{len(clashes)} 处）：\n"
                f"      {listing}\n"
                f"      同层多来源时，各批次的层键必须错开（甲骨层 JGW 占 1..1203、"
                f"汉典占 1204..）。\n"
                f"      继续导出会静默改掉别家的字形文件，让它们的出处记录里的 sha256 变成假话。")

    if scope is None:
        stale = sorted(p.name for p in out_dir.glob("*.svg") if p.name not in expected_names)
        foreign = []
    else:
        stale = sorted(name for name in owned_names if name not in expected_names)
        foreign = sorted(p.name for p in out_dir.glob("*.svg")
                         if p.name not in expected_names and p.name not in owned_names)
    if stale:
        listing = ", ".join(stale[:10]) + (" …" if len(stale) > 10 else "")
        if args.prune:
            for name in stale:
                (out_dir / name).unlink()
            print(f"多余字形    : 删除 {len(stale)} 个（--prune）：{listing}")
        else:
            raise SystemExit(
                f"{out_dir} 里有 {len(stale)} 个不在本次清单里的旧字形：{listing}\n"
                f"      这些文件没有对应的 provenance 记录，违反「无出处，不入仓库」。\n"
                f"      要删就重跑并加 --prune；要留就先确认它们另有出处。")
    if foreign:
        print(f"其他来源    : {len(foreign)} 个字形不属于本批次，原样保留"
              f"（{', '.join(foreign[:5])}{' …' if len(foreign) > 5 else ''}）")

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    for item, src, local_sha, upstream_sha, name, record_id in plan:
        glyph_id = int(item["glyph_id"])
        dest = out_dir / name
        if args.dry_run:
            dest_sha = local_sha
        else:
            shutil.copyfile(src, dest)
            dest_sha = sha256_file(dest)
            if dest_sha != local_sha:
                raise SystemExit(f"{dest}: 复制后 sha256 不一致")

        modifications = str(item.get("modifications") or "").strip()
        record = {
            "path": f"glyphs/{script}/{name}",
            "sha256": dest_sha,
            "script": script,
            "layer": layer,
            "glyph_id": record_id,
            "license": str(item.get("license") or license_id).strip(),
            # **取回时间取清单里的逐字形值，取不到才用入库时刻。**
            #
            # 清单（抓取脚本的 manifest）记着每个字形是哪一刻从上游拿到的。
            # 重新导入一遍 ≠ 重新从上游取一次：扩量重拓时旧字形的字节没变、
            # 也没重下，把它们的时间戳刷成「现在」等于凭空多了一次上游取回。
            # 所以这里优先用清单的值。
            "retrieved_at": str(item.get("retrieved_at") or retrieved_at).strip(),
            "modifications": modifications or "none (byte-identical copy)",
        }
        for field in ("license_url", "attribution", "source_dataset", "source_url",
                      "source_commit", "source_path", "source_sha256", "source_id",
                      "source_book", "source_number", "source_page_url", "modern_char",
                      "unicode", "period", "variant", "rendering", "source_doi",
                      "source_record_url", "source_artifact_url", "codepoint",
                      "seal_candidates", "seal_note", "alt_caption", "book_code",
                      "book_part", "source_cited_book", "dual_caption",
                      "source_references"):
            value = str(item.get(field) or manifest.get(field) or "").strip()
            if value:
                record[field] = value
        record["source_sha256"] = upstream_sha
        # 楚文字：题记只给出出土文献的代码，对照表里有全称就换上去。
        # 表里没有就保留原文代码——宁可留个代码，也不要编一个书名。
        if record.get("book_code") and books:
            mapped = lookup_book(books, str(record.get("source_book") or ""),
                                 str(record["book_code"]))
            if mapped:
                record["source_book"] = mapped
        if not any(record.get(f) for f in ("source_url", "source_record_url",
                                           "source_artifact_url", "source_page_url",
                                           "mirror_url")):
            raise SystemExit(f"glyph {glyph_id}: 缺少来源 URL 字段")
        if scope is not None:
            # scope 的值必须跟清单里写的一致。写错一个字符的话，旧记录不会被替换、
            # 过期文件检不出来，同一个文件还会写出两条 provenance——而导入却报成功。
            field, value = scope
            got = str(record.get(field) or "").strip()
            if got != value:
                raise SystemExit(
                    f"glyph {glyph_id}: 清单的 {field} 是 {got!r}，"
                    f"与 --provenance-scope 指定的 {value!r} 不一致。\n"
                    f"      两边必须一致，否则这批字形的出处记录会与旧记录重复。")
        records.append(record)

        row = {
            "modern_char": record.get("modern_char", ""),
            "unicode": record.get("unicode", ""),
            "period": record.get("period", ""),
            "variant": record.get("variant", ""),
            "source_book": record.get("source_book", ""),
            "source_number": record.get("source_number", ""),
            "source_id": record.get("source_id", ""),
            "source_path": record.get("source_path", ""),
            "source_url": record.get("source_url", ""),
            "file": name,
            "sha256": dest_sha,
        }
        if record.get("book_part"):
            row["book_part"] = record["book_part"]
        if record.get("source_cited_book"):
            row["source_cited_book"] = record["source_cited_book"]
        if args.key_mode == "seal_codepoint":
            row["codepoint"] = record.get("codepoint", "")
            row["seal_candidates"] = record.get("seal_candidates", "")
            row["seal_note"] = record.get("seal_note", "")
        else:
            row["glyph_id"] = glyph_id
        index_rows.append(row)

    if not args.dry_run:
        index_path = out_dir / "index.csv"
        if args.key_mode == "seal_codepoint":
            header = list(SEAL_KEY_COLUMNS)
        else:
            header = ["glyph_id"] + [c for c in INDEX_EXTRA_COLUMNS if c != "glyph_id"]
            # 只在确实有值时加可选列，且放在 source_book 后面，读表时挨着看。
            for col in OPTIONAL_INDEX_COLUMNS:
                if any(str(row.get(col) or "").strip() for row in index_rows):
                    header.insert(header.index("source_book") + 1, col)
        # 同层多来源时（甲骨层有 JGW 与汉典两批），索引要**并**进去，不能盖掉别家。
        # 列取并集：别家那一批有的列（如 JGW 的 char_form）本批没有就留空。
        #
        # 但**本批次自己的旧行必须剔掉**：那批文件这次被替换了，旧行留着就成了
        # 悬空（文件被 --prune 删了，索引行还在），同一次导入两次还会写出重复行。
        # 「本批次的旧行」就是本 scope 拥有过的那些文件（从 provenance 查）。
        old_rows: list[dict] = []
        if scope is not None and index_path.is_file():
            with index_path.open("r", encoding="utf-8", newline="") as handle:
                old_rows = list(csv.DictReader(handle))
            for row in old_rows:
                for col in row:
                    if col not in header:
                        header.append(col)
            old_rows = [r for r in old_rows
                        if (r.get("file") or "") not in owned_names]
            index_rows = old_rows + index_rows
            # 排序键按键模式取：篆书模式的索引主键是 codepoint，没有 glyph_id 列。
            # 按 glyph_id 排会 KeyError——而且崩在**落盘之后**，
            # 留下一批既没有出处记录、也没有索引行的孤儿字形。
            if args.key_mode == "seal_codepoint":
                index_rows.sort(key=lambda r: str(r.get("codepoint") or ""))
            else:
                index_rows.sort(key=lambda r: int(r.get("glyph_id") or 0))
        with index_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
            writer.writeheader()
            writer.writerows(index_rows)
        kept, total, _owned = merge_provenance(prov_path, script, layer, records, scope)
        print(f"provenance.jsonl: 保留其他记录 {kept} 条，写入后共 {total} 条")
        if scope:
            print(f"批次范围    : {scope[0]}={scope[1]}（别的来源原样保留）")

    print(f"书体        : {script}")
    print(f"许可        : {license_id}（在允许名单内）")
    if args.key_mode == "seal_codepoint":
        print(f"字形        : {len(records)} 个 -> glyphs/{script}/<码位>.svg")
    else:
        print(f"字形        : {len(records)} 个 -> glyphs/{script}/<glyph_id:04d>.svg")
    if skipped:
        print(f"未入库      : {len(skipped)} 个")
    print("dry-run：未写入任何文件" if args.dry_run else "完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
