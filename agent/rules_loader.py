"""rules_loader.py – wczytuje rulesy z plików rules_*.md w roota repo
oraz opcjonalnie z katalogu rules/ (pliki *.md).

Nie modyfikuje żadnego kodu aplikacji IFG.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RulesBundle:
    files: list[str]       # ścieżki plików (posortowane tekstowo)
    content: str           # scalona treść wszystkich plików


def load_rules(root_dir: str = ".", rules_subdir: str = "rules") -> RulesBundle:
    """Wczytaj rulesy z dwóch źródeł:

    a) pliki ``rules_*.md`` bezpośrednio w ``root_dir``,
    b) pliki ``*.md`` w ``root_dir/rules_subdir``, jeśli katalog istnieje.

    Lista scalona i posortowana deterministycznie po ścieżce tekstowej.
    Jeśli nic nie znajdzie – zwraca puste struktury. Nie crashuje.
    """
    root = Path(root_dir)

    candidates: list[Path] = list(root.glob("rules_*.md"))

    subdir = root / rules_subdir
    if subdir.is_dir():
        candidates.extend(subdir.glob("*.md"))

    all_paths = sorted(set(candidates), key=lambda p: str(p))

    if not all_paths:
        return RulesBundle(files=[], content="")

    parts: list[str] = []
    for p in all_paths:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            text = f"(nie można odczytać pliku {p})"
        parts.append(f"### {p.name}\n\n{text}")

    return RulesBundle(
        files=[str(p) for p in all_paths],
        content="\n\n---\n\n".join(parts),
    )
