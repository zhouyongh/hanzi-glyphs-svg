#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小学堂批次的**全流程驱动器**：位图 → 描摹 → 清单 → 合并 → 入库 → 校验。

用法::

    python src/run_xxt_pipeline.py --db chuwenzi --stage all
    python src/run_xxt_pipeline.py --db chuwenzi --stage trace
    python src/run_xxt_pipeline.py --db chuwenzi --stage import --yes

**为什么要有这个脚本。** 全量抓取是几十小时的活，每一步手工敲命令会漏、
会错、也跑不完。这脚本把一条链固定下来，任何一步失败就**停在那一步**
（不往下走），并把每一步的用时与产出打印出来。

各库的配置在 ``DBS`` 里：

=================  =====================  ============================
库                 层名                   合并用的漢典清单
=================  =====================  ============================
chuwenzi           chu                    tmp/zdic/chu-merged/…
qinwenzi           qinwenzi               （无：本来就没有这一层）
chuanchao          chuanchao              （无）
xiaozhuan          xiaozhuan              （无：与 seal/ 不是同一批）
=================  =====================  ============================

**合并时「漢典矢量优先」**：合并器对同一键的两条记录按 ``layer`` 判——
``skeleton``（漢典矢量）優先于 ``outline``（小學堂描摹），并在清单的
``merge_conflicts`` 里留痕。層的归属闸门用层自己的 ``books.csv``。

**identity 阶段**：小学堂有些字頭的「楷書字頭」只是**字体排版槽位**（私用区），
不是 Unicode 汉字码位。这个阶段用 ``resolve_pua_identity.py`` 反查补回真身份
（底本页.行为主、說文小篆槽位为辅），清单阶段据此给出真汉字码位；
反查不出来才走**临时身份**并标记。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

DBS = {
    "chuwenzi": {
        "layer": "chu",
        "zdic_manifest": ROOT / "tmp" / "zdic" / "chu-merged" / "manifest.json",
        "books": ROOT / "glyphs" / "chu" / "books.csv",
        "books_xxt": ROOT / "glyphs" / "chu" / "books_xxt.csv",
        # 身份反查：路線 D（底本頁.行）要對方层的 provenance 裡有 source_base_pages
        "zdic_provenance": ROOT / "glyphs" / "provenance" / "chu.jsonl",
        "base_book": "楚系簡帛文字編",
    },
    "qinwenzi": {
        "layer": "qinwenzi",
        "zdic_manifest": None,
        "books": ROOT / "glyphs" / "qinwenzi" / "books.csv",
        "books_xxt": ROOT / "glyphs" / "qinwenzi" / "books_xxt.csv",
        # 漢典的秦系那批還在未發布清單裡，沒有可對的 provenance → 只走槽位旁證
        "zdic_provenance": None,
        "base_book": "",
    },
    "chuanchao": {
        "layer": "chuanchao",
        "zdic_manifest": None,
        "books": ROOT / "glyphs" / "chuanchao" / "books.csv",
        "books_xxt": ROOT / "glyphs" / "chuanchao" / "books_xxt.csv",
        "zdic_provenance": None,
        "base_book": "",
    },
    "xiaozhuan": {
        "layer": "xiaozhuan",
        "zdic_manifest": None,
        "books": ROOT / "glyphs" / "xiaozhuan" / "books.csv",
        "books_xxt": ROOT / "glyphs" / "xiaozhuan" / "books_xxt.csv",
        "zdic_provenance": None,
        "base_book": "",
    },
    # 增量入库的三层：旧记录要一起重排（条目号是整层内容的函数），
    # 所以合并时要拼上**重建出来的**漢典清单——
    # src/rebuild_layer_manifest.py 从层里的 index.csv + provenance 重来，
    # 不用把十几万个上游 SVG 再抓一遍。
    "jiaguwen": {
        "layer": "oracle",
        "zdic_manifest": ROOT / "tmp" / "zdic" / "oracle-rebuilt" / "manifest.json",
        "books": ROOT / "glyphs" / "oracle" / "books.csv",
        "books_xxt": ROOT / "glyphs" / "oracle" / "books_xxt.csv",
        "zdic_provenance": None,
        "base_book": "",
        "zdic_index": ROOT / "glyphs" / "oracle" / "index.csv",
    },
    "jinwen": {
        "layer": "bronze",
        "zdic_manifest": ROOT / "tmp" / "zdic" / "bronze-rebuilt" / "manifest.json",
        "books": ROOT / "glyphs" / "bronze" / "books.csv",
        "books_xxt": ROOT / "glyphs" / "bronze" / "books_xxt.csv",
        "zdic_provenance": None,
        "base_book": "",
        "zdic_index": ROOT / "glyphs" / "bronze" / "index.csv",
    },
    # **隸變庫同時喂兩层**：字體就是書體的判据——
    # 「中研院隸書重文」是隸書字形（隶书层），
    # 「中研院秦系簡牘文字重文」是**秦系字形**（秦系层，不是隶书层）。
    "lishu": {
        "layer": "clerical",
        "zdic_manifest": ROOT / "tmp" / "zdic" / "clerical-rebuilt" / "manifest.json",
        "books": ROOT / "glyphs" / "clerical" / "books.csv",
        "books_xxt": ROOT / "glyphs" / "clerical" / "books_xxt.csv",
        "zdic_provenance": None,
        "base_book": "",
        "targets": [
            {"layer": "clerical", "font_allow": "中研院隸書",
             "books": ROOT / "glyphs" / "clerical" / "books.csv",
             "books_xxt": ROOT / "glyphs" / "clerical" / "books_xxt.csv",
             "zdic_index": ROOT / "glyphs" / "clerical" / "index.csv",
             "zdic_manifest": ROOT / "tmp" / "zdic" / "clerical-rebuilt" / "manifest.json"},
            {"layer": "qinwenzi", "font_allow": "中研院秦系簡牘",
             "books": ROOT / "glyphs" / "qinwenzi" / "books.csv",
             "books_xxt": ROOT / "glyphs" / "qinwenzi" / "books.csv",
             "zdic_index": None,
             "zdic_manifest": None},
        ],
    },
}

STAGES = ("images", "trace", "identity", "manifest", "merge", "import", "verify")


def books_xxt_of(cfg: dict) -> Path:
    """出處表登记表的路径。

    楚系层有专门的 ``books_xxt.csv``（小學堂出處表 + 派生行）；
    新层（傳抄 / 秦系 / 小篆）**只有層自己的 books.csv**——
    那一张表就能兼当出處表用（``load_books_xxt`` 两种列名都认），不必再抄一份。
    """
    path = cfg.get("books_xxt")
    if path and Path(path).is_file():
        return Path(path)
    return Path(cfg["books"])


def run(label: str, args: list[str], *, allow_fail: bool = False) -> int:
    print("\n=== {} ===".format(label))
    print(" ".join(str(a) for a in args))
    t0 = time.time()
    proc = subprocess.run([str(a) for a in args], cwd=str(ROOT))
    dt = time.time() - t0
    print("--- {} 用时 {:.1f}s，返回码 {}".format(label, dt, proc.returncode))
    if proc.returncode != 0 and not allow_fail:
        raise SystemExit("{} 失败（返回码 {}）；后续步骤不执行".format(label, proc.returncode))
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="小学堂批次的全流程驱动器")
    ap.add_argument("--db", required=True, choices=sorted(DBS))
    ap.add_argument("--stage", default="all",
                    help="要跑的阶段：images / trace / identity / manifest / merge / import / verify / all")
    ap.add_argument("--out", type=Path, default=None, help="落盘目录（默认 tmp/xxt/<库>）")
    ap.add_argument("--size", type=int, default=400, help="位图尺寸")
    ap.add_argument("--batch", type=int, default=200, help="每个 PowerShell 进程取多少张位图")
    ap.add_argument("--delay", type=float, default=4.0, help="两次请求之间的间隔秒数")
    ap.add_argument("--lanes", type=int, default=1,
                    help="取图并发几路（实测两路不劣化；间隔 1s + 两路 ≈ 1s/张）")
    ap.add_argument("--shape-list", type=Path, default=None,
                    help="只取这些字形（每行一个「字体号_码位」）。"
                         "清单由 src/plan_xxt_fetch.py 生成：按层的选取规则筛过、"
                         "再扣掉漢典层已有的字形")
    ap.add_argument("--limit", type=int, default=0, help="只取多少张位图（0 = 全部）")
    ap.add_argument("--eps", type=float, default=0.7, help="描摹的 Douglas-Peucker 容差")
    ap.add_argument("--smooth", type=int, default=1, help="描摹的 Chaikin 平滑轮数")
    ap.add_argument("--yes", action="store_true", help="真往正式仓写（否则只做干跑）")
    args = ap.parse_args(argv)

    cfg = DBS[args.db]
    out = args.out or (ROOT / "tmp" / "xxt" / args.db)
    img_dir = out / "img"
    svg_dir = out / "svg"
    manifest = out / "manifest.json"

    stages = STAGES if args.stage == "all" else (args.stage,)
    for st in stages:
        if st not in STAGES:
            raise SystemExit("未知阶段：{}（可选：{} / all）".format(st, "、".join(STAGES)))

    if "images" in stages:
        cmd = [PY, "-X", "utf8", "-u", "src/fetch_xiaoxuetang_glyphs.py",
               "--mode", "glyphs", "--stage", "images", "--db", args.db,
               "--size", str(args.size), "--batch", str(args.batch),
               "--delay", str(args.delay), "--lanes", str(args.lanes),
               "--out", str(out)]
        if args.shape_list:
            cmd += ["--shape-list", str(args.shape_list)]
        if args.limit:
            cmd += ["--limit", str(args.limit)]
        run("位图抓取", cmd)

    if "trace" in stages:
        cmd = [PY, "-X", "utf8", "src/trace_xiaoxuetang_glyphs.py",
               "--input", str(img_dir), "--out", str(svg_dir),
               "--check", "--eps", str(args.eps), "--smooth", str(args.smooth),
               "--manifest", str(out / "manifest.jsonl")]
        run("位图描摹 → SVG", cmd)

    if "identity" in stages:
        cmd = [PY, "-X", "utf8", "src/resolve_pua_identity.py",
               "--index", str(out / "index.jsonl"),
               "--out", str(out / "identity_map.jsonl"),
               "--seal-index", str(ROOT / "glyphs" / "seal" / "index.csv")]
        if cfg.get("zdic_provenance"):
            cmd += ["--zdic-provenance", str(cfg["zdic_provenance"])]
        if cfg.get("base_book"):
            cmd += ["--base-book", cfg["base_book"]]
        run("私用區身份反查", cmd)

    # **目标层**：一个库可能喂多个层（隸變庫按字体拆成隸書层 + 秦系层）。
    # 每个目标层有自己的清单、文献对照、漢典清单与收录闸门。
    targets = cfg.get("targets") or [{
        "layer": cfg["layer"],
        "font_allow": None,
        "books": cfg["books"],
        "books_xxt": books_xxt_of(cfg),
        "zdic_index": cfg.get("zdic_index"),
        "zdic_manifest": cfg.get("zdic_manifest"),
    }]
    for tgt in targets:
        t_layer = tgt["layer"]
        t_books = tgt.get("books") or cfg["books"]
        t_books_xxt = tgt.get("books_xxt") or books_xxt_of(cfg)
        t_zdic_index = tgt.get("zdic_index")
        t_zdic_manifest = tgt.get("zdic_manifest", cfg.get("zdic_manifest"))
        suffix = "" if len(targets) == 1 else f"（{t_layer}）"
        t_manifest = out / f"manifest-{t_layer}.json" if len(targets) > 1 else manifest
        t_merged = ROOT / "tmp" / "zdic" / (t_layer + "-mixed")

        if "manifest" in stages:
            cmd = [PY, "-X", "utf8", "src/build_xxt_manifest.py",
                   "--db", args.db,
                   "--index", str(out / "index.jsonl"),
                   "--traced", str(out / "traced.jsonl"),
                   "--svg-dir", str(svg_dir),
                   "--out", str(t_manifest),
                   "--books-xxt", str(t_books_xxt),
                   "--books", str(t_books),
                   "--identity-map", str(out / "identity_map.jsonl"),
                   "--out-dir", str(out / "files")]
            if tgt.get("font_allow"):
                cmd += ["--font-allow", tgt["font_allow"]]
            if t_zdic_index and Path(t_zdic_index).is_file():
                cmd += ["--zdic-index", str(t_zdic_index)]
            run("抓取结果 → 合并器清单" + suffix, cmd)

        if "merge" in stages:
            cmd = [PY, "-X", "utf8", "src/merge_glyph_manifests.py",
                   "--manifest", str(t_manifest)]
            if t_zdic_manifest and Path(t_zdic_manifest).is_file():
                cmd += ["--manifest", str(t_zdic_manifest)]
            cmd += ["--keep-multi", "--out", str(t_merged)]
            if Path(t_books).is_file():
                cmd += ["--books-csv", str(t_books)]
            run("合并清单" + suffix, cmd)

        if "import" in stages:
            cmd = [PY, "-X", "utf8", "src/import_glyph_layer.py",
                   "--manifest", str(t_merged / "manifest.json"), "--layer", t_layer]
            if not args.yes:
                cmd.append("--dry-run")
            run("入库" + suffix + ("（干跑）" if not args.yes else ""), cmd)

        if "verify" in stages:
            run("出处核验" + suffix, [PY, "-X", "utf8", "src/verify_provenance.py",
                                       "--script", t_layer, "--quiet"])

    if "verify" in stages:
        run("字形体检", [PY, "-X", "utf8", "src/check_glyphs.py", "--repo-root", "."])
        run("描摹保真", [PY, "-X", "utf8", "src/check_glyphs.py", "--trace-fidelity"])

    print("\n全部完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
