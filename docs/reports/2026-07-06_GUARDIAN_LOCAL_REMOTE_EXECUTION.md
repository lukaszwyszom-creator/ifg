# Guardian — local vs remote execution (architektura)

**Data:** 2026-07-06  
**Incydent:** na DS723+ uruchomiono:

```bash
PYTHONPATH=scripts python3 -m ifg_guardian ifg cutover run --yes
```

Wynik:

```
backup failed: ssh exit 255
```

**Zakres:** analiza `scripts/ifg_guardian/` — bez implementacji, bez deploy, bez LIVE cutover.

---

## 1. Podsumowanie

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy workflow zakłada Mac → SSH → DS723+? | **TAK** — to jest **jedyny** zaimplementowany tryb mutacji cutover |
| Czy jest auto-przełączenie na local executor na DS723+? | **NIE** |
| Dlaczego backup używa SSH na DS723+? | Wszystkie etapy cutover wołają `SSHExecutor.run_remote()` bez detekcji hosta |
| Czy problem to tylko backup? | **NIE** — każdy mutujący etap + preflight (LIVE) + `deploy check` mają ten sam model |

---

## 2. Architektura wykonania (stan obecny)

### 2.1 Model mentalny (dokumentacja)

Oficjalne runbooki i raporty GWO zakładają **operator na Mac mini**, mutacje na DS723+ przez SSH:

- `docs/runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md` — krok 7 Guardian verify: **„Z Mac mini”**
- `docs/reports/GWO_IFG_002A_REPO_CLEAN_STATE_PREP.md` — **„Cutover wykonuje się z Mac mini (SSH → DS723+)”**
- `docs/GUARDIAN_DEPLOY_CHECK.md` — **„Mac mini → DS723+”**

Ręczne kroki runbooku (backup SQL, `compose up`) są opisane **„Wykonaj na DS723+”** — hybryda: shell lokalnie na NAS, Guardian z Maca przez SSH.

### 2.2 Model implementacji (kod)

```
┌─────────────────┐     ssh -p 32122 user@ds723     ┌──────────────────┐
│  Guardian CLI   │ ──────────────────────────────► │     DS723+       │
│  (Mac lub NAS)  │      bash -s < script_body      │  docker/git/...  │
└─────────────────┘                                 └──────────────────┘
        │
        │  ExecutionEngine.host_local = socket.gethostname()  (tylko zapis w transaction)
        │  DeployExecutorContext.remote_host → DS723Config (ds723.env)
        │
        └── Brak porównania host_local vs target → zawsze SSH
```

**Kluczowe komponenty:**

| Komponent | Rola |
|-----------|------|
| `ExecutionEngine._run_stages()` | Tworzy `DeployExecutorContext`, nie ustawia trybu local/remote |
| `SSHExecutor.run_remote()` | `ssh -p {port} {user}@{host} bash -s` + `remote_preamble()` |
| `LocalExecutor` | Subprocess lokalny — **tylko** `IntentExecutor` (npm build, fallback) |
| `DS723Config` | Host z `scripts/ds723.env` (`DS723_HOST=ds723`, port `32122`) |
| `core/execution/*` | Szkic `ExecutionBackend` — **niepodłączony** do `ifg.container.cutover` |

### 2.3 Łańcuch wywołania — cutover LIVE

```
ifg cutover run --yes
  → execute_ifg_container_cutover(assume_yes=True)
  → ExecutionEngine.run(ifg.container.cutover)
  → BackupStage.interpret()
       → _ssh(ctx).run_remote(backup_script(cfg), label="cutover_backup")
            → ssh -p 32122 zdalny_admin@ds723 bash -s
```

`backup_script()` to bash (docker compose, pg_dump) — **poprawny** do uruchomienia na DS723+, ale jest dostarczany przez **SSH**, nawet gdy Guardian już działa na DS723+.

### 2.4 Wszystkie etapy cutover używające SSH (LIVE)

| Stage | `SSHExecutor.run_remote` | Uwagi |
|-------|--------------------------|--------|
| `backup` | ✅ | **tu padł błąd** |
| `git_pull` | ✅ | |
| `compose_config_gate` | ✅ | |
| `preflight` | ✅ (probes) | `skip_remote` tylko w **dry-run** |
| `legacy_containers` | ✅ | |
| `frontend_build` | ✅ | |
| `frontend_artifact_gate` | ✅ | |
| `cutover_up` | ✅ | |
| `post_health` | ✅ | |
| `guardian_verify` | ✅ pośrednio | `run_deploy_check()` → `ssh(ds723)` |
| `cleanup` | ✅ | |
| `init`, `functional_gate`, `summary` | ❌ | lokalne |

**Wniosek:** uruchomienie na DS723+ bez poprawki **nie przejdzie** żadnego mutującego etapu wymagającego SSH do `ds723` — backup to pierwszy taki etap.

### 2.5 Dlaczego `ssh exit 255` na DS723+

Typowe przyczyny SSH do **samego siebie** z hostname `ds723`:

| Przyczyna | Opis |
|-----------|------|
| Brak skonfigurowanego SSH loopback | NAS nie akceptuje `ssh zdalny_admin@ds723` z localhost |
| DNS/host `ds723` | Nie rozwiązuje się lokalnie lub wskazuje inny host |
| Klucze / `known_hosts` | Inny kontekst niż Mac → DS723 |
| Port 32122 | Wymaga jawnego `-p`; executor go podaje, ale połączenie i tak pada |

Exit **255** = ogólny błąd SSH (brak sesji), nie błąd skryptu backupu.

Guardian **nie interpretuje** `host_local` (`DS723plus` z `ExecutionEngine`) — mimo że zapisuje go w `WorkflowTransaction.hosts.local`.

### 2.6 Deploy run (`ifg deploy run`) — ten sam problem

`IntentExecutor` routinguje:

| Komenda | Executor LIVE |
|---------|----------------|
| `git pull` | lokalny git + **SSH** `git pull` na DS723+ |
| `npm run build` | **lokalny** Mac |
| `rsync dist/` | **SSH** do DS723+ |
| `docker compose build/up` | **SSH** |
| `alembic upgrade` | **SSH** |
| `curl /health` | **SSH** |

Na DS723+ deploy LIVE również wykona SSH do `ds723` (oraz rsync do samego siebie).

### 2.7 Preflight — wyjątek częściowy

```python
# container_cutover/stages.py — PreflightStage
skip_remote=_dry_run(ctx)  # tylko dry-run pomija SSH
```

W **LIVE** na DS723+ preflight nadal woła `run_remote_readonly()` → SSH ping, docker, compose config, volume, health.

---

## 3. Odpowiedzi na pytania audytowe

### 3.1 Czy workflow zakłada wyłącznie Mac mini → SSH → DS723+?

**TAK** — w kodzie mutacji cutover/deploy **nie ma** alternatywy.

Dokumentacja operacyjna to potwierdza (Mac jako stacja sterująca). Runbook miesza: kroki ręczne „na DS723+”, Guardian „z Mac mini”.

### 3.2 Czy uruchomienie na DS723+ powinno auto-przełączać na local executor?

**Powinno (docelowo TAK)** — obecnie **NIE**:

- `LocalExecutor` istnieje, ale cutover **nigdy** go nie używa do skryptów bash.
- `host_local` jest rejestrowany, ale **nie wpływa** na routing.
- `core/execution/` (`ExecutionBackend`, `ComposeBackend`) to warstwa przygotowana pod refaktor — **nie zintegrowana** z workflow cutover.

### 3.3 Dlaczego backup nadal używa SSH na DS723+?

Bo `BackupStage` zawsze woła:

```python
ssh = _ssh(ctx)
result = ssh.run_remote(backup_script(cfg), label="cutover_backup")
```

Bez warunku „jeśli już jesteśmy na `cfg.repo` → uruchom bash lokalnie”.

`backup_script()` nie jest problemem — **transport** jest problemem.

### 3.4 Proponowana poprawka — auto local / remote

#### A. Wykrywanie trybu (`ExecutionTarget`)

Dodać do `DeployExecutorContext`:

```python
class ExecutionTarget(str, Enum):
    LOCAL = "local"       # skrypty bash na bieżącym hoście (repo = cfg.repo)
    REMOTE_SSH = "remote" # obecne zachowanie
```

**Heurystyka auto (propozycja):**

| Sygnał | Waga |
|--------|------|
| `Path(cfg.repo).resolve()` istnieje i `Path.cwd()` wewnątrz repo prod | silny LOCAL |
| `socket.gethostname()` pasuje do wzorca DS723 (`DS723plus`, env `GUARDIAN_LOCAL=1`) | średni LOCAL |
| `--remote-host` / `IFG_DS723_HOST` wskazuje host osiągalny tylko z zewnątrz | REMOTE |
| Jawny flag CLI `--local` / `--remote` | nadpisuje auto |

#### B. Wspólny executor skryptów

```python
class ScriptExecutor:
    def run(self, script_body: str, *, label: str) -> IntentResult:
        if target == LOCAL:
            return local_bash(cfg.remote_preamble() + script_body)
        return ssh.run_remote(script_body, label=label)
```

Zastąpić `_ssh(ctx).run_remote(...)` w cutover stages → `script_executor(ctx).run(...)`.

#### C. Preflight

W trybie LOCAL: `skip_remote=True` automatycznie + lokalne odpowiedniki probe (subprocess bez SSH).

#### D. Guardian verify / deploy check

W LOCAL: nie wołać `ssh(ds723)` — czytać git/docker bezpośrednio z `cfg.repo`.

#### E. Deploy run

| Krok | LOCAL na DS723+ |
|------|------------------|
| git pull | tylko lokalny `git pull` w `cfg.repo` |
| npm build | lokalny w `cfg.repo/frontend-react` |
| dist sync | **pomiń** (już na miejscu) |
| docker compose | lokalny subprocess z `remote_preamble` PATH |
| rsync | **pomiń** lub rsync lokalny no-op |

#### F. Transaction / audyt

Zapisać w `WorkflowTransaction`:

```json
"hosts": { "local": "DS723plus", "target": "local", "repo": "/volume1/..." }
```

#### G. Minimalny zakres (MVP)

1. `ScriptExecutor` + detekcja LOCAL  
2. Podmiana w `container_cutover/stages.py` (wszystkie `run_remote`)  
3. `PreflightContext.skip_remote=True` gdy LOCAL  
4. Testy: mock hostname + repo path  
5. Dokumentacja runbook: oba tryby dozwolone

**Ryzyko:** niskie przy zachowaniu REMOTE jako domyślnego gdy detekcja niepewna.  
**Ryzyko deploy run:** średnie — rsync/npm wymagają osobnej logiki LOCAL.

---

## 4. Ocena ryzyka

| Scenariusz | Ryzyko | Komentarz |
|------------|--------|-----------|
| LIVE cutover z DS723+ (stan obecny) | **WYSOKIE** | Zawsze fail na SSH (backup lub później) |
| LIVE cutover z Mac mini (SSH OK) | **NISKIE** | Zaprojektowany path |
| Dry-run z Mac mini | **NISKIE** | Symulacja + preflight skip_remote |
| Dry-run z DS723+ | **ŚREDNIE** | Może przejść (symulacja), ale mylące |
| Poprawka auto LOCAL | **NISKIE–ŚREDNIE** | Wymaga testów na prawdziwym NAS |
| Wymuszenie tylko Mac (bez kodu) | **OPERACYJNE** | Działa dziś, ale łatwo o powtórkę incydentu |

---

## 5. Rekomendacja operacyjna (do wdrożenia poprawki)

**Do czasu poprawki:** LIVE cutover uruchamiać **wyłącznie z Mac mini** z działającym `ssh -p 32122 zdalny_admin@ds723`.

Na DS723+ dopuszczalne: ręczne kroki runbooka lub dry-run (z ostrożnością), nie `ifg cutover run --yes`.

---

## 6. Werdykt A / B

# B) Poprawić workflow tak, aby działał również lokalnie na DS723+.

**Uzasadnienie:**

1. Operator **już** uruchamia Guardiana na DS723+ (Python 3.8, repo prod, docker) — to naturalne środowisko cutover.
2. Runbook **hybrydowy** (ręcznie na NAS, Guardian z Maca) prowadzi do błędów operacyjnych.
3. Architektura ma `LocalExecutor` i `host_local`, ale **nie są spięte** — to luka projektowa, nie zamierzony „Mac-only guard”.
4. SSH do samego siebie jest **kruche** (exit 255) i niepotrzebne, gdy proces już działa na target host.
5. Mac → SSH powinien pozostać **domyślnym trybem zewnętrznym**, ale nie jedynym.

**Do momentu implementacji B:** praktycznie obowiązuje **A** (tylko Mac mini) — z powodu stanu kodu, nie z powodu docelowej architektury.

---

## 7. Pliki kluczowe (referencja)

| Plik | Znaczenie |
|------|-----------|
| `plugins/ifg/container_cutover/stages.py` | `_ssh()` + wszystkie etapy mutacji |
| `core/workflow/executors/ssh_executor.py` | `run_remote()` — jedyne wykonanie bash na DS723+ |
| `core/workflow/engine.py` | `host_local` bez routing |
| `core/deploy_config.py` | `DS723Config`, `remote_preamble()` |
| `core/preflight/probes.py` | `run_remote_readonly()` |
| `modules/deploy.py` | `run_deploy_check()` przez `ssh(host)` |
| `scripts/ds723.env` | `DS723_HOST`, port, repo |

---

*Raport analityczny. Bez zmian w kodzie, deployu i LIVE cutover.*
