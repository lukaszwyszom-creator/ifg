# Deploy status: sale `number_local` fix

**Data:** 2026-05-22  
**Branch docelowy:** `production`  
**Deploy DS723+:** **nie wykonano** (zgodnie z poleceniem)

## Weryfikacja lokalna

Fix z `docs/SALE_INVOICE_NUMBER_LOCAL_FIX.md` **był obecny w working tree**, ale **nie był w `origin/production`**.

| Plik | Stan przed commitem | Kluczowe elementy fixa |
|------|---------------------|-------------------------|
| `app/services/invoice_service.py` | zmodyfikowany (niecommit.) | `_allocate_number_local` przy create, defensywa po create/update, retry kolizji |
| `app/services/transmission_service.py` | zmodyfikowany (niecommit.) | walidacja przed enqueue, `_friendly_submit_error` |
| `app/domain/models/invoice.py` | zmodyfikowany (niecommit.) | komunikat o braku numeru lokalnego |
| `tests/unit/test_invoice_service.py` | zmodyfikowany (niecommit.) | purchase bez numeru, mocki numeracji |
| `tests/unit/test_invoice_numbering_regression.py` | **nowy, nieśledzony** | regresja sale/purchase/backfill |
| `tests/unit/test_transmission_service.py` | zmodyfikowany (niecommit.) | submit bez numeru |

**HEAD `production` przed fixem (`db9fae4`):** `create_invoice` ustawiał `number_local=None` dla sale — brak alokacji przy tworzeniu. To tłumaczy FV produkcyjną bez numeru.

**Testy przed commitem:** 80 passed (invoice + numbering regression + repository sequence + transmission).

## Git

| Pytanie | Odpowiedź |
|---------|-----------|
| Inny branch? | **Nie** — fix był na lokalnym `production`, niecommitowany |
| `git log --grep number_local` przed commitem | pusty |
| Commit | `32e5887` — `fix(invoice): ensure sale invoices receive number_local before KSeF.` |
| Push | `origin/production` zaktualizowany (`db9fae4..32e5887`) |

```bash
git log --grep=number_local --oneline -3
# 32e5887 fix(invoice): ensure sale invoices receive number_local before KSeF.
```

## Co **nie** weszło w commit

Pozostałe lokalne zmiany (m.in. `invoice_number_policy.py`, frontend numeracji, inne docs) — **poza zakresem** tego fixu, nadal niecommitowane na `production`.

## Następne kroki (poza tym zadaniem)

1. **Deploy na DS723+** — wymaga osobnego polecenia (tu: celowo pominięty).
2. Po deploy: ponowny zapis FV `cc4a8c2f-948d-45e2-86e8-9dd19c7961a5` w UI (PUT) lub `mark-as-ready` — nada brakujący numer.
3. Masowy repair DB — tylko po potwierdzeniu.

## Uwaga techniczna

Commit zawiera normalizację końców linii (CRLF→LF) w `invoice.py` i `transmission_service.py` obok zmian merytorycznych — diff większy niż sama logika, testy przechodzą.
