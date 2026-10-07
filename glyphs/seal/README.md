# `glyphs/seal/` —— 篆书层（**外部登记，本仓库不含字形文件**）

这里**没有字形 SVG**。本目录只放一份「映射表」：把 Unicode 18.0 篆书区块的每个码位，
指到上游仓库里对应的字形文件。**我们不复制上游的任何字形内容**，只登记指针。

## 文件

| 文件 | 内容 |
|------|------|
| `external.csv` | 11,328 行，一行一个篆书码位 |
| `external.meta.json` | 登记时钉住的上游仓库、分支、commit 与统计 |

`external.csv` 的列：

| 列 | 含义 |
|----|------|
| `codepoint` | Unicode 篆书区块码位（U+3D000–U+3FC3F） |
| `unicode` | 对应的**现代汉字**码位，6 位大写十六进制（与 `AGENTS.md` 的文件名约定一致） |
| `modern_char` | 对应的现代汉字 |
| `radical_no` / `radical_cp` | 《说文》540 部首编号 / 部首自身的篆书码位 |
| `ccz` `dyc` `qjz` `thx` | 该字在四个《说文》版本中的**流水号**：陈昌治本 `C-#####`、段玉裁本 `D-#####`、祁寯藻本 `K-#####`、藤花榭本 `TH-#####`（来源：Unicode `SealSources.txt`） |
| `upstream_path` | 上游仓库里的文件路径，如 `glyphs/u3D000.svg`（**为空 = 上游尚无此字形**） |
| `upstream_blob_sha1` | 上游该文件的 git blob SHA-1，用来钉住「我们指向的是哪个字节」 |

拼接上游文件 URL 的模板（`<commit>` 取 `external.meta.json` 的 `upstream_commit`）：

```
https://github.com/frankslin/kaiyuan-small-seal-font/blob/<commit>/<upstream_path>
```

## 为什么是登记表，而不是 submodule 或直接复制

- **只登记标识符与链接，不构成对上游内容的分发**，因此不受上游许可状态影响；
- 不把上游仓库（约 96 MB）带进本项目，也不影响 GitHub Pages 部署；
- 上游文件命名就是 `u<码位大写十六进制>.svg`，所以这份映射可以完全由码位推出。

## 上游许可状态（重要）

截至登记时（见 `external.meta.json` 的 `generated_at`）：

1. 上游的授权语句只覆盖「**output fonts**」（README / `AGENTS.md` 原文），
   并未明确把 `glyphs/**` 纳入；OFL 对 "Font Software" 的定义要求文件被
   **明确标记**为受本协议约束，而上游 `glyphs/` 下没有任何许可标记。
2. 上游根目录的 `OFL.txt` 正文与其声明的 OFL 1.1 **不一致**（行级相似度 0.43；
   缺官方抬头、缺第 4/5 条、缺 `Reserved Font Name` 定义段，自订为 10 条条款）。

因此本仓库**不复制其字形**，只登记指针，并把该层标为「未收录」。
上游一旦澄清授权范围，可用同一份表一次性导入（届时 `glyphs/seal/<Unicode>.svg`
按 `AGENTS.md` 命名，并逐条写 `glyphs/provenance.jsonl`）。

详见仓库根目录的 `THIRD_PARTY_NOTICES.md`。

## 重新生成

```bash
python src/build_seal_registry.py            # 用缓存
python src/build_seal_registry.py --refresh  # 重新拉上游清单与 SealSources.txt
```
