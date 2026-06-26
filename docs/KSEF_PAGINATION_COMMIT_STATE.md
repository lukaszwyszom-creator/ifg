# KSeF pagination commit state

## Commit

- **Hash:** `0b9707f`
- **Message:** `fix(ksef): paginate purchase metadata across all pages`
- **Branch:** `production`
- **Parent:** `ca30742`

## Staged / committed files (5)

1. `app/integrations/ksef/client.py`
2. `tests/unit/test_ksef_metadata_pagination.py` (new)
3. `tests/unit/test_ksef_purchase_sync_resume.py`
4. `tests/unit/test_ksef_client_retry.py`
5. `docs/KSEF_PURCHASE_METADATA_PAGINATION_FIX_2026_06.md` (new)

```
5 files changed, 401 insertions(+), 25 deletions(-)
```

## Working tree po commicie

**Tak** — pozostały niecommitowane zmiany poza tym commitem:

- Modified: `app/api/deps.py`, `app/domain/enums.py`, `app/persistence/*`, `app/services/invoice_number_policy.py`, `app/services/payment_service.py`, `frontend-react/*`
- Untracked: wiele dokumentów diag/fix oraz `frontend-react/src/components/invoice/invoiceCardListNumbering.test.js`

Commit selektywny — bez plików spoza listy paginacji KSeF.
