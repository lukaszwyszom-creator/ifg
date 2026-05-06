ZASADY PROJEKTU IFG:

1. Architektura:
- Backend: FastAPI
- Warstwy: router → service → repository
- Zakaz logiki biznesowej w routerach

2. Finanse:
- Decimal + ROUND_HALF_UP
- Brak float

3. Faktury:
- Statusy: READY_FOR_SUBMISSION, SENDING, ACCEPTED, REJECTED
- Brak draft
- number_local wymagany przed send

4. KSeF:
- Idempotencja transmisji
- Walidacja przed wysyłką
- Retry nie może omijać walidacji

5. Styl:
- Minimalne zmiany
- Nie ruszać API bez potrzeby
- Nie tworzyć nowych abstrakcji bez uzasadnienia

6. Testy:
- Każda zmiana musi przejść pytest

ZASADA:
Generuj kod zgodny z powyższymi regułami. Jeśli nie jesteś pewien — zapytaj zamiast zgadywać.