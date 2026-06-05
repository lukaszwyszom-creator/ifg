# IFGM USER FLOW V1

Dokument opisuje pełny przepływ użytkownika aplikacji mobilnej IFGM (Imperium Faktur G Mobile) na iPhone.

## Założenia

* IFGM jest aplikacją operacyjną do szybkiej pracy właściciela firmy.
* Desktop IFG pozostaje głównym systemem księgowym.
* Mobilka obsługuje najczęstsze codzienne operacje — bez duplikowania pełnej funkcjonalności desktopu.
* Interfejs zoptymalizowany pod iPhone 15 (390×844).
* Dark theme + złote akcenty.
* IFGM komunikuje się wyłącznie z backendem IFG — bez bezpośredniego połączenia z KSeF.

---

## 1. Dashboard (ekran startowy)

Ekran wejściowy po zalogowaniu. Pełnoekranowy dashboard — bez bottom navigation.

### Kafel główny

* **Sprzedaż netto** — suma netto faktur sprzedaży w wybranym okresie (złoty akcent).
* **Zakup netto** — suma netto faktur zakupowych w wybranym okresie (niebieski akcent).
* **VAT do zapłaty** lub **VAT do odliczenia** — w tym samym kaflu, pod separatorem:
  * stan dodatni → „VAT do zapłaty” (czerwony),
  * stan ujemny → „VAT do odliczenia” (zielony).

Okres wybierany selektorem **[ miesiąc rok ▾ ]** — tylko miesiąc i rok, bez dnia.

### Kafelki KPI

Każdy kafel jest klikalny i prowadzi do odpowiedniego ekranu.

| Kafel | Zawartość | Cel |
|-------|-----------|-----|
| **Powiadomienia** | liczba aktywnych spraw wymagających działania (np. „3 nowe”) | centrum spraw do załatwienia — patrz rozdział Powiadomienia |
| **Dłużnicy** | liczba faktur, suma należności, kwota po terminie | faktury sprzedaży nieopłacone lub częściowo opłacone |
| **Wierzyciele** | liczba faktur, suma zobowiązań, kwota po terminie | niezapłacone faktury zakupowe |
| **Płatności do przypisania** | liczba transakcji, suma | wpływy/wypływy bankowe bez przypisania do dokumentu |
| **KSeF** | liczba nowych zakupów, czas ostatniej synchronizacji | status integracji i skrót do widoku KSeF |

### Zasada projektowa

**Dashboard pokazuje stan firmy.**

**Powiadomienia pokazują rzeczy wymagające działania.**

### Nagłówek

* małe logo **IFG** po lewej
* tekst **Imperium Faktur G** po prawej stronie logo — logo i tekst w jednej linii
* po prawej: status KSeF (🟢 Połączono) + godzina ostatniej synchronizacji

### Sekcja dolna

**Ostatnie zakupy z KSeF** — skrócona lista ostatnio pobranych faktur zakupowych (dostawca, kwota). Tap → ekran faktur zakupu lub podgląd dokumentu.

### Przepływ

```text
Logowanie → Dashboard
Dashboard → tap kafel KPI → ekran szczegółowy
Dashboard → tap zakup KSeF → podgląd / lista zakupów
Dashboard → selektor okresu → zmiana miesiąca/roku → odświeżenie KPI
```

---

## 2. Dłużnicy

Wejście: tap kafel **Dłużnicy** na Dashboardzie.

### Lista kontrahentów

Każdy wiersz zawiera:

* nazwa kontrahenta
* kwota zadłużenia
* liczba faktur
* liczba faktur po terminie
* 2 linie ostatniej notatki (obcięcie z wielokropkiem)
* data ostatniego kontaktu

Sortowanie domyślne: malejąco po kwocie po terminie, potem po sumie zadłużenia.

### Akcje

* **tap wiersz** → Szczegóły dłużnika

---

## 3. Szczegóły dłużnika

Wejście: tap kontrahent na liście Dłużników.

### Widoczne od razu (above the fold)

* nazwa kontrahenta
* suma zadłużenia (wyeksponowana)
* ostatnia notatka — duża, czytelna, pełna treść ostatniego wpisu
* lista faktur zaległych

### Faktury

Każda faktura na liście:

* numer
* kwota
* termin płatności
* dni po terminie (0 = w terminie, >0 = przeterminowane)

### Akcje

* **Zadzwoń** — uruchomienie dialera z numerem kontrahenta (jeśli zapisany w IFG)
* **Dodaj notatkę** — formularz krótkiej notatki windykacyjnej (tekst + opcjonalnie typ kontaktu)

### Historia

Sekcja poniżej listy faktur:

* starsze notatki (chronologicznie, najnowsze u góry)
* historia kontaktów (data, typ, skrót treści)

### Przepływ

```text
Dashboard → Dłużnicy → Szczegóły dłużnika
Szczegóły → Zadzwoń → powrót do Szczegółów
Szczegóły → Dodaj notatkę → zapis → odświeżenie notatki i historii
Szczegóły → tap faktura → podgląd faktury sprzedaży (read-only)
```

---

## 4. Wierzyciele

Wejście: tap kafel **Wierzyciele** na Dashboardzie.

Struktura analogiczna do **Dłużników**, z perspektywy zobowiązań wobec dostawców:

### Lista

* nazwa dostawcy
* kwota zobowiązania
* liczba faktur
* liczba faktur po terminie
* 2 linie ostatniej notatki
* data ostatniego kontaktu

### Szczegóły wierzyciela

* nazwa dostawcy
* suma zobowiązania
* ostatnia notatka (wyeksponowana)
* lista faktur zakupowych
* akcje: **Zadzwoń**, **Dodaj notatkę**
* faktury: numer, kwota, termin, dni po terminie
* historia notatek i kontaktów

### Przepływ

```text
Dashboard → Wierzyciele → Szczegóły wierzyciela
Szczegóły → tap faktura → podgląd faktury zakupu (read-only)
```

---

## 5. Płatności do przypisania

Wejście: tap kafel **Płatności do przypisania** na Dashboardzie.

### Główne założenie

Mobilka służy do **akceptowania propozycji IFG** — system desktopowy (auto-match) proponuje przypisanie; użytkownik mobilny zatwierdza lub koryguje. Zaawansowana ręczna dekretacja pozostaje na desktopie.

### Kolejność informacji na ekranie decyzji

1. **kwota wpłaty** (najważniejsza, u góry)
2. **kontrahent** (z propozycji dopasowania)
3. **propozycja przypisania** (numer faktury / faktury, kwoty)
4. **zgodność dopasowania** (pełne / częściowe / brak — wskaźnik wizualny)

### Akcje

* **Przypisz** — zatwierdzenie propozycji IFG
* **Zmień** — wybór innej faktury lub korekta kwoty (w granicach MVP: prosta zmiana, bez pełnej dekretacji wielowierszowej)

### Scenariusze

| Scenariusz | Opis | Akcja mobilna |
|------------|------|---------------|
| jedna wpłata → jedna faktura | pełne dopasowanie kwoty | **Przypisz** |
| jedna wpłata → wiele faktur | IFG proponuje podział | **Przypisz** lub **Zmień** proporcje |
| częściowa płatność | wpłata < kwota faktury | **Przypisz** jako partial; reszta pozostaje otwarta |

### Przepływ

```text
Dashboard → Płatności do przypisania → lista transakcji
Lista → tap transakcja → ekran decyzji (kwota, kontrahent, propozycja)
Decyzja → Przypisz → potwierdzenie → powrót do listy
Decyzja → Zmień → wybór faktury → Przypisz
```

Import CSV i zaawansowane operacje bankowe — tylko desktop IFG.

---

## 6. Faktury sprzedaży

Wejście: z Dashboardu (skrót) lub nawigacja z menu kontekstowego / przyszłego launchera (poza dashboardem w v1 — dostęp z powiązanych ekranów).

### Lista

* numer faktury
* kontrahent
* kwota (brutto)
* status płatności (opłacona / częściowo / nieopłacona / po terminie)

Filtr domyślny: bieżący miesiąc (zgodnie z selektorem okresu Dashboardu).

### Akcje

* **tap wiersz** → podgląd faktury (read-only, HTML/PDF)

Bez wystawiania, edycji i wysyłki do KSeF — te operacje na desktopie.

---

## 7. Faktury zakupu

Wejście: tap **Ostatnie zakupy z KSeF** na Dashboardzie lub nawigacja z kafelka KSeF.

### Lista

* numer dokumentu
* dostawca
* kwota
* status (np. nieopłacona / opłacona / częściowo)

### Akcje

* **tap wiersz** → podgląd dokumentu (read-only)

---

## 8. KSeF

Wejście: tap kafel **KSeF** na Dashboardzie.

### Widok

* status połączenia (połączono / brak sesji / błąd)
* data i godzina ostatniej synchronizacji
* liczba nowych faktur zakupowych od ostatniej sync
* lista ostatnio pobranych faktur (skrót)

### Akcje

* **Synchronizuj** — wymuszenie pobrania faktur zakupowych przez backend IFG

Automatyczna synchronizacja IFG (DS723+): 08:00 i 15:00 — bez udziału użytkownika mobilnego.

### Przepływ

```text
Dashboard → KSeF → status + lista
KSeF → Synchronizuj → oczekiwanie → odświeżenie statusu i listy
KSeF → tap faktura → podgląd faktury zakupu
```

---

## Powiadomienia

### Cel

Powiadomienia nie są klasycznym systemem push.

Powiadomienia są **centrum spraw wymagających działania** przez użytkownika.

### Przykładowe zdarzenia

* płatności do przypisania
* nowe faktury zakupowe z KSeF
* przeterminowane należności
* przeterminowane zobowiązania
* błędy synchronizacji KSeF

Powiadomienia nie zawsze prowadzą od razu do pojedynczego rekordu.

Jeżeli zdarzenie jest **zbiorcze**, np.:

* 3 płatności do przypisania
* 2 nowe faktury z KSeF
* 4 przeterminowane należności

tap prowadzi najpierw do odpowiedniej **listy**, a dopiero potem do szczegółu.

Pojedyncze zdarzenie (np. jedna płatność, jedna faktura, jeden dłużnik) może prowadzić bezpośrednio do ekranu szczegółowego.

### Przykładowe przejścia

| Zdarzenie | Docelowy ekran |
|-----------|----------------|
| Płatność do przypisania | Płatności do przypisania |
| Nowa faktura KSeF | Podgląd faktury zakupu |
| Przeterminowana należność | Szczegóły dłużnika |
| Przeterminowane zobowiązanie | Szczegóły wierzyciela |
| Błąd synchronizacji KSeF | KSeF |

### Przykładowe przepływy zbiorcze

```text
Powiadomienia
→ Płatności do przypisania (3)
→ konkretna płatność
→ decyzja przypisania

Powiadomienia
→ Nowe faktury KSeF (2)
→ lista faktur
→ podgląd faktury
```

Wejście: tap kafel **Powiadomienia** na Dashboardzie → lista spraw → tap sprawy → lista (gdy zbiorcze) lub ekran docelowy → szczegół.

---

## 9. Nawigacja

Struktura ekranów (drzewo):

```text
Dashboard
├─ Powiadomienia
│  └─ Przekierowanie do odpowiedniego ekranu
├─ Dłużnicy
│  └─ Szczegóły dłużnika
│     └─ Podgląd faktury sprzedaży
├─ Wierzyciele
│  └─ Szczegóły wierzyciela
│     └─ Podgląd faktury zakupu
├─ Płatności do przypisania
│  └─ Decyzja przypisania (Przypisz / Zmień)
├─ Faktury sprzedaży
│  └─ Podgląd faktury
├─ Faktury zakupu
│  └─ Podgląd dokumentu
└─ KSeF
   └─ Podgląd faktury zakupu
```

Powrót: standardowy gest iOS (swipe back) lub przycisk **←** w nagłówku ekranu szczegółowego.

Dashboard nie ma bottom navigation — każdy ekran szczegółowy wraca do Dashboardu lub do ekranu nadrzędnego.

---

## 10. Zakres MVP

### Obowiązkowe (v1)

* Dashboard
* Powiadomienia (centrum spraw wymagających działania)
* Dłużnicy
* Szczegóły dłużnika (notatki, kontakt, lista faktur)
* Wierzyciele
* Szczegóły wierzyciela
* Płatności do przypisania (akceptacja / korekta propozycji IFG)
* Faktury sprzedaży (lista + podgląd)
* Faktury zakupu (lista + podgląd)
* KSeF (status + synchronizacja ręczna)

### Poza MVP

* magazyn
* raporty zaawansowane
* pełna windykacja (masowe akcje, szablony pism, eskalacje)
* OCR
* skanowanie dokumentów
* wystawianie i edycja faktur
* import CSV
* pełna ręczna dekretacja bankowa

---

## Otwarte pytania do V2

