# Audyt Repo IFG (read-only)

Data audytu: 2026-04-29
Zakres: analiza bez modyfikacji kodu

## Krytyczne

1. Jawne hasło i ryzykowne uprawnienia do Dockera w deploy.
- Hasło sudo zapisane wprost: scripts/deploy_ds723.sh
- Nadawanie `chmod 666 /var/run/docker.sock` zwiększa powierzchnię ataku.

2. Niespójny smoke test względem backendu.
- Testuje `/ui`, którego backend nie wystawia.
- Test kontrahenta używa query (`/contractors?nip=...`) zamiast route `/contractors/by-nip/{nip}`.

3. Ryzyko operacyjne migracji uruchamianych wielokrotnie.
- Alembic uruchamiany przy starcie API (Dockerfile) i ponownie w deploy script.

## Ważne

1. Niespójność stylu ścieżek API.
- Frontend używa `/api/v1` jako base URL.
- `GET /health` i `GET /metrics` są poza `/api/v1`.

2. Endpointy potencjalnie martwe z perspektywy UI.
- `GET /api/v1/transmissions/{id}/upo`
- `GET /api/v1/transmissions/invoice/{invoice_id}`
- Legacy aliasy KSeF pod `/ksef/session/*` obok `/ksef-sessions/*`.

3. Potencjalnie nieużyte metody warstwy API frontendu.
- `paymentsApi.invoiceHistory`
- `paymentsApi.reverseAllocation`
- `contractorsApi.refresh`
- `contractorsApi.createManual`

4. Ograniczenie dostępności usług produkcyjnych.
- Bind `127.0.0.1` dla API i frontendu wymaga poprawnie skonfigurowanego reverse proxy.

## Do później

1. Duplikaty logiki dat/okresów w frontendzie.
- Powtarzalne helpery w DashboardSummary i VATSummary.

2. Uporządkowanie wariantów endpointów KSeF.
- Pozostawić jeden kanoniczny kontrakt i oznaczyć/deprecjonować aliasy.

3. Aktualizacja README.
- Obecny opis jest skrótowy względem rzeczywistego zakresu systemu.

## Można usunąć

1. Artefakty robocze trzymane w repo.
- draft.txt
- draft_sample.txt
- draft_stats.txt
- backup_before_commit.patch

2. Nieużywane metody API frontendu (po potwierdzeniu przez zespół).

## Nie ruszać

1. Historia migracji i pliki Alembic.
2. Walidacje bezpieczeństwa production w `app/core/config.py`.
3. Produkcyjny proxy `/api` i `/health` w nginx frontendu.

## Odwołania frontend -> backend

1. Frontend client: baseURL `/api/v1`.
2. Dev: Vite proxy `/api -> localhost:8000`.
3. Prod: nginx frontendu proxy `/api -> api:8000`.
4. Login UI: route `/login`.

## Spójność ścieżek `/ui`, `/api/v1`, `/health`

1. `/api/v1` używane konsekwentnie dla endpointów biznesowych.
2. `/health` i `/metrics` celowo poza prefiksem API.
3. `/ui` występuje jako przestarzałe odwołanie w smoke teście.

## Zależności (pyproject)

1. Brak `requirements.txt`; źródłem prawdy jest `pyproject.toml`.
2. Kluczowe biblioteki są używane (m.in. `httpx`, `requests`, `lxml`, `weasyprint`, `zeep`).

## Wielkość repo i największe pliki

1. Worktree lokalny: ~390 MB (zawyżone przez lokalne środowiska).
2. Śledzone pliki Git: 259.
3. Największe śledzone pliki:
- frontend-react/src/assets/logo-ifg.png
- frontend-react/public/favicon.png
- backup_before_commit.patch

## Pliki wygenerowane, które nie powinny być w Git

1. `.venv`, `node_modules`, `dist`, `.pytest_cache` nie są śledzone (OK).
2. Do usunięcia z Git: artefakty draft/patch wymienione wyżej.

## Ryzyka wdrożeniowe Docker/Synology

1. Sekrety i sudo hasło w skrypcie deploy.
2. Ryzykowne uprawnienia do socketu Docker.
3. Podwójne migracje DB.
4. Wymóg reverse proxy przy bindzie do localhost.
5. Frontend image budowany lokalnie i transportowany tar.gz (procedura działa, ale jest podatna na błędy operacyjne bez dodatkowych kontroli).

## Minimalny zestaw plików do uruchomienia produkcyjnego

1. Backend:
- app/
- alembic/
- alembic.ini
- pyproject.toml
- docker/Dockerfile

2. Frontend:
- frontend-react/
- docker/Dockerfile.frontend
- docker/nginx.frontend.conf

3. Orkiestracja:
- docker/docker-compose.prod.yml

4. Poza repo (wymagane):
- `.env.production` na serwerze
- wolumen `postgres_data`
- wolumen/sekrety `ksef_keys`

## Proponowany plan porządkowania krok po kroku

1. Bezpieczeństwo deploymentu:
- usunąć hasło i `chmod 666`; wdrożyć bezpieczny model uprawnień.

2. Naprawa smoke testu:
- usunąć `/ui`, poprawić kontrakt `contractors` i uruchamiać testy w CI.

3. Ustalenie polityki ścieżek:
- zdecydować, czy `health/metrics` zostają poza `/api/v1`, i opisać to jawnie.

4. Audyt endpointów i metod frontend API:
- oznaczyć public/internal/deprecated, usunąć faktycznie martwe.

5. Higiena repo:
- usunąć artefakty draft/patch i doprecyzować `.gitignore`.

6. Refactor frontend:
- wydzielić wspólne helpery dat/okresów.

7. Dokumentacja operacyjna:
- rozszerzyć README o realny runbook dev/prod, healthchecki, rollback.

8. Hardening produkcji:
- checklista backup/migracje/rollback, test restore, kontrola sekretów.
