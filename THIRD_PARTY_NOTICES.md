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
