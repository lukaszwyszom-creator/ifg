# DS723+ — sudo NOPASSWD dla Docker (IFG deploy)

Data: 2026-06-10  
Host: DS723+ (`zdalny_admin@100.87.84.118:32122`)  
Plik: `/etc/sudoers.d/ifg-docker`

## Cel

Umożliwić `zdalny_admin` wykonywanie poleceń Docker używanych w deployu IFG (`scripts/deploy-ds723.sh`) bez pytania o hasło sudo — **bez** `NOPASSWD: ALL`.

## Ścieżka docker

```
/var/packages/ContainerManager/target/usr/bin/docker
/var/packages/ContainerManager/target/usr/bin/docker-compose
```

(Package Synology Container Manager; `docker compose` to subkomenda `docker`.)

## Zawartość `/etc/sudoers.d/ifg-docker`

```
# IFG deploy: passwordless docker for zdalny_admin
Defaults:zdalny_admin secure_path="/var/packages/ContainerManager/target/usr/bin:/usr/sbin:/usr/bin:/sbin:/bin"
zdalny_admin ALL=(ALL) NOPASSWD: /var/packages/ContainerManager/target/usr/bin/docker
zdalny_admin ALL=(ALL) NOPASSWD: /var/packages/ContainerManager/target/usr/bin/docker-compose
```

Uprawnienia pliku: `440` (root:root).

`secure_path` zapewnia, że `sudo docker ps` znajduje binarkę bez ręcznego `export PATH=...`.

## Walidacja składni

Host Synology nie udostępnia `visudo` w PATH użytkownikowi; walidacja wykonana na pliku docelowym:

```bash
docker run --rm --privileged -v /etc/sudoers.d:/etc/sudoers.d alpine:3.19 \
  sh -c "apk add --no-cache sudo >/dev/null && visudo -cf /etc/sudoers.d/ifg-docker"
```

Wynik:

```
/etc/sudoers.d/ifg-docker: parsed OK
```

## Test

```bash
sudo docker ps
```

Wynik: lista kontenerów (m.in. `docker-api-1`, `docker-worker-1`, `docker-db-1`) — **bez pytania o hasło**.

## Uwagi

- `zdalny_admin` jest już w grupie `docker` — `docker ps` działa też bez sudo; reguła sudo jest potrzebna, gdy skrypt/deploy wymaga `sudo docker ...`.
- Nie dodawano `NOPASSWD: ALL`.
- Plik utworzony przez privileged container mount `/etc/sudoers.d` (standardowa procedura na Synology bez interaktywnego sudo).
