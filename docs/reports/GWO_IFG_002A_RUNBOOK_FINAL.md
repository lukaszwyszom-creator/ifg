# GWO-IFG-002A — Runbook final (Container Manager cutover)

**Data:** 2026-07-06  
**GWO:** GWO-IFG-002A  
**Status:** **DOKUMENTACJA GOTOWA** — migracja **nie wykonana**

---

## 1. Co zmieniono

| Dokument | Zmiana |
|----------|--------|
| [GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md](./GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md) | RECOMMENDED CUTOVER: usunięto `docker rm` przed Start; dodano kroki Guardian + test funkcjonalny; sprzątanie na końcu |
| [IFG_CONTAINER_MANAGER_MIGRATION.md](./IFG_CONTAINER_MANAGER_MIGRATION.md) | Fazy migracji 3–7; rollback wykorzystuje zachowane `docker-*`; checklist §9; link do runbooka |
| [RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md](../runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md) | **Nowy** — autorytatywny runbook produkcyjny |
| Ten raport | Podsumowanie i werdykt gotowości |

### Poprawka zaakceptowana (GWO-IFG-002B review)

**Było (błędne):** `docker rm docker-*` **przed** Start projektu `ifg`.

**Jest (poprawne):** kontenery `docker-api-1`, `docker-worker-1`, `docker-db-1` **pozostają** do pełnej walidacji — stanowią **najszybszy rollback**.

**Nowa kolejność:**

1. Backup  
2. git pull  
3. compose config  
4. Start projektu ifg  
5. Health  
6. Guardian verify  
7. Test funkcjonalny IFG  
8. **Dopiero po pełnej walidacji:** `docker rm docker-*`

---

## 2. Dlaczego

| Powód | Wyjaśnienie |
|-------|-------------|
| **Rollback time** | Przy zachowanych `docker-*` rollback = `stop ifg` + `up -p docker` + stary compose — bez odtwarzania kontenerów od zera |
| **Ryzyko operacyjne** | Wcześniejsze `docker rm` nie daje korzyści (Exited nie blokuje Start — różne prefiksy `docker-` vs `ifg-`) |
| **Spójność z analizą CM** | Scenariusz B (recreate) — stare kontenery to orphans do czasu sprzątania, nie przeszkoda przy Exited |
| **Gate jakości** | Guardian verify + test funkcjonalny przed nieodwracalnym usunięciem rollback asset |

---

## 3. Końcowa rekomendacja

| Aspekt | Werdykt |
|--------|---------|
| Compose prep w repo | ✅ Gotowe (`9505adc`) |
| Analiza CM (002B) | ✅ Zaakceptowana z poprawką runbooka |
| Runbook produkcyjny | ✅ **APPROVED** |
| Migracja wykonana | ❌ Nie — oczekuje operatora |
| Push compose prep na DS723+ | ⏳ Operator: `git push` + `git pull` na DS723+ przed cutover |

**Wykonanie cutover:** wyłącznie według [RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md](../runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md).

**Scenariusz CM:** **B** — recreate kontenerów z istniejącymi wolumenami (external pin). **Nie** adoptacja (A).

---

## 4. Gotowość do wykonania migracji

| Kryterium | Status |
|-----------|--------|
| Dokumentacja operacyjna kompletna | ✅ |
| Runbook STATUS: APPROVED | ✅ |
| Backup procedure zdefiniowana | ✅ |
| Rollback procedure (z `docker-*`) | ✅ |
| Gate compose config | ✅ |
| Checklist operatora | ✅ |
| Kod / deploy / compose up / SSH DS723+ w tej sesji | ❌ Nie wykonano (zgodnie z zakresem) |

### Werdykt gotowości

**GOTOWE DO WYKONANIA MIGRACJI** przez operatora po:

1. Push commitu compose prep na `production` (jeśli jeszcze nie na remote/DS723+).
2. Oknie maintenance / akceptacja operatora.
3. Wykonanie runbooka krok po kroku.

**NO-GO** bez backupu SQL i bez gate compose config.

---

## 5. Pliki w scope GWO-IFG-002A (dokumentacja)

```
docs/runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md          ← APPROVED runbook
docs/reports/GWO_IFG_002A_COMPOSE_PROJECT_PREP.md
docs/reports/GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md        ← zaktualizowany
docs/reports/IFG_CONTAINER_MANAGER_MIGRATION.md                 ← zaktualizowany
docs/reports/GWO_IFG_002A_RUNBOOK_FINAL.md                        ← ten raport
docker/docker-compose.prod.yml                                  ← prep (commit 9505adc)
```

---

*Sesja dokumentacyjna zakończona. Brak operacji na DS723+.*
