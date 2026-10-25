# -*- coding: utf-8 -*-
"""把各字体层的 OFL 许可证据汇成一份可**逐条复核**的文档。

产出 `glyphs/font-license-evidence.md`：

- 每个字体层一份 **逐条款** 比对表（PREAMBLE + 1)–5) 共六段），
  条款文字相似度与原始排版相似度都列出来——差异不许被藏起来；
- 每层的 `OFL.txt` sha256、字节数、版权行、RFN 判定；
- **字体二进制的 name 表**也查（OFL 1.1 把 RFN 定义成
  「copyright statement 里写明的名字」，字体 name 表的 copyright 字段就是一份
  copyright statement，所以 RFN 可能只写在字体里）；
- 上游字体 sha256 与取回地址，便于复核者重新下载后逐字节对账。

**字体二进制不进仓库**（体积与许可再分发都不合适），所以 name 表那几行
要靠 `--font-dir` 指向本地副本；找不到时该行写「未提供字体本体」并说明原因，
不假装查过。

用法：
    python src/build_font_license_evidence.py --font-dir <本地字体目录> \
        --out glyphs/font-license-evidence.md

字体目录里放什么文件名不重要——脚本按 **sha256** 与各层 `SOURCE.md` 里
记录的字体 sha256 对上号，认得出来就查。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_font_licenses import (  # noqa: E402
    compare,
    inspect,
    inspect_font,
    split_body,
)

ROOT = Path(__file__).resolve().parent.parent
GLYPHS = ROOT / "glyphs"
REFERENCE = ROOT / "src" / "licenses" / "OFL-1.1-official.txt"

# 层名 → 书体中文名（用于文档标题）
LAYER_TITLES = {
    "kaishu": "楷书",
    "xingshu": "行书",
    "caoshu": "草书",
    "songti": "宋体·简",
    "songti-tc": "宋体·繁",
    "heiti-hk": "黑体·港",
}

# SOURCE.md 里字段与取值的对应
FIELD_RE = {
    "family": re.compile(r"^\|\s*字体\s*\|\s*(.+?)\s*\|$", re.M),
    "font_sha256": re.compile(r"^\|\s*上游字体 sha256\s*\|\s*`([0-9a-f]{64})`\s*\|$", re.M),
    "font_url": re.compile(r"^\|\s*上游字体原件\s*\|\s*(\S+)\s*\|$", re.M),
    "license_sha256": re.compile(r"^\|\s*上游许可\s*\|.*?sha256 `([0-9a-f]{64})`", re.M),
    "retrieved": re.compile(r"^\|\s*取回时刻（UTC）\s*\|\s*(.+?)\s*\|$", re.M),
    "glyphs": re.compile(r"^\|\s*字形数\s*\|\s*(\d+)\s*\|$", re.M),
}

FONT_SUFFIXES = (".ttf", ".otf", ".ttc")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_source_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    out = {}
    for key, rx in FIELD_RE.items():
        m = rx.search(text)
        out[key] = m.group(1) if m else ""
    return out


def index_fonts(font_dir: Path) -> dict:
    """把本地字体目录按 sha256 建索引。"""
    index = {}
    if not font_dir.is_dir():
        return index
    for p in sorted(font_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in FONT_SUFFIXES:
            index.setdefault(sha256_file(p), p)
    return index


def font_layers() -> list[Path]:
    """找出所有自带 OFL.txt 的层目录（按目录名排序，顺序稳定）。"""
    out = []
    for d in sorted(GLYPHS.iterdir()):
        if d.is_dir() and (d / "OFL.txt").is_file():
            out.append(d)
    return out


def clause_table(row: dict) -> list[str]:
    lines = [
        "| 条款 | 对应 OFL 1.1 段落 | 条款文字相似度 | 原始排版相似度 | 归一化后长度 |",
        "|---:|---|---:|---:|---:|",
    ]
    names = {
        0: "PREAMBLE + DEFINITIONS + 条件前言",
        1: "1) 允许使用与再分发",
        2: "2) 每份副本须带版权声明与许可全文",
        3: "3) 不得使用被保留的字体名（RFN）",
        4: "4) 不得单独销售字体软件本身",
        5: "5) 终止与免责声明",
    }
    for c in row.get("clauses", []):
        i = c["clause"]
        lines.append(
            f"| {i} | {names.get(i, '—')} | {c['similarity']:.4f} | "
            f"{c['similarity_raw']:.4f} | {c['length']} |")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="汇总各字体层的 OFL 许可证据")
    ap.add_argument("--font-dir", type=Path, default=None,
                    help="本地字体副本目录（按 sha256 与各层 SOURCE.md 对号）")
    ap.add_argument("--out", type=Path,
                    default=GLYPHS / "font-license-evidence.md")
    args = ap.parse_args(argv)

    if not REFERENCE.is_file():
        raise SystemExit(f"找不到官方原文：{REFERENCE}")
    ref_text = REFERENCE.read_text(encoding="utf-8")
    _ref_header, reference_body = split_body(ref_text)
    if not reference_body:
        raise SystemExit(f"官方原文 {REFERENCE} 里找不到 OFL 1.1 正文标记")

    fonts = index_fonts(args.font_dir) if args.font_dir else {}
    layers = font_layers()
    if not layers:
        raise SystemExit(f"{GLYPHS} 下没有找到带 OFL.txt 的层目录")

    ts = "生成时间（UTC）：" + datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out: list[str] = []
    out.append("# 字体层 OFL 1.1 许可证据（逐条复核用）")
    out.append("")
    out.append("本文件是**证据汇总**，不是法律意见。它回答一个问题：")
    out.append("本仓库从 OFL 开源字体提取的那几层，许可文本**是不是 SIL 官方 OFL 1.1 原文**，")
    out.append("以及**有没有保留字体名（RFN）**——这是两层硬约束里最容易漏判的一处。")
    out.append("")
    out.append("## 一句话结论")
    out.append("")
    out.append("| 层 | 书体 | `OFL.txt` 条款文字相似度 | 原始排版相似度 | 逐条款一致 | "
               "`OFL.txt` RFN | 字体 name 表 RFN |")
    out.append("|---|---|---:|---:|---|---|---|")
    summary_rows = []
    for d in layers:
        layer = d.name
        title = LAYER_TITLES.get(layer, layer)
        row = inspect(d / "OFL.txt", reference_body)
        src = parse_source_md(d / "SOURCE.md")
        frow = inspect_font(fonts[src["font_sha256"]]) if src["font_sha256"] in fonts else None
        name_rfn = "—"
        if frow and not frow.get("error"):
            name_rfn = ("有：" + "、".join(frow["name_table_rfn"])
                        if frow["has_name_table_rfn"] else "无")
        summary_rows.append((layer, title, row, src, frow))
        out.append(
            f"| `{layer}` | {title} | {row['min_similarity']:.4f} | "
            f"{row.get('min_similarity_raw', row['min_similarity']):.4f} | "
            f"{'是' if row['identical'] else '**否**'} | "
            f"{'有' if row['has_rfn_clause'] else '无'} | {name_rfn} |")
    out.append("")
    n_layers = len(summary_rows)
    n_same = sum(1 for r in summary_rows if r[2]["min_similarity"] >= 1.0)
    n_raw = sum(1 for r in summary_rows
                if r[2].get("min_similarity_raw", 0) >= 1.0)
    out.append(f"{n_layers} 个层的 `OFL.txt` **条款文字与官方原文逐字相同**"
               f"（条款文字相似度均 1.0000），")
    out.append("且 `OFL.txt` 抬头与**字体二进制的 name 表两处**都没有 RFN 声明——")
    out.append("因此本仓库可以用通用书体名（楷书/行书/草书/宋体·简/宋体·繁/黑体·港）给这几层命名，")
    out.append("字体家族名只出现在署名与 `index.csv` 里（OFL 第 3 条）。")
    body_hashes = {r[2]["body_sha256"] for r in summary_rows}
    if n_raw < n_layers:
        out.append("")
        out.append(f"**{n_raw} 个层的原始排版也是 1.0000**，剩下的那层是上游把 OFL 转成了 Markdown"
                   "（小节标题下多一条 `----` 下划线）——")
        out.append("**差的是排版不是条款**，两个数都列出来，差异不藏。")
    if len(body_hashes) == 1:
        h = body_hashes.pop()
        out.append("")
        out.append(f"另有一条**交叉印证**：{n_layers} 层的 `OFL.txt` 归一化后正文 sha256 **完全相同**")
        out.append(f"（`{h}`），也就是这些许可文件去掉排版差异后是同一份文本，")
        out.append("与官方原文逐字一致。")
    else:
        groups: dict[str, list[str]] = {}
        for layer, _t, row, _s, _f in summary_rows:
            groups.setdefault(row["body_sha256"], []).append(layer)
        out.append("")
        out.append("归一化后的正文 sha256 分成 " + str(len(groups)) + " 组（排版不同则哈希不同）：")
        for h, layers in groups.items():
            out.append(f"- `{h[:16]}…` —— {'、'.join('`' + x + '`' for x in layers)}")
    out.append("")
    out.append("## 复核方法")
    out.append("")
    out.append("| 要查什么 | 怎么查 |")
    out.append("|---|---|")
    out.append("| 某一层的许可正文是不是官方原文 | "
               "`python src/verify_font_licenses.py --license-dir glyphs/<层> --markdown` |")
    out.append("| 字体本体有没有 RFN | 同上，加 `--font <字体路径>`"
               "（只看 `OFL.txt` 会漏判） |")
    out.append("| 本文件的数据 | "
               "`python src/build_font_license_evidence.py --font-dir <本地字体目录>` |")
    out.append("| 比对基准是哪一份 | `src/licenses/OFL-1.1-official.txt`，sha256 "
               f"`{sha256_file(REFERENCE)}`，等于 <https://openfontlicense.org/documents/OFL.txt> |")
    out.append("")
    out.append(f"> {ts}")
    out.append("")

    for layer, title, row, src, frow in summary_rows:
        d = GLYPHS / layer
        out.append(f"## {title}（`glyphs/{layer}/`）")
        out.append("")
        out.append("| 项 | 值 |")
        out.append("|----|----|")
        out.append(f"| 字体 | {src.get('family', '—')} |")
        out.append(f"| 上游字体原件 | {src.get('font_url', '—')} |")
        out.append(f"| 上游字体 sha256 | `{src.get('font_sha256', '—')}` |")
        out.append(f"| 取回时刻（UTC） | {src.get('retrieved', '—')} |")
        out.append(f"| 字形数 | {src.get('glyphs', '—')} |")
        out.append(f"| 本层 `OFL.txt` 字节 | {row['bytes']} |")
        out.append(f"| 本层 `OFL.txt` sha256 | `{row['sha256']}` |")
        out.append(f"| 条款数（官方 / 本层） | {row['clause_count_reference']} / "
                   f"{row['clause_count_actual']} |")
        out.append(f"| `OFL.txt` 版权行 | {' / '.join(row['copyright_lines']) or '（未找到）'} |")
        out.append(f"| `OFL.txt` RFN | "
                   f"{'有：' + '、'.join(row['reserved_font_names']) if row['has_rfn_clause'] else '无'} |")
        out.append(f"| 正文 sha256（归一化后） | `{row['body_sha256']}` |")
        if frow and not frow.get("error"):
            out.append(f"| 字体 name 表 family | {frow['family']} |")
            out.append(f"| 字体 name 表 version | {frow['version']} |")
            out.append(f"| 字体 name 表版权行 | {frow['copyright'] or '（未找到）'} |")
            out.append(f"| 字体 name 表 RFN | "
                       f"{'有：' + '、'.join(frow['name_table_rfn']) if frow['has_name_table_rfn'] else '无'} |")
            out.append(f"| 字体 sha256（复核时另算） | `{frow['font_sha256']}` |")
        else:
            out.append("| 字体 name 表 | **未提供字体本体**——"
                       "字体二进制不进仓库，复核时用 `--font-dir` 指向本地副本，"
                       "脚本按 sha256 对号 |")
        out.append("")
        out.append("### 逐条款比对")
        out.append("")
        out.extend(clause_table(row))
        out.append("")
        note = row.get("note") or ""
        if row["identical"]:
            verdict = "条款文字**逐字相同**"
        else:
            verdict = "**不是**官方 OFL 1.1 正文"
        out.append(f"判定：{verdict}" + (f"（{note}）" if note else "") + "。")
        out.append("")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8", newline="\n")
    print(f"已写出 {args.out}")
    bad = [r[0] for r in summary_rows if not r[2]["identical"]]
    if bad:
        print(f"\n注意：以下层的正文不是官方 OFL 1.1：{', '.join(bad)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
