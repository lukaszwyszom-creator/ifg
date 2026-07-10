# GWO-IFG-0049 — Backup Safety Gate Verification

**Data:** 2026-07-08  
**Status:** DONE (Safety Gate GO po utworzeniu backupu)  
**Deploy:** nie wykonywano

---

## Lokalizacja backupów

### Katalog sprawdzany przez Guardian

```
/volume1/docker/ifg_v2/backups
```

Konfiguracja: `scripts/ifg_guardian/core/preflight/config.py` → `DEFAULT_REMOTE_BACKUP_DIR`

### Stan przed naprawą

```bash
ssh zdalny_admin@ds723 'ls /volume1/docker/ifg_v2/backups'
# ls: cannot access '/volume1/docker/ifg_v2/backups': No such file or directory

ssh zdalny_admin@ds723 'ls /volume1/docker/ifg_v2/ifg_standalone/backups'
# ls: cannot access ...: No such file or directory
```

Wniosek: **brak katalogu i brak backupów** w oczekiwanej lokalizacji Safety Gate.

### Stan po naprawie

Utworzono backup zgodnie z workflow produkcyjnym (`docs/IFGM_PILOT_DEPLOYMENT_PLAN.md`):

```bash
mkdir -p /volume1/docker/ifg_v2/backups
docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T db \
  pg_dump -U postgres -d ksef_backend -Fc \
  > /volume1/docker/ifg_v2/backups/ksef_backend_20260708_230227.dump
```

Weryfikacja:

```text
-rw-r--r-- 1 zdalny_admin users 273K Jul  8 23:02 ksef_backend_20260708_230227.dump
```

Uwaga: pierwsza próba (bez `PATH` do docker) pozostawiła pusty plik `ksef_backend_20260708_230219.dump` (0 B). Guardian wykrywa oba pliki `.dump`; do rollbacku używać wyłącznie pliku 273K.

---

## Weryfikacja implementacji Safety Gate

### Skąd Guardian czyta backupy

`check_backup_exists()` w `scripts/ifg_guardian/core/preflight/checks.py`:

```python
find "/volume1/docker/ifg_v2/backups" -maxdepth 2 \
  \( -name "*.tgz" -o -name "*.dump" -o -name "*.sql" \)
```

`check_backup_freshness()` szuka `.tgz` / `.dump` młodszych niż 7 dni w tym samym katalogu.

### Czy ścieżka jest poprawna?

**Tak** — zgodna z dokumentacją operacyjną (`IFGM_PILOT_DEPLOYMENT_PLAN.md`, `GWO_G003A_PREFLIGHT_ENGINE.md`).

### Czy występuje błąd konfiguracji detekcji?

**Nie.** Guardian poprawnie wykrył brak backupów w GWO-0048:

```text
PRECHECK_REPORT_2026_07_08.md (przed naprawą):
- FAIL | Backup exists | no backups found in /volume1/docker/ifg_v2/backups
```

### Uwaga architektoniczna (nie była root cause tego incydentu)

`ssh_executor.run_backup_before_migration()` zapisuje backup do **innej ścieżki**:

```text
/volume1/docker/ifg_v2/ifg_standalone/backups/pre_migrate_*.sql
```

Safety Gate **nie** sprawdza tego katalogu. To rozjazd workflow migracji vs preflight, ale w tym przypadku oba katalogi były puste — problemem był brak backupu, nie zła detekcja.

---

## Root cause

1. Katalog `/volume1/docker/ifg_v2/backups` nigdy nie został utworzony na DS723+.
2. Produkcyjny backup `pg_dump` nie był wykonany przed deployem GWO-0048.
3. Safety Gate zadziałał poprawnie i zablokował deploy (`NO_GO` → `Backup exists: FAIL`).
4. GWO-0048 nie padł na błędzie detekcji — padł na **rzeczywistym braku backupu**.

---

## Ewentualna poprawka

**Nie wymagana dla detekcji** (backup nie istniał).

Rekomendowana poprawka follow-up (Guardian, nie IFG deploy):

- Ujednolicić ścieżkę zapisu backupu w `ssh_executor.run_backup_before_migration()` z `DEFAULT_REMOTE_BACKUP_DIR`.
- Dodać walidację `test -s` (rozmiar > 0) w `check_backup_exists()`.

---

## Wynik ponownego Preflight / Safety Gate

Po utworzeniu backupu uruchomiono preflight (LIVE, `allow_dirty_build=True`):

```text
DECISION=GO
BLOCKING=0
BACKUP_CHECK: PASS | 2 backup artifact(s) found
BACKUP_CHECK: PASS | backup within 7 days
```

Raport: `docs/guardian/PRECHECK_REPORT_2026_07_08.md` (workflow `GWO-IFG-0049-preflight`)

### Blockery usunięte

- `Backup exists: no backups found in /volume1/docker/ifg_v2/backups` → **PASS**

### Pozostałe ostrzeżenia (nie blokują Safety Gate)

- `Git clean: Production build from dirty working tree (--allow-dirty-build)` — WARNING tylko

---

## Rekomendacja następnego kroku

1. **GWO-IFG-0050:** ponowić controlled deploy (`ifg deploy run --allow-dirty-build --yes`) — Safety Gate backup jest już GO.
2. Usunąć pusty plik `ksef_backend_20260708_230219.dump` (0 B) na DS723+ (opcjonalnie, higiena).
3. **GWO-Guardian-001:** ujednolicić ścieżki backupu między `ssh_executor` a `PreflightConfig`.

---

## Lista wszystkich wygenerowanych raportów `.md`

1. `docs/reports/2026-07-08_GWO-IFG-0049_BACKUP_SAFETY_GATE_VERIFICATION.md`
2. `docs/guardian/PRECHECK_REPORT_2026_07_08.md` (zaktualizowany — Decision: GO)

---

## 🩷 STATUS KOŃCOWY

### ✅ CO DZIAŁA

- Guardian poprawnie wykrywa brak backupu (GWO-0048).
- Backup produkcyjny utworzony w oczekiwanej lokalizacji (273K).
- Safety Gate po naprawie: **GO** (0 blocking items).

### ⚠️ ZNANE PROBLEMY

- Pusty plik backupu (0 B) z nieudanej pierwszej próby.
- Rozjazd ścieżek backupu: `ssh_executor` vs `PreflightConfig`.

### ❌ CO NIE DZIAŁA

- Brak — weryfikacja zakończona pomyślnie.

## A. ROOT CAUSE

Brak katalogu i plików backupu na DS723+, nie błąd detekcji Guardiana.

## B. ZMIENIONE PLIKI

- `docs/reports/2026-07-08_GWO-IFG-0049_BACKUP_SAFETY_GATE_VERIFICATION.md`
- `docs/guardian/PRECHECK_REPORT_2026_07_08.md` (nadpisany przez preflight)

## C. DEPLOY

Nie wykonano (zgodnie z poleceniem).

## D. TESTY

- Remote `ls` backup dir: PASS (273K dump istnieje)
- Preflight + Safety Gate: GO

## E. NASTĘPNY KROK

GWO-IFG-0050: ponowienie controlled deploy z override dirty tree.
