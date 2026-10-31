# `glyphs/qinwenzi/` —— 秦系簡牘层

秦系简牘（睡虎地秦簡一路）的文字字形。两批来源：

- **漢典「书法」栏里的秦系矢量件 1,594 个**——这些字形原先被歸在 `glyphs/clerical/`（隸書层），
  但字体是「中研院秦系簡牘文字重文*」，**书体由字体决定，不由材料决定**，已归位过来；
- **中研院「小學堂」秦系簡牘庫的位图描摹件 2,114 个**——上游给的是位图，本仓库
  **自动描摹**成 SVG。

两批都以 **CC0 1.0** 释出（漢典依其《服务条款》第四条、小學堂依《版權聲明》）。
字形键空间两库同构，同一键时**漢典矢量件優先**（合并器内建）——
1,056 件因此由漢典的矢量件顶掉了小學堂的描摹件，渲染更忠实、出处也更完整。

规模：**3,708** 个字形，键是**本仓库条目号**（≥4 位十进制，如 `0001.svg`）。

## 文件

| 文件 | 内容 |
|------|------|
| `<条目号>.svg` | 字形，文件名 = 本仓库条目号 |
| `index.csv` | 本地字形索引：一行一个字形（条目号 → 文件 → 现代字 → 出處 → sha256） |
| `books.csv` | **文献代号对照表**：出處簡號（「睡.秦51」这样的篇名简写）→ 全称、归属、收录与否 |
| `../provenance/qinwenzi.jsonl` | 逐条出处记录：上游位图、描摹参数、`trace_iou`、许可、署名 |

## 键：条目号

这一层用**本仓库条目号**做键，不用现代字码位——秦系简牘**一字多形**：
同一个现代字在不同篇目各有各的写法，按现代字命名会撞车。

条目号的规则是仓库通用规则：**按「现代字码位 → 来源编号 → 文件名」排序后重排 1..N**，
所以它是**整层内容的函数**——层里增删字形会整体重排。
**下游要按 `index.csv` 解析，不要硬编 `NNNN.svg` 文件名。**

## 键不是现代字码位：还有一批「临时身份」条目

小學堂有些字頭只给**字體排版槽位碼位**（私用區），不是 Unicode 汉字码位。
这类记录**不丢弃**，但也**不能拿私用區码位当汉字码位**——
它们的 `modern_char` 与 `unicode` **都留空**，身份线索记在两个字段里：

| 字段 | 含义 |
|---|---|
| `identity_confidence` | 身份是怎么定出来的：`seal-slot`（說文小篆槽位旁证）/ `pua-slot`（只有槽位，身份待考） |
| `modern_char_slot` | `<字体号>_<码位>`，槽位码位——身份未定时的唯一线索 |

**私用區码位不是汉字码位，不得当汉字引用。** 本层 3,708 条里：

| `identity_confidence` | 条数 | 含义 |
|---|---|---|
| （空） | 3,510 | 站点直接给出真漢字（或由反查补回），身份确定 |
| `seal-slot` | 30 | 身份由**說文小篆槽位**旁证定出，`modern_char_slot` 留作线索 |
| `pua-slot` | 168 | **临时身份**：只有槽位，现代字待考；`modern_char` 与 `unicode` **都留空** |

## 书体由字体决定，不由材料决定

「隸變」库里同时有「中研院隸書重文*」與「中研院秦系簡牘文字重文*」两种字体：
前者是隸書字形（归 `glyphs/clerical/`），后者是**秦系字形**（归本层）。
材料的朝代（出處簡號后面的「秦」「西漢」「東漢」）不管用。
分流靠 `src/build_xxt_manifest.py --font-allow`。

**隸書层原来混着 1,723 个秦系字体件**——那是**归类错误**，不是「同一个字有两种写法」。
已按本层的规矩归位（每（现代字, 文献代号）只留一条、每字最多 5 条）：

| 归位判定 | 条数 | 处置 |
|---|---|---|
| 同键（现代字 + 字形键相同） | 1,056 | **漢典矢量件顶掉小學堂描摹件**（层内替换，条数不变） |
| 同桶异键（同一字同一文献的另一处出现） | 128 | 不新增，沿用层里那一条 |
| 新桶 | 538 | **新增** |
| 超每字上限 | 1 | 不收 |

归位后每字最多 5 条、合并键 0 重复。复跑命令见 `tmp/move_qinwen_to_qinwenzi.py`
（prepare → 合并 → `import_glyph_layer.py --prune`）；
隸書层剔秦系件用 `src/rebuild_layer_manifest.py --exclude-font 71`。

## 出处链条

```
睡虎地秦墓出土的竹簡 → 整理出版本 → 《睡虎地秦簡文字編》（張守中 編著，文物出版社）摹本
                     → 中研院「小學堂」摹本位圖 → 本仓库自动描摹 → SVG
```

`index.csv` 的 `source_book` 记**所出材料**（《睡虎地秦墓竹簡‧為吏之道》这样的全称），
`source_references` 记**底本链条**（含《睡虎地秦簡文字編》的页.行）。

## 上游原件是位图，本地 SVG 是派生件

每条 provenance 记录另记：

- `derived_from`（上游位图的取图 URL）、`derived_from_sha256`（上游位图校验值）；
- `transform`（描摹参数：marching squares + Douglas-Peucker 容差 + Chaikin 平滑轮数）；
- `tool`（脚本与版本）；
- `trace_iou`：**本地 SVG 回光栅化与上游位图墨迹掩膜的 IoU**（保真核验用）。

**描摹参数定案**：`size=400 / eps=0.7 / smooth=1`（分辨率与容差同步放大，
产物体积不变而轮廓精度翻倍）。

**实测**（2,114 件描摹件）：IoU 最低 **0.9872**、p05 **0.9942**、中位 **0.9962**，
合格 2,114 件、警戒 0、失败 0——门槛（单条 ≥ 0.97、层级 p05 ≥ 0.96、失败率 ≤ 1%）
全部满足，离下限还有余量。

漢典那 1,594 件是**矢量原件**（不是派生件），没有描摹环节，也就没有 `trace_iou`。

## 底本权利未澄清

**CC0 只处置中研院对自己「字形圖片」的权利，不消灭底本著作权**——
《睡虎地秦簡文字編》是受著作权保护的出版物。
审计结论是「⚠️ 可发布（有残余风险，须随附底本说明）」。

## 复跑

```powershell
# 1) 取图（间隔 1 s + 并发 2 路；总速率压在 ~1.7 req/s）
powershell -NoProfile -ExecutionPolicy Bypass -File src/run_xxt_crawl.ps1 -Stage images -Db qinwenzi -Delay 1 -Lanes 2

# 2) 描摹 → SVG
python -X utf8 src/trace_xiaoxuetang_glyphs.py --input tmp/xxt/qinwenzi/img --out tmp/xxt/qinwenzi/svg --check --eps 0.7 --smooth 1 --manifest tmp/xxt/qinwenzi/manifest.jsonl

# 3) 身份反查（底本页.行为主、說文小篆槽位为辅）
python -X utf8 src/resolve_pua_identity.py --index tmp/xxt/qinwenzi/index.jsonl --out tmp/xxt/qinwenzi/identity_map.jsonl --seal-index glyphs/seal/index.csv

# 4) 清单 → 合并 → 入库
python -X utf8 src/run_xxt_pipeline.py --db qinwenzi --stage manifest
python -X utf8 src/run_xxt_pipeline.py --db qinwenzi --stage merge
python -X utf8 src/run_xxt_pipeline.py --db qinwenzi --stage import --yes
```

## 核验

```powershell
python -X utf8 src/verify_provenance.py --script qinwenzi --quiet   # 出处与 sha256 对账
python -X utf8 src/check_glyphs.py glyphs/qinwenzi                 # 字形体检
python -X utf8 src/check_glyphs.py --trace-fidelity                # 描摹保真（读 trace_iou）
python -X utf8 src/check_layer_rules.py --repo-root . --layer qinwenzi  # 层的规则与不变量
```
