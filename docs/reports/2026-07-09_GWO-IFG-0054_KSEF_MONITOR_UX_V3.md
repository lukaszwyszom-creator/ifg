# GWO-IFG-0054 — Monitor KSeF UX v3 (ergonomia operatora)

**Data:** 2026-07-09  
**Status:** DONE (implementacja + testy; deploy nie wykonano w tym zadaniu)

---

## Cel

Domknięcie ergonomii Monitora KSeF po pierwszych testach produkcyjnych — ostatnia iteracja UX przed dłuższym okresem użytkowania. Bez przebudowy architektury.

---

## Opis zmian

### 1. Data i czas (prezentacja „ludzka”)

Nowa funkcja `formatOperatorDateTime()` zwraca obiekt `{ dateLine, timeLine }`:

| Odległość | Przykład `dateLine` | `timeLine` |
|-----------|---------------------|------------|
| Dzisiaj | `Dzisiaj (czwartek)` | `14:00` |
| Wczoraj | `Wczoraj (środa)` | `09:12` |
| Starsze | `07.07.2026 (wtorek)` | `18:44` |

- Dzień tygodnia zawsze słownie po polsku.
- Kolumna „Czas” w nagłówku grupy pokazuje datę i godzinę w dwóch liniach (`dateLine` / `timeLine`).
- Etapy w `TransmissionDetails` używają tego samego formatu.

### 2. Podsumowanie procesu (efekt przed techniką)

`buildSummaryLines()` zwraca teraz strukturę `{ status, effects, meta }` zamiast płaskiej tablicy stringów:

**Zwinięty wiersz** (`buildProcessSummaryMeta`):
```
12 nowych faktur · czas 5 s · 4 etapy
```

**Rozwinięte podsumowanie** (`TransmissionSummary`):
```
📥 Synchronizacja zakupów
✔ Sukces
12 nowych faktur
czas 5 s · 4 etapy
```

Dla sprzedaży efekt to numer FV i „UPO odebrane” — liczba etapów i czas trwania schodzą na drugi plan (`meta`).

### 3. Tooltip faktury

- `invoiceHasTooltipDetails()` — weryfikuje, czy snapshot ma wystarczające dane (numer + kontrahent/NIP/kwota/KSeF).
- `buildInvoiceSnapshot()` ustawia flagę `hasDetails: true/false`.
- Gdy brak danych: stały komunikat `Brak szczegółów faktury dla tego wpisu dziennika.` — **nigdy pusty tooltip**.
- Pełny tooltip: numer, nabywca/sprzedawca, NIP, kwota brutto, data, numer KSeF, status.

### 4. Ikony procesów

`deriveProcessIcon(title, status)` — subtelne emoji w nagłówku grupy i podsumowaniu:

| Typ | Ikona |
|-----|-------|
| Synchronizacja zakupów | 📥 |
| Wysyłka sprzedaży | 📤 |
| Sesja KSeF | 🔐 |
| Harmonogram | ⏰ |
| Błąd (status) | ❌ |
| Ostrzeżenie (status) | ⚠ |
| Inne | • |

Ikony nie zastępują kolumny statusu — są pomocą przy skanowaniu listy (`opacity: 0.85–0.9`).

### 5. Kolory statusów

Pigułki statusu (`.statusPill`) z kolorami semantycznymi:

| Status | Kolor | Etykieta |
|--------|-------|----------|
| Sukces | zielony (`--color-success`) | ✔ Sukces |
| Ostrzeżenie | pomarańczowy (`--color-warning`) | ⚠ Ostrzeżenia |
| Błąd | czerwony (`--color-error`) | ✖ Błąd |
| W toku | niebieski (`--color-info`) | ◌ W toku |

Tło pigułki: `color-mix` ~14–16% koloru statusu — rozpoznawalne bez czytania tekstu.

### 6. Czytelność

- Zwiększone odstępy wierszy (`padding` nagłówka grupy, `line-height` metadanych).
- Dwuliniowy czas — lepsze wyrównanie kolumny daty.
- `processMeta` z `word-break: break-word` — długie podsumowania nie rozpychają siatki.
- Test wydajności: `groupTransmissions` na 100 wierszach — OK (< 2 ms).

### 7. Responsywność

- `overflow-x: hidden` na kontenerze monitora — brak poziomego scrollbara.
- Breakpointy: `1024px` (laptop), `720px` (tablet/mobile) — siatka przechodzi na układ dwukolumnowy, kolumny statusu/faktur/czasu pod procesem.
- `minmax()` w `grid-template-columns` — elastyczne kolumny bez przepełnienia.

---

## Zmodyfikowane pliki

| Plik | Zakres zmian |
|------|--------------|
| `frontend-react/src/components/dashboard/transmissions/transmissionUtils.js` | `formatOperatorDateTime`, `deriveProcessIcon`, `buildSummaryLines` (struktura), `invoiceHasTooltipDetails`, `TOOLTIP_EMPTY_MESSAGE`, `dateTimeParts` w `groupTransmissions` |
| `frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js` | +6 testów v3, aktualizacja `buildSummaryLines` |
| `frontend-react/src/components/dashboard/transmissions/TransmissionGroup.jsx` | ikony, pigułki statusu, dwuliniowy czas |
| `frontend-react/src/components/dashboard/transmissions/TransmissionSummary.jsx` | efekt-first summary z ikoną procesu |
| `frontend-react/src/components/dashboard/transmissions/TransmissionInvoiceTooltip.jsx` | empty-state message |
| `frontend-react/src/components/dashboard/transmissions/TransmissionDetails.jsx` | operator datetime na etapach |
| `frontend-react/src/components/dashboard/transmissions/TransmissionMonitor.module.css` | spacing, status pills, responsive breakpoints, tooltip empty style |

**Backend:** bez zmian w tym zadaniu (pole `invoice_snapshot` z GWO-IFG-0053).

---

## Wyniki testów

### Unit tests

```bash
node --test frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js
```

```
ℹ tests 19
ℹ pass 19
ℹ fail 0
```

Nowe testy v3:
- `formatOperatorDateTime używa Dzisiaj i Wczoraj`
- `deriveProcessIcon rozpoznaje typ procesu`
- `invoiceHasTooltipDetails wykrywa brak danych`
- `buildProcessSummaryMeta kończy się etapami`
- zaktualizowany `buildSummaryLines pokazuje efekt procesu sprzedaży` (struktura `{ effects, meta }`)

### Build frontendu

```bash
cd frontend-react && npm run build
```

```
✓ built in 1.32s
```

### Guardian

Nie uruchamiano — brak nowych endpointów API; zmiany wyłącznie frontendowe.

---

## UX Review (test operatora 5 sekund)

> Gdybym był operatorem IFG, czy potrafiłbym w ciągu 5 sekund odpowiedzieć na pytania:

| Pytanie | Odpowiedź | Dowód w UI |
|---------|-----------|------------|
| **Czy synchronizacja się udała?** | **TAK** | Kolorowa pigułka (zielona = sukces) + etykieta `✔ Sukces` w kolumnie statusu; ikona 📥 przy nazwie procesu |
| **Ile faktur pobrano?** | **TAK** | Kolumna „Faktury”: `12 nowych`; zwinięte meta: `12 nowych faktur`; rozwinięte: osobna linia efektu |
| **Jakiej firmy dotyczy faktura?** | **CZĘŚCIOWO** | Tooltip po najechaniu pokazuje nabywcę/sprzedawcę i NIP. W zwiniętym wierszu widać głównie numer FV — kontrahent wymaga hovera |
| **Kiedy to się wydarzyło?** | **TAK** | `Dzisiaj (czwartek)` / `Wczoraj` / pełna data + godzina w osobnej linii |
| **Czy wymagana jest moja reakcja?** | **TAK** | Pomarańczowa/czerwona pigułka + ikony ⚠/❌; ostrzeżenia w `meta` rozwiniętego podsumowania |

### Werdykt

**4/5 pytań — natychmiastowa odpowiedź.** Jedyna luka: kontrahent faktury w widoku zwiniętym (bez hovera).

### Proponowana poprawka (następna iteracja, opcjonalna)

Dla grup z dokładnie 1 fakturą i pełnym snapshotem — dopisać skróconą nazwę kontrahenta do kolumny „Faktury”, np. `FV/123/2026 · ACME Sp. z o.o.` (z `text-overflow: ellipsis`). Nie blokuje deployu v3.

---

## Ograniczenia

1. **Tooltip zależy od `invoice_snapshot`** — starsze wpisy dziennika bez snapshotu pokazują komunikat „Brak szczegółów…”, nie pełne dane.
2. **Ikony emoji** — renderowanie zależy od systemu/OS; na niektórych urządzeniach mogą wyglądać nieco inaczej.
3. **„Dzisiaj/Wczoraj”** — liczone wg strefy czasowej przeglądarki operatora, nie serwera.
4. **Brak testów E2E w przeglądarce** — responsywność zweryfikowana przez CSS breakpoints i build; manualny smoke test na produkcji zalecany po deployu.

---

## Propozycje dalszego rozwoju

1. Kontrahent w kolumnie faktur (patrz UX Review).
2. Filtr „wymaga reakcji” (status warning/error).
3. Grupowanie po dniu (`Dzisiaj` / `Wczoraj` / `Wcześniej`) jako sekcje listy.
4. Powiadomienie dźwiękowe / toast przy zakończeniu długiej synchronizacji zakupów.
5. E2E test Playwright dla tooltipów i breakpointów tabletowych.

---

## Deploy

Nie wykonano w ramach GWO-IFG-0054. Wymaga standardowego deployu frontendu (`npm run build` + Guardian + `ifg_guardian deploy`).

---

## Powiązane zadania

- GWO-IFG-0053 — UX v2 (statusy, snapshot, daty z dniem tygodnia)
- GWO-IFG-0051B — produkcyjny deploy Monitora KSeF
