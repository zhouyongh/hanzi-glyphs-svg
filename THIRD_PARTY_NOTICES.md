# 第三方内容与署名

本仓库的**代码**与**字形 SVG** 许可不同，字形还**逐书体**不同。使用任一内容前，请读本文件
与 `glyphs/provenance.jsonl`（一个字形一条，含 `license` 与 `attribution` 字段），
并用 `python src/verify_provenance.py` 校验。

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
| 本仓库做了什么 | 只把 `data/svg_polyline/` 的 1,203 个 SVG **逐字节复制**到 `glyphs/oracle/<glyph_id>.svg`；**未做任何修改**（未转码、未归一化 viewBox、未重绘）。 |
| 校验 | 1,203 个文件已与 Zenodo 原件逐一 sha256 比对**全部一致**；Zenodo zip 的 MD5 与官方公布值一致。 |
| 未收录 | 上游 `data/svg_parametric/`（解析重建后的光滑化版本）、`src/`、`figs/`。 |

### 署名文字（使用本目录字形时请原样附上）

> 字形来源：Li, Qing-sheng & Bian, Yu-lin (2026), *Oracle Bone Glyphs: Parametric Vector
> Dataset (v0.3)*, doi:10.5281/zenodo.22467946, CC BY 4.0.

### 相关论文

Li, Qing-sheng and Bian, Yu-lin. *An Interpretable Parametric Representation and Open
Dataset for Oracle Bone Script: Adaptive Arc Segmentation and SVG Resource.*
npj Heritage Science (2026).

> ⚠️ **论文与数据集的许可不同**。本仓库只依据数据集（CC BY 4.0）使用字形；
> 引用论文正文请以期刊页面公布的条款为准。

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

## 代码

`src/` 下的脚本由本仓库编写。**本仓库尚未确定代码许可**（见 `AGENTS.md`「许可」一节）。
