# AGENTS.md — hanzi-glyphs-svg

汉字库：把汉字字形 **SVG** 建全，并保证 **出处可追溯**。

## 通用技能库

跨仓库技能统一在 `D:\yohan\skills\`（目录见其 `INDEX.md`）。执行通用任务（配图、发布、写规范/规格/方案文档等）时，先查技能库有无对应技能：有则读其 `SKILL.md` 并遵循，技能库是这些规范的唯一事实源；没有才用本仓库自带做法。仓库特有的事实（文章放哪、本仓库主题）仍以本文件为准。

## 用途

- 收录汉字 SVG 字形（甲骨文、篆书、楷书、行书、草书、宋体、黑体）
- 供上层项目引用；本仓库不做游戏、不做业务应用
- 附一个**零构建的只读浏览页** `viewer/index.html`（由 `src/build_viewer.py` 生成，不是应用、
  不引入依赖、不复制字形文件），用于人工核验字形

## 目录

```
hanzi-glyphs-svg/
  AGENTS.md / README.md
  LICENSE            # CC BY 4.0 全文（只覆盖 CC BY 那一层）
  LICENSE-CODE       # MIT 全文（代码）
  LICENSE-DOCS       # CC0 1.0 全文（文档；篆书层的 CC0 也引这一份）
  LICENSE-DATA       # 数据/文档/代码许可说明
  THIRD_PARTY_NOTICES.md
  glyphs/            # 字形 SVG + 出处记录
    provenance/      # 出处记录，一层一个文件（文件名 = 书体名）
    oracle/          # 骨架 + index.csv + outline/（派生层）
    seal/            # 篆书字形 + index.csv + external.csv（全量码位登记表）+ README.md
    kaishu/ xingshu/ caoshu/ songti/ songti-tc/ heiti-hk/
                     # 现代书体（OFL）：字形 + index.csv + OFL.txt + SOURCE.md
  src/               # 脚本（导入/抽取/派生/校验/生成浏览页）
    licenses/        # 第三方许可原文（供逐条款比对）
  viewer/            # 静态浏览页（生成的，勿手改）
  .github/workflows/ # GitHub Pages 部署 + CI 校验
```

保持精简，勿随意增加顶层目录。

## 书体目录名

| 目录 | 中文 | 英文（学术/国际常用） |
|------|------|----------------------|
| `glyphs/oracle/` | 甲骨文 | Oracle bone script |
| `glyphs/seal/` | 篆书 | Seal script |
| `glyphs/kaishu/` | 楷书 | Regular script |
| `glyphs/xingshu/` | 行书 | Running script |
| `glyphs/caoshu/` | 草书 | Cursive script |
| `glyphs/songti/` | 宋体（简体） | Song / Ming, Simplified Chinese |
| `glyphs/songti-tc/` | 宋体（繁体） | Song / Ming, Traditional Chinese |
| `glyphs/heiti-hk/` | 黑体（港版） | Sans, Hong Kong |

> **两个宋体层**：同一书体的**地区变体**，键都是现代字 Unicode 码位，所以**码位会重叠**——
> 两层各自独立，`index.csv` 分开列。差异主要在**扩展 B 区的繁体异体码位**
> （`songti` 52 个，`songti-tc` 1,705 个）。下游要「简体优先」用 `songti`，要繁体异体用 `songti-tc`。
>
> **黑体·港**是**香港標準字形**（Chiron Hei HK），与大陆写法在约两千字上不同——
> 它不是「同一字形的另一种写法」，不能当大陆字形用。

新增书体时沿用同一套目录结构（`<书体>/index.csv` + `provenance/<书体>.jsonl`），
并在本文件补上该层的键规则与许可。

## 字形文件

文件名按书体分三种，因为**只有小篆在 Unicode 里有自己的码位**：

| 书体 | 文件名 | 键 |
|------|--------|----|
| `glyphs/seal/` | `<Unicode>.svg` | 篆书区块码位，**5 位大写十六进制**，如 `3D000.svg` = U+3D000（一） |
| `glyphs/oracle/` | `<glyph_id>.svg` | 源字库条目号，**4 位十进制**，如 `0001.svg` |
| `glyphs/kaishu/` `glyphs/xingshu/` `glyphs/caoshu/` `glyphs/songti/` `glyphs/songti-tc/` `glyphs/heiti-hk/` | `<Unicode>.svg` | 现代字的 Unicode 码位，**6 位大写十六进制**（补零），如 `004E04.svg` = 你 |

- **甲骨文在 Unicode 里没有自己的码位**，`<Unicode>.svg` 表达不了它；而且一字多形是常态
  （JGW 那批 1,203 条里，33 个现代字各对应 2 个条目），所以改用**条目号**做键。
- **篆书用篆书区块自己的码位做键**（U+3D000–U+3FC3F），不是现代字码位：同一个现代字在
  篆书区块里有多个码位（正篆 + 重文），篆书区块 **11,328** 个码位只对应 **11,231** 个现代字，
  其中 **93 个现代字对应多个码位**（89 个 ×2、4 个 ×3，共多出 96 个码位），
  按现代字命名会撞车。现代字码位放在 `index.csv` 里反查。
- **现代书体六层是从 OFL 开源字体提取轮廓的派生件**，用 `src/extract_font_glyphs.py` 生成。
  键是**现代字的 Unicode 码位**（6 位十六进制，补零），因为字体里一个码位只有一个字形。
  - 字形文件既是该层的 `layer="skeleton"`，也是**派生件**：每条记录另记
    `derived_from`（上游字体二进制）、`derived_from_sha256`、`transform`（轮廓 → SVG 的变换）、
    `tool`（fontTools 版本 + 脚本名）、`font_name` / `font_version`。
  - 每层目录里放**上游 `OFL.txt` 的逐字节副本**（OFL 第 2 条要求每份副本带版权声明与许可全文）
    和 `SOURCE.md`（家族名、版本、上游路径、字体 sha256、取回时刻、变换说明）。
  - **RFN 要查两处**：`OFL.txt` 抬头**和**字体二进制的 name 表。OFL 1.1 把 Reserved Font Name
    定义为「copyright statement 里写明的名字」，字体 name 表的 copyright 字段也算一份。
    只看许可文件会漏判；加 `--font <字体路径>` 才会连 name 表一起查。
  - **Noto CJK 与 Chiron 都是可变字体，默认实例不是 Regular**（Noto CJK 默认 ExtraLight，
    Chiron Hei HK 默认 `wght=200`）。提取必须显式 `--location wght=400`；**保真核验也必须用
    同一个实例**，否则「轮廓被外接盒罩住」的判据形同虚设。
  - **抽取器有意不收 CJK 兼容表意（F900–FAFF）与兼容补充（2F800–2FA1F）**：它们的字形与
    统一表意文字重复，收了会让「一个现代字一个码位」变成一对多。算「净增量」时要扣掉这两块。
- **现代字码位一律写成 6 位大写十六进制**（`004E04`），**篆书码位一律写成 5 位**
  （`3D000`）。抓取脚本按 `ord(char)` 的十六进制给文件命名，宽度不统一
  （`4E04` 与 `0053E1` 都出现过），合并清单时必须先归一，否则同一个字会出现两条记录。
- 每个书体目录下放一份 `index.csv`，提供「现代字 / 码位 → 文件名」反查。
- `glyphs/oracle/` 的文件是上游的**逐字节副本**：不重新编码、不归一化 viewBox。
- `glyphs/seal/` 的文件是汉典字形的**逐字节副本**（去水印的例外记在 `modifications`）。
- 书体目录下可以有**派生层**子目录。目前有 `glyphs/oracle/outline/`：与骨架**同名、同 viewBox**
  的可填充轮廓（把 `stroke` 换成真正的填充区域），由 `python src/outline_oracle.py` 生成。
  **骨架是溯源锚点**（能逐字节对回上游），轮廓是给上层渲染用的派生件；改了骨架必须重跑生成。
- **登记表可以与字形并存**：`glyphs/seal/external.csv` 登记 Unicode 篆书区块**全部** 11,328 个
  码位的身份（现代字、部首、四本《说文》流水号）与上游文件指针，
  由 `python src/build_seal_registry.py` 生成，字段说明见 `glyphs/seal/README.md`。
  它的 `upstream_*` 列只是指针，**不构成分发**，因此不受上游许可状态影响；
  本地字形的出处以 `glyphs/provenance/seal.jsonl` 为准，两者按 `codepoint` 关联。
- **条目号必须由确定性规则给出**（甲骨层用到条目号），不能按「抓取完成顺序」编号：
  同一份字表跑两次若网络抖动不同，编号就会漂移，整层立刻失去可追溯性。
  规则：按「现代字码位 → 来源编号 → 文件名」排序后重排为 1..N。条目号是**整层内容的函数**，
  层里增删字形后会整体重排，所以下游要按 `index.csv` 解析，**不要硬编 `NNNN.svg` 文件名**。

## 硬规则

1. **无出处，不入仓库**。说不清从哪来的，删除。
2. 出处写在 `glyphs/provenance/<书体>.jsonl`（一行一条，一个文件一条；文件名必须等于书体名）：  
   必填 `path`、`sha256`、`license`，时间字段 `retrieved_at`（派生件用 `generated_at`），
   以及至少一个来源 URL；另记 `script`、`layer`、`glyph_id`、`source_path`、
   `source_sha256`、`attribution`。  
   `retrieved_at` 记的是**从上游取回的时刻**：优先用抓取清单里逐字形的值，
   清单没记才用入库时刻——**重新导入一遍不等于重新从上游取一次**。  
   `source_doi` **上游有 DOI 才记**——JGW 批次有 DOI，汉典与字体层没有。  
   派生件（甲骨轮廓、现代书体六层）另记 `derived_from`、`derived_from_sha256`、
   `transform`、`tool`；字体层再加 `font_name` / `font_version`。  
   用 `python src/verify_provenance.py` 校验（它同时查许可白名单与「文件名 = 书体名」）。
3. **禁止编造链接**；网络来源须核实后再写入 provenance。
4. 正式字形须**贴近原字形**；禁止卡通美化当正式字形。
5. 未获原作者同意时，**如实写来源**，不冒充原创或隐瞒出处。
6. **一层一个 provenance 文件**：不要把别的书体的记录并进来。这样某一层的授权状态变化时，
   整层（字形 + 索引 + 出处）可以一起加入或一起移除，不必在一份全量文件里做手术。

## 许可

- 字形 SVG 的许可**逐书体**不同，以 `glyphs/provenance/<书体>.jsonl` 每条的 `license` 为准；
  使用方须按该许可署名，署名文字在 `attribution` 字段与 `THIRD_PARTY_NOTICES.md`。
- 目前 `glyphs/oracle/`（1,203 骨架 + 1,203 轮廓）为 **CC-BY-4.0**；
  `glyphs/seal/` 为 **CC0-1.0**；
  `glyphs/kaishu/` `glyphs/xingshu/` `glyphs/caoshu/` `glyphs/songti/` `glyphs/songti-tc/`
  `glyphs/heiti-hk/`（从 OFL 开源字体提取的轮廓）为 **OFL-1.1**。
- **根 `LICENSE`（CC BY 4.0）只覆盖 CC BY 4.0 那一层**，不覆盖 CC0、OFL 与 Unicode 授权的材料；
  完整地图在 `README.md` 的「许可」一节与 `THIRD_PARTY_NOTICES.md`。
- **OFL 派生层的四条硬约束**（缺一条就违约）：
  1. **整层以 OFL-1.1 分发**，不得改成 CC0、不得改成 CC BY；
  2. **随附上游 `OFL.txt` 与版权声明**（OFL 第 2 条要求每份副本都带这两样）——
     每层目录里放上游 `OFL.txt` 的逐字节副本，版权行抄进 `attribution`；
  3. **不得使用被保留的字体名（RFN）**（OFL 第 3 条）。已采用的六个字体在 `OFL.txt` 抬头
     与字体 name 表**两处**都无 RFN，所以层名用通用书体名，字体家族名只出现在
     `attribution` 与 `index.csv` 里；
  4. **不得单独销售字体软件本身**（OFL 第 1 条）——本仓库不销售任何东西。
  逐条证据用 `python src/verify_font_licenses.py --license-dir glyphs/<层> --font <字体>` 可复跑。
- **CC BY-ND / CC BY-NC / 无许可的来源不得作为字形来源入库**：矢量化与重绘都属于「改作」，
  ND 直接禁止；NC 与本库公开供引用的目的冲突。
- **底本权利未澄清的字形不得入库**：上游的 CC0 只处置它自己的权利；底本若是在版出版物，
  先拿到许可或明确的公有领域证据，再进 `glyphs/`。
- **本仓库自身的对外许可**：文档 **CC0 1.0**（`LICENSE-DOCS`，无义务），
  代码 `src/**`、`viewer/**` 为 **MIT**（`LICENSE-CODE`）；数据逐层不同，见上。
- 根 `LICENSE` 必须是 CC BY 4.0 的**逐字全文**：GitHub 的协议识别（Licensee）是把文件正文
  与已知协议做相似度比对，只写一句「本仓库采用 CC BY 4.0」的说明**不会被识别**。
- **不得给下游附加额外限制**（例如「仅限非商业」「禁止再分发」）：既违反 CC BY 4.0
  §2(a)(5)(B)，也会让自己的授权失效；对 CC0 材料同样不得附加。
- **外部登记表**（如 `glyphs/seal/external.csv`）里派生于 Unicode `SealSources.txt` 的列
  适用 **Unicode License v3**，其版权与许可声明已随 `THIRD_PARTY_NOTICES.md` 提供
  （该协议条件 (b) 允许把声明放在关联文档里）。
- **「哪些能安全发布」是可机检的**：`python src/license_audit.py` 逐层统计「许可能否覆盖
  本仓库的改作与再分发用法、发布时必须随附什么、这些义务是否已履行、还剩什么残余风险」，
  结果在 `glyphs/publish-license-audit.md`（另有 `.json` 机读版）。

## 当前状态

| 书体 | 状态 |
|------|------|
| 甲骨文（JGW 批） | **1,203** 骨架 + **1,203** 轮廓（CC BY 4.0），provenance 与 `index.csv` 齐全 |
| 篆书 | **10,591** 字形（CC0 1.0），键 = 篆书区块码位，覆盖 **10,591 / 11,328**（93.5%）；另有 `external.csv` 登记全量 11,328 个码位 |
| 楷书 | **6,763** 字形（OFL 1.1，Ma Shan Zheng），键 = 现代字码位；层内带 `OFL.txt` + `SOURCE.md` |
| 行书 | **6,763** 字形（OFL 1.1，Zhi Mang Xing） |
| 草书 | **6,763** 字形（OFL 1.1，Liu Jian Mao Cao） |
| 宋体（简） | **27,797** 字形（OFL 1.1，Noto Serif SC `wght=400`）；基本区 20,992 + 扩展 A 6,592 + 扩展 B/C/D/E/F 213 |
| 宋体（繁） | **17,665** 字形（OFL 1.1，Noto Serif TC `wght=400`）；**扩展 B 1,705 个是简体层没有的繁体异体码位** |
| 黑体（港） | **31,598** 字形（OFL 1.1，Chiron Hei HK `wght=400`）；**香港標準字形**，不是大陆字形的另一种写法 |

- `glyphs/provenance/` 现为 **110,346 条**（oracle 2,406 + seal 10,591 + 六个字体层 97,349）；
  `verify_provenance.py` 机读校验 **0 问题**，`check_glyphs.py` 各层 **0 问题**。
- 甲骨文特例：`0380`、`0916` 无对应现代汉字；`1180`（妞）身份为 `provisional`。
- 篆书层的键、覆盖率、正篆/重文的取舍规则，以及一处对 Unicode `SealSources.txt`
  的偏差修正（U+3D06D 归「玉」而非「王」）见 `glyphs/seal/README.md`。
- 字体六层的来源、许可证据与取舍见各层 `SOURCE.md`；逐条款证据汇总在
  `glyphs/font-license-evidence.md`（由 `src/build_font_license_evidence.py` 生成）。

## 脚本

| 脚本 | 作用 |
|------|------|
| `src/import_oracle_jgw.py` | 导入甲骨文骨架 |
| `src/outline_oracle.py` | 骨架 → 可填充轮廓（`--selftest` 几何自检） |
| `src/extract_font_glyphs.py` | 从 OFL 字体提取汉字轮廓为 SVG（fontTools → path；画布取墨迹并集） |
| `src/verify_font_licenses.py` | 逐条款核验 OFL 许可文本（正文比对 + RFN + 版权行）；加 `--font` 会连字体 name 表一起查 |
| `src/build_font_license_evidence.py` | 汇总各字体层的 OFL 1.1 逐条款证据成 `glyphs/font-license-evidence.md` |
| `src/eval_candidate.py` | 候选字体的**净增量评测**：相对已覆盖码位算还能补多少（扣掉兼容区块） |
| `src/license_audit.py` | **发布安全审计**：逐层「能不能安全发布」，出 `glyphs/publish-license-audit.md` + `.json` |
| `src/fetch_zdic_glyphs.py` | 抓汉典「书法」字形实例，出 `manifest.json` |
| `src/build_char_table.py` | 生成抓取用的字表（说文登记表 ∪ CJK 基本区/扩展 A 区） |
| `src/clean_zdic_glyphs.py` | 洗掉汉典字形里的近白水印层，产出可入库的字形与清单 |
| `src/merge_glyph_manifests.py` | 合并多批清单（`--keep-multi` 保留一字多形） |
| `src/build_seal_zheng_table.py` | 生成「现代字 → 正篆码位」反查表（含 93/93 交叉验证） |
| `src/assign_seal_codepoints.py` | 给小篆字形指派篆书区块码位（正篆/重文取舍） |
| `src/import_glyph_layer.py` | 按清单导入任一书体层（许可闸门 + provenance + index.csv + 孤儿体检；`--key-mode unicode_codepoint` 用于字体层） |
| `src/import_seal_kaiyuan.py` | 開元小篆导入（`--verify-tree` 只对账 blob SHA-1；许可闸门挡在落盘之前） |
| `src/build_seal_registry.py` | 生成篆书全量码位登记表（含玉/王偏差修正） |
| `src/build_viewer.py` | 生成只读浏览页（只给仓里真有的层出 Tab） |
| `src/check_glyphs.py` | 字形体检（XML 合法、viewBox、路径 bbox、退化检测） |
| `src/glyph_stats.py` | 字形库统计汇总（只读，`--json` 机读） |
| `src/verify_provenance.py` | 校验 provenance 与文件 sha256 |
| `src/fetch_seal_upstream.py` | 把開元小篆上游拉到本地查看（`fetch_kaiyuan.bat` 调它），只看不入库 |

## 协作

- 中文交流；标识符用英文
- 改结构先改本文件
- 提交信息说明「为什么」
