# Guardian2 recover-prod — DS723+

Tryb recovery: `python3 scripts/guardian2.py recover-prod --yes`

Bezpieczne operacje: `up -d db`, `up -d api worker` — **bez** `down -v`, bez resetu DB.

**Wygenerowano:** 2026-06-13 20:26:05 UTC  
**Host:** `ds723`  
**Repo:** `/volume1/docker/ifg_v2/ifg_standalone`  

## Podsumowanie

- **db:** działa
- **api:** działa
- **worker:** działa
- **cloudflared-ifg:** działa
- **health check:** `http://127.0.0.1:8000/health` → OK
- **KSeF Connect blocker:** brak (API+worker OK)

## Notatki

- db ready: docker-db-1         postgres:17         "docker-entrypoint.s…"   db                  4 days ago          Up 2 minutes (healthy)        5432/tcp
- api running: docker-api-1        ifg-api:latest      "uvicorn app.main:ap…"   api                 2 minutes ago       Up About a minute (healthy)   127.0.0.1:8000->8000/tcp
- cloudflared logs zawierają 'error' — sprawdź origin/ingress.

## Git

- branch: `production`
- HEAD: `1706937`

```
?? backups/
?? logs/
```

## Compose services (config)

```
db
api
worker
```

## docker compose ps (przed)

```
NAME                IMAGE               COMMAND                  SERVICE             CREATED             STATUS                        PORTS
docker-api-1        ifg-api:latest      "uvicorn app.main:ap…"   api                 2 minutes ago       Up About a minute (healthy)   127.0.0.1:8000->8000/tcp
docker-db-1         postgres:17         "docker-entrypoint.s…"   db                  4 days ago          Up 2 minutes (healthy)        5432/tcp
docker-worker-1     ifg-api:latest      "sh -c 'python -m ap…"   worker              2 minutes ago       Up About a minute
```

## docker compose ps (po)

```
NAME                IMAGE               COMMAND                  SERVICE             CREATED             STATUS                        PORTS
docker-api-1        ifg-api:latest      "uvicorn app.main:ap…"   api                 2 minutes ago       Up About a minute (healthy)   127.0.0.1:8000->8000/tcp
docker-db-1         postgres:17         "docker-entrypoint.s…"   db                  4 days ago          Up 2 minutes (healthy)        5432/tcp
docker-worker-1     ifg-api:latest      "sh -c 'python -m ap…"   worker              2 minutes ago       Up About a minute
```

## Health

- URL: `http://127.0.0.1:8000/health`
- OK: True

```
{"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_timezone_utc":false,"regon":{"environment":"production","configured":true}}
```

## API logs (tail 120)

```
docker-api-1  | INFO:     Started server process [1]
docker-api-1  | INFO:     Waiting for application startup.
docker-api-1  | INFO:     Application startup complete.
docker-api-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
docker-api-1  | {"timestamp": "2026-06-13T20:24:35.063980+00:00", "level": "INFO", "logger": "app.access", "message": "http.access", "request_id": null, "job_id": null, "method": "GET", "endpoint": "/api/v1/ksef/status", "status_code": 401, "transaction_result": "no_db"}
docker-api-1  | INFO:     172.20.0.1:56078 - "GET /api/v1/ksef/status?nip=9670402857 HTTP/1.1" 401 Unauthorized
docker-api-1  | {"timestamp": "2026-06-13T20:24:35.292480+00:00", "level": "INFO", "logger": "app.access", "message": "http.access", "request_id": null, "job_id": null, "method": "GET", "endpoint": "/ui/login", "status_code": 200, "transaction_result": "no_db"}
docker-api-1  | INFO:     172.20.0.1:56078 - "GET /ui/login HTTP/1.1" 200 OK
docker-api-1  | {"timestamp": "2026-06-13T20:24:35.860795+00:00", "level": "INFO", "logger": "app.access", "message": "http.access", "request_id": null, "job_id": null, "method": "GET", "endpoint": "/ui/assets/index-LZriez43.js", "status_code": 200, "transaction_result": "no_db"}
docker-api-1  | INFO:     172.20.0.1:56078 - "GET /ui/assets/index-LZriez43.js HTTP/1.1" 200 OK
docker-api-1  | INFO:     127.0.0.1:57276 - "GET /health HTTP/1.1" 200 OK
docker-api-1  | INFO:     127.0.0.1:57310 - "GET /health HTTP/1.1" 200 OK
docker-api-1  | INFO:     172.20.0.1:56160 - "GET /health HTTP/1.1" 200 OK
docker-api-1  | INFO:     127.0.0.1:57378 - "GET /health HTTP/1.1" 200 OK
docker-api-1  | INFO:     172.20.0.1:56250 - "GET /health HTTP/1.1" 200 OK
```

## cloudflared-ifg

```
cloudflared-ifg	Up 17 minutes
```

```
2026-06-13T00:11:48Z INF Initiating graceful shutdown due to signal terminated ...
2026-06-13T00:11:49Z ERR failed to run the datagram handler error="context canceled" connIndex=2 event=0 ip=198.41.200.113
2026-06-13T00:11:49Z ERR failed to run the datagram handler error="context canceled" connIndex=0 event=0 ip=198.41.200.63
2026-06-13T00:11:49Z ERR failed to run the datagram handler error="context canceled" connIndex=1 event=0 ip=198.41.192.47
2026-06-13T00:11:50Z ERR failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=2 event=0 ip=198.41.200.113
2026-06-13T00:11:50Z ERR Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=2 event=0 ip=198.41.200.113
2026-06-13T00:11:50Z INF Retrying connection in up to 1s connIndex=2 event=0 ip=198.41.200.113
2026-06-13T00:11:50Z ERR failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=1 event=0 ip=198.41.192.47
2026-06-13T00:11:50Z ERR Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=1 event=0 ip=198.41.192.47
2026-06-13T00:11:50Z INF Retrying connection in up to 1s connIndex=1 event=0 ip=198.41.192.47
2026-06-13T00:11:50Z ERR Connection terminated connIndex=1
2026-06-13T00:11:50Z ERR Connection terminated connIndex=2
2026-06-13T00:11:50Z ERR failed to serve tunnel connection error="accept stream listener encountered a failure while serving" connIndex=0 event=0 ip=198.41.200.63
2026-06-13T00:11:50Z ERR Serve tunnel error error="accept stream listener encountered a failure while serving" connIndex=0 event=0 ip=198.41.200.63
2026-06-13T00:11:50Z INF Retrying connection in up to 1s connIndex=0 event=0 ip=198.41.200.63
2026-06-13T00:11:50Z ERR Connection terminated connIndex=0
2026-06-13T00:11:50Z ERR no more connections active and exiting
2026-06-13T00:11:50Z INF Tunnel server stopped
2026-06-13T00:11:50Z INF Metrics server stopped
2026-06-13T20:08:27Z INF Starting tunnel tunnelID=6a8cca6d-1d4f-4e18-979e-c0def7d120f0
2026-06-13T20:08:27Z INF Version 2026.5.2 (Checksum a157f79263b8be3efe887846edd47b8af37303b4e6959bc2f08019e093b01ae2)
2026-06-13T20:08:27Z INF GOOS: linux, GOVersion: go1.26.3, GoArch: amd64
2026-06-13T20:08:27Z INF Settings: map[config:/home/nonroot/.cloudflared/config.yml cred-file:/home/nonroot/.cloudflared/6a8cca6d-1d4f-4e18-979e-c0def7d120f0.json credentials-file:/home/nonroot/.cloudflared/6a8cca6d-1d4f-4e18-979e-c0def7d120f0.json no-autoupdate:true]
2026-06-13T20:08:27Z INF Generated Connector ID: 506a38f3-6e2d-4e0a-8f1b-06b5869855d6
2026-06-13T20:08:27Z INF Initial protocol quic
2026-06-13T20:08:27Z INF ICMP proxy will use 10.0.0.146 as source for IPv4
2026-06-13T20:08:27Z INF ICMP proxy will use ::1 in zone lo as source for IPv6
2026-06-13T20:08:27Z WRN The user running cloudflared process has a GID (group ID) that is not within ping_group_range. You might need to add that user to a group within that range, or instead update the range to encompass a group the user is already in by modifying /proc/sys/net/ipv4/ping_group_range. Otherwise cloudflared will not be able to ping this network error="Group ID 65532 is not between ping group 1 to 0"
2026-06-13T20:08:27Z WRN ICMP proxy feature is disabled error="cannot create ICMPv4 proxy: Group ID 65532 is not between ping group 1 to 0 nor ICMPv6 proxy: socket: permission denied"
2026/06/13 20:08:27 failed to sufficiently increase receive buffer size (was: 208 kiB, wanted: 7168 kiB, got: 416 kiB). See https://github.com/quic-go/quic-go/wiki/UDP-Buffer-Sizes for details.
2026-06-13T20:08:27Z INF ICMP proxy will use 10.0.0.146 as source for IPv4
2026-06-13T20:08:27Z INF ICMP proxy will use ::1 in zone lo as source for IPv6
2026-06-13T20:08:27Z INF Starting metrics server on [::]:20241/metrics
2026-06-13T20:08:27Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=0 event=0 ip=198.41.200.23
2026-06-13T20:08:27Z INF Registered tunnel connection connIndex=0 connection=81f6a790-2d30-45dc-8550-d000d4acfb8c event=0 ip=198.41.200.23 location=waw06 protocol=quic
2026-06-13T20:08:27Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=1 event=0 ip=198.41.192.27
2026-06-13T20:08:27Z INF Updated to new configuration config="{\"ingress\":[{\"hostname\":\"ifg.ikonastudio.pl\",\"originRequest\":{},\"service\":\"http://127.0.0.1:8000\"},{\"hostname\":\"api.ikonastudio.pl\",\"originRequest\":{},\"service\":\"http://127.0.0.1:8000\"},{\"originRequest\":{},\"service\":\"http_status:404\"}],\"warp-routing\":{\"enabled\":false}}" version=5
2026-06-13T20:08:28Z INF Registered tunnel connection connIndex=1 connection=8cc933e8-babd-4631-baae-98a79974a1fb event=0 ip=198.41.192.27 location=waw03 protocol=quic
2026-06-13T20:08:28Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=2 event=0 ip=198.41.200.233
2026-06-13T20:08:29Z INF Registered tunnel connection connIndex=2 connection=afb1ee71-ba85-49a5-bc3c-e832fe2fdf51 event=0 ip=198.41.200.233 location=waw04 protocol=quic
2026-06-13T20:08:29Z INF Tunnel connection curve preferences: [X25519MLKEM768 CurveID(65074) CurveP256] connIndex=3 event=0 ip=198.41.192.47
2026-06-13T20:08:30Z INF Registered tunnel connection connIndex=3 connection=5eccd1d3-2cd0-491b-9749-5bd20fe53c9c event=0 ip=198.41.192.47 location=waw03 protocol=quic
2026-06-13T20:08:33Z INF +-------------------------------------------------------------------------------------+
2026-06-13T20:08:33Z INF |                               CONNECTIVITY PRE-CHECKS                               |
2026-06-13T20:08:33Z INF +-------------------------------------------------------------------------------------+
2026-06-13T20:08:33Z INF |  COMPONENT         TARGET                     STATUS  DETAILS                       |
2026-06-13T20:08:33Z INF |  DNS Resolution    region1.v2.argotunnel.com  PASS    DNS Resolved successfully     |
2026-06-13T20:08:33Z INF |  DNS Resolution    region2.v2.argotunnel.com  PASS    DNS Resolved successfully     |
2026-06-13T20:08:33Z INF |  UDP Connectivity  region1.v2.argotunnel.com  PASS    QUIC connection successful    |
2026-06-13T20:08:33Z INF |  UDP Connectivity  region2.v2.argotunnel.com  PASS    QUIC connection successful    |
2026-06-13T20:08:33Z INF |  TCP Connectivity  region1.v2.argotunnel.com  PASS    HTTP/2 connection successful  |
2026-06-13T20:08:33Z INF |  TCP Connectivity  region2.v2.argotunnel.com  PASS    HTTP/2 connection successful  |
2026-06-13T20:08:33Z INF |  Cloudflare API    api.cloudflare.com:443     PASS    API is reachable              |
2026-06-13T20:08:33Z INF |                                                                                     |
2026-06-13T20:08:33Z INF |  SUMMARY: Environment is healthy. cloudflared will use 'quic' as primary protocol.  |
2026-06-13T20:08:33Z INF +-------------------------------------------------------------------------------------+
2026-06-13T20:08:33Z INF precheck component="DNS Resolution" details="DNS Resolved successfully" run_id=c91b04f5-6a81-42b0-bd14-b94ca85cda83 status=pass target=region1.v2.argotunnel.com
2026-06-13T20:08:33Z INF precheck component="DNS Resolution" details="DNS Resolved successfully" run_id=c91b04f5-6a81-42b0-bd14-b94ca85cda83 status=pass target=region2.v2.argotunnel.com
2026-06-13T20:08:33Z INF precheck component="UDP Connectivity" details="QUIC connection successful" run_id=c91b04f5-6a81-42b0-bd14-b94ca85cda83 status=pass target=region1.v2.argotunnel.com
2026-06-13T20:08:33Z INF precheck component="UDP Connectivity" details="QUIC connection successful" run_id=c91b04f5-6a81-42b0-bd14-b94ca85cda83 status=pass target=region2.v2.argotunnel.com
2026-06-13T20:08:33Z INF precheck component="TCP Connectivity" details="HTTP/2 connection successful" run_id=c91b04f5-6a81-42b0-bd14-b94ca85cda83 status=pass target=region1.v2.argotunnel.com
2026-06-13T20:08:33Z INF precheck component="TCP Connectivity" details="HTTP/2 connection successful" run_id=c91b04f5-6a81-42b0-bd14-b94ca85cda83 status=pass target=region2.v2.argotunnel.com
2026-06-13T20:08:33Z INF precheck component="Cloudflare API" details="API is reachable" run_id=c91b04f5-6a81-42b0-bd14-b94ca85cda83 status=pass target=api.cloudflare.com:443
2026-06-13T20:08:33Z INF precheck complete hard_fail=false run_id=c91b04f5-6a81-42b0-bd14-b94ca85cda83 suggested_protocol=quic
2026-06-13T20:08:34Z ERR  error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 event=1 ingressRule=0 originService=http://127.0.0.1:8000
2026-06-13T20:08:34Z ERR Request failed error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 dest=https://ifg.ikonastudio.pl/api/v1/ksef/status?nip=9670402857 event=0 ip=198.41.200.23 type=http
2026-06-13T20:10:34Z ERR  error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 event=1 ingressRule=0 originService=http://127.0.0.1:8000
2026-06-13T20:10:34Z ERR Request failed error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 dest=https://ifg.ikonastudio.pl/api/v1/ksef/status?nip=9670402857 event=0 ip=198.41.200.23 type=http
2026-06-13T20:12:34Z ERR  error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: EOF" connIndex=0 event=1 ingressRule=0 originService=http://127.0.0.1:8000
2026-06-13T20:12:34Z ERR Request failed error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: EOF" connIndex=0 dest=https://ifg.ikonastudio.pl/api/v1/ksef/status?nip=9670402857 event=0 ip=198.41.200.23 type=http
2026-06-13T20:14:34Z ERR  error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 event=1 ingressRule=0 originService=http://127.0.0.1:8000
2026-06-13T20:14:34Z ERR Request failed error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 dest=https://ifg.ikonastudio.pl/api/v1/ksef/status?nip=9670402857 event=0 ip=198.41.200.23 type=http
2026-06-13T20:16:34Z ERR  error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 event=1 ingressRule=0 originService=http://127.0.0.1:8000
2026-06-13T20:16:34Z ERR Request failed error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 dest=https://ifg.ikonastudio.pl/api/v1/ksef/status?nip=9670402857 event=0 ip=198.41.200.23 type=http
2026-06-13T20:18:34Z ERR  error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 event=1 ingressRule=0 originService=http://127.0.0.1:8000
2026-06-13T20:18:34Z ERR Request failed error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 dest=https://ifg.ikonastudio.pl/api/v1/ksef/status?nip=9670402857 event=0 ip=198.41.200.23 type=http
2026-06-13T20:20:34Z ERR  error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 event=1 ingressRule=0 originService=http://127.0.0.1:8000
2026-06-13T20:20:34Z ERR Request failed error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: dial tcp 127.0.0.1:8000: connect: connection refused" connIndex=0 dest=https://ifg.ikonastudio.pl/api/v1/ksef/status?nip=9670402857 event=0 ip=198.41.200.23 type=http
2026-06-13T20:22:34Z ERR  error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: read tcp 127.0.0.1:57070->127.0.0.1:8000: read: connection reset by peer" connIndex=0 event=1 ingressRule=0 originService=http://127.0.0.1:8000
2026-06-13T20:22:34Z ERR Request failed error="Unable to reach the origin service. The service may be down or it may not be responding to traffic from cloudflared: read tcp 127.0.0.1:57070->127.0.0.1:8000: read: connection reset by peer" connIndex=0 dest=https://ifg.ikonastudio.pl/api/v1/ksef/status?nip=9670402857 event=0 ip=198.41.200.23 type=http
```

## Cloudflare / sieć

Jeśli API odpowiada tylko wewnątrz compose (`127.0.0.1:8000` na hoście DS723+), tunel **cloudflared-ifg** musi wskazywać ten reachable origin (np. `http://127.0.0.1:8000`) albo współdzielić sieć Docker z kontenerem `api`. Ten krok **nie modyfikuje** config cloudflared — tylko diagnostyka.

## Bezpieczeństwo

- Nie wykonano `docker compose down -v`
- Nie usuwano wolumenów
- Dozwolone: `up -d db`, `up -d api worker`
