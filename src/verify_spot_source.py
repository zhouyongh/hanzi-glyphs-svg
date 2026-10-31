#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抽样回源核验：随机（分层）抽若干字形，回到汉典核一遍。

核四件事：

1. **上游原件对得上**——重新下载上游 SVG，算出的 sha256 与 provenance 里的
   `source_sha256` 相同吗？
2. **本地字形只差水印**——对上游原件跑一遍 ``strip_watermark``，得到的字节
   与层目录里的文件逐字节相同吗？（改动是否只发生在水印上）
3. **题记与页面配对没错**——重新抓汉典的字页面，题记原文（``variant``）在页面的
   实例列表里吗？
4. **汉典字形编号在页面上**——``source_id`` 在该页的图片列表里吗？

抽样是**按文献代号分层**的：先每个代号各抽一条，再从剩下的里随机补。
不然稀有代号（「馬」只有几条）永远抽不到——抽样就白做了。

用法：

    python src/verify_spot_source.py --layer chu --count 30
    python src/verify_spot_source.py --layer bronze --count 20 --kind jinwen

只用标准库（``strip_watermark`` 从 ``clean_zdic_glyphs`` 借）。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clean_zdic_glyphs import strip_watermark  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
CAPTION_RE = re.compile(r'class="caption"[^>]*>(.*?)</div>', re.S)
IMAGE_RE = re.compile(r"img\.zdic\.net/zy/[a-z]+/([A-Za-z0-9_]+)\.svg")

# 汉典的字页路径：<kind> 是汉典那一栏的名字（chuwenzi / jinwen / lishu …）。
KIND_BY_LAYER = {
    "chu": "chuwenzi",
    "bronze": "jinwen",
    "clerical": "lishu",
    "oracle": "jiaguwen",
    "seal": "xiaozhuan",
}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.zdic.net/",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def stratified_sample(rows: list[dict], count: int, rng: random.Random) -> list[dict]:
    """每个文献代号先各取一条，再随机补足。"""
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        buckets.setdefault(row.get("source_book") or row.get("book_code") or "", []).append(row)
    picked: list[dict] = []
    for key in sorted(buckets):
        picked.append(rng.choice(buckets[key]))
    rest = [r for r in rows if r not in picked]
    rng.shuffle(rest)
    picked.extend(rest[: max(0, count - len(picked))])
    return picked[:count]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抽样回源核验汉典来源的字形层")
    parser.add_argument("--layer", required=True, help="层名（chu / bronze / clerical / oracle / seal）")
    parser.add_argument("--count", type=int, default=20, help="抽样条数")
    parser.add_argument("--kind", default=None, help="汉典那一栏的名字（默认按层名推断）")
    parser.add_argument("--seed", type=int, default=None, help="随机种子（便于复现同一次抽样）")
    parser.add_argument("--delay", type=float, default=0.4, help="每个字之间的间隔秒数")
    args = parser.parse_args(argv)

    kind = args.kind or KIND_BY_LAYER.get(args.layer)
    if not kind:
        raise SystemExit(f"不知道层「{args.layer}」对应汉典哪一栏，请用 --kind 指定")

    layer_dir = ROOT / "glyphs" / args.layer
    index_path = layer_dir / "index.csv"
    prov_path = ROOT / "glyphs" / "provenance" / f"{args.layer}.jsonl"
    if not index_path.is_file():
        raise SystemExit(f"找不到索引：{index_path}")
    if not prov_path.is_file():
        raise SystemExit(f"找不到出处记录：{prov_path}")

    rows = list(csv.DictReader(index_path.open(encoding="utf-8-sig", newline="")))
    prov = {}
    for line in prov_path.open(encoding="utf-8"):
        if line.strip():
            rec = json.loads(line)
            prov[rec["source_id"]] = rec

    rng = random.Random(args.seed)
    sample = stratified_sample(rows, min(args.count, len(rows)), rng)

    ok = {"upstream": 0, "local": 0, "caption": 0, "page": 0}
    bad: list[str] = []
    for row in sample:
        sid = row["source_id"]
        rec = prov.get(sid, {})
        try:
            raw = get(row["source_url"])
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{sid}: 上游下载失败 {exc!r}")
            time.sleep(args.delay)
            continue
        src_sha = hashlib.sha256(raw).hexdigest()
        if src_sha == rec.get("source_sha256"):
            ok["upstream"] += 1
        else:
            bad.append(f"{sid}: 上游 sha256 不符（{src_sha[:12]} vs {str(rec.get('source_sha256'))[:12]}）")
        text = raw.decode("utf-8", "replace")
        cleaned, count, _ = strip_watermark(text)
        out_bytes = cleaned.encode("utf-8") if count else raw
        local = (layer_dir / row["file"]).read_bytes()
        if out_bytes == local:
            ok["local"] += 1
        else:
            bad.append(f"{sid}: 本地字形与「洗掉水印的上游」不一致")
        try:
            page = get(f"https://www.zdic.net/hans/"
                       f"{urllib.parse.quote(row['modern_char'])}/{kind}").decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{sid}: 字页面抓取失败 {exc!r}")
            time.sleep(args.delay)
            continue
        caps = [re.sub(r"<[^>]+>", "", m.group(1)).strip()
                for m in CAPTION_RE.finditer(page)]
        if row["variant"] in caps:
            ok["caption"] += 1
        else:
            bad.append(f"{sid}: 题记「{row['variant']}」不在字页面的实例列表里")
        if sid in IMAGE_RE.findall(page):
            ok["page"] += 1
        else:
            bad.append(f"{sid}: 汉典字形编号不在字页面的图片列表里")
        time.sleep(args.delay)

    total = len(sample)
    print(f"层          : {args.layer}（汉典栏 {kind}）")
    print(f"抽样        : {total} 条（按文献代号分层）")
    for k, label in (("upstream", "上游原件 sha256 相符"),
                     ("local", "本地字形 = 洗掉水印的上游"),
                     ("caption", "题记在汉典页面实例列表里"),
                     ("page", "汉典字形编号在页面图片列表里")):
        print(f"  {label:26s} {ok[k]}/{total}")
    if bad:
        print("\n=== 不符 ===")
        for b in bad:
            print("  " + b)
    else:
        print("\n全部相符。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
