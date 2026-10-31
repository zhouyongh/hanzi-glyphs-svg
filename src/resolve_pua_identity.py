#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反查私用區字頭的现代字身份。

**为什么要做这件事。** 小學堂字頭行的「楷書字頭」是**字體排版槽位**，不是 Unicode：
罕見字落在字體自己的私用區（PUA）上。PUA 码位**不是漢字**，不能当层键的 unicode 部分。
这类字頭占實測實例的 14%（楚系库）——直接丢字形是浪费，直接用码位当 unicode 是造假。

所以要**反查**出一条有据可查的身份来。两条路：

路线 D · 底本页.行（主）
    《楚系簡帛文字編》按「页.行」定位——摹本里一字一行，一个页.行只对应一个字。
    小學堂字頭的「相關索引」列記这个字在各底本的页.行；漢典层的 ``source_base_pages``
    记的就是同一套页.行。两边一对，字就接回去了。
    **实测在 195 个已知身份的字頭上，一致率 100%。**

路线 A · 說文小篆槽位（辅）
    篆书层（``glyphs/seal/``）的 ``source_id`` 就是「說文小篆」字體的槽位，
    與小學堂字體號 27 是同一套槽位。槽位 → 现代字候选。
    槽位常常对应多个码位（正字 + 重文 + 古文），所以它只能**当旁证**：
    与路线 D 同时命中且一致时加强证据；单独命中时作为次选。

路线 D 唯一命中 > 路线 A 唯一命中 > 两者交集唯一 > 都不成立（临时身份）。

**不做的事。** 不用「在现代书体层收不收得到」或「在漢典层出现频次高低」来挑正字——
两者都验过，会选错（简繁成对、异体字同样收录）。多候选一律不猜。

输出是一份「字頭 → 现代字」的对照表（JSONL），由 ``build_xxt_manifest.py`` 读取。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 私用區（PUA）與代理區——这些码位**不是漢字**，不能当层键的 unicode 部分。
PUA_RANGES = (
    (0xE000, 0xF8FF),      # BMP 私用區
    (0xF0000, 0xFFFFD),    # 私用區 A
    (0x100000, 0x10FFFD),  # 私用區 B
)

# 「底本名 …… 頁.行：1.3、8.4」里的页.行
RE_BASE_PAGES = re.compile(r"頁[.．]?行[：:]\s*([^\s，,；;]+)")
RE_SPLIT = re.compile(r"[、,，;；\s]+")


def is_pua(ch: str) -> bool:
    """这个字符是不是私用區/代理區（不是漢字）。"""
    if not ch or len(ch) != 1:
        return True
    cp = ord(ch)
    if 0xD800 <= cp <= 0xDFFF:      # 代理區
        return True
    return any(lo <= cp <= hi for lo, hi in PUA_RANGES)


def norm_cp(ch: str) -> str:
    return f"{ord(ch):04X}".rjust(6, "0")


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_csv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def base_pages_of(references: list[str], base_book: str) -> set[str]:
    """從「相關索引」裡抽出指定底本的页.行集合。

    只认**指定底本**的那一条：同一份字頭的相關索引里还列着《睡虎地秦簡文字編》
    《傳抄古文字編》等别的底本，粒度与页.行体系都不同，混进来会错配。
    """
    out: set[str] = set()
    for item in references or []:
        if base_book and base_book not in item:
            continue
        m = RE_BASE_PAGES.search(item)
        if not m:
            continue
        for part in RE_SPLIT.split(m.group(1)):
            part = part.strip()
            if part:
                out.add(part)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="反查私用區字頭的现代字身份")
    ap.add_argument("--index", required=True, type=Path, help="实例索引 index.jsonl")
    ap.add_argument("--out", required=True, type=Path, help="输出对照表 identity_map.jsonl")
    ap.add_argument("--zdic-provenance", type=Path, default=None,
                    help="漢典层 provenance（路线 D 用；要含 source_base_pages 字段）")
    ap.add_argument("--seal-index", type=Path, default=None,
                    help="篆书层 index.csv（路线 A 用；source_id 是「說文小篆」槽位）")
    ap.add_argument("--base-book", default="楚系簡帛文字編",
                    help="路线 D 的底本名（要在相關索引里匹配）")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个私用區字頭（调试）")
    ap.add_argument("--verify-known", action="store_true",
                    help="自检：不停在已知身份的字頭上，改成拿反查结果去对答案，"
                         "统计一致率（路线 D 的可信度就是靠这个量出来的）")
    args = ap.parse_args(argv)

    instances = load_jsonl(args.index.resolve())
    if not instances:
        raise SystemExit(f"索引读不出来：{args.index}")

    # ---- 路线 D：页.行 → 漢典层的现代字 ----
    z_by_page: dict[str, set[str]] = defaultdict(set)
    z_pages_of_char: dict[str, set[str]] = defaultdict(set)
    if args.zdic_provenance:
        for rec in load_jsonl(args.zdic_provenance.resolve()):
            ch = rec.get("modern_char") or ""
            if not ch:
                continue
            pages = (rec.get("source_base_pages") or "").strip()
            if not pages:
                continue
            for p in RE_SPLIT.split(pages):
                p = p.strip()
                if p:
                    z_by_page[p].add(ch)
                    z_pages_of_char[ch].add(p)

    # ---- 路线 A：說文小篆槽位 → 现代字候选 ----
    seal_by_slot: dict[str, list[str]] = defaultdict(list)
    if args.seal_index:
        for row in load_csv(args.seal_index.resolve()):
            sid = (row.get("source_id") or "").strip()
            ch = (row.get("modern_char") or "").strip()
            if sid and ch:
                seal_by_slot[sid].append(ch)

    # ---- 字頭級彙總：页.行集合、槽位、已知身份 ----
    head_pages: dict[int, set[str]] = {}
    head_slots: dict[int, set[str]] = defaultdict(set)
    head_known: dict[int, set[str]] = defaultdict(set)
    head_count: dict[int, int] = defaultdict(int)
    for inst in instances:
        zi = inst.get("zi_order")
        if zi is None:
            continue
        head_count[zi] += 1
        slot = inst.get("modern_char_slot") or ""
        if slot:
            head_slots[zi].add(slot)
        # 字頭行里的**異體字**也带槽位；其中可能藏着「說文小篆」那条（字體號 27），
        # 那是路线 A 的入口——只取 modern_char_slot 会漏掉它。
        for v in inst.get("variants") or []:
            if isinstance(v, str) and "_" in v:
                head_slots[zi].add(v)
        ch = inst.get("modern_char") or ""
        if ch and not is_pua(ch):
            head_known[zi].add(ch)
        if zi not in head_pages:
            head_pages[zi] = base_pages_of(inst.get("base_pages", []), args.base_book)

    records: list[dict] = []
    stats = {"base-page": 0, "seal-slot": 0, "base-page+seal-slot": 0,
             "base-page∩seal-slot": 0, "pua-slot": 0}
    verify = {"agree": 0, "disagree": 0, "no_candidate": 0, "multi": 0}
    mismatches: list[tuple] = []

    for zi in sorted(head_pages):
        known = head_known.get(zi)
        if known and not args.verify_known:
            continue    # 站点已经给出真汉字，不用反查
        slots = head_slots.get(zi, set())

        # 路线 D
        pages = head_pages.get(zi, set())
        cands_d: set[str] = set()
        for p in pages:
            cands_d |= z_by_page.get(p, set())

        # 路线 A
        cands_a: set[str] = set()
        for s in slots:
            cands_a |= set(seal_by_slot.get(s, []))

        char = ""
        confidence = ""
        evidence: dict = {"slot": sorted(slots), "base_pages": sorted(pages)}

        if len(cands_d) == 1:
            char = next(iter(cands_d))
            if len(cands_a) == 1 and cands_a == cands_d:
                confidence = "base-page+seal-slot"
            else:
                confidence = "base-page"
            evidence["base_page_chars"] = sorted(cands_d)
            if cands_a:
                evidence["seal_slot_chars"] = sorted(cands_a)
        elif len(cands_d) > 1 and len(cands_a) == 1 and cands_a <= cands_d:
            # 槽位在页.行候选里 —— 两条证据一致地指向同一个字
            char = next(iter(cands_a))
            confidence = "base-page∩seal-slot"
            evidence["base_page_chars"] = sorted(cands_d)
            evidence["seal_slot_chars"] = sorted(cands_a)
        elif len(cands_a) == 1:
            char = next(iter(cands_a))
            confidence = "seal-slot"
            evidence["seal_slot_chars"] = sorted(cands_a)

        if char:
            stats[confidence] = stats.get(confidence, 0) + 1
        else:
            confidence = "pua-slot"
            stats["pua-slot"] += 1
            evidence["base_page_chars"] = sorted(cands_d)
            evidence["seal_slot_chars"] = sorted(cands_a)

        if known and args.verify_known:
            # 自检：拿反查结论去对站点自己给的身份。
            if not char:
                verify["no_candidate"] += 1
            elif len(cands_d) > 1:
                verify["multi"] += 1
            elif char in known:
                verify["agree"] += 1
            else:
                verify["disagree"] += 1
                mismatches.append((zi, sorted(known), char, confidence))
            continue

        records.append({
            "zi_order": zi,
            "modern_char": char,
            "unicode": norm_cp(char) if char else "",
            "confidence": confidence,
            "instances": head_count.get(zi, 0),
            "evidence": evidence,
        })
        if args.limit and len(records) >= args.limit:
            break

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")

    total = len(records)
    if args.verify_known:
        print(f"自检模式：检查 {total} 个字頭")
    else:
        print(f"私用區字頭 {total} 個 → {args.out}")
        for k, v in stats.items():
            if v:
                print(f"  {k}: {v}")
        resolved = total - stats.get("pua-slot", 0)
        if total:
            print(f"  可反查出身份：{resolved}/{total} = {resolved/total:.2%}")
    if args.verify_known:
        judged = verify["agree"] + verify["disagree"]
        print(f"\n自检（拿反查结论对站点自己给的身份）：")
        print(f"  一致 {verify['agree']} / 不一致 {verify['disagree']} / "
              f"无候选 {verify['no_candidate']} / 多候选 {verify['multi']}")
        if judged:
            print(f"  一致率 {verify['agree']}/{judged} = {verify['agree']/judged:.2%}")
        for row in mismatches[:20]:
            print(f"    不一致：zi={row[0]} 站点={row[1]} 反查={row[2]!r} ({row[3]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
