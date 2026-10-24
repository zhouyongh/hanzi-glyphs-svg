# `glyphs/seal/` —— 篆书层

本目录有两样东西：**本仓库收录的篆书字形**（来自汉典「书法」小篆，CC0 1.0），
以及 **Unicode 篆书区块的全量码位登记表** `external.csv`（登记上游[開元小篆](https://github.com/frankslin/kaiyuan-small-seal-font)
的文件指针，**本仓库不复制上游的字形内容**）。

## 文件

| 文件 | 内容 |
|------|------|
| `<码位>.svg` | **10,591** 个篆书字形，文件名 = Unicode 篆书区块码位（5 位大写十六进制），如 `3D000.svg` = U+3D000（一） |
| `index.csv` | 本地字形索引：**10,591** 行，一行一个字形（码位 → 文件 → 现代字 → 出处） |
| `external.csv` | 篆书区块**全量**码位登记表：**11,328** 行，一行一个篆书码位 |
| `external.meta.json` | 登记时钉住的上游仓库、分支、commit 与统计，含偏差修正汇总 |

## 两张表怎么配合

两张表都按 `codepoint` 关联，用途不同：

| | `index.csv` | `external.csv` |
|---|---|---|
| 范围 | **本仓库实际收录的** 10,591 个码位 | 篆书区块**全部** 11,328 个码位 |
| 回答的问题 | 「这个篆书码位，我们手上有哪个文件？」 | 「这个篆书码位是谁、属哪一部、在四本《说文》里的流水号是多少？」 |
| 额外列 | 文件名、sha256、出处作品与编号、来源 URL | 部首归属、四本流水号、上游指针、偏差修正说明 |

`external.csv` 的 `upstream_path` / `upstream_blob_sha1` **只是指向外部仓库的指针**，
不是本目录里那些字形的出处——本地字形的出处以 `glyphs/provenance/seal.jsonl` 为准。

### `external.csv` 的列

| 列 | 含义 |
|----|------|
| `codepoint` | Unicode 篆书区块码位（U+3D000–U+3FC3F） |
| `unicode` | 对应的**现代汉字**码位，6 位大写十六进制（与 `AGENTS.md` 的 `index.csv` 约定一致） |
| `modern_char` | 对应的现代汉字 |
| `radical_no` / `radical_cp` | 《说文》540 部首编号 / 部首自身的篆书码位 |
| `ccz` `dyc` `qjz` `thx` | 该字在四个《说文》版本中的**流水号**：陈昌治本 `C-#####`、段玉裁本 `D-#####`、祁寯藻本 `K-#####`、藤花榭本 `TH-#####`（来源：Unicode `SealSources.txt`） |
| `upstream_path` | 上游仓库里的文件路径，如 `glyphs/u3D000.svg`（**为空 = 上游尚无此字形**） |
| `upstream_blob_sha1` | 上游该文件的 git blob SHA-1，用来钉住「我们指向的是哪个字节」 |
| `note` | 两类说明：对 Unicode 原文做偏差修正的说明（目前仅 1 行，见下）；以及**这个码位为什么没入库**（`未入库：上游有字形…` / `未入库：无来源…`） |

## 键：为什么用篆书区块码位，不用现代字码位

同一个现代字在篆书区块里可能有多个码位（正篆 + 重文 / 异体），
按现代字命名会撞车。篆书区块自己的码位是唯一且稳定的键，
所以 `glyphs/seal/` 下的文件名是 `<5 位十六进制>.svg`，
现代字码位放在 `index.csv` 与 `external.csv` 里反查。

Unicode 篆书区块共 **11,328** 个码位，对应 **11,231** 个现代字：
**93** 个现代字对应多个码位（89 个 ×2、4 个 ×3）。

## 正篆与重文：每个字只落一个码位

汉典对同一个字往往给多个实例（《说文》正篆、古文、籀文、或体……），
本层**每个现代字只收一个实例**，落在**正篆**码位上，其余码位留空。
正篆码位的判定规则：

1. 《说文》主序列（`kSEAL_THXSrc` 为 `TH-#####`）优先于附录（`TH-X###` / `TH-Y###`）；
2. 同组内比收录版本数（说文四本收录此字的次数）；
3. 再比码位大小（小者在前）。

这条规则与 Unicode 核心规范 §18.14 的码位排序规则（按 540 部、组内依 THX 原书顺序）
一致。规则实现在 `src/build_seal_zheng_table.py`（取 Unicode `SealSources.txt` 与
OpenCC `SealCharacters.txt` 生成反查表）。

**交叉验证**：把同一张表与 OpenCC 的 `SealCharacters.txt` 反查首选对比，
93 个多码位字里 **93 个全部一致**（脚本每次运行都会重跑这项对拍，不一致就报警）。

本层 10,591 个字形中，有 86 个字的篆书区块另有码位（重文/异体），
这些码位留空，`index.csv` 与 `provenance/seal.jsonl` 的 `seal_note` 字段记明是哪些。

## 覆盖率

| 项 | 数量 |
|----|------|
| 篆书区块码位总数 | **11,328** |
| 本层收录 | **10,591**（**93.5%**） |
| 缺口 | **737**（其中 543 个上游[開元小篆](https://github.com/frankslin/kaiyuan-small-seal-font)有字形、194 个哪里都没有） |
| 无本地字形的现代字 | **640**（多为《说文》收录而汉典未提供小篆实例的生僻字） |

每个没入库的码位，`external.csv` 的 `note` 列都写明了原因：
「未入库：上游有字形（blob SHA-1 已登记），待上游补齐许可文件后导入」
（543 个）或「未入库：无来源（本层无字形，上游也无指针）」（194 个）。
看表就能分清哪些是**等上游**、哪些是**没辙**。

缺口对应的上游文件 URL 模板（`<commit>` 取 `external.meta.json` 的 `upstream_commit`）：

```
https://github.com/frankslin/kaiyuan-small-seal-font/blob/<commit>/<upstream_path>
```

## 一处对 Unicode 原文的偏差修正

`SealSources.txt` 用 `kSEAL_MCJK` 记录「这个篆书码位对应哪个现代汉字」，
其中 **U+3D06D 被记成 U+738B（王）**，但同一份文件里的部首结构自相矛盾：

| 码位 | `kSEAL_Rad` | 含义 |
|------|-------------|------|
| U+3D068 | `5.3D068` | 说文第 5 部「王」部的部首字 |
| U+3D06D | `6.3D06D` | 说文第 6 部「玉」部的部首字 |

说文 540 部里第 5 部是「王」、第 6 部是「玉」，两部相邻、各有各的首字。
若 U+3D06D 真是「王」的重文，它不可能同时是「玉」部的部首字。
OpenCC 的 `SealCharacters.txt` 也把 U+3D06D 记作「玉」。

**不修正的后果很实际**：按 Unicode 原始口径，「玉」没有任何篆书码位，
抓取名单里就根本没有「玉」这个字，篆书层永远缺一块。
本表按部首结构修正（**玉 → U+3D06D，王 → U+3D068**），
修正在 `src/build_seal_registry.py` 的 `MCJK_DEVIATIONS` 里写死，
逐行记在 `external.csv` 的 `note` 列，并汇总进 `external.meta.json` 的 `deviations`。
生成脚本会对修正前提做校验：若上游 `SealSources.txt` 将来改了这条映射，
脚本会直接报错要求复核，而不是默默沿用旧结论。

## 上游许可状态

截至登记时（见 `external.meta.json` 的 `generated_at`），上游[開元小篆](https://github.com/frankslin/kaiyuan-small-seal-font)
有两处缺口，都可在上游复现：

1. 授权语句只覆盖「**output fonts / 字型**」（其 README 与 `AGENTS.md` 原文），
   `glyphs/**` 被描述为流水线的生成物，**没有任何目录级许可标记**；
   而 OFL 对 "Font Software" 的定义要求文件被**明确标记**为受本协议约束。
2. 上游根目录的 `OFL.txt` **不是 SIL 官方 OFL 1.1 文本**：第 1、2 条与官方逐字相同，
   第 3–9 条与官方 5 条编号条款的最高相似度 **0.344**、第 10 条 **0.602**
   （最接近官方第 5 条）（实为 OFL 1.0 的条款 + 自订条款），
   官方最关键的**第 5 条**「不得按其他许可分发」缺失（官方第 3 条是 Reserved Font Name 条款），
   `TERMINATION` 段与
   `Reserved Font Name` 定义段也都没有。GitHub 对该仓库的许可识别是 `NOASSERTION`。

因此本仓库**不复制、不改作、不再分发**上游字形，只登记路径与 blob SHA-1。
上游补齐许可文件后，可用同一份表一次性导入。

另据上游 README 第 104 行原文：「公版底本：字形由公版刻本的掃描描出，
不參考現代篆書字型，著作權狀態清楚，**可依 OFL 自由修改、再發行**」——
这是**上游自己对字形可自由修改、再发行的表述**，也是日后补齐许可文件最自然的落点。

逐条比对结论见仓库根目录的 `THIRD_PARTY_NOTICES.md`。

## 登记表的完整性：已与上游逐条对账

2026-10-23 用 `python src/import_seal_kaiyuan.py --upstream-dir <上游目录> --verify-tree`
对过一遍：对账方式是读上游 **git tree 对象里的 blob SHA-1**（不下载字形内容），
结果是 **10,980 个有指向的字形全部一致，0 条不符**，也没有上游多出而未登记的文件。

复核方法（只需 tree，几百 KB）：

```bash
git init tmp/kaiyuan-trees && cd tmp/kaiyuan-trees
git remote add origin https://github.com/frankslin/kaiyuan-small-seal-font.git
git fetch --depth 1 --filter=blob:none origin <external.meta.json 里的 upstream_commit>
cd ../.. && python src/import_seal_kaiyuan.py --upstream-dir tmp/kaiyuan-trees --verify-tree
```

表里 `upstream_path` 为空的 **348** 个码位，是上游尚未产出字形的。

## 重新生成

```bash
# 重建全量码位登记表（含玉/王偏差修正）
python src/build_seal_registry.py            # 用缓存
python src/build_seal_registry.py --refresh  # 重新拉上游清单与 SealSources.txt
```

字形本身走汉典那条线，与金文/隶书同源：

```bash
# 0) 先出「现代字 → 正篆码位」反查表（Unicode SealSources.txt + OpenCC SealCharacters.txt）
python src/build_seal_zheng_table.py --out tmp/research/seal-modern-to-zheng.txt

# 1) 抓汉典小篆实例
python src/fetch_zdic_glyphs.py --script xiaozhuan --from-seal-registry --out tmp/zdic/xiaozhuan --workers 5
python src/clean_zdic_glyphs.py --manifest tmp/zdic/xiaozhuan/manifest.json --out tmp/zdic/xiaozhuan-clean
python src/merge_glyph_manifests.py --manifest tmp/zdic/xiaozhuan-clean/manifest.json --out tmp/zdic/xiaozhuan-final
python src/assign_seal_codepoints.py --manifest tmp/zdic/xiaozhuan-final/manifest.json \
    --out tmp/zdic/xiaozhuan-seal --zheng-table tmp/research/seal-modern-to-zheng.txt
python src/import_glyph_layer.py --manifest tmp/zdic/xiaozhuan-seal/manifest.json --layer seal --key-mode seal_codepoint
```

`build_seal_zheng_table.py` 会拿 OpenCC 自己的反查首选与本仓库的规则 R 逐个对拍，
**93 个多码位字全部一致**才算通过——这是对正篆判定规则的一次独立交叉验证。
