# 第三方内容与署名

本仓库的**数据**与**代码**许可是分开的，数据还**逐书体**不同。使用任一内容前，请读本文件
与 `glyphs/provenance/<书体>.jsonl`（一个文件一条，含 `license` 与 `attribution` 字段），
并用 `python src/verify_provenance.py` 校验。

## 许可地图

| 范围 | 许可 | 全文 |
|------|------|------|
| `glyphs/oracle/` 的 JGW 批（骨架 1,203 + 派生轮廓 1,203） | **CC BY 4.0** | 根 `LICENSE` |
| `glyphs/oracle/` 的汉典批（拓片摹本 10,213）、`glyphs/bronze/`（金文 8,290）、`glyphs/clerical/`（隶书 10,224）、`glyphs/seal/`（篆书 10,591）、`glyphs/chu/`（楚文字 11,039）、`glyphs/chuanchao/`（傳抄古文字 12,975）、`glyphs/qinwenzi/` 的漢典秦系矢量件（1,594） | **CC0 1.0**（公有领域奉献，无义务） | `LICENSE-DOCS`；汉典的归公宣告原文见本文件 |
| `glyphs/qinwenzi/`、`glyphs/chuanchao/`、`glyphs/oracle/`、`glyphs/bronze/`、`glyphs/clerical/` 的小學堂位图描摹件（秦系 2,114 + 傳抄 7,469 + 甲骨 2,540 + 金文 3,401 + 隸書 1,812） | **CC0 1.0**（中研院「小學堂」《版權聲明》） | `LICENSE-DOCS`；声明原文见本文件 |
| `glyphs/chu/books_xxt.csv`（小學堂出處表对照）、`src/licenses/xiaoxuetang-CC0-1.0-statement.{md,html}` | **CC0 1.0**（中研院「小學堂」《版權聲明》） | `LICENSE-DOCS`；声明原文见本文件 |
| `glyphs/kaishu/` `glyphs/xingshu/` `glyphs/caoshu/` `glyphs/songti/` `glyphs/songti-tc/` `glyphs/heiti-hk/`（现代书体六层 97,349 个字形、索引、出处记录） | **SIL OFL 1.1** | 各层目录的 `OFL.txt`（上游逐字节副本） |
| `glyphs/provenance/*.jsonl` | **逐条记录**：每条按其 `license` 字段（CC BY 4.0 / CC0 1.0 / OFL-1.1） | 本文件 + 根 `LICENSE` |
| `glyphs/seal/external.csv` —— 本仓库整理的部分 | CC0 1.0 | `LICENSE-DOCS` |
| `glyphs/seal/external.csv` —— 派生于 Unicode `SealSources.txt` 的列 | Unicode License v3（声明见下） | 本文件 |
| `glyphs/seal/external.csv` 的 `upstream_*` 列（指向上游） | **不适用**：本仓库未复制上游内容，只登记指针 | — |
| `README.md`、`AGENTS.md`、本文件、各层 `index.csv` | CC0 1.0（无义务） | `LICENSE-DOCS` |
| `src/**`、`viewer/**` | CC0 1.0（无义务） | `LICENSE-CODE` |

**根 `LICENSE`（CC BY 4.0）只覆盖 CC BY 4.0 那一层**（甲骨 JGW 骨架与派生轮廓），
**不覆盖** CC0、OFL 与 Unicode 授权的材料。下游须按各层许可分别使用。

---

## 底本与作者

字形是**摹本**，摹的是下列出版物。CC0 放弃的是**中研院／汉典自己**的权利，
**不消灭**这些底本的著作权——列出作者与版本，供核对与追索。

| 底本 | 作者／编者 | 用在哪一层 |
|---|---|---|
| 《甲骨文合集》（1978–1982，中華書局，13 冊） | **郭沫若** 主编、**胡厚宣** 总编辑，中国社会科学院历史研究所《甲骨文合集》编辑工作组集体编辑 | 甲骨文层（记拓片号 + 合号 + 卜辞组别） |
| 《殷周金文集成》（1984–1994，中華書局；2007 修订增补本全 8 冊） | 中国社会科学院考古研究所 编 | 金文层（记器名 + 集成号） |
| 《金文編》（1985，中華書局） | **容庚** 编著，**張振林**、**馬國權** 摹补 | 金文层（汉典参考书目） |
| 《殷周金文集成引得》（2001，中華書局） | **張亞初** 编著 | 金文层（汉典参考书目） |
| 《說文解字》（東漢） | **許慎** | 篆书层（记部次与形制） |
| 《秦漢魏晉篆隸字形表》（1985，四川辭書出版社） | 汉语大字典字形组 编 | 隶书层、楚文字层（汉典参考书目） |
| 《漢印徵》 | **吳昌碩** 辑 | 隶书层 |
| 《楚系簡帛文字編》（1995；增訂本 2008，湖北教育出版社） | **滕壬生** | 楚文字层（摹本底本，逐条记页.行） |
| 《戰國文字編》（2001；修訂本 2015，福建人民出版社） | **湯餘惠** 主编 | 楚文字层（汉典参考书目） |
| 《秦簡牘文字編》（2012，福建人民出版社） | **方勇** 编著 | 楚文字层（汉典参考书目） |
| 《傳抄古文字編》（2006，綫裝書局，全三冊） | **徐在國** 编（课题组：郝士宏、張通海、張振謙） | **傳抄层（摹本底本，逐条记冊頁.行）**、楚文字层（汉典参考书目） |
| 《戰國古文字典：戰國古文聲系》（1998，中華書局） | **何琳儀** 著 | 楚文字层（汉典参考书目） |
| 《睡虎地秦簡文字編》（1994；2003 再版，文物出版社） | **張守中** 编 | **秦系层（摹本底本）**、楚文字层（汉典参考书目） |

《甲骨文合集》编号的首字是该片拓片**所出著录书的代号**（本仓库共 82 种，如「甲」「乙」「菁」「鐵」「京津」「京都」）。

---

## `glyphs/oracle/` —— 甲骨文（两批：JGW 批 CC BY 4.0 + 汉典拓片摹本 CC0 1.0）

| 项 | 内容 |
|---|---|
| 来源数据集 | Oracle Bone Glyphs: Parametric Vector Dataset (**v0.3**) |
| 作者 | Li, Qing-sheng；Bian, Yu-lin（浙江传媒学院） |
| DOI | [`10.5281/zenodo.22467946`](https://zenodo.org/records/22467946) |
| 镜像 | [github.com/aylqs2025/oracle-bone-jgw-1203](https://github.com/aylqs2025/oracle-bone-jgw-1203)（tag `v0.3`，commit `5496ad559f81ae8632f3915e8ec2beb705c64ba3`） |
| 原件 | `aylqs2025/oracle-bone-jgw-1203-v0.3.zip`，MD5 `7764c7f5b0feb8f0052c36233ddf8d4b` |
| 许可 | **CC BY 4.0**（上游 `/data`、`/figs`） — <https://creativecommons.org/licenses/by/4.0/> |
| 校验 | 1,203 个骨架文件与 Zenodo 原件逐一 sha256 **全部一致**；Zenodo zip 的 MD5 与官方公布值一致 |
| 未收录 | 上游 `data/svg_parametric/`（解析重建后的光滑化版本）、`src/`、`figs/` |

### 署名文字（使用 `glyphs/oracle/` 时请原样附上）

> 字形来源：Li, Qing-sheng & Bian, Yu-lin (2026), *Oracle Bone Glyphs: Parametric Vector
> Dataset (v0.3)*, doi:10.5281/zenodo.22467946, CC BY 4.0.
> 数据集主页：https://zenodo.org/records/22467946
> 许可全文：https://creativecommons.org/licenses/by/4.0/legalcode

### 本仓库做了哪些修改（CC BY 4.0 §3(a)(1)(B) 要求声明）

1. 把上游 `data/svg_polyline/` 的 1,203 个 SVG **逐字节复制**为 `glyphs/oracle/<glyph_id>.svg`，
   **未改动其几何内容**（未转码、未归一化 viewBox、未重绘）；每条的 sha256 见
   `glyphs/provenance/oracle.jsonl`，可与上游原件逐一比对。
2. 由这些骨架**派生**出可填充轮廓 `glyphs/oracle/outline/<glyph_id>.svg`（把 `stroke` 骨架
   转换为填充路径，同名、同 viewBox），由本仓库脚本 `src/outline_oracle.py` 生成，
   **不是上游产物**。
3. 新增了本仓库自己的 `index.csv`、`provenance/`、`src/**` 脚本、`viewer/` 浏览页与文档。
4. 上述修改**不改变上游材料的许可状态**：`glyphs/oracle/*.svg` 与
   `glyphs/oracle/outline/*.svg` 均继续适用 CC BY 4.0；任何下游使用都须遵守 CC BY 4.0
   （含署名与改动声明要求）。本仓库未对下游附加任何额外限制。

### 派生层 `glyphs/oracle/outline/`

- 派生件沿用上游的 **CC BY 4.0** 与同一署名要求。
- 每个派生文件的出处记在 `glyphs/provenance/oracle.jsonl`（`layer: "outline"`，含
  `derived_from` 与 `derived_from_sha256` 指回骨架）。

### 上游自述的限制（转录，非本仓库添加）

- 上游每个字只提供**一个代表字形**；异形、跨阶段字形演变、贞人（scribe group）风格分析
  均明确不在其范围内。
- 上游自述：最锐的钩笔分段存在少量**残环**（中位重建误差 0.0026）。
- **甲骨文在 Unicode 中没有码位**；每条记录的 `unicode` 指的是对应**现代汉字**的码位。
- v0.3 中有 **33 个现代字各对应 2 个条目**（如 `0013` 与 `1149` 都是「祥」），
  属考古学上的分化，不是重复标注；身份请以 `glyph_id` 为准。
- `0380`、`0916` 两条没有可对应的现代汉字；`1180`（妞）的身份为 `provisional`。

---

## `glyphs/seal/` —— 篆书（汉典「书法」小篆，CC0 1.0）

| 项 | 内容 |
|---|---|
| 来源 | 汉典（zdic.net）「书法」字形实例 |
| 实例页 | `https://www.zdic.net/hans/<字>/xiaozhuan` |
| 字形文件直链 | `https://img.zdic.net/zy/xiaozhuan/<id>.svg` |
| 许可 | **CC0 1.0**（汉典《服务条款》第四条「归公宣告」） |
| 规模 | `glyphs/seal/` 10,591 个字形，覆盖篆书区块 11,328 个码位中的 93.5% |

### 许可原文（照录，勿改写）

> 四、归公宣告
> 汉典奉行 CC0 1.0 公约，将本站字词、古籍、诗词、书法诸作，悉数贡献天下，放弃著作专权及邻接法益，任人取用，以公无穷。
>
> —— <https://www.zdic.net/terms/>（2026-10-30 核验）

CC0 1.0 是**公有领域奉献**：不设任何条件，不署名、不注明改动也可以使用。

### 本仓库做了哪些修改

1. **去水印。** 汉典的篆书字形 SVG 里带一层**近白色的角标水印**（近白填充 `#fafafb` 一类，
   与字形笔画零重叠，占画布 0.16%–0.46%）。入库前用 `src/clean_zdic_glyphs.py` 把
   「有效填充色接近纯白」的 `<g>` / `<path>` 元素**整块删掉**，其余字节原样保留。
   每条的改动情况记在 `provenance/seal.jsonl` 的 `modifications` 字段。
2. **剔除位图实例。** 汉典有个别实例不是矢量轮廓，而是把 PNG 以 base64 塞进 `<image>`。
   这类文件不是**矢量字形**，且水印与笔画烤在同一张位图里分不开，本库只收矢量字形。
   因此 `3F32F`、`3F41A` 两个码位空缺。
3. **留痕。** 逐字形记录了 `source_sha256`（上游原件）与本地 `sha256`，可与汉典原件逐一比对。

本层的字形出处是**题记里的「說文‧X部」**（10,591 条全部如此，无例外），
对应《说文》刻本系统；`index.csv` 与 `provenance/seal.jsonl` 里逐条记着部次与形制
（正篆 / 說文古文 / 說文籀文 / 說文或體）。本仓库**不对字形及其底本主张任何权利**；
若相关权利人认为某条内容侵犯权利，请通过 Issue 或 <1279190619@qq.com> 联系，核实后移除。

---

## 金文、隶书与甲骨拓片摹本 —— 汉典「书法」字形（CC0 1.0）

| 项 | 内容 |
|---|---|
| 来源 | 汉典（zdic.net）「书法」字形实例 |
| 实例页 | `https://www.zdic.net/hans/<字>/<kind>`（`jinwen` 金文 / `lishu` 隶书 / `jiaguwen` 甲骨文） |
| 字形直链 | `https://img.zdic.net/zy/<kind>/<id>.svg` |
| 许可 | **CC0 1.0**（汉典《服务条款》第四条「归公宣告」，原文见上一节） |
| 规模 | 甲骨 10,213（`glyphs/oracle/`，与 JGW 批同目录）、金文 8,290（`glyphs/bronze/`）、隶书 10,224（`glyphs/clerical/`，秦系件已归位到 `glyphs/qinwenzi/`） |

**出处粒度**：逐件记出处作品、编号与时代——甲骨「乙3400 / 合1285 / 賓組」、
金文「毛公鼎 / 集成2838 / 西周中期」、隶书「睡.日甲111背 / 秦」。底本分别是
《甲骨文合集》所收拓片、青铜器拓片、汉碑与印谱及秦汉简牍。

**本仓库做了哪些修改**：删去字形里的近白色角标水印元素（与笔画零重叠，占画布 0.16%–0.46%），
剔除以 base64 PNG 套壳的位图实例，其余字节原样保留；每条的改动记在
`glyphs/provenance/<层>.jsonl` 的 `modifications` 字段，`source_sha256` 仍指上游原件。

**立场**：本仓库不对字形及其底本主张任何权利。若相关权利人认为某条内容侵犯权利，
请通过 Issue 或 <1279190619@qq.com> 联系，核实后按 `source_id` 整份移除。

---

## 楚文字 —— 汉典「书法」楚系簡帛实例（CC0 1.0）

| 项 | 内容 |
|---|---|
| 来源 | 汉典（zdic.net）「书法」**楚系簡帛**字形实例 |
| 实例页 | `https://www.zdic.net/hans/<字>/chuwenzi` |
| 字形直链 | `https://img.zdic.net/zy/chuwenzi/<id>.svg` |
| 许可 | **CC0 1.0**（汉典《服务条款》第四条「归公宣告」，原文见上一节；2026-10-30 复核，现行有效，涵盖「书法诸作」） |
| 目录 | `glyphs/chu/`（11,039 个字形，覆盖 4,171 个现代字） |

**出处粒度**：逐件记**出土文献**、**篇名与位置编号**——题记原文如「郭.語2.26」
（郭店楚簡《語》第 2 簡第 26 字）、「包2.241」（包山楚簡）、
「上(2).容.28」（上博藏戰國楚竹書第二冊《容》篇）、「帛甲5.19」（長沙楚帛書甲篇）。

底本相关有两个字段，**层级不同，别混用**：

| 字段 | 层级 | 内容 |
|---|---|---|
| `source_base_pages` | 字级 | 这个字在《楚系簡帛文字編》（增訂本）里的**页.行**，例如「543.9」。同字有多个实例时含各实例的页。 |
| `source_references` | 字级 | 汉典字页底部「参考文献」栏的**原文**：这个字在汉典**各书体栏**下用到的全部底本（《楚系簡帛文字編》《睡虎地秦簡文字編》《秦簡牘文字編》《傳抄古文字編》《戰國文字編》《戰國古文字典》等）。 |

两者都是字级而非实例级——汉典把参考书目挂在「字页」上，不挂在单个实例上。
**实例级**的是 `source_book`（出土文献）、`book_part`（篇名）、`source_number`（位置编号）、
`source_id`（汉典字形编号）。

**权利链条比金文/隶书多一层**：

```
原簡帛（楚墓出土） → 考古整理本 → 《楚系簡帛文字編》（增訂本，湖北教育出版社，2008）摹本 → 漢典矢量化轉錄
```

漢典的 CC0 放弃的是**漢典自己**的权利，**不消灭**上述摹本底本的著作权。
本仓库对每一层都如实标注，不主张任何权利；若相关权利人认为某条内容侵犯权利，
请通过 Issue 或 <1279190619@qq.com> 联系，核实后按 `source_id` 整份移除。

**这一层只收楚系材料**：漢典「楚系簡帛」栏目里同时有秦系简帛
（《睡虎地秦簡文字編》《秦簡牘文字編》《秦簡墨書集成字形表》等底本）与
傳抄古文（《傳抄古文字編》的磚文等）。这些字形**未收录于本层**，但**也没有被删除**：
它们登记在未发布清单里（`glyphs/chu/staged.csv`，186 条：秦 150 + 磚 36），
留给将来的秦文字层与傳抄古文层直接取用；字形本体留在本地暂存目录，不随层发布。
筛选依据是 `glyphs/chu/books.csv` 的 `script_belong` 列，逐条写了归属与理由。

**六个代号的文献全称已从小學堂出處表补齐**（「天策」「香中大」「常」「雨」「范」「馬」）：
**归属**用汉典跨栏实测证实为楚系（该代号在汉典别的书体栏——秦系簡牘 / 傳抄古文 /
隸書 / 篆書 / 金文 / 甲骨文——都不出现，见 `src/probe_zdic_book_tabs.py`），
**全称**取自中研院「小學堂」楚系簡帛庫的出處表（2026-10-31 取回，见下一节）。
「常」这一例要讲清楚：出處表只列「常2」= 2 號墓，而汉典层的「常」桶**同时含 1 號墓与 2 號墓**
（實測 26 + 9 條，題記作「常1」「常2.1」），全称写成「1、2號墓」是**兜底聚合**，
其中 1 號墓那半按编号规律**推定**，未核实。出处照样可追——摹本底本页.行逐条记在 `source_base_pages` 里。

**本仓库做了哪些修改**：与金文/隶书/甲骨同一套处理——删去字形里的近白色角标水印元素、
剔除以 base64 PNG 套壳的位图实例，其余字节原样保留；每条的改动记在
`glyphs/provenance/chu.jsonl` 的 `modifications` 字段，`source_sha256` 仍指上游原件。

---

## 傳抄古文字与秦系簡牘 —— 两层新层

### `glyphs/chuanchao/` —— 傳抄古文字（漢典矢量件 + 小學堂位图描摹件，CC0 1.0）

| 项 | 内容 |
|---|---|
| 来源 | 汉典（zdic.net）「书法」**傳抄古文**字形实例（12,975 个） |
| 实例页 | `https://www.zdic.net/hans/<字>/chuanchao` |
| 字形直链 | `https://img.zdic.net/zy/chuanchao/<id>.svg` |
| 许可 | **CC0 1.0**（汉典《服务条款》第四条，2026-10-30 复核，现行有效） |
| 目录 | `glyphs/chuanchao/`（20,444 个字形：漢典矢量件 12,975 + 小學堂位图描摹件 7,469） |
| 摹本底本 | 《傳抄古文字編》（徐在國 主編，綫裝書局，2006，全三冊） |

**出处粒度**：逐件记**源書代号**（题记里的「海」「汗」「說」「說籀」「汗目」「石附」「石補」……）
与**冊頁.行**（「中777.7」——帶冊次，与楚系的「頁.行」粒度不同，两层各认各的底本名）。

**源書代号的全称未证实**，按仓库惯例**一律按上游原文记**：`glyphs/chuanchao/books.csv`
里这四行的 `corpus_full` 留空，层里的 `source_book` 就保留这个代号
（「编一个书名比留个代码更糟」）。**「三」与「四」是同一部《古文四聲韻》的不同卷，
是两个代号**——靠两边全称逐字比对才分得开。

**两边的代号是两套体系**：漢典有「汗目」「說籀」「石附」「石補」而小學堂出處表一个都没有；
小學堂有 **119 个**碑刻类代号而漢典沒出過。所以本层有两张表：
`glyphs/chuanchao/books.csv`（漢典口径，131 行）与
`glyphs/chuanchao/books_xxt.csv`（小學堂口径，132 行，含 `zdic_code` 对照列）。

### `glyphs/qinwenzi/` —— 秦系簡牘（漢典矢量件 + 小學堂位图描摹件，CC0 1.0）

| 项 | 内容 |
|---|---|
| 来源 | ① 漢典「书法」栏里的**秦系字体**矢量件 1,594 个（字形键与中研院「小學堂」同构）<br>② 中研院「小學堂」**秦系簡牘**庫的「中研院秦系簡牘文字重文*」字体位图描摹件 2,114 个 |
| 取图端点 | `https://xiaoxue.iis.sinica.edu.tw/ImageText2/ShowImage.ashx?text=…&font=…&size=400` |
| 许可 | **CC0 1.0**（① 漢典《服务条款》第四条；② 中研院《版權聲明》，原文见下一节） |
| 目录 | `glyphs/qinwenzi/`（3,708 个字形） |
| 摹本底本 | 《睡虎地秦簡文字編》（張守中 編著，文物出版社）；所出材料记《睡虎地秦墓竹簡》各篇全称 |

**归位说明**：这 1,594 个字形原先在 `glyphs/clerical/`（隸書层）里——漢典把「中研院秦系簡牘文字重文*」
的秦系字形挂在「书法›隶书」栏下，但**书体由字体决定，不由材料决定**，那是归类错误。
已按秦系层自己的规矩归位（每（现代字, 文献代号）一条、每字最多 5 条）：
1,056 件与層里的小學堂件**同键**，由漢典矢量件顶替（渲染更忠实、出处更完整）；
128 件同（现代字, 文献）已有，不新增；538 件新桶，新增；1 件超每字上限，不收。
隸書层相应减少到 10,224 条。

**书体由字体决定，不由材料决定**：同一库里混着不同书体的字形，字体名就是判据——
「中研院隸書重文*」是隸書字形（归隸書层），「中研院秦系簡牘文字重文*」是**秦系字形**
（归本层，不是隸書层）。材料的朝代（出處簡號后面的「秦」「西漢」「東漢」）不管用。

**上游原件是位图，本地 SVG 是自动描摹的派生件**——记法与保真核验见下一节。

---

## 小學堂（中央研究院）—— 字形圖片與字形屬性資訊（CC0 1.0）

| 项 | 内容 |
|---|---|
| 来源 | 中研院「小學堂」漢字 字形資料庫 <https://xiaoxue.iis.sinica.edu.tw/> |
| 许可声明页 | <https://xiaoxue.iis.sinica.edu.tw/License/License>（2026-10-30 取回） |
| 许可 | **CC0 1.0**（公有领域奉献，无义务） — <https://creativecommons.org/publicdomain/zero/1.0/> |
| 声明快照 | `src/licenses/xiaoxuetang-CC0-1.0-statement.md`（含原文引用）与 `.html`（逐字节副本） |

### 许可原文（照录，勿改写）

> 使用者操作本網站查詢介面所得之各解析度「字形圖片」及字形屬性資訊，權利人特於此明示主張以CC0 1.0通用方式，在法律許可的範圍內，拋棄該字形圖片及字形屬性資訊依著作權法可得享有之權利，使用者當可安心再行利用該查詢字形圖片及字形屬性資訊。

这份声明**点名了权利人、对象与范围**（各解析度的「字形圖片」与「字形屬性資訊」），
比汉典《服务条款》第四条的笼统归公宣告精确。本仓库古文字各层的直接授权依据见
`src/licenses/xiaoxuetang-CC0-1.0-statement.md`。

### 本仓库目前发布的小學堂衍生内容

本仓库目前发布的小學堂衍生内容共 **17,336 件描摹件**（五层），外加两张出處表对照与许可声明快照：

| 文件 | 内容 | 许可 |
|------|------|------|
| `glyphs/oracle/`（2,540 个描摹件） | 小學堂「甲骨文」庫的**位图**自动描摹件（上游原件是位图，本地 SVG 是派生件） | CC0 1.0 |
| `glyphs/bronze/`（3,401 个描摹件） | 小學堂「金文」庫的位图描摹件 | CC0 1.0 |
| `glyphs/clerical/`（1,812 个描摹件） | 小學堂「隸變」庫**「中研院隸書重文」字体**的位图描摹件 | CC0 1.0 |
| `glyphs/chuanchao/`（7,469 个描摹件） | 小學堂「傳抄古文字」庫的位图描摹件 | CC0 1.0 |
| `glyphs/qinwenzi/`（2,114 个描摹件 + 1,594 个漢典矢量件 + `index.csv` + 出处记录） | 小學堂「隸變」庫**「中研院秦系簡牘文字重文」字体**的位图描摹件；另有 1,594 个漢典矢量件从隸書层归位过来 | CC0 1.0 |
| `glyphs/chu/books_xxt.csv` | 小學堂「楚系簡帛」庫**出處表**的登记与对照（74 行：出處表原样行 + 按实测数据补的派生行） | CC0 1.0 |
| `glyphs/chuanchao/books_xxt.csv`（132 行） | 小學堂「傳抄古文字」庫**出處表**的登记与对照 | CC0 1.0 |
| `src/licenses/xiaoxuetang-CC0-1.0-statement.{md,html}` | 许可声明快照（原文引用 + 逐字节副本） | CC0 1.0 |

`books_xxt.csv` 里的 `corpus_full` 与 `source_publication`（文献全称、摹本底本与版本）
是**书目事实**，由中研院出處表照录；其中 `row_kind=派生` 的行由本仓库按实测数据补出，
每行 `note` 都写明依据，**未核实的全称保留〔待考〕标记**。

### 位图描摹件与「派生件」的记法

小學堂给的是**位图**，本仓库的 SVG 是**自动描摹**出来的派生件——
按 CC BY / CC0 的规则，矢量化与重绘都属于「改作」，所以每条记录另记：

- `derived_from`（上游位图路径）、`derived_from_sha256`（上游位图校验值）、
  `transform`（描摹参数：marching squares + Douglas-Peucker 容差 + Chaikin 平滑轮数）、
  `tool`（脚本与版本）；
- `trace_iou`：本地 SVG **回光栅化**与上游位图墨迹掩膜的 IoU（保真核验用）。
  门槛：单条 ≥ 0.97 合格、0.93–0.97 警戒、< 0.93 判失败；层级 p05 ≥ 0.96、失败率 ≤ 1%。
  机检入口：`python src/check_glyphs.py --trace-fidelity`。

**各层实测**（本仓库当前发布的 17,336 件描摹件）：

| 层 | 描摹件 | 最低 IoU | p05 | 中位 | 警戒 | 失败 |
|---|---|---|---|---|---|---|
| `glyphs/oracle/` | 2,540 | 0.9391 | 0.9752 | 0.9857 | 48 | 0 |
| `glyphs/bronze/` | 3,401 | 0.9363 | 0.9723 | 0.9888 | 131 | 0 |
| `glyphs/clerical/` | 1,812 | 0.9693 | 0.9854 | 0.9908 | 1 | 0 |
| `glyphs/chuanchao/` | 7,469 | 0.9369 | 0.9710 | 0.9814 | 288 | 0 |
| `glyphs/qinwenzi/` | 2,114 | 0.9872 | 0.9942 | 0.9962 | 0 | 0 |

**失败 0 件**——单条不合格的件都按单条闸挡在层外，层级 p05 全部 ≥ 0.96。
机检入口：`python src/check_glyphs.py --trace-fidelity`（只读 provenance 里记的 `trace_iou`）。

### 尚未发布的部分

- `glyphs/xiaozhuan/`（小學堂「小篆」庫）**尚未发布**；
- `glyphs/chu/` 目前发布的是漢典矢量件，小學堂楚系描摹件**尚未发布**；
- `glyphs/clerical/` 的小學堂批次**还差 565 件位图**——上游取图端点当前不可用
  （`xiaoxue.iis.sinica.edu.tw` 对本机所在地区返回「Access Restricted」，
  `char.iis.sinica.edu.tw` 改版成 Blazor 后旧渲染路由 `/ImageText2/ShowImage.ashx` 已下线）。
  缺口逐条记在 `glyphs/clerical/pending-xxt.csv`（含上游取图地址，端点恢复后可直接续抓）。

这些层入库时须另记
`derived_from` / `derived_from_sha256` / `transform` / `tool` / `trace_iou`。

**注意**：CC0 只处置中研院自己那部分权利，**不消灭摹本底本**（《甲骨文編》
《楚系簡帛文字編》《傳抄古文字編》《睡虎地秦簡文字編》等在版出版物）的著作权。
底本链条在上一节与本文件逐层说明。

---

## 现代书体六层 —— SIL OFL 1.1（从开源字体提取轮廓）

这六层的字形**不是上游的逐字节副本**，而是用 `src/extract_font_glyphs.py` 从 OFL 字体提取轮廓
生成的派生件：取字体轮廓路径、y 轴翻转（字体坐标 y 向上 → SVG y 向下）、坐标四舍五入到 0.01
字体单位；全层共用同一个画布（该层全部字形墨迹的并集外扩 1%），字形之间的相对比例与字体里一致。
可变字体按 `wght=400` 实例提取。

| 层 | 字体（版本） | 版权行 | 上游 |
|---|---|---|---|
| `glyphs/kaishu/` | Ma Shan Zheng 2.003 | Copyright 2018 The MaShanZheng Project Authors | `google/fonts` 的 `ofl/mashanzheng` |
| `glyphs/xingshu/` | Zhi Mang Xing 2.001 | Copyright 2018 The ZhiMangXing Project Authors | `google/fonts` 的 `ofl/zhimangxing` |
| `glyphs/caoshu/` | Liu Jian Mao Cao 1.003 | Copyright 2018 The Liu Jian Mao Cao Project Authors | `google/fonts` 的 `ofl/liujianmaocao` |
| `glyphs/songti/` | Noto Serif SC 2.003（`wght=400`） | Copyright 2012 Google Inc.（name 表：© 2017-2024 Adobe） | `google/fonts` 的 `ofl/notoserifsc` |
| `glyphs/songti-tc/` | Noto Serif TC 2.003（`wght=400`） | Copyright 2012 Google Inc.（name 表：© 2017-2024 Adobe） | `google/fonts` 的 `ofl/notoserifctc` |
| `glyphs/heiti-hk/` | Chiron Hei HK 2.530（`wght=400`） | Copyright 2025 The Chiron Hei HK Project Authors | [chiron-fonts/chiron-hei-hk](https://github.com/chiron-fonts/chiron-hei-hk) |

每层的 `SOURCE.md` 记着字体家族名、版本、上游路径、**字体二进制的 sha256**、取回时刻与变换说明；
每层的 `OFL.txt` 是**上游随附许可全文的逐字节副本**（sha256 见 `SOURCE.md`），版权行在文件抬头。

### OFL 1.1 的四条义务与履行方式

| OFL 条款 | 要求 | 本仓库怎么做的 |
|---|---|---|
| 第 2 条 | 每份副本带版权声明与许可全文 | 每层目录随附 `OFL.txt` 逐字节副本；`attribution` 逐条写明字体家族与「Copyright 见该层 OFL.txt」 |
| 第 3 条 | 修改版不得使用保留字体名（RFN） | 六个字体在 `OFL.txt` 抬头与**字体二进制 name 表**两处都**没有 RFN**；层名用通用书体名，字体家族名只出现在 `attribution` 与 `index.csv` |
| 第 5 条 | 修改版须完全按 OFL 分发，不得按其他许可分发 | 六层整层标 `OFL-1.1`，**不**混入 CC0 / CC BY；下游基于这些字形做的东西也必须按 OFL 分发 |
| 第 1 条 | 不得单独销售字体软件本身 | 本仓库不销售任何东西 |

**取用须知**：版权声明与许可全文随**层目录**提供（`OFL.txt` + `SOURCE.md`），
单个 SVG 文件里不含声明。把某个字形单独拷进其他项目时，请**连同该层的 `OFL.txt` 一并保留**，
并按 OFL 1.1 分发。

逐条款核验可复跑（正文与 SIL 官方文本 `src/licenses/OFL-1.1-official.txt` 逐条款比对，
并检查 RFN 与版权行）：

```bash
python src/verify_font_licenses.py --license-dir glyphs/kaishu --font <本地字体路径>
python src/build_font_license_evidence.py --font-dir <本地字体目录>
```

---

## `glyphs/seal/external.csv` 的上游登记 —— 開元小篆：只登记指针，不复制字形

`external.csv`（11,328 行）把每个 Unicode 篆书码位指向
[frankslin/kaiyuan-small-seal-font](https://github.com/frankslin/kaiyuan-small-seal-font)
里的字形文件，并记录其 git blob SHA-1；**不复制任何上游内容**，因此不构成对上游材料的分发。
`upstream_*` 列只是指针，**不涉及授权**。

本仓库没有直接引用上游字形，原因：上游的授权语句只覆盖「output fonts」，
而 `glyphs/` 被描述为流水线的生成物、没有目录级许可标记；随附的 `OFL.txt` 也不是 SIL 官方
OFL 1.1 文本。把 10,980 个文件标成 `OFL-1.1` 入库等于替上游背书一份它没有签过的协议，
所以只登记、不复制。上游若补齐许可文件，这一层可以按 OFL 1.1 正式导入。

登记时钉住的 commit 见 `glyphs/seal/external.meta.json` 的 `upstream_commit`。

---

## Unicode 数据（`SealSources.txt`）—— Unicode License v3

`glyphs/seal/external.csv` 的 `ccz` / `dyc` / `qjz` / `thx` / `radical_*` / `unicode` /
`modern_char` 列派生自 Unicode 18.0 的 `SealSources.txt`
（<https://www.unicode.org/Public/18.0.0/ucd/SealSources.txt>，见 UAX #60）。按该协议
条件 (b)，其版权与许可声明随本文件一并提供：

### 一处偏差修正

`SealSources.txt` 用 `kSEAL_MCJK` 记录「篆书码位 → 现代汉字」，其中 **U+3D06D 记成 U+738B（王）**，
但同一份文件的部首属性 `kSEAL_Rad` 自相矛盾：U+3D068 是第 5 部「王」部的部首字，
U+3D06D 是第 6 部「玉」部的部首字。OpenCC 的 `SealCharacters.txt` 也把 U+3D06D 记作「玉」。
本仓库按部首结构修正（**玉 → U+3D06D，王 → U+3D068**），修正在 `src/build_seal_registry.py`
的 `MCJK_DEVIATIONS` 里写死，逐行记在 `external.csv` 的 `note` 列。
**这是对 Unicode 数据的唯一一处改动**，其余列照录原文。

```
UNICODE LICENSE V3

COPYRIGHT AND PERMISSION NOTICE

Copyright © 1991-2026 Unicode, Inc.

NOTICE TO USER: Carefully read the following legal agreement. BY
DOWNLOADING, INSTALLING, COPYING OR OTHERWISE USING DATA FILES, AND/OR
SOFTWARE, YOU UNEQUIVOCALLY ACCEPT, AND AGREE TO BE BOUND BY, ALL OF THE
TERMS AND CONDITIONS OF THIS AGREEMENT. IF YOU DO NOT AGREE, DO NOT
DOWNLOAD, INSTALL, COPY, DISTRIBUTE OR USE THE DATA FILES OR SOFTWARE.

Permission is hereby granted, free of charge, to any person obtaining a
copy of data files and any associated documentation (the "Data Files") or
software and any associated documentation (the "Software") to deal in the
Data Files or Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, and/or sell
copies of the Data Files or Software, and to permit persons to whom the
Data Files or Software are furnished to do so, provided that either (a)
this copyright and permission notice appear with all copies of the Data
Files or Software, or (b) this copyright and permission notice appear in
associated Documentation.

THE DATA FILES AND SOFTWARE ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT OF
THIRD PARTY RIGHTS.

IN NO EVENT SHALL THE COPYRIGHT HOLDER OR HOLDERS INCLUDED IN THIS NOTICE
BE LIABLE FOR ANY CLAIM, OR ANY SPECIAL INDIRECT OR CONSEQUENTIAL DAMAGES,
OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THE DATA
FILES OR SOFTWARE.

Except as contained in this notice, the name of a copyright holder shall
not be used in advertising or otherwise to promote the sale, use or other
dealings in these Data Files or Software without prior written
authorization of the copyright holder.
```

---

## 第三方权利保留

甲骨文字形本身是三千年前的古文字，其刻划不产生著作权；《说文》篆形同理。
本仓库**不对古文字形本身主张任何权利**，只对自己新增的部分（轮廓派生、索引、脚本、
浏览页、文档）主张权利。

但本仓库注意到：JGW 上游自述其字形取自其「source hand copy」与 **2012 年的 source database**
（见上游 `data/provenance_manifest.csv`：`0380` 条目提到殷契文渊平台，`0916` 条目提到 2012 年
源数据库里的私用区码位 U+E83B），**上游并未披露该第三方来源的名称与许可状态**，本仓库无法核实。

- 若你是相关权利人，并认为本仓库内容侵犯了你的权利，请通过 GitHub Issue 或
  <1279190619@qq.com> 联系我们；我们会在核实后移除相应条目。
- 由于 `glyphs/provenance/` 一个文件一条，**单条字形可以独立移除而不影响其余内容**。
- 本仓库保留与上游逐字节一致的 sha256 记录，作为善意使用的证据。

---

## 代码

`src/**` 与 `viewer/**` 由本仓库编写，以 **CC0 1.0** 释出，说明见 `LICENSE-CODE`。
