# hanzi-glyphs-svg

汉字古文字字形 **SVG** 库：收录甲骨文、篆书等书体的字形，并保证**每个字形都能追溯到出处**。
供上层项目（字典、教学、排版）直接引用；本仓库只做字形，不做应用。

**当前公开发布两批**：甲骨文 JGW 参数化矢量骨架（1,203 骨架 + 1,203 轮廓，CC BY 4.0）与
篆书（10,591 个字形，CC0 1.0）。其余书体（金文、隶书、楚文字、傳抄古文，以及甲骨层里
来自汉典的拓片摹本）已整理入库，但**底本授权待确认，暂缓发布**——原因见下文「暂缓发布的书体」。

## 现在有什么

| 书体 | 目录 | 数量 | 许可 |
|------|------|------|------|
| 甲骨文 Oracle bone script | `glyphs/oracle/` | **1,203** 个骨架 + **1,203** 个轮廓 | **CC BY 4.0** |
| 篆书 Seal script | `glyphs/seal/` | **10,591** 个字形 | **CC0 1.0** |
| 篆书全量码位登记表 | `glyphs/seal/external.csv` | **11,328** 个码位（只登记指针，不含字形） | 见「许可」 |

甲骨文这批来自公开数据集 *Oracle Bone Glyphs: Parametric Vector Dataset (v0.3)*
（DOI [`10.5281/zenodo.22467946`](https://zenodo.org/records/22467946)，CC BY 4.0），
骨架文件与上游**逐字节一致**，并已与 Zenodo 原件逐一 sha256 比对通过；
轮廓层由骨架派生（同名、同 viewBox），是**本仓库产物**，沿用同一许可。
使用这批字形的义务（署名、注明修改、附协议链接）已在下文与
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 中履行。

篆书层的字形来自汉典（zdic.net）「书法」小篆实例，依其《服务条款》第四条以
**CC0 1.0** 释出。每个字形都记清**出处部次与形制**——例如「說文‧心部」的正篆 /
說文古文 / 說文籀文 / 說文或體，逐条写在 `glyphs/provenance/seal.jsonl` 与
`glyphs/seal/index.csv` 里。这一层的底本是《说文》刻本系统（公有领域），
矢量化由汉典完成并已放弃权利，所以它是已整理的各层里**权利链最干净**的一层。

## 浏览

- **在线预览**：https://zhouyongh.github.io/hanzi-glyphs-svg/ （仓库开启 GitHub Pages 后生效）
- **本地预览**：直接双击 `viewer/index.html`（零依赖、无需服务器；数据已内联进页面）

页面按书体分 Tab：甲骨文 Tab 可预览全部 1,203 个字形，支持按编号 / 现代字 / 码位 / 拼音搜索，
可在「骨架」与「轮廓」两层之间切换，身份存疑的条目有黄框标记；篆书 Tab 预览 10,591 个字形，
悬停可看到该字的出处部次与形制，并另标出该字的篆书区块码位。

## 两种字形层

| 层 | 路径 | 是什么 | 用途 |
|----|------|--------|------|
| **骨架** | `glyphs/oracle/<glyph_id>.svg` | 上游原件的逐字节副本，笔画为 `stroke` 线条 | **溯源锚点**，sha256 能对回上游 |
| **轮廓** | `glyphs/oracle/outline/<glyph_id>.svg` | 由骨架派生：把描边区域换成真正的填充路径，同名、同 viewBox | 需要**填充**字形时用（排版、图标、转字体） |

轮廓层是派生件，不是上游文件；改骨架后必须重跑 `src/outline_oracle.py` 重新生成。
两者的几何一致性有自动校验（见下）。

## 篆书层：键是篆书区块码位，覆盖 93.5%

Unicode 给小篆单开了一个区块（U+3D000–U+3FC3F，**11,328** 个码位）。
本层的文件名就是**篆书区块码位**（`3D000.svg` = U+3D000，一），不是现代字码位——
因为同一个现代字在篆书区块里可能有多个码位（正篆 + 重文），按现代字命名会撞车。
11,328 个码位对应 11,231 个现代字，其中 93 个现代字有多个码位。

**每个现代字只收一个实例**，落在**正篆**码位上（判定规则：说文主序列优先 →
四本《说文》收录数 → 码位大小；与 Unicode 核心规范 §18.14 的排序规则一致，
并与 OpenCC 的首选反查 93/93 一致），其余重文码位留空。
本层收录 **10,591** 个字形，覆盖 **10,591 / 11,328 = 93.5%**；
缺口 737 个码位中，543 个上游[開元小篆](https://github.com/frankslin/kaiyuan-small-seal-font)
有字形、194 个哪里都没有。

`glyphs/seal/external.csv` 另有一份**全量码位登记表**（11,328 行），
记每个码位对应哪个现代字、属《说文》540 部哪一部、在四个《说文》版本中的流水号，
以及上游[開元小篆](https://github.com/frankslin/kaiyuan-small-seal-font)的文件路径与
git blob SHA-1。**本仓库不复制上游的任何字形内容**，只登记指针——
上游有两处许可缺口（授权语句只写到「output fonts」，且随附的 `OFL.txt` **并非 SIL 官方
OFL 1.1 文本**，只有第 1、2 条与官方逐字相同，第 3–9 条相似度最高 0.344、第 10 条 0.602，
官方最关键的**第 5 条**「不得按其他许可分发」缺失），
把 `glyphs/**` 标成 `OFL-1.1` 入库是不实标注。逐条比对结论与字段说明见
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [glyphs/seal/README.md](glyphs/seal/README.md)。

> 顺带修了一处 Unicode 原文的偏差：`SealSources.txt` 把篆书码位 **U+3D06D** 记成
> 「王」，但它自己的部首属性 `kSEAL_Rad = 6.3D06D` 表明这是说文第 6 部「**玉**」部的
> 部首字（U+3D068 才是第 5 部「王」部的部首字），OpenCC 也记作「玉」。
> 按原文口径「玉」将没有任何篆书码位，抓取名单里根本没有这个字。
> 本仓库按部首结构修正并在 `external.csv` 的 `note` 列标出，依据见
> [glyphs/seal/README.md](glyphs/seal/README.md)。

## 暂缓发布的书体（为什么）

以下内容已在本地整理入库，但**没有随本仓库发布**：

- 甲骨层里来自汉典的拓片摹本；
- 金文、隶书、楚文字、傳抄古文。

这些字形的直接上游是汉典「书法」实例，汉典已就其自身权利作 CC0 宣告；但它们是
**「摹本 + 矢量化」**的产物，底本是**仍在版权保护期内的现代出版物**
（《殷周金文集成》《睡虎地秦简文字编》《秦汉魏晋篆隶字形表》《楚系简帛文字编》
《傳抄古文字編》等）。汉典的 CC0 **放弃的是汉典自己的权利，不消灭底本的权利**。

本仓库的立场：**不主张这些字形及其底本的任何权利**；在底本授权状况澄清前不发布，
以免以「CC0」的名义替第三方背书。授权或权利状态确认后，各层会连同逐条出处记录
一并加入——出处记录已按层拆到 `glyphs/provenance/<书体>.jsonl`，加一层只需加一个文件与一个目录。

**篆书层为什么不在此列**：它的底本 100% 是《说文》刻本系统（题记 `source_book`
全部是「說文‧X部」，10,591/10,591 无例外），属公有领域，不存在「在版摹本汇编」这一环。

## 目录

```
hanzi-glyphs-svg/
  AGENTS.md                  本仓库的约定（改结构先改它）
  README.md                  本文件
  THIRD_PARTY_NOTICES.md     第三方署名、改动声明、权利保留
  LICENSE                    CC BY 4.0 全文（只覆盖 CC BY 那一层数据）
  LICENSE-CODE               MIT 全文（代码）
  LICENSE-DOCS               CC0 1.0 全文（文档；篆书层的 CC0 也引这一份）
  LICENSE-DATA               逐层数据/文档/代码许可说明
  glyphs/
    provenance/              出处记录，一层一个文件（oracle.jsonl / seal.jsonl）
    oracle/                  甲骨文骨架 + index.csv + outline/（派生）
    seal/                    篆书字形 + index.csv + external.csv（全量码位登记表）
  src/                       脚本：导入 / 派生 / 校验 / 生成浏览页
  viewer/index.html          静态浏览页（生成的，勿手改）
```

## 出处与校验

`glyphs/provenance/<书体>.jsonl` 一行一条，每个字形文件一条，含：来源数据集、DOI、来源 URL、
上游路径、上游 sha256、本地 sha256、许可、署名文字、时间；派生件另含
`derived_from` / `derived_from_sha256` / `transform`。

```bash
python src/glyph_stats.py                # 统计汇总：各层许可、上游原件数、时代桶、改动分布
python src/verify_provenance.py          # 校验每个文件的 sha256 与记录是否一致
python src/outline_oracle.py --selftest  # 轮廓层的几何自检
```

`verify_provenance.py` 以退出码 1 报告任何不符，可直接用于 CI。它同时复核两件事：
每条的 `license` 是否在允许名单内（ND / NC / 无许可一律不许在库里），
以及每条记录的书体是否与所在文件名一致。

## 重新生成

```bash
# 1) 导入骨架（需要一个解包后的上游数据集副本）
python src/import_oracle_jgw.py --dataset-dir <解包目录> [--zenodo-dir <Zenodo 原件解包目录>]

# 2) 由骨架派生可填充轮廓
python src/outline_oracle.py

# 3) 篆书层（字表来自篆书全量登记表）
python src/fetch_zdic_glyphs.py --script xiaozhuan --from-seal-registry --out tmp/zdic/xiaozhuan --workers 5 \
    --source-dataset "汉典（zdic.net）篆文字形"
python src/clean_zdic_glyphs.py --manifest tmp/zdic/xiaozhuan/manifest.json --out tmp/zdic/xiaozhuan-clean
python src/merge_glyph_manifests.py --manifest tmp/zdic/xiaozhuan-clean/manifest.json --out tmp/zdic/xiaozhuan-final
python src/assign_seal_codepoints.py --manifest tmp/zdic/xiaozhuan-final/manifest.json \
    --out tmp/zdic/xiaozhuan-seal --zheng-table tmp/research/seal-modern-to-zheng.txt
python src/import_glyph_layer.py --manifest tmp/zdic/xiaozhuan-seal/manifest.json --layer seal --key-mode seal_codepoint

# 4) 重建篆书全量码位登记表（含玉/王偏差修正）
python src/build_seal_registry.py

# 5) 重新生成浏览页（数据变了才需要）
python src/build_viewer.py
```

这些脚本都可重跑：导入只替换自己那一层（`layer="skeleton"`）的 provenance 记录，
不会动派生层；写入的是 `glyphs/provenance/<书体>.jsonl`，不会碰别的书体的记录。

## 许可

许可**逐层不同**，以 `glyphs/provenance/<书体>.jsonl` 每条的 `license` 字段为准。

| 范围 | 许可 |
|------|------|
| `glyphs/oracle/**`（1,203 骨架 + 1,203 轮廓 + 索引 + 出处记录） | **CC BY 4.0**（全文见根 `LICENSE`） |
| `glyphs/seal/**`（篆书字形、索引、出处记录） | **CC0 1.0**（公有领域奉献，无义务；全文见 `LICENSE-DOCS`） |
| `glyphs/seal/external.csv` 中派生于 Unicode `SealSources.txt` 的列 | **Unicode License v3**（声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)） |
| `glyphs/seal/external.csv` 的 `upstream_*` 列 | **不适用**：只是指向外部仓库的指针 |
| `README.md`、`AGENTS.md`、`THIRD_PARTY_NOTICES.md` | **CC0 1.0**（无义务，随便用） |
| `src/**`、`viewer/**` | **MIT** |

根 `LICENSE`（CC BY 4.0）**只覆盖 CC BY 4.0 那一层**（甲骨 JGW 骨架与派生轮廓），
不覆盖 CC0 与 Unicode 授权的材料。使用 `glyphs/oracle/` 下的数据**必须署名**并注明是否做过
修改——署名文字与改动声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；
篆书层是 CC0，**没有义务**，但本仓库同样不对它附加任何限制。

## 第三方权利

三千年前的甲骨文与《说文》篆形本身不产生著作权。但本仓库注意到：
JGW 上游数据集自述其字形取自其「source hand copy」与 2012 年的 source database，
**未披露该第三方来源的名称与许可**；篆书层的矢量化由汉典完成，汉典已作 CC0 宣告。
本仓库只对自己新增的部分（轮廓派生、索引、脚本、浏览页、文档）主张权利，
**不对古文字形及其来源摹本主张任何权利**。若你是相关权利人并认为本仓库内容侵犯了你的权利，
请通过 Issue 或 <1279190619@qq.com> 联系我们，我们会在核实后移除相应条目——
`glyphs/provenance/` 一层一个文件、一个文件一条记录，单条字形可以独立移除而不影响其余内容。

详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
