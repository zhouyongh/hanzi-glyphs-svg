# 宋体·繁体层（`glyphs/songti-tc/`）

| 项 | 值 |
|----|----|
| 书体 | 宋体·繁体（Song / Ming script, Traditional Chinese） |
| 字体 | Noto Serif TC Version 2.003 (wght=400) |
| 上游仓库 | google/fonts，目录 `ofl/notoseriftc` |
| 上游文件 | `NotoSerifTC[wght].ttf` |
| 上游字体 sha256 | `0077e18f57c6908f4a000969880940bdb0dad057c0e8d98b49dc364c3d1b09c6` |
| 上游许可 | 本目录下的 `OFL.txt`（上游逐字节副本，sha256 `5e0da210fb04058a8c0087985d2d456b931c2579811a49655721d3cf0c36b6d6`） |
| 许可标识 | OFL-1.1 |
| 保留字体名（RFN） | 无（`OFL.txt` 抬头无 RFN 声明；**字体二进制的 name 表也无**） |
| 字体 name 表版权行 | `(c) 2017-2024 Adobe (http://www.adobe.com/).` |
| 字体 name 表 RFN | 无 |
| 取回时刻（UTC） | 2026-10-24T18:18:14Z |
| 提取工具 | fontTools 4.67.0 (SVGPathPen) + src/extract_font_glyphs.py |
| 变换 | font-outline-to-svg: 用 fontTools 的 SVGPathPen 取字体轮廓路径，y 轴翻转（字体坐标 y 向上 → SVG y 向下），坐标四舍五入到 0.01 字体单位；可变字体按 location=wght=400 取实例；viewBox 取该层全部字形墨迹的并集外扩 1%，全层共用同一个画布，字形之间的相对比例与字体里一致 |
| 字形数 | 17665 |
| 画布 | `1 -873 1004 990`（全层共用；按本层全部字形墨迹的并集外扩 1% 定） |
| 层的键 | 现代字 Unicode 码位，6 位大写十六进制（`index.csv` 的 `codepoint` 列） |

## 复核入口

| 要查什么 | 怎么查 |
|----------|--------|
| 许可正文是不是官方 OFL 1.1 | `python src/verify_font_licenses.py --license-dir glyphs/songti-tc` |
| 字体本体有没有声明 RFN | `python src/verify_font_licenses.py --license-dir glyphs/songti-tc --font <本地字体路径>`（RFN 可能只写在字体里，只看 `OFL.txt` 会漏判） |
| 比对基准是哪一份 | `src/licenses/OFL-1.1-official.txt`，sha256 `1d361a8f8e8ce6e68457dcd93fb56e162e6baa3bbb7e7573a290d44399f6b57e`，等于 <https://openfontlicense.org/documents/OFL.txt> |
| 官方原文 | <https://openfontlicense.org/documents/OFL.txt> |
| 上游字体原件 | https://github.com/google/fonts/raw/main/ofl/notoseriftc/NotoSerifTC%5Bwght%5D.ttf |
| 上游许可原件 | https://github.com/google/fonts/blob/main/ofl/notoseriftc/OFL.txt |
| 逐字形的出处 | `glyphs/provenance.jsonl` 里 `script=songti-tc` 的记录 |

## OFL 1.1 对本层的四条硬约束

1. **整层以 OFL-1.1 分发**，不得改成 CC0、不得改成 CC BY。
2. **每份副本都要带版权声明与许可全文**（OFL 第 2 条）——
   本目录下的 `OFL.txt` 就是许可全文，版权声明见上表与 `provenance.jsonl` 的 `attribution`。
3. **不得使用被保留的字体名（RFN）**（OFL 第 3 条）——本字体**没有**保留字体名声明，本层以通用书体名命名，字体家族名只出现在署名与 `index.csv` 里。
4. 另外第 1 条规定**不得单独销售**字体软件本身；本仓库不销售任何东西。
