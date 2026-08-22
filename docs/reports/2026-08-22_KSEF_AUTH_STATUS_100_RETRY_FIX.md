# GWO — KSeF auth status 100: bounded retry na redeem

**Data:** 2026-08-22  
**Tryb:** implementacja + testy (bez deployu)  
**Incydent źródłowy:** `docs/reports/2026-08-22_KSEF_PURCHASE_SYNC_2026-08-21_INCIDENT_AUDIT.md`

---

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- `POST /auth/token/redeem` traktuje status uwierzytelniania **100** i **450** jako stany przejściowe.
- Bounded retry: limit czasu `KSEF_AUTH_REDEEM_TIMEOUT_SECONDS` (domyślnie 120 s), backoff 0.5 → ×1.5 (max 5 s), log każdej próby.
- Po udanym retry sync kontynuuje w **tym samym jobie** (brak czekania na kolejny slot).
- Monitor: `RETRY` + `WARNING` przy 100/450; `RESUME` + `SUCCESS` po przejściu; `ERROR` dopiero po wyczerpaniu limitu / trwałym błędzie.
- Testy: **87 passed** (auth redeem + purchase auth + session worker + notify).

⚠️ ZNANE PROBLEMY
- Brak (w zakresie tej poprawki). Deploy na DS723+ jeszcze nie wykonany.

❌ CO NIE DZIAŁA
- Brak.

---

## 1. ROOT CAUSE (incydent 21.08)

Redeem kończył się HTTP 400 / `exceptionCode` **21301** ze statusem uwierzytelniania **100**.  
Retry obsługiwał wyłącznie status **450** → natychmiastowy fail joba przed metadata/XML → odtworzenie dopiero kolejnym slotem + overlap (~12–24 h opóźnienia).

## 2. ROZWIĄZANIE

### Auth (`app/integrations/ksef/auth.py`)
- Parser statusu z `details`: regex `Status uwierzytelniania (N)`.
- Retry **tylko** gdy `exceptionCode == 21301` **oraz** `N ∈ {100, 450}`.
- Inne 21301 / inne 400 → fail natychmiast (bez ciemnego retry wszystkich 21301).
- Callbacki: `on_transient_retry`, `on_transient_recovered` (dla Monitora).

### Purchase auth + Monitor
- `PurchaseAuthService._authenticate_fresh` podpina callbacki → journal:
  - `RETRY` / `WARNING` (`auth_pending_100` / `auth_pending_450`)
  - `RESUME` / `SUCCESS` (`auth_ready`)
  - `ERROR` / `ERROR` po wyczerpaniu / trwałym failu
- `sync_received_invoices` przekazuje `correlation_id` syncu do `ensure_purchase_auth` — wpisy RETRY/RESUME w tym samym przebiegu Monitora.

### Bez zmian
- Scheduler, cron, overlap — bez zmian (pozostają warstwą bezpieczeństwa).

## 3. TESTY

```bash
python3 -m pytest \
  tests/unit/test_ksef_auth_redeem_timeout.py \
  tests/unit/test_ksef_purchase_auth_service.py \
  tests/unit/test_ksef_session_worker.py \
  tests/unit/test_purchase_sync_email_notification.py \
  tests/unit/test_purchase_sync_notify_config.py -q
```

→ **87 passed**

Pokrycie wymagane:
| Case | Wynik |
|------|--------|
| status 100 → retry → sukces | PASS |
| status 100 powtarzany → bounded fail | PASS |
| status 450 nadal działa | PASS |
| normalny sukces bez retry | PASS |
| błąd trwały (nie 100/450) bez nieskończonego retry | PASS |
| Monitor RETRY + RESUME przy transient | PASS |

## 4. ZMIENIONE PLIKI

- `app/integrations/ksef/auth.py`
- `app/services/ksef_purchase_auth_service.py`
- `app/services/ksef_session_service.py` (przekazanie `correlation_id`)
- `tests/unit/test_ksef_auth_redeem_timeout.py`
- `tests/unit/test_ksef_purchase_auth_service.py`
- `scripts/test_ksef_auth.py` (spójność diagnostyki 100/450)
- `docs/reports/2026-08-22_KSEF_AUTH_STATUS_100_RETRY_FIX.md`

## A. ROOT CAUSE
Redeem failował natychmiast przy statusie auth **100**; retry był tylko dla **450**.

## B. ZMIENIONE PLIKI
Jak w sekcji 4.

## C. DEPLOY
Nie wykonany w tym GWO. Kod gotowy do deployu workera/API (zmiana w ścieżce auth workera).

## D. TESTY
87 passed (pakiet auth/sync/retry powyżej).

## E. NASTĘPNY KROK
Deploy Guardian na DS723+ (rebuild API + worker). Po deployu: obserwacja Monitora przy kolejnym slocie z eventu spożywczym 100 (RETRY → RESUME w tym samym jobie).

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [x] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/2026-08-22_KSEF_AUTH_STATUS_100_RETRY_FIX.md`
- (kontekst) `docs/reports/2026-08-22_KSEF_PURCHASE_SYNC_2026-08-21_INCIDENT_AUDIT.md`
