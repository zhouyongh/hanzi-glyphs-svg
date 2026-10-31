# -*- coding: utf-8 -*-
"""**发布安全审计**：逐层统计「这一层能不能安全发布」，并把随附义务的履行情况机检一遍。

为什么要有这个脚本。仓库里有三类许可（CC BY 4.0 / CC0 1.0 / OFL 1.1）、
十二个书体层，发布前要回答的不是「这层是什么许可」，而是四件事：

1. **许可能不能覆盖本仓库的用法** —— 本仓库对上游素材做的是「改作」
   （字体取轮廓、汉典字形去水印、摹本转 SVG），改作是分水岭：
   ND 类许可直接禁止，NC 类与「公开供引用」的目的冲突，都不得入库。
2. **发布时必须随附什么** —— 署名文本、许可全文、改动说明、保留字体名限制。
3. **这些义务现在履行了没有** —— 这一项可以机检，本脚本就做这件事。
4. **还剩什么残余风险** —— 主要是汉典层的「摹本 + 矢量化」链条：
   汉典的 CC0 放弃的是汉典自己的权利，**不消灭底本出版物的著作权**。

用法：

    python src/license_audit.py                 # 生成 Markdown + JSON
    python src/license_audit.py --json-only     # 只出机读结果
    python src/license_audit.py --check         # 只机检，退出码非 0 表示有未履行的义务

输出：
- `glyphs/publish-license-audit.md`（人读）
- `glyphs/publish-license-audit.json`（机读）

**「可安全发布」的定义**：许可允许本仓库的用法、且该层的全部随附义务都已履行。
汉典层的摹本链条是**残余风险**（不是「不可发布」）：本仓库逐条如实标注了底本，
风险写在 `THIRD_PARTY_NOTICES.md`，由使用方自行判断。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GLYPHS = ROOT / "glyphs"
PROV_DIR = GLYPHS / "provenance"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"
REFERENCE = ROOT / "src" / "licenses" / "OFL-1.1-official.txt"
OUT_MD = GLYPHS / "publish-license-audit.md"
OUT_JSON = GLYPHS / "publish-license-audit.json"

sys.path.insert(0, str(ROOT / "src"))
from verify_font_licenses import compare, split_body, split_clauses  # noqa: E402

# ---------------------------------------------------------------- 许可能力矩阵
# 判定依据写在每条的 note 里，可回查许可原文。
LICENSE_RULES = {
    "CC-BY-4.0": {
        "label": "CC BY 4.0",
        "permits_derivative": True,
        "permits_redistribution": True,
        "requires_attribution": True,
        "requires_license_copy": True,
        "requires_indicate_changes": True,
        "requires_same_license": True,
        "obligations": [
            "署名：作者、来源、许可、**并说明是否修改过**（§3(a)(1)）",
            "衍生作品须以**同一许可**（CC BY 4.0）分发（§3(a)(5)(B)）",
            "不得施加额外限制（§2(a)(5)(B)）",
        ],
        "note": "允许改作与再分发；义务最重，但本仓库已逐条履行。",
    },
    "CC0-1.0": {
        "label": "CC0 1.0",
        "permits_derivative": True,
        "permits_redistribution": True,
        "requires_attribution": False,
        "requires_license_copy": False,
        "requires_indicate_changes": False,
        "requires_same_license": False,
        "obligations": [
            "无强制署名义务（CC0 放弃权利而非授予许可）",
            "**不得**因此追加使用限制（CC0 是放弃权利，不是许可别人加条件）",
        ],
        "note": "本仓库仍逐条标注了来源与底本——这既符合「如实写来源」，也让使用方能自行判断。",
    },
    "OFL-1.1": {
        "label": "SIL Open Font License 1.1",
        "permits_derivative": True,
        "permits_redistribution": True,
        "requires_attribution": True,
        "requires_license_copy": True,
        "requires_indicate_changes": True,
        "requires_same_license": True,
        "obligations": [
            "**每份副本**都要带版权声明与许可全文（第 2 条）",
            "衍生作品须以 OFL 分发，且**不得使用被保留的字体名**（第 3 条）",
            "不得单独销售字体软件本身（第 1 条）",
        ],
        "note": "整层以 OFL-1.1 分发；层名用通用书体名，字体家族名只出现在 attribution 与 index.csv。",
    },
}

# 层目录 → 书体中文名（表格用）
LAYER_TITLES = {
    "oracle": "甲骨文", "bronze": "金文", "seal": "篆书", "clerical": "隶书",
    "chu": "楚文字", "chuanchao": "傳抄古文",
    "qinwenzi": "秦系簡牘", "xiaozhuan": "小篆·小学堂",
    "kaishu": "楷书", "xingshu": "行书", "caoshu": "草书",
    "songti": "宋体·简", "songti-tc": "宋体·繁", "heiti-hk": "黑体·港",
}

# 层的展示顺序（古文字 → 现代书体）
LAYER_ORDER = ["oracle", "bronze", "seal", "clerical", "chu", "chuanchao",
                "qinwenzi", "xiaozhuan",
                "kaishu", "xingshu", "caoshu", "songti", "songti-tc", "heiti-hk"]

# 各层已知的上游结构性风险（人工判定，脚本只负责把数据统计出来）
LAYER_RISK_NOTE = {
    "oracle": "两批两许可：JGW 批次（CC BY 4.0，骨架逐字节副本）+ 汉典拓片摹本批次"
              "（CC0 1.0）。汉典批次是**摹本**，《甲骨文合集》的底本著作权不消灭。",
    "bronze": "汉典「书法」字形是**摹本 + 矢量化**产物，底本为《殷周金文集成》等出版物。",
    "clerical": "同上，底本为《睡虎地秦简文字编》《秦汉魏晋篆隶字形表》等。",
    "seal": "同上，底本为《秦汉魏晋篆隶字形表》等。另有「開元小篆」上游只登记指针、不复制字形。",
    "chu": "链条**多一层**：原简帛 → 考古整理本 → 《楚系简帛文字编》摹本 → 汉典转录；"
           "逐字形的摹本底本与页.行记在 `source_references`。"
           "另有**小学堂批次**（中研院數位文化中心，CC0 1.0）：同为《楚系簡帛文字編》"
           "摹本的字形圖片，本地 SVG 是**位图自动描摹**的派生件，改动与工具记在 "
           "`modifications` / `transform`；底本链条与漢典批次相同。",
    "chuanchao": "底本是徐在國《傳抄古文字編》（綫裝書局，2006），逐条记在 `source_references`。"
                 "改以**小学堂**傳抄古文字資料庫为主源后，本地 SVG 是**位图自动描摹**的派生件，"
                 "底本链条不变。",
    "qinwenzi": "**小学堂批次**（中研院數位文化中心，CC0 1.0）：上游原件是位图，"
                "本地 SVG 是**位图自动描摹**的派生件（改动与工具记在 `modifications` / `transform`，"
                "保真指标记在 `trace_iou`）。底本是《睡虎地秦簡文字編》等出版物，"
                "**摹本底本的著作权不因 CC0 而消灭**。",
    "xiaozhuan": "**小学堂批次**（中研院數位文化中心，CC0 1.0）：上游原件是位图，"
                 "本地 SVG 是**位图自动描摹**的派生件（改动与工具记在 `modifications` / `transform`，"
                 "保真指标记在 `trace_iou`）。底本为《說文解字》等出版物，"
                 "**底本著作权不因 CC0 而消灭**；与 `seal/`（漢典《說文》系）不是同一批材料。",
    "kaishu": "OFL 派生件（字体轮廓 → SVG），改动已声明；无底本链条。",
    "xingshu": "OFL 派生件（字体轮廓 → SVG），改动已声明；无底本链条。",
    "caoshu": "OFL 派生件（字体轮廓 → SVG），改动已声明；无底本链条。",
    "songti": "OFL 派生件（字体轮廓 → SVG），改动已声明；无底本链条。",
    "songti-tc": "OFL 派生件（字体轮廓 → SVG），改动已声明；无底本链条。",
    "heiti-hk": "OFL 派生件（字体轮廓 → SVG），改动已声明；**港版字形标准**不是大陆写法。",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_body(text: str) -> str:
    """归一化许可正文：只保留条款文字，删掉排版分隔线、折叠空白。

    与 `verify_font_licenses.py` 的判定口径一致——**条款文字**说了算，
    原始排版只报不判（有些上游把 OFL 转成 Markdown，条款逐字相同但排版不同）。
    """
    keep = []
    for line in text.splitlines():
        s = line.strip()
        if s and set(s) <= set("-=") and len(s) >= 3:
            continue
        if s:
            keep.append(s)
    return "\n".join(keep)


def collect() -> dict:
    """扫一遍 `glyphs/provenance/*.jsonl`，按书体层统计许可相关的事实。"""
    by_layer = defaultdict(list)
    for prov_path in sorted(PROV_DIR.glob("*.jsonl")):
        with prov_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                by_layer[rec.get("script", "?")].append(rec)

    notices = NOTICES.read_text(encoding="utf-8") if NOTICES.is_file() else ""
    layers = {}
    for name, recs in by_layer.items():
        lic = Counter(r.get("license", "") for r in recs)
        attr_missing = sum(1 for r in recs if not (r.get("attribution") or "").strip())
        # 改动声明：**骨架层记在 `modifications`，派生层记在 `transform`**
        # （甲骨轮廓层是派生件，它的改动是「骨架 → 轮廓」，没有 modifications 字段）。
        mod_missing = sum(1 for r in recs
                          if not (r.get("modifications") or "").strip()
                          and not (r.get("transform") or "").strip())
        mod_kinds = Counter()
        for r in recs:
            m = (r.get("modifications") or "").strip()
            t = (r.get("transform") or "").strip()
            if m.startswith("removed"):
                mod_kinds["删除汉典近白水印"] += 1
            elif m.startswith("font-outline-to-svg"):
                mod_kinds["字体轮廓 → SVG"] += 1
            elif m.startswith("none"):
                mod_kinds["未改动（逐字节副本）"] += 1
            elif t:
                mod_kinds["骨架 → 可填充轮廓（派生层）"] += 1
            else:
                mod_kinds[m[:40] or "(空)"] += 1
        # 底本链条
        books = Counter((r.get("source_book") or "").strip() for r in recs
                        if (r.get("source_book") or "").strip())
        refs = sum(1 for r in recs if (r.get("source_references") or "").strip())
        # 每层的目录与许可文件
        d = GLYPHS / name
        ofl = d / "OFL.txt"
        layers[name] = {
            "records": len(recs),
            "licenses": dict(lic),
            "attribution_missing": attr_missing,
            "attribution_variants": len({(r.get("attribution") or "") for r in recs}),
            "modifications_missing": mod_missing,
            "modification_kinds": dict(mod_kinds),
            "source_book_records": sum(books.values()),
            "source_books_top": books.most_common(6),
            "source_references_records": refs,
            "has_license_copy": ofl.is_file(),
            "license_copy_path": str(ofl.relative_to(ROOT)) if ofl.is_file() else "",
            "license_copy_sha256": sha256_file(ofl) if ofl.is_file() else "",
            "has_source_md": (d / "SOURCE.md").is_file(),
            "has_readme": (d / "README.md").is_file(),
            "notices_mentions_layer": f"glyphs/{name}/" in notices,
            "risk_note": LAYER_RISK_NOTE.get(name, ""),
        }
    return layers


def ofl_body_check(layers: dict) -> dict:
    """OFL 层：许可全文副本的正文是否与 SIL 官方原文逐条款相同。

    判定口径与 `verify_font_licenses.py` 一致：**条款文字**（`min_similarity_typographic`）
    说了算，原始排版相似度只报不判。
    """
    out = {}
    if not REFERENCE.is_file():
        return out
    ref_text = REFERENCE.read_text(encoding="utf-8")
    _ref_head, ref_body = split_body(ref_text)
    for name, info in layers.items():
        if not info["has_license_copy"]:
            continue
        p = ROOT / info["license_copy_path"]
        text = p.read_text(encoding="utf-8", errors="replace")
        _head, body = split_body(text)
        c = compare(ref_body, body)
        out[name] = {
            "min_similarity": c.get("min_similarity", 0.0),
            "min_similarity_typographic": c.get("min_similarity_typographic", 0.0),
            "clause_count_official": len(split_clauses(ref_body)),
            "clause_count_layer": len(split_clauses(body)),
            "body_sha256": hashlib.sha256(normalize_body(ref_body).encode()).hexdigest(),
            "layer_body_sha256": hashlib.sha256(normalize_body(body).encode()).hexdigest(),
        }
    return out


def verdict(name: str, info: dict, ofl: dict) -> tuple[str, list[str]]:
    """给出发布结论与「必须随附的东西」清单。"""
    problems = []
    must = []
    for lic, n in info["licenses"].items():
        rule = LICENSE_RULES.get(lic)
        if rule is None:
            problems.append(f"未知许可 `{lic}`（{n} 条）")
            continue
        if not rule["permits_derivative"]:
            problems.append(f"许可 `{lic}` 不允许改作")
        if not rule["permits_redistribution"]:
            problems.append(f"许可 `{lic}` 不允许再分发")
        must.extend(rule["obligations"])
    if info["attribution_missing"]:
        problems.append(f"{info['attribution_missing']} 条缺 attribution")
    if info["modifications_missing"]:
        problems.append(f"{info['modifications_missing']} 条缺 modifications（改动说明）")
    if any(l.startswith("OFL") for l in info["licenses"]):
        if not info["has_license_copy"]:
            problems.append("缺上游许可全文副本（OFL 第 2 条）")
        else:
            c = ofl.get(name)
            if c and c["min_similarity_typographic"] < 1.0:
                problems.append(f"OFL 正文与官方原文条款相似度 {c['min_similarity_typographic']:.4f}（非逐条款相同）")
    if not info["notices_mentions_layer"]:
        problems.append("THIRD_PARTY_NOTICES.md 里找不到该层的署名段")
    if problems:
        return "❌ 有未履行的义务", sorted(set(must))
    if info["source_book_records"]:
        return "⚠️ 可发布（有残余风险，须随附底本说明）", sorted(set(must))
    return "✅ 可安全发布", sorted(set(must))


def build_markdown(layers: dict, ofl: dict) -> str:
    ts = "生成物：由 `python src/license_audit.py` 生成，勿手改。"
    out = [
        "# 发布安全审计：逐层统计「能不能安全发布」",
        "",
        f"> {ts}",
        "",
        "## 结论先行",
        "",
    ]
    verdicts = {n: verdict(n, i, ofl)[0] for n, i in layers.items()}
    ok = sum(1 for v in verdicts.values() if v.startswith("✅"))
    warn = sum(1 for v in verdicts.values() if v.startswith("⚠️"))
    bad = sum(1 for v in verdicts.values() if v.startswith("❌"))
    total = sum(i["records"] for i in layers.values())
    out.append(f"- **{ok}** 层可安全发布，**{warn}** 层可发布但有残余风险，**{bad}** 层有未履行的义务。")
    out.append(f"- 覆盖 **{total:,}** 条出处记录，全部来自三类许可：**CC BY 4.0**（甲骨 JGW 批）、"
               f"**CC0 1.0**（汉典五层 + 甲骨汉典批）、**SIL OFL 1.1**（现代书体六层）。")
    out.append("- 三类许可**都允许改作与再分发**——这是能入库的前提；"
               "被排除的是 CC BY-ND（禁止改作）、CC BY-NC（与「公开供引用」冲突）与无许可来源。")
    out.append("- **本仓库不做的事**：不售卖任何东西（OFL 第 1 条要求「不得单独销售字体软件」），"
               "不给下游附加任何使用限制（CC BY 4.0 §2(a)(5)(B)、CC0 均不允许）。")
    out.append("")

    out.append("## 逐层一览")
    out.append("")
    out.append("| 书体 | 层目录 | 记录数 | 许可（条数） | 许可能否改作 | 署名义务 | 随附许可全文 | "
               "署名已备 | 改动已声明 | 底本链条 | **发布结论** |")
    out.append("|---|---|---:|---|:--:|:--:|---|:--:|:--:|---:|---|")
    for name in LAYER_ORDER:
        if name not in layers:
            continue
        i = layers[name]
        lic = " + ".join(f"{k}（{v:,}）" for k, v in sorted(i["licenses"].items()))
        rule = next((LICENSE_RULES[k] for k in i["licenses"] if k in LICENSE_RULES), None)
        deriv = "是" if rule and rule["permits_derivative"] else "否"
        if rule and rule["requires_attribution"]:
            attr_col = "是"
        else:
            attr_col = "否（非强制）"
        # 随附的许可全文在哪：OFL 层在层目录；CC BY 4.0 是根 LICENSE；CC0 见 LICENSE-DATA
        if any(k.startswith("OFL") for k in i["licenses"]):
            lic_copy = "层内 `OFL.txt`" if i["has_license_copy"] else "**缺**"
        elif "CC-BY-4.0" in i["licenses"]:
            lic_copy = "根 `LICENSE`"
        else:
            lic_copy = "`LICENSE-DATA`"
        # 署名已备：每条记录都有 attribution，且 THIRD_PARTY_NOTICES 里有该层署名段
        attr_ok = "是" if (i["attribution_missing"] == 0 and i["notices_mentions_layer"]) else "**缺**"
        # 改动已声明：只要有任一「有改动」的类型就算已声明
        changed = "是" if any(k != "未改动（逐字节副本）" for k in i["modification_kinds"]) else "无改动"
        chain = f"{i['source_book_records']:,}" if i["source_book_records"] else "无"
        out.append(f"| {LAYER_TITLES.get(name, name)} | `glyphs/{name}/` | {i['records']:,} | {lic} | "
                   f"{deriv} | {attr_col} | {lic_copy} | {attr_ok} | {changed} | {chain} | "
                   f"**{verdicts[name]}** |")
    out.append("")

    out.append("## 各类许可的随附义务与履行情况")
    out.append("")
    for lic in ("CC-BY-4.0", "CC0-1.0", "OFL-1.1"):
        rule = LICENSE_RULES[lic]
        # 条数按**该许可实际覆盖的记录数**算，不是按层的总记录数
        n = sum(i["licenses"].get(lic, 0) for i in layers.values())
        out.append(f"### {rule['label']}（{n:,} 条记录）")
        out.append("")
        out.append("**发布时必须随附：**")
        out.append("")
        for o in rule["obligations"]:
            out.append(f"- {o}")
        out.append("")
        out.append(f"**本仓库怎么做：** {rule['note']}")
        out.append("")

    # 层数按实际统计，别写死——加一层就多一层，写死的数字会变成假话。
    _chain_layers = [n for n in LAYER_ORDER
                     if n in layers and layers[n].get("source_book_records")]
    out.append(f"## 残余风险：汉典{len(_chain_layers)}层的「摹本 + 矢量化」链条")
    out.append("")
    out.append("汉典的 CC0 1.0 宣告放弃的是**汉典自己**的权利，"
               "**不消灭底本出版物的著作权**。本仓库的做法与甲骨层一致："
               "接受并**逐条如实标注**这条链条，风险写在 `THIRD_PARTY_NOTICES.md`，由使用方自行判断。")
    out.append("")
    out.append("| 层 | 带底本记载的记录 | 逐字形底本与页.行 | 主要底本（按记录数） |")
    out.append("|---|---:|---:|---|")
    for name in LAYER_ORDER:
        if name not in layers:
            continue
        i = layers[name]
        if not i["source_book_records"]:
            continue
        books = "；".join(f"{b}（{n:,}）" for b, n in i["source_books_top"][:3]) or "—"
        refs = f"{i['source_references_records']:,}" if i["source_references_records"] else "—"
        out.append(f"| {LAYER_TITLES.get(name, name)} | {i['source_book_records']:,} | {refs} | {books} |")
    out.append("")

    out.append("## 本仓库做了哪些改动（许可能求声明）")
    out.append("")
    out.append("| 改动类型 | 记录数 | 涉及层 |")
    out.append("|---|---:|---|")
    kinds = defaultdict(lambda: defaultdict(int))
    for name, i in layers.items():
        for k, n in i["modification_kinds"].items():
            kinds[k][name] = n
    for k, per in sorted(kinds.items(), key=lambda x: -sum(x[1].values())):
        who = "、".join(f"{LAYER_TITLES.get(n, n)}（{v:,}）" for n, v in sorted(per.items()))
        out.append(f"| {k} | {sum(per.values()):,} | {who} |")
    out.append("")

    out.append("## 怎么复核")
    out.append("")
    out.append("| 要查什么 | 怎么查 |")
    out.append("|---|---|")
    out.append("| 本文件的数据 | `python src/license_audit.py` |")
    out.append("| 某一层的许可正文是不是官方原文 | "
               "`python src/verify_font_licenses.py --license-dir glyphs/<层> --markdown` |")
    out.append("| 字体本体有没有 RFN | 同上，加 `--font <字体路径>`（只看 `OFL.txt` 会漏判） |")
    out.append("| 逐条款证据（六层） | `glyphs/font-license-evidence.md` |")
    out.append("| 署名与改动声明的正文 | `THIRD_PARTY_NOTICES.md` |")
    out.append("| 出处记录逐条 | `glyphs/provenance/<书体>.jsonl` |")
    out.append("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="发布安全审计：逐层统计能不能安全发布")
    ap.add_argument("--json-only", action="store_true", help="只出机读结果")
    ap.add_argument("--check", action="store_true", help="只机检；有未履行的义务时退出码非 0")
    ap.add_argument("--out", type=Path, default=OUT_MD)
    args = ap.parse_args(argv)

    layers = collect()
    ofl = ofl_body_check(layers)
    result = {"layers": {}, "generated_by": "src/license_audit.py"}
    failures = []
    for name, info in layers.items():
        v, must = verdict(name, info, ofl)
        result["layers"][name] = dict(info, verdict=v, must_include=must, ofl=ofl.get(name, {}))
        if v.startswith("❌"):
            failures.append(name)

    if args.json_only or args.check:
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    if not args.json_only and not args.check:
        OUT_MD.write_text(build_markdown(layers, ofl), encoding="utf-8")
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"-> {OUT_MD.relative_to(ROOT)}")
        print(f"-> {OUT_JSON.relative_to(ROOT)}")

    for name in LAYER_ORDER:
        if name in result["layers"]:
            r = result["layers"][name]
            print(f"  {LAYER_TITLES.get(name, name):<8} {r['verdict']}")
    if failures:
        print(f"\n有未履行的义务：{', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
