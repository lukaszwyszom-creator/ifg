from __future__ import annotations

from datetime import datetime

from ifg_guardian.core.time_compat import UTC
from time import perf_counter

from ifg_guardian.config import COMPOSE_FILE, TARGET_BRANCH
from ifg_guardian.core.preflight.checks import (
    ALL_CHECKS,
    check_backup_exists,
    check_backup_freshness,
    check_compose_config_validation,
    check_disk_space,
    check_external_volume_correct,
    check_postgres_volume_exists,
)
from ifg_guardian.core.preflight.config import PreflightConfig
from ifg_guardian.core.preflight.models import PreflightContext, PreflightReport


class PreflightEngine:
    """Read-only preflight verification. Does not mutate environment."""

    def __init__(self, *, config: PreflightConfig | None = None) -> None:
        self._config = config or PreflightConfig()

    def run(self, ctx: PreflightContext) -> PreflightReport:
        started = perf_counter()
        report = PreflightReport(
            started_at=datetime.now(UTC),
            mode=ctx.mode.value if hasattr(ctx.mode, "value") else str(ctx.mode),
        )

        config_checks = {
            check_compose_config_validation,
            check_postgres_volume_exists,
            check_external_volume_correct,
            check_backup_exists,
            check_backup_freshness,
            check_disk_space,
        }

        for check_fn in ALL_CHECKS:
            if check_fn in config_checks:
                result = check_fn(ctx, config=self._config)
            else:
                result = check_fn(ctx)
            report.add(result)

        report.finished_at = datetime.now(UTC)
        report.duration_ms = int((perf_counter() - started) * 1000)
        return report

    @classmethod
    def context_from_workflow(
        cls,
        *,
        root,
        mode,
        remote_host: str | None = None,
        remote_path: str | None = None,
        skip_remote: bool = False,
    ) -> PreflightContext:
        return PreflightContext(
            root=root,
            mode=mode,
            remote_host=remote_host,
            remote_path=remote_path,
            compose_file=COMPOSE_FILE,
            env_file=".env.production",
            target_branch=TARGET_BRANCH,
            skip_remote=skip_remote,
        )
