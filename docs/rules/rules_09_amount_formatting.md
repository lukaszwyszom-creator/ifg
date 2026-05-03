# Rules 09 - Ujednolicenie prezentacji kwot

## Cel
W całym IFG kwoty prezentowane użytkownikowi mają spójny format liczbowy:

- `xxx xxx,xx`

Sufiks/symbol waluty zależy od kontekstu:

- dla PLN: `xxx xxx,xx zł`
- dla walut obcych: `xxx xxx,xx` + symbol/kod waluty dokumentu (np. `€`, `$`, `GBP`)

## Twardy podział: dane vs prezentacja

- Dane w API, domenie i bazie pozostają liczbowe (`Decimal` / liczby), bez sufiksu waluty.
- Formatowanie z sufiksem/symbolem waluty jest wykonywane wyłącznie na granicy prezentacji:
  - frontend (render UI),
  - eksporty i raporty (warstwa wyjścia),
  - nigdy w logice biznesowej.
- `zł` wolno pokazać tylko wtedy, gdy waluta danych jest PLN albo dany widok jest z definicji PLN-only.

## Frontend

- Do formatowania kwot używamy wyłącznie helpera:
  - `frontend-react/src/utils/amountFormatting.js`
- Zabronione jest lokalne formatowanie przez `toFixed(2) + " PLN"` oraz lokalne duplikaty helperów.
- Widoki wielowalutowe muszą używać formattera zależnego od `currency` rekordu.
- Agregaty obejmujące wiele walut nie mogą mieć jednego symbolu waluty bez wcześniejszej normalizacji.
  - Akceptowalne: agregacja per waluta albo neutralny zapis bez symbolu.

## Eksport / raporty

- W eksportach XLSX kwoty pozostają liczbami.
- Wygląd prezentacyjny uzyskujemy przez format komórki (`number_format`):
  - dla PLN: `# ##0,00 "zł"`,
  - dla walut obcych: `# ##0,00` (waluta jest wskazywana oddzielnie w kolumnie `currency`).
- Nie zamieniamy kwot na tekst, jeśli eksport ma zachować możliwość dalszych obliczeń.

## Testy regresji

- Test helpera frontendowego musi obejmować wartości:
  - `0`, `1`, `12.3`, `999.99`, `1000`, `123456.7`, `1234567.89`
- Test helpera backendowego powinien potwierdzać:
  - spacje tysięcy,
  - przecinek dziesiętny,
  - 2 miejsca po przecinku,
  - sufiks `zł`.
