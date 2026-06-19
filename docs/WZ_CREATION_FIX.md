# Fix: wybór typu dokumentu WZ w formularzu

**Data:** 2026-06-19  
**Plik:** `frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx`

## Problem

Dropdown PZ/WZ/KK nie aktualizował `docType` — brak settera w `useState` i brak `onChange` na `<select>`. Payload `create` zawsze miał `doc_type: 'PZ'`.

## Zmiana

W komponencie `DocForm`:

```javascript
const [docType, setDocType] = useState(initial?.doc_type ?? 'PZ');
```

```javascript
<select
  className="input"
  value={docType}
  disabled={isEdit}
  onChange={(e) => setDocType(e.target.value)}
>
```

Select pozostaje `disabled={isEdit}` — tylko edycja istniejącego draftu blokuje zmianę typu.

## Build

```bash
cd frontend-react && npm run build
# ✓ built in 1.28s
# dist/assets/index-DRop1uew.js
```

## Weryfikacja

1. Nowy dokument → wybierz WZ → UI bez kolumn PZ, pole „Powód wydania”.
2. Zapisz → dokument w liście ma typ WZ.
