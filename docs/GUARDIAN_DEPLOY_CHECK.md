# Guardian — kontrola wdrożenia Mac mini → DS723+

Data: 2026-05-22

## Cel

Tryb `--deploy-check` w `scripts/guardian.py` odpowiada na pytanie: **czy produkcja na DS723+ jest zgodna z lokalnym kodem na Mac mini?**

Guardian **tylko czyta stan** — nie wdraża, nie restartuje, nie modyfikuje repo ani kontenerów.

## Uruchomienie

```bash
# Pełna kontrola wdrożenia (Mac mini + DS723+ przez SSH)
python3 scripts/guardian.py --deploy-check

# Pomoc (wszystkie tryby)
python3 scripts/guardian.py --help

# Opcjonalnie: inny host SSH
IFG_DS723_HOST=192.168.1.50 python3 scripts/guardian.py --deploy-check

# lub
python3 scripts/guardian.py --deploy-check --remote-host ds723
```

## Co sprawdza

### Lokalnie (Mac mini)

| Sprawdzenie | Komenda git |
|-------------|-------------|
| Branch | `git branch --show-current` |
| Commit | `git rev-parse HEAD` |
| Working tree | `git status --short` |

### Zdalnie (DS723+ przez SSH)

Host: `ds723` lub `IFG_DS723_HOST`  
Ścieżka: `/volume1/docker/ifg_v2/ifg_standalone`

| Sprawdzenie | Komenda |
|-------------|---------|
| Branch | `git branch --show-current` |
| Commit | `git rev-parse HEAD` |
| Working tree | `git status --short` |
| Kontenery | `sudo docker compose -f docker/docker-compose.prod.yml ps` |

Wymagane serwisy: **api**, **worker**, **db** (stan `running` / `Up`).

## Format raportu

```
✅ branch zgodny / ❌ branch różny
✅ commit zgodny / ❌ commit różny
✅ repo clean / ⚠️ są lokalne zmiany
✅ kontenery działają / ❌ problem z api/worker/db
```

### Werdykt końcowy

| Werdykt | Warunki |
|---------|---------|
| **PRODUKCJA ZGODNA Z LOKALNYM KODEM** | SSH OK, branch i commit zgodne, api/worker/db działają |
| **PRODUKCJA NIEZGODNA — WYMAGANY DEPLOY** | SSH OK, ale branch/commit różne lub problem z kontenerami |
| **NIE MOŻNA POTWIERDZIĆ — BRAK SSH / BŁĄD UPRAWNIEŃ** | Brak połączenia SSH, brak uprawnień sudo/docker, błąd odczytu repo |

Uwaga: niezatwierdzone zmiany lokalne (`⚠️ są lokalne zmiany`) **nie blokują** werdyktu ZGODNA, jeśli **HEAD** lokalny = HEAD na DS723+ i kontenery działają. Ostrzeżenie informuje, że working tree różni się od commita.

## Czego Guardian NIE robi

- ❌ `git pull` / `git fetch` (w trybie `--deploy-check`)
- ❌ restart kontenerów
- ❌ `docker compose up` / `down`
- ❌ usuwanie wolumenów
- ❌ modyfikacja bazy danych
- ❌ wdrożenie / deploy jakiegokolwiek kodu

## Powiązane tryby

| Flaga | Opis |
|-------|------|
| *(domyślnie)* | Zgodność endpointów mobile-expo ↔ backend |
| `--deploy-check` | Mac mini vs DS723+ (git + kontenery) |
| `--repo-sync [--remote ds723] [--fetch]` | Mac mini vs origin/production vs DS723+ (tylko git) |

## Wymagania

- Lokalnie: repozytorium git w katalogu projektu
- DS723+: skonfigurowany SSH (`ssh ds723`), dostęp do repo i `sudo docker compose ps`
- Kod wyjścia: `0` = zgodna produkcja, `1` = niezgodna lub błąd potwierdzenia

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `scripts/guardian.py` | Tryb `--deploy-check`, rozszerzone `--help`, `IFG_DS723_HOST` |
| `docs/GUARDIAN_DEPLOY_CHECK.md` | Ten dokument |
