# AGENTS.md — hanzi-glyphs-svg

汉字库：把汉字字形 **SVG** 建全，并保证 **出处可追溯**。

## 用途

- 收录汉字 SVG 字形（甲骨/金文/篆书/隶书等）
- 供上层项目引用；本仓库不做游戏、不做网站

## 目录

```
hanzi-glyphs-svg/
  AGENTS.md
  docs/          # 文档（调研、路线）
  glyphs/        # 字形 SVG + 出处记录
    oracle/
    bronze/
    seal/
    clerical/
  src/           # 脚本（导出/校验/打包）
```

保持精简，勿随意增加顶层目录。

## 书体目录名

| 目录 | 中文 | 英文（学术/国际常用） |
|------|------|----------------------|
| `glyphs/oracle/` | 甲骨文 | Oracle bone script |
| `glyphs/bronze/` | 金文 | Bronze script |
| `glyphs/seal/` | 篆书 | Seal script |
| `glyphs/clerical/` | 隶书 | Clerical script |

## 字形文件

文件名按书体分两种，因为**只有小篆在 Unicode 里有自己的码位**：

| 书体 | 文件名 | 键 |
|------|--------|----|
| `glyphs/seal/` | `<Unicode>.svg` | 现代汉字码位，**6 位大写十六进制**，如 `0065E5.svg` = 日 |
| `glyphs/oracle/` | `<glyph_id>.svg` | 源字库条目号，**4 位十进制**，如 `0001.svg` |

- **甲骨文/金文没有自己的 Unicode 码位**，`<Unicode>.svg` 表达不了它们；而且一字多形是常态
  （已导入的 1,203 条甲骨文里，33 个现代字各对应 2 个条目），所以改用**条目号**做键。
- 每个书体目录下放一份 `index.csv`，提供「现代字 / 码位 → 文件名」反查。
- `glyphs/oracle/` 的文件是上游的**逐字节副本**：不重新编码、不归一化 viewBox。
- 书体目录下可以有**派生层**子目录。目前有 `glyphs/oracle/outline/`：与骨架**同名、同 viewBox**
  的可填充轮廓（把 `stroke` 换成真正的填充区域），由 `python src/outline_oracle.py` 生成。
  **骨架是溯源锚点**（能逐字节对回上游），轮廓是给上层渲染用的派生件；改了骨架必须重跑生成。

## 硬规则

1. **无出处，不入仓库**。说不清从哪来的，删除。
2. 出处写在 `glyphs/provenance.jsonl`（一行一条，一个文件一条）：  
   必填 `path`、`sha256`、`license`，时间字段 `retrieved_at`（派生件用 `generated_at`），
   以及至少一个来源 URL；另记 `script`、`layer`、`glyph_id`、`source_path`、
   `source_sha256`、`source_doi`、`attribution`。  
   派生件（`layer` 不是 `skeleton`）另记 `derived_from`、`derived_from_sha256`、`transform`、`tool`。  
   用 `python src/verify_provenance.py` 校验。
3. **禁止编造链接**；网络来源须核实后再写入 provenance。
4. 正式字形须**贴近原字形**；禁止卡通美化当正式字形。
5. 未获原作者同意时，**如实写来源**，不冒充原创或隐瞒出处。

## 许可

- 字形 SVG 的许可**逐书体**不同，以 `provenance.jsonl` 每条的 `license` 为准；
  使用方须按该许可署名，署名文字在 `attribution` 字段与 `THIRD_PARTY_NOTICES.md`。
- 目前 `glyphs/oracle/`（1,203 个字形）为 **CC-BY-4.0**。
- **CC BY-ND / CC BY-NC / 无许可的来源不得作为字形来源入库**：矢量化与重绘都属于「改作」，
  ND 直接禁止；NC 与本库公开供引用的目的冲突。

## 当前状态

- 2026-10-05：导入甲骨文 **1,203** 个字形到 `glyphs/oracle/`。来源为公开数据集
  （DOI `10.5281/zenodo.22467946`，CC-BY-4.0），逐字 provenance 与 `index.csv` 已就位，
  且已与 Zenodo 原件逐文件对拍一致。
- 其中 2 条没有对应现代汉字（`0380`、`0916`），1 条身份为 `provisional`（`1180` 妞）。
- 同日生成派生层 `glyphs/oracle/outline/`（1,203 个可填充轮廓，2.08 MB）。骨架的 `stroke`
  在多数渲染场景下只能当线条看，轮廓层解决「字形要能填充」的问题；几何自检见
  `python src/outline_oracle.py --selftest`。
- 金文 / 篆书 / 隶书仍为空。
- 脚本：`src/import_oracle_jgw.py`（导入骨架）、`src/outline_oracle.py`（骨架 → 轮廓）、
  `src/verify_provenance.py`（校验出处）。

## 协作

- 中文交流；标识符用英文
- 改结构先改本文件
- 提交信息说明「为什么」
