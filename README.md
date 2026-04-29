# KSeF Backend

Szkielet modularnego monolitu FastAPI dla integracji z KSeF i REGON.

Aktualny stan:

- przygotowana struktura warstw `api`, `services`, `domain`, `integrations`, `persistence`, `worker`
- dodane minimalne pliki startowe bez implementacji logiki biznesowej
- przygotowany Dockerfile i `docker-compose.yml` dla uruchomienia lokalnego

## Invoice state transitions

- Status `draft` został usunięty (historyczna migracja domeny).
- Nowe faktury są tworzone bezpośrednio w statusie `READY_FOR_SUBMISSION`.
- Endpoint `POST /api/v1/invoices/{id}/mark-ready` jest celowo idempotentny po usunięciu `draft`.
- Jeśli faktura jest już `READY_FOR_SUBMISSION` i nie ma `number_local`, `mark-ready` nadaje numer lokalny.
- Jeśli faktura jest już `READY_FOR_SUBMISSION` i ma `number_local`, `mark-ready` zwraca fakturę bez zmian.
- Dla statusów `SENDING`, `ACCEPTED`, `REJECTED` wywołanie `mark-ready` jest niedozwolone i zwraca `409`.
