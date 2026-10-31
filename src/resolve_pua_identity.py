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

路线 C · 字形键（辅）
    字形键 = 「字体号_码位」。**两库同构**：同一套摹本的同一套字体槽位，
    在漢典与小學堂里是同一个键。漢典层收录了这个字形、且**只给了一个**现代字时，
    那个字就是它的身份；同一字形挂着多个现代字时属歧义，**不猜**。
    傳抄层实测：两库键空间完全一致（60/60 命中，零不一致）。

    **歧义不是噪声，是层语义**：傳抄层实测 1,789 个字形键里 **395 个挂着多个现代字**
    （302 个挂 2 个，最多的挂 6 个）——那是「正字 + 異體字並存」
    （「三/叁」「上/丄」「下/丅」「世/丗/卋」…）。这些键**按歧义处理，不猜**。

    **「不一致」多半也不是反查错，是字書編纂差異**：全量实测 869 个「不一致」样本，
    **每一个都是形近異體字**（禔/媞、珌/㻫、葉/枼、理/俚、熏/曛、霝/孁…）——
    同一个字形，《傳抄古文字編》与漢典的《說文》系各釋成不同的字。
    所以路线 C 的結論要這樣讀：**唯一命中 → 該字形就是這個字**；
    命中的是異體 → 那是**层语义**，不是錯。

**路线顺序由每层自己的实测定**（``--prefer``），不是写死的：先用 ``--verify-known``
量出各路线在**已知身份**字頭上的一致率，哪条更可靠就排前面。

**但「不一致」要先分清是「反查错」还是「层语义」。** 傳抄层全量实测：
路线 D 的 3,430 次「不一致」全是**簡繁對与異體**（殺/杀、網/冈、響/响、華/华、
賓/宾、箕/其）；路线 C 的 1,072 次也全是**形近異體**（禱/𥜹、瑁/珼、璏/璓、
珌/㻫、葉/枼）——同一个字形，各底本各釋各的。**这些不是错**，是「正字 + 異體字並存」。
把这类算作「不一致」会低估路线的可靠性。

**另一件要说清的事：两条路线都受同一个上限约束。** 傳抄层全量实测（漢典 12,975 件）：

    判法              樣本    答對    答對率
    D 唯一命中        3,236   2,364   73.05%
    C 唯一命中        3,823   2,811   73.53%
    D 有候選          7,376   6,237   84.56%
    D∪C 有候選        7,377   6,237   88.38%

**「唯一命中」只有 ~28–34%**——因為異體字會讓同一个字形挂多个现代字（漢典 7,384 个
字形键里 **3,473 个挂多字**），候选集就不唯一了。**这不是路线的问题**，是层语义。
把「有候选」也算进去，D∪C 的覆盖率到 **88.38%**。
**但 D∪C 的答对数等于 D 单独答对数**（6,237 = 6,237）——**C 完全被 D 覆盖**，
C 唯一多覆盖的那部分，D 也覆盖了（且更严格）。所以**傳抄层 D 优先即可**。

- 楚系层：``--prefer D,A,C``。实测 D 712/714 = 99.72%（已知不一致的两条是
  「侯/𥎦」「蛙/䖯」——一个字在新旧字書里分屬不同部首，不是反查错）。
- 傳抄层：``--prefer D,C,A``。**实测 D 74.72% > C 73.49%**；
  两者都受「異體 → 候选不唯一」这个上限约束（唯一命中仅 28–34%）。
  D 在這层够用，**不必为了 C 换顺序**——C 只在 D 无候选时才补位。

路线 D 唯一命中 > 路线 A 唯一命中 > 路线 C 唯一命中 > 都不成立（临时身份）。

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

# 「底本名 …… 頁.行：1.3、8.4」里的页.行。
# **冊頁.行**（傳抄層的寫法，帶冊次，如「上1.2、下1031.3」）也要认——
# 只認「頁.行」的話，傳抄層一條也取不到。
RE_BASE_PAGES = re.compile(r"冊?頁[.．]?行[：:]\s*([^\s，,；;]+)")
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
    ap.add_argument("--zdic-shape-index", type=Path, default=None,
                    help="漢典层 index.csv（路线 C 用；source_id 是「字体号_码位」字形键）")
    ap.add_argument("--base-book", default="楚系簡帛文字編",
                    help="路线 D 的底本名（要在相關索引里匹配）")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个私用區字頭（调试）")
    ap.add_argument("--prefer", default="D,A,C",
                    help="路线优先顺序（逗号分隔）：D=底本页.行 A=說文小篆槽位 C=字形键。"
                         "**顺序由每层自己的实测定**：用 --verify-known 量各路线的一致率，"
                         "哪条更可靠就排前面。默认 D,A,C")
    ap.add_argument("--verify-known", action="store_true",
                    help="自检：不停在已知身份的字頭上，改成拿反查结果去对答案，"
                         "统计一致率（路线 D 的可信度就是靠这个量出来的）")
    args = ap.parse_args(argv)

    prefer = [p.strip().upper() for p in (args.prefer or "").split(",") if p.strip()]
    unknown = [p for p in prefer if p not in ("D", "A", "C")]
    if unknown:
        raise SystemExit(f"未知的路线代号：{'、'.join(unknown)}（只认 D / A / C）")

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

    # ---- 路线 C：字形键 → 现代字候选 ----
    # 字形键 = 「字体号_码位」。**两库同构**：同一套摹本的同一套字体槽位，
    # 在漢典与小學堂里是同一个键。所以「漢典层收录了这个字形、且只给了一个现代字」
    # 时，那个字就是它的身份。同一字形挂着多个现代字时属歧义，**不猜**。
    z_by_shape: dict[str, set[str]] = defaultdict(set)
    if args.zdic_shape_index:
        shape_path = args.zdic_shape_index.resolve()
        if not shape_path.is_file():
            raise SystemExit(
                f"路线 C 的字形键表读不出来：{shape_path}\n"
                "（路线 C 要用对方层的 index.csv——那是**入库后**才有的。"
                "先把漢典那批矢量件入库，再跑身份反查。）")
        for row in load_csv(shape_path):
            sid = (row.get("source_id") or "").strip()
            ch = (row.get("modern_char") or "").strip()
            if sid and ch:
                z_by_shape[sid].add(ch)

    # ---- 字頭級彙總：页.行集合、槽位、字形键、已知身份 ----
    head_pages: dict[int, set[str]] = {}
    head_slots: dict[int, set[str]] = defaultdict(set)
    head_shapes: dict[int, set[str]] = defaultdict(set)
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
        # 路线 C 的入口：这一条实例自己的字形键（字体号_码位）。
        font_id = inst.get("font_id")
        pua = inst.get("pua")
        if font_id and pua:
            head_shapes[zi].add("{}_{}".format(font_id, pua))
        ch = inst.get("modern_char") or ""
        if ch and not is_pua(ch):
            head_known[zi].add(ch)
        if zi not in head_pages:
            head_pages[zi] = base_pages_of(inst.get("base_pages", []), args.base_book)

    records: list[dict] = []
    stats = {"base-page": 0, "seal-slot": 0, "base-page+seal-slot": 0,
             "base-page∩seal-slot": 0, "shape-key": 0, "pua-slot": 0}
    verify = {"agree": 0, "disagree": 0, "no_candidate": 0, "multi": 0}
    route_verify: dict[str, dict] = {}
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

        # 路线 C
        cands_c: set[str] = set()
        for s in head_shapes.get(zi, set()):
            cands_c |= z_by_shape.get(s, set())

        char = ""
        confidence = ""
        evidence: dict = {"slot": sorted(slots), "base_pages": sorted(pages),
                           "shapes": sorted(head_shapes.get(zi, set()))}

        # 三条路线各给一组候选。**按 --prefer 定的顺序取第一个唯一命中的**——
        # 顺序由每层自己的实测定（--verify-known 量出一致率），不写死。
        cand_by_route = {"D": cands_d, "A": cands_a, "C": cands_c}
        for name in prefer:
            cands = cand_by_route.get(name, set())
            if len(cands) != 1:
                continue
            char = next(iter(cands))
            # 旁证一致时加强证据：另外两条路线也唯一命中同一个字。
            agree = sorted(n for n, cs in cand_by_route.items()
                           if n != name and len(cs) == 1 and cs == cands)
            if name == "D":
                if "A" in agree:
                    confidence = "base-page+seal-slot"
                else:
                    confidence = "base-page"
            elif name == "A":
                if "D" in agree:
                    confidence = "base-page+seal-slot"
                else:
                    confidence = "seal-slot"
            else:   # C
                confidence = "shape-key"
            evidence["route"] = name
            evidence["agree_routes"] = agree
            break
        else:
            # 没有任何一条路线唯一命中。若 D 多候选而 A 唯一命中且是 D 的子集，
            # 两条证据一致地指向同一个字——这在楚系层出现过。
            if len(cands_d) > 1 and len(cands_a) == 1 and cands_a <= cands_d:
                char = next(iter(cands_a))
                confidence = "base-page∩seal-slot"

        if char:
            stats[confidence] = stats.get(confidence, 0) + 1
        else:
            confidence = "pua-slot"
            stats["pua-slot"] += 1
            evidence["base_page_chars"] = sorted(cands_d)
            evidence["seal_slot_chars"] = sorted(cands_a)
            evidence["shape_chars"] = sorted(cands_c)

        if known and args.verify_known:
            # 自检：拿反查结论去对站点自己给的身份。
            #
            # **「不一致」不等于「反查错」**：傳抄层实测里，路线 D 的 3,430 次不一致
            # 全是簡繁對与異體（殺/杀、網/冈、響/响），路线 C 的 869 次全是形近異體
            # （禔/媞、珌/㻫、葉/枼）。那是「正字 + 異體字並存」的**层语义**——
            # 同一个字形，各底本各釋各的。所以这里把不一致**单列**，
            # 让人自己看，而不是混进一个「准确率」数字里。
            if not char:
                verify["no_candidate"] += 1
            elif len(cands_d) > 1:
                verify["multi"] += 1
            elif char in known:
                verify["agree"] += 1
            else:
                verify["disagree"] += 1
                mismatches.append((zi, sorted(known), char, confidence))
            # **逐路线量一致率**——这是每层定 --prefer 顺序的依据。
            # 只统计「该路线唯一命中」的字頭；多候选与无候选分列，不混进一致率。
            for name, cands in (("D", cands_d), ("A", cands_a), ("C", cands_c)):
                st = route_verify.setdefault(name, {"hit": 0, "agree": 0, "disagree": 0})
                if len(cands) != 1:
                    continue
                st["hit"] += 1
                c = next(iter(cands))
                if c in known:
                    st["agree"] += 1
                else:
                    st["disagree"] += 1
                    # 记下不一致的字對，供人工判断是異體还是真错。
                    st.setdefault("pairs", []).append((c, sorted(known)[0]))
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
        # 逐路线一致率：这是**给每层定 --prefer 顺序**的依据。
        # 哪条路线的一致率高就排前面——不凭印象排。
        if route_verify:
            print("\n  逐路线一致率（只算该路线唯一命中的字頭）：")
            for name in ("D", "A", "C"):
                st = route_verify.get(name)
                if not st or not st["hit"]:
                    continue
                rate = st["agree"] / st["hit"]
                print(f"    {name}: 命中 {st['hit']}，一致 {st['agree']}，"
                      f"不一致 {st['disagree']}，一致率 {rate:.2%}")
                # 不一致的字對列出来：**多半是異體對**（層語義），
                # 人工看一眼就知道有沒有真錯。
                pairs = st.get("pairs") or []
                if pairs:
                    uniq = sorted(set(pairs))
                    print(f"      不一致的字對（前 12，共 {len(uniq)} 種）："
                          + "、".join(f"{a}↔{b}" for a, b in uniq[:12]))
        for row in mismatches[:20]:
            print(f"    不一致：zi={row[0]} 站点={row[1]} 反查={row[2]!r} ({row[3]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
