---
kind: gwo
project: IFG
workflow: GWO-GUARDIAN-CLIPBOARD-HOTFIX
handoff: true
created_at: 2026-07-11T00:20:00Z
---

# HOTFIX — Guardian Handoff Clipboard Regression

**Data:** 2026-07-11  
**Cel:** Przywrócić automatyczne kopiowanie handoff do schowka z weryfikacją sukcesu.

---

## Diagnoza — root cause

| Przyczyna | Opis |
|---|---|
| **1. `--no-clipboard` w sesjach agenta** | Podczas GWO-0064/0065/0066 testy uruchamiano `handoff latest --no-clipboard`, co wyłączało kopiowanie. Operator uruchamiając komendę ręcznie mógł widzieć brak schowka po wcześniejszych runach agenta. |
| **2. Fałszywy komunikat sukcesu/błędu** | Przy błędzie `pbcopy` (np. sandbox Cursor, exit 1) wyświetlano: `Clipboard: not available on this environment` — sugerując brak macOS, podczas gdy problemem był błąd wykonania, nie brak narzędzia. |
| **3. Brak weryfikacji** | Po `pbcopy` nie było odczytu `pbpaste` — niemożliwe wykrycie cichej porażki kopiowania. |
| **4. Nieczytelny UX** | Brak jednoznacznych komunikatów `✓ Skopiowano` / `⚠ Nie udało się`. |

**Potwierdzenie regresji w sandbox:**

```
Clipboard copy skipped: Command '['pbcopy']' returned non-zero exit status 1.
Clipboard: not available on this environment
```

**Potwierdzenie działania poza sandbox (macOS):**

```
✓ Handoff wygenerowany
✓ Skopiowano do schowka
✓ Gotowy do wklejenia do ChatGPT
pbpaste → zawartość CHATGPT HANDOFF 2026-07-11
```

---

## Naprawa

### Nowy moduł `scripts/ifg_guardian/core/clipboard.py`

- `pbcopy` → zapis treści
- `pbpaste` → weryfikacja round-trip (normalizacja EOL)
- Zwraca `(success, reason)` — bez fałszywego sukcesu

### Zmiany w `ifg_handoff.py`

- `_print_handoff_summary()` — oczekiwany output operatora
- Usunięto `_copy_to_clipboard_if_possible()` bez weryfikacji
- Przy `--no-clipboard`: `ℹ Kopiowanie do schowka wyłączone`

### Testy

- `tests/unit/test_guardian_handoff_clipboard.py` — 4 testy (round-trip, mismatch, success/failure UX)
- 21/21 testów handoff+clipboard PASS

---

## Wynik testu końcowego

```bash
PYTHONPATH=scripts python3 -m ifg_guardian.cli ifg handoff latest
```

```
✓ Handoff wygenerowany
  Plik: reports/CHATGPT_HANDOFF_2026-07-11.md
  Scalono raportów: 1
✓ Skopiowano do schowka
✓ Gotowy do wklejenia do ChatGPT
```

**Weryfikacja `pbpaste`:** nagłówek `# CHATGPT HANDOFF 2026-07-11` — zgodny z plikiem. Operator może natychmiast wkleić do ChatGPT (⌘V).

---

🩷 STATUS KOŃCOWY

✅ Co działa  
- Zapis pliku handoff  
- Automatyczne kopiowanie z weryfikacją `pbpaste`  
- Jednoznaczne komunikaty sukcesu/błędu  

⚠️ Znane problemy  
- W sandboxie Cursor `pbcopy` może nadal zwrócić exit 1 — wtedy handoff wyświetla `⚠` z powodem (bez fałszywego sukcesu)  

❌ Co nie działa  
- Brak regresji przy normalnym uruchomieniu na macOS  

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/2026-07-11_GWO-GUARDIAN_CLIPBOARD_REGRESSION_FIX.md`
- `reports/CHATGPT_HANDOFF_2026-07-11.md`
