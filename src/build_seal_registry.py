#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建立篆书层的「外部登记表」glyphs/seal/external.csv。

用法::

    python src/build_seal_registry.py [--repo-root DIR]

**本脚本不下载、不复制任何字形文件内容。** 它只登记两类信息：

1. 上游仓库（frankslin/kaiyuan-small-seal-font）的文件清单——从 GitHub 的
   git/trees API 取路径与 blob SHA-1，作为「我们指向的是哪个字节」的锚点；
2. Unicode 18.0 `SealSources.txt` 的篆书身份骨架——kSEAL_CCZSrc / DYCSrc /
   QJZSrc / THXSrc（四个《说文》版本的流水号）、kSEAL_MCJK（现代汉字）、
   kSEAL_Rad（部首）。

为什么用登记表而不是 submodule 或直接复制：
- 只登记标识符与链接，**不构成对上游内容的分发**，所以不受上游许可状态影响；
- 不把上游 96 MB 的仓库带进本项目，也不影响 GitHub Pages 部署；
- 上游文件命名就是 ``u<码位大写十六进制>.svg``，所以这份映射可以完全由码位推出。

上游许可状态见 `THIRD_PARTY_NOTICES.md`：截至登记时，上游的 ``OFL.txt`` 正文与其
声明的 OFL 1.1 不一致、且 ``glyphs/**`` 未被明确标记为受该协议约束，因此本仓库
**不复制其字形**，只登记指针。上游一旦澄清，可用同一份表一次性导入。

表里还有一处**对 Unicode 原文的偏差修正**（U+3D06D 归「玉」而非「王」），
依据是 SealSources.txt 自己的 ``kSEAL_Rad`` 部首结构。修正写死在
``MCJK_DEVIATIONS`` 里，逐行记在 ``note`` 列，并汇总进 ``external.meta.json``。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UPSTREAM_REPO = "frankslin/kaiyuan-small-seal-font"
UPSTREAM_BRANCH = "main"
TREE_API = f"https://api.github.com/repos/{UPSTREAM_REPO}/git/trees/{UPSTREAM_BRANCH}?recursive=1"
UPSTREAM_URL_TEMPLATE = f"https://github.com/{UPSTREAM_REPO}/blob/{{commit}}/{{path}}"
SEAL_SOURCES_URL = "https://www.unicode.org/Public/18.0.0/ucd/SealSources.txt"

COLUMNS = [
    "codepoint", "unicode", "modern_char", "radical_no", "radical_cp",
    "ccz", "dyc", "qjz", "thx",
    "upstream_path", "upstream_blob_sha1", "note",
]

# ---------------------------------------------------------------------------
# 对 Unicode SealSources.txt 的已知偏差修正。
#
# SealSources.txt 用 kSEAL_MCJK 记录「这个篆书码位对应哪个现代汉字」。其中
# U+3D06D 被记成 U+738B（王），但同一份文件里的 kSEAL_Rad（部首归属）自相矛盾：
#
#     U+3D068   kSEAL_Rad = 5.3D068    → 说文第 5 部「王」部的部首字
#     U+3D06D   kSEAL_Rad = 6.3D06D    → 说文第 6 部「玉」部的部首字
#
# 说文 540 部里第 5 部是「王」、第 6 部是「玉」，两部相邻，各自的首字不同。
# 若 U+3D06D 真是「王」的重文，它不可能同时是「玉」部的部首字。
# OpenCC 的 SealCharacters.txt 也把 U+3D06D 记作「玉」（其反查表给出的
# 玉 → U+3D06D、王 → U+3D068，与部首结构一致）。
#
# 不修正的后果很实际：Unicode 口径下「玉」没有任何篆书码位，抓取名单里就根本没有
# 「玉」这个字，篆书层永远缺一块。本表按部首结构修正，并在 note 列逐行标出，
# 修正依据同时写进 external.meta.json 与 THIRD_PARTY_NOTICES.md。
# ---------------------------------------------------------------------------
MCJK_DEVIATIONS = {
    "3D06D": {
        "unicode": "007389",
        "char": "玉",
        "was": "00738B",
        "reason": "kSEAL_Rad=6.3D06D 表明此码位是「玉」部（说文第 6 部）部首字，"
                  "与 kSEAL_MCJK=738B（王）矛盾；OpenCC SealCharacters.txt 亦记作「玉」",
    },
}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "hanzi-glyphs-svg/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def load_seal_sources(cache: Path) -> dict[str, dict[str, str]]:
    if not cache.is_file():
        print(f"  拉取 {SEAL_SOURCES_URL}")
        cache.write_bytes(fetch(SEAL_SOURCES_URL))
    props: dict[str, dict[str, str]] = {}
    for line in cache.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        codepoint, key, value = parts
        codepoint = codepoint.strip().upper()
        if codepoint.startswith("U+"):
            codepoint = codepoint[2:]
        props.setdefault(codepoint, {})[key] = value
    return props


def load_upstream_glyphs(cache: Path) -> tuple[str, dict[str, dict[str, object]]]:
    if not cache.is_file():
        print(f"  拉取 {TREE_API}")
        cache.write_bytes(fetch(TREE_API))
    tree = json.loads(cache.read_text(encoding="utf-8"))
    if tree.get("truncated"):
        raise SystemExit("上游 tree 被截断，映射会不完整；请改用分页方式重取")
    glyphs: dict[str, dict[str, object]] = {}
    for entry in tree["tree"]:
        path = entry["path"]
        if entry.get("type") == "blob" and path.startswith("glyphs/") and path.endswith(".svg"):
            stem = path[len("glyphs/"):-len(".svg")]
            if stem.startswith("u"):
                glyphs[stem[1:].upper()] = {
                    "path": path, "sha1": entry["sha"], "size": entry.get("size"),
                }
    return tree["sha"], glyphs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="建立篆书外部登记表")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="上游数据的缓存目录，默认 <repo>/tmp/seal-registry")
    parser.add_argument("--refresh", action="store_true", help="忽略缓存重新拉取")
    args = parser.parse_args(argv)

    repo_root: Path = args.repo_root.resolve()
    cache = (args.cache_dir or repo_root / "tmp" / "seal-registry").resolve()
    cache.mkdir(parents=True, exist_ok=True)
    if args.refresh:
        for name in ("upstream-tree.json", "SealSources.txt"):
            target = cache / name
            if target.is_file():
                target.unlink()

    print("取上游文件清单与 Unicode 篆书骨架…")
    commit, upstream = load_upstream_glyphs(cache / "upstream-tree.json")
    props = load_seal_sources(cache / "SealSources.txt")
    print(f"  上游 commit : {commit}")
    print(f"  上游字形文件: {len(upstream)}")
    print(f"  篆书码位    : {len(props)}")

    rows = []
    deviations: list[dict] = []
    # 本层已落盘的字形：���来算「哪些码位还空着」，逐行写进 note 列。
    local_dir = repo_root / "glyphs" / "seal"
    local_filled = {p.stem.upper() for p in local_dir.glob("*.svg")}
    for codepoint in sorted(props):
        info = props[codepoint]
        up = upstream.get(codepoint)
        modern = info.get("kSEAL_MCJK", "").strip()
        radical = info.get("kSEAL_Rad", "").strip()
        radical_no, _, radical_cp = radical.partition(".")
        note = ""
        dev = MCJK_DEVIATIONS.get(codepoint)
        if dev:
            # SealSources.txt 里的 kSEAL_MCJK 是 4 位（738B），这里统一成 6 位比。
            if modern.upper().rjust(6, "0") != dev["was"]:
                raise SystemExit(
                    f"{codepoint}: 偏差修正的前提变了——SealSources.txt 现在记的是 "
                    f"{modern!r}，不再是 {dev['was']!r}。请重新核对后改这张表。")
            modern = dev["unicode"]
            note = ("unicode-mcjk-deviation:原记 "
                    f"{dev['was']}（王），按 kSEAL_Rad 部首结构改判为 {dev['unicode']}（玉）；"
                    f"依据：{dev['reason']}")
            deviations.append({
                "codepoint": f"U+{codepoint}",
                "was_unicode": dev["was"],
                "now_unicode": dev["unicode"],
                "now_char": dev["char"],
                "reason": dev["reason"],
            })
        # 缺口也要说清楚为什么空着。分两种：
        # - 上游（開元小篆）有这个码位的字形，blob SHA-1 已登记，
        #   但上游许可文件没补齐，本仓库不复制字形，只登记指针；
        # - 既没有本层字形、上游也没有指针，确实无来源。
        if codepoint.upper() not in local_filled:
            gap = ("未入库：上游有字形（blob SHA-1 已登记），"
                   "待上游补齐许可文件后导入" if up else
                   "未入库：无来源（本层无字形，上游也无指针）")
            note = f"{note}；{gap}" if note else gap
        rows.append({
            "codepoint": f"U+{codepoint}",
            # 与 AGENTS.md 的文件名约定一致：现代汉字码位取 6 位大写十六进制
            "unicode": modern.upper().rjust(6, "0"),
            "modern_char": chr(int(modern, 16)) if modern else "",
            "radical_no": radical_no,
            "radical_cp": radical_cp,
            "ccz": info.get("kSEAL_CCZSrc", ""),
            "dyc": info.get("kSEAL_DYCSrc", ""),
            "qjz": info.get("kSEAL_QJZSrc", ""),
            "thx": info.get("kSEAL_THXSrc", ""),
            "upstream_path": up["path"] if up else "",
            "upstream_blob_sha1": up["sha1"] if up else "",
            "note": note,
        })

    out_dir = repo_root / "glyphs" / "seal"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "external.csv"
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    meta = {
        "upstream_repo": UPSTREAM_REPO,
        "upstream_branch": UPSTREAM_BRANCH,
        "upstream_commit": commit,
        "upstream_glyph_count": len(upstream),
        "codepoint_count": len(rows),
        "codepoints_with_upstream": sum(1 for r in rows if r["upstream_path"]),
        "unsealed_sources_url": SEAL_SOURCES_URL,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "仅登记指针，未复制任何上游字形内容；许可状态见 THIRD_PARTY_NOTICES.md",
        "deviations": deviations,
    }
    meta_path = out_dir / "external.meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    missing = [r["codepoint"] for r in rows if not r["upstream_path"]]
    print()
    print(f"写出 : {out_path}  ({out_path.stat().st_size} bytes, {len(rows)} 行)")
    print(f"写出 : {meta_path}")
    print(f"有上游文件 : {meta['codepoints_with_upstream']} / {len(rows)}")
    print(f"缺上游文件 : {len(missing)}  {missing[:8]}{' …' if len(missing) > 8 else ''}")
    extra = sorted(set(upstream) - set(props))
    print(f"上游多出的码位 : {len(extra)} {extra[:5]}")
    if deviations:
        print(f"对 Unicode 原文的偏差修正 {len(deviations)} 处：")
        for dev in deviations:
            print(f"  {dev['codepoint']}  {dev['was_unicode']} → {dev['now_unicode']}"
                  f"（{dev['now_char']}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
