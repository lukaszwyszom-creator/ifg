# KSeF — naprawa synchronizacji faktur zakupowych (prod)

## Diagnoza

Produkcyjny KSeF odpowiada poprawnie (sesja aktywna, endpoint sync purchases zwraca HTTP 200), ale faktury zakupowe nie trafiają do IFG.

Logi wskazują, że `query_received_invoices` wysyłał na sztywno `subjectType=subject2`. Dla części podmiotów KSeF zwraca wtedy pustą listę faktur, mimo że faktury zakupowe istnieją pod innym `subjectType` (np. `subject1` — nabywca, `subject3` — inna rola w FA).

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `app/integrations/ksef/client.py` | Parametr `subject_type` (domyślnie `"subject2"`) zamiast hardcoded wartości; logowanie `subjectType` w zapytaniach GET/POST |
| `app/services/ksef_session_service.py` | Fallback `subject2` → `subject1` → `subject3`; import tylko z pierwszego niepustego wyniku |
| `docs/KSEF_PROD_PURCHASE_SYNC_FIX.md` | Ten raport |

Nie zmieniono: tokenów, env, endpointów, modeli DB.

## Sposób testu

1. Upewnij się, że sesja KSeF jest aktywna dla NIP firmy.
2. Wywołaj synchronizację faktur zakupowych (UI lub API sync purchases) za okres, w którym w KSeF są znane faktury zakupowe.
3. Sprawdź logi backendu — powinny pojawić się wpisy:
   ```
   KSeF purchases sync subjectType=subject2 result_count=0
   KSeF purchases sync subjectType=subject1 result_count=3
   ```
   (liczby zależą od danych).
4. Zweryfikuj w IFG, że faktury zakupowe pojawiły się na liście (direction=purchase).
5. Powtórz sync — istniejące faktury powinny być pomijane (`skipped_existing`), bez duplikatów.

Opcjonalnie: w logach KSeF clienta sprawdź `params` / `subjectType` w liniach `query_received_invoices GET attempt` i `POST fallback`.

## Ryzyko

Fallback `subjectType` jest rozwiązaniem **diagnostyczno-naprawczym** — automatycznie próbuje trzech wartości, co może wydłużyć sync (do 3× więcej zapytań przy pustych wynikach). Docelowo warto dodać konfigurację przez env (np. `KSEF_PURCHASES_SUBJECT_TYPE`) dla podmiotów, u których znany jest właściwy typ, i wtedy pominąć fallback.
