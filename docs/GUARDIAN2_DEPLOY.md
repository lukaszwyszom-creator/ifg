# Guardian2 MVP — deploy KSeF async sync

Data: 2026-05-22

## Cel

**Guardian2** (`scripts/guardian2.py`) — półautomatyczny deploy pakietu KSeF async sync.

**Guardian** (`scripts/guardian.py`) — read-only (diagnostyka, bez wdrożenia).

## CLI (MVP)

```bash
python3 scripts/guardian2.py --help
python3 scripts/guardian2.py deploy-ksef --dry-run
python3 scripts/guardian2.py deploy-ksef
python3 scripts/guardian2.py deploy-ksef --yes
```

| Flaga | Opis |
|-------|------|
| `--dry-run` | Wypisuje polecenia, nie wykonuje |
| `--yes` | Bez pytania przed etapem DS723+ |

Host SSH: `IFG_DS723_HOST` lub `ds723`.

## Sekwencja `deploy-ksef`

### Lokalnie (Mac mini)

1. `git branch --show-current` → musi być `production`
2. `node --test frontend-react/src/api/ksef.purchase-sync.test.mjs`
3. `cd frontend-react && npm ci && npm run build`
4. `python3 scripts/guardian.py --ksef-async-check`
5. `git status --short`
6. `git add` — tylko allowlista (KSeF, guardian, docs; **bez** `frontend-react/dist`)
7. Jeśli staged → `git commit -m "fix: harden KSeF async sync deploy flow"`
8. `git push origin production`

> **Build lokalny:** krok 3 buduje `frontend-react/dist` do walidacji (`--ksef-async-check`).  
> **Dist nie jest commitowany** — katalog jest w `.gitignore`. Artefakt musi powstać lokalnie (test) i ponownie na DS723+ (krok 4 remote).

### Remote (DS723+)

1. SSH → `cd /volume1/docker/ifg_v2/ifg_standalone`
2. `git branch --show-current` → musi być `production`
3. `git pull origin production`
4. `cd frontend-react && npm ci && npm run build`
5. `sudo docker compose -f docker/docker-compose.prod.yml build api`
6. `sudo docker compose -f docker/docker-compose.prod.yml up -d --no-deps --force-recreate api worker`
7. `python3 scripts/guardian.py --ksef-async-check`
8. `python3 scripts/guardian.py --deploy-check`
9. `curl -fsS http://127.0.0.1:8000/health`

Bez `--yes`: przed remote → `Kontynuować deploy na DS723+? [y/N]`

## Allowlist `git add`

- `app/api/routers/ksef_session.py`
- `app/worker/job_handlers/sync_purchase_invoices.py`
- `frontend-react/src/api/ksef.js`
- `frontend-react/src/api/ksef.purchase-sync.test.mjs`
- `frontend-react/src/components/dashboard/KSeFSessionBar.jsx`
- `frontend-react/src/components/layout/KSeFTopbarInfo.jsx`
- `scripts/guardian.py`, `scripts/guardian2.py`
- `docs/KSEF_FORCE_ASYNC_PURCHASE_SYNC.md`
- `docs/KSEF_SYNC_REFRESH_UX_FIX.md`
- `docs/KSEF_ASYNC_SYNC_E2E_DIAGNOSTIC.md`
- `docs/GUARDIAN2_DEPLOY.md`

### `frontend-react/dist`

- Artefakt builda Vite (`npm run build`), **nie** commitowany (`.gitignore`)
- **Lokalnie:** budowany w kroku 3 przed `--ksef-async-check` (walidacja bundle)
- **DS723+:** budowany ponownie w kroku 4 remote — ten dist trafia do produkcji

## Bezpieczniki

Guardian2 **nie wykonuje**:

- `docker compose down` / `down -v`
- resetu bazy / migracji Alembic
- `git reset --hard` / `git clean`
- `npm audit fix`, aktualizacji npm/node

Błąd dowolnego kroku → **abort** (exit 1).

## Ograniczenia MVP

- Tylko scenariusz **`deploy-ksef`** (brak `--local-only` / `--remote-only`)
- Commit tylko z allowlisty; jeden stały komunikat commita
- `git push` zawsze na końcu etapu lokalnego (nawet bez nowego commita)
- Restart tylko **api** i **worker** (db nietknięte)
- Brak automatycznego `git pull --rebase` przy odrzuconym pushu
- Wymaga skonfigurowanego SSH (`ds723`) i sudo docker na NAS
- Logi KSeF po deployu — ręcznie:
  ```bash
  sudo docker compose -f docker/docker-compose.prod.yml logs -f api | grep KSEF_ASYNC_SYNC
  sudo docker compose -f docker/docker-compose.prod.yml logs -f worker | grep KSEF_ASYNC_SYNC
  ```

## Pliki

| Plik | Opis |
|------|------|
| `scripts/guardian2.py` | Deploy helper MVP |
| `docs/GUARDIAN2_DEPLOY.md` | Ten dokument |
