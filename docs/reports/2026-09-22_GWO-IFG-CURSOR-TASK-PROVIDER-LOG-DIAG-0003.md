# GWO-IFG-CURSOR-TASK-PROVIDER-LOG-DIAG-0003

Data: 2026-09-22  
Zakres: wyłącznie diagnostyka logów Cursor (bez zmian w repo / settings / cache / node_modules).

## STATUS

`DIAG_COMPLETE_UNDERLYING_EXCEPTION_SWALLOWED`

## LATEST_CURSOR_SESSION

`/Users/lukasz/Library/Application Support/Cursor/logs/20260917T220613`

Aktywne okno IFG: `window3` (workspaceId `37a0afe3aa48dea3f0f2500a6852a83a`, folder `/Users/lukasz/projekty/ifg_standalone`).

## ERROR_AFTER_RELOAD

`YES`

Ostatni Reload Window (exthost):

- `2026-09-22 21:10:07.131` — Extension host pid 85744 exiting
- `2026-09-22 21:10:09.177` — Extension host pid 85992 started
- `2026-09-22 21:10:09.307` — `ExtensionService#_doActivateExtension vscode.npm` (`onLanguage:json`)
- `2026-09-22 21:10:09.478` — `Extension activated success: vscode.npm`

Po tym reloadzie Tasks output na dysku został zapisany ponownie:

- plik: `.../window3/output_20260922T211007/tasks.workspaceId-37a0afe3aa48dea3f0f2500a6852a83a.log`
- mtime: `2026-09-22T21:10:14+0200`

Ten sam błąd powtórzył się też po wcześniejszych reloadach tego samego wieczoru:

| output dir | mtime Tasks log |
|---|---|
| `output_20260922T205809` | 20:58:15 |
| `output_20260922T210400` | 21:04:06 |
| `output_20260922T210913` | 21:09:20 |
| `output_20260922T211007` | 21:10:14 |

## ERROR_TIMESTAMP

`2026-09-22 21:10:14 +0200` (mtime najnowszego `tasks.*.log` po reloadzie 21:10:07–21:10:09)

## ERROR_SOURCE

Built-in extension **`vscode.npm`** (task provider `npm`), aktywowany przez `onLanguage:json`.

Nie znaleziono osobnego provider’a zewnętrznego.  
W logach sesji **brak** stringa `faktura-frontend` (to tylko `"name"` w `package.json`).

## FAILING_PATH

`/Users/lukasz/projekty/ifg_standalone/frontend-react/package.json`

- ścieżka w komunikacie jest **rzeczywista** (nie inny plik przebrany za `package.json`)
- plik regularny (nie symlink), `file(1)`: `JSON data`
- `JSON.parse` / `npm pkg get` PASS (wcześniej potwierdzone)
- LF-only, brak BOM, `scripts` = 7 stringów, `name` = `faktura-frontend`
- provider **nie** wskazuje innego `package.json` w treści wyjątku

## EXCEPTION

Jedyna treść w Tasks output (cały plik = 1 linia + pusta linia):

```text
Error: Npm task detection: failed to parse the file /Users/lukasz/projekty/ifg_standalone/frontend-react/package.json
```

## STACK_TRACE

`NONE_IN_LOGS`

- `tasks.*.log` — tylko powyższy `Error:` bez stacka
- `exthost.log` — aktywacja `vscode.npm` OK, **bez** wyjątku nested
- `renderer.log` — **brak** trafień `Npm task` / `failed to parse` / `There are task errors`
- toast `"There are task errors. See the output for details."` **nie jest logowany** do plików sesji

Dlatego panel Output/Tasks w UI może wyglądać na pusty, mimo że kanał Tasks na dysku zawiera jedną linię Error.

## Kontekst logów (≥30 linii wokół aktywacji po ostatnim reloadzie)

Źródło: `.../window3/exthost/exthost.log` (linie ~696–765). Trafienie błędu Tasks nie ma ±30 linii w samym pliku Tasks (plik ma 1 linię); poniżej kontekst reload + aktywacji `vscode.npm`:

```text
... Extension host terminate / dispose stack ...
2026-09-22 21:10:07.131 [info] Extension host with pid 85744 exiting with code 0
2026-09-22 21:10:07.134 [info] Extension host with pid 85753 exiting with code 0
2026-09-22 21:10:09.177 [info] Extension host with pid 85992 started
2026-09-22 21:10:09.177 [info] Skipping acquiring lock for .../workspaceStorage/37a0afe3aa48dea3f0f2500a6852a83a.
... sandbox probe from /Users/lukasz/projekty/ifg_standalone ...
2026-09-22 21:10:09.262 [info] ExtensionService#_doActivateExtension anysphere.cursor-polyfills-remote ...
2026-09-22 21:10:09.271 [info] ExtensionService#_doActivateExtension vscode.git-base ...
2026-09-22 21:10:09.273 [info] ExtensionService#_doActivateExtension vscode.emmet ...
2026-09-22 21:10:09.278 [info] ExtensionService#_doActivateExtension vscode.configuration-editing ... onLanguage:json
2026-09-22 21:10:09.281 [info] ExtensionService#_doActivateExtension vscode.extension-editing ... onLanguage:json
2026-09-22 21:10:09.286 [info] ExtensionService#_doActivateExtension vscode.json-language-features ... onLanguage:json
2026-09-22 21:10:09.307 [info] ExtensionService#_doActivateExtension vscode.npm ... onLanguage:json
2026-09-22 21:10:09.324 [info] ExtensionService#_doActivateExtension vscode.typescript-language-features ...
...
2026-09-22 21:10:09.478 [info] Extension activated success: vscode.npm — 89ms
...
```

Bezpośrednio potem (mtime 21:10:14) Tasks log:

```text
Error: Npm task detection: failed to parse the file /Users/lukasz/projekty/ifg_standalone/frontend-react/package.json
```

## Mechanizm w kodzie Cursor (`vscode.npm`)

Z `/Applications/Cursor.app/Contents/Resources/app/extensions/npm/dist/npmMain.js`:

```javascript
async function dd(e,t){
  if(e.scheme!=="file")return;
  let n=e.fsPath;
  if(await vu(n)&&!t?.isCancellationRequested)
    try{
      let r=await q.workspace.openTextDocument(e);
      return t?.isCancellationRequested?void 0:Ce(r)
    }catch{
      let i=q.l10n.t("Npm task detection: failed to parse the file {0}",e.fsPath);
      throw new Error(i)  // oryginalny wyjątek jest PORZUCANY (brak cause / log)
    }
}
```

`Ce()` (parser skryptów) używa `jsonc-parser` `visit` z pustym `onError(){}` — **nie rzuca** przy złym JSON; przy braku `scripts` zwraca `undefined`.

Wniosek:

1. Komunikat „failed to parse” jest **myłący** — to catch-all wokół `openTextDocument` **lub** `Ce`, nie dowód `JSON.parse` failure.
2. Prawdziwy wyjątek **nigdy nie trafia do logów**, bo `catch { ... throw new Error(i) }` go gubi.
3. Dlatego z samych logów Cursor **nie da się** odczytać underlying exception / stack.

## ROOT_CAUSE

`vscode.npm` task detection (`dd()`): catch-all zamienia dowolny błąd `workspace.openTextDocument(uri)` / `Ce(doc)` na lokalizowany `Error: Npm task detection: failed to parse the file <fsPath>` **bez cause i bez stacka**.

- Invalid JSON w `frontend-react/package.json`: **wykluczony** (parse PASS; `Ce` i tak nie throwuje na JSON errors).
- Inna ścieżka niż wskazana: **wykluczona**.
- Konkretny underlying exception (`openTextDocument` reject reason vs rzadki throw w `Ce`): **`NOT_CONFIRMED`** — celowo niewidoczny w logach.

## NEXT_MINIMAL_ACTION

Bez zmian w repo: w Cursor DevTools (Help → Toggle Developer Tools) ustawić breakpoint / override w `npmMain.js` funkcji `dd` na `catch (err)` i zalogować `err` przed `throw new Error(i)` — **albo** jednorazowo w User settings (nie repo): `"npm.autoDetect": "off"` aby potwierdzić, że toast znika (workaround, nie root fix).

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

(Diag-only; brak zmian aplikacji IFG.)
