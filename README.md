# hanzi-glyphs-svg

汉字字形 **SVG** 库：收录甲骨文、金文、篆书、隶书，以及楷书、行书、草书、宋体、黑体等现代书体，
并保证**每个字形都能追溯到出处**。
供上层项目（字典、教学、排版）直接引用；本仓库只做字形，不做应用。

本仓库**自有的内容**（文档、索引、代码、浏览页）以 **CC0 1.0** 释出，不署名、不注明改动、无任何义务。
`glyphs/` 下的字形逐层不同：甲骨 JGW 层 **CC BY 4.0**、六个字体层 **OFL 1.1**、其余 **CC0 1.0**。

## 现在有什么

| 书体 | 目录 | 数量 | 许可 |
|------|------|------|------|
| 甲骨文 Oracle bone script | `glyphs/oracle/` | **10,213** 个拓片摹本 + **1,203** 个骨架 + **1,203** 个轮廓 | **CC0 1.0**（摹本）+ **CC BY 4.0**（骨架/轮廓） |
| 金文 Bronze script | `glyphs/bronze/` | **8,290** 个字形 | **CC0 1.0**（无义务） |
| 篆书 Seal script | `glyphs/seal/` | **10,591** 个字形 | **CC0 1.0**（无义务） |
| 隶书 Clerical script | `glyphs/clerical/` | **11,947** 个字形 | **CC0 1.0**（无义务） |
| 楷书 Regular script | `glyphs/kaishu/` | **6,763** 个字形 | **OFL 1.1** |
| 行书 Running script | `glyphs/xingshu/` | **6,763** 个字形 | **OFL 1.1** |
| 草书 Cursive script | `glyphs/caoshu/` | **6,763** 个字形 | **OFL 1.1** |
| 宋体（简）Song / Ming, SC | `glyphs/songti/` | **27,797** 个字形 | **OFL 1.1** |
| 宋体（繁）Song / Ming, TC | `glyphs/songti-tc/` | **17,665** 个字形 | **OFL 1.1** |
| 黑体（港）Sans, HK | `glyphs/heiti-hk/` | **31,598** 个字形 | **OFL 1.1** |
| 篆书全量码位登记表 | `glyphs/seal/external.csv` | **11,328** 个码位（不含字形，只登记指针） | 见「许可」 |

合计 **140,796** 条字形记录（含 1,203 个派生轮廓）。

### 甲骨文（JGW 批 CC BY 4.0 + 汉典摹本 CC0 1.0）

来自公开数据集 *Oracle Bone Glyphs: Parametric Vector Dataset (v0.3)*
（DOI [`10.5281/zenodo.22467946`](https://zenodo.org/records/22467946)，CC BY 4.0）。
骨架文件与上游**逐字节一致**，已与 Zenodo 原件逐一 sha256 比对通过；
轮廓层由骨架派生（同名、同 viewBox），是本仓库产物，沿用同一许可。
使用这批字形的义务（署名、注明修改、附协议链接）见
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

同一目录里另有 **10,213** 个汉典（zdic.net）的拓片摹本，依其《服务条款》第四条以 **CC0 1.0** 释出。
题记逐件带拓片号、《甲骨文合集》合号与卜辞组别（如「乙3400 / 合1285 / 賓組」）。
两批同目录，靠 `glyphs/provenance/oracle.jsonl` 的 `license` 与 `source_dataset` 区分，
`index.csv` 里靠 `char_form` 列区分（JGW 批有值）。

### 金文（CC0 1.0）

来自汉典「书法」金文实例，**8,290** 条。题记为器名 + 集成号 + 时代
（如「毛公鼎 集成2838 西周中期」），底本是青铜器拓片。
同一个现代字在不同器物、不同时代各收一条（26 个时代桶），拼起来是字形演变链。

### 篆书（CC0 1.0）

来自汉典（zdic.net）「书法」小篆实例，依其《服务条款》第四条以 **CC0 1.0** 释出。
每个字形都记清**出处部次与形制**——例如「說文‧心部」的正篆 / 說文古文 / 說文籀文 /
說文或體，逐条写在 `glyphs/provenance/seal.jsonl` 与 `glyphs/seal/index.csv` 里。
这一层的底本是《说文》刻本系统（公有领域），矢量化由汉典完成并已放弃权利。

### 隶书（CC0 1.0）

来自汉典「书法」隶书实例，**11,947** 条。题记为碑帖名或简号 + 时代
（如「睡.日甲111背 秦」「武梁祠畫象題字」），底本为汉碑、印谱与秦汉简牍。
同样每字每时代一条（12 个时代桶）。

### 现代书体六层（OFL 1.1）

六层都是**从 OFL 开源字体提取轮廓**的派生件，用 `src/extract_font_glyphs.py` 生成：

| 层 | 字体 | 版本 |
|---|---|---|
| `glyphs/kaishu/` | Ma Shan Zheng | 2.003 |
| `glyphs/xingshu/` | Zhi Mang Xing | 2.001 |
| `glyphs/caoshu/` | Liu Jian Mao Cao | 1.003 |
| `glyphs/songti/` | Noto Serif SC | 2.003（`wght=400` 实例） |
| `glyphs/songti-tc/` | Noto Serif TC | 2.003（`wght=400` 实例） |
| `glyphs/heiti-hk/` | Chiron Hei HK | 2.530（`wght=400` 实例） |

每层目录里有三样东西，缺一不可：

- `OFL.txt` —— **上游字体随附的许可全文逐字节副本**（OFL 第 2 条要求每份副本都带版权声明与许可）；
- `SOURCE.md` —— 字体家族名、版本、上游仓库路径、字体 sha256、取回时刻、变换说明；
- `index.csv` —— 「现代字码位 → 文件名」反查。

六个字体在 `OFL.txt` 抬头与字体二进制的 name 表**两处都没有保留字体名（RFN）**，
所以层名用通用书体名，字体家族名只出现在 `attribution` 与 `index.csv` 里。
逐条款核验可复跑：`python src/verify_font_licenses.py --license-dir glyphs/<层> --font <字体>`。

## 浏览

- **在线预览**：https://zhouyongh.github.io/hanzi-glyphs-svg/
- **本地预览**：直接双击 `viewer/index.html`（零依赖、无需服务器；索引数据已内联进页面，
  字形文件按需去取）

页面按书体分 Tab：甲骨文 Tab 可预览全部 11,416 个字形，支持按编号 / 现代字 / 码位 / 拼音搜索，
可在「骨架」与「轮廓」两层之间切换，身份存疑的条目有黄框标记；金文、篆书、隶书三个 Tab
各预览该层全部字形，悬停可看到出处作品、编号与时代（金文与隶书另有时代筛选）；
楷/行/草/宋简/宋繁/黑港六个 Tab 各预览该层全部字形，悬停可看到字体家族与版本。

线上预览的字形从 jsDelivr（`gh` 通道）取，取不到时回落到 raw.githubusercontent；
本地双击时走相对路径 `../glyphs/`，离线可用。

## 两种字形层（甲骨）

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
git blob SHA-1。**本仓库不复制上游的任何字形**，只登记指针：上游的授权语句只写到
「output fonts」，随附的 `OFL.txt` 也不是 SIL 官方 OFL 1.1 文本，
把它标成 `OFL-1.1` 入库是不实标注。核验结论与字段说明见
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [glyphs/seal/README.md](glyphs/seal/README.md)。

> 顺带修了一处 Unicode 原文的偏差：`SealSources.txt` 把篆书码位 **U+3D06D** 记成
> 「王」，但它自己的部首属性 `kSEAL_Rad = 6.3D06D` 表明这是说文第 6 部「**玉**」部的
> 部首字（U+3D068 才是第 5 部「王」部的部首字），OpenCC 也记作「玉」。
> 按原文口径「玉」将没有任何篆书码位，抓取名单里根本没有这个字。
> 本仓库按部首结构修正并在 `external.csv` 的 `note` 列标出，依据见
> [glyphs/seal/README.md](glyphs/seal/README.md)。

## 现代书体六层：键是现代字码位，两层宋体会重叠

这六层的文件名是**现代字的 Unicode 码位**（6 位大写十六进制，`004E04.svg` = 你），
因为字体里一个码位只有一个字形，不需要「条目号」这种人为序号。
抽取器**有意不收 CJK 兼容表意（F900–FAFF）与兼容补充（2F800–2FA1F）**：
它们的字形与统一表意文字重复，收了会让「一个现代字一个码位」变成一对多。

**两层宋体是地区变体，码位会重叠**：`songti` 与 `songti-tc` 的键都是现代字码位，
同一码位两层都有字形，差异主要在扩展 B 区的繁体异体码位（`songti` 52 个、`songti-tc` 1,705 个）。
要「简体优先」用 `songti`，要繁体异体用 `songti-tc`；**不要按码位把两层拼在一起**。

**黑体·港是香港標準字形**（Chiron Hei HK），与大陆写法在约两千字上不同。
它不是「同一个字形的另一种写法」，当成大陆字形用会出错。

## 出处与校验

`glyphs/provenance/<书体>.jsonl` 一行一条，一个文件一条。骨架层记：来源、来源 URL、
上游路径、上游 sha256、本地 sha256、许可、署名文字、取回时刻；
派生件（甲骨轮廓与六个字体层）另记 `derived_from` / `derived_from_sha256` /
`transform` / `tool`。字体层另有 `font_name` / `font_version`。

```bash
python src/glyph_stats.py                 # 统计汇总：各层许可、上游原件数、改动分布
python src/verify_provenance.py           # 校验每个文件的 sha256 与记录是否一致
python src/outline_oracle.py --selftest   # 轮廓层的几何自检
python src/license_audit.py               # 逐层「能不能安全发布」的机检
python src/verify_font_licenses.py --license-dir glyphs/kaishu --font <字体>
```

`verify_provenance.py` 以退出码 1 报告任何不符，可直接用于 CI。它同时复核三件事：
每条的 `license` 是否在允许名单内（ND / NC / 无许可一律不许在库里）、
每条记录的书体是否与所在文件名一致、每层 `index.csv` 与出处记录是否三账对得上。

## 重新生成

```bash
# 1) 甲骨：导入骨架（需要一个解包后的上游数据集副本），再由骨架派生轮廓
python src/import_oracle_jgw.py --dataset-dir <解包目录> [--zenodo-dir <Zenodo 原件解包目录>]
python src/outline_oracle.py

# 2) 篆书层：字表来自篆书全量登记表
python src/fetch_zdic_glyphs.py --script xiaozhuan --from-seal-registry --out tmp/zdic/xiaozhuan --workers 5 \
    --source-dataset "汉典（zdic.net）篆文字形"
python src/clean_zdic_glyphs.py --manifest tmp/zdic/xiaozhuan/manifest.json --out tmp/zdic/xiaozhuan-clean
python src/merge_glyph_manifests.py --manifest tmp/zdic/xiaozhuan-clean/manifest.json --out tmp/zdic/xiaozhuan-final
python src/assign_seal_codepoints.py --manifest tmp/zdic/xiaozhuan-final/manifest.json \
    --out tmp/zdic/xiaozhuan-seal --zheng-table tmp/research/seal-modern-to-zheng.txt
python src/import_glyph_layer.py --manifest tmp/zdic/xiaozhuan-seal/manifest.json --layer seal --key-mode seal_codepoint

# 3) 篆书全量码位登记表（含玉/王偏差修正）
python src/build_seal_registry.py

# 4) 现代书体六层：从 OFL 字体提取轮廓，再按 Unicode 码位入库
python src/extract_font_glyphs.py --font <字体.ttf> --layer kaishu --out tmp/font/kaishu --location wght=400
python src/import_glyph_layer.py --manifest tmp/font/kaishu/manifest.json --layer kaishu --key-mode unicode_codepoint

# 5) 许可证据与发布审计
python src/verify_font_licenses.py --license-dir glyphs/kaishu --font <字体.ttf>
python src/build_font_license_evidence.py --font-dir <本地字体目录>
python src/license_audit.py

# 6) 浏览页（数据变了才需要）
python src/build_viewer.py
```

导入只替换自己那一层（`layer="skeleton"`）的记录，不会动派生层；
写入的是 `glyphs/provenance/<书体>.jsonl`，不会碰别的书体的记录。

## 许可

| 范围 | 许可 |
|------|------|
| `glyphs/oracle/` 的 JGW 批（1,203 骨架 + 1,203 轮廓） | **CC BY 4.0**（全文见根 `LICENSE`） |
| `glyphs/oracle/` 的汉典批（10,213 拓片摹本）、`glyphs/bronze/`、`glyphs/seal/`、`glyphs/clerical/` | **CC0 1.0**（全文见 `LICENSE-DOCS`） |
| `glyphs/kaishu/` `glyphs/xingshu/` `glyphs/caoshu/` `glyphs/songti/` `glyphs/songti-tc/` `glyphs/heiti-hk/` | **SIL OFL 1.1**（各层目录的 `OFL.txt`） |
| `glyphs/seal/external.csv` 中派生于 Unicode `SealSources.txt` 的列 | **Unicode License v3**（声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)） |
| `glyphs/seal/external.csv` 的 `upstream_*` 列 | **不适用**：只是指向外部仓库的指针 |
| `README.md`、`AGENTS.md`、`THIRD_PARTY_NOTICES.md`、各层 `index.csv` | **CC0 1.0**（无义务，随便用） |
| `src/**`、`viewer/**` | **CC0 1.0**（无义务，随便用） |

根 `LICENSE`（CC BY 4.0）只覆盖 CC BY 4.0 那一层（甲骨 JGW 骨架与派生轮廓），
不覆盖 CC0、OFL 与 Unicode 授权的材料。用 `glyphs/oracle/` 下的 JGW 批数据**必须署名**并注明
是否做过修改，署名文字见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；
汉典各层与篆书层是 CC0，**没有义务**，本仓库也不对它附加任何限制。

**OFL 层有四条必须守住的约束**：整层只能按 OFL-1.1 分发（不得改成 CC0 / CC BY）、
必须随附 `OFL.txt` 与版权声明、不得使用被保留的字体名（本库六个字体都没有 RFN）、
不得单独销售字体软件本身（本仓库不销售任何东西）。
OFL 第 5 条要求衍生作品「完全按本许可分发，且不得按其他许可分发」——
所以你拿这六层的字形做出来的东西，也要按 OFL 分发。

## 第三方权利

三千年前的甲骨文与《说文》篆形本身不产生著作权；现代书体的字形轮廓来自 OFL 字体，
其权利已由字体版权人按 OFL 授予。本仓库只对自己新增的部分（轮廓派生、索引、脚本、
浏览页、文档）主张权利，**不对字形本身及其来源摹本主张任何权利**。
若你是相关权利人并认为本仓库内容侵犯了你的权利，请通过 Issue 或 <1279190619@qq.com>
联系我们，我们会在核实后移除相应条目——`glyphs/provenance/` 一层一个文件、一个文件一条记录，
单条字形可以独立移除而不影响其余内容。

详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 目录

```
hanzi-glyphs-svg/
  AGENTS.md                  本仓库的约定（改结构先改它）
  README.md                  本文件
  THIRD_PARTY_NOTICES.md     第三方署名、改动声明、权利保留
  LICENSE                    CC BY 4.0 全文（只覆盖 CC BY 那一层数据）
  LICENSE-CODE               CC0 1.0 说明（代码与页面）
  LICENSE-DOCS               CC0 1.0 全文（文档；篆书层的 CC0 也引这一份）
  LICENSE-DATA               逐层数据/文档/代码许可说明
  glyphs/
    provenance/              出处记录，一层一个文件
    oracle/                  甲骨文：JGW 骨架 + 汉典拓片摹本 + index.csv + outline/（派生）
    bronze/                  金文字形 + index.csv
    seal/                    篆书字形 + index.csv + external.csv（全量码位登记表）
    clerical/                隶书字形 + index.csv
    kaishu/ xingshu/ caoshu/ 现代书体（OFL）：字形 + index.csv + OFL.txt + SOURCE.md
    songti/ songti-tc/ heiti-hk/
  src/                       脚本：导入 / 抽取 / 派生 / 校验 / 生成浏览页
    licenses/                第三方许可原文（供逐条款比对）
  viewer/index.html          静态浏览页（生成的，勿手改）
```

## 致谢

这些字形不是我们画的，是很多人一笔一笔留下来的：

- **汉典（zdic.net）**：把甲骨、金文、小篆、隶书逐字整理成矢量字形，并以 CC0 释出。本库的古文字形大多来自这里。
- **李庆生、边玉林**（浙江传媒学院）：1,203 个甲骨文字形的参数化矢量数据集，CC BY 4.0 公开。
- **Ma Shan Zheng、Zhi Mang Xing、Liu Jian Mao Cao** 三个书法字体项目（各依其书法家的手迹），
  **Google Fonts / Adobe**（Noto Serif SC、TC），**Chiron Fonts**（Chiron Hei HK）：
  楷、行、草、宋、黑六层的轮廓来源。
- **郭沫若、胡厚宣**等《甲骨文合集》的编纂者，**中国社会科学院考古研究所**《殷周金文集成》的编者，
  历代**拓本与摹本**的制作者，《说文解字》两千年来传抄、刊刻的人——他们大多没有留下名字。
- **Unicode Consortium**（篆书区块与 `SealSources.txt`）、**OpenCC**（篆书反查表）、
  **fontTools**：码位与工具。

我们能做的，是把每一个字形的来路记清楚。

