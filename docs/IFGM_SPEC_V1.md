# IFGM_SPEC_V1

## 1. Cel

IFGM (Imperium Faktur G Mobile) jest mobilnym interfejsem systemu IFG przeznaczonym dla iPhone.

IFGM nie jest osobnym systemem.

Architektura:

```text
IFGM (iPhone)
        ↓
IFG (DS723+)
        ↓
KSeF
```

Cała logika biznesowa, baza danych, integracje i komunikacja z KSeF pozostają po stronie IFG.

IFGM jest mobilnym centrum kontroli firmy.

---

## 2. Zakres IFGM v1

### Dostępne funkcje

* Dashboard (Start)
* Dłużnicy
* Wierzyciele
* Płatności do przypisania
* Zmiana przypisania płatności
* Cofnięcie przypisania płatności
* KSeF
* Zakupy z KSeF
* Historia kontaktów
* Notatki windykacyjne

### Poza zakresem

* wystawianie faktur
* edycja faktur
* magazyn
* konfiguracja firmy
* ustawienia systemowe
* administracja
* numeracja dokumentów

---

## 3. KSeF

### Architektura

IFGM nie łączy się bezpośrednio z KSeF.

Komunikacja:

```text
IFGM
 ↓
IFG
 ↓
KSeF
```

### Synchronizacja automatyczna

IFG wykonuje automatyczną synchronizację:

* 08:00
* 15:00

Synchronizacja wykonywana jest na DS723+.

### Synchronizacja ręczna

IFGM może wymusić synchronizację:

```text
Synchronizuj teraz
```

Jest to funkcja awaryjna.

### Status KSeF

Kafel KSeF pokazuje:

* status połączenia
* liczbę nowych zakupów
* datę i godzinę ostatniej synchronizacji

---

## 4. Dashboard (Start)

### Nagłówek

```text
IFG
Imperium Faktur G

KSeF OK
Ostatnia synchronizacja

[ miesiąc rok ]
```

Przykład:

```text
maj 2026
```

Użytkownik może zmieniać wyłącznie:

* miesiąc
* rok

### Główny kafel

```text
Sprzedaż netto | Zakup netto
```

Pod separatorem:

```text
VAT do zapłaty
```

lub

```text
VAT do odliczenia
```

### Kafle KPI

#### Dłużnicy

Pokazuje:

* liczbę faktur
* sumę należności
* sumę przeterminowaną

#### Wierzyciele

Pokazuje:

* liczbę faktur
* sumę zobowiązań
* sumę przeterminowaną

#### Płatności do przypisania

Pokazuje:

* liczbę transakcji
* wartość transakcji

#### KSeF

Pokazuje:

* status
* nowe zakupy
* ostatnią synchronizację

### Ostatnie zakupy z KSeF

Na dole dashboardu prezentowana jest lista ostatnich faktur zakupowych pobranych z KSeF.

---

## 5. Dłużnicy

Lista prezentuje faktury sprzedażowe.

Format pozycji:

```text
Kontrahent
Numer faktury

Kwota brutto

za X dni
lub
X dni po terminie
```

Przykład:

```text
ABC Sp. z o.o.
45/2026

1250 zł

18 dni po terminie
```

### Notatki

Jeżeli istnieje notatka, wyświetlana jest ostatnia notatka.

Przykład:

```text
12.06 10:15

Klient deklaruje płatność do piątku.
```

Widoczna bez otwierania szczegółów.

### Szczegóły

Dostępne akcje:

* Zadzwoń
* Email
* Dodaj notatkę

### Historia kontaktów

Każda notatka zawiera:

* datę
* godzinę
* użytkownika
* treść

Notatki są przypisane do konkretnej faktury.

---

## 6. Wierzyciele

Widok analogiczny do Dłużników.

Dotyczy faktur zakupowych.

Format:

```text
Kontrahent
Numer faktury

Kwota brutto

za X dni
lub
X dni po terminie
```

---

## 7. Płatności do przypisania

Ekran prezentuje nieprzypisane płatności.

Dla każdej pozycji:

```text
Kwota
Kontrahent
Tytuł przelewu
```

### Przypisanie

Użytkownik wybiera fakturę.

IFG może proponować dopasowanie.

### Przypisanie częściowe

Obsługiwane.

Przykład:

```text
Płatność 500 zł

Faktura 1250 zł
```

### Korekta przypisania

Dostępne operacje:

* Zmień przypisanie
* Cofnij przypisanie

### Audyt

IFG zapisuje:

* kto przypisał
* kiedy przypisał
* kto zmienił
* kiedy zmienił

Historia pozostaje w IFG.

---

## 8. Założenia UX

IFGM ma odpowiadać na pytania:

* Ile sprzedałem?
* Ile kupiłem?
* Ile VAT?
* Kto mi nie zapłacił?
* Komu ja nie zapłaciłem?
* Czy mam płatności do przypisania?
* Czy KSeF działa?

Priorytet:

```text
minimum kliknięć
maksimum informacji
```

Telefon służy do kontroli i szybkich działań operacyjnych.

Pełna obsługa firmy pozostaje w IFG.
