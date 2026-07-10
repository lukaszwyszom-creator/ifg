# GWO-IFG-0051A — Ujednolicenie strategii grupowania procesów Monitora KSeF

**Data:** 2026-07-08  
**Status:** DONE  
**Zakres:** wyłącznie architektura frontend (bez zmian backend/API/wyglądu)

---

## Opis zmian

Zastąpiono rozproszoną logikę `groupKeyForRow()` (correlation → job → row) centralną funkcją **`deriveProcessKey(row)`**.

### Nowa kolejność wyboru klucza procesu

1. `job_id`
2. `correlation_id`
3. `marker` / `transmission_marker` / `batch_marker` (top-level lub `metadata_json`)
4. `transmission_id` / `id`
5. fallback: pojedynczy rekord (`row:{id}`)

### Gdzie jest logika

- **Jedyny punkt grupowania:** `transmissionUtils.js`
  - `pickMarkerValue()` — prywatny helper markerów
  - `deriveProcessKey()` — strategia klucza
  - `groupTransmissions()` — budowa gotowych grup
- **Komponenty UI** (`TransmissionGroup`, `TransmissionTable`, …) otrzymują gotowe grupy i nie znają reguł grupowania.

### Usunięte

- `groupKeyForRow()` — zastąpione przez `deriveProcessKey()`

---

## Zmodyfikowane pliki

| Plik | Zmiana |
|------|--------|
| `frontend-react/src/components/dashboard/transmissions/transmissionUtils.js` | `deriveProcessKey`, nowa strategia, usunięcie `groupKeyForRow` |
| `frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js` | 16 testów (było 7) |

**Bez zmian:** backend, API, komponenty wizualne, CSS Monitora.

---

## Uzasadnienie nowej strategii

| Aspekt | Uzasadnienie |
|--------|--------------|
| **job_id pierwszy** | Partie worker/scheduler i sync zakupów naturalnie grupują się po zadaniu w tle |
| **correlation_id drugi** | Łańcuchy logiczne KSeF (np. submit → poll → UPO) bez wspólnego job |
| **markery trzeci** | Przyszłe źródła zdarzeń mogą dostarczać batch_marker bez UUID job/corr |
| **transmission_id / id** | Stabilny fallback gdy brak identyfikatorów procesowych |
| **Jedna funkcja** | Zmiana strategii w jednym miejscu — odporność na ewolucję backendu |

**Zmiana względem GWO-0051:** priorytet `job_id` > `correlation_id` (wcześniej odwrotnie). Wpływ: wpisy z oboma polami grupują się po job (np. sync batch), nie po correlation.

---

## Wyniki testów

```bash
node --test frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js
# 16/16 PASS

cd frontend-react && npm run build
# SUCCESS
```

### Nowe przypadki testowe

| Test | Scenariusz |
|------|------------|
| `deriveProcessKey preferuje job_id nad correlation_id` | Oba pola → klucz `job:*` |
| `deriveProcessKey używa correlation_id gdy brak job_id` | Tylko correlation |
| `deriveProcessKey używa marker gdy...` | marker top-level i w metadata |
| `deriveProcessKey używa transmission_id lub id` | Fallback tx |
| `deriveProcessKey jest stabilny` | Idempotencja |
| `groupTransmissions grupuje po job_id gdy oba...` | Grupowanie job |
| `groupTransmissions grupuje po correlation_id...` | Grupowanie corr |
| `groupTransmissions grupuje po markerze...` | Grupowanie marker |
| `groupTransmissions tworzy pojedyncze grupy...` | Brak wspólnych kluczy |
| `groupTransmissions obsługuje mieszane rekordy` | Mix strategii w jednej liście |
| Wydajność 500 wierszy | < 100ms, 25 grup |

---

## Wpływ na kompatybilność

| Obszar | Wpływ |
|--------|-------|
| **API / backend** | Brak — bez zmian |
| **Wygląd Monitora** | Brak — te same komponenty i CSS |
| **Dane historyczne z job_id** | Grupy mogą być inne niż w GWO-0051 (job beats correlation) — semantycznie poprawniejsze dla batchy |
| **Dane tylko z correlation_id** | Zachowanie jak wcześniej |
| **Przyszłe markery** | Gotowe bez zmiany komponentów |
| **TransmissionDetails** | Nadal wyświetla correlation/job w diagnostyce (nie grupowanie) |

---

## 🩷 STATUS KOŃCOWY

### ✅ CO DZIAŁA

- Centralna strategia `deriveProcessKey()` w `transmissionUtils`
- Komponenty odseparowane od logiki grupowania
- 16/16 testów PASS, build PASS

### ⚠️ ZNANE PROBLEMY

- Zmiana priorytetu job vs correlation może rozdzielić grupy, które wcześniej były scalone po correlation (gdy oba pola różnią się semantycznie)

### ❌ CO NIE DZIAŁA

- Brak

## E. NASTĘPNY KROK

Deploy frontendu razem z GWO-0051 lub osobno; weryfikacja grupowania na produkcji (sync zakupów vs wysyłka sprzedaży).

---

## Lista wygenerowanych raportów `.md`

1. `docs/reports/2026-07-08_GWO-IFG-0051A_PROCESS_GROUPING_STRATEGY.md`
