# Invoice presentation assets

## stained_glass.* — STAINED_GLASS_ASSET_REQUIRED

Canonical path expected by the elegant sales invoice template:

- `app/assets/invoice/stained_glass.png` (preferred), or
- `app/assets/invoice/stained_glass.svg` / `.jpg`

Until the operator-approved Wydawnictwo Ikona stained-glass artwork is placed here,
the template keeps an empty circular ornament slot (`data-stained-glass="STAINED_GLASS_ASSET_REQUIRED"`).

Do not treat CSS-only placeholders as final brand assets.
Gate: **ASSET_BLOCKED** until the file is committed.
