# AGENTS.md — hanzi-glyphs-svg

汉字库：把汉字字形 **SVG** 建全，并保证 **出处可追溯**。

## 用途

- 收录汉字 SVG 字形（甲骨/金文/篆书/隶书等）
- 供上层项目引用；本仓库不做游戏、不做业务应用
- 附一个**零构建的只读浏览页** `viewer/index.html`（由 `src/build_viewer.py` 生成，不是应用、
  不引入依赖、不复制字形文件），用于人工核验字形

## 目录

```
hanzi-glyphs-svg/
  AGENTS.md / README.md
  LICENSE            # CC BY 4.0 全文（数据与文档）
  LICENSE-CODE       # MIT 全文（代码）
  LICENSE-DATA       # 数据许可说明
  THIRD_PARTY_NOTICES.md
  glyphs/            # 字形 SVG + 出处记录
    provenance.jsonl
    oracle/          # 骨架 + index.csv + outline/（派生层）
    seal/            # external.csv 外部登记表（无字形文件）
    bronze/  clerical/
  src/               # 脚本（导入/派生/校验/生成浏览页）
  viewer/            # 静态浏览页（生成的，勿手改）
  .github/workflows/ # GitHub Pages 部署
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
- 书体目录下也可以**只有登记表、没有字形文件**：`glyphs/seal/external.csv` + `external.meta.json`
  把每个码位指向上游仓库的文件（记 `upstream_path` 与 `upstream_blob_sha1`），**不复制内容**。
  适用条件：上游许可未澄清、或不宜再分发时。登记表由 `python src/build_seal_registry.py` 生成，
  字段说明见 `glyphs/seal/README.md`。**登记表里不放字形，所以它不受上游许可状态影响。**

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
- **本仓库自身的对外许可**：数据与文档 **CC BY 4.0**（根 `LICENSE`），
  代码 `src/**`、`viewer/**` 为 **MIT**（`LICENSE-CODE`）。完整地图在 `README.md`。
- 根 `LICENSE` 必须是 CC BY 4.0 的**逐字全文**：GitHub 的协议识别（Licensee）是把文件正文
  与已知协议做相似度比对，只写一句「本仓库采用 CC BY 4.0」的说明**不会被识别**，
  仓库会显示成 Unknown 或只显示 MIT（上游仓库就是这种情况）。
- **不得给下游附加额外限制**（例如「仅限非商业」「禁止再分发」）：既违反 CC BY 4.0
  §2(a)(5)(B)，也会让自己的授权失效。
- **外部登记表**（如 `glyphs/seal/external.csv`）里派生于 Unicode `SealSources.txt` 的列
  适用 **Unicode License v3**，其版权与许可声明已随 `THIRD_PARTY_NOTICES.md` 提供
  （该协议条件 (b) 允许把声明放在关联文档里）。表里 `upstream_*` 列只是指针，不涉及授权。

## 当前状态

| 书体 | 状态 |
|------|------|
| 甲骨文 | **1,203** 骨架 + **1,203** 轮廓（CC BY 4.0，DOI `10.5281/zenodo.22467946`），provenance 与 `index.csv` 齐全 |
| 篆书 | 外部登记表 `external.csv`：**11,328** 个码位指针，**无字形文件** |
| 金文 / 隶书 | 尚未收录 |

- 甲骨文特例：`0380`、`0916` 无对应现代汉字；`1180`（妞）身份为 `provisional`。
- 已知残余风险（上游数据集未披露其字形所依据的第三方摹本来源）见 `THIRD_PARTY_NOTICES.md`。

## 脚本

| 脚本 | 作用 |
|------|------|
| `src/import_oracle_jgw.py` | 导入甲骨文骨架 |
| `src/outline_oracle.py` | 骨架 → 可填充轮廓（`--selftest` 几何自检） |
| `src/build_seal_registry.py` | 生成篆书外部登记表 |
| `src/build_viewer.py` | 生成只读浏览页 |
| `src/verify_provenance.py` | 校验 provenance 与文件 sha256 |

## 协作

- 中文交流；标识符用英文
- 改结构先改本文件
- 提交信息说明「为什么」
