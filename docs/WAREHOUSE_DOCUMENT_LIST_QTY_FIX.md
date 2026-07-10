# Fix: kolumna ILOŚĆ w liście dokumentów magazynowych

**Data:** 2026-06-19  
**Plik:** `frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx`

## Zmiana

W `DocList` dodano kolumnę **ILOŚĆ** (przed **Pozycji**):

- Suma `items[].quantity` po stronie UI.
- Format wpływu na stan:
  - **PZ:** `+N` (wartość bezwzględna)
  - **WZ:** `-N` (wartość bezwzględna)
  - **KK:** znak algebraiczny sumy (`+1`, `-1`, `0`)
- Liczba całkowita (`Math.trunc`), wyrównanie do prawej (`styles.right`).

Helpery: `sumDocItemQuantities()`, `fmtDocListQtyImpact()`.

## Build

```bash
cd frontend-react && npm run build
# ✓ built
```

## Ryzyka

- Lista API może nie zwracać `items` dla wszystkich dokumentów — wtedy `—` zamiast ilości.
- Draft bez pozycji: `—` / `0` pozycji.
- KK ze mieszanymi znakami pozycji: wyświetlana jest **suma algebraiczna**, nie osobne zdjęcia/przyjęcia.
