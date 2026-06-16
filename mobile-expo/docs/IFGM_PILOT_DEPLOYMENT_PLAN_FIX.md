# IFGM — korekta planu wdrożenia pilotażowego (G2)

**Data:** 2026-05-22  
**Dokument źródłowy:** `docs/IFGM_PILOT_DEPLOYMENT_PLAN.md` (wersja 1.0 → 1.1)

---

## Co poprawiono

| # | Zmiana | Sekcje |
|---|--------|--------|
| 1 | Ścieżka produkcyjna DS723+: `/volume1/docker/ifg/ifg_standalone` → `/volume1/docker/ifg_v2/ifg_standalone` | 1.1–1.4, 2, 7.2 |
| 2 | Backupy: `/volume1/docker/ifg/backups/` → `/volume1/docker/ifg_v2/backups/` | 1.1, 7.2 |
| 3 | Build frontend: `npm run build` obowiązkowy po zmianach w `src`; `npm ci` tylko przy zmianie `package.json` / `package-lock.json` | 2 (komendy deployu), 7.2 |
| 4 | Przykłady curl: neutralny placeholder `{"username":"TWOJ_LOGIN","password":"TWOJE_HASLO"}` zamiast `admin` / `ADMIN` | 1.4, 2, 4.1 |
| 5 | Bezpieczeństwo produkcji: nowa sekcja 1.0; rozszerzona 7.0 (zakaz `down -v`, reset DB, restore jako ostateczność) | 1.0, 1.1, 2, 7.0, 7.2 |
| 6 | Użytkownicy pilotażowi: wzmianka o `gosia`, `lukasz` (bez haseł w dokumencie) | 3.3 |
| 7 | Wersja dokumentu: 1.0 → 1.1 | nagłówek, stopka |

---

## Czego nie zmieniono

- **Kod aplikacji** — brak modyfikacji (backend, mobile-expo, frontend-react).
- **Rekomendacja** — pozostaje **WDRAŻAĆ PILOTAŻOWO**.
- **Zakres pilotażu** — bez KSeF mobile, SecureStore, paginacji.
- **Procedury deployu** — poza wskazanymi korektami (ścieżki, build npm, loginy, bezpieczeństwo).

---

*Notatka korekty G2 — wyłącznie dokumentacja.*
