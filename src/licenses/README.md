# 第三方许可原文

供 `src/verify_font_licenses.py` 逐条款比对用的基准文本。

| 文件 | 来源 | sha256 | 取得方式 |
|------|------|--------|----------|
| `OFL-1.1-official.txt` | <https://openfontlicense.org/documents/OFL.txt>（SIL 官方 OFL 1.1，26 February 2007） | `1d361a8f8e8ce6e68457dcd93fb56e162e6baa3bbb7e7573a290d44399f6b57e` | 2026-10-25 直接下载，与本文件**逐字节相同** |

## 为什么要在仓库里放一份基准

「这个字体的许可是不是官方 OFL 1.1」不能靠文件名、也不能靠记忆。
把官方原文放进仓库，`verify_font_licenses.py` 就能把上游 `OFL.txt`
按 1)–5) 切成六段**逐段比相似度**，任何一条被改过或缺失都会被机器指出来。

基准本身也要能复核：上面那一行 sha256 就是复核点——
重新下载官方文本后比对 sha256 即可，不一致说明官方文本变了（那也要重新审）。

## 注意

- 这份文本是 **SIL 的作品**，不是本仓库的作品，随 `LICENSE-DOCS`（CC0 1.0）发布不准确；
  它按 SIL 自己的许可条款分发（OFL 允许分发许可全文）。
- 它只作**比对基准**，不构成对任何字体的授权；某个字体的实际授权以
  该字体层目录下的 `OFL.txt` 与 `glyphs/provenance.jsonl` 里的 `license` 字段为准。
