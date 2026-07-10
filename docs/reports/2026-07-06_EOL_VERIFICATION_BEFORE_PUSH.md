# EOL Verification Before Push

**Data:** 2026-07-06  
**Check:** `repo.eol_check`  
**Branch:** `production`  
**HEAD:** `ce6685f6e595ddca716d3bd4af2695fec08375e7`  
**Werdykt przed push:** **NO_GO**

## Podsumowanie operatora

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy jakikolwiek tracked `M` ma realną zmianę logiczną? | **Tak** — 2 pliki |
| Czy można pushować bez commitu/discard? | **Nie** |
| Pliki EOL-only (9) | Szum CRLF — nie blokują same w sobie, ale werdykt to NO_GO z powodu logical |

**Pliki z realnym diffem (wymagają commit lub discard przed push):**

1. `app/persistence/repositories/transmission_repository.py`
2. `scripts/ifg_guardian/cli.py` (zmiany z tej sesji — `repo eol-check`)

**Rekomendacja:** Zacommituj zamierzone zmiany (`cli.py`, eol_check module, testy, raporty) lub przywróć do HEAD. Pliki EOL-only (9× app/frontend) można znormalizować **ręcznie** po osobnej zgodzie — Guardian ich nie zmieni automatycznie.

---

# Guardian EOL Check (`repo.eol_check`)

**Check ID:** `repo.eol_check`
**Branch:** `production`
**HEAD:** `ce6685f6e595ddca716d3bd4af2695fec08375e7`
**Verdict:** **NO_GO**

## Recommendation

2 file(s) with logical diff — commit or discard before release/cutover.

## Summary

| Metric | Count |
|--------|-------|
| Tracked modified files | 11 |
| EOL-only | 9 |
| Logical change | 2 |
| Unknown | 0 |

## EOL-only files

- `app/api/deps.py` (M) — Diff disappears with --ignore-cr-at-eol
- `app/domain/enums.py` (M) — Diff disappears with --ignore-cr-at-eol
- `app/persistence/mappers/invoice_mapper.py` (M) — Diff disappears with --ignore-cr-at-eol
- `app/persistence/models/invoice.py` (M) — Diff disappears with --ignore-cr-at-eol
- `app/services/invoice_number_policy.py` (M) — Diff disappears with --ignore-cr-at-eol
- `app/services/payment_service.py` (M) — Diff disappears with --ignore-cr-at-eol
- `frontend-react/src/api/invoices.js` (M) — Diff disappears with --ignore-cr-at-eol
- `frontend-react/src/components/invoice/InvoiceActions.jsx` (M) — Diff disappears with --ignore-cr-at-eol
- `frontend-react/vite.config.js` (M) — Diff disappears with --ignore-cr-at-eol

## Logical change files

- `app/persistence/repositories/transmission_repository.py` (M) — Diff remains with --ignore-cr-at-eol
- `scripts/ifg_guardian/cli.py` (M) — Diff remains with --ignore-cr-at-eol

## Per-file classification

| Path | Status | Classification | Normal diff | Ignore-CR diff | Note |
|------|--------|----------------|-------------|----------------|------|
| `app/api/deps.py` | `M` | EOL_ONLY | yes | no | Diff disappears with --ignore-cr-at-eol |
| `app/domain/enums.py` | `M` | EOL_ONLY | yes | no | Diff disappears with --ignore-cr-at-eol |
| `app/persistence/mappers/invoice_mapper.py` | `M` | EOL_ONLY | yes | no | Diff disappears with --ignore-cr-at-eol |
| `app/persistence/models/invoice.py` | `M` | EOL_ONLY | yes | no | Diff disappears with --ignore-cr-at-eol |
| `app/persistence/repositories/transmission_repository.py` | `M` | LOGICAL_CHANGE | yes | yes | Diff remains with --ignore-cr-at-eol |
| `app/services/invoice_number_policy.py` | `M` | EOL_ONLY | yes | no | Diff disappears with --ignore-cr-at-eol |
| `app/services/payment_service.py` | `M` | EOL_ONLY | yes | no | Diff disappears with --ignore-cr-at-eol |
| `frontend-react/src/api/invoices.js` | `M` | EOL_ONLY | yes | no | Diff disappears with --ignore-cr-at-eol |
| `frontend-react/src/components/invoice/InvoiceActions.jsx` | `M` | EOL_ONLY | yes | no | Diff disappears with --ignore-cr-at-eol |
| `frontend-react/vite.config.js` | `M` | EOL_ONLY | yes | no | Diff disappears with --ignore-cr-at-eol |
| `scripts/ifg_guardian/cli.py` | `M` | LOGICAL_CHANGE | yes | yes | Diff remains with --ignore-cr-at-eol |

## Release / cutover gate

| Verdict | Meaning |
|---------|---------|
| GO | No tracked modifications |
| GO_WITH_CAUTION | EOL-only noise — not full GO; manual normalize/restore before push |
| NO_GO | Logical diff and/or unknown files present |
