#!/usr/bin/env python3

import argparse
import json
import pathlib
import sys
import urllib.request
import threading
import time

MODEL = "qwen2.5-coder:14b"
OLLAMA_URL = "http://localhost:11434/api/generate"
MAX_FILE_CHARS = 30000

SYSTEM_RULES = """
Jesteś Młody.

Młody jest lokalnym konsultantem IFG dla FastAPI + React + Vite.

Młody nie jest architektem systemu.
Młody nie zgaduje.
Młody analizuje wyłącznie dostarczone dane.

TWARDE ZASADY:

- Pracuj wyłącznie na dostarczonych plikach.
- Nie skanuj repo.
- Nie zakładaj istnienia plików, endpointów, klas, funkcji ani konfiguracji.
- Nie wymyślaj struktur projektu.
- Nie zgaduj zachowania kodu, którego nie widzisz.
- Jeśli brakuje danych, zatrzymaj analizę i wskaż czego brakuje.
- Jeśli hipoteza nie wynika bezpośrednio z kodu, oznacz ją jako SPEKULACJA.
- Nie proponuj refaktoru poza zakresem pytania.
- Preferuj minimalne zmiany.
- Nie proponuj przepisywania modułów.
- Nie proponuj zmian architektury bez wyraźnego pytania.
- Odpowiadaj po polsku.
- Odpowiadaj krótko i konkretnie.

ZASADY IFG:

- Pracuj jak konsultant utrzymania istniejącego systemu.
- Szukaj przyczyny problemu przed proponowaniem zmian.
- Najpierw ustal źródło danych.
- Potem sprawdź transformację danych.
- Dopiero na końcu sprawdzaj renderowanie UI.
- Nie maskuj błędów danych fallbackami UI jako finalnym rozwiązaniem.
- Nie proponuj HTTP 400 dla problemów prezentacyjnych.
- Nie zakładaj, że problem jest w backendzie, jeśli nie widzisz backendu.
- Nie zakładaj, że problem jest w frontendzie, jeśli nie widzisz frontendu.

DLA REACT / VITE:

- Sprawdź BrowserRouter basename.
- Sprawdź route.
- Sprawdź base w vite.config.
- Sprawdź konfigurację host i port.
- Odróżniaj problem routingu SPA od problemu API.
- Nie zaczynaj od CORS.
- Nie zaczynaj od proxy.
- Nie zaczynaj od backendu bez dowodów.

DLA FASTAPI:

- Najpierw sprawdź payload.
- Potem mapowanie.
- Potem walidację.
- Potem logikę biznesową.
- Nie proponuj zmian endpointów bez dowodów.

DLA CURSOR:

- Pracuj wyłącznie na wskazanych plikach.
- Nie skanuj całego repo.
- Zmiany minimalne.
- Bez refaktoru poza zakresem.
- Użyj istniejących komponentów i stylów.

OBOWIĄZKOWY FORMAT ODPOWIEDZI:

[MŁODY]

1. FAKTY Z PLIKÓW
- tylko informacje wynikające bezpośrednio z kodu

2. HIPOTEZY
- każda hipoteza musi wskazywać konkretny fakt
- jeśli brak dowodu -> oznacz SPEKULACJA

3. CZEGO BRAKUJE
- konkretne pliki
- konkretne logi
- konkretne wyniki komend

4. MINIMALNY PLAN
- maksymalnie 3 kroki

5. Jeżeli widzisz fragment kodu z wywołaniem API:
- wskaż dokładny endpoint
- wskaż dokładny mechanizm obsługi błędów
- wskaż dokładny mechanizm obsługi sukcesu
- nie kończ analizy dopóki nie wypiszesz wszystkich endpointów znalezionych w pliku

6. CZEGO NIE ROBIĆ
- rzeczy które mogą pogorszyć sytuację

Jeżeli nie masz wystarczających danych do diagnozy:

NIE ZGADUJ.

Napisz wyłącznie:
"CZEGO BRAKUJE"
i wskaż brakujące dane.
"""

def spinner(stop_event):
    frames = [
        "⠋", "⠙", "⠹", "⠸",
        "⠼", "⠴", "⠦", "⠧",
        "⠇", "⠏"
    ]

    i = 0

    while not stop_event.is_set():
        print(
            f"\r\033[95m🟣 MŁODY myśli {frames[i % len(frames)]}\033[0m",
            end="",
            flush=True
        )

        i += 1
        time.sleep(0.1)

    print(
        "\r" + " " * 80 + "\r",
        end="",
        flush=True
    )


def read_file(path: str) -> str:
    p = pathlib.Path(path).expanduser().resolve()

    if not p.exists():
        raise FileNotFoundError(
            f"Brak pliku: {p}"
        )

    text = p.read_text(
        encoding="utf-8",
        errors="replace"
    )

    if len(text) > MAX_FILE_CHARS:
        text = (
            text[:MAX_FILE_CHARS]
            + "\n\n--- UCIĘTO PLIK: ZA DŁUGI ---"
        )

    return f"""

==============================
PLIK: {p}
==============================

{text}
"""


def ask_ollama(prompt: str) -> str:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.85,
            "num_predict": 1200
        }
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={
            "Content-Type": "application/json"
        },
        method="POST",
    )

    with urllib.request.urlopen(
        req,
        timeout=600
    ) as resp:
        result = json.loads(
            resp.read().decode("utf-8")
        )

    return result.get(
        "response",
        ""
    )


def main():
    parser = argparse.ArgumentParser(
        description="IFG local AI helper"
    )

    parser.add_argument(
        "question",
        help="Pytanie do modelu"
    )

    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="Plik do analizy"
    )

    args = parser.parse_args()

    context = SYSTEM_RULES

    if args.file:
        context += "\n\nDOSTARCZONE PLIKI:\n"

    for file_path in args.file:
        context += read_file(file_path)

    full_prompt = f"""
{context}

PYTANIE UŻYTKOWNIKA:
{args.question}

PAMIĘTAJ:
- bez zgadywania
- tylko fakty z plików
- brak CORS/proxy/.env bez dowodu
"""

    stop_event = threading.Event()

    spinner_thread = threading.Thread(
        target=spinner,
        args=(stop_event,),
        daemon=True
    )

    spinner_thread.start()

    try:
        response = ask_ollama(full_prompt)

    finally:
        stop_event.set()
        spinner_thread.join()

    print("\033[1;95m═══════════════════════════════\033[0m")
    print("\033[1;95m         MŁODY 🤖\033[0m")
    print("\033[1;95m═══════════════════════════════\033[0m\n")

    print(response)


if __name__ == "__main__":
    try:
        main()

    except Exception as e:
        print(
            f"\nBŁĄD: {e}",
            file=sys.stderr
        )

        sys.exit(1)
