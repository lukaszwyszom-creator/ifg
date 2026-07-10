# Bug: nie można utworzyć WZ — formularz zawsze jak PZ

**Data:** 2026-06-19  
**Zakres:** `frontend-react/src/pages/warehouse/*`, `warehouseDocumentsApi.create`

---

## Objaw

Magazyn → Nowy dokument: dropdown pokazuje PZ/WZ/KK, ale po wyborze WZ UI nadal wygląda jak PZ (kolumny zakupu/VAT/normatywna cena), a zapis tworzy dokument PZ.

---

## Diagnoza

### 1. Czy wybór WZ zmienia state `doc_type`?

**Nie** — bug frontendowy.

```javascript
// DocumentsTab.jsx — DocForm (przed poprawką)
const [docType] = useState(initial?.doc_type ?? 'PZ');
// ...
<select className="input" value={docType} disabled={isEdit}>
```

- Brak settera w destrukturyzacji `useState`.
- Brak `onChange` na `<select>`.
- `docType` zawsze `'PZ'` dla nowego dokumentu → cały JSX warunkowy (`docType === 'PZ'`, pola WZ/KK) nie reaguje na wybór użytkownika.

### 2. Czy payload do API zawiera `doc_type: 'WZ'`?

**Nie** (przed poprawką) — zawsze `'PZ'`:

```javascript
const body = {
  doc_type: docType,  // zawsze 'PZ' dla nowego formularza
  ...
};
warehouseDocumentsApi.create(body);  // POST /warehouse-documents
```

API (`warehouseDocuments.js`) przekazuje body bez modyfikacji — problem nie leży w warstwie API client.

### 3. Czy backend obsługuje tworzenie WZ?

**Tak.**

- `WarehouseDocumentService.create_document()` — akceptuje `doc_type='WZ'`.
- `_validate_doc_header()` — wymaga `issue_reason` gdy brak `source_invoice_id`.
- `_validate_items_for_type()` — WZ: ilość dodatnia, całkowita.
- `post_document()` → `_post_wz()` — księgowanie FIFO.

Backend nie wymagał zmian.

---

## Poprawka (minimalna)

**Plik:** `frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx`

1. `const [docType, setDocType] = useState(...)`
2. `onChange={(e) => setDocType(e.target.value)}` na select typu dokumentu

Po poprawce:
- UI przełącza kolumny pozycji (PZ vs WZ/KK).
- Pokazuje pole „Powód wydania” dla WZ bez faktury.
- Payload `create` zawiera wybrany `doc_type`.

---

## Weryfikacja manualna

1. Magazyn → Dokumenty → Nowy dokument.
2. Wybierz **WZ — Wydanie** → tabela bez kolumn PZ (zakup/VAT/normatywna); widoczne „Powód wydania”.
3. Wypełnij towar, ilość dodatnią, powód wydania → Zapisz draft.
4. Podgląd dokumentu: typ **WZ**, status draft.

---

## Pliki

| Plik | Rola |
|------|------|
| `frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx` | formularz `DocForm` — **naprawiony** |
| `frontend-react/src/api/warehouseDocuments.js` | `POST /warehouse-documents` — bez zmian |
| `app/services/warehouse_document_service.py` | backend WZ — OK (poza zakresem edycji) |
