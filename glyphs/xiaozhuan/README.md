# `glyphs/xiaozhuan/` —— 小篆层（小學堂批）

《說文解字》系小篆的字形，来自**中研院「小學堂」小篆資料庫**（CC0 1.0）。
上游给的是位图，本仓库**自动描摹**成 SVG，是派生件。

规模：**7,284** 个字形，键是**本仓库条目号**（≥4 位十进制，如 `0001.svg`），
与 `glyphs/qinwenzi/` 同款。

## 与「篆书」层（`glyphs/seal/`）的关系

**两批材料，不混用、不互相补位**：

| | `glyphs/seal/`（篆书） | `glyphs/xiaozhuan/`（本层） |
|---|---|---|
| 来源 | 漢典「书法」小篆实例 | 小學堂「小篆」庫位图 |
| 材料 | 漢典绘制的矢量字形 | 北師大說文小篆字体渲染的位图 |
| 键 | Unicode 篆书区块码位（5 位十六进制） | 本仓库条目号 |
| 上游字体槽位 | `source_id` = `27_<槽位>` | 字体号 27/28 的同一套槽位编号 |

两层的字体槽位编号**同构**（同一套《說文》小篆槽位），但**槽位同构不等于材料相同**——
同一槽位两边是各自绘制的字形。本层的判重键仍是「(现代字, 字形键)」。

## 文件

| 文件 | 内容 |
|------|------|
| `<条目号>.svg` | 字形，文件名 = 本仓库条目号 |
| `index.csv` | 本地字形索引：一行一个字形（条目号 → 文件 → 现代字 → 出處 → sha256） |
| `books.csv` | **文獻标识对照表**：部別（「說文‧人部」）与重文類別（「說文古文」等）→ 收录与否 |
| `../provenance/xiaozhuan.jsonl` | 逐条出处记录：上游位图、描摹参数、`trace_iou`、许可、署名 |

## 键：条目号

这一层用**本仓库条目号**做键，不用现代字码位——《說文》小篆**一字多形**：
同一个现代字有正篆、古文、籀文、或體、篆文、俗字、奇字多个码位/槽位，
按现代字命名会撞车（实测 7,284 个字形只对应约 6,305 个现代字）。

条目号的规则是仓库通用规则：**按「现代字码位 → 来源编号 → 文件名」排序后重排 1..N**，
所以它是**整层内容的函数**——层里增删字形会整体重排。
**下游要按 `index.csv` 解析，不要硬编 `NNNN.svg` 文件名。**

## 文献标识：没有出處表，标识取自字头自己的「說文」栏

小學堂小篆庫**没有出處表页**（实测首页无该链接）。
上游自己给的文献信息就是字頭行里的「說文」欄，两类：

| 类别 | 形式 | 实例数 |
|---|---|---|
| 部別 | 「說文‧一部」……「說文‧亥部」共 384 个 | 正篆为主 |
| 重文類別 | 說文古文 / 說文籀文 / 說文或體 / 說文篆文 / 說文俗字 / 說文奇字 | 古文 293、或體 350、籀文 148…… |

`books.csv` 由 `python src/build_layer_books.py --db xiaozhuan` 从抓取索引生成，
**398 个标识全量登记**（索引里出现过的全部，不只是选中批次的 390 个——
缺一个，收录闸门就会把整桶误挡）。`corpus_full` 照抄上游标识，不代它编全称。

## 现代字身份：反查只有路线 A 可用

小學堂的「楷書字頭」有时是**字体排版槽位码位**（私用區），不是 Unicode 汉字码位。
本层的身份反查**只有路线 A（說文小篆槽位）可用**：

- **路线 D（底本页.行）不适用**：本层没有页.行体系的底本（《說文》以卷.部首.頁记，
  与汉典那种「一页一行一个字」的摹本底本不是一套粒度）；
- **路线 C（字形键）不适用**：`glyphs/seal/` 的键是篆书区块码位，不是「字体号_槽位」，
  没有可直接对照的 index（同构槽位只在 provenance 的 `source_id` 里）；
- **路线 A（說文小篆槽位）**：字頭行里「北師大說文小篆」（字体号 27）的槽位
  与 `glyphs/seal/index.csv` 的 `source_id` 同一套，槽位对上即身份接上。

实测 1,739 个私用區字頭：**1,587** 个由路线 A 补回真身份（与 seal 层 index 逐条核对
零不一致），**152** 个走**临时身份**。全层身份分布：

| `identity_confidence` | 条数 | 含义 |
|---|---|---|
| （空）/ `xxt-head` / `reverse-lookup` | 7,061（站点直给 5,462 + 反查补回 1,599） | 站点直接给出真漢字，或由路线 A 反查补回 |
| `pua-slot` | 223 | **临时身份**：只有槽位，现代字待考；`modern_char` 与 `unicode` **都留空** |

**私用區码位不是汉字码位，不得当汉字引用。** 临时身份条目的身份线索记在
`identity_confidence` + `modern_char_slot` 两个字段里（照甲骨层先例）。

## 上游原件是位图，本地 SVG 是派生件

每条 provenance 记录另记：

- `derived_from`（上游位图的取图 URL）、`derived_from_sha256`（上游位图校验值）；
- `transform`（描摹参数：marching squares + Douglas-Peucker 容差 + Chaikin 平滑轮数）；
- `tool`（脚本与版本）；
- `trace_iou`：**本地 SVG 回光栅化与上游位图墨迹掩膜的 IoU**（保真核验用）。

**描摹参数**：`size=300 / eps=0.525 / smooth=1`。
**尺寸上限已变（2026-11-03 实测）**：ShowImage.ashx 的 size 上限从 400 降到 300
（>300 一律 400 Bad Request）；eps 按分辨率等比缩放（0.7 × 300/400 = 0.525），
维持「容差相对字形尺度不变」的设计。

**实测**（7,284 件描摹件）：IoU 最低 0.9744、p05 0.9840、中位 0.9867，
合格 7,284 件、警戒 0、失败 0——
门槛（单条 ≥ 0.97、层级 p05 ≥ 0.96、失败率 ≤ 1%）全部满足。

## 出处链条

```
《說文解字》（東漢 許慎）→ 大徐本系刻本 → 北師大說文小篆字体的字形设计
                        → 中研院「小學堂」字形圖片（位图）→ 本仓库自动描摹 → SVG
```

`index.csv` 的 `source_book` 记**部別/重文類別**（上游原文标识），
`source_base_pages` 记字頭的字典页信息（《說文解字》卷.部首.頁 等，上游原样给出）。

底本《說文解字》是公有领域材料；上游字体的字形设计权由中研院以 CC0 1.0 处置
（声明原文存档在 `src/licenses/xiaoxuetang-CC0-1.0-statement.{md,html}`）。

## 复跑

```powershell
# 1) 取图（间隔 1 s + 并发 2 路；尺寸上限 300，2026-11-03 实测）
powershell -NoProfile -ExecutionPolicy Bypass -File src/run_xxt_crawl.ps1 -Stage images -Db xiaozhuan -Size 300 -Delay 1 -Lanes 2 -ShapeList tmp/xxt/xiaozhuan/fetch-keys.txt

# 2) 描摹 → SVG
python -X utf8 src/trace_xiaoxuetang_glyphs.py --input tmp/xxt/xiaozhuan/img --out tmp/xxt/xiaozhuan/svg --check --eps 0.525 --smooth 1 --manifest tmp/xxt/xiaozhuan/manifest.jsonl

# 3) 文献对照（无出處表，从索引生成）
python -X utf8 src/build_layer_books.py --db xiaozhuan

# 4) 清单 → 合并 → 入库
python -X utf8 src/run_xxt_pipeline.py --db xiaozhuan --stage manifest
python -X utf8 src/run_xxt_pipeline.py --db xiaozhuan --stage merge
python -X utf8 src/run_xxt_pipeline.py --db xiaozhuan --stage import --yes
python -X utf8 src/run_xxt_pipeline.py --db xiaozhuan --stage verify
```
