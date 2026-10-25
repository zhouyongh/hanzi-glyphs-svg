# 第三方内容与署名

本仓库的**数据**与**代码**许可是分开的，数据还**逐书体**不同。使用任一内容前，请读本文件
与 `glyphs/provenance/<书体>.jsonl`（一个文件一条，含 `license` 与 `attribution` 字段），
并用 `python src/verify_provenance.py` 校验。

## 许可地图

| 范围 | 许可 | 全文 |
|------|------|------|
| `glyphs/oracle/**`（甲骨 JGW 骨架 1,203 个 + 派生轮廓 1,203 个 + 索引 + 出处记录） | **CC BY 4.0** | 根 `LICENSE` |
| `glyphs/seal/**`（篆书 10,591 个字形、索引、出处记录） | **CC0 1.0**（公有领域奉献，无义务） | `LICENSE-DOCS`；汉典的归公宣告原文见本文件 |
| `glyphs/kaishu/` `glyphs/xingshu/` `glyphs/caoshu/` `glyphs/songti/` `glyphs/songti-tc/` `glyphs/heiti-hk/`（现代书体六层 97,349 个字形、索引、出处记录） | **SIL OFL 1.1** | 各层目录的 `OFL.txt`（上游逐字节副本） |
| `glyphs/provenance/*.jsonl` | **逐条记录**：每条按其 `license` 字段（CC BY 4.0 / CC0 1.0 / OFL-1.1） | 本文件 + 根 `LICENSE` |
| `glyphs/seal/external.csv` —— 本仓库整理的部分 | CC BY 4.0 | 根 `LICENSE` |
| `glyphs/seal/external.csv` —— 派生于 Unicode `SealSources.txt` 的列 | Unicode License v3（声明见下） | 本文件 |
| `glyphs/seal/external.csv` 的 `upstream_*` 列（指向上游） | **不适用**：本仓库未复制上游内容，只登记指针 | — |
| `README.md`、`AGENTS.md`、本文件 | CC0 1.0（无义务） | `LICENSE-DOCS` |
| `src/**`、`viewer/**` | CC0 1.0（无义务） | `LICENSE-CODE` |

**根 `LICENSE`（CC BY 4.0）只覆盖 CC BY 4.0 那一层**（甲骨 JGW 层，以及篆书登记表里本仓库整理的
部分），**不覆盖** CC0、OFL 与 Unicode 授权的材料。下游须按各层许可分别使用。

---

## `glyphs/oracle/` —— 甲骨文（JGW 批，CC BY 4.0）

| 项 | 内容 |
|---|---|
| 来源数据集 | Oracle Bone Glyphs: Parametric Vector Dataset (**v0.3**) |
| 作者 | Li, Qing-sheng；Bian, Yu-lin（浙江传媒学院） |
| DOI | [`10.5281/zenodo.22467946`](https://zenodo.org/records/22467946) |
| 镜像 | [github.com/aylqs2025/oracle-bone-jgw-1203](https://github.com/aylqs2025/oracle-bone-jgw-1203)（tag `v0.3`，commit `5496ad559f81ae8632f3915e8ec2beb705c64ba3`） |
| 原件 | `aylqs2025/oracle-bone-jgw-1203-v0.3.zip`，MD5 `7764c7f5b0feb8f0052c36233ddf8d4b` |
| 许可 | **CC BY 4.0**（上游 `/data`、`/figs`） — <https://creativecommons.org/licenses/by/4.0/> |
| 校验 | 1,203 个骨架文件与 Zenodo 原件逐一 sha256 **全部一致**；Zenodo zip 的 MD5 与官方公布值一致 |
| 未收录 | 上游 `data/svg_parametric/`（解析重建后的光滑化版本）、`src/`、`figs/` |

### 署名文字（使用 `glyphs/oracle/` 时请原样附上）

> 字形来源：Li, Qing-sheng & Bian, Yu-lin (2026), *Oracle Bone Glyphs: Parametric Vector
> Dataset (v0.3)*, doi:10.5281/zenodo.22467946, CC BY 4.0.
> 数据集主页：https://zenodo.org/records/22467946
> 许可全文：https://creativecommons.org/licenses/by/4.0/legalcode

### 本仓库做了哪些修改（CC BY 4.0 §3(a)(1)(B) 要求声明）

1. 把上游 `data/svg_polyline/` 的 1,203 个 SVG **逐字节复制**为 `glyphs/oracle/<glyph_id>.svg`，
   **未改动其几何内容**（未转码、未归一化 viewBox、未重绘）；每条的 sha256 见
   `glyphs/provenance/oracle.jsonl`，可与上游原件逐一比对。
2. 由这些骨架**派生**出可填充轮廓 `glyphs/oracle/outline/<glyph_id>.svg`（把 `stroke` 骨架
   转换为填充路径，同名、同 viewBox），由本仓库脚本 `src/outline_oracle.py` 生成，
   **不是上游产物**。
3. 新增了本仓库自己的 `index.csv`、`provenance/`、`src/**` 脚本、`viewer/` 浏览页与文档。
4. 上述修改**不改变上游材料的许可状态**：`glyphs/oracle/*.svg` 与
   `glyphs/oracle/outline/*.svg` 均继续适用 CC BY 4.0；任何下游使用都须遵守 CC BY 4.0
   （含署名与改动声明要求）。本仓库未对下游附加任何额外限制。

### 派生层 `glyphs/oracle/outline/`

- 派生件沿用上游的 **CC BY 4.0** 与同一署名要求。
- 每个派生文件的出处记在 `glyphs/provenance/oracle.jsonl`（`layer: "outline"`，含
  `derived_from` 与 `derived_from_sha256` 指回骨架）。

### 上游自述的限制（转录，非本仓库添加）

- 上游每个字只提供**一个代表字形**；异形、跨阶段字形演变、贞人（scribe group）风格分析
  均明确不在其范围内。
- 上游自述：最锐的钩笔分段存在少量**残环**（中位重建误差 0.0026）。
- **甲骨文在 Unicode 中没有码位**；每条记录的 `unicode` 指的是对应**现代汉字**的码位。
- v0.3 中有 **33 个现代字各对应 2 个条目**（如 `0013` 与 `1149` 都是「祥」），
  属考古学上的分化，不是重复标注；身份请以 `glyph_id` 为准。
- `0380`、`0916` 两条没有可对应的现代汉字；`1180`（妞）的身份为 `provisional`。

---

## `glyphs/seal/` —— 篆书（汉典「书法」小篆，CC0 1.0）

| 项 | 内容 |
|---|---|
| 来源 | 汉典（zdic.net）「书法」字形实例 |
| 实例页 | `https://www.zdic.net/hans/<字>/xiaozhuan` |
| 字形文件直链 | `https://img.zdic.net/zy/xiaozhuan/<id>.svg` |
| 许可 | **CC0 1.0**（汉典《服务条款》第四条「归公宣告」） |
| 规模 | `glyphs/seal/` 10,591 个字形，覆盖篆书区块 11,328 个码位中的 93.5% |

### 许可原文（照录，勿改写）

> 四、归公宣告
> 汉典奉行 CC0 1.0 公约，将本站字词、古籍、诗词、书法诸作，悉数贡献天下，放弃著作专权及邻接法益，任人取用，以公无穷。
>
> —— <https://www.zdic.net/terms/>（2026-10-24 核验）

CC0 1.0 是**公有领域奉献**：不设任何条件，不署名、不注明改动也可以使用。

### 本仓库做了哪些修改

1. **去水印。** 汉典的篆书字形 SVG 里带一层**近白色的角标水印**（近白填充 `#fafafb` 一类，
   与字形笔画零重叠，占画布 0.16%–0.46%）。入库前用 `src/clean_zdic_glyphs.py` 把
   「有效填充色接近纯白」的 `<g>` / `<path>` 元素**整块删掉**，其余字节原样保留。
   每条的改动情况记在 `provenance/seal.jsonl` 的 `modifications` 字段。
2. **剔除位图实例。** 汉典有个别实例不是矢量轮廓，而是把 PNG 以 base64 塞进 `<image>`。
   这类文件不是**矢量字形**，且水印与笔画烤在同一张位图里分不开，本库只收矢量字形。
   因此 `3F32F`、`3F41A` 两个码位空缺。
3. **留痕。** 逐字形记录了 `source_sha256`（上游原件）与本地 `sha256`，可与汉典原件逐一比对。

本层的字形出处是**题记里的「說文‧X部」**（10,591 条全部如此，无例外），
对应《说文》刻本系统；`index.csv` 与 `provenance/seal.jsonl` 里逐条记着部次与形制
（正篆 / 說文古文 / 說文籀文 / 說文或體）。本仓库**不对字形及其底本主张任何权利**；
若相关权利人认为某条内容侵犯权利，请通过 Issue 或 <1279190619@qq.com> 联系，核实后移除。

---

## 现代书体六层 —— SIL OFL 1.1（从开源字体提取轮廓）

这六层的字形**不是上游的逐字节副本**，而是用 `src/extract_font_glyphs.py` 从 OFL 字体提取轮廓
生成的派生件：取字体轮廓路径、y 轴翻转（字体坐标 y 向上 → SVG y 向下）、坐标四舍五入到 0.01
字体单位；全层共用同一个画布（该层全部字形墨迹的并集外扩 1%），字形之间的相对比例与字体里一致。
可变字体按 `wght=400` 实例提取。

| 层 | 字体（版本） | 版权行 | 上游 |
|---|---|---|---|
| `glyphs/kaishu/` | Ma Shan Zheng 2.003 | Copyright 2018 The MaShanZheng Project Authors | `google/fonts` 的 `ofl/mashanzheng` |
| `glyphs/xingshu/` | Zhi Mang Xing 2.001 | Copyright 2018 The ZhiMangXing Project Authors | `google/fonts` 的 `ofl/zhimangxing` |
| `glyphs/caoshu/` | Liu Jian Mao Cao 1.003 | Copyright 2018 The Liu Jian Mao Cao Project Authors | `google/fonts` 的 `ofl/liujianmaocao` |
| `glyphs/songti/` | Noto Serif SC 2.003（`wght=400`） | Copyright 2012 Google Inc.（name 表：© 2017-2024 Adobe） | `google/fonts` 的 `ofl/notoserifsc` |
| `glyphs/songti-tc/` | Noto Serif TC 2.003（`wght=400`） | Copyright 2012 Google Inc.（name 表：© 2017-2024 Adobe） | `google/fonts` 的 `ofl/notoserifctc` |
| `glyphs/heiti-hk/` | Chiron Hei HK 2.530（`wght=400`） | Copyright 2025 The Chiron Hei HK Project Authors | [chiron-fonts/chiron-hei-hk](https://github.com/chiron-fonts/chiron-hei-hk) |

每层的 `SOURCE.md` 记着字体家族名、版本、上游路径、**字体二进制的 sha256**、取回时刻与变换说明；
每层的 `OFL.txt` 是**上游随附许可全文的逐字节副本**（sha256 见 `SOURCE.md`），版权行在文件抬头。

### OFL 1.1 的四条义务与履行方式

| OFL 条款 | 要求 | 本仓库怎么做的 |
|---|---|---|
| 第 2 条 | 每份副本带版权声明与许可全文 | 每层目录随附 `OFL.txt` 逐字节副本；`attribution` 逐条写明字体家族与「Copyright 见该层 OFL.txt」 |
| 第 3 条 | 修改版不得使用保留字体名（RFN） | 六个字体在 `OFL.txt` 抬头与**字体二进制 name 表**两处都**没有 RFN**；层名用通用书体名，字体家族名只出现在 `attribution` 与 `index.csv` |
| 第 5 条 | 修改版须完全按 OFL 分发，不得按其他许可分发 | 六层整层标 `OFL-1.1`，**不**混入 CC0 / CC BY；下游基于这些字形做的东西也必须按 OFL 分发 |
| 第 1 条 | 不得单独销售字体软件本身 | 本仓库不销售任何东西 |

**取用须知**：版权声明与许可全文随**层目录**提供（`OFL.txt` + `SOURCE.md`），
单个 SVG 文件里不含声明。把某个字形单独拷进其他项目时，请**连同该层的 `OFL.txt` 一并保留**，
并按 OFL 1.1 分发。

逐条款核验可复跑（正文与 SIL 官方文本 `src/licenses/OFL-1.1-official.txt` 逐条款比对，
并检查 RFN 与版权行）：

```bash
python src/verify_font_licenses.py --license-dir glyphs/kaishu --font <本地字体路径>
python src/build_font_license_evidence.py --font-dir <本地字体目录>
```

---

## `glyphs/seal/external.csv` 的上游登记 —— 開元小篆：只登记指针，不复制字形

`external.csv`（11,328 行）把每个 Unicode 篆书码位指向
[frankslin/kaiyuan-small-seal-font](https://github.com/frankslin/kaiyuan-small-seal-font)
里的字形文件，并记录其 git blob SHA-1；**不复制任何上游内容**，因此不构成对上游材料的分发。
`upstream_*` 列只是指针，**不涉及授权**。

本仓库没有直接引用上游字形，原因：上游的授权语句只覆盖「output fonts」，
而 `glyphs/` 被描述为流水线的生成物、没有目录级许可标记；随附的 `OFL.txt` 也不是 SIL 官方
OFL 1.1 文本。把 10,980 个文件标成 `OFL-1.1` 入库等于替上游背书一份它没有签过的协议，
所以只登记、不复制。上游若补齐许可文件，这一层可以按 OFL 1.1 正式导入。

登记时钉住的 commit 见 `glyphs/seal/external.meta.json` 的 `upstream_commit`。

---

## Unicode 数据（`SealSources.txt`）—— Unicode License v3

`glyphs/seal/external.csv` 的 `ccz` / `dyc` / `qjz` / `thx` / `radical_*` / `unicode` /
`modern_char` 列派生自 Unicode 18.0 的 `SealSources.txt`
（<https://www.unicode.org/Public/18.0.0/ucd/SealSources.txt>，见 UAX #60）。按该协议
条件 (b)，其版权与许可声明随本文件一并提供：

### 一处偏差修正

`SealSources.txt` 用 `kSEAL_MCJK` 记录「篆书码位 → 现代汉字」，其中 **U+3D06D 记成 U+738B（王）**，
但同一份文件的部首属性 `kSEAL_Rad` 自相矛盾：U+3D068 是第 5 部「王」部的部首字，
U+3D06D 是第 6 部「玉」部的部首字。OpenCC 的 `SealCharacters.txt` 也把 U+3D06D 记作「玉」。
本仓库按部首结构修正（**玉 → U+3D06D，王 → U+3D068**），修正在 `src/build_seal_registry.py`
的 `MCJK_DEVIATIONS` 里写死，逐行记在 `external.csv` 的 `note` 列。
**这是对 Unicode 数据的唯一一处改动**，其余列照录原文。

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

甲骨文字形本身是三千年前的古文字，其刻划不产生著作权；《说文》篆形同理。
本仓库**不对古文字形本身主张任何权利**，只对自己新增的部分（轮廓派生、索引、脚本、
浏览页、文档）主张权利。

但本仓库注意到：JGW 上游自述其字形取自其「source hand copy」与 **2012 年的 source database**
（见上游 `data/provenance_manifest.csv`：`0380` 条目提到殷契文渊平台，`0916` 条目提到 2012 年
源数据库里的私用区码位 U+E83B），**上游并未披露该第三方来源的名称与许可状态**，本仓库无法核实。

- 若你是相关权利人，并认为本仓库内容侵犯了你的权利，请通过 GitHub Issue 或
  <1279190619@qq.com> 联系我们；我们会在核实后移除相应条目。
- 由于 `glyphs/provenance/` 一个文件一条，**单条字形可以独立移除而不影响其余内容**。
- 本仓库保留与上游逐字节一致的 sha256 记录，作为善意使用的证据。

---

## 代码

`src/**` 与 `viewer/**` 由本仓库编写，以 **CC0 1.0** 释出，说明见 `LICENSE-CODE`。
