# 第三方内容与署名

本仓库的**数据**与**代码**许可是分开的，数据许可还**逐书体**不同。使用任一内容前，请读本文件
与 `glyphs/provenance.jsonl`（一个文件一条，含 `license` 与 `attribution` 字段），
并用 `python src/verify_provenance.py` 校验。

## 许可地图

| 范围 | 许可 | 全文 |
|------|------|------|
| `glyphs/**`（字形 SVG、`index.csv`、`provenance.jsonl`） | CC BY 4.0 | 根 `LICENSE` |
| `README.md`、`AGENTS.md`、`docs/**`、本文件 | CC BY 4.0 | 根 `LICENSE` |
| `src/**`、`viewer/**` | MIT | `LICENSE-CODE` |
| `glyphs/seal/external.csv` —— 本仓库整理的部分 | CC BY 4.0 | 根 `LICENSE` |
| `glyphs/seal/external.csv` —— 派生于 Unicode `SealSources.txt` 的列 | Unicode License v3（声明见下） | 本文件 |
| `glyphs/seal/external.csv` 的 `upstream_*` 列（指向上游） | **不适用**：本仓库未复制上游内容，只登记指针 | — |

---

## `glyphs/oracle/` —— 甲骨文字形（1,203 个）

| 项 | 内容 |
|---|---|
| 来源数据集 | Oracle Bone Glyphs: Parametric Vector Dataset (**v0.3**) |
| 作者 | Li, Qing-sheng；Bian, Yu-lin（浙江传媒学院） |
| DOI | [`10.5281/zenodo.22467946`](https://zenodo.org/records/22467946) |
| 镜像 | [github.com/aylqs2025/oracle-bone-jgw-1203](https://github.com/aylqs2025/oracle-bone-jgw-1203)（tag `v0.3`，commit `5496ad559f81ae8632f3915e8ec2beb705c64ba3`） |
| 原件 | `aylqs2025/oracle-bone-jgw-1203-v0.3.zip`，MD5 `7764c7f5b0feb8f0052c36233ddf8d4b` |
| 许可 | **CC BY 4.0**（上游 `/data`、`/figs`） — <https://creativecommons.org/licenses/by/4.0/> |
| 校验 | 1,203 个骨架文件与 Zenodo 原件逐一 sha256 **全部一致**；Zenodo zip 的 MD5 与官方公布值一致。 |
| 未收录 | 上游 `data/svg_parametric/`（解析重建后的光滑化版本）、`src/`、`figs/`。 |

### 署名文字（使用 `glyphs/oracle/` 时请原样附上）

> 字形来源：Li, Qing-sheng & Bian, Yu-lin (2026), *Oracle Bone Glyphs: Parametric Vector
> Dataset (v0.3)*, doi:10.5281/zenodo.22467946, CC BY 4.0.
> 数据集主页：https://zenodo.org/records/22467946
> 许可全文：https://creativecommons.org/licenses/by/4.0/legalcode

### 本仓库做了哪些修改（CC BY 4.0 §3(a)(1)(B) 要求声明）

1. 把上游 `data/svg_polyline/` 的 1,203 个 SVG **逐字节复制**为 `glyphs/oracle/<glyph_id>.svg`，
   **未改动其几何内容**（未转码、未归一化 viewBox、未重绘）；每条的 sha256 见
   `glyphs/provenance.jsonl`，可与上游原件逐一比对。
2. 由这些骨架**派生**出可填充轮廓 `glyphs/oracle/outline/<glyph_id>.svg`（把 `stroke` 骨架
   转换为填充路径，同名、同 viewBox），由本仓库脚本 `src/outline_oracle.py` 生成，
   **不是上游产物**。
3. 新增了本仓库自己的 `index.csv`、`provenance.jsonl`、`src/**` 脚本、`viewer/` 浏览页与文档。
4. 上述修改**不改变上游材料的许可状态**：`glyphs/oracle/*.svg` 与
   `glyphs/oracle/outline/*.svg` 均继续适用 CC BY 4.0；任何下游使用都须遵守 CC BY 4.0
   （含署名与改动声明要求）。本仓库未对下游附加任何额外限制。

### 派生层 `glyphs/oracle/outline/`

- 派生件沿用上游的 **CC BY 4.0** 与同一署名要求。
- 每个派生文件的出处记在 `glyphs/provenance.jsonl`（`layer: "outline"`，含
  `derived_from` 与 `derived_from_sha256` 指回骨架）。

### 相关论文

Li, Qing-sheng and Bian, Yu-lin. *An Interpretable Parametric Representation and Open
Dataset for Oracle Bone Script: Adaptive Arc Segmentation and SVG Resource.*
npj Heritage Science (2026).

> ⚠️ **论文与数据集的许可不同**。论文正文依 Crossref 记录为 **CC BY-NC-ND 4.0**，
> 而数据集是 CC BY 4.0。本仓库**只依据数据集**使用字形，**没有**收录论文的任何文本或图表。

### 上游自述的限制（转录，非本仓库添加）

- 上游每个字只提供**一个代表字形**；异形、跨阶段字形演变、贞人（scribe group）风格分析
  均明确不在其范围内。
- 上游自述：最锐的钩笔分段存在少量**残环**（中位重建误差 0.0026）。
- **甲骨文在 Unicode 中没有码位**；每条记录的 `unicode` 指的是对应**现代汉字**的码位，
  不是甲骨文字形自身的码位。
- v0.3 中有 **33 个现代字各对应 2 个条目**（如 `0013` 与 `1149` 都是「祥」），
  属考古学上的分化，不是重复标注；身份请以 `glyph_id` 为准。
- `0380`、`0916` 两条没有可对应的现代汉字（前者作者在殷契文渊查无、后者是旧库私用区
  U+E83B，仅作历史留痕）；`1180`（妞）的身份为 `provisional`。

---

## `glyphs/seal/` —— 篆书层：**只登记指针，不含字形文件**

本目录**没有**篆书字形 SVG。`external.csv`（11,328 行）把每个 Unicode 篆书码位指向
上游仓库里的字形文件，并记录其 git blob SHA-1；**不复制任何上游内容**，因此不构成
对上游材料的分发。详见 `glyphs/seal/README.md`。

| 项 | 内容 |
|---|---|
| 上游仓库 | [frankslin/kaiyuan-small-seal-font](https://github.com/frankslin/kaiyuan-small-seal-font)（開元小篆） |
| 登记时钉住的 commit | 见 `glyphs/seal/external.meta.json` 的 `upstream_commit` |
| 上游字形文件数 | 10,980（另有 348 个码位上游尚无字形） |
| 上游声明的许可 | SIL Open Font License 1.1（但其正文与官方 OFL 1.1 不一致，见下） |
| 本仓库的处理 | **不复制、不改作、不再分发**；只登记路径与 blob SHA |

### 为什么没有直接引用上游字形

登记时发现两处缺漏，均可在上游仓库复现：

1. 上游的授权语句只覆盖「**output fonts**」（其 README 写「字型：SIL OFL 1.1」，
   `AGENTS.md` 写 "Output fonts are released under the SIL Open Font License 1.1"），
   而 `glyphs/` 被描述为流水线的生成物（"Generated, but committed so reviewers can
   diff them"）。OFL 对 "Font Software" 的定义是「由版权人以本协议发布、并被
   **明确标记为此**的一组文件」，而上游 `glyphs/` 下没有任何许可标记或目录级声明，
   仓库根目录也没有 LICENSE 文件（只有 `OFL.txt`）。
2. 上游 `OFL.txt` 的正文与其声明的 OFL 1.1 **不一致**：缺官方抬头
   `SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007`、缺官方第 4 条与第 5 条
   （第 5 条即「修改版或未修改版必须整体以本协议分发」）、缺 `Reserved Font Name`
   定义段，并自订为 10 条条款。

本仓库对此的处理是**只登记、不复制**，并欢迎上游澄清后升级为正式导入。
若你是上游权利人并希望我们调整登记方式，请通过 Issue 或 <1279190619@qq.com> 联系。

---

## Unicode 数据（`SealSources.txt`）—— Unicode License v3

`glyphs/seal/external.csv` 的 `ccz` / `dyc` / `qjz` / `thx` / `radical_*` / `unicode` /
`modern_char` 列派生自 Unicode 18.0 的 `SealSources.txt`
（<https://www.unicode.org/Public/18.0.0/ucd/SealSources.txt>，见 UAX #60）。按该协议
条件 (b)，其版权与许可声明随本文件一并提供：

```
UNICODE LICENSE V3

COPYRIGHT AND PERMISSION NOTICE

Copyright © 1991-2026 Unicode, Inc.

NOTICE TO USER: Carefully read the following legal agreement. BY
DOWNLOADING, INSTALLING, COPYING OR OTHERWISE USING DATA FILES, AND/OR
SOFTWARE, YOU UNEQUIVOCALLY ACCEPT, AND AGREE TO BE BOUND BY, ALL OF THE
TERMS AND CONDITIONS OF THIS AGREEMENT. IF YOU DO NOT AGREE, DO NOT
DOWNLOAD, INSTALL, COPY, DISTRIBUTE OR USE THE DATA FILES OR SOFTWARE.

Permission is hereby granted, free of charge, to any person obtaining a
copy of data files and any associated documentation (the "Data Files") or
software and any associated documentation (the "Software") to deal in the
Data Files or Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, and/or sell
copies of the Data Files or Software, and to permit persons to whom the
Data Files or Software are furnished to do so, provided that either (a)
this copyright and permission notice appear with all copies of the Data
Files or Software, or (b) this copyright and permission notice appear in
associated Documentation.

THE DATA FILES AND SOFTWARE ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT OF
THIRD PARTY RIGHTS.

IN NO EVENT SHALL THE COPYRIGHT HOLDER OR HOLDERS INCLUDED IN THIS NOTICE
BE LIABLE FOR ANY CLAIM, OR ANY SPECIAL INDIRECT OR CONSEQUENTIAL DAMAGES,
OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THE DATA
FILES OR SOFTWARE.

Except as contained in this notice, the name of a copyright holder shall
not be used in advertising or otherwise to promote the sale, use or other
dealings in these Data Files or Software without prior written
authorization of the copyright holder.
```

---

## 第三方权利保留

甲骨文字形本身是三千年前的古文字，其刻划不产生著作权，本仓库**不对古文字形本身主张任何权利**。

但本仓库注意到：上游数据集自述其字形取自其「source hand copy」与 **2012 年的 source database**
（见上游 `data/provenance_manifest.csv`：`0380` 条目提到殷契文渊平台，`0916` 条目提到 2012 年
源数据库里的私用区码位 U+E83B），**上游并未披露该第三方来源的名称与许可状态**，本仓库无法核实。

- 本仓库只对自己新增的部分（轮廓派生、索引、脚本、浏览页、文档）主张权利。
- 若你是相关权利人，并认为本仓库内容侵犯了你的权利，请通过 GitHub Issue 或
  <1279190619@qq.com> 联系我们；我们会在核实后移除相应条目。
- 由于 `provenance.jsonl` 一个文件一条，**单条字形可以独立移除而不影响其余内容**。
- 本仓库保留与上游逐字节一致的 sha256 记录，作为善意使用的证据。

---

## 代码

`src/**` 与 `viewer/**` 由本仓库编写，以 **MIT** 授权，全文见 `LICENSE-CODE`。
