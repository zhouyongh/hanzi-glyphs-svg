# 第三方内容与署名

本仓库的**数据**与**代码**许可是分开的，数据许可还**逐书体**不同。使用任一内容前，请读本文件
与 `glyphs/provenance/<书体>.jsonl`（一个文件一条，含 `license` 与 `attribution` 字段），
并用 `python src/verify_provenance.py` 校验。

**发布状态**：本文件描述的范围**大于**当前公开发布的范围。公开仓库里只有
甲骨 JGW 批（CC BY 4.0）与篆书（CC0 1.0）；金文、隶书、楚文字、傳抄古文，
以及甲骨层里来自汉典的拓片摹本，**已整理但暂缓发布**——原因见「汉典『书法』字形」一节开头的
说明。保留它们的出处与权利说明有两个用处：让「为什么暂缓」有据可查；授权澄清后可以原样接上。

## 许可地图（公开发布的部分）

| 范围 | 许可 | 全文 |
|------|------|------|
| `glyphs/oracle/**`（甲骨 JGW 骨架 1,203 个 + 派生轮廓 1,203 个 + 索引 + 出处记录） | **CC BY 4.0** | 根 `LICENSE` |
| `glyphs/seal/**`（篆书 10,591 个字形、索引、出处记录） | **CC0 1.0**（公有领域奉献，无义务） | `LICENSE-DOCS`（全文）；汉典的归公宣告原文见本文件 |
| `glyphs/provenance/oracle.jsonl`、`glyphs/provenance/seal.jsonl` | **逐条记录**：每条按其 `license` 字段（CC BY 4.0 / CC0 1.0） | 本文件 + 根 `LICENSE` |
| `glyphs/seal/external.csv` —— 本仓库整理的部分 | CC BY 4.0 | 根 `LICENSE` |
| `glyphs/seal/external.csv` —— 派生于 Unicode `SealSources.txt` 的列 | Unicode License v3（声明见下） | 本文件 |
| `glyphs/seal/external.csv` 的 `upstream_*` 列（指向上游） | **不适用**：本仓库未复制上游内容，只登记指针 | — |
| `README.md`、`AGENTS.md`、本文件 | CC0 1.0（无义务） | `LICENSE-DOCS` |
| `src/**`、`viewer/**` | MIT | `LICENSE-CODE` |

**根 `LICENSE`（CC BY 4.0）只覆盖 CC BY 4.0 那一层**（甲骨 JGW 层，以及篆书登记表里本仓库整理的
部分），**不覆盖** CC0 与 Unicode 授权的材料。下游须按各层许可分别使用。

---

## `glyphs/oracle/` —— 甲骨文字形（公开发布的只有 JGW 批）

本目录设计上可放两批字形，**当前公开仓库里只有第一批**：

| 批次 | 数量 | 许可 | 发布状态 |
|------|------|------|----------|
| **JGW 参数化矢量骨架** | 1,203（+ 1,203 个派生轮廓） | **CC BY 4.0** | **已发布**，见本节 |
| **汉典拓片摹本** | 10,213（逐件带《甲骨文合集》合号 + 拓片号 + 卜辞组别） | **CC0 1.0**（上游声明） | **暂缓发布**，见下节「汉典『书法』字形」 |

两批都是 `script=oracle`、`layer=skeleton`，划分靠 `source_dataset`
（JGW 那批是数据集全名，汉典那批是「汉典（zdic.net）甲骨文字形」），
在 `index.csv` 里靠 `char_form` 列（JGW 那批有值，汉典那批为空）。
将来两批并存时**逐条看 `license` 字段最保险**。

### JGW 批次

| 项 | 内容 |
|---|---|
| 来源数据集 | Oracle Bone Glyphs: Parametric Vector Dataset (**v0.3**) |
| 作者 | Li, Qing-sheng；Bian, Yu-lin（浙江传媒学院） |
| DOI | [`10.5281/zenodo.22467946`](https://zenodo.org/records/22467946) |
| 镜像 | [github.com/aylqs2025/oracle-bone-jgw-1203](https://github.com/aylqs2025/oracle-bone-jgw-1203)（tag `v0.3`，commit `5496ad559f81ae8632f3915e8ec2beb705c64ba3`） |
| 原件 | `aylqs2025/oracle-bone-jgw-1203-v0.3.zip`，MD5 `7764c7f5b0feb8f0052c36233ddf8d4b` |
| 许可 | **CC BY 4.0**（上游 `/data`、`/figs`） — <https://creativecommons.org/licenses/by/4.0/> |
| 校验 | 1,203 个骨架文件与 Zenodo 原件逐一 sha256 **全部一致**；Zenodo zip 的 MD5 与官方公布值一致。 |
| 未收录 | 上游 `data/svg_parametric/`（解析重建后的光滑化版本）、`src/`、`figs/`。 |

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
3. 新增了本仓库自己的 `index.csv`、`glyphs/provenance/<书体>.jsonl`、`src/**` 脚本、`viewer/` 浏览页与文档。
4. 上述修改**不改变上游材料的许可状态**：`glyphs/oracle/*.svg` 与
   `glyphs/oracle/outline/*.svg` 均继续适用 CC BY 4.0；任何下游使用都须遵守 CC BY 4.0
   （含署名与改动声明要求）。本仓库未对下游附加任何额外限制。

### 派生层 `glyphs/oracle/outline/`

- 派生件沿用上游的 **CC BY 4.0** 与同一署名要求。
- 每个派生文件的出处记在 `glyphs/provenance/oracle.jsonl`（`layer: "outline"`，含
  `derived_from` 与 `derived_from_sha256` 指回骨架）。

### 相关论文

Li, Qing-sheng and Bian, Yu-lin. *An Interpretable Parametric Representation and Open
Dataset for Oracle Bone Script: Adaptive Arc Segmentation and SVG Resource.*
npj Heritage Science (2026).

> ⚠️ **论文与数据集的许可不同**。论文正文依 Crossref 记录为 **CC BY-NC-ND 4.0**，
> 而数据集是 CC BY 4.0。本仓库**只依据数据集**使用字形，**没有**收录论文的任何文本或图表。

### 上游自述的限制（转录，非本仓库添加）

- 上游每个字只提供**一个代表字形**；异形、跨阶段字形演变、贞人（scribe group）风格分析
  均明确不在其范围内。
- 上游自述：最锐的钩笔分段存在少量**残环**（中位重建误差 0.0026）。
- **甲骨文在 Unicode 中没有码位**；每条记录的 `unicode` 指的是对应**现代汉字**的码位，
  不是甲骨文字形自身的码位。
- v0.3 中有 **33 个现代字各对应 2 个条目**（如 `0013` 与 `1149` 都是「祥」），
  属考古学上的分化，不是重复标注；身份请以 `glyph_id` 为准。
- `0380`、`0916` 两条没有可对应的现代汉字（前者作者在殷契文渊查无、后者是旧库私用区
  U+E83B，仅作历史留痕）；`1180`（妞）的身份为 `provisional`。

---

## 汉典「书法」字形（上游声明 CC0 1.0）—— 除篆书外**均暂缓发布**

> **这一节解释的是「暂缓发布」的那几批**（甲骨拓片摹本、金文、隶书、楚文字、傳抄古文）。
> 公开仓库里只有篆书一层来自汉典，适用同一节前四段（来源、直链、归公宣告、改动声明），
> 且它的底本是《说文》刻本系统（公有领域），不涉及下面的「残余风险」。
>
> 暂缓的理由：这些字形是**「摹本 + 矢量化」**的产物，汉典的 CC0 放弃的是**汉典自己的权利**，
> 不消灭底本出版物的著作权；底本为在版现代出版物时，本仓库选择先不发布。

| 项 | 内容 |
|---|---|
| 来源 | 汉典（zdic.net）「书法」字形实例 |
| 实例页 | `https://www.zdic.net/hans/<字>/<kind>`（`<kind>`：`jinwen` 金文 / `lishu` 隶书 / `xiaozhuan` 小篆 / `jiaguwen` 甲骨文 / `chuwenzi` 楚系簡帛） |
| 字形文件直链 | `https://img.zdic.net/zy/<kind>/<id>.svg` |
| 许可 | **CC0 1.0**（汉典《服务条款》第四条「归公宣告」） |
| 规模 | 金文 `glyphs/bronze/`；隶书 `glyphs/clerical/`；篆书 `glyphs/seal/`；楚文字 `glyphs/chu/`；甲骨文在 `glyphs/oracle/`（与 JGW 骨架同层，靠 `source_dataset` 区分批次） |

### 许可原文（照录，勿改写）

> 四、归公宣告
> 汉典奉行 CC0 1.0 公约，将本站字词、古籍、诗词、书法诸作，悉数贡献天下，放弃著作专权及邻接法益，任人取用，以公无穷。
>
> —— <https://www.zdic.net/terms/>（2026-10-23 核验）

CC0 1.0 是**公有领域奉献**：不设任何条件，不署名、不注明改动也可以使用。

### 出处粒度

每个字形在 `glyphs/provenance/<书体>.jsonl` 与 `index.csv` 里逐件记清**出处作品（器名 / 碑帖名）、
编号、时代**，例如：

- 金文：`曶鼎` / `集成2838` / `西周中期`
- 隶书：`睡.日甲111背` / `秦`
- 小篆：`說文‧心部`（正篆；「說文古文」「說文籀文」「說文或體」是另几种形式）
- 甲骨文：`乙3400` / `合1285` / `賓組`（拓片号 / 《甲骨文合集》合号 / 卜辞组别）
- 楚文字：`信` / `1.23`（出土文献简称 / 位置编号；**没有时代**，见下节）

现代字与码位另见各层 `index.csv`。篆书层的键不是现代字码位而是
**Unicode 篆书区块码位**（`U+3D000`–`U+3FC3F`，5 位十六进制），现代字码位在
`unicode` 列反查。

### 本仓库做了哪些修改

1. **去水印。** 汉典的金文与篆书字形 SVG 里带一层**近白色的角标水印**（近白填充 `#fafafb`
   一类，与字形笔画零重叠，占画布 0.16%–0.46%）。本仓库用 `src/clean_zdic_glyphs.py` 把
   「有效填充色接近纯白」的 `<g>` / `<path>` 元素**整块删掉**，其余字节原样保留。
   **CC0 不设任何条件**，此项改动无需授权，也不产生「相同方式共享」的义务。
   每个字形的改动情况记在 `glyphs/provenance/<书体>.jsonl` 的 `modifications` 字段。
2. **剔除位图实例。** 汉典有个别实例不是矢量轮廓，而是把 PNG 以 base64 塞进
   `<image xlink:href="data:image/png;base64,…">`（2026-10-23 实测：小篆「挈」「挂」两字）。
   这类文件虽是合法 SVG，却不是**矢量字形**（转字体、缩放、取轮廓都用不上），
   而且水印与笔画烤在同一张位图里分不开。本库只收矢量字形，
   `src/clean_zdic_glyphs.py` 将其剔除并在清单的 `raster_gate` 字段留痕。
   这两个篆书码位（`3F32F`、`3F41A`）因此空缺。
3. **留痕。** 逐字形记录了 `source_sha256`（上游原件）与本地 `sha256`，可与汉典原件逐一比对。

### 残余风险须知（与甲骨层同类，须一并阅读）

> **残余风险须知（与甲骨层同类，须一并阅读）。** 汉典的 CC0 宣告放弃的是**汉典自己的权利**，
> **不能消灭底本出版物的著作权**：这些字形是「摹本 + 矢量化」的产物，底本为现代出版物
> （《殷周金文集成》《睡虎地秦简文字编》《秦汉魏晋篆隶字形表》等）。本仓库只对自己新增的
> 索引、脚本、文档主张权利，**不对字形及其底本摹本主张任何权利**。
>
> 若你是相关权利人，并认为本仓库内容侵犯了你的权利，请通过 GitHub Issue 或
> <1279190619@qq.com> 联系我们；我们会在核实后移除相应条目。由于 `glyphs/provenance/<书体>.jsonl` 一个文件一条，
> **单条字形可以独立移除而不影响其余内容**。

### 底本同样列在汉典自己的「字书所据」里

汉典《服务条款》第一条「字书所据」自述：

> 字源字形：广征甲骨、金文、楚简、秦牍之编，若《甲骨文编》《金文编》《战国古文字典》之属；及《说文》诸家疏证，若《诂林》《新证》之属。

也就是说，字形的**底本是有著作权的现代出版物**——这正是上面「残余风险须知」所说的那条链子。

### 楚文字层：这条链子多了一层，且汉典自己把底本列了出来

`glyphs/chu/`（汉典「楚系簡帛」）的底本链条比其它书体更清楚，汉典在**每个字页底部**
列了「参考文献」段，把这份字形所依据的**摹本底本 + 页.行**逐条写明，例如「月」字页：

> 《楚系簡帛文字編》（增訂本）（湖北教育出版社），頁.行：655.9、658.10
> 《睡虎地秦簡文字編》（文物出版社）頁.行：106.2
> 《秦簡牘文字編》（福建人民出版社）頁：202
> 《戰國古文字典：戰國古文聲系》（中華書局）冊頁：下911、上816
> 《傳抄古文字編》（綫裝書局）冊頁.行：中660.5
> 《秦漢魏晉篆隸字形表》（四川辭書版社）頁：459

本仓库把这一段**逐字形**记进 `glyphs/provenance/<书体>.jsonl` 的 `source_references` 字段——
这正是「如实标注摹本底本链条」的证据。

链条是：

```
原简帛 → 各家考古整理本（郭店、包山、上博、望山、九店、马王堆帛书等）
       → 滕壬生《楚系简帛文字编》（湖北教育出版社，1995 初版 / 2008 增订本，
          ISBN 9787535146939）的摹本或照片复印件
       → 汉典转录并以 CC0 1.0 释出
```

该编《凡例》第二条自述其材料「一類是照片掃描字形或照片複印件；另一類是摹本」，
摹本「嚴格按照原物照片摹寫」。所以本层字形**不是原件扫描**，而是摹本/复印件的矢量化。

**本仓库的立场与其它汉典书体一致**：不对字形及其摹本主张任何权利，只逐条标注链条；
单条字形可独立移除（`glyphs/provenance/<书体>.jsonl` 一个文件一条）。

`glyphs/chu/books.csv` 登记汉典题记里的**出土文献简称**与出土文献全称的对照，
每条带 `confidence` 列；**未考定的（如 `新甲`/`新乙`/`新零`）明确标注，不臆造墓名**。

### 傳抄古文层：底本是徐在國《傳抄古文字編》

`glyphs/chuanchao/`（汉典「傳抄古文」）的底本是**徐在國《傳抄古文字編》**
（綫裝書局，2006 年）——汉典在每个字页底部的「参考文献」段里明写：

> 徐在國：《傳抄古文字編》〈綫裝書局，2006年〉
> 《傳抄古文字編》（綫裝書局） 冊頁.行：中495.5

本仓库把这一段**逐字形**记进 `glyphs/provenance/<书体>.jsonl` 的 `source_references` 字段
（29,260 个字形**全部**带这条记录）。链条是：

```
先秦文字 → 历代传抄本（《说文》古文、魏三体石经、《汗简》《古文四声韵》
        《集篆古文韵海》《三体阴符经》、碧落碑、大嚮记碑、历代墓志等）
        → 徐在國《傳抄古文字編》（綫裝書局，2006）摹录汇编（十四卷 + 附录二卷）
        → 汉典转录并以 CC0 1.0 释出
```

> **一条要说清楚的事**：汉典字页底部的「参考文献」段是**全站通用**的——
> 同一个字在金文页、隶书页、楚文字页上挂着**同一组书名**，
> 那一组书名是这个字在**各个书体里**都出现过的底本，
> 不等于本层字形逐个对应那一整段里的每一本。
> 本层字形的**精确指针**是那一段里的
> **《傳抄古文字編》條目及其「冊頁.行」**；本仓库按上游原文整段记录，不做取舍，
> 由下游按「哪一条是该层的底本」自行判断。

**本仓库的立场与其它汉典书体一致**：不对字形及其摹本主张任何权利，只逐条标注链条；
单条字形可独立移除（`glyphs/provenance/<书体>.jsonl` 一个文件一条）。

`glyphs/chuanchao/books.csv` 登记汉典题记里的**源书代号**与传抄本全称的对照
（23 个代号：說 / 說籀 / 石 / 石附 / 石補 / 京一 / 京二 / 合 / 所 / 隸 / 碧 / 施 / 陽 /
汗 / 汗目 / 四 / 三 / 陰 / 海 / 磚 / 宋 / 大嚮記碑 / 金），每条带 `confidence` 列；
**未考定的（`三`）明确标注，不臆造书名**。
考订依据是徐书自身的成果简介（11 类来源清单）、题记的相邻全序与编号对撞三条证据，
详见 `glyphs/chuanchao/README.md`。

---

## `glyphs/seal/` 的上游登记 —— 開元小篆：**只登记指针，不复制字形**

篆书层的**字形本身来自汉典（CC0 1.0，同上一节）**。本节说的是本目录里**另有一份**
指向另一个上游的登记表：`external.csv`（11,328 行）把每个 Unicode 篆书码位指向
上游仓库里的字形文件，并记录其 git blob SHA-1；**不复制任何上游内容**，因此不构成
对上游材料的分发。详见 `glyphs/seal/README.md`。

| 项 | 内容 |
|---|---|
| 上游仓库 | [frankslin/kaiyuan-small-seal-font](https://github.com/frankslin/kaiyuan-small-seal-font)（開元小篆） |
| 登记时钉住的 commit | 见 `glyphs/seal/external.meta.json` 的 `upstream_commit` |
| 上游字形文件数 | 10,980（另有 348 个码位上游尚无字形） |
| 上游声明的许可 | SIL Open Font License 1.1（**但上游随附的 `OFL.txt` 并非官方 OFL 1.1 文本**，见下） |
| 本仓库的处理 | **不复制、不改作、不再分发**；只登记路径与 blob SHA |

### 为什么没有直接引用上游字形

登记时发现**一处**缺漏，可在上游仓库复现：

1. 上游的授权语句只覆盖「**output fonts**」（其 README 写「字型：SIL OFL 1.1」，
   `AGENTS.md` 写 "Output fonts are released under the SIL Open Font License 1.1"），
   而 `glyphs/` 被描述为流水线的生成物（"Generated, but committed so reviewers can
   diff them"）。OFL 对 "Font Software" 的定义是「由版权人以本协议发布、并被
   **明确标记为此**的一组文件」，而上游 `glyphs/` 下没有任何许可标记或目录级声明，
   仓库根目录也没有 LICENSE 文件（只有 `OFL.txt`）。

本仓库对此的处理是**只登记、不复制**，并欢迎上游澄清后升级为正式导入。
若你是上游权利人并希望我们调整登记方式，请通过 Issue 或 <1279190619@qq.com> 联系。

### 核验结论（2026-10-23，三次更正）

早先版本的本文件先称「上游 `OFL.txt` 与其声明的 OFL 1.1 不一致」，后经一次核验改称
「上游随附的是 SIL 发布过的 OFL 1.1 文本（10 条条款措辞），只是与 SPDX 的 5 条措辞
不同」。**第二次更正把话说反了：上游随附的并不是 SIL 的 OFL 1.1 文本。**
这一节的结论是本仓库对篆书层「只登记、不复制」的直接依据，故按实测重写。

实测（2026-10-23，取上游 commit `97433695858330ec9fdb7de9c4604da2f635eba6` 的
`OFL.txt`，5,312 字节，与 `main` 分支内容一致），逐条与 SIL 官方文本
（<https://openfontlicense.org/documents/OFL.txt>）、SPDX
（<https://spdx.org/licenses/OFL-1.1.txt>）及现行字型项目随附文本
（LXGW Seal <https://cdn.jsdelivr.net/gh/lxgw/LxgwSeal@main/OFL.txt>）比对：

| 比对项 | 上游 `OFL.txt` | SIL 官方 OFL 1.1 |
|---|---|---|
| 条款数 | **10** | **5** |
| 第 1、2 条 | 与官方**逐字相同**（条款正文相似度 1.000；连编号写法一并比对时为 0.992 / 0.998） | 同 |
| 第 3–9 条 | 与官方 5 条**编号条款**的最高相似度 **0.344** | — |
| 第 10 条 | 与官方第 5 条最接近，相似度 **0.602** | — |
| 第 3–5 条 | **非官方原文**：是 OFL 条款的改写残句（与 OFL 1.1 官方条款相似度最高 **0.344**、与归档的 OFL 1.0（2005）条款最高 **0.310**） | 与之不同 |
| 第 6–10 条 | **自订条款**，官方两版中均不存在（与 OFL 1.1 官方条款相似度最高 0.602，即第 10 条与官方第 5 条） | — |
| 「must be distributed entirely under this license, and must not be distributed under any other license」 | **缺** | 有（官方**第 5 条**；官方第 3 条是 Reserved Font Name 条款） |
| `TERMINATION` 段 | **缺** | 有 |
| `DISCLAIMER` 段 | 改写为 `NO WARRANTY`，并删去专利 / 商标 / 不侵权三项 | 有 |
| `Reserved Font Name` 定义段 | **缺**（第 5 条用了这个词，却从未定义；抬头也没有「with Reserved Font Name」） | 有 |
| 抬头句 | 有 `This Font Software is licensed under the SIL Open Font License, Version 1.1.` | 同 |

> **相似度的度量口径**（否则数字不可复现）：条款按**行首编号**切分，条款文本**保留原编号写法**
> （上游 `1.` / 官方 `1)`），空白折叠为单空格后取 `difflib.SequenceMatcher` 的 ratio；
> 候选集合为官方的 5 条编号条款。逐条复算的脚本与中间产物见 `tmp/research/`（未入库）。

结论：**上游随附的是一份自撰改写的混合文本**（OFL 1.1 的第 1、2 条 + 第 3–5 条 OFL 条款的
改写残句 + 第 6–10 条自订条款），**不是** SPDX 的 `OFL-1.1`，官方**第 5 条**「不得按其他许可分发」这一最关键的
条款也不在其中。GitHub 对该仓库的许可识别同样是 `NOASSERTION`。

所以，**把这 10,980 个文件标成 `OFL-1.1` 入库是不实标注**——等于替上游背书一份它没有
签过的协议文本，也违反本仓库「如实写来源」的硬规则。加上上一节说的第二处缺口
（授权语句只写到 output fonts，`glyphs/**` 无任何目录级标记），本仓库对这一层的处理是
**只登记、不复制**，并欢迎上游澄清后升级为正式导入。

另据上游 **README.md 第 104 行**原文：「**公版底本**：字形由公版刻本的掃描描出，
不參考現代篆書字型，著作權狀態清楚，**可依 OFL 自由修改、再發行**。」——这是**上游自己
对「字形可依 OFL 自由修改、再发行」的表述**，是本层最有力的一条依据，也是上游日后
补齐许可文件时最自然的落点。

上游**未声明 Reserved Font Name**，故即便日后补齐许可文件，本层也不涉改名义务；
若上游日后声明，需重新评估。

### 上游补齐许可文件后，本仓库会怎么做

上游只要做三件事，缺口即关闭，本仓库即可一次性按 OFL 1.1 正式导入
（`glyphs/seal/external.csv` 已逐条对账 10,980 个 blob SHA-1，导入管线是现成的）：

1. 把根 `OFL.txt` 换成 SIL 官方逐字原文（保留其版权抬头）；
2. 在 `glyphs/` 下加目录级标记（`glyphs/LICENSE` 或 README 一行），写明该目录的字形
   是本字型 Font Software 的一部分、依 OFL 1.1 发布（OFL 要求 *clearly marked as such*）；
3. 明确 Reserved Font Name（声明或明确写「无」），并在根目录加 `LICENSE`。

复核入口：
`https://raw.githubusercontent.com/frankslin/kaiyuan-small-seal-font/97433695858330ec9fdb7de9c4604da2f635eba6/OFL.txt`
与 <https://openfontlicense.org/documents/OFL.txt>（2026-10-23 核验）。
逐条比对脚本与中间产物见 `tmp/research/`（未入库）。

---

## Unicode 数据（`SealSources.txt`）—— Unicode License v3

`glyphs/seal/external.csv` 的 `ccz` / `dyc` / `qjz` / `thx` / `radical_*` / `unicode` /
`modern_char` 列派生自 Unicode 18.0 的 `SealSources.txt`
（<https://www.unicode.org/Public/18.0.0/ucd/SealSources.txt>，见 UAX #60）。按该协议
条件 (b)，其版权与许可声明随本文件一并提供：

### 一处偏差修正

`SealSources.txt` 用 `kSEAL_MCJK` 记录「篆书码位 → 现代汉字」，
其中 **U+3D06D 记成 U+738B（王）**，但同一份文件的部首属性 `kSEAL_Rad` 自相矛盾：

| 码位 | `kSEAL_Rad` | 含义 |
|------|-------------|------|
| U+3D068 | `5.3D068` | 说文第 5 部「王」部的部首字 |
| U+3D06D | `6.3D06D` | 说文第 6 部「玉」部的部首字 |

说文 540 部里第 5 部是「王」、第 6 部是「玉」，两部相邻、各有各的首字；
若 U+3D06D 真是「王」的重文，它不可能同时是「玉」部的部首字。
OpenCC 的 `SealCharacters.txt` 也把 U+3D06D 记作「玉」。
**不修正的后果很实际**：按原文口径「玉」没有任何篆书码位，
抓取名单里就根本没有「玉」这个字，篆书层永远缺一块。

本仓库按部首结构修正（**玉 → U+3D06D，王 → U+3D068**），
修正在 `src/build_seal_registry.py` 的 `MCJK_DEVIATIONS` 里写死，
逐行记在 `external.csv` 的 `note` 列，并汇总进 `external.meta.json` 的 `deviations`。
生成脚本对修正前提做校验：上游 `SealSources.txt` 将来若改了这条映射，
脚本会直接报错要求复核，而不是默默沿用旧结论。
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

甲骨文字形本身是三千年前的古文字，其刻划不产生著作权，本仓库**不对古文字形本身主张任何权利**。

但本仓库注意到：上游数据集自述其字形取自其「source hand copy」与 **2012 年的 source database**
（见上游 `data/provenance_manifest.csv`：`0380` 条目提到殷契文渊平台，`0916` 条目提到 2012 年
源数据库里的私用区码位 U+E83B），**上游并未披露该第三方来源的名称与许可状态**，本仓库无法核实。

- 本仓库只对自己新增的部分（轮廓派生、索引、脚本、浏览页、文档）主张权利。
- 若你是相关权利人，并认为本仓库内容侵犯了你的权利，请通过 GitHub Issue 或
  <1279190619@qq.com> 联系我们；我们会在核实后移除相应条目。
- 由于 `glyphs/provenance/<书体>.jsonl` 一个文件一条，**单条字形可以独立移除而不影响其余内容**。
- 本仓库保留与上游逐字节一致的 sha256 记录，作为善意使用的证据。
- 汉典层（金文、隶书）的**底本摹本**同样属于第三方权利保留的范围，细节见「汉典「书法」字形（CC0 1.0）」一节。

---

## 代码

`src/**` 与 `viewer/**` 由本仓库编写，以 **MIT** 授权，全文见 `LICENSE-CODE`。
