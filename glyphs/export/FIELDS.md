# Field dictionary (English)

Field dictionary version: **1** (this file's own revision).

Ledger schema version: **2** — pinned in `glyphs/glyph-ids.meta.json`
(`schema_version`), alongside `id_format` = `6-4-6` (the `unified_id` syntax
below). The two numbers are independent: this dictionary describes the
**columns** of the wide exports; the ledger schema describes the **ledger's
own fields**. Do not read the ledger schema version off this file.

All artifacts in this directory plus the sibling files `glyph-ids.csv`,
`glyph-ids-excluded.csv` and `glyph-ids.meta.json` are **deterministic build
products** (`python src/build_glyph_ids.py`; verified byte-identical in CI by
`--check`). Cite glyphs by `unified_id`; never hard-code file paths.

## Files

| file | contents |
|---|---|
| `../glyph-ids.csv` | The ledger. One row per glyph. Append-only: published IDs are frozen forever; deleted glyphs become `retired` and their serials are never reused. |
| `../glyph-ids-excluded.csv` | Index rows that intentionally carry **no** `unified_id` (no modern-char codepoint and no PUA slot). Currently 2 oracle rows (JGW `0380`/`0916`). |
| `../glyph-ids.meta.json` | `schema_version` + `id_format` + row counts + artifact list. |
| `../glyph-ids-subcodes.csv` | Extension-slot registry (layer, subcode, meaning, owner, date) — **human-maintained**, append-only, never redefined. Empty = only the default partition `00` exists. It lives beside the ledger, not in this directory: it is registry, not a build product. |
| `../glyph-ids-release.csv` | Release anchor — one row per published release (release, released_at, stable_sha256, ledger_sha256, id_format, note). **Human-maintained**, append-only; `release` is also the git tag name and must be unique, `released_at` is `YYYY-MM-DD` and must not go backwards. `stable_sha256` is the fingerprint of the released `unified_id` set (durable: it does not change as the library grows); `ledger_sha256` is the whole-file hash at that release (point-in-time, non-empty). CI re-checks `stable_sha256` against the current ledger — a changed published ID turns the build red — and `ledger_sha256` against the ledger blob under that release's git tag. |
| `<layer>.csv` | Wide join `ledger ⋈ index ⋈ provenance`, one file per layer — downstream code does not need to join three tables. |
| `export/FIELDS.md` | This dictionary. |

## `unified_id` syntax

`<root>-<script>-<seq>`, e.g. `004E00-0E00-000001` = 「一」(U+4E00), small-seal
script, instance 1. Regex: `^[0-9A-F]{6}-[0-9A-Z]{4}-[0-9]{6}$`.

- **root** — the modern character's Unicode codepoint, 6 uppercase hex digits.
  For provisional entries (`identity_confidence="pua-slot"`) the root is a
  **Private Use Area** codepoint carried over from `modern_char_slot`; these
  rows are machine-checked to never collide with real Han codepoints.
- **script** — **4-digit** layer key = *base digit* (1) + *layer key* (1) +
  *extension slot* (2), frozen, append-only. Base36 alphabet `0-9A-Z`;
  **no `I`/`L`/`O`/`U` normalisation** (the frozen layer keys include `0I` and
  `0L`; Crockford folding belongs to the `GID` space only):

  | code | layer | directory | era anchor |
  |---|---|---|---|
  | 0A00 | Oracle bone script | oracle | late Shang |
  | 0B00 | Bronze script | bronze | Shang–Zhou |
  | 0C00 | Chu script | chu | Warring States (Chu) |
  | 0D00 | Qin bamboo/wooden slips | qinwenzi | late Warring States–Qin |
  | 0E00 | Small seal script | seal | Qin (incl. Xiaoxuetang fills) |
  | 0F00 | Clerical script | clerical | late Qin–Han |
  | 0G00 | Cursive script | caoshu | Han |
  | 0H00 | Regular script | kaishu | late Han– |
  | 0I00 | Running script | xingshu | late Han–Wei/Jin– |
  | 0J00 | Transmitted ancient script | chuanchao | pre-Qin forms, Song–modern copies (appendix slot) |
  | 0K00 | Song/Ming, Simplified | songti | Song–present (mainland standard) |
  | 0L00 | Song/Ming, Traditional | songti-tc | Song–present (TW/HK standard) |
  | 0M00 | Sans, Hong Kong | heiti-hk | 20th century |

  The **base digit** is 1 char wide and fixed (segments `0`–`Z` × 36 layer keys
  = 1,296 layer slots; 13 used). The **extension slot** (last 2 chars) is an
  **opaque per-layer partition handle**: `00` is each layer's default
  partition. Its meaning is defined in `../glyph-ids-subcodes.csv`
  (human-maintained, append-only, never redefined). The extension slot does
  **not** enter the serial bucket.
- **seq** — 6-digit instance number within a (root, layer-key) bucket. Initial
  assignment used a per-layer scholarly order (small seal = Shuowen sequence;
  bronze/clerical = chronological; Chu = excavation-date order); **after the
  first mint, IDs are frozen**: new glyphs take max+1, retired serials are never
  reused.

## Ledger columns (`glyph-ids.csv`)

| column | description |
|---|---|
| `unified_id` | Persistent cross-layer glyph identifier (see syntax above). |
| `status` | `active` = current layer content; `retired` = removed from the layers, ID kept for citation, serial never reused. |
| `release` | Release channel, orthogonal to lifecycle: `draft` = minted, not yet published; `stable` = included in a published release. |
| `layer` | Layer directory name (`oracle` … `heiti-hk`). |
| `modern_char` | The modern Chinese character (empty for provisional PUA-root rows). |
| `unicode` | The root codepoint as a 6-digit hex string (empty for provisional rows). |
| `file` | Current file name within the layer directory. Updated when layers are re-imported — **resolve paths through this column, never hard-code them**. |
| `source_id` | The upstream source's own key for this glyph (zdic slot `27_4E00`, registry codepoint, font glyph name, …). Current source, not historical. |
| `identity_confidence` | Empty = identity given by the site; `pua-slot` = provisional PUA-root identity (do **not** cite the PUA codepoint as a Han character). |
| `modern_char_slot` | `<font-no>_<codepoint>` slot — the only identity clue for provisional rows. |

## Wide-export columns (`export/<layer>.csv`)

Superset of the ledger columns plus:

| column | description |
|---|---|
| `layer_zh` | Layer's Chinese name (e.g. 小篆). |
| `script_code` | The 4-digit script code (0A00…0M00); last 2 chars are the extension slot (see syntax above). |
| `sha256` | SHA-256 of the SVG file in the layer directory. |
| `license` | License of this glyph's record (CC0-1.0 / CC-BY-4.0 / OFL-1.1). Check `THIRD_PARTY_NOTICES.md` for attribution obligations. |
| `source_dataset` | Upstream batch (漢典 vector, 小學堂 bitmap trace, OFL font outline, JGW parametric, …). |
| `source_url` | Upstream retrieval URL (glyph images themselves are not bundled with the site; fetch from the repo/CDN by `layer` + `file`). |
| `period` | Era label (bronze/clerical/oracle layers; empty elsewhere). |
| `source_book` | Source corpus / Shuowen section label (ancient-script layers; empty for font layers). |

## Identity migration

When a provisional PUA-root glyph's real Han identity is established, the old
row is retired and a new row is minted under the CJK root. Old→new redirects
are derivable by `(layer, source_id)` lineage:

```
python src/build_glyph_ids.py --redirects
```

## Relation to Unicode

This scheme is structurally similar to an Ideographic Variation Sequence
(base codepoint + variant qualifier) but is **not** an IVD-registered
sequence — never map these IDs to `U+FE00..U+E01xx` variation selectors for
rendering. The library does not claim TIP (Plane 3 beyond the registered Seal
block) or any other unallocated codepoints: oracle/bronze forms have no UCS
script block yet; when official encodings land, migration follows the frozen
ledger policy above.
