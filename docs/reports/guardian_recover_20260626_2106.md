# IFG Guardian — Prod Recover

**Generated:** 2026-06-26 21:06:57 UTC  
**Mode:** DRY-RUN  
**Host:** `ds723`  
**Workflow ID:** `2026-06-26T210657Z_ifg_prod_recover`  

## Status

- branch: `production`
- HEAD: `dry-run`
- db: FAIL
- api: FAIL
- worker: OK
- health: OK
- ksef: OK

## Notes

- [dry-run] would inspect docker compose ps
- [dry-run] sudo docker compose -f docker/docker-compose.prod.yml up -d db
- [dry-run] sudo docker compose -f docker/docker-compose.prod.yml up -d api worker
- [dry-run] curl http://127.0.0.1:8000/health
- [dry-run] verify KSeF openapi endpoint