# IFGM — plan wdrożenia pilotażowego na DS723+

**Wersja:** 1.1  
**Data:** 2026-05-22  
**Rola:** architekt wdrożenia / audytor operacyjny (G2)  
**Zakres:** backend IFG (DS723+) + aplikacja mobilna IFGM (Expo)  
**Status aplikacji:** rekomendacja RC — **WDRAŻAĆ PILOTAŻOWO** (po RC-FIX: P1-1, P1-7 zamknięte)

**Środowisko:** DS723+ to **produkcja** — wszystkie operacje wykonuj zgodnie z sekcją 1.0 (bezpieczeństwo).

Ten dokument **nie zastępuje** [`DS723_DEPLOYMENT_CHECKLIST.md`](DS723_DEPLOYMENT_CHECKLIST.md) — uzupełnia go o warstwę mobile i procedury pilotażowe.

**Repo produkcyjne IFG:**

```
/volume1/docker/ifg_v2/ifg_standalone
```

---

## Streszczenie

| Warstwa | Cel pilotażu |
|---------|----------------|
| IFG (backend + web) | Stabilny stack Docker na DS723+, migracje, healthcheck |
| IFGM (mobile) | Połączenie z API **bez Cloudflare Access** (LAN lub Tailscale) |
| Poza zakresem pilotażu | KSeF w mobile (ekran demo), SecureStore, paginacja |

---

## 1. Wymagania wstępne

Wykonaj **przed** jakimkolwiek deployem. Każdy punkt musi być potwierdzony (data, osoba, wynik).

### 1.0 Bezpieczeństwo produkcji (DS723+)

**Obowiązkowe zasady — bez wyjątków:**

| Zasada | Opis |
|--------|------|
| Backup przed migracją | Przed każdym `alembic upgrade head` wykonaj backup PostgreSQL (sekcja 1.1) |
| Nie resetuj bazy | **Zakaz** `DROP DATABASE`, czyszczenia tabel produkcyjnych, seedów na produkcji |
| Nie usuwaj wolumenów | **Zakaz** `docker compose down -v` i `docker volume rm` na DS723+ |
| Restore tylko w ostateczności | `pg_restore` wyłącznie po potwierdzonej regresji; wymaga wcześniejszego backupu |
| DS723+ = produkcja | Każdy deploy wpływa na dane operacyjne firmy |

### 1.1 Backup PostgreSQL na DS723+

```bash
# Na DS723+ (SSH)
cd /volume1/docker/ifg_v2/ifg_standalone

# Snapshot logiczny (zalecany przed deployem i PRZED migracjami Alembic)
docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T db \
  pg_dump -U postgres -d ksef_backend -Fc \
  > /volume1/docker/ifg_v2/backups/ksef_backend_$(date +%Y%m%d_%H%M%S).dump

# Weryfikacja pliku backupu
ls -lh /volume1/docker/ifg_v2/backups/*.dump | tail -1
```

**Kryterium gotowości:** istnieje backup z ostatnich 24 h, rozmiar > 0, zapisany poza kontenerem (`/volume1/docker/ifg_v2/backups/`).

Opcjonalnie: snapshot wolumenu Docker (`postgres_data`) przez DSM Snapshot Replication — dodatkowa warstwa, nie zamiennik `pg_dump`.

### 1.2 Potwierdzenie aktualnego brancha / commita

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
git fetch origin
git status
git log -1 --oneline
git branch -vv
```

**Zapisz w protokole pilotażu:**
- commit SHA wdrażany na produkcję,
- branch (np. `main` / tag pilotażowy),
- czy working tree jest czysty (`git status` bez niezacommitowanych zmian na serwerze).

**Kryterium gotowości:** znany, zatwierdzony commit; brak lokalnych modyfikacji na DS723 poza `.env.production`.

### 1.3 Weryfikacja statusu kontenerów Docker

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
docker compose -f docker/docker-compose.prod.yml --env-file .env.production ps
docker compose -f docker/docker-compose.prod.yml --env-file .env.production ps --format json | jq '.[].Health' 2>/dev/null || true
```

**Oczekiwany stan przed deployem (baseline):**
| Kontener | Status |
|----------|--------|
| `api` | running, healthy |
| `worker` | running |
| `db` | running, healthy |

**Kryterium gotowości:** wszystkie trzy kontenery `running`; `api` i `db` przechodzą healthcheck.

### 1.4 Zgodność repo ↔ produkcja

| Element | Weryfikacja |
|---------|-------------|
| `.env.production` | Istnieje, `chmod 600`, nie w git |
| `frontend-react/dist` | Zbudowany z tego samego commita co API |
| Migracje Alembic | `alembic current` = oczekiwana rewizja z brancha |
| Wersja API | `curl -fsS http://127.0.0.1:8000/health` → 200 |
| Mobile RC | Commit z RC-FIX (`partially_paid`, modal salda) |

```bash
# Rewizja migracji
docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec api alembic current

# Health
curl -fsS http://127.0.0.1:8000/health && echo OK

# JWT login (z DS723 localhost — omija Cloudflare)
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"TWOJ_LOGIN","password":"TWOJE_HASLO"}' | head -c 200
```

**Kryterium gotowości:** health OK, login zwraca JSON z `access_token`, migracja zgodna z oczekiwaniami.

---

## 2. Checklista deployu IFG na DS723+

### Kolejność działań

| # | Działanie | Punkt kontrolny |
|---|-----------|-----------------|
| 1 | Backup DB (sekcja 1.1) | Plik `.dump` utworzony |
| 2 | `git pull` / checkout zatwierdzonego commita | SHA zapisany |
| 3 | Build frontend React (jeśli zmiany w `frontend-react/src`) | `frontend-react/dist/index.html` istnieje |
| 4 | `docker compose … up -d --build --force-recreate api worker` | Kontenery running |
| 5 | `alembic upgrade head` (jeśli nowe migracje; **tylko po backupie**) | `alembic current` = head |
| 6 | Health + logi | Brak ERROR w ostatnich 50 liniach api |
| 7 | Test web UI `/ui` | Logowanie użytkownika IFG |
| 8 | Test endpointów mobile (curl) | Dashboard mobile 200 |

### Komendy deployu (standard)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

# 1. Frontend — obowiązkowy po każdej zmianie w frontend-react/src
cd frontend-react
npm run build
cd ..

# Jeżeli zmieniły się zależności npm (package.json / package-lock.json), przed buildem wykonaj:
#   cd frontend-react && npm ci && npm run build && cd ..

# 2. Rebuild API + worker
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  up -d --build --force-recreate api worker

# 3. Migracje (TYLKO po backupie DB — sekcja 1.1)
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec api alembic upgrade head

# 4. Weryfikacja
docker compose -f docker/docker-compose.prod.yml --env-file .env.production ps
curl -fsS http://127.0.0.1:8000/health
```

### Test endpointów używanych przez IFGM (z DS723)

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"TWOJ_LOGIN","password":"TWOJE_HASLO"}' | jq -r .access_token)

curl -fsS -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/v1/mobile/dashboard?period=$(date +%Y-%m)" | head -c 300

curl -fsS -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/v1/invoices/?direction=sale&page=1&size=5" | head -c 200

curl -fsS -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/v1/payments/settlements?side=all" | head -c 200
```

### Kryteria przerwania wdrożenia IFG

**STOP deploy — nie przechodź do IFGM:**

| Warunek | Działanie |
|---------|-----------|
| Brak backupu DB przed migracją | Wykonaj backup (sekcja 1.1), dopiero potem `alembic upgrade` |
| `alembic upgrade head` kończy się błędem | Rollback (sekcja 7), nie uruchamiaj mobile |
| `/health` ≠ 200 po 3 minutach | Sprawdź logi api/db, rollback jeśli regresja |
| Login JWT nie działa na localhost:8000 | Napraw auth przed mobile |
| `api` lub `db` unhealthy | Nie wdrażaj IFGM |
| Brak backupu DB | Wykonaj backup, dopiero potem kontynuuj |

---

## 3. Checklista uruchomienia IFGM

### 3.1 EXPO_PUBLIC_API_BASE_URL

**Priorytet konfiguracji** (z `mobile-expo/src/api/config.ts`):
1. `EXPO_PUBLIC_API_BASE_URL` (env przy starcie/buildzie)
2. `app.json` → `expo.extra.apiBaseUrl`
3. fallback: `http://127.0.0.1:8000` — **nie działa na fizycznym iPhone**

**Domyślny `app.json` wskazuje localhost** — dla pilotażu **obowiązkowo** ustaw env przy starcie lub buildzie.

### 3.2 Konfiguracja Expo

#### Opcja A — pilotaż developerski (Expo Go, szybki start)

Na Macu z repo:

```bash
cd mobile-expo
npm ci

# LAN (iPhone w tej samej sieci co DS723 / Mac z mostem)
EXPO_PUBLIC_API_BASE_URL=http://192.168.x.x:8000 npx expo start

# Tailscale (zalecane dla pilotażu poza LAN)
EXPO_PUBLIC_API_BASE_URL=http://100.x.x.x:8000 npx expo start
```

Zeskanuj QR w **Expo Go** na iPhone.

#### Opcja B — build pilotażowy (TestFlight / dev client)

```bash
cd mobile-expo
EXPO_PUBLIC_API_BASE_URL=http://100.x.x.x:8000 npx expo prebuild  # jeśli wymagane
# EAS Build z ustawionym EXPO_PUBLIC_API_BASE_URL w secrets EAS
```

Dla buildu natywnego z HTTP (bez TLS) — wymagana konfiguracja ATS w iOS (`NSAppTransportSecurity` / Exception Domains). **Expo Go** toleruje HTTP w dev; standalone build może wymagać dodatkowej konfiguracji — zweryfikuj przed dystrybucją poza Expo Go.

### 3.3 Wymagania dla iPhone

| Wymaganie | Szczegóły |
|-----------|-----------|
| iOS | Wspierany przez Expo SDK 54 |
| Sieć | LAN **lub** Tailscale aktywny na iPhone |
| Aplikacja | Expo Go (pilotaż) lub zainstalowany dev build |
| Konto | Użytkownik IFG z dostępem do logowania (użytkownicy pilotażowi: gosia, lukasz) |
| Cloudflare | **Nie używać** `https://ifg.ikonastudio.pl` bez bypass Access |

### 3.4 Połączenie IFGM → IFG

```
[iPhone + IFGM] ──HTTP:8000──► [DS723 API]
                                    │
                                    ├── LAN: http://192.168.x.x:8000
                                    └── Tailscale: http://100.x.x.x:8000
```

**Uwaga infrastrukturalna:** `docker-compose.prod.yml` binduje port API jako `127.0.0.1:8000:8000` — dostęp spoza localhost wymaga jednego z:

- **Tailscale** na DS723 + `tailscale serve` / zmiana bind na `0.0.0.0:8000` (tylko w zaufanej sieci),
- reverse proxy DSM z regułą LAN,
- SSH tunnel (tylko dev, nie dla pilotażu użytkownika).

Przed pilotażem **potwierdź**, że iPhone osiąga API:

```bash
# Z iPhone (Safari) lub z Maca w tej samej sieci co telefon:
curl -fsS http://ADRES_API:8000/health
```

Komunikat IFGM o Cloudflare Access oznacza użycie złego URL — patrz sekcja 4.

---

## 4. Weryfikacja infrastruktury sieciowej

### 4.1 Cloudflare Access

| Aspekt | Ocena |
|--------|-------|
| URL publiczny `https://ifg.ikonastudio.pl` | Chroniony CF Access — **blokuje** mobile JWT login |
| Objaw w IFGM | HTTP 302, komunikat o Cloudflare Access |
| Dla pilotażu | **Nie używać** jako `EXPO_PUBLIC_API_BASE_URL` |

Weryfikacja:

```bash
curl -i -X POST https://ifg.ikonastudio.pl/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"TWOJ_LOGIN","password":"TWOJE_HASLO"}' | head -5
# Oczekiwane: 302 → cloudflareaccess.com (potwierdza problem)
```

### 4.2 Tailscale

| Zalety | Wady |
|--------|------|
| Dostęp spoza LAN bez otwierania portów | Wymaga Tailscale na DS723 i iPhone |
| Stabilny IP `100.x.x.x` | HTTP bez TLS (akceptowalne w pilocie) |
| Zalecany dla pilotażu mobilnego | Konfiguracja początkowa |

**Rekomendacja pilotażu:** **Tailscale** jako główna ścieżka IFGM → IFG.

### 4.3 LAN

| Zalety | Wady |
|--------|------|
| Niska latencja w biurze | Brak dostępu poza siecią |
| Prosty adres IP | Wymaga bind portu 8000 poza 127.0.0.1 |
| Dobry dla testów w siedzibie | iPhone musi być w WiFi |

**Rekomendacja pilotażu:** LAN jako **środowisko testowe** w biurze; Tailscale dla użytkowników zdalnych.

### 4.4 Rekomendacja dla pilotażu

```
┌─────────────────────────────────────────────────────────┐
│  REKOMENDACJA: Tailscale + bezpośredni HTTP :8000       │
│  Unikać: publiczny URL z Cloudflare Access              │
│  Web IFG (przeglądarka): CF Access OK                    │
│  IFGM (mobile): LAN lub Tailscale IP                      │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Checklist testów pilotażowych (IFGM)

Wykonaj na iPhone połączonym z API (LAN/Tailscale). Zaznacz ✅/❌. Czas: ~45–60 min.

### 5.1 Login

| # | Test | Oczekiwany wynik |
|---|------|------------------|
| L1 | Logowanie poprawnymi danymi | Dashboard |
| L2 | Błędne hasło | Komunikat błędu, brak crasha |
| L3 | Zły URL API (CF Access) | Czytelny komunikat o Cloudflare / HTML |

### 5.2 Dashboard

| # | Test | Oczekiwany wynik |
|---|------|------------------|
| D1 | KPI: sprzedaż, zakup, VAT | Kwoty widoczne |
| D2 | KPI: dłużnicy, wierzyciele, płatności | Klikalne, poprawna nawigacja |
| D3 | Zmiana okresu (miesiąc) | Dane się odświeżają |
| D4 | Ostatnie zakupy KSeF → faktura | Szczegół FV otwiera się |

### 5.3 FV sprzedaży

| # | Test | Oczekiwany wynik |
|---|------|------------------|
| S1 | Dashboard → FV sprzedaż | Lista z miesiącem z dashboardu |
| S2 | Filtr „Częściowo” | Faktury `partially_paid` widoczne (RC-FIX) |
| S3 | Wiersz → szczegół | Kwoty brutto/zapłacono/pozostało spójne |
| S4 | Pusty okres | Komunikat „Brak faktur sprzedaży” |

### 5.4 FV zakupu

| # | Test | Oczekiwany wynik |
|---|------|------------------|
| P1 | Dashboard → FV zakup | Lista zakupów |
| P2 | Wiersz → szczegół | Kontrahent (dostawca), KSeF jeśli jest |
| P3 | Kwota na liście | Saldo (`remaining_amount`), nie brutto |

### 5.5 Dłużnicy

| # | Test | Oczekiwany wynik |
|---|------|------------------|
| DB1 | Dashboard → Dłużnicy | Lista kontrahentów |
| DB2 | Kontrahent → szczegół | Suma należności, lista FV |
| DB3 | FV z listy → szczegół | Nawigacja OK |

### 5.6 Wierzyciele

| # | Test | Oczekiwany wynik |
|---|------|------------------|
| CR1 | Dashboard → Wierzyciele | Lista kontrahentów |
| CR2 | Kontrahent → szczegół | Zobowiązania, FV |
| CR3 | FV → szczegół | Nawigacja OK |

### 5.7 Rozrachunki

| # | Test | Oczekiwany wynik |
|---|------|------------------|
| R1 | Wejście: `/settlements` (deep link / ręczna nawigacja) | Ekran ładuje się |
| R2 | Tab Należności / Zobowiązania | Dane z API |
| R3 | Wiersz → faktura | Szczegół FV |
| R4 | Karta agregatu → dłużnicy/wierzyciele | Nawigacja OK |

*Uwaga: brak linku z dashboardu do rozrachunków — znany P1, nie blokuje pilotażu jeśli tester zna trasę.*

### 5.8 Płatności nieprzypisane

| # | Test | Oczekiwany wynik |
|---|------|------------------|
| PN1 | Dashboard → Płatności | Lista transakcji |
| PN2 | Kwoty i kontrahenci | Zgodne z web IFG |
| PN3 | Pusty stan | „Brak płatności do przypisania” |

### 5.9 Przypisanie płatności

| # | Test | Oczekiwany wynik |
|---|------|------------------|
| PA1 | „Przypisz do faktury” | Modal wyszukiwania |
| PA2 | Wyszukaj FV (≥2 znaki) | Wyniki z saldem (RC-FIX) |
| PA3 | Wybierz FV | Sukces, lista odświeżona |
| PA4 | Weryfikacja w web IFG | Alokacja widoczna w systemie |

### 5.10 Zmiana przypisania

| # | Test | Oczekiwany wynik |
|---|------|------------------|
| PR1 | „Zmień przypisanie” (partial/manual_review) | Modal: stara FV |
| PR2 | Wybór nowej FV | Sukces lub czytelny błąd |
| PR3 | Weryfikacja w web IFG | Alokacja na nowej FV |

### 5.11 Testy negatywne (opcjonalnie)

| # | Test | Oczekiwany wynik |
|---|------|------------------|
| N1 | Wygasły JWT (po ~60 min) | Redirect do loginu |
| N2 | Brak sieci | Komunikat błędu + retry |

---

## 6. Kryteria sukcesu pilotażu

### 6.1 Pilot zakończony sukcesem

Wszystkie poniższe warunki spełnione przez **minimum 5 dni roboczych** użytkowania przez 1–3 użytkowników pilotażowych:

| Kryterium | Próg |
|-----------|------|
| Login mobile | 100% udanych prób w znanej sieci (LAN/Tailscale) |
| Dashboard + KPI | Dane zgodne z web IFG (± zaokrąglenia) |
| Przepływy FV (sprzedaż/zakup) | Nawigacja i kwoty poprawne |
| Dłużnicy / wierzyciele | Zgodność sum z web |
| Przypisanie płatności | Min. 3 udane alokacje bez ręcznej korekty w web |
| Zmiana przypisania | Min. 1 udany case lub świadomie pominięty (brak danych) |
| Brak utraty danych | Zero incydentów nieodwracalnych w DB |
| Dostępność API | Uptime > 95% w godzinach pracy |

### 6.2 Błędy akceptowalne w pilocie

| Błąd | Akceptacja |
|------|------------|
| Ponowne logowanie po restarcie aplikacji | Tak (brak SecureStore — P1) |
| Brak linku dashboard → rozrachunki | Tak |
| Ekran `/ksef` demo (fałszywy sync) | Tak — nie testować jako produkcja |
| Lista FV > 100 rekordów — brak starszych | Tak przy małej bazie |
| Filtr wyszukiwania wolny (>500 ms) | Tak |
| Jednorazowy błąd sieci z recovery po retry | Tak |

### 6.3 Błędy kończące pilotaż

| Błąd | Reakcja |
|------|---------|
| Błędne kwoty salda vs web IFG (systematycznie) | STOP — analiza przed kontynuacją |
| Przypisanie płatności zapisuje złą kwotę / złą FV | STOP |
| Utrata alokacji po „zmiana przypisania” bez możliwości recovery | STOP |
| 401 / brak dostępu do API dla wszystkich użytkowników > 1 h | STOP — infra |
| Regresja DB po migracji | STOP — rollback |
| Wyciek danych / dostęp bez autoryzacji | STOP — natychmiast |

---

## 7. Plan rollbacku

### 7.0 Ograniczenia rollbacku na produkcji

- **Nie używaj** `docker compose down -v` — usuwa wolumen PostgreSQL.
- **Nie resetuj** bazy produkcyjnej bez pisemnej decyzji operatora.
- `alembic downgrade` tylko gdy masz pewność co do regresji migracji; w razie wątpliwości — **restore z backupu**.
- Restore DB (`pg_restore`) — **ostateczność**, po zatrzymaniu api/worker.

### 7.1 Kiedy przerwać pilotaż

- Kryteria z sekcji 6.3,
- `alembic upgrade` spowodował regresję,
- API unhealthy > 15 min po deployu,
- Decyzja operatora po ≥ 3 identycznych błędach krytycznych w ciągu 24 h.

### 7.2 Rollback backendu IFG

```bash
cd /volume1/docker/ifg_v2/ifg_standalone

# 1. Wróć do poprzedniego commita
git checkout PREVIOUS_SHA

# 2. Frontend (jeśli był rebuild)
cd frontend-react
npm run build
cd ..
# Jeżeli zmieniły się zależności npm, przed buildem wykonaj: npm ci

# 3. Rebuild kontenerów
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  up -d --build --force-recreate api worker

# 4. Rollback migracji (TYLKO jeśli nowa migracja była przyczyną — ostrożnie)
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec api alembic downgrade -1
# lub restore z backupu (preferowane przy poważnej regresji)

# 5. Restore DB z backupu (OSTATECZNOŚĆ — tylko po backupie i zatrzymaniu api/worker)
docker compose -f docker/docker-compose.prod.yml --env-file .env.production stop api worker
docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T db \
  pg_restore -U postgres -d ksef_backend --clean --if-exists \
  < /volume1/docker/ifg_v2/backups/ksef_backend_YYYYMMDD_HHMMSS.dump
docker compose -f docker/docker-compose.prod.yml --env-file .env.production start api worker
```

### 7.3 Rollback IFGM

IFGM nie jest deployowany na DS723 — rollback = powrót użytkowników do poprzedniej wersji:

- Expo Go: checkout poprzedniego commita + restart z poprzednim `EXPO_PUBLIC_API_BASE_URL`,
- Dev build: reinstalacja poprzedniego builda TestFlight.

**Brak wpływu rollbacku mobile na dane serwerowe** (mobile tylko czyta/zapisuje przez API).

### 7.4 Weryfikacja po rollbacku

| # | Test | Oczekiwany wynik |
|---|------|------------------|
| V1 | `curl http://127.0.0.1:8000/health` | 200 |
| V2 | Login web `/ui` | OK |
| V3 | `alembic current` | Zgodne z rollback commit |
| V4 | Login IFGM + dashboard | OK |
| V5 | Porównanie KPI dashboard web vs mobile | Zgodność |
| V6 | Liczba alokacji płatności w DB | Bez nieoczekiwanych zmian |

---

## Załącznik A — pozostałe P1 po RC-FIX (świadomie otwarte)

| ID | Opis | Wpływ na pilotaż |
|----|------|------------------|
| P1-2 | Brak linku dashboard → rozrachunki | Niski — deep link |
| P1-3 | Sesja JWT w pamięci | Średni — re-login |
| P1-4 | Reassign bez transakcji atomowej | Niski przy ostrożnym teście |
| P1-5 | Paginacja 100/200 | Niski przy małej bazie |
| P1-6 | KSeF mobile = demo | Brak — nie testować |
| P1-8 | Brak testów routera płatności | Niski — testy serwisu OK |

## Załącznik B — dokumenty powiązane

| Dokument | Ścieżka |
|----------|---------|
| Checklist DS723 | `docs/DS723_DEPLOYMENT_CHECKLIST.md` |
| RC Audit | `mobile-expo/docs/IFGM_RELEASE_CANDIDATE_AUDIT.md` |
| RC Fixes | `mobile-expo/docs/IFGM_RC_FIXES.md` |
| Cloudflare Access | `mobile-expo/docs/REPORT_CLOUDFLARE_ACCESS.md` |
| Spec IFGM | `docs/IFGM_SPEC_V1.md` |

---

*IFGM Pilot Deployment Plan — G2, wersja 1.1*
