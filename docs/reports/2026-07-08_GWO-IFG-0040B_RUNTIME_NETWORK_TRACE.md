# GWO-IFG-0040B — Runtime Network Trace

**Data:** 2026-07-08  
**Zakres:** wyłącznie runtime trace (bez analizy kodu, bez testowych scenariuszy)

---

## Źródło danych runtime

- Logi kontenera backendu: `docker compose -f docker/docker-compose.yml logs api --since 30m`
- Zakres czasowy obserwacji: ostatnie ~30 minut

---

## Zidentyfikowane requesty `/api/v1/transmissions/` w runtime

W logach runtime wystąpiły requesty:

1. `GET /api/v1/transmissions/?page=1&size=20`
2. `GET /api/v1/transmissions/?page=1&size=20&warnings_or_errors_only=true`

W obu przypadkach backend zwrócił:

- **HTTP 401 Unauthorized**

Potwierdzenie w logach backendu (`app.access` + uvicorn access):

- `status_code: 401`, `endpoint: /api/v1/transmissions/`
- linia access: `"GET /api/v1/transmissions/... HTTP/1.1" 401 Unauthorized`

---

## Wymagane pola trace vs dostępność danych

| Pole | Status |
|------|--------|
| Dokładny URL | ✅ dostępny (w access log) |
| HTTP status | ✅ dostępny (401) |
| Czy request dochodzi do backendu | ✅ tak (wpisy access log istnieją) |
| Response headers | ❌ niedostępne w obecnym logowaniu backendu |
| Response body | ❌ niedostępne dla `/transmissions/` w obecnym logowaniu backendu |
| Request headers | ❌ niedostępne w obecnym logowaniu backendu |
| Authorization header (czy wysłany) | ❌ niedostępne (brak logowania nagłówków requestu) |
| 500 traceback | ℹ️ brak 500 w obserwowanym runtime |
| 422 validation error | ℹ️ brak 422 w obserwowanym runtime |
| 401 przyczyna odrzucenia tokenu aktywnej sesji | ⚠️ nieustalone na podstawie dostępnych runtime logów (brak wartości `Authorization` i brak payloadu odpowiedzi dla tego requestu) |

---

## Statusy backendu zaobserwowane dla flow transmisji

W obserwowanym runtime dla requestów do transmisji:

- **401** — występuje
- **403** — brak wpisów
- **404** — brak wpisów dla `/api/v1/transmissions/`
- **422** — brak wpisów
- **500** — brak wpisów
- **200** — brak wpisów

---

## Ograniczenie diagnostyczne (fakt)

Na podstawie samych logów backendu nie ma technicznej możliwości odtworzenia:

- pełnych request headers / response headers / response body konkretnego requestu z przeglądarki,
- wartości nagłówka `Authorization`,
- przyczyny odrzucenia konkretnego tokenu aktywnej sesji użytkownika (poza samym faktem `401`).

Do pełnego trace (tak jak wymagane) potrzebny jest eksport z **Network tab (HAR)** z aktywnej sesji przeglądarki użytkownika dla jednego requestu `GET /api/v1/transmissions/...`.

---

## Wniosek runtime (bez hipotez)

1. Request `GET /api/v1/transmissions/...` dochodzi do backendu.
2. Backend odpowiada **401 Unauthorized**.
3. Obecne logi runtime backendu nie zawierają danych koniecznych do potwierdzenia, czy aktywna sesja wysłała `Authorization` oraz dlaczego konkretny token został odrzucony.

