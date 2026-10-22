# Invoice presentation assets

## stained_glass.png

Canonical brand slot for the elegant sales invoice template:

- `app/assets/invoice/stained_glass.png` (preferred), or
- `app/assets/invoice/stained_glass.svg` / `.jpg`

When the file is present, the template embeds it in a circular viewport
(`data-stained-glass="provided"`, CSS `object-fit: cover`).

When absent, the slot stays empty with
`data-stained-glass="STAINED_GLASS_ASSET_REQUIRED"`.
