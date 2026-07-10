# Fix: wybór KK w formularzu nowego dokumentu

**Data:** 2026-06-19  
**Plik:** `frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx`

## Diagnoza

- `setDocType` i `onChange` na `<select>` były już obecne (poprawka WZ).
- Układ tabeli dla KK był zagnieżdżony w gałęzi `else` współdzielonej z WZ (`docType === 'KK' &&` wewnątrz bloku non-PZ) — podatny na mylenie layoutu.
- `isEdit = !!initial` mogło teoretycznie zablokować select przy truthy `initial` bez `id`.

## Zmiany

1. `isEdit = Boolean(initial?.id)` — select aktywny tylko przy edycji istniejącego dokumentu.
2. `handleDocTypeChange(nextType)` — jawna aktualizacja `docType` + czyszczenie błędu.
3. Nagłówki i komórki pozycji: trzy osobne gałęzie `PZ` | `KK` | `WZ` (KK: Ilość + Cena zakupu + Cena suger.).
4. Payload `create` bez zmian — `doc_type: docType` (wartość `'KK'` po wyborze).

## Build

```bash
cd frontend-react && npm run build
# ✓ built
```

## Weryfikacja

1. Nowy dokument → wybierz KK → pole „Powód korekty *” widoczne.
2. Tabela: Ilość, Cena zakupu, Cena suger. (bez kolumn PZ).
3. Zapis → dokument typu KK w API.
