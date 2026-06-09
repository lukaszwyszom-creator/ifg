# KSeF purchase sync — weryfikacja patcha

Data: 2026-05-22  
Pliki: `app/services/ksef_session_service.py`, `app/api/routers/ksef_session.py`

## Składnia

`py_compile` na obu plikach — **OK**, brak błędów składni.

## resolved_from / resolved_to vs wejściowe date_from/date_to

| Miejsce | Status |
|---------|--------|
| Response JSON (`date_from`, `date_to`) | ✅ `resolved_from.isoformat()`, `resolved_to.isoformat()` |
| Log końcowy `KSeF purchases sync done` | ✅ `resolved_from`, `resolved_to` |
| Wywołanie `sync_received_invoices` | ✅ przekazywane `resolved_from`, `resolved_to` |
| Logi per subjectType w `sync_received_invoices` | ✅ używają parametrów funkcji, które w tym flow są już wartościami resolved (nie surowe `None` z API) |
| Zapis `state_json` (`last_date_from`, `last_date_to`) | ✅ resolved |

## Priorytety zakresu dat (`resolve_purchase_sync_window`)

Kolejność w kodzie:

1. `date_from` podane ręcznie → **pierwszeństwo**, zwraca `(date_from, resolved_to)` — ✅
2. `force_full=true` → **ignoruje** `sync_state_json`, zwraca ostatnie 365 dni (`ksef_purchase_sync_full_days`) — ✅
3. Inkrementalny (stan `last_date_to` − bufor 2 dni) — tylko gdy brak `date_from` i `force_full=false` — ✅
4. Fallback: `dziś − days_back` — ✅

## days_back → settings

| Warstwa | Przed poprawką | Po poprawce |
|---------|----------------|-------------|
| Router `KSeFPurchaseSyncRequest.days_back` | Domyślnie `90` (hardcoded) — settings nigdy nie używane z API | `None` — brak wartości w body |
| Service `sync_purchase_invoices` | `days_back if days_back is not None else settings.ksef_purchase_sync_days_back` | bez zmian — ✅ |

**Poprawka:** `days_back: int | None = None` w routerze, aby puste body delegowało domyślną wartość do `settings.ksef_purchase_sync_days_back`.

## Podsumowanie

Implementacja poprawna pod kątem resolved dat, `force_full`, priorytetu `date_from`. Jedyna usterka: router blokował domyślną wartość `days_back` ze settings — naprawiona minimalną zmianą (1 linia).
