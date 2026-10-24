# AGENTS.md — hanzi-glyphs-svg

汉字库：把汉字字形 **SVG** 建全，并保证 **出处可追溯**。

## 通用技能库

跨仓库技能统一在 `D:\yohan\skills\`（目录见其 `INDEX.md`）。执行通用任务（配图、发布、写规范/规格/方案文档等）时，先查技能库有无对应技能：有则读其 `SKILL.md` 并遵循，技能库是这些规范的唯一事实源；没有才用本仓库自带做法。仓库特有的事实（文章放哪、本仓库主题）仍以本文件为准。

## 用途

- 收录汉字 SVG 字形（甲骨文、篆书）
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
    provenance/      # 出处记录，一层一个文件：oracle.jsonl / seal.jsonl
    oracle/          # 骨架 + index.csv + outline/（派生层）
    seal/            # 篆书字形 + index.csv + external.csv（全量码位登记表）+ README.md
  src/               # 脚本（导入/派生/校验/生成浏览页）
  viewer/            # 静态浏览页（生成的，勿手改）
  .github/workflows/ # GitHub Pages 部署 + CI 校验
```

保持精简，勿随意增加顶层目录。

## 书体目录名

| 目录 | 中文 | 英文（学术/国际常用） |
|------|------|----------------------|
| `glyphs/oracle/` | 甲骨文 | Oracle bone script |
| `glyphs/seal/` | 篆书 | Seal script |

新增书体时沿用同一套目录结构（`<书体>/index.csv` + `provenance/<书体>.jsonl`），
并在本文件补上该层的键规则与许可。

## 字形文件

文件名按书体分两种，因为**只有小篆在 Unicode 里有自己的码位**：

| 书体 | 文件名 | 键 |
|------|--------|----|
| `glyphs/seal/` | `<Unicode>.svg` | 篆书区块码位，**5 位大写十六进制**，如 `3D000.svg` = U+3D000（一） |
| `glyphs/oracle/` | `<glyph_id>.svg` | 源字库条目号，**4 位十进制**，如 `0001.svg` |

- **甲骨文在 Unicode 里没有自己的码位**，`<Unicode>.svg` 表达不了它；而且一字多形是常态
  （JGW 那批 1,203 条里，33 个现代字各对应 2 个条目），所以改用**条目号**做键。
- **篆书用篆书区块自己的码位做键**（U+3D000–U+3FC3F），不是现代字码位：同一个现代字在
  篆书区块里有多个码位（正篆 + 重文），篆书区块 **11,328** 个码位只对应 **11,231** 个现代字，
  其中 **93 个现代字对应多个码位**（89 个 ×2、4 个 ×3，共多出 96 个码位），
  按现代字命名会撞车。现代字码位放在 `index.csv` 里反查。
- **现代字码位一律写成 6 位大写十六进制**（`004E04`），**篆书码位一律写成 5 位**
  （`3D000`）。抓取脚本按 `ord(char)` 的十六进制给文件命名，宽度不统一
  （`4E04` 与 `0053E1` 都出现过），合并清单时必须先归一，否则同一个字会出现两条记录。
- 每个书体目录下放一份 `index.csv`，提供「现代字 / 码位 → 文件名」反查。
- `glyphs/oracle/` 的文件是上游的**逐字节副本**：不重新编码、不归一化 viewBox。
- 书体目录下可以有**派生层**子目录。目前有 `glyphs/oracle/outline/`：与骨架**同名、同 viewBox**
  的可填充轮廓（把 `stroke` 换成真正的填充区域），由 `python src/outline_oracle.py` 生成。
  **骨架是溯源锚点**（能逐字节对回上游），轮廓是给上层渲染用的派生件；改了骨架必须重跑生成。
- **登记表可以与字形并存**：`glyphs/seal/external.csv` 登记 Unicode 篆书区块**全部** 11,328 个
  码位的身份（现代字、部首、四本《说文》流水号）与上游文件指针，
  由 `python src/build_seal_registry.py` 生成，字段说明见 `glyphs/seal/README.md`。
  它的 `upstream_*` 列只是指针，**不构成分发**，因此不受上游许可状态影响；
  本地字形的出处以 `glyphs/provenance/seal.jsonl` 为准，两者按 `codepoint` 关联。
- **条目号必须由确定性规则给出**，不能按「抓取完成顺序」编号：同一份字表跑两次若网络抖动
  不同，编号就会漂移，整层立刻失去可追溯性。规则：按「现代字码位 → 来源编号 → 文件名」
  排序后重排为 1..N。条目号是**整层内容的函数**，层里增删字形后会整体重排，
  所以下游要按 `index.csv` 解析，**不要硬编 `NNNN.svg` 文件名**。

## 硬规则

1. **无出处，不入仓库**。说不清从哪来的，删除。
2. 出处写在 `glyphs/provenance/<书体>.jsonl`（一行一条，一个文件一条；文件名必须等于书体名）：  
   必填 `path`、`sha256`、`license`，时间字段 `retrieved_at`（派生件用 `generated_at`），
   以及至少一个来源 URL；另记 `script`、`layer`、`glyph_id`、`source_path`、
   `source_sha256`、`attribution`。  
   `retrieved_at` 记的是**从上游取回的时刻**：优先用抓取清单里逐字形的值，
   清单没记才用入库时刻——**重新导入一遍不等于重新从上游取一次**。  
   `source_doi` **上游有 DOI 才记**——JGW 批次有 DOI，汉典没有。  
   派生件（`layer` 不是 `skeleton`）另记 `derived_from`、`derived_from_sha256`、`transform`、`tool`。  
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
  `glyphs/seal/` 为 **CC0-1.0**。
- **根 `LICENSE`（CC BY 4.0）只覆盖 CC BY 4.0 那一层**，不覆盖 CC0 与 Unicode 授权的材料；
  完整地图在 `README.md` 的「许可」一节与 `THIRD_PARTY_NOTICES.md`。
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

## 当前状态

| 书体 | 状态 |
|------|------|
| 甲骨文（JGW 批） | **1,203** 骨架 + **1,203** 轮廓（CC BY 4.0），provenance 与 `index.csv` 齐全 |
| 篆书 | **10,591** 字形（CC0 1.0），键 = 篆书区块码位，覆盖 **10,591 / 11,328**（93.5%）；另有 `external.csv` 登记全量 11,328 个码位 |

- `glyphs/provenance/` 现为 **12,997 条**（oracle 2,406 + seal 10,591）；
  `verify_provenance.py` 机读校验 **0 问题**，`check_glyphs.py` 各层 **0 问题**。
- 甲骨文特例：`0380`、`0916` 无对应现代汉字；`1180`（妞）身份为 `provisional`。
- 篆书层的键、覆盖率、正篆/重文的取舍规则，以及一处对 Unicode `SealSources.txt`
  的偏差修正（U+3D06D 归「玉」而非「王」）见 `glyphs/seal/README.md`。
- JGW 上游未披露其字形所依据的第三方来源；篆书层底本为《说文》刻本系统。
  两处残余风险都写在 `THIRD_PARTY_NOTICES.md`。

## 脚本

| 脚本 | 作用 |
|------|------|
| `src/import_oracle_jgw.py` | 导入甲骨文骨架 |
| `src/outline_oracle.py` | 骨架 → 可填充轮廓（`--selftest` 几何自检） |
| `src/fetch_zdic_glyphs.py` | 抓汉典「书法」字形实例，出 `manifest.json`；题记按书体分派解析器 |
| `src/build_char_table.py` | 生成抓取用的字表（说文登记表 ∪ CJK 基本区/扩展 A 区） |
| `src/clean_zdic_glyphs.py` | 洗掉汉典字形里的近白水印层，产出可入库的字形与清单 |
| `src/merge_glyph_manifests.py` | 合并多批清单（`--keep-multi` 保留一字多形） |
| `src/build_seal_zheng_table.py` | 生成「现代字 → 正篆码位」反查表（含 93/93 交叉验证） |
| `src/assign_seal_codepoints.py` | 给小篆字形指派篆书区块码位（正篆/重文取舍） |
| `src/import_glyph_layer.py` | 按清单导入任一书体层（许可闸门 + provenance + index.csv + 孤儿体检） |
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
