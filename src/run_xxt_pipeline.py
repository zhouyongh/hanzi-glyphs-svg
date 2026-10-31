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
chuanchao          chuanchao              tmp/zdic/chuanchao-merged/…
xiaozhuan          xiaozhuan              （无：与 seal/ 不是同一批）
=================  =====================  ============================

**合并时「漢典矢量优先」**：合并器对同一键的两条记录按 ``layer`` 判——
``skeleton``（漢典矢量）優先于 ``outline``（小學堂描摹），并在清单的
``merge_conflicts`` 里留痕。層的归属闸门用层自己的 ``books.csv``。

**identity 阶段**：小学堂有些字頭的「楷書字頭」只是**字体排版槽位**（私用区），
不是 Unicode 汉字码位。这个阶段用 ``resolve_pua_identity.py`` 反查补回真身份，
清单阶段据此给出真汉字码位；反查不出来才走**临时身份**并标记。

**路线顺序按层实测定**（``--prefer``）：楚系层 ``D,A,C``（路线 D 实测 99.72%），
傳抄层 ``D,C,A``（全量实测 D 74.72% > C 73.49%，且 C 的命中被 D 完全覆盖）。
详见 ``resolve_pua_identity.py`` 的模块说明。
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
        # 傳抄层的漢典矢量基底（本次新抓）：同一批材料，漢典给矢量件、
        # 小學堂给位图描摹件，合并时**漢典矢量优先**。
        # 这是抓取器的原始输出（12,975 条，字形文件与清单同目录）；
        # 合并阶段照样按层自己的 books.csv 过收录闸门。
        "zdic_manifest": ROOT / "tmp" / "zdic" / "chuanchao-full" / "manifest.json",
        "books": ROOT / "glyphs" / "chuanchao" / "books.csv",
        "books_xxt": ROOT / "glyphs" / "chuanchao" / "books_xxt.csv",
        # 身份反查：傳抄层的摹本底本是《傳抄古文字編》（冊頁.行，帶冊次），
        # 与楚系的《楚系簡帛文字編》（頁.行）粒度不同，各认各的底本名。
        "zdic_provenance": ROOT / "glyphs" / "provenance" / "chuanchao.jsonl",
        "base_book": "傳抄古文字編",
        # 路线顺序：**D 优先**。全量数据实测 D 74.72% > C 73.49%，且 D∪C 的答对数
        # 与 D 单独的答对数相同（6,237）——说明 C 的命中**完全被 D 覆盖**，
        # 把 C 放前面并不能多答对，只会让「一致」的判定更早被 C 定死。
        # （部分数据时的初判是 C 优先，全量下已修正。）
        "prefer": "D,C,A",
        # 路线 C 的输入是**漢典傳抄层的 index.csv**。傳抄层是**新层**，
        # 所以这一步要先入库漢典那批矢量件（key-mode=glyph_id），跑一次才有 index.csv。
        "zdic_index": ROOT / "glyphs" / "chuanchao" / "index.csv",
        # **整层替换**：合并重排后条目号变了，旧文件名全部作废。
        "prune": True,
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
        # **整层替换**：条目号重排后旧文件名全部作废。
        "prune": True,
    },
    "jinwen": {
        "layer": "bronze",
        "zdic_manifest": ROOT / "tmp" / "zdic" / "bronze-rebuilt" / "manifest.json",
        "books": ROOT / "glyphs" / "bronze" / "books.csv",
        "books_xxt": ROOT / "glyphs" / "bronze" / "books_xxt.csv",
        "zdic_provenance": None,
        "base_book": "",
        "zdic_index": ROOT / "glyphs" / "bronze" / "index.csv",
        # **整层替换**：条目号重排后旧文件名全部作废。
        "prune": True,
    },
    # **隸變庫喂隸書层**（「中研院隸書重文」字体）。
    #
    # 隸變庫里也有「中研院秦系簡牘文字重文」字体（3,726 个实例），但**秦系层不由这个库喂**：
    # 同一个字体在**秦系庫**里有 **3,890** 个实例（是隸變庫那批的**超集**，
    # 字形键重合 3,712），秦系层已按秦系庫入库（3,170 件）。
    # 若这里也把秦系列为目标，重跑 lishu 会用**少 164 个实例的子集**覆盖秦系层——
    # 所以秦系层只由 `--db qinwenzi` 喂。
    "lishu": {
        "layer": "clerical",
        "zdic_manifest": ROOT / "tmp" / "zdic" / "clerical-rebuilt" / "manifest.json",
        "books": ROOT / "glyphs" / "clerical" / "books.csv",
        "books_xxt": ROOT / "glyphs" / "clerical" / "books_xxt.csv",
        "zdic_provenance": None,
        "base_book": "",
        # **时代词表**从现有层的 period 列取——计划阶段要靠它认时代、分时代桶。
        "zdic_index": ROOT / "glyphs" / "clerical" / "index.csv",
        # **字体闸门**：隸變库里还有「中研院秦系簡牘文字重文*」（3,726 个实例），
        # 那是**秦系字形**，归秦系层，不进隸書层。
        # 顶层也要写一份——计划阶段读的是顶层的这个键（targets 里那份只管清单阶段）。
        "font_allow": "中研院隸書",
        "prune": True,
        "targets": [
            {"layer": "clerical", "font_allow": "中研院隸書",
             "books": ROOT / "glyphs" / "clerical" / "books.csv",
             "books_xxt": ROOT / "glyphs" / "clerical" / "books_xxt.csv",
             "zdic_index": ROOT / "glyphs" / "clerical" / "index.csv",
             "zdic_manifest": ROOT / "tmp" / "zdic" / "clerical-rebuilt" / "manifest.json",
             # **整层替换**：条目号重排后旧文件名全部作废。
             "prune": True},
        ],
    },
}

STAGES = ("zdic-import", "rebuild", "identity", "plan", "images", "trace", "manifest", "merge",
          "import", "verify")


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
                    help="要跑的阶段（--stage all 按 STAGES 的顺序跑）："
                         "zdic-import / rebuild / identity / plan / images / trace / "
                         "manifest / merge / import / verify。"
                         "**顺序有意义**：plan 在 identity 之后（每字上限按码位算，"
                         "反查会把私用區字頭补成真汉字），images 在 plan 之后")
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

    # ---- 取图计划 ----
    #
    # **顺序是有讲究的**：计划要在**身份反查之后**跑。
    # 每字上限是**按码位**算的，而反查会把一部分私用區字頭**补成真汉字**——
    # 计划跑在反查之前时，这些字头按「槽位」占额度（额度记在另一个键上），
    # 清单阶段身份补回来后额度就超了（实测甲骨层一次合并有 35 个字超上限）。
    # 把 plan 做成流水线里的一个阶段，顺序就固化在工具里，不靠人记。
    if "plan" in stages:
        cmd = [PY, "-X", "utf8", "src/plan_xxt_fetch.py",
               "--db", args.db, "--layer", cfg["layer"]]
        zman = cfg.get("zdic_manifest")
        if zman:
            zman = Path(zman)
            # 基线用**合并时的那份漢典清单**：层现在的 index.csv 已经含有
            # 上一轮并进来的小學堂批次，拿它判重会把小學堂那批判成自己的重复。
            # **每次都重建**：层重排过之后旧清单里的**文件名已经作废**
            # （条目号是整层内容的函数，层一改，旧基线指向的文件就不是那一件了）。
            run("重建漢典侧清单",
                [PY, "-X", "utf8", "src/rebuild_layer_manifest.py",
                 "--layer", cfg["layer"], "--out", str(zman.parent)])
            cmd += ["--zdic-manifest", str(zman)]
        # **时代词表要从现有层的 period 列取**（两边用同一张表才谈得上规则统一），
        # 所以索引基线也要传——清单基线只管「层里已经有了什么」，
        # 不带时代词表的话，时代认不出来，桶键会退成「器名 + 编号」。
        if cfg.get("zdic_index"):
            cmd += ["--zdic-index", str(cfg["zdic_index"])]
        ident = out / "identity_map.jsonl"
        if ident.is_file():
            cmd += ["--identity-map", str(ident)]
        if cfg.get("books_xxt") and Path(cfg["books_xxt"]).is_file():
            cmd += ["--books-xxt", str(cfg["books_xxt"])]
        if cfg.get("books") and Path(cfg["books"]).is_file():
            cmd += ["--books", str(cfg["books"])]
        if cfg.get("font_allow"):
            cmd += ["--font-allow", cfg["font_allow"]]
        cmd += ["--out-keys", str(out / "fetch-keys.txt"),
                "--out-list", str(out / "fetch-list.tsv"),
                "--out-selection", str(out / "fetch-selection.jsonl")]
        run("取图计划", cmd)

    if "images" in stages:
        cmd = [PY, "-X", "utf8", "-u", "src/fetch_xiaoxuetang_glyphs.py",
               "--mode", "glyphs", "--stage", "images", "--db", args.db,
               "--size", str(args.size), "--batch", str(args.batch),
               "--delay", str(args.delay), "--lanes", str(args.lanes),
               "--out", str(out)]
        if args.shape_list:
            cmd += ["--shape-list", str(args.shape_list)]
        else:
            # 没显式给清单就用**计划阶段的产出**——抓的正是计划选中的那些字形。
            keys = out / "fetch-keys.txt"
            if keys.is_file():
                cmd += ["--shape-list", str(keys)]
        if args.limit:
            cmd += ["--limit", str(args.limit)]
        run("位图抓取", cmd)

    if "trace" in stages:
        cmd = [PY, "-X", "utf8", "src/trace_xiaoxuetang_glyphs.py",
               "--input", str(img_dir), "--out", str(svg_dir),
               "--check", "--eps", str(args.eps), "--smooth", str(args.smooth),
               "--manifest", str(out / "manifest.jsonl")]
        run("位图描摹 → SVG", cmd)

    if "zdic-import" in stages:
        # **先把漢典那批矢量件入库**，产生层的 index.csv。
        #
        # 为什么单独一步：傳抄层的身份反查要用**路线 C（字形键）**，
        # 路线 C 的输入是層自己的 index.csv——而 index.csv 是**入库后才有的**。
        # 傳抄層是**新層**，所以这一步只写新层，不碰任何现有层。
        zdic_manifest = cfg.get("zdic_manifest")
        if not zdic_manifest or not Path(zdic_manifest).is_file():
            print("跳过 zdic-import：这层没有漢典矢量基底（{}）".format(zdic_manifest))
        else:
            cmd = [PY, "-X", "utf8", "src/import_glyph_layer.py",
                   "--manifest", str(zdic_manifest), "--layer", cfg["layer"]]
            if not args.yes:
                cmd.append("--dry-run")
            run("漢典矢量件入库" + ("（干跑）" if not args.yes else ""), cmd)

    if "identity" in stages:
        cmd = [PY, "-X", "utf8", "src/resolve_pua_identity.py",
               "--index", str(out / "index.jsonl"),
               "--out", str(out / "identity_map.jsonl"),
               "--seal-index", str(ROOT / "glyphs" / "seal" / "index.csv")]
        if cfg.get("zdic_provenance"):
            cmd += ["--zdic-provenance", str(cfg["zdic_provenance"])]
        if cfg.get("base_book"):
            cmd += ["--base-book", cfg["base_book"]]
        # **路线顺序按层实测定**（见 resolve_pua_identity.py 的 --prefer）：
        # 楚系层 D 优先（实测 99.72%），傳抄层 C 优先（实测 D 只有 75.61%）。
        if cfg.get("prefer"):
            cmd += ["--prefer", cfg["prefer"]]
        # 路线 C（字形键）要對方层的 index.csv——**键空间两库同构**。
        if cfg.get("zdic_index"):
            cmd += ["--zdic-shape-index", str(cfg["zdic_index"])]
        run("私用區身份反查", cmd)

    # **目标层**：一个库可能喂多个层（隸變庫按字体拆成隸書层 + 秦系层）。
    # 每个目标层有自己的清单、文献对照、漢典清单与收录闸门。
    #
    # ``prune`` = **整层替换**：条目号重排后旧文件名全部作废，
    # 留着就是「有文件、无出处记录」的孤儿字形。增量入库的层都要开。
    targets = cfg.get("targets") or [{
        "layer": cfg["layer"],
        "font_allow": None,
        "books": cfg["books"],
        "books_xxt": books_xxt_of(cfg),
        "zdic_index": cfg.get("zdic_index"),
        "zdic_manifest": cfg.get("zdic_manifest"),
        "prune": cfg.get("prune", False),
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

        if "rebuild" in stages and t_zdic_manifest:
            # **现有层的漢典侧清单**：从层里的 index.csv + provenance 重建，
            # 不用把十几万个上游 SVG 再抓一遍。
            # 增量入库要**整层替换**（条目号是整层内容的函数，层里增删字形会整体重排），
            # 所以合并时要拼上这份重建清单，合并器重排条目号后再整层写回。
            out_dir = Path(t_zdic_manifest).parent
            run("重建漢典侧清单" + suffix,
                [PY, "-X", "utf8", "src/rebuild_layer_manifest.py",
                 "--layer", t_layer, "--out", str(out_dir)])
            if not Path(t_zdic_manifest).is_file():
                raise SystemExit(f"重建清单没出来：{t_zdic_manifest}")

        if "manifest" in stages:
            cmd = [PY, "-X", "utf8", "src/build_xxt_manifest.py",
                   "--db", args.db,
                   "--layer", t_layer,
                   "--index", str(out / "index.jsonl"),
                   "--traced", str(out / "traced.jsonl"),
                   "--svg-dir", str(svg_dir),
                   "--out", str(t_manifest),
                   "--books-xxt", str(t_books_xxt),
                   "--books", str(t_books),
                   "--identity-map", str(out / "identity_map.jsonl"),
                   "--out-dir", str(out / "files")]
            # **按取图阶段同一份选择走**：分桶规则与每字上限是在那儿算的。
            sel = out / "fetch-selection.jsonl"
            if sel.is_file():
                cmd += ["--selection", str(sel)]
            if tgt.get("font_allow"):
                cmd += ["--font-allow", tgt["font_allow"]]
            if t_zdic_index and Path(t_zdic_index).is_file():
                cmd += ["--zdic-index", str(t_zdic_index)]
            # **基线用合并时的那一份漢典清单**：层现在的 index.csv 已经含有
            # 上一轮并进来的小學堂批次，拿它判重会把小學堂那批判成自己的重复。
            if t_zdic_manifest and Path(t_zdic_manifest).is_file():
                cmd += ["--zdic-manifest", str(t_zdic_manifest)]
            run("抓取结果 → 合并器清单" + suffix, cmd)

        if "merge" in stages:
            cmd = [PY, "-X", "utf8", "src/merge_glyph_manifests.py",
                   "--manifest", str(t_manifest)]
            if t_zdic_manifest and Path(t_zdic_manifest).is_file():
                cmd += ["--manifest", str(t_zdic_manifest)]
            cmd += ["--keep-multi", "--clean", "--out", str(t_merged)]
            if Path(t_books).is_file():
                cmd += ["--books-csv", str(t_books)]
            run("合并清单" + suffix, cmd)

        if "import" in stages:
            cmd = [PY, "-X", "utf8", "src/import_glyph_layer.py",
                   "--manifest", str(t_merged / "manifest.json"), "--layer", t_layer]
            if tgt.get("prune"):
                # **整层替换**：条目号重排后旧文件名全部作废，
                # 留着就是「有文件、无出处记录」的孤儿字形。
                cmd.append("--prune")
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
