# IFG Container Manager Cutover — Guardian Report

**Workflow ID:** `2026-07-06T214930Z_ifg_container_cutover`  
**Mode:** DRY-RUN  
**Outcome:**   

## Runbook

Source: `docs/runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md`

## Results

| Step | Status |
|------|--------|
| SQL backup | backups/pre_ifg_project_DRYRUN.sql |
| Compose config gate | PASS |
| Safety Gate | GO |
| Artifact Verification Gate | GO |
| Cutover (compose up) | no/simulated |
| Post-health | PASS |
| Guardian verify | PASS |
| Functional attestation | pending |
| Legacy cleanup | skipped |

## Stages

| Stage | Status | Message |
|-------|--------|---------|
| init | pass | cutover dry-run initialized |
| backup | pass | [dry-run] SQL backup simulated |
| git_pull | pass | [dry-run] git pull simulated |
| compose_config_gate | pass | [dry-run] compose config gate simulated |
| preflight | pass | Safety Gate GO, 14 warning(s) |
| legacy_containers | pass | [dry-run] legacy containers check simulated |
| frontend_build | pass | [dry-run] frontend build simulated |
| frontend_artifact_gate | pass | [dry-run] artifact gate simulated GO |
| cutover_up | pass | [dry-run] compose up -d simulated |
| post_health | pass | [dry-run] post-health simulated |
| guardian_verify | pass | [dry-run] guardian verify simulated |
| functional_gate | warn | functional attestation missing (--confirm-functional) |
| cleanup | skip | cleanup not requested (--cleanup) |

## Warnings

- Functional tests not attested — run UI/KSeF checks, then re-run with --confirm-functional --cleanup

## Rollback

```bash
ssh zdalny_admin@ds723 'cd /volume1/docker/ifg_v2/ifg_standalone && docker compose -f "docker/docker-compose.prod.yml" --env-file .env.production stop && git checkout $(cat backups/pre_cutover_commit.txt) -- docker/docker-compose.prod.yml && docker compose -p docker -f "docker/docker-compose.prod.yml" --env-file .env.production up -d'
```

Or:

```bash
python3 scripts/guardian.py ifg cutover rollback --yes
```
