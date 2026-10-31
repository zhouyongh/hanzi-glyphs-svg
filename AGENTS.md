# AGENTS.md — hanzi-glyphs-svg

汉字库：把汉字字形 **SVG** 建全，并保证 **出处可追溯**。

## 通用技能库

跨仓库技能统一在 `D:\yohan\skills\`（目录见其 `INDEX.md`）。执行通用任务（配图、发布、写规范/规格/方案文档等）时，先查技能库有无对应技能：有则读其 `SKILL.md` 并遵循，技能库是这些规范的唯一事实源；没有才用本仓库自带做法。仓库特有的事实（文章放哪、本仓库主题）仍以本文件为准。

## 用途

- 收录汉字 SVG 字形（甲骨文、金文、篆书、隶书、楷书、行书、草书、宋体、黑体）
- 供上层项目引用；本仓库不做游戏、不做业务应用
- 附一个**零构建的只读浏览页** `viewer/index.html`（由 `src/build_viewer.py` 生成，不是应用、
  不引入依赖、不复制字形文件），用于人工核验字形
- 浏览页的字形**按需从 CDN 取**（部署到 Pages 时 `glyphs/` 不随站点发布）。
  **取字必须有兜底链**：单一 CDN 的一次失败就会留一个空白格，兜底链见
  `src/build_viewer.py` 的 `retryPlan()`；全试完还不行就把格子标成「取不到」，
  别让「取不到」看起来像「这个字形是空的」

## 目录

```
hanzi-glyphs-svg/
  AGENTS.md / README.md
  LICENSE            # CC BY 4.0 全文（只覆盖 CC BY 那一层）
  LICENSE-CODE       # CC0 1.0 说明（代码与页面）
  LICENSE-DOCS       # CC0 1.0 全文（文档；篆书层的 CC0 也引这一份）
  LICENSE-DATA       # 数据/文档/代码许可说明
  THIRD_PARTY_NOTICES.md
  glyphs/            # 字形 SVG + 出处记录
    provenance/      # 出处记录，一层一个文件（文件名 = 书体名）
    oracle/          # JGW 骨架 + 汉典拓片摹本 + index.csv + outline/（派生层）
    bronze/          # 金文字形 + index.csv
    seal/            # 篆书字形 + index.csv + external.csv（全量码位登记表）+ README.md
    clerical/        # 隶书字形 + index.csv
    chu/             # 楚文字形 + index.csv + books.csv（文献代号对照表）+ books_xxt.csv（小学堂出處表对照）+ staged.csv（未发布登记）+ README.md
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
| `glyphs/bronze/` | 金文 | Bronze script |
| `glyphs/seal/` | 篆书 | Seal script |
| `glyphs/clerical/` | 隶书 | Clerical script |
| `glyphs/chu/` | 楚文字 | Chu script |
| `glyphs/chuanchao/` | 傳抄古文字 | Chuanchao (transcribed ancient characters) |
| `glyphs/qinwenzi/` | 秦系简牘 | Qin bamboo and wooden slips script |
| `glyphs/xiaozhuan/` | 小篆·小学堂 | Seal script (Xiaoxuetang) |
| `glyphs/kaishu/` | 楷书 | Regular script |
| `glyphs/xingshu/` | 行书 | Running script |
| `glyphs/caoshu/` | 草书 | Cursive script |
| `glyphs/songti/` | 宋体（简体） | Song / Ming, Simplified Chinese |
| `glyphs/songti-tc/` | 宋体（繁体） | Song / Ming, Traditional Chinese |
| `glyphs/heiti-hk/` | 黑体（港版） | Sans, Hong Kong |

> **两个宋体层**：同一书体的**地区变体**，键都是现代字 Unicode 码位，所以**码位会重叠**——
> 两层各自独立，`index.csv` 分开列。共有 15,975 个码位里，路径串逐字节相同的 **8,170** 个、
> 渲染后差异明显的 **7,802** 个（大陆规范 vs 台湾规范）。码位集合差异主要在**扩展 B 区的
> 繁体异体码位**（`songti` 52 个，`songti-tc` 1,705 个）。
> 下游要「简体优先」用 `songti`，要繁体异体用 `songti-tc`。
>
> **黑体·港**是**香港標準字形**（Chiron Hei HK），与大陆写法在约两千字上不同——
> 它不是「同一字形的另一种写法」，不能当大陆字形用。
>
> **`qinwenzi` / `xiaozhuan` 是小学堂批次**：上游原件是**位图**，本地 SVG 是
> **自动描摹**的派生件（许可 CC0 1.0，见 `src/licenses/xiaoxuetang-CC0-1.0-statement.md`）。
> 两层的键都是**本仓库条目号**（`≥4` 位十进制），不是现代字码位——
> 尤其 `xiaozhuan` 与 `seal/`（漢典《說文》系小篆，键是 Unicode 篆书区块码位）
> **不是同一批材料**，键空间也完全不同，不能混用。
>
> **位图描摹件的硬约束**：
>
> - 填充规则用 **`nonzero`**（SVG 与光栅化校验必须一致）；
> - 每件记 **`trace_iou`**（本地 SVG 回光栅化与上游位图墨迹掩膜的 IoU），
>   门槛：单条 ≥ 0.97 合格、0.93–0.97 警戒、< 0.93 判失败；
>   层级 p05 ≥ 0.96、失败率 ≤ 1%。机检入口：`python src/check_glyphs.py --trace-fidelity`；
> - 描摹参数定案：**size=400 / eps=0.7 / smooth=1**（分辨率与容差同步放大，
>   产物体积不变而轮廓精度翻倍）。
>
> **现代字身份不明时的处理**：小学堂有些字頭只给**字体排版槽位码位**（私用区），
> 不是 Unicode 汉字码位。这类记录**不丢弃**，但**也不能拿私用区码位当汉字码位**——
> 两条路补回真身份，都由 `python src/resolve_pua_identity.py` 做：
>
> - **路线 D · 底本页.行（主，可靠）**：《楚系簡帛文字編》按「页.行」定位，摹本里一字一行，
>   一个页.行只对应一个字。小学堂字頭的「相關索引」列这个字在各底本的页.行，
>   漢典层的 `source_base_pages` 记的就是同一套页.行，两边一对，字就接回去了。
>   **实测一致率 100%**：在两百多个**已知身份**的字頭上反查结论与站点自己给的身份
>   **零不一致**（`--verify-known` 可复跑；条数随数据增长）。
> - **路线 A · 說文小篆槽位（辅）**：`glyphs/seal/` 的 `source_id` 就是「說文小篆」字体的槽位，
>   与小学堂字体号 27 是同一套槽位。槽位常对应多个码位（正字 + 重文 + 古文），
>   所以只能当旁证：与路线 D 一致时加强证据，单用时作次选。
> - **路线 C · 字形键（辅）**：字形键 = `字体号_码位`，同一套字体槽位就是同一个字。
>   漢典层已收录这个字形、且**只给了一个**现代字时，那个字就是它的身份
>   （楚系实测 289 个实例）。**同一字形挂着多个现代字时属歧义，不猜**——
>   漢典层 11,039 行只有 5,304 个唯一字形，最多的一个挂了 11 个现代字。
> - **三条都不成立** → 走**临时身份**：`identity_confidence="pua-slot"`、
>   `modern_char_slot="<字体号>_<码位>"`。该码位**不是汉字码位，不得当汉字引用**。
>
> `identity_confidence` 的取值：`""`（站点直接给出真汉字）、`base-page`、`seal-slot`、
> `base-page+seal-slot`、`base-page∩seal-slot`、`shape-key`、`pua-slot`。
> **不用**「在现代书体层收不收得到」或「在漢典层出现频次高低」挑正字——两者都验过，会选错。
> **多候选一律不猜**：猜错比不猜更糟。
>
> **临时身份条目的写法**（照甲骨层先例，glyph_id 380/916）：
> `modern_char=""`、`unicode=""`、`identity_confidence="pua-slot"`、
> `modern_char_slot="<字体号>_<码位>"`。
> **不拿 PUA 码位冒充汉字码位**——否则层里会出现「一个没有对应汉字的码位」。
> 合并器对这类条目的去重键用 `slot:<字体号>_<码位>`（只作去重与排序，
> **不进 index.csv 的 unicode 列**）；注意 `normalize_cp("")` 会补成 `000000`，
> 那是个**根本不存在的码位**，所以空 unicode 必须**先判空再补零**。
>
> **「正字 + 异体字并存」是层语义，不是重复**：小學堂给的是**楷書正字**
> （楚系 1,829 个），漢典层记的是**异体字读法**（4,171 个），交集 1,827，
> 只有小学堂有的 2 个（蛙、陼）都是基本区规范字。
> 同一字形挂多个现代字是漢典层的既有记法（异体 + 通用），合并时按
> **(现代字码位, 字形键)** 判重，各记一条。

新增书体时沿用同一套目录结构（`<书体>/index.csv` + `provenance/<书体>.jsonl`），
并在本文件补上该层的键规则与许可。

## 字形文件

文件名按书体分三种，因为**只有小篆在 Unicode 里有自己的码位**：

| 书体 | 文件名 | 键 |
|------|--------|----|
| `glyphs/seal/` | `<Unicode>.svg` | 篆书区块码位，**5 位大写十六进制**，如 `3D000.svg` = U+3D000（一） |
| `glyphs/oracle/` | `<glyph_id>.svg` | 源字库条目号，**4 位十进制**，如 `0001.svg` |
| `glyphs/bronze/` `glyphs/clerical/` `glyphs/chu/` | `<glyph_id>.svg` | 本仓库条目号，**≥4 位十进制**（不足 10,000 时补零），如 `0001.svg` |
| `glyphs/kaishu/` `glyphs/xingshu/` `glyphs/caoshu/` `glyphs/songti/` `glyphs/songti-tc/` `glyphs/heiti-hk/` | `<Unicode>.svg` | 现代字的 Unicode 码位，**6 位大写十六进制**（补零），如 `004E04.svg` = 你 |

- **甲骨文在 Unicode 里没有自己的码位**，`<Unicode>.svg` 表达不了它；而且一字多形是常态
  （JGW 那批 1,203 条里，33 个现代字各对应 2 个条目；汉典拓片摹本 10,213 条覆盖 1,811 个现代字），
  所以改用**条目号**做键。
- **金文/隶书层有意收「一字多形」**：同一个现代字在不同器物、不同时代各收一条，
  拼起来才是演变链。选取规则是**每个时代最多取 1 个实例**（`--max-per-era 1`），
  目的是覆盖时代跨度，不是堆数量。合并清单要用 `--keep-multi`（键 = 现代字码位 + 来源编号）。
- **楚文字层也收「一字多形」，但分桶维度不是时代而是出土文献**：战国楚简的题记里
  **没有时代词**（传世楚简都是战国中晚期的），所以按时代分桶会退化成「每字只取一个」。
  楚文字按**文献代号**分桶（`--max-per-book 1`，代码来自题记，如「郭」「包」「上」「新甲」），
  同一个字在不同出土文献各取一条，拼起来是楚文字内部的写法演变链。
  **层里只收楚系材料**：汉典「楚系簡帛」栏目里混着秦系简帛（《睡虎地秦简文字编》等）
  与傳抄古文（《传抄古文字编》的砖文等），按 `glyphs/chu/books.csv` 的归属列筛选，
  **不收的字形不删除**，登记在未发布清单里（`glyphs/chu/staged.csv` + 本地暂存目录）留给将来的层。
  - **归属要靠证据，不靠猜书名**：文献代号只在汉典「楚系簡帛」栏出现才是楚系材料，
    用 `src/probe_zdic_book_tabs.py` 做跨栏实测（该代号在秦系簡牘 / 傳抄古文 / 隸書 /
    篆書 / 金文 / 甲骨文栏里出不出现）。
  - **全称查不到就不编**：`books.csv` 的 `corpus_full` 留空，`source_book` 按上游原文记代号。
    这种字形照样有出处——摹本底本《楚系簡帛文字編》（增訂本）的页.行逐条记在
    `source_base_pages` 字段里，读者据此可回原书定位。
  - **小学堂批次（进行中）**：同一层再加一个来源——中研院「楚系簡帛文字」库的字形圖片
    （CC0 1.0，见 `src/licenses/xiaoxuetang-CC0-1.0-statement.md`）。上游给的是**位图**，
    本地 SVG 是**自动描摹**的派生件（`layer="outline"`，记 `derived_from`/`transform`/`tool`）。
    合并规则是**漢典矢量优先**：字形键（字体号_PUA，两库同构）对得上就沿用漢典的矢量字形，
    小学堂只补缺口。小学堂侧的文献对照另存 `glyphs/chu/books_xxt.csv`（出處表原样 + 对应漢典代号，
    用 `src/build_books_xxt.py` 生成）——
    **不能复用 `books.csv` 的 code**：漢典那一栏的「磚」「秦」是傳抄磚文与睡虎地秦簡，
    而小学堂的「磚370」「秦1/13/99」是江陵的楚墓竹简，属楚系，
    故这两个代号在 `books.csv` 里另立行（`include=yes`），`books_xxt.csv` 里 `zdic_code` 留空。
  - **混合层的键是「(现代字码位, 字形键)」**：字形键相同但**现代字不同**时，
    小學堂的**楷書字頭是正字**，正字身份本身就是漢典层缺的那一条——
    所以要**新增**（unicode 不同，不撞键）；**现代字与字形都相同**则沿用漢典，不新增。
    出處簡號对不上而现代字+字形都对上时，只登记差异（crosswalk 的 `source_mismatch`），
    **不新增**——再新增会与漢典那条**撞键**，合并时把小學堂的描摹件顶掉漢典的矢量。
    合并器已有**撞键检测**（清单的 `merge_conflicts`）：同一键两条记录时
    **漢典矢量件（`layer=skeleton`）優先**，不靠清单顺序决定。
  - **现代字身份要逐条核**：小學堂的「楷書字頭」有時是**字體排版槽位碼位**（私用區），
    不是真漢字（字頭行里「標楷體/沙海隸」給的是真 Unicode，「說文小篆」與
    「標楷體外字集N」給的是槽位）。取的是**槽位碼位真實漢字**的那一項；
    仍然只有私用區時，先走**反查**（`src/resolve_pua_identity.py`：底本页.行为主、
    說文小篆槽位为辅），反查不出来才走**临时身份**（见上文「位图描摹件的硬约束」）。
  - **位图只抓「层真正要用的那些」**（`src/plan_xxt_fetch.py`）：按层的规则先筛，
    再扣掉漢典层已有的字形。层的规则 = **(现代字, 文献) 留 1 条 + 每字 ≤5 条**
    （与漢典层 `--max-per-book 1 --per-char 5` 同口径）。楚系实测：
    全部唯一字形 37,180 → 选中 7,017 条 → **真正要抓 2,558 张（6.9%）**。
  - **选取规则 R2（漢典字形优先，无则字体号升序）**：比 R1 多保住 548 个漢典已有字形
    （不用抓位图也不用描摹），且与「重叠处漢典优先」是同一条原则。
  - **「重文一~八」不是重复字形**：8 套字体是**同一批摹本的 8 套转写**，
    同 (字, 文献) 下字体间 IoU 仅 **0.26–0.43**（是不同写法，不是重复登记）。
    但层的口径是「一桶一条」，所以**同一 (字, 文献) 只进一条**：
    有漢典字形就用漢典的，没有就按字体号升序取一条。
  - **抓取纪律（实测定档，别擅自提速）**：取图端点服务时间 ~1.02 s、检索页 ~1.05 s；
    **间隔 1 s + 并发 2 路**安全（两路延迟都 1,015–1,073 ms，无劣化、无拦截）；
    已知拦截阈值 ≈8 req/s（12 次/1.5 s 进拦截态）。总速率压在 ~1.7 req/s。
    **一批坏掉不中断整轮**（原来一张图失败就 `break`，实测 2,600/11,190 就停摆）；
    抓取脚本的**指纹只覆盖「解析面」**（`PARSER_VERSION` + 解析函数源码 + 正则 + 字体前缀表），
    改取图参数不再作废已抓好的索引。
- **小学堂批次里「书体由字体决定，不由材料决定」**：同一个库里可能混着不同书体的字形，
  字体的名字就是书体的判据：
  - 「中研院楚系簡帛文字重文*」→ 楚系层；「中研院秦系簡牘文字重文*」→ 秦系层；
    「中研院傳抄古文字重文*」→ 傳抄层；「中研院甲骨文重文*」→ 甲骨层；
    「中研院金文重文*」→ 金文层；
  - **「隸變」库里同时有「中研院隸書重文*」與「中研院秦系簡牘文字重文*」**——
    前者是隸書字形（归隶书层），后者是**秦系字形**（归秦系层，不是隶书层）。
    材料的朝代（出處簡號后面的「秦」「西漢」「東漢」）不管用。
    分流靠 `build_xxt_manifest.py --font-allow`；
  - **「小篆」库的字体是「北師大說文小篆」，不是「中研院」**——那是《說文》小篆字体，
    与篆书层的 `source_id`（`27_<槽位>`）是**同一套槽位**。
    抓取脚本按库配字体前缀（`GLYPH_FONT_PREFIXES`），一刀切用「中研院」会让小篆库一个实例都出不来。
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
   派生件（甲骨轮廓、现代书体六层、位图描摹件）另记 `derived_from`、`derived_from_sha256`、
   `transform`、`tool`；字体层再加 `font_name` / `font_version`。  
   **位图描摹件**另记 `trace_iou`（本地 SVG 与上游位图的 IoU，保真核验用）；
   **现代字身份不是站点直接给出时**另记 `identity_confidence`（`base-page` / `seal-slot` /
   `base-page+seal-slot` / `base-page∩seal-slot` / `shape-key` / `pua-slot`）与 `modern_char_slot`
   （`<字体号>_<码位>`，槽位码位；身份未定时的唯一线索）。  
   **临时身份条目 `modern_char` 与 `unicode` 都留空**（不拿 PUA 码位冒充汉字码位）。  
   用 `python src/verify_provenance.py` 校验（它同时查许可白名单与「文件名 = 书体名」）。
3. **禁止编造链接**；网络来源须核实后再写入 provenance。
4. 正式字形须**贴近原字形**；禁止卡通美化当正式字形。
5. 未获原作者同意时，**如实写来源**，不冒充原创或隐瞒出处。
6. **一层一个 provenance 文件**：不要把别的书体的记录并进来。这样某一层的授权状态变化时，
   整层（字形 + 索引 + 出处）可以一起加入或一起移除，不必在一份全量文件里做手术。

## 许可

- 字形 SVG 的许可**逐书体**不同，以 `glyphs/provenance/<书体>.jsonl` 每条的 `license` 为准；
  使用方须按该许可署名，署名文字在 `attribution` 字段与 `THIRD_PARTY_NOTICES.md`。
- 目前 `glyphs/oracle/` 的 JGW 批（1,203 骨架 + 1,203 轮廓）为 **CC-BY-4.0**；
  `glyphs/oracle/` 的汉典批（10,213 拓片摹本）、`glyphs/bronze/`、`glyphs/seal/`、
  `glyphs/clerical/`、`glyphs/chu/` 为 **CC0-1.0**；
  `glyphs/kaishu/` `glyphs/xingshu/` `glyphs/caoshu/` `glyphs/songti/` `glyphs/songti-tc/`
  `glyphs/heiti-hk/`（从 OFL 开源字体提取的轮廓）为 **OFL-1.1**；
  **小学堂批次**（`glyphs/chu/` 的位图描摹件，以及将来的 `glyphs/qinwenzi/`、
  `glyphs/xiaozhuan/`、`glyphs/chuanchao/`）为 **CC0-1.0**，
  声明原文存档在 `src/licenses/xiaoxuetang-CC0-1.0-statement.{md,html}`。
  **CC0 只处置中研院对自己「字形圖片」的权利，不消灭底本著作权**——
  审计结论仍是「⚠️ 可发布（有残余风险，须随附底本说明）」。
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
- **本仓库自身的对外许可**：文档、索引、代码与浏览页 **CC0 1.0**（无义务），
  其中代码与页面另见 `LICENSE-CODE`；数据逐层不同，见上。
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
| 甲骨文 | **10,213** 拓片摹本（CC0 1.0） + **1,203** 骨架 + **1,203** 轮廓（CC BY 4.0），provenance 与 `index.csv` 齐全 |
| 金文 | **8,290** 字形（CC0 1.0），**一字多形**：每时代最多 1 个实例，26 个时代桶 |
| 篆书 | **10,591** 字形（CC0 1.0），键 = 篆书区块码位，覆盖 **10,591 / 11,328**（93.5%）；另有 `external.csv` 登记全量 11,328 个码位 |
| 隶书 | **11,947** 字形（CC0 1.0），**一字多形**，12 个时代桶 |
| 楚文字 | **11,039** 字形（CC0 1.0），**一字多形**：按**出土文献**分桶（每个文献最多 1 个实例），`index.csv` 里 26 个文献桶（上博分（一）（二）两册），覆盖 **4,171** 个现代字 |
| 楷书 | **6,763** 字形（OFL 1.1，Ma Shan Zheng），键 = 现代字码位；层内带 `OFL.txt` + `SOURCE.md` |
| 行书 | **6,763** 字形（OFL 1.1，Zhi Mang Xing） |
| 草书 | **6,763** 字形（OFL 1.1，Liu Jian Mao Cao） |
| 宋体（简） | **27,797** 字形（OFL 1.1，Noto Serif SC `wght=400`）；基本区 20,992 + 扩展 A 6,592 + 扩展 B/C/D/E/F 213 |
| 宋体（繁） | **17,665** 字形（OFL 1.1，Noto Serif TC `wght=400`）；**扩展 B 1,705 个是简体层没有的繁体异体码位** |
| 黑体（港） | **31,598** 字形（OFL 1.1，Chiron Hei HK `wght=400`）；**香港標準字形**，不是大陆字形的另一种写法 |

- `glyphs/provenance/` 现为 **151,835 条**
  （oracle 12,619 + bronze 8,290 + seal 10,591 + clerical 11,947 + chu 11,039 + 六个字体层 97,349）；
  `verify_provenance.py` 机读校验 **0 问题**，`check_glyphs.py` 各层 **0 问题**。
- 甲骨文特例：`0380`、`0916` 无对应现代汉字；`1180`（妞）身份为 `provisional`。
- 楚文字层的分桶维度、文献代号归属闸门、「全称待考按代号记」的取舍，
  以及摹本底本链条（`source_base_pages` / `source_references` 的层级差别）见 `glyphs/chu/README.md`。
- 篆书层的键、覆盖率、正篆/重文的取舍规则，以及一处对 Unicode `SealSources.txt`
  的偏差修正（U+3D06D 归「玉」而非「王」）见 `glyphs/seal/README.md`。
- 字体六层的来源、许可证据与取舍见各层 `SOURCE.md`；逐条款证据汇总在
  `glyphs/font-license-evidence.md`（由 `src/build_font_license_evidence.py` 生成）。
- **六个字体层在收字区块内漏收为 0**（`python src/audit_font_coverage.py --font-dir <字体目录>` 可复跑）。
  收字区块之外另有 403 个 CJK 相关码位（康熙部首 214、CJK 部首补充 115、带圈表意补充 58、
  迭代记号 3、杭州数字 13），不算漏收——收字区块本来就不含它们。

## 脚本

| 脚本 | 作用 |
|------|------|
| `src/import_oracle_jgw.py` | 导入甲骨文骨架 |
| `src/outline_oracle.py` | 骨架 → 可填充轮廓（`--selftest` 几何自检） |
| `src/extract_font_glyphs.py` | 从 OFL 字体提取汉字轮廓为 SVG（fontTools → path；画布取墨迹并集） |
| `src/verify_font_licenses.py` | 逐条款核验 OFL 许可文本（正文比对 + RFN + 版权行）；加 `--font` 会连字体 name 表一起查 |
| `src/verify_songti_variants.py` | 核验「宋体·简 / 宋体·繁」两层的性质：层里装的是简繁**码位**（不是筛过的字符集）、共有码位里多少字形不同（**比像素**，不能比 SVG 字节）、层是否忠实于源字体（加 `--font-sc/--font-tc` 比路径串）；`--charset-only` 只用标准库，可进 CI |
| `src/audit_font_coverage.py` | **字体层漏收审计**：层里的码位集合与源字体 cmap 逐块对照，报漏收 / 多收 / 有意不收 / 收字区块外的 CJK 码位；收字区块直接 import 抽取器的 `BLOCKS`，不另抄一份 |
| `src/build_font_license_evidence.py` | 汇总各字体层的 OFL 1.1 逐条款证据成 `glyphs/font-license-evidence.md` |
| `src/eval_candidate.py` | 候选字体的**净增量评测**：相对已覆盖码位算还能补多少（扣掉兼容区块） |
| `src/license_audit.py` | **发布安全审计**：逐层「能不能安全发布」，出 `glyphs/publish-license-audit.md` + `.json` |
| `src/fetch_zdic_glyphs.py` | 抓汉典「书法」字形实例，出 `manifest.json` |
| `src/fetch_xiaoxuetang_pages.ps1` | **小学堂页面/位图抓取**（PowerShell 传输层：ASCDC 边缘只放行 Windows 原生 TLS 客户端，Python 直连一律被挡） |
| `src/fetch_xiaoxuetang_glyphs.py` | 抓小学堂的字形实例索引 / 出處表 / 许可快照 / 规模快照（枚举键 `ZiOrder`+`PageNo` 留空+`PageTo` 分页；实例级去重） |
| `src/trace_xiaoxuetang_glyphs.py` | **位图 → SVG 自动描摹**（零第三方依赖：numpy+Pillow 自实现 marching squares，case 表由几何推导生成，附 IoU 保真核验与断链断言） |
| `src/build_xxt_manifest.py` | 小学堂抓取结果 → 合并器清单（判「层里有没有这一条」看 **(现代字, 字形)** 这对键；字形键对上而现代字不同 → **新增**（小學堂的楷書字頭是正字）；现代字+字形都对上 → 沿用漢典，不新增；现代字身份只有私用區槽位 → 先查反查表，仍无解才走**临时身份**并标记） |
| `src/resolve_pua_identity.py` | **私用區字頭的身份反查**：路线 D 底本页.行（摹本一字一行，**实测一致率 100%**，`--verify-known` 可复跑）+ 路线 A 說文小篆槽位（旁证）+ 路线 C 字形键（同槽位 = 同一个字，漢典只给一个现代字时才用）；出「字頭 → 现代字」对照表 |
| `src/plan_xxt_fetch.py` | **算清楚要抓哪些位图**：按层的选取规则（每 (现代字,文献) 1 条、每字 ≤5 条）筛，再扣掉漢典层已有的字形；出字形键清单 + 取图清单 + 逐桶选取记录（合并阶段按同一份选择走） |
| `src/rebuild_layer_manifest.py` | **从已入库的层重建合并器清单**（`index.csv` + `provenance` → 清单）：增量入库要把旧记录一起重排（条目号是整层内容的函数），但没必要重新抓十几万个上游 SVG |
| `src/build_books_xxt.py` | 生成 `glyphs/chu/books_xxt.csv`（小學堂出處表原样行 + 派生行；`row_kind` 列区分两者；对不上漢典代号的 `zdic_code` 留空） |
| `src/build_layer_books.py` | 按小學堂出處表生成某层的 `glyphs/<层>/books.csv`（傳抄 / 秦系 / 小篆）；同一簡稱出现在两张出處表时保留更全的全称 |
| `src/crosscheck_xiaoxuetang.py` | **小学堂 × 漢典 交叉比对**：锚点是**字形键**（字体号_PUA），出四类结果（完全对上 / 现代字不一致 / 出處不一致 / 仅小学堂有），出 `crosscheck.md` + `.jsonl` |
| `src/run_xxt_pipeline.py` | **全流程驱动器**：位图 → 描摹 → 清单 → 合并 → 入库 → 校验；任一步失败就停在那一步 |
| `src/run_xxt_crawl.ps1` | **分离进程长跑启动器**（后台任务有 1 小时上限，全量抓取是几十小时的活，必须脱离工具调用；日志落 `tmp/xxt/logs/`） |
| `src/build_char_table.py` | 生成抓取用的字表（说文登记表 ∪ CJK 基本区/扩展 A 区） |
| `src/clean_zdic_glyphs.py` | 洗掉汉典字形里的近白水印层，产出可入库的字形与清单 |
| `src/merge_glyph_manifests.py` | 合并多批清单（`--keep-multi` 保留一字多形）；`--books-csv` 按文献代号筛选：只收表里标为收录的代号，**不收的字形不删除**，登记到 `--staged-out`（`--staged-csv-out` 可把登记表另存一份随层发布） |
| `src/probe_zdic_book_tabs.py` | **文献代号归属实测**：某代号在汉典别的书体栏（秦系簡牘 / 傳抄古文 / 隸書 / 篆書 / 金文 / 甲骨文）里出不出现——只出现在「楚系簡帛」栏才是楚系材料 |
| `src/build_seal_zheng_table.py` | 生成「现代字 → 正篆码位」反查表（含 93/93 交叉验证） |
| `src/assign_seal_codepoints.py` | 给小篆字形指派篆书区块码位（正篆/重文取舍） |
| `src/import_glyph_layer.py` | 按清单导入任一书体层（许可闸门 + provenance + index.csv + 孤儿体检；`--key-mode unicode_codepoint` 用于字体层） |
| `src/import_seal_kaiyuan.py` | 開元小篆导入（`--verify-tree` 只对账 blob SHA-1；许可闸门挡在落盘之前） |
| `src/build_seal_registry.py` | 生成篆书全量码位登记表（含玉/王偏差修正） |
| `src/build_viewer.py` | 生成只读浏览页（只给仓里真有的层出 Tab） |
| `src/check_glyphs.py` | 字形体检（XML 合法、viewBox、路径 bbox、退化检测）+ `--trace-fidelity`（读 provenance 的 `trace_iou` 判定位图描摹件是否忠实于上游位图） |
| `src/glyph_stats.py` | 字形库统计汇总（只读，`--json` 机读） |
| `src/verify_provenance.py` | 校验 provenance 与文件 sha256 |
| `src/verify_spot_source.py` | **抽样回源核验**：按文献代号分层抽样，回汉典核上游原件 sha256、本地字形是否只差水印、题记与字形编号是否在该字页面上 |
| `src/fetch_seal_upstream.py` | 把開元小篆上游拉到本地查看（`fetch_kaiyuan.bat` 调它），只看不入库 |

## 协作

- 中文交流；标识符用英文
- 改结构先改本文件
- 提交信息说明「为什么」
