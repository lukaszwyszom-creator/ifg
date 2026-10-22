# IFG – STATIC GRAPHIC UNDERLAY V1

Źródło prawdy: `projektfv.jpg`.

Ten pakiet NIE rekonstruuje layoutu. Bazuje bezpośrednio na zaakceptowanym MASTER i:
- usuwa przykładowe wartości dynamiczne,
- zachowuje stałą geometrię dokumentu,
- aktualizuje tabelę do 10 kolumn (CENA NETTO + CENA BRUTTO),
- pozostawia po prawej tylko `DO ZAPŁATY`,
- rezerwuje slot KSeF + QR,
- usuwa witraż z podkładu i traktuje go jako OSOBNY, EDYTOWALNY moduł.

Pliki:
- `sale_invoice_background_locked.png` — statyczny podkład.
- `sale_invoice_fields.json` — współrzędne pól dynamicznych.
- `stained_glass_module.json` — edytowalne parametry witraża.
- `stained_glass_current.png` — bieżący asset witraża.
- `sale_invoice_background_preview.png` — podgląd podkładu z aktualnym witrażem i pustymi polami.

Binder IFG może zmieniać WYŁĄCZNIE wartości pól z JSON oraz parametry modułu witraża.
Nie może zmieniać osi, separatorów, tabeli, typografii statycznej ani geometrii strony.
