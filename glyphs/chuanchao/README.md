# `glyphs/chuanchao/` —— 傳抄古文字层

「漢以後歷代輾轉抄寫的先秦文字」：漢典「书法」「傳抄古文」栏的实例，
依漢典《服务条款》第四条以 **CC0 1.0** 释出；小學堂的同批字形（位图 →
自动描摹）依中研院《版權聲明》以 **CC0 1.0** 释出。

规模：**20,444** 个字形（漢典矢量件 **12,975** + 小學堂描摹件 **7,469**），
键是**本仓库条目号**（≥4 位十进制，如 `0001.svg`）。

## 文件

| 文件 | 内容 |
|------|------|
| `<条目号>.svg` | 字形，文件名 = 本仓库条目号 |
| `index.csv` | 本地字形索引：一行一个字形（条目号 → 文件 → 现代字 → 源書代号 → 位置 → sha256） |
| `books.csv` | **漢典口径**的文献代号对照表（131 行）：源書代号 → 全称、归属、收录与否 |
| `books_xxt.csv` | **小學堂口径**的出處表对照（132 行）：小學堂簡稱 → 全称 → 對應漢典代号（`zdic_code`） |
| `../provenance/chuanchao.jsonl` | 逐条出处记录：上游 URL、摹本底本頁.行、描摹参数、`trace_iou`、许可、署名 |

## 键：条目号

这一层用**本仓库条目号**做键，不用现代字码位——傳抄古文**一字多形**：
同一个现代字在不同源書里各有各的写法，按现代字命名会撞车。

条目号的规则是仓库通用规则：**按「现代字码位 → 来源编号 → 文件名」排序后重排 1..N**，
所以它是**整层内容的函数**——层里增删字形会整体重排。
**下游要按 `index.csv` 解析，不要硬编 `NNNN.svg` 文件名。**

## 分桶：按**源書代号**，一个源書一条

分桶维度是**源書代号**（题记开头的「海」「汗」「說」「說籀」「汗目」「石附」「石補」……）。
每个源書最多取 1 个实例（`--max-per-book 1`），每字最多 5 条（`--per-char 5`）。

**为什么按源書而不是按时代**：傳抄古文的题记里**没有时代**——它是漢以後歷代
輾轉抄寫的先秦文字，本身就没有单一时代，漢典也没标。

## 两边的文献代号是**两套体系**

| | 漢典 | 小學堂 |
|---|---|---|
| 代号数 | 21 | 132 |
| 獨有 | 「說籀」「汗目」「石附」「石補」（小學堂没有） | 119 个碑刻类代号（三體陰符經、山海經、楊大夫碑……）（漢典沒出過） |

所以本层有**两张表**：`books.csv`（漢典口径，收录闸门按它判）与
`books_xxt.csv`（小學堂口径，带 `zdic_code` 对照列）。
**对照判据是「两边的全称指向同一件材料」**——脚本从漢典清单取全称自动判定
（去标点空白后逐字相同才连上），不靠手写映射表：手写只对出 9 个，
自动判定对出 **17 个**。对不上就留空——**不猜**。

**「三」与「四」是同一部《古文四聲韻》的不同卷，是两个代号**——
全称逐字比对能把它们分开（实测「三」只匹配漢典「三」、不匹配「四」）。

## 源書代号的**全称未证实**，按上游原文记

`src/fetch_zdic_glyphs.py` 的 `CHUANCHAO_BOOK_CODES` 注释写得很清楚：
「各代号具体指哪部书**未证实**，按仓库惯例一律按上游原文记，不替它猜」。
所以 `books.csv` 里这四行的 `corpus_full` **留空**，层里的 `source_book`
就保留这个代号（「编一个书名比留个代码更糟」）。

## 出处链条

```
先秦文字 → 历代摹寫 → 漢以後的轉抄本 → 徐在國《傳抄古文字編》（綫裝書局，2006，全三冊）摹本
         → 漢典矢量化轉錄 / 中研院「小學堂」摹本位圖 → 本仓库自动描摹 → SVG
```

**出处粒度**：逐件记**源書代号**与**冊頁.行**（「中777.7」——帶冊次）。
冊頁.行 是**摹本底本**里的位置，与楚系的「頁.行」（《楚系簡帛文字編》）粒度不同，
**两层各认各的底本名**（`source_base_pages` 字段）。

## 上游原件是位图，本地 SVG 是派生件

小學堂那 7,469 件的 provenance 另记：

- `derived_from`（上游位图的取图 URL）、`derived_from_sha256`（上游位图校验值）；
- `transform`（描摹参数：marching squares + Douglas-Peucker 容差 + Chaikin 平滑轮数）；
- `tool`（脚本与版本）；
- `trace_iou`：**本地 SVG 回光栅化与上游位图墨迹掩膜的 IoU**（保真核验用）。

**描摹参数定案**：`size=400 / eps=0.7 / smooth=1`。

**实测**（7,972 件描摹）：IoU 最低 **0.9068**、p05 **0.9710**、中位 **0.9815**；
合格 7,670 / 警戒 301 / 失败 **2**——失败率 **0.026%**（门槛 ≤ 1%），
层级 p05 **0.9710**（门槛 ≥ 0.96），全部满足。

## 底本权利未澄清

**CC0 只处置中研院／漢典自己「字形圖片」的权利，不消灭底本著作权**——
《傳抄古文字編》是受著作权保护的出版物。
审计结论是「⚠️ 可发布（有残余风险，须随附底本说明）」。

## 复跑

```powershell
# 1) 取图（间隔 1 s + 并发 2 路；总速率压在 ~1.7 req/s）
powershell -NoProfile -ExecutionPolicy Bypass -File src/run_xxt_crawl.ps1 -Stage images -Db chuanchao -Delay 1 -Lanes 2 -ShapeList tmp/xxt/chuanchao/fetch-keys.txt

# 2) 描摹 → SVG
python -X utf8 src/trace_xiaoxuetang_glyphs.py --input tmp/xxt/chuanchao/img --out tmp/xxt/chuanchao/svg --check --eps 0.7 --smooth 1 --manifest tmp/xxt/chuanchao/manifest.jsonl

# 3) 身份反查（底本页.行为主、字形键为辅）
python -X utf8 src/resolve_pua_identity.py --index tmp/xxt/chuanchao/index.jsonl --out tmp/xxt/chuanchao/identity_map.jsonl --seal-index glyphs/seal/index.csv --zdic-provenance glyphs/provenance/chuanchao.jsonl --base-book 傳抄古文字編 --prefer D,C,A --zdic-shape-index glyphs/chuanchao/index.csv

# 4) 算要抓哪些位图（按层的规则先筛，再扣掉層里已有的）
python -X utf8 src/plan_xxt_fetch.py --db chuanchao --layer chuanchao --books-xxt glyphs/chuanchao/books_xxt.csv --zdic-manifest tmp/zdic/chuanchao-full/manifest.json --out-keys tmp/xxt/chuanchao/fetch-keys.txt --out-list tmp/xxt/chuanchao/fetch-list.tsv --out-selection tmp/xxt/chuanchao/fetch-selection.jsonl

# 5) 清单 → 合并 → 入库（整层替换：条目号重排后旧文件名全部作废）
python -X utf8 src/run_xxt_pipeline.py --db chuanchao --stage manifest
python -X utf8 src/run_xxt_pipeline.py --db chuanchao --stage merge
python -X utf8 src/run_xxt_pipeline.py --db chuanchao --stage import --yes
```

## 核验

```powershell
python -X utf8 src/verify_provenance.py --script chuanchao --quiet   # 出处与 sha256 对账
python -X utf8 src/check_glyphs.py glyphs/chuanchao                 # 字形体检
python -X utf8 src/check_glyphs.py --trace-fidelity                # 描摹保真（读 trace_iou）
python -X utf8 src/check_layer_rules.py --repo-root . --layer chuanchao  # 层的规则与不变量
```
