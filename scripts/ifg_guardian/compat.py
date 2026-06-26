"""Backward-compatible re-exports for guardian2 and legacy imports."""

from ifg_guardian.config import (
    COMPOSE_FILE,
    DEFAULT_REMOTE_HOST,
    DEFAULT_REMOTE_PATH,
    ROOT,
    TARGET_BRANCH,
)
from ifg_guardian.core.compose import (
    compose_services_healthy,
    parse_compose_service_states,
    service_state_is_healthy,
    service_state_is_restarting,
    service_state_is_running,
)
from ifg_guardian.modules.api_mobile import run_api_guardian
from ifg_guardian.modules.deploy import run_deploy_check
from ifg_guardian.modules.frontend import (
    check_frontend_dist_freshness,
    check_frontend_worktree_requires_build,
    check_ksef_connect_button_fix,
    check_remote_frontend_dist_freshness,
)
from ifg_guardian.modules.ksef import run_ksef_check
from ifg_guardian.modules.repo import run_repo_sync

# Legacy aliases matching old guardian.py function names
run_ksef_async_check = run_ksef_check

__all__ = [
    "COMPOSE_FILE",
    "DEFAULT_REMOTE_HOST",
    "DEFAULT_REMOTE_PATH",
    "ROOT",
    "TARGET_BRANCH",
    "check_frontend_dist_freshness",
    "check_frontend_worktree_requires_build",
    "check_ksef_connect_button_fix",
    "check_remote_frontend_dist_freshness",
    "compose_services_healthy",
    "parse_compose_service_states",
    "run_api_guardian",
    "run_deploy_check",
    "run_ksef_async_check",
    "run_ksef_check",
    "run_repo_sync",
    "service_state_is_healthy",
    "service_state_is_restarting",
    "service_state_is_running",
]
