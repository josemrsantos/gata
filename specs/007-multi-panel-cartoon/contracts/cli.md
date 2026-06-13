# CLI Contract: Multi-Panel Cartoon Format

**Feature**: specs/007-multi-panel-cartoon/
**Phase**: 1 — Design
**Date**: 2026-06-11

## New Flags

### `--panels <int>`

Controls the number of panels in the output image.

| Attribute | Value |
|-----------|-------|
| Type | integer |
| Valid range | 1–4 (inclusive) |
| Default | 1 (single-panel, existing behaviour) |
| Source priority | CLI > community config > global default |
| Out-of-range behaviour | Exit code 1 with descriptive error before any API call |

**Examples**:
```bash
python pipeline.py --community uk-politics --panels 3
python pipeline.py --community uk-politics --panels 1   # explicit single-panel
```

---

### `--layout <str>`

Controls the panel arrangement direction.

| Attribute | Value |
|-----------|-------|
| Type | string |
| Valid values | `horizontal`, `vertical` |
| Default | `horizontal` (when `--panels` > 1; ignored when panels == 1) |
| Source priority | CLI > community config > global default |
| Invalid value behaviour | Exit code 1 with descriptive error before any API call |

**Examples**:
```bash
python pipeline.py --community uk-politics --panels 3 --layout horizontal
python pipeline.py --community uk-politics --panels 2 --layout vertical
```

---

## Precedence Matrix

| `--panels` provided | Community has `panels` | Effective panels |
|---------------------|------------------------|-----------------|
| Yes | Yes | CLI value |
| Yes | No | CLI value |
| No | Yes | Community value |
| No | No | 1 (default) |

Same matrix applies to `--layout` / community `layout`.

---

## Validation Rules (FR-010)

All validation runs in `pipeline.py` immediately after `args = parser.parse_args()`, before any API call or file operation:

1. If `--panels` is provided and not in [1, 4]: exit(1) with message `"--panels must be between 1 and 4"`
2. If `--layout` is provided and not in `["horizontal", "vertical"]`: exit(1) with message `"--layout must be 'horizontal' or 'vertical'"`
3. If `--panels 1` with any `--layout`: layout is silently ignored; single-panel path runs

---

## Backwards Compatibility

`--panels` and `--layout` are both optional with safe defaults. Omitting both is identical to `--panels 1 --layout horizontal`, which produces the current single-panel behaviour. All existing CLI invocations continue to work without modification (US4, SC-002).
