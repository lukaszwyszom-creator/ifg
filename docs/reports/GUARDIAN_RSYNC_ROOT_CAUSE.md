# GUARDIAN_RSYNC_ROOT_CAUSE

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- SSH Mac -> DS723+ działa poprawnie (`ssh -p 32122 zdalny_admin@ds723`).
- Użytkownik `zdalny_admin` loguje się poprawnie i ma dostęp do repo.
- Po stronie DS723+ `rsync` jest dostępny (`/usr/bin/rsync`, wersja 3.1.2).
- Katalog docelowy istnieje i jest zapisywalny dla `zdalny_admin`.
- Ręczne uruchomienie rsync działa po poprawieniu sposobu wywołania (jawna ścieżka binarki):  
  `rsync -av --rsync-path=/bin/rsync -e "ssh -p 32122" frontend-react/dist/ zdalny_admin@ds723:/volume1/docker/ifg_v2/ifg_standalone/frontend-react/dist/`

⚠️ ZNANE PROBLEMY
- Dokładna komenda Guardiana (bez `--rsync-path`) failuje:
  `rsync -av -e "ssh -p 32122" frontend-react/dist/ zdalny_admin@ds723:/volume1/docker/ifg_v2/ifg_standalone/frontend-react/dist/`
  z błędem: `Permission denied, please try again.`
- Błąd występuje na warstwie uruchomienia zdalnego `rsync --server` i nie wynika z samego SSH loginu.

❌ CO NIE DZIAŁA
- `dist sync` Guardiana w obecnej formie (gołe `rsync`) zatrzymuje deploy.

A. ROOT CAUSE
- Odtworzono 1:1 komendę Guardiana i potwierdzono fail.
- Zweryfikowano kolejno:
  - **autoryzacja SSH**: OK (public key accepted),
  - **użytkownik**: OK (`zdalny_admin`),
  - **klucz**: OK (`id_ed25519`),
  - **ścieżka docelowa**: OK (istnieje),
  - **uprawnienia katalogu**: OK (test `touch` działa),
  - **rsync na DS723+**: OK (binary + version dostępne).
- Przyczyna operacyjna: problem nie leży w dostępie do hosta ani katalogu, tylko w sposobie wywołania zdalnego `rsync` przez domyślne `rsync` (bez jawnego `--rsync-path`).
- Potwierdzenie: ten sam transfer działa po wymuszeniu zdalnej binarki absolutną ścieżką (`--rsync-path=/bin/rsync`).

B. ZMIENIONE PLIKI
- `docs/reports/GUARDIAN_RSYNC_ROOT_CAUSE.md`

C. DEPLOY
- Nie zmieniano kodu Guardiana.
- Nie wyłączano żadnego kroku pipeline.
- Naprawa wykonana wyłącznie na poziomie sposobu wywołania rsync (operacyjnie, poza kodem).

D. TESTY
- Test 1 (dokładna komenda Guardiana): FAIL (`Permission denied, please try again.`)
- Test 2 (SSH login): PASS
- Test 3 (rsync/version na DS723+): PASS
- Test 4 (write permission do dist): PASS
- Test 5 (rsync z `--rsync-path=/bin/rsync`): PASS

E. NASTĘPNY KROK
- Do czasu zmiany implementacji Guardiana uruchamiać synchronizację artefaktów operacyjnie przez:
  `rsync -av --rsync-path=/bin/rsync -e "ssh -p 32122" ...`
- Następnie ponowić `guardian ifg deploy run --yes` po wcześniejszym zsynchronizowaniu `frontend-react/dist`.
