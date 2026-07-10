# GWO-IFG-0051 — Redesign Monitora KSeF (UX + grupowanie + szczegóły)

**Data:** 2026-07-08  
**Status:** DONE (implementacja frontend + testy jednostkowe)  
**Deploy:** nie wykonywano w tym zadaniu

---

## Opis zmian

Monitor KSeF został przebudowany z płaskiej tabeli technicznej (12 kolumn, poziomy scroll) na **widok procesów operatorskich** z rozwijaną diagnostyką.

### 1. Grupowanie procesów

- Wpisy grupowane po `correlation_id` (fallback: `job_id`, pojedynczy wiersz).
- Widok zwinięty: znacznik, nazwa procesu, status, liczba faktur, czas, liczba etapów.
- Widok rozwinięty: lista etapów (SESSION_REFRESH, PURCHASE_* …), faktury, pełna diagnostyka techniczna.

### 2. Brak poziomego scrolla

- Zastąpiono generyczną tabelę `Table` (overflow-x: auto) kompaktowym layoutem CSS Grid.
- Kolumny główne: Znacznik, Proces, Status, Faktury, Czas, Akcje.
- Pola techniczne (Correlation, Job, Retry, Severity, Metadata, Ref KSeF) przeniesione do sekcji szczegółów.

### 3. Lista faktur

- Faktury wyciągane z wierszy grupy (`invoice_id` / `invoice_number_local`).
- Deduplikacja w obrębie procesu.
- Podsumowanie: „12 faktur” lub numer pojedynczej faktury.

### 4. Tooltip kontrahenta

- Hover na numerze faktury pokazuje tooltip z danych już obecnych w wierszu (`metadata_json`, `ksef_reference_number`, status, data).
- **Bez dodatkowych zapytań API** przy hoverze.

### 5. Correlation / Job / Retry

- Usunięte z widoku głównego.
- Widoczne w rozwiniętych kartach diagnostycznych każdego etapu.

### 6. Podsumowanie procesu

- Komponent `TransmissionSummary`: sukces/błąd, liczba faktur, czas trwania, etapy, ostrzeżenia, UPO/KSeF.

### 7. Zachowanie diagnostyki

- Wszystkie dane techniczne zachowane w `TransmissionDetails` (severity, status, próby, correlation, job, błędy, metadata JSON).

---

## Architektura

```
TransmissionTable.jsx (kontener: fetch, polling, paginacja)
├── transmissionUtils.js          # grupowanie, etykiety, podsumowania
├── TransmissionGroup.jsx         # wiersz zwinięty / rozwinięty
├── TransmissionSummary.jsx       # podsumowanie procesu
├── TransmissionDetails.jsx       # etapy + faktury + diagnostyka
├── TransmissionInvoiceTooltip.jsx
└── TransmissionMonitor.module.css
```

**Kluczowe funkcje (`transmissionUtils.js`):**

| Funkcja | Rola |
|---------|------|
| `groupTransmissions()` | Grupowanie po correlation/job |
| `deriveProcessTitle()` | Nazwa procesu (zakupy/sprzedaż/sesja) |
| `aggregateGroupStatus()` | Status grupy (SUKCES/BŁĄD/W TOKU) |
| `extractInvoicesFromRows()` | Lista faktur w procesie |
| `summarizeGroup()` | Metryki: etapy, czas, ostrzeżenia |

**Grupowanie:** `correlation_id` → `job_id` → pojedynczy wiersz.

---

## Lista zmodyfikowanych plików

### Nowe

- `frontend-react/src/components/dashboard/transmissions/transmissionUtils.js`
- `frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js`
- `frontend-react/src/components/dashboard/transmissions/TransmissionGroup.jsx`
- `frontend-react/src/components/dashboard/transmissions/TransmissionSummary.jsx`
- `frontend-react/src/components/dashboard/transmissions/TransmissionDetails.jsx`
- `frontend-react/src/components/dashboard/transmissions/TransmissionInvoiceTooltip.jsx`
- `frontend-react/src/components/dashboard/transmissions/TransmissionMonitor.module.css`

### Zmodyfikowane

- `frontend-react/src/components/dashboard/TransmissionTable.jsx` — przebudowa na widok grupowy

### Bez zmian backend

- API `/api/v1/transmissions/` — bez modyfikacji (zgodnie z założeniem UX-only).

---

## Wyniki testów

```bash
node --test frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js
# 7/7 PASS

cd frontend-react && npm run build
# SUCCESS
```

**Pokrycie testami:**

| Obszar | Test |
|--------|------|
| Grupowanie | `groupTransmissions grupuje po correlation_id` |
| Sprzedaż / zakupy | `deriveProcessTitle rozpoznaje sprzedaż i zakupy` |
| Status grupy | `aggregateGroupStatus` |
| Faktury | `extractInvoicesFromRows deduplikuje` |
| Podsumowanie | `invoicesSummaryLabel` |
| Wydajność | 500 wierszy → 25 grup < 100ms |

**Testy manualne (do wykonania przez operatora po deploy):**

- brak poziomego scrolla na desktopie,
- responsywność mobile,
- tooltip na numerze faktury,
- filtr „Tylko błędy i ostrzeżenia”,
- odświeżanie / polling.

---

## Znane ograniczenia

1. **Grupowanie w obrębie strony paginacji** — API zwraca płaską listę (20/strona); proces rozciągnięty na wiele stron może być podzielony wizualnie.
2. **Dane kontrahenta w tooltipie** — API transmisji nie zwraca NIP/kwoty/nabywcy bezpośrednio; tooltip korzysta z `metadata_json` i pól wiersza. Pełne dane wymagają rozszerzenia API (np. snapshot kontrahenta w `TransmissionResponse`).
3. **Liczba faktur w sync zakupów** — gdy brak `invoice_id` w etapach pośrednich, używana jest suma `metadata_json.saved` z etapów grupy.
4. **Stary plik CSS** `TransmissionTable.module.css` — pozostaje w repo (niewykorzystany); można usunąć w housekeeping.

---

## Propozycje dalszego rozwoju

1. **Backend:** rozszerzyć `TransmissionResponse` o `invoice_snapshot` (nabywca, NIP, kwota, kierunek) — eliminuje ograniczenie tooltipu.
2. **API:** opcjonalne grupowanie server-side po `correlation_id` z paginacją po grupach.
3. **UX:** filtr po typie procesu (zakupy / sprzedaż / sesja).
4. **Guardian:** dodać smoke test UI Monitora KSeF w workflow post-deploy.
5. **GWO-Guardian:** ujednolicić ścieżki backupu (z GWO-0049).

---

## 🩷 STATUS KOŃCOWY

### ✅ CO DZIAŁA

- Grupowanie procesów po correlation/job.
- Kompaktowy widok bez poziomego scrolla.
- Rozwijana pełna diagnostyka.
- Tooltip faktury bez dodatkowych requestów.
- Testy jednostkowe 7/7 PASS.
- `npm run build` PASS.

### ⚠️ ZNANE PROBLEMY

- Ograniczone dane kontrahenta w API (patrz wyżej).
- Grupowanie tylko w ramach bieżącej strony.

### ❌ CO NIE DZIAŁA

- Brak — implementacja frontend kompletna w scope zadania.

## A. ROOT CAUSE (motywacja)

Poprzedni monitor był dziennikiem technicznym (12 kolumn), nieoperacyjnym dla użytkownika i wymuszał poziomy scroll.

## B. ZMIENIONE PLIKI

Patrz sekcja „Lista zmodyfikowanych plików”.

## C. DEPLOY

Nie wykonano — wymaga osobnego wdrożenia frontendu.

## D. TESTY

7/7 unit + build PASS.

## E. NASTĘPNY KROK

Deploy frontendu (`npm run build` + rsync) i weryfikacja Monitora KSeF w przeglądarce po logout/login.

---

## Lista wygenerowanych raportów `.md`

1. `docs/reports/2026-07-08_GWO-IFG-0051_KSEF_MONITOR_REDESIGN.md`
