# Repo hygiene and bloat control rules

## Cel
Chronić projekt IFG przed niekontrolowanym rozrostem:
- martwy kod
- zbędne pliki
- duże pliki
- gigantyczne linie
- przypadkowe backupy
- wygenerowane śmieci
- nieużywane zależności

---

## Zasada główna

Projekt ma pozostać mały, czytelny i kontrolowany.

Każda zmiana musi być minimalna.

---

## Obowiązkowa kontrola przed większą zmianą

Agent musi sprawdzić:

1. rozmiar repo
2. największe pliki
3. bardzo długie pliki
4. bardzo długie linie
5. pliki tymczasowe / backupowe
6. nieśledzone pliki
7. martwe importy
8. nieużywane funkcje / klasy
9. nowe zależności
10. przypadkowo wygenerowane pliki

---

## Komendy kontrolne

### Status Git

```bash
git status --short
```
