# KSeF Purchase Authentication vs Online Session

## Dlaczego rozdzielono

API KSeF używa **dwóch niezależnych mechanizmów**:

| Mechanizm | Operacje KSeF | Wymagane dane |
|-----------|---------------|---------------|
| **Purchase auth** (tokeny) | `query metadata`, `download XML` zakupów | `access_token`, opcjonalnie `refresh_token` |
| **Online session** (sesja FA) | `open session`, `submit invoice`, `close session` | `session_reference`, klucz symetryczny, IV |

Wcześniej `KSeFSessionService` wymuszał aktywną sesję online także przy synchronizacji zakupów (`get_session_context()` → `get_active_session()`). To blokowało auto-sync schedulera — operator musiał kliknąć „Połącz” w UI.

Po refaktorze GWO-IFG-0032:

- **Zakupy** → `PurchaseAuthService.ensure_purchase_auth()`
- **Sprzedaż** → `KSeFSessionService.ensure_online_session()` (alias `get_session_context()`)

## Komponenty

```
app/services/ksef_token_store.py      — statusy, walidacja tokenów, metadata JSON
app/services/ksef_purchase_auth_service.py — cykl życia tokenów zakupowych
app/services/ksef_session_service.py    — sesja online + sync zakupów (deleguje auth)
app/integrations/ksef/auth.py           — get_tokens(), refresh_access_token()
```

## Statusy w `ksef_sessions`

| `status` | `session_reference` | Znaczenie |
|----------|---------------------|-----------|
| `auth_active` | `NULL` | Tylko purchase auth (scheduler) |
| `active` | ustawione | Sesja online (sprzedaż) |
| `expired` / `terminated` | dowolne | Historyczny rekord |

**Brak migracji DB** — nowy status `auth_active` jest wartością tekstową w istniejącej kolumnie `status`.

## Przepływ purchase auth

```
ensure_purchase_auth(nip)
  ├─ access_token ważny? → return PurchaseAuthContext
  ├─ refresh_token ważny? → auth_provider.refresh_access_token()
  │     └─ błąd? → pełna autoryzacja (fallback)
  └─ auth_provider.get_tokens(nip, KSEF_AUTH_TOKEN)
        └─ zapis rekordu auth_active (session_reference = NULL)
```

Zmienne środowiskowe:

- `KSEF_AUTH_TOKEN` — token autoryzacyjny do pełnego uwierzytelnienia (scheduler, tło)
- `KSEF_AUTO_SYNC_ENABLED`, `KSEF_AUTO_SYNC_CRON` — harmonogram (bez zmian)

## Przepływ sprzedaży (bez zmian semantycznych)

```
submit_invoice / poll_ksef_status
  → ensure_online_session(nip)
    → get_active_session() — tylko status=active AND session_reference IS NOT NULL
    → wymaga symmetric_key + IV w metadata
```

Wysyłka faktury **nadal wymaga** jawnego otwarcia sesji online przez UI lub API.

## UI — `get_connection_status()`

| `ui_status` | Opis |
|-------------|------|
| `CONNECTED` | Aktywna sesja online |
| `PURCHASE_AUTH_ONLY` | Tokeny zakupowe OK, brak sesji online |
| `DISCONNECTED` | Brak ważnych tokenów |

## Wpływ na scheduler

Scheduler **nie wymaga zmian** — enqueue `sync_purchase_invoices` pozostaje bez zmian. Handler woła `sync_received_invoices()`, które wewnętrznie używa `ensure_purchase_auth()`.

```
Scheduler tick
  → enqueue sync_purchase_invoices
    → SyncPurchaseInvoicesJobHandler
      → sync_received_invoices()
        → ensure_purchase_auth()   ← nowe
        → metadata + XML download
```

## Wpływ na Guardian

Guardian MVP skanuje endpointy mobile/backend — **brak nowych tras API**. Zmiana jest warstwy serwisowej. Przed deployem nadal uruchamiaj:

```bash
python scripts/guardian.py
```

Guardian nie weryfikuje tokenów KSeF — operacyjnie wymaga `KSEF_AUTH_TOKEN` w ENV workera.

## Bezpieczeństwo

- Tokeny i klucze szyfrowania pozostają w `token_metadata_json` (jak dotąd).
- Purchase auth **nie udostępnia** klucza symetrycznego ani `session_reference` — sync zakupów ich nie potrzebuje.
- Sprzedaż nadal wymaga pełnej sesji online z szyfrowaniem FA(3).
- `refresh_access_token()` używa refresh tokena z DB — bez logowania hasła/tokena w logach.

## Kompatybilność wsteczna

- Istniejące rekordy `status=active` z `session_reference` działają dla sprzedaży i zakupów.
- `open_session()` może **uaktualnić** rekord `auth_active` → `active` (upgrade do sesji online).
- API endpointów bez zmian kontraktu.
