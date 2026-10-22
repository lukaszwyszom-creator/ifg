# GWO-IFG-SALES-INVOICE-MASTER-COORDINATE-SHELL-0015L

**Data:** 2026-10-01  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015` @ `b6e82da`

## CEL

Odrzucenie geometrii 0015K (CONTENT_WIDTH=147mm).  
Szkielet wyłącznie w układzie współrzędnych MASTER 1024×1536 → A4 (offset 6mm, scale 297/1536).

## TRANSFORM

```
MASTER_SCALE = 297/1536 = 0.193359375 mm/px
MASTER_OFFSET_X = 6 mm
WIDTH_ON_A4 = 198 mm
x_mm = 6 + x_px * MASTER_SCALE
y_mm = y_px * MASTER_SCALE
```

## ZMIERZONE GATY (programowo z MASTER)

| Gate | Value |
|------|-------|
| ORNAMENT_X_MASTER_PX | 83 |
| ORNAMENT_X_A4_MM | 22.048828125 |
| CONTENT_LEFT_MASTER_PX | 120 |
| CONTENT_RIGHT_MASTER_PX | 977 |
| CONTENT_WIDTH_MASTER_PX | 857 |
| CONTENT_WIDTH_A4_MM | 165.708984375 |
| STAINED_GLASS_BBOX_MASTER_PX | [-33, 78, 199, 310] |
| INVOICE_TITLE_BBOX_MASTER_PX | [120, 383, 425, 415] |
| META_BBOX_MASTER_PX | [120, 480, 977, 560] |
| PARTIES_BBOX_MASTER_PX | [122, 560, 897, 760] |
| TABLE_BBOX_MASTER_PX | [120, 780, 977, 1070] |
| VAT_SUMMARY_BBOX_MASTER_PX | [136, 1140, 607, 1250] |
| PAYABLE_BBOX_MASTER_PX | [495, 1138, 977, 1260] |
| KSEF_BBOX_MASTER_PX | [120, 1389, 699, 1447] |
| QR_BBOX_MASTER_PX | [817, 1385, 977, 1525] |
| TABLE_WIDTH_MASTER_PX | 857 |
| TABLE_WIDTH_A4_MM | 165.708984375 |

0015K `CONTENT_WIDTH=147mm` — **ODRZUCONE** (MASTER content ≈ 165.71mm).

## PLIKI

- `app/assets/invoice/layout_shell/master_geometry.json`
- `app/assets/invoice/layout_shell/stained_glass_module.json` (MASTER px + editable crop/scale/rotation)
- `app/assets/invoice/layout_shell/layout_shell_master.html`
- `scripts/measure_master_geometry_0015l.py`
- `scripts/render_master_coordinate_shell_0015l.py`

## RENDER / VERIFY

| Artefakt | Size / path |
|----------|-------------|
| master.png | 1024×1536 `/tmp/ifg-0015l/master.png` |
| render.png | 1024×1536 `/tmp/ifg-0015l/render.png` |
| overlay-50.png | 1024×1536 `/tmp/ifg-0015l/overlay-50.png` |
| difference.png | 1024×1536 `/tmp/ifg-0015l/difference.png` |
| layout.pdf | A4 `/tmp/ifg-0015l/layout.pdf` (PDF_PAGES=1) |
| Desktop shell | `~/Desktop/IFG-MASTER-COORDINATE-SHELL.jpg` |
| Desktop overlay | `~/Desktop/IFG-MASTER-COORDINATE-OVERLAY.jpg` |

DEBUG overlay = MASTER @ 50% — **nie** production background.

## STOP

IFG_DATA_BOUND=NO · commit/merge/deploy=NO · witraż nie finalizowany

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## 🩷 STATUS KOŃCOWY

✅ Co działa  
- MASTER 1024×1536 jedyny układ współrzędnych  
- Zmierzona szerokość content/table ≈ 165.71mm (nie 147)  
- Witraż jako osobny moduł MASTER-px  
- Overlay + difference 1:1 z MASTER  
- PDF A4 1 page; fixture data only  

⚠️ Znane problemy  
- Shell PNG to geometry skeleton (typografia uproszczona vs MASTER) — wymaga visual review overlay  
- QR = reserved bbox (MASTER bez QR)  
- Niektóre H-rule detections rzadkie — diamenty/osie z pomiaru  

❌ Co nie działa  
- Brak bindingu (celowo)  

### A. Root cause
0015K projektował w mm; 0015L mapuje MASTER px → mm.

### B. Zmienione pliki
`layout_shell/master_geometry.json`, `stained_glass_module.json`, `layout_shell_master.html`, `README.md`, skrypty 0015L, raport

### C. Deploy — nie  
### D. Testy — size gates 1024×1536; PDF 1 page; scale/offset constants  
### E. Następny krok — review overlay Desktop vs MASTER; korektá bbox jeśli operator wskaże

## Decyzje dla ChatGPT

1. Czy zmierzone CONTENT_WIDTH≈165.71mm / ORNAMENT_X=83px akceptujemy?  
2. Czy QR bbox [817,1385,977,1525] (placeholder) zostaje?  
3. Czy po akceptacji idziemy do bind IFG na tym układzie?

---

STATUS=DONE  
VERDICT=MASTER_COORDINATE_VISUAL_REVIEW_REQUIRED  
MASTER_SIZE=1024x1536  
MASTER_SCALE=0.193359375  
MASTER_OFFSET_X_MM=6  
ORNAMENT_X_MASTER_PX=83  
ORNAMENT_X_A4_MM=22.048828125  
CONTENT_WIDTH_MASTER_PX=857  
CONTENT_WIDTH_A4_MM=165.708984375  
STAINED_GLASS_MODULE_EDITABLE=YES  
TABLE_WIDTH_MASTER_PX=857  
TABLE_WIDTH_A4_MM=165.708984375  
PDF_PAGES=1  
SHELL_PREVIEW=/Users/lukasz/Desktop/IFG-MASTER-COORDINATE-SHELL.jpg  
OVERLAY_PREVIEW=/Users/lukasz/Desktop/IFG-MASTER-COORDINATE-OVERLAY.jpg  
IFG_DATA_BOUND=NO  
COMMIT_PERFORMED=NO  
MERGE_PERFORMED=NO  
DEPLOY_PERFORMED=NO  
