# 字体层 OFL 1.1 许可证据（逐条复核用）

本文件是**证据汇总**，不是法律意见。它回答一个问题：
本仓库从 OFL 开源字体提取的那几层，许可文本**是不是 SIL 官方 OFL 1.1 原文**，
以及**有没有保留字体名（RFN）**——这是两层硬约束里最容易漏判的一处。

## 一句话结论

| 层 | 书体 | `OFL.txt` 条款文字相似度 | 原始排版相似度 | 逐条款一致 | `OFL.txt` RFN | 字体 name 表 RFN |
|---|---|---:|---:|---|---|---|
| `caoshu` | 草书 | 1.0000 | 1.0000 | 是 | 无 | 无 |
| `heiti-hk` | 黑体·港 | 1.0000 | 0.9672 | 是 | 无 | 无 |
| `kaishu` | 楷书 | 1.0000 | 1.0000 | 是 | 无 | 无 |
| `songti` | 宋体·简 | 1.0000 | 1.0000 | 是 | 无 | 无 |
| `songti-tc` | 宋体·繁 | 1.0000 | 1.0000 | 是 | 无 | 无 |
| `xingshu` | 行书 | 1.0000 | 1.0000 | 是 | 无 | 无 |

6 个层的 `OFL.txt` **条款文字与官方原文逐字相同**（条款文字相似度均 1.0000），
且 `OFL.txt` 抬头与**字体二进制的 name 表两处**都没有 RFN 声明——
因此本仓库可以用通用书体名（楷书/行书/草书/宋体·简/宋体·繁/黑体·港）给这几层命名，
字体家族名只出现在署名与 `index.csv` 里（OFL 第 3 条）。

**5 个层的原始排版也是 1.0000**，剩下的那层是上游把 OFL 转成了 Markdown（小节标题下多一条 `----` 下划线）——
**差的是排版不是条款**，两个数都列出来，差异不藏。

归一化后的正文 sha256 分成 2 组（排版不同则哈希不同）：
- `0339f4642e8741de…` —— `caoshu`、`kaishu`、`songti`、`songti-tc`、`xingshu`
- `d08f9149a4fa2fc9…` —— `heiti-hk`

## 复核方法

| 要查什么 | 怎么查 |
|---|---|
| 某一层的许可正文是不是官方原文 | `python src/verify_font_licenses.py --license-dir glyphs/<层> --markdown` |
| 字体本体有没有 RFN | 同上，加 `--font <字体路径>`（只看 `OFL.txt` 会漏判） |
| 本文件的数据 | `python src/build_font_license_evidence.py --font-dir <本地字体目录>` |
| 比对基准是哪一份 | `src/licenses/OFL-1.1-official.txt`，sha256 `1d361a8f8e8ce6e68457dcd93fb56e162e6baa3bbb7e7573a290d44399f6b57e`，等于 <https://openfontlicense.org/documents/OFL.txt> |

> 生成时间（UTC）：2026-10-24T21:55:59Z

## 草书（`glyphs/caoshu/`）

| 项 | 值 |
|----|----|
| 字体 | Liu Jian Mao Cao Version 1.003 |
| 上游字体原件 | https://github.com/google/fonts/raw/main/ofl/liujianmaocao/LiuJianMaoCao-Regular.ttf |
| 上游字体 sha256 | `cab396b91a5b7c0b4005a35891180d06e6751f5ac261fe680aec65c1ae209033` |
| 取回时刻（UTC） | 2026-10-24T18:04:38Z |
| 字形数 | 6763 |
| 本层 `OFL.txt` 字节 | 4406 |
| 本层 `OFL.txt` sha256 | `ff56684b0212481e7c3886c26d5a655de9b211c8119e5ccc756138a97b066acc` |
| 条款数（官方 / 本层） | 6 / 6 |
| `OFL.txt` 版权行 | Copyright 2018 The Liu Jian Mao Cao Project Authors (https://www.github.com/googlefonts/liujianmaocao) |
| `OFL.txt` RFN | 无 |
| 正文 sha256（归一化后） | `0339f4642e8741dea4841c236d258f360ffbe6e2cd3d032fbd0c10d1de8f58d1` |
| 字体 name 表 family | Liu Jian Mao Cao |
| 字体 name 表 version | Version 1.003 |
| 字体 name 表版权行 | Copyright 2018 The Liu Jian Mao Cao Project Authors (https://www.github.com/googlefonts/liujianmaocao) |
| 字体 name 表 RFN | 无 |
| 字体 sha256（复核时另算） | `cab396b91a5b7c0b4005a35891180d06e6751f5ac261fe680aec65c1ae209033` |

### 逐条款比对

| 条款 | 对应 OFL 1.1 段落 | 条款文字相似度 | 原始排版相似度 | 归一化后长度 |
|---:|---|---:|---:|---:|
| 0 | PREAMBLE + DEFINITIONS + 条件前言 | 1.0000 | 1.0000 | 1945 |
| 1 | 1) 允许使用与再分发 | 1.0000 | 1.0000 | 123 |
| 2 | 2) 每份副本须带版权声明与许可全文 | 1.0000 | 1.0000 | 412 |
| 3 | 3) 不得使用被保留的字体名（RFN） | 1.0000 | 1.0000 | 244 |
| 4 | 4) 不得单独销售字体软件本身 | 1.0000 | 1.0000 | 282 |
| 5 | 5) 终止与免责声明 | 1.0000 | 1.0000 | 981 |

判定：条款文字**逐字相同**。

## 黑体·港（`glyphs/heiti-hk/`）

| 项 | 值 |
|----|----|
| 字体 | Chiron Hei HK Version 2.530 (wght=400) |
| 上游字体原件 | https://github.com/google/fonts/raw/main/ofl/chironheihk/ChironHeiHK%5Bwght%5D.ttf |
| 上游字体 sha256 | `0d788ded72dc88f478818182179af4c7cd143df0bf86557d29729ab132333930` |
| 取回时刻（UTC） | 2026-10-24T19:25:20Z |
| 字形数 | 31598 |
| 本层 `OFL.txt` 字节 | 4443 |
| 本层 `OFL.txt` sha256 | `68b9a31cc191bb8f5f428f191209f7d08c6b5b0d4816a293e5bd230724e84f10` |
| 条款数（官方 / 本层） | 6 / 6 |
| `OFL.txt` 版权行 | Copyright 2025 The Chiron Hei HK Project Authors (https://github.com/chiron-fonts/chiron-hei-hk). |
| `OFL.txt` RFN | 无 |
| 正文 sha256（归一化后） | `d08f9149a4fa2fc9a3a9866628a3f6a13f5dd1c550c2dcaad1313a861fa7137d` |
| 字体 name 表 family | Chiron Hei HK ExtraLight |
| 字体 name 表 version | Version 2.530 |
| 字体 name 表版权行 | Copyright 2025 The Chiron Hei HK Project Authors (https://github.com/chiron-fonts/chiron-hei-hk) |
| 字体 name 表 RFN | 无 |
| 字体 sha256（复核时另算） | `0d788ded72dc88f478818182179af4c7cd143df0bf86557d29729ab132333930` |

### 逐条款比对

| 条款 | 对应 OFL 1.1 段落 | 条款文字相似度 | 原始排版相似度 | 归一化后长度 |
|---:|---|---:|---:|---:|
| 0 | PREAMBLE + DEFINITIONS + 条件前言 | 1.0000 | 0.9672 | 1945 |
| 1 | 1) 允许使用与再分发 | 1.0000 | 1.0000 | 123 |
| 2 | 2) 每份副本须带版权声明与许可全文 | 1.0000 | 1.0000 | 412 |
| 3 | 3) 不得使用被保留的字体名（RFN） | 1.0000 | 1.0000 | 244 |
| 4 | 4) 不得单独销售字体软件本身 | 1.0000 | 1.0000 | 282 |
| 5 | 5) 终止与免责声明 | 1.0000 | 0.9884 | 981 |

判定：条款文字**逐字相同**（差异只在排版分隔线（整行只有 - 或 =）；条款文字逐字相同）。

## 楷书（`glyphs/kaishu/`）

| 项 | 值 |
|----|----|
| 字体 | Ma Shan Zheng Version 2.003 |
| 上游字体原件 | https://github.com/google/fonts/raw/main/ofl/mashanzheng/MaShanZheng-Regular.ttf |
| 上游字体 sha256 | `6d2546bb189c732a8ca29af9e22457b152387d158aa459e4ac2ce1e51788b7fb` |
| 取回时刻（UTC） | 2026-10-24T17:57:06Z |
| 字形数 | 6763 |
| 本层 `OFL.txt` 字节 | 4397 |
| 本层 `OFL.txt` sha256 | `d7bdb1cee215b689e23c2f95672a6084c790542170648267a55114103d756a08` |
| 条款数（官方 / 本层） | 6 / 6 |
| `OFL.txt` 版权行 | Copyright 2018 The Ma Shan Zheng Project Authors (https://github.com/googlefonts/mashanzheng) |
| `OFL.txt` RFN | 无 |
| 正文 sha256（归一化后） | `0339f4642e8741dea4841c236d258f360ffbe6e2cd3d032fbd0c10d1de8f58d1` |
| 字体 name 表 family | Ma Shan Zheng |
| 字体 name 表 version | Version 2.003 |
| 字体 name 表版权行 | Copyright 2018 The MaShanZheng Project Authors (https://github.com/googlefonts/mashanzheng) |
| 字体 name 表 RFN | 无 |
| 字体 sha256（复核时另算） | `6d2546bb189c732a8ca29af9e22457b152387d158aa459e4ac2ce1e51788b7fb` |

### 逐条款比对

| 条款 | 对应 OFL 1.1 段落 | 条款文字相似度 | 原始排版相似度 | 归一化后长度 |
|---:|---|---:|---:|---:|
| 0 | PREAMBLE + DEFINITIONS + 条件前言 | 1.0000 | 1.0000 | 1945 |
| 1 | 1) 允许使用与再分发 | 1.0000 | 1.0000 | 123 |
| 2 | 2) 每份副本须带版权声明与许可全文 | 1.0000 | 1.0000 | 412 |
| 3 | 3) 不得使用被保留的字体名（RFN） | 1.0000 | 1.0000 | 244 |
| 4 | 4) 不得单独销售字体软件本身 | 1.0000 | 1.0000 | 282 |
| 5 | 5) 终止与免责声明 | 1.0000 | 1.0000 | 981 |

判定：条款文字**逐字相同**。

## 宋体·简（`glyphs/songti/`）

| 项 | 值 |
|----|----|
| 字体 | Noto Serif SC Version 2.003 (wght=400) |
| 上游字体原件 | https://github.com/google/fonts/raw/main/ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf |
| 上游字体 sha256 | `050080d9255a86808f2945bffac582b31ef32bc36411ce29563b4961670c66f9` |
| 取回时刻（UTC） | 2026-10-24T18:14:54Z |
| 字形数 | 27797 |
| 本层 `OFL.txt` 字节 | 4350 |
| 本层 `OFL.txt` sha256 | `5e0da210fb04058a8c0087985d2d456b931c2579811a49655721d3cf0c36b6d6` |
| 条款数（官方 / 本层） | 6 / 6 |
| `OFL.txt` 版权行 | Copyright 2012 Google Inc. All Rights Reserved. |
| `OFL.txt` RFN | 无 |
| 正文 sha256（归一化后） | `0339f4642e8741dea4841c236d258f360ffbe6e2cd3d032fbd0c10d1de8f58d1` |
| 字体 name 表 family | Noto Serif SC ExtraLight |
| 字体 name 表 version | Version 2.003-H1;hotconv 1.1.1;makeotfexe 2.6.0 |
| 字体 name 表版权行 | (c) 2017-2024 Adobe (http://www.adobe.com/). |
| 字体 name 表 RFN | 无 |
| 字体 sha256（复核时另算） | `050080d9255a86808f2945bffac582b31ef32bc36411ce29563b4961670c66f9` |

### 逐条款比对

| 条款 | 对应 OFL 1.1 段落 | 条款文字相似度 | 原始排版相似度 | 归一化后长度 |
|---:|---|---:|---:|---:|
| 0 | PREAMBLE + DEFINITIONS + 条件前言 | 1.0000 | 1.0000 | 1945 |
| 1 | 1) 允许使用与再分发 | 1.0000 | 1.0000 | 123 |
| 2 | 2) 每份副本须带版权声明与许可全文 | 1.0000 | 1.0000 | 412 |
| 3 | 3) 不得使用被保留的字体名（RFN） | 1.0000 | 1.0000 | 244 |
| 4 | 4) 不得单独销售字体软件本身 | 1.0000 | 1.0000 | 282 |
| 5 | 5) 终止与免责声明 | 1.0000 | 1.0000 | 981 |

判定：条款文字**逐字相同**。

## 宋体·繁（`glyphs/songti-tc/`）

| 项 | 值 |
|----|----|
| 字体 | Noto Serif TC Version 2.003 (wght=400) |
| 上游字体原件 | https://github.com/google/fonts/raw/main/ofl/notoseriftc/NotoSerifTC%5Bwght%5D.ttf |
| 上游字体 sha256 | `0077e18f57c6908f4a000969880940bdb0dad057c0e8d98b49dc364c3d1b09c6` |
| 取回时刻（UTC） | 2026-10-24T18:18:14Z |
| 字形数 | 17665 |
| 本层 `OFL.txt` 字节 | 4350 |
| 本层 `OFL.txt` sha256 | `5e0da210fb04058a8c0087985d2d456b931c2579811a49655721d3cf0c36b6d6` |
| 条款数（官方 / 本层） | 6 / 6 |
| `OFL.txt` 版权行 | Copyright 2012 Google Inc. All Rights Reserved. |
| `OFL.txt` RFN | 无 |
| 正文 sha256（归一化后） | `0339f4642e8741dea4841c236d258f360ffbe6e2cd3d032fbd0c10d1de8f58d1` |
| 字体 name 表 family | Noto Serif TC ExtraLight |
| 字体 name 表 version | Version 2.003-H1;hotconv 1.1.1;makeotfexe 2.6.0 |
| 字体 name 表版权行 | (c) 2017-2024 Adobe (http://www.adobe.com/). |
| 字体 name 表 RFN | 无 |
| 字体 sha256（复核时另算） | `0077e18f57c6908f4a000969880940bdb0dad057c0e8d98b49dc364c3d1b09c6` |

### 逐条款比对

| 条款 | 对应 OFL 1.1 段落 | 条款文字相似度 | 原始排版相似度 | 归一化后长度 |
|---:|---|---:|---:|---:|
| 0 | PREAMBLE + DEFINITIONS + 条件前言 | 1.0000 | 1.0000 | 1945 |
| 1 | 1) 允许使用与再分发 | 1.0000 | 1.0000 | 123 |
| 2 | 2) 每份副本须带版权声明与许可全文 | 1.0000 | 1.0000 | 412 |
| 3 | 3) 不得使用被保留的字体名（RFN） | 1.0000 | 1.0000 | 244 |
| 4 | 4) 不得单独销售字体软件本身 | 1.0000 | 1.0000 | 282 |
| 5 | 5) 终止与免责声明 | 1.0000 | 1.0000 | 981 |

判定：条款文字**逐字相同**。

## 行书（`glyphs/xingshu/`）

| 项 | 值 |
|----|----|
| 字体 | Zhi Mang Xing Version 2.001 |
| 上游字体原件 | https://github.com/google/fonts/raw/main/ofl/zhimangxing/ZhiMangXing-Regular.ttf |
| 上游字体 sha256 | `644e0cae9b40f0b10ab729a01bd32032e3973bac22be3dccae01bf6ae7fde969` |
| 取回时刻（UTC） | 2026-10-24T18:01:57Z |
| 字形数 | 6763 |
| 本层 `OFL.txt` 字节 | 4397 |
| 本层 `OFL.txt` sha256 | `10947328199e369a3e6b4a67e8e5507ed99d5bbb264a1f156415aa9b665e4d15` |
| 条款数（官方 / 本层） | 6 / 6 |
| `OFL.txt` 版权行 | Copyright 2018 The Zhi Mang Xing Project Authors (https://github.com/googlefonts/zhimangxing) |
| `OFL.txt` RFN | 无 |
| 正文 sha256（归一化后） | `0339f4642e8741dea4841c236d258f360ffbe6e2cd3d032fbd0c10d1de8f58d1` |
| 字体 name 表 family | Zhi Mang Xing |
| 字体 name 表 version | Version 2.001 |
| 字体 name 表版权行 | Copyright 2018 The ZhiMangXing Project Authors (https://github.com/googlefonts/zhimangxing) |
| 字体 name 表 RFN | 无 |
| 字体 sha256（复核时另算） | `644e0cae9b40f0b10ab729a01bd32032e3973bac22be3dccae01bf6ae7fde969` |

### 逐条款比对

| 条款 | 对应 OFL 1.1 段落 | 条款文字相似度 | 原始排版相似度 | 归一化后长度 |
|---:|---|---:|---:|---:|
| 0 | PREAMBLE + DEFINITIONS + 条件前言 | 1.0000 | 1.0000 | 1945 |
| 1 | 1) 允许使用与再分发 | 1.0000 | 1.0000 | 123 |
| 2 | 2) 每份副本须带版权声明与许可全文 | 1.0000 | 1.0000 | 412 |
| 3 | 3) 不得使用被保留的字体名（RFN） | 1.0000 | 1.0000 | 244 |
| 4 | 4) 不得单独销售字体软件本身 | 1.0000 | 1.0000 | 282 |
| 5 | 5) 终止与免责声明 | 1.0000 | 1.0000 | 981 |

判定：条款文字**逐字相同**。
