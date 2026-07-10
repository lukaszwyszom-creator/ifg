from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ifg_guardian.core.deploy_config import DS723Config

DIST_REL = "frontend-react/dist"
INDEX_REL = f"{DIST_REL}/index.html"
ASSETS_REL = f"{DIST_REL}/assets"

ARTIFACT_GATE_LOCAL_CMD = "python3 scripts/ifg_guardian_frontend_artifact_gate.py local"
ARTIFACT_GATE_REMOTE_CMD = "python3 scripts/ifg_guardian_frontend_artifact_gate.py remote"

GO_MARKER = "ARTIFACT_GATE_STATUS=GO"
NO_GO_MARKER = "ARTIFACT_GATE_STATUS=NO_GO"


@dataclass(frozen=True)
class ArtifactGateResult:
    ok: bool
    status: str
    message: str
    index_html: bool = False
    assets_dir: bool = False
    js_count: int = 0

    @property
    def is_go(self) -> bool:
        return self.ok and self.status == "GO"


def verify_local_dist(root: Path) -> ArtifactGateResult:
    """Verify frontend dist artifacts under repository root (Mac mini)."""
    dist = root / DIST_REL
    index = dist / "index.html"
    assets = dist / "assets"
    problems: list[str] = []
    js_count = 0

    if not index.is_file():
        problems.append(f"missing {INDEX_REL}")
    if not assets.is_dir():
        problems.append(f"missing {ASSETS_REL}/")
    else:
        js_count = len(list(assets.glob("*.js")))
        if js_count < 1:
            problems.append(f"missing {ASSETS_REL}/*.js")

    if problems:
        return ArtifactGateResult(
            ok=False,
            status="NO_GO",
            message="; ".join(problems),
            index_html=index.is_file(),
            assets_dir=assets.is_dir(),
            js_count=js_count,
        )
    return ArtifactGateResult(
        ok=True,
        status="GO",
        message="frontend artifacts OK",
        index_html=True,
        assets_dir=True,
        js_count=js_count,
    )


def parse_artifact_gate_output(output: str) -> ArtifactGateResult:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    status = ""
    message = ""
    index_html = False
    assets_dir = False
    js_count = 0

    for line in lines:
        if line.startswith("ARTIFACT_GATE_STATUS="):
            status = line.split("=", 1)[1].strip()
        elif line.startswith("ARTIFACT_GATE_MESSAGE="):
            message = line.split("=", 1)[1].strip()
        elif line.startswith("ARTIFACT_INDEX_HTML="):
            index_html = line.split("=", 1)[1].strip().lower() in ("1", "true", "yes", "present")
        elif line.startswith("ARTIFACT_ASSETS_DIR="):
            assets_dir = line.split("=", 1)[1].strip().lower() in ("1", "true", "yes", "present")
        elif line.startswith("ARTIFACT_JS_COUNT="):
            try:
                js_count = int(line.split("=", 1)[1].strip())
            except ValueError:
                js_count = 0

    if GO_MARKER in output or status == "GO":
        return ArtifactGateResult(
            ok=True,
            status="GO",
            message=message or "frontend artifacts OK",
            index_html=True if index_html or GO_MARKER in output else index_html,
            assets_dir=True if assets_dir or GO_MARKER in output else assets_dir,
            js_count=js_count,
        )
    if NO_GO_MARKER in output or status == "NO_GO":
        return ArtifactGateResult(
            ok=False,
            status="NO_GO",
            message=message or "artifact verification failed",
            index_html=index_html,
            assets_dir=assets_dir,
            js_count=js_count,
        )
    return ArtifactGateResult(
        ok=False,
        status="NO_GO",
        message=message or "artifact gate output missing GO marker",
        index_html=index_html,
        assets_dir=assets_dir,
        js_count=js_count,
    )


def remote_frontend_build_script(repo: str) -> str:
    return (
        f'cd "{repo}/frontend-react"\n'
        "npm run build\n"
    )


def remote_artifact_verify_script(repo: str) -> str:
    return (
        f'cd "{repo}"\n'
        f'DIST="{DIST_REL}"\n'
        'fail=0\n'
        'index_ok=0\n'
        'assets_ok=0\n'
        'js_count=0\n'
        'if [ -f "$DIST/index.html" ]; then index_ok=1; else fail=1; fi\n'
        'if [ -d "$DIST/assets" ]; then assets_ok=1; else fail=1; fi\n'
        'if [ "$assets_ok" = "1" ]; then\n'
        '  js_count=$(ls "$DIST/assets"/*.js 2>/dev/null | wc -l | tr -d " ")\n'
        '  if [ "${js_count:-0}" -lt 1 ]; then fail=1; fi\n'
        'fi\n'
        'if [ "$fail" -ne 0 ]; then\n'
        '  echo "ARTIFACT_GATE_STATUS=NO_GO"\n'
        '  echo "ARTIFACT_GATE_MESSAGE=missing or incomplete frontend-react/dist (index.html and assets/*.js required)"\n'
        f'  echo "ARTIFACT_INDEX_HTML=$([ -f \\"$DIST/index.html\\" ] && echo present || echo missing)"\n'
        f'  echo "ARTIFACT_ASSETS_DIR=$([ -d \\"$DIST/assets\\" ] && echo present || echo missing)"\n'
        '  echo "ARTIFACT_JS_COUNT=${js_count:-0}"\n'
        '  exit 1\n'
        'fi\n'
        'echo "ARTIFACT_GATE_STATUS=GO"\n'
        'echo "ARTIFACT_GATE_MESSAGE=frontend artifacts OK"\n'
        'echo "ARTIFACT_INDEX_HTML=present"\n'
        'echo "ARTIFACT_ASSETS_DIR=present"\n'
        'echo "ARTIFACT_JS_COUNT=${js_count}"\n'
    )


def build_rsync_dist_command(*, remote_path: str | None = None) -> str:
    cfg = DS723Config.from_context(remote_path=remote_path)
    ssh_target = cfg.ssh_target
    port = cfg.port
    dest = f"{ssh_target}:{cfg.repo}/frontend-react/dist/"
    rsync_path = f" --rsync-path={cfg.remote_rsync_path}" if cfg.remote_rsync_path else ""
    return f'rsync -av{rsync_path} -e "ssh -p {port}" frontend-react/dist/ {dest}'
