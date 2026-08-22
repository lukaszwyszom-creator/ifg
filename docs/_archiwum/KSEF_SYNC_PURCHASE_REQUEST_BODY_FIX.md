# KSeF — naprawa body POST `/ksef/sync/purchases`

Data: 2026-06-10

---

## Przyczyna 422

Endpoint `POST /api/v1/ksef/sync/purchases` wymagał **obowiązkowego** body typu `KSeFPurchaseSyncRequest`:

```python
def sync_ksef_purchases_now(body: KSeFPurchaseSyncRequest, ...)
```

Wywołanie **bez body** (curl, stary klient, pusty POST) → FastAPI **422 Field required body**.

Dodatkowo frontend wysyłał **`force`** zamiast **`force_full`** (pole ignorowane przez schemat po `extra="ignore"`).

---

## Zmiana

### Backend — `app/api/routers/ksef_session.py`

- `body: KSeFPurchaseSyncRequest = Body(default_factory=KSeFPurchaseSyncRequest)` — domyślne body gdy brak JSON.
- `extra="ignore"` + mapowanie legacy `"force"` → `force_full`.

### Frontend — `frontend-react/src/api/ksef.js`

```javascript
client.post('/ksef/sync/purchases', {
  force_full: forceFull,
  incremental: false,
  ...(nip ? { nip } : {}),
})
```

---

## Testy

```bash
.venv/bin/python -m pytest tests/unit/test_ksef_sync_api.py -q
```

- `test_post_ksef_sync_purchases_without_body_uses_defaults` — brak 422
- `test_post_ksef_sync_purchases_accepts_legacy_force_field`
- `test_post_ksef_sync_purchases_accepts_force_full_body`

---

## Deploy

| Warstwa | Wymagany rebuild |
|---------|------------------|
| Backend | **Tak** |
| Frontend | **Tak** (poprawione `force_full` w API call) |

Logika sync KSeF bez zmian — tylko start requestu z UI/API.
