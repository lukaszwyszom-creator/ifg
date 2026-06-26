#!/usr/bin/env python3
"""IFG Guardian — entry point (v3 CLI + legacy flag compatibility)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.cli import main  # noqa: E402

# Re-export for guardian2 dynamic import compatibility
from ifg_guardian import compat as _compat  # noqa: E402

COMPOSE_FILE = _compat.COMPOSE_FILE
DEFAULT_REMOTE_HOST = _compat.DEFAULT_REMOTE_HOST
DEFAULT_REMOTE_PATH = _compat.DEFAULT_REMOTE_PATH
ROOT = _compat.ROOT
parse_compose_service_states = _compat.parse_compose_service_states
service_state_is_healthy = _compat.service_state_is_healthy
service_state_is_restarting = _compat.service_state_is_restarting
service_state_is_running = _compat.service_state_is_running
run_deploy_check = _compat.run_deploy_check
run_ksef_async_check = _compat.run_ksef_async_check
run_repo_sync = _compat.run_repo_sync
check_frontend_dist_freshness = _compat.check_frontend_dist_freshness
check_frontend_worktree_requires_build = _compat.check_frontend_worktree_requires_build
check_ksef_connect_button_fix = _compat.check_ksef_connect_button_fix
check_remote_frontend_dist_freshness = _compat.check_remote_frontend_dist_freshness

if __name__ == "__main__":
    sys.exit(main())
