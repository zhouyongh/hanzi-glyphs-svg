# ID-FORMAT — 可读编号 `unified_id`（6-4-6）

> **状态**：Current，v1.0.0 已发布。
> **范围**：本文件是 `glyphs/glyph-ids.csv` 的 `unified_id` 规范。
> 下一代 `GID`（`hg:` 不透明键）是独立规划，不在本分支、不在本发布范围。

---

## 1. 语法

```text
<root 6 hex>-<script 4 base36>-<seq 6 decimal>
```

正则：

```text
^[0-9A-F]{6}-[0-9A-Z]{4}-[0-9]{6}$
```

示例：`004E00-0E00-000001` = 「一」的小篆第 1 件。

字段：

| 字段 | 宽度 | 含义 |
|---|---:|---|
| `root` | 6 | 现代字 Unicode 码位，大写十六进制 |
| `script` | 4 | 书体码：base + layer + sub（见 §2） |
| `seq` | 6 | 同一 `(root, layer)` 桶内的十进制序号 |

**旧 6-2-6 形不接受**：v1 的 6-2-6 从未公开，无兼容对象。旧形输入即 404，不回落、不误判。

---

## 2. 书体码

```text
script4 = base(1) + layer(1) + sub(2)
```

### 2.1 base

- 1 位 base36，当前全部为 `0`。
- 段位用尽后顺延到 `1`…`Z`；`base` 固定 1 位，不写成 `10`、`11`。
- 段 0–Z × 层键 36 个 = 1,296 个层位。

### 2.2 layer

| 书体码 | 层 | 目录 |
|---|---|---|
| `0A00` | 甲骨文 | `oracle` |
| `0B00` | 金文 | `bronze` |
| `0C00` | 楚文字 | `chu` |
| `0D00` | 秦系簡牘 | `qinwenzi` |
| `0E00` | 小篆 | `seal` |
| `0F00` | 隶书 | `clerical` |
| `0G00` | 草书 | `caoshu` |
| `0H00` | 楷书 | `kaishu` |
| `0I00` | 行书 | `xingshu` |
| `0J00` | 傳抄古文 | `chuanchao` |
| `0K00` | 宋体·简 | `songti` |
| `0L00` | 宋体·繁 | `songti-tc` |
| `0M00` | 黑体·港 | `heiti-hk` |

- 层键按序冻结、只增不改；新层取下一个未用字母，不预留跳号。
- 字母是层键，不是书体学断言。

### 2.3 sub（扩展位）

- 2 位，`00` = 默认分区；当前 183,749 件全部为 `00`。
- 扩展位是**层内不透明分区句柄**，不编码来源、版本、异体、字体版本、出处。
- 语义由 `glyphs/glyph-ids-subcodes.csv`（`layer, subcode, meaning, owner, date`）人工登记；
  代码只校验、不生成、不覆盖。空表 = 只有 `00`。
- 某层出现第二个分区时，取该层最小未用后缀（`01` 起），登记后冻结；不得为一个分区预留多个号。
- **扩展位不进桶**：桶 = `(root, layer)`，不是 `(root, script4)`。

### 2.4 字母表

- base36 `0-9A-Z`，**不做 `I`/`L`/`O`/`U` 归一化**。
- 存量层键含 `0I`（行书）与 `0L`（宋体·繁），必须原样表示。

---

## 3. 序号与冻结

- 同一 `(root, layer)` 桶内 `seq` 唯一，6 位十进制。
- 新增行取桶内**最大已用号 + 1**，包含退役号；序号永不复用。
- 初始序号用 `src/era_sequence.py` 的学术序（小篆说文序、金文/隶书时代序、楚文字文献年代序、甲骨/秦系/傳抄保持条目号）。
- `status=active` 与 `status=retired` 并存；退役行保留 ID，不删除、不复用序号。
- 同一 `(root, layer)` 下不同 `sub` 的 `seq` 仍共享同一桶，不因分区重新从 1 开始。

---

## 4. 根码

- 有 `unicode`：`root == unicode`，6 位大写十六进制。
- `unicode` 为空且 `identity_confidence="pua-slot"`：`root` 取 `modern_char_slot` 里的私用区码位。
- 私用区根码只表示临时身份，**不是汉字码位**；不得把它当正式 Unicode 引用。
- 槽位不是码位的 2 件（甲骨 JGW `JGW_0380`/`JGW_0916`）不入账本，登记在
  `glyphs/glyph-ids-excluded.csv`。

---

## 5. 账本与产物

`glyphs/glyph-ids.csv` 列：

```text
unified_id, status, release, layer, modern_char, unicode,
file, source_id, identity_confidence, modern_char_slot
```

- `active` 行与各层 `index.csv` 一一对应。
- `release` 与 `status` 正交：`draft` = 铸发未对外；`stable` = 已随发布对外。
- 账本不含 sha256；文件校验属 `index.csv` / `provenance`。

随账本确定性生成：

| 文件 | 内容 |
|---|---|
| `glyph-ids-excluded.csv` | 无根码排除清单（2 件 oracle JGW） |
| `glyph-ids.meta.json` | `schema_version` / `id_format` / 计数 / 产物列表 |
| `export/<layer>.csv` × 13 | 账本 ⋈ index ⋈ provenance 宽表 |
| `export/FIELDS.md` | 英文字段词典（手维护） |

人工维护、代码只校验：

| 文件 | 内容 |
|---|---|
| `glyph-ids-subcodes.csv` | 扩展位登记表 |
| `glyph-ids-release.csv` | 发布锚点 |

`glyphs/glyph-ids.csv` 由 `python src/build_glyph_ids.py` 生成/校验；
`--check` 逐字节复算，`--selftest` 测冻结/退役/扩展位，`--char` 查询，`--redirects` 导出身份迁移。

---

## 6. 发布锚点

`glyphs/glyph-ids-release.csv` 一行一次发布：

| 列 | 含义 |
|---|---|
| `release` | 发布号，同时是 git tag 名，如 `v1.0.0`；不得重复 |
| `released_at` | `YYYY-MM-DD`；不得倒序 |
| `stable_sha256` | 已发布号集合的指纹（stable `unified_id` 排序后逐行 sha256） |
| `ledger_sha256` | 发布那一刻整份 `glyphs/glyph-ids.csv` 的 sha256；不得为空 |
| `id_format` | `6-4-6` |
| `note` | 一句话说明 |

机检：

- 最新一行的 `stable_sha256` 必须等于当前账本的 stable 集合指纹；改任何已发布号即红。
- 每一行 `ledger_sha256` 与 **该 release 的 git tag 下账本**逐字节对账。
- `stable_sha256` 对历史行用 tag 下账本的 stable 集合复算。
- 逐行校验 `release` 唯一、日期格式/顺序、两个 hash 非空且 64 位 hex、`id_format` 一致。
- 锚点文件存在时一律对账；不存在时账本不得有 stable 行。

发布流程：

1. 新件一律 `release=draft`。
2. `python src/build_glyph_ids.py --release stable --dry-run` 预览并打印新锚点行。
3. `python src/build_glyph_ids.py --release stable` 翻转发布态。
4. 把打印的锚点行追加到 `glyphs/glyph-ids-release.csv`（人工维护）。
5. 提交 + 打同名 annotated tag；tag 推送后 `--check` 才对账 `ledger_sha256`。

`--release draft` 在锚点存在时 fail-closed 拒绝；确需撤销发布必须显式 `--force` 并同步更新锚点。

---

## 7. 机器可检不变量

1. 每行 `unified_id` 匹配 §1 正则；全局唯一。
2. `root`：有 `unicode` 时相等；无 `unicode` 时落在私用区且标 `pua-slot`。
3. `script4[0]` 是已知段位，`script4[1]` 是已知层键，`script4[2:4]` 非 `00` 时必须在 subcodes 登记。
4. 同一 `(root, layer)` 内 `seq` 唯一；退役号不复用；`seq` 不因 `sub` 重排。
5. `glyph-ids-subcodes.csv` 无重复 `(layer, subcode)`、`meaning` 非空、`00` 不得重定义。
6. `export/<layer>.csv` 的 `unified_id` / `script_code` 与账本逐行一致。
7. `viewer` 深链正则只接受 6-4-6。
8. `glyph-ids-release.csv` 逐行通过 §6 检查。
9. `build_glyph_ids.py --check` 全部产物逐字节复算；`--selftest` 通过。

---

## 8. 文件与命令

```text
glyphs/glyph-ids.csv              账本（183,749 行，v1.0.0）
glyphs/glyph-ids.meta.json        元数据
glyphs/glyph-ids-excluded.csv     排除清单（2 件）
glyphs/glyph-ids-subcodes.csv     扩展位登记（当前仅表头）
glyphs/glyph-ids-release.csv      发布锚点（v1.0.0）
glyphs/export/<layer>.csv         宽表导出 × 13
glyphs/export/FIELDS.md           字段词典
```

```bash
python src/build_glyph_ids.py --check
python src/build_glyph_ids.py --selftest
python src/build_glyph_ids.py --char 一
python src/build_glyph_ids.py --release stable --dry-run
```

旧 6-2-6 形、下一代 `GID` 工具链、迁移评审稿均不在本发布分支；不要从旧文档抄路径。
