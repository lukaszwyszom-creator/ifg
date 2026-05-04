1. Przygotowanie serwera DS723+
1. Zainstaluj i uruchom Container Manager (Docker) na DSM.
2. Włącz SSH w DSM: Panel sterowania -> Terminal i SNMP.
3. Zaloguj się przez SSH i przygotuj katalogi:
   $ mkdir -p /volume1/docker/ifg
   $ mkdir -p /volume1/docker/ifg/postgres_data
   $ mkdir -p /volume1/docker/ifg/logs
4. Ustaw właściciela i prawa:
   $ sudo chown -R admin:users /volume1/docker/ifg
   $ sudo chmod -R 750 /volume1/docker/ifg
5. Sprawdź Docker:
   $ docker --version
   $ docker compose version

2. Przygotowanie repo
1. Umieść kod w:
   /volume1/docker/ifg/ifg_standalone
2. Skopiuj repo:
   $ cd /volume1/docker/ifg
   $ git clone REPO_URL ifg_standalone
   $ cd ifg_standalone
3. Wymagane pliki:
   - docker/docker-compose.prod.yml
   - docker/Dockerfile
   - alembic.ini
   - katalog alembic
   - katalog app
4. Nie kopiuj/nie commituj sekretów:
   - .env.example i .env.production.template służą tylko jako wzór
   - używaj lokalnego pliku .env.production na serwerze
5. Opcjonalnie przypnij konkretny commit:
   $ git checkout BRANCH_LUB_TAG

3. Konfiguracja .env.production
1. Utwórz plik:
   $ cd /volume1/docker/ifg/ifg_standalone
   $ cp .env.production.template .env.production
2. Uzupełnij minimalnie wymagane:
   - APP_ENV=production
   - DEBUG=false
   - DATABASE_URL=postgresql+psycopg://postgres:SILNE_HASLO@db:5432/ksef_backend
   - POSTGRES_DB=ksef_backend
   - POSTGRES_USER=postgres
   - POSTGRES_PASSWORD=SILNE_HASLO
   - JWT_SECRET_KEY=LOSOWY_KLUCZ_MIN_32_ZNAKI
   - JWT_ALGORITHM=HS256
   - ACCESS_TOKEN_EXPIRE_MINUTES=60
   - INITIAL_ADMIN_USERNAME=admin
   - INITIAL_ADMIN_PASSWORD=SILNE_HASLO_ADMINA
   - SELLER_NIP=1234567890
   - SELLER_NAME=Twoja Firma Sp z o o
   - SELLER_STREET=Przykladowa
   - SELLER_BUILDING_NO=1
   - SELLER_POSTAL_CODE=00-001
   - SELLER_CITY=Warszawa
   - SELLER_COUNTRY=PL
   - KSEF_ENVIRONMENT=test
   - KSEF_AUTH_TOKEN=TOKEN_SANDBOX
   - KSEF_TIMEOUT_SECONDS=30
   - REGON_ENVIRONMENT=production
   - REGON_API_KEY=KLUCZ_REGON
   - REQUEST_TIMEOUT_SECONDS=15
   - ENABLE_KSEF=true
   - ENABLE_WAREHOUSE=true
   - ENABLE_PAYMENTS=true
3. Krytyczne zmienne (bez nich start/funkcje będą błędne):
   - DATABASE_URL
   - POSTGRES_PASSWORD
   - JWT_SECRET_KEY
   - INITIAL_ADMIN_PASSWORD
   - KSEF_AUTH_TOKEN
   - SELLER_NIP
4. Ustaw prawa do pliku:
   $ chmod 600 .env.production

4. Uruchomienie kontenerów
1. Zbuduj i uruchom:
   $ cd /volume1/docker/ifg/ifg_standalone
   $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d --build
2. Sprawdź status:
   $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production ps

5. Migracje
1. Wykonaj migracje ręcznie w kontenerze api:
   $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec api alembic upgrade head
2. Sprawdź aktualną wersję:
   $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec api alembic current
3. Podejrzyj historię:
   $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec api alembic history --verbose

6. Weryfikacja działania
1. Healthcheck API:
   $ curl -fsS http://127.0.0.1:8000/health
2. Logi:
   $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs -f api
   $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs -f worker
   $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs -f db
3. Połączenie z DB:
   $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec db pg_isready -U postgres -d ksef_backend
4. Front przez backend:
   - otwórz http://IP_DS723:8000/ui

7. Test funkcjonalny
1. Logowanie:
   - zaloguj się kontem admin z INITIAL_ADMIN_USERNAME i INITIAL_ADMIN_PASSWORD
2. Kontrahent z REGON:
   - wyszukaj/utwórz kontrahenta po NIP i potwierdź pobranie danych
3. Utwórz fakturę sprzedaży:
   - zapisz fakturę z poprawnym NIP sprzedawcy zgodnym z KSEF tokenem
4. Otwórz sesję KSeF:
   - w UI lub przez endpoint sesji KSeF
5. Wyślij fakturę do KSeF sandbox:
   - uruchom submit faktury
6. Sprawdź status transmisji:
   - oczekiwane przejścia: queued -> processing -> submitted -> waiting_status -> success
7. Potwierdź numer KSeF i UPO:
   - transmisja/faktura ma mieć zapisany numer referencyjny KSeF
   - UPO powinno być pobrane po sukcesie

8. Lista typowych problemów i ich diagnoza
1. Brak DATABASE_URL
   - Objaw: api nie startuje lub błąd konfiguracji.
   - Diagnostyka:
     $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs api | grep DATABASE_URL
   - Naprawa: uzupełnij DATABASE_URL w .env.production i restart:
     $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
2. Brak migracji
   - Objaw: błędy typu relation does not exist.
   - Diagnostyka: alembic current i logi api.
   - Naprawa:
     $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec api alembic upgrade head
3. Brak KSeF tokena
   - Objaw: błąd otwarcia sesji KSeF/autoryzacji.
   - Diagnostyka: logi api/worker, sprawdź KSEF_AUTH_TOKEN i KSEF_ENVIRONMENT.
   - Naprawa: ustaw poprawny token sandbox i restart api+worker:
     $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production restart api worker
4. Worker nie działa
   - Objaw: transmisje stoją w queued/submitted bez postępu.
   - Diagnostyka:
     $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production ps
     $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs worker
   - Naprawa:
     $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production restart worker
5. API nie odpowiada
   - Objaw: /health timeout lub 5xx.
   - Diagnostyka:
     $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production ps
     $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs api
     $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs db
   - Naprawa: popraw .env.production, DB credentials, wykonaj migracje, restart stack:
     $ docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d
