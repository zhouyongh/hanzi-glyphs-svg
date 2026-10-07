#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拉取「開元小篆」上游仓库到本地查看（只看不入库）。

    python src/fetch_seal_upstream.py [--target tmp/kaiyuan-upstream]

clone https://github.com/frankslin/kaiyuan-small-seal-font 并停在
glyphs/seal/external.meta.json 钉住的 upstream_commit，随后把上游字形文件数
与登记表统计对照，便于人工核验。也可直接双击仓库根目录的 fetch_kaiyuan.bat。

注意：仅供本地查看对比；其字形不得复制进本仓库分发，
许可状态见 THIRD_PARTY_NOTICES.md。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/frankslin/kaiyuan-small-seal-font.git"
DEFAULT_TARGET = Path("tmp") / "kaiyuan-upstream"


def run_git(*args: str, cwd: Path | None = None) -> str:
    cmd = ["git", *args]
    print("  $ " + " ".join(cmd))
    proc = subprocess.run(
        cmd, cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return proc.stdout


def main() -> int:
    ap = argparse.ArgumentParser(description="拉取開元小篆上游到本地（只看不入库）")
    ap.add_argument("--target", type=Path, default=DEFAULT_TARGET,
                    help="clone 目标目录（默认 tmp/kaiyuan-upstream，已被 gitignore）")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    meta_path = root / "glyphs" / "seal" / "external.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    commit = meta["upstream_commit"]
    print(f"钉住的 commit : {commit}")
    print(f"登记时间       : {meta.get('generated_at', '?')}")
    print(f"目标目录       : {args.target}")

    if (args.target / ".git").is_dir():
        print("已存在，fetch 更新 ...")
        run_git("fetch", "--quiet", cwd=args.target)
    else:
        print("clone 上游仓库 ...")
        run_git("clone", REPO_URL, str(args.target))

    print("切换到钉住版本 ...")
    run_git("checkout", "--quiet", commit, cwd=args.target)

    paths = run_git("ls-tree", "-r", "--name-only", commit, "--", "glyphs",
                    cwd=args.target).splitlines()
    upstream_count = len(paths)
    expected = meta.get("upstream_glyph_count")
    status = "一致" if upstream_count == expected else "不一致！"

    print()
    print(f"上游字形文件数 : {upstream_count}（登记表记 {expected}）→ {status}")
    print(f"登记码位数     : {meta['codepoints_with_upstream']} / "
          f"{meta['codepoint_count']}")
    print()
    print(f"完成：{args.target} 已停在 {commit[:12]}")
    print("注意：仅供本地查看对比，字形不得复制进本仓库分发（见 THIRD_PARTY_NOTICES.md）。")
    return 0 if upstream_count == expected else 1


if __name__ == "__main__":
    sys.exit(main())
