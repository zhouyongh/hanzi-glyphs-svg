# Field dictionary (English)

Schema version: **1** (pinned in `glyphs/glyph-ids.meta.json`).

All artifacts in this directory plus the sibling files `glyph-ids.csv`,
`glyph-ids-excluded.csv` and `glyph-ids.meta.json` are **deterministic build
products** (`python src/build_glyph_ids.py`; verified byte-identical in CI by
`--check`). Cite glyphs by `unified_id`; never hard-code file paths.

## Files

| file | contents |
|---|---|
| `../glyph-ids.csv` | The ledger. One row per glyph. Append-only: published IDs are frozen forever; deleted glyphs become `retired` and their serials are never reused. |
| `../glyph-ids-excluded.csv` | Index rows that intentionally carry **no** `unified_id` (no modern-char codepoint and no PUA slot). Currently 2 oracle rows (JGW `0380`/`0916`). |
| `../glyph-ids.meta.json` | `schema_version` + row counts + artifact list. |
| `export/<layer>.csv` | Wide join `ledger ⋈ index ⋈ provenance`, one file per layer — downstream code does not need to join three tables. |
| `export/FIELDS.md` | This dictionary. |

## `unified_id` syntax

`<root>-<script>-<seq>`, e.g. `004E00-0E-000001` = 「一」(U+4E00), small-seal
script, instance 1.

- **root** — the modern character's Unicode codepoint, 6 uppercase hex digits.
  For provisional entries (`identity_confidence="pua-slot"`) the root is a
  **Private Use Area** codepoint carried over from `modern_char_slot`; these
  rows are machine-checked to never collide with real Han codepoints.
- **script** — 2-digit layer key, frozen, append-only:

  | code | layer | directory | era anchor |
  |---|---|---|---|
  | 0A | Oracle bone script | oracle | late Shang |
  | 0B | Bronze script | bronze | Shang–Zhou |
  | 0C | Chu script | chu | Warring States (Chu) |
  | 0D | Qin bamboo/wooden slips | qinwenzi | late Warring States–Qin |
  | 0E | Small seal script | seal | Qin (incl. Xiaoxuetang fills) |
  | 0F | Clerical script | clerical | late Qin–Han |
  | 0G | Cursive script | caoshu | Han |
  | 0H | Regular script | kaishu | late Han– |
  | 0I | Running script | xingshu | late Han–Wei/Jin– |
  | 0J | Transmitted ancient script | chuanchao | pre-Qin forms, Song–modern copies (appendix slot) |
  | 0K | Song/Ming, Simplified | songti | Song–present (mainland standard) |
  | 0L | Song/Ming, Traditional | songti-tc | Song–present (TW/HK standard) |
  | 0M | Sans, Hong Kong | heiti-hk | 20th century |

- **seq** — 6-digit instance number within a (root, script) bucket. Initial
  assignment used a per-layer scholarly order (small seal = Shuowen sequence;
  bronze/clerical = chronological; Chu = excavation-date order); **after the
  v1 mint, IDs are frozen**: new glyphs take max+1, retired serials are never
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
| `script_code` | The 2-digit script code (0A…0M). |
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
