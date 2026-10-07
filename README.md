# hanzi-glyphs-svg

汉字古文字字形 **SVG** 库：收录甲骨文、金文、篆书、隶书的字形，并保证**每个字形都能追溯到出处**。
供上层项目（字典、教学、游戏、排版）直接引用；本仓库只做字形，不做应用。

## 现在有什么

| 书体 | 目录 | 数量 | 许可 |
|------|------|------|------|
| 甲骨文 Oracle bone script | `glyphs/oracle/` | **1,203** 个骨架 + **1,203** 个轮廓 | CC BY 4.0 |
| 金文 Bronze script | `glyphs/bronze/` | 尚未收录 | — |
| 篆书 Seal script | `glyphs/seal/` | 尚未收录 | — |
| 隶书 Clerical script | `glyphs/clerical/` | 尚未收录 | — |

甲骨文这批来自公开数据集 *Oracle Bone Glyphs: Parametric Vector Dataset (v0.3)*
（DOI [`10.5281/zenodo.22467946`](https://zenodo.org/records/22467946)，CC BY 4.0）。
骨架文件与上游**逐字节一致**，并已与 Zenodo 原件逐一 sha256 比对通过。

## 浏览

- **在线预览**：仓库开启 GitHub Pages 后为 `https://<你的用户名>.github.io/hanzi-glyphs-svg/`
- **本地预览**：直接双击 `viewer/index.html`（零依赖、无需服务器；数据已内联进页面）

页面有四个书体 Tab。甲骨文 Tab 可预览全部 1,203 个字形，支持按编号 / 现代字 / 码位 / 拼音搜索，
可在「骨架」与「轮廓」两层之间切换，身份存疑的条目有黄框标记。

## 两种字形层

| 层 | 路径 | 是什么 | 用途 |
|----|------|--------|------|
| **骨架** | `glyphs/oracle/<glyph_id>.svg` | 上游原件的逐字节副本，笔画为 `stroke` 线条 | **溯源锚点**，sha256 能对回上游 |
| **轮廓** | `glyphs/oracle/outline/<glyph_id>.svg` | 由骨架派生：把描边区域换成真正的填充路径，同名、同 viewBox | 需要**填充**字形时用（排版、图标、转字体） |

轮廓层是派生件，不是上游文件；改骨架后必须重跑 `src/outline_oracle.py` 重新生成。
两者的几何一致性有自动校验（见下）。

## 目录

```
hanzi-glyphs-svg/
  AGENTS.md                  本仓库的约定（改结构先改它）
  README.md                  本文件
  THIRD_PARTY_NOTICES.md     第三方署名、改动声明、权利保留
  LICENSE                    CC BY 4.0 全文（数据与文档）
  LICENSE-CODE               MIT 全文（代码）
  LICENSE-DATA               数据许可说明
  glyphs/
    provenance.jsonl         每个字形一条出处记录
    oracle/                  甲骨文骨架 + index.csv
      outline/               甲骨文轮廓（派生）
  src/                       脚本：导入 / 派生 / 校验 / 生成浏览页
  viewer/index.html          静态浏览页（生成的，勿手改）
  docs/                      调研与路线
```

## 出处与校验

`glyphs/provenance.jsonl` 一行一条，每个字形文件一条，含：来源数据集、DOI、来源 URL、
上游路径、上游 sha256、本地 sha256、许可、署名文字、时间；派生件另含
`derived_from` / `derived_from_sha256` / `transform`。

```bash
python src/verify_provenance.py          # 校验每个文件的 sha256 与记录是否一致
python src/outline_oracle.py --selftest  # 轮廓层的几何自检
```

`verify_provenance.py` 以退出码 1 报告任何不符，可直接用于 CI。

## 重新生成

```bash
# 1) 导入骨架（需要一个解包后的上游数据集副本）
python src/import_oracle_jgw.py --dataset-dir <解包目录> [--zenodo-dir <Zenodo 原件解包目录>]

# 2) 由骨架派生可填充轮廓
python src/outline_oracle.py

# 3) 重新生成浏览页（数据变了才需要）
python src/build_viewer.py
```

三个脚本都是可重跑的：导入只替换自己那一层（`layer="skeleton"`）的记录，不会动派生层。

## 许可

| 范围 | 许可 |
|------|------|
| `glyphs/**`（字形、索引、出处记录） | **CC BY 4.0** |
| `README.md`、`AGENTS.md`、`docs/**`、`THIRD_PARTY_NOTICES.md` | **CC BY 4.0** |
| `src/**`、`viewer/**` | **MIT** |

使用 `glyphs/` 下的数据**必须署名**，并注明是否做过修改——署名文字与改动声明见
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 第三方权利

甲骨文字形本身是三千年前的古文字，不主张著作权。但本仓库注意到：上游数据集自述其字形取自
其「source hand copy」与 2012 年的 source database，**未披露该第三方来源的名称与许可**。
本仓库只对自己新增的部分（轮廓派生、索引、脚本、文档）主张权利，**不对古文字形及其来源摹本
主张任何权利**。若你是相关权利人并认为本仓库内容侵犯了你的权利，请通过 Issue 或
<1279190619@qq.com> 联系我们，我们会在核实后移除相应条目。

详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
