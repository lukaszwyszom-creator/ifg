from __future__ import annotations

from dataclasses import dataclass

# Remote backup directory on DS723+ (read-only inspection).
DEFAULT_REMOTE_BACKUP_DIR = "/volume1/docker/ifg_v2/backups"

# Backups older than this limit produce WARNING (not blocking by default).
BACKUP_MAX_AGE_DAYS = 7

# Minimum free disk space (GB) on remote repo volume — below → WARNING.
MIN_FREE_DISK_GB = 5

# Expected PostgreSQL volume name (production DS723+).
POSTGRES_VOLUME_NAME = "docker_postgres_data"


@dataclass(frozen=True)
class PreflightConfig:
    remote_backup_dir: str = DEFAULT_REMOTE_BACKUP_DIR
    backup_max_age_days: int = BACKUP_MAX_AGE_DAYS
    min_free_disk_gb: int = MIN_FREE_DISK_GB
    postgres_volume_name: str = POSTGRES_VOLUME_NAME
