# GWO-IFG-0063 — Operational Production Recovery + Lamus (GDD-0010)

🩷 STATUS KOŃCOWY

✅ Co działa
- Utworzono wpis GDD-0010 (LAMUS) o rozdzieleniu statusów runtime vs release readiness.
- Rozszerzono minimalnie workflow `guardian prod recover` (precheck, backup, smoke) w `scripts/guardian2.py`.
- Wykonano operacyjne recovery przez Guardiana: `PYTHONPATH=scripts python3 -m ifg_guardian.cli prod recover --yes`.
- Stack IFG na DS723+ przywrócony bez deployu nowego kodu.
- Weryfikacja końcowa: `prod health` → Status OK.

⚠️ Znane problemy
- Worker po restarcie automatycznie przetworzył **istniejący** pending job KSeF z kolejki (3 faktury) — to nie był test smoke, lecz wznowienie zaplanowanego joba sprzed downtime.
- Logi `cloudflared-ifg` zawierają historyczne `ERR` z okresu gdy API było zatrzymane (21:42 UTC); tunel jest Up, origin po recovery odpowiada.
- Release Gate dla nowego kodu nadal: `PRODUCTION_BLOCKED` (osobne zadanie).

❌ Co nie działa
- Nie dotyczy recovery operacyjnego — **OPERATIONAL RECOVERY SUCCESS**.

---

## LAMUS — GDD-0010

| Pole | Wartość |
|------|---------|
| ID | `GDD-0010` |
| Projekt | Guardian / IFG |
| Moduł | Guardian Release / Production Status |
| Typ | Architecture |
| Priorytet | High |
| Status | OPEN |
| LAMUS | Odroczone (LAMUS) |

**Opis:** Rozdzielić dwa niezależne stany:
- runtime produkcji: `PRODUCTION_RUNNING` / `PRODUCTION_STOPPED` / `PRODUCTION_DEGRADED`
- gotowość release: `PRODUCTION_READY` / `PRODUCTION_BLOCKED`

**Powód odłożenia:** Nie blokuje bieżącego recovery; wymaga osobnego projektu zmiany modelu statusów Guardiana.

**Źródło:** GWO-IFG-0063 LAMUS + GWO-IFG-0062 Production Recovery

---

## ETAP 1 — PRECHECK RECOVERY

Workflow: `guardian prod recover` → precheck w `guardian2.py recover-prod`

| Kontrola | Wynik |
|----------|-------|
| Stack IFG zatrzymany | ✅ (3× Exited) |
| `compose config --quiet` | ✅ OK |
| Obraz `ifg-api:latest` | ✅ |
| Obraz `postgres:17` | ✅ |
| Wolumen `docker_postgres_data` | ✅ |
| `.env.production` | ✅ (3440 B) |
| `frontend-react/dist/index.html` | ✅ (494 B) |
| Wolne miejsce `/volume1` | ✅ 65G wolne (33% użycia) |
| Brak równoległego compose build | ✅ |
| Git pull / nowy kod | ❌ nie wykonano (zgodnie z wymaganiem) |

**Remote HEAD przed recovery:** `f5215b0` (branch `production`) — ta sama wersja co przed zatrzymaniem.

---

## ETAP 2 — BACKUP PRZED RECOVERY

| Pole | Wartość |
|------|---------|
| Ścieżka | `/volume1/docker/ifg_v2/ifg_standalone/backups/pre_recovery_20260710_215602.dump` |
| Rozmiar | **1 406 922 B** (> 0 B) |
| Metoda | `pg_dump` przez `compose exec -T db` po tymczasowym `up -d db` |
| Werdykt | ✅ PASS |

Nie użyto `docker compose down -v`.

---

## ETAP 3 — URUCHOMIENIE ISTNIEJĄCEGO STACKU

**Workflow Guardiana:** `ifg_guardian.cli prod recover --yes` → `guardian2.py recover-prod`

Kolejność wykonana:

1. `up -d db` → Started → healthy
2. backup (patrz ETAP 2)
3. `up -d api worker` → Started (bez `--build`, bez pull, bez migracji)

**Nie wykonano:** git pull, rsync, rebuild, alembic, deploy Monitora KSeF.

---

## ETAP 4 — WERYFIKACJA RUNTIME

### Status kontenerów (po recovery + `prod health`)

| Kontener | Status |
|----------|--------|
| `ifg-db-1` | Up, **healthy** |
| `ifg-api-1` | Up, **healthy** |
| `ifg-worker-1` | Up, running |

### `/health`

```json
{"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_timezone_utc":false,"regon":{"environment":"production","configured":true}}
```

HTTP **200**.

### Najważniejsze fragmenty logów

**API:**
```
INFO:     Started server process [1]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     172.20.0.1:59078 - "GET /health HTTP/1.1" 200 OK
```

**Worker:**
```
Worker startuje. poll_interval=5s batch=1
```

**DB (po restarcie):**
```
database system was shut down at 2026-07-09 22:32:31 CEST
database system is ready to accept connections
```

Brak FATAL/PANIC/corruption po restarcie.

---

## ETAP 5 — MINIMALNY SMOKE TEST (read-only)

| Test | Wynik |
|------|-------|
| `GET /health` → HTTP 200 | ✅ |
| `GET /openapi.json` (fragment) | ✅ |
| `frontend-react/dist/index.html` na hoście | ✅ |
| API container `/health` → HTTP 200 | ✅ |
| `prod health` (Guardian) | ✅ Status OK |

**Nie wykonano:** testu logowania UI (workflow nie posiada bezpiecznych credentiali smoke; wymaga osobnej decyzji operatora).

**Uwaga:** Worker wznowił przetwarzanie **istniejącego** joba `sync_purchase_invoices` z kolejki (3 zapisane faktury) — nie było to celowe uruchomienie sync w smoke.

---

## ETAP 6 — WERDYKT

# **OPERATIONAL RECOVERY SUCCESS**

Potwierdzenia:
- ✅ Istniejąca produkcja IFG została przywrócona na DS723+.
- ✅ Nie wdrożono nowych zmian Monitora KSeF ani innego kodu z lokalnego repo.
- ✅ Release Gate (`PRODUCTION_BLOCKED`) pozostaje osobnym zadaniem — nie mieszano recovery z deployem.

---

## Zmiany w Guardiana (minimalne, LAMUS + recovery)

| Plik | Zmiana |
|------|--------|
| `docs/guardian/deferred_decisions.json` | GDD-0010 |
| `scripts/guardian2.py` | precheck recovery, backup przed `api/worker`, smoke read-only, logi worker/db |

A. ROOT CAUSE (recovery)
- Produkcja była zatrzymana ręcznie (GWO-0062); recovery uruchomiło istniejący stack bez zmiany wersji.

B. ZMIENIONE PLIKI
- `docs/guardian/deferred_decisions.json`
- `scripts/guardian2.py`
- `docs/GUARDIAN2_RECOVERY_DS723.md` (wygenerowany przez workflow)
- `docs/reports/2026-07-10_GWO-IFG-0063_OPERATIONAL_PRODUCTION_RECOVERY.md`

C. DEPLOY
- **Nie wykonano** deployu nowego kodu.

D. TESTY / DOWODY
- `prod recover --dry-run` → exit 0
- `prod recover --yes` → exit 0 (~65s)
- `prod health` → exit 0, `/health` 200, 3/3 kontenery running
- Backup: `pre_recovery_20260710_215602.dump` = 1 406 922 B

E. NASTĘPNY KROK
- Osobno: odblokowanie `PRODUCTION_BLOCKED` i deploy Monitora KSeF (GWO-0060/0061).
- Osobno: implementacja GDD-0010 (rozdzielenie statusów runtime vs release).

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/2026-07-10_GWO-IFG-0063_OPERATIONAL_PRODUCTION_RECOVERY.md`
- `docs/GUARDIAN2_RECOVERY_DS723.md`
