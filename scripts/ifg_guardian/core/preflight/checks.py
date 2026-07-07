from __future__ import annotations

import re
import subprocess
from pathlib import Path
from time import perf_counter

from ifg_guardian.core.deploy_config import DS723Config
from ifg_guardian.core.git import porcelain_is_dirty
from ifg_guardian.core.preflight.config import PreflightConfig
from ifg_guardian.core.preflight.models import PreflightCheckResult, PreflightContext, PreflightStatus
from ifg_guardian.core.preflight.probes import run_remote_readonly
from ifg_guardian.core.workflow.mode import ExecutionMode


def _result(
    check_id: str,
    label: str,
    status: PreflightStatus,
    description: str,
    *,
    started: float,
    details: dict | None = None,
) -> PreflightCheckResult:
    return PreflightCheckResult(
        check_id=check_id,
        label=label,
        status=status,
        description=description,
        duration_ms=int((perf_counter() - started) * 1000),
        details=details or {},
    )


def check_repo_accessible(ctx: PreflightContext) -> PreflightCheckResult:
    started = perf_counter()
    root = Path(ctx.root)
    if root.is_dir():
        return _result("repo.accessible", "Repo accessible", PreflightStatus.PASS, f"root={root}", started=started)
    return _result("repo.accessible", "Repo accessible", PreflightStatus.FAIL, f"root missing: {root}", started=started)


def check_compose_file_exists(ctx: PreflightContext) -> PreflightCheckResult:
    started = perf_counter()
    path = Path(ctx.root) / ctx.compose_file
    if path.is_file():
        return _result("compose.file", "Compose file exists", PreflightStatus.PASS, str(path), started=started)
    return _result("compose.file", "Compose file exists", PreflightStatus.FAIL, f"missing: {path}", started=started)


def check_env_file_exists(ctx: PreflightContext) -> PreflightCheckResult:
    started = perf_counter()
    local_env = Path(ctx.root) / ctx.env_file
    if local_env.is_file():
        return _result("env.file", ".env exists", PreflightStatus.PASS, str(local_env), started=started)
    return _result(
        "env.file",
        ".env exists",
        PreflightStatus.WARNING,
        f"local {ctx.env_file} not found — will verify on remote",
        started=started,
    )


def check_git_branch(ctx: PreflightContext) -> PreflightCheckResult:
    started = perf_counter()
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=Path(ctx.root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return _result("git.branch", "Correct branch", PreflightStatus.WARNING, str(exc), started=started)

    if result.returncode != 0:
        return _result("git.branch", "Correct branch", PreflightStatus.WARNING, "not a git repository", started=started)

    branch = (result.stdout or "").strip()
    if branch == ctx.target_branch:
        return _result("git.branch", "Correct branch", PreflightStatus.PASS, branch, started=started)

    status = PreflightStatus.FAIL if ctx.mode == ExecutionMode.LIVE else PreflightStatus.WARNING
    return _result(
        "git.branch",
        "Correct branch",
        status,
        f"on '{branch}', expected '{ctx.target_branch}'",
        started=started,
        details={"current": branch, "expected": ctx.target_branch},
    )


DIRTY_TREE_BLOCK_MESSAGE = (
    "Production deployment blocked. Working tree contains uncommitted changes."
)
DIRTY_TREE_OVERRIDE_WARNING = (
    "Production build from dirty working tree (--allow-dirty-build)."
)


def check_git_clean(ctx: PreflightContext) -> PreflightCheckResult:
    started = perf_counter()
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=Path(ctx.root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return _result("git.clean", "Git clean", PreflightStatus.WARNING, str(exc), started=started)

    if result.returncode != 0:
        return _result("git.clean", "Git clean", PreflightStatus.WARNING, "git status unavailable", started=started)

    porcelain = result.stdout or ""
    if not porcelain_is_dirty(porcelain):
        return _result("git.clean", "Git clean", PreflightStatus.PASS, "working tree clean", started=started)

    lines = [ln for ln in porcelain.splitlines() if ln.strip()][:5]
    if ctx.mode == ExecutionMode.LIVE and not ctx.allow_dirty_build:
        return _result(
            "git.clean",
            "Git clean",
            PreflightStatus.FAIL,
            DIRTY_TREE_BLOCK_MESSAGE,
            started=started,
            details={"sample": lines},
        )

    status = PreflightStatus.WARNING
    description = DIRTY_TREE_OVERRIDE_WARNING if ctx.allow_dirty_build else (
        f"uncommitted changes ({len(porcelain.splitlines())} line(s))"
    )
    return _result(
        "git.clean",
        "Git clean",
        status,
        description,
        started=started,
        details={"sample": lines, "allow_dirty_build": ctx.allow_dirty_build},
    )


def _ds723_config(ctx: PreflightContext) -> DS723Config:
    return DS723Config.from_context(remote_host=ctx.remote_host, remote_path=ctx.remote_path)


def check_ssh(ctx: PreflightContext) -> PreflightCheckResult:
    started = perf_counter()
    if ctx.skip_remote:
        return _result("ssh.connectivity", "SSH works", PreflightStatus.WARNING, "remote checks skipped", started=started)

    cfg = _ds723_config(ctx)
    probe = run_remote_readonly(cfg, 'echo "guardian-preflight-ok"\n', label="ssh_ping")
    if probe.ok and "guardian-preflight-ok" in probe.output:
        return _result("ssh.connectivity", "SSH works", PreflightStatus.PASS, cfg.ssh_target, started=started)
    return _result(
        "ssh.connectivity",
        "SSH works",
        PreflightStatus.FAIL,
        probe.error or probe.output or "SSH probe failed",
        started=started,
        details={"host": cfg.ssh_target},
    )


def check_docker_available(ctx: PreflightContext) -> PreflightCheckResult:
    started = perf_counter()
    if ctx.skip_remote:
        return _result("docker.available", "Docker available", PreflightStatus.WARNING, "remote checks skipped", started=started)

    cfg = _ds723_config(ctx)
    probe = run_remote_readonly(cfg, "docker version --format '{{.Server.Version}}'\n", label="docker_version")
    if probe.ok and probe.output:
        return _result("docker.available", "Docker available", PreflightStatus.PASS, probe.output, started=started)
    return _result(
        "docker.available",
        "Docker available",
        PreflightStatus.FAIL,
        probe.error or "docker not available",
        started=started,
    )


def check_compose_available(ctx: PreflightContext) -> PreflightCheckResult:
    started = perf_counter()
    if ctx.skip_remote:
        return _result("compose.available", "Docker Compose available", PreflightStatus.WARNING, "remote checks skipped", started=started)

    cfg = _ds723_config(ctx)
    probe = run_remote_readonly(cfg, "docker compose version --short\n", label="compose_version")
    if probe.ok and probe.output:
        return _result("compose.available", "Docker Compose available", PreflightStatus.PASS, probe.output, started=started)
    return _result(
        "compose.available",
        "Docker Compose available",
        PreflightStatus.FAIL,
        probe.error or "docker compose not available",
        started=started,
    )


def check_compose_config_valid(ctx: PreflightContext) -> PreflightCheckResult:
    started = perf_counter()
    if ctx.skip_remote:
        return _result("compose.config", "Compose config valid", PreflightStatus.WARNING, "remote checks skipped", started=started)

    cfg = _ds723_config(ctx)
    script = (
        f'docker compose -f "{cfg.compose_file}" --env-file "{cfg.env_file}" config >/dev/null 2>&1\n'
        f'echo "config_ok"\n'
    )
    probe = run_remote_readonly(cfg, script, label="compose_config")
    if probe.ok and "config_ok" in probe.output:
        return _result("compose.config", "Compose config valid", PreflightStatus.PASS, "compose config OK", started=started)
    return _result(
        "compose.config",
        "Compose config valid",
        PreflightStatus.FAIL,
        probe.error or probe.output or "compose config failed",
        started=started,
    )


def check_compose_config_validation(ctx: PreflightContext, *, config: PreflightConfig) -> PreflightCheckResult:
    started = perf_counter()
    if ctx.skip_remote:
        return _result("compose.validation", "Compose config validation", PreflightStatus.WARNING, "remote checks skipped", started=started)

    cfg = _ds723_config(ctx)
    script = f'docker compose -f "{cfg.compose_file}" --env-file "{cfg.env_file}" config 2>/dev/null\n'
    probe = run_remote_readonly(cfg, script, label="compose_config_dump")
    if not probe.ok:
        return _result(
            "compose.validation",
            "Compose config validation",
            PreflightStatus.FAIL,
            probe.error or "cannot render compose config",
            started=started,
        )

    text = probe.output
    project_match = re.search(r"^name:\s*(\S+)", text, re.MULTILINE)
    project_name = project_match.group(1) if project_match else "unknown"
    volume_names = re.findall(r"^\s+name:\s+(\S+)", text, re.MULTILINE)

    if "ifg_postgres_data" in volume_names and config.postgres_volume_name not in volume_names:
        return _result(
            "compose.validation",
            "Compose config validation",
            PreflightStatus.FAIL,
            f"resolved volume ifg_postgres_data — expected pin to {config.postgres_volume_name}",
            started=started,
            details={"project": project_name, "volumes": volume_names},
        )

    if config.postgres_volume_name not in volume_names:
        return _result(
            "compose.validation",
            "Compose config validation",
            PreflightStatus.FAIL,
            f"compose config does not reference {config.postgres_volume_name}",
            started=started,
            details={"project": project_name, "volumes": volume_names},
        )

    return _result(
        "compose.validation",
        "Compose config validation",
        PreflightStatus.PASS,
        f"project={project_name}, postgres volume={config.postgres_volume_name}",
        started=started,
        details={"project": project_name, "volumes": volume_names},
    )


def check_postgres_volume_exists(ctx: PreflightContext, *, config: PreflightConfig) -> PreflightCheckResult:
    started = perf_counter()
    if ctx.skip_remote:
        return _result("volume.postgres", "PostgreSQL volume exists", PreflightStatus.WARNING, "remote checks skipped", started=started)

    cfg = _ds723_config(ctx)
    script = f'docker volume inspect {config.postgres_volume_name} --format "{{{{.Name}}}}"\n'
    probe = run_remote_readonly(cfg, script, label="volume_inspect")
    if probe.ok and config.postgres_volume_name in probe.output:
        return _result(
            "volume.postgres",
            "PostgreSQL volume exists",
            PreflightStatus.PASS,
            config.postgres_volume_name,
            started=started,
        )
    return _result(
        "volume.postgres",
        "PostgreSQL volume exists",
        PreflightStatus.FAIL,
        probe.error or f"volume {config.postgres_volume_name} not found",
        started=started,
    )


def check_external_volume_correct(ctx: PreflightContext, *, config: PreflightConfig) -> PreflightCheckResult:
    started = perf_counter()
    compose_path = Path(ctx.root) / ctx.compose_file
    if not compose_path.is_file():
        return _result("volume.external", "External volume correct", PreflightStatus.WARNING, "compose file not local", started=started)

    text = compose_path.read_text(encoding="utf-8")
    has_external = "external: true" in text and config.postgres_volume_name in text
    has_name_ifg = re.search(r"^name:\s*ifg\s*$", text, re.MULTILINE)

    if has_name_ifg and not has_external:
        return _result(
            "volume.external",
            "External volume correct",
            PreflightStatus.FAIL,
            "name: ifg without external pin on postgres volume",
            started=started,
        )

    if has_external:
        return _result(
            "volume.external",
            "External volume correct",
            PreflightStatus.PASS,
            f"external pin to {config.postgres_volume_name}",
            started=started,
        )

    return _result(
        "volume.external",
        "External volume correct",
        PreflightStatus.WARNING,
        "no external pin in compose (pre-migration state acceptable)",
        started=started,
    )


def check_backup_exists(ctx: PreflightContext, *, config: PreflightConfig) -> PreflightCheckResult:
    started = perf_counter()
    if ctx.skip_remote:
        return _result("backup.exists", "Backup exists", PreflightStatus.WARNING, "remote checks skipped", started=started)

    cfg = _ds723_config(ctx)
    script = (
        f'if [ -d "{config.remote_backup_dir}" ]; then '
        f'find "{config.remote_backup_dir}" -maxdepth 2 \\( -name "*.tgz" -o -name "*.dump" -o -name "*.sql" \\) | head -5; '
        f'else echo "NO_BACKUP_DIR"; fi\n'
    )
    probe = run_remote_readonly(cfg, script, label="backup_find")
    if not probe.ok:
        return _result("backup.exists", "Backup exists", PreflightStatus.WARNING, probe.error or "backup probe failed", started=started)

    if "NO_BACKUP_DIR" in probe.output or not probe.output.strip():
        status = PreflightStatus.FAIL if ctx.mode == ExecutionMode.LIVE else PreflightStatus.WARNING
        return _result(
            "backup.exists",
            "Backup exists",
            status,
            f"no backups found in {config.remote_backup_dir}",
            started=started,
        )

    files = [ln for ln in probe.output.splitlines() if ln.strip()]
    return _result(
        "backup.exists",
        "Backup exists",
        PreflightStatus.PASS,
        f"{len(files)} backup artifact(s) found",
        started=started,
        details={"files": files},
    )


def check_backup_freshness(ctx: PreflightContext, *, config: PreflightConfig) -> PreflightCheckResult:
    started = perf_counter()
    if ctx.skip_remote:
        return _result("backup.freshness", "Backup freshness", PreflightStatus.WARNING, "remote checks skipped", started=started)

    cfg = _ds723_config(ctx)
    script = (
        f'find "{config.remote_backup_dir}" -maxdepth 2 \\( -name "*.tgz" -o -name "*.dump" \\) '
        f'-mtime -{config.backup_max_age_days} 2>/dev/null | head -1\n'
    )
    probe = run_remote_readonly(cfg, script, label="backup_fresh")
    if probe.ok and probe.output.strip():
        return _result(
            "backup.freshness",
            "Backup freshness",
            PreflightStatus.PASS,
            f"backup within {config.backup_max_age_days} days",
            started=started,
            details={"path": probe.output.strip()},
        )
    return _result(
        "backup.freshness",
        "Backup freshness",
        PreflightStatus.WARNING,
        f"no backup newer than {config.backup_max_age_days} days",
        started=started,
    )


def check_health_endpoint(ctx: PreflightContext) -> PreflightCheckResult:
    started = perf_counter()
    if ctx.skip_remote:
        return _result("health.endpoint", "Health endpoint", PreflightStatus.WARNING, "remote checks skipped", started=started)

    cfg = _ds723_config(ctx)
    script = 'curl -fsS --max-time 5 http://127.0.0.1:8000/health 2>/dev/null || echo "HEALTH_UNREACHABLE"\n'
    probe = run_remote_readonly(cfg, script, label="health_check")
    if probe.ok and "HEALTH_UNREACHABLE" not in probe.output and probe.output.strip():
        return _result(
            "health.endpoint",
            "Health endpoint",
            PreflightStatus.PASS,
            probe.output[:120],
            started=started,
        )
    return _result(
        "health.endpoint",
        "Health endpoint",
        PreflightStatus.WARNING,
        "health unreachable (stack may be stopped)",
        started=started,
    )


def check_disk_space(ctx: PreflightContext, *, config: PreflightConfig) -> PreflightCheckResult:
    started = perf_counter()
    if ctx.skip_remote:
        return _result("disk.space", "Disk space", PreflightStatus.WARNING, "remote checks skipped", started=started)

    cfg = _ds723_config(ctx)
    script = f'df -BG "{cfg.repo}" | tail -1 | awk \'{{print $4}}\' | tr -d "G"\n'
    probe = run_remote_readonly(cfg, script, label="disk_free")
    if not probe.ok or not probe.output.strip().isdigit():
        return _result("disk.space", "Disk space", PreflightStatus.WARNING, "could not read disk space", started=started)

    free_gb = int(probe.output.strip())
    if free_gb >= config.min_free_disk_gb:
        return _result("disk.space", "Disk space", PreflightStatus.PASS, f"{free_gb} GB free", started=started)
    return _result(
        "disk.space",
        "Disk space",
        PreflightStatus.WARNING,
        f"only {free_gb} GB free (min {config.min_free_disk_gb} GB)",
        started=started,
        details={"free_gb": free_gb},
    )


def check_permissions(ctx: PreflightContext) -> PreflightCheckResult:
    started = perf_counter()
    if ctx.skip_remote:
        return _result("permissions.docker", "Docker permissions", PreflightStatus.WARNING, "remote checks skipped", started=started)

    cfg = _ds723_config(ctx)
    probe = run_remote_readonly(cfg, "docker ps --format '{{.Names}}' | head -3\n", label="docker_ps")
    if probe.ok:
        return _result("permissions.docker", "Docker permissions", PreflightStatus.PASS, "docker ps OK", started=started)
    return _result(
        "permissions.docker",
        "Docker permissions",
        PreflightStatus.FAIL,
        probe.error or "docker ps denied",
        started=started,
    )


def check_remote_env_exists(ctx: PreflightContext) -> PreflightCheckResult:
    started = perf_counter()
    if ctx.skip_remote:
        return _result("env.remote", "Remote .env exists", PreflightStatus.WARNING, "remote checks skipped", started=started)

    cfg = _ds723_config(ctx)
    script = f'test -f "{cfg.env_file}" && echo "env_ok" || echo "env_missing"\n'
    probe = run_remote_readonly(cfg, script, label="remote_env")
    if probe.ok and "env_ok" in probe.output:
        return _result("env.remote", "Remote .env exists", PreflightStatus.PASS, cfg.env_file, started=started)
    return _result(
        "env.remote",
        "Remote .env exists",
        PreflightStatus.FAIL,
        f"missing {cfg.env_file} on remote",
        started=started,
    )


ALL_CHECKS = (
    check_repo_accessible,
    check_compose_file_exists,
    check_env_file_exists,
    check_git_branch,
    check_git_clean,
    check_ssh,
    check_docker_available,
    check_compose_available,
    check_compose_config_valid,
    check_compose_config_validation,
    check_remote_env_exists,
    check_postgres_volume_exists,
    check_external_volume_correct,
    check_backup_exists,
    check_backup_freshness,
    check_health_endpoint,
    check_disk_space,
    check_permissions,
)
