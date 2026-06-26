from __future__ import annotations

from ifg_guardian.config import FRONTEND_SRC_PREFIX, TARGET_BRANCH
from ifg_guardian.core.repo_audit.models import RepoAuditState
from ifg_guardian.core.risk import FileCategory


def build_recommended_actions(audit: RepoAuditState) -> list[str]:
    actions: list[str] = []

    crlf_files = [
        f.path for f in audit.files
        if f.category == FileCategory.CRLF_ONLY and f.restore_recommended
    ]
    if crlf_files:
        actions.append(
            f"Oczyść szum CRLF ({len(crlf_files)} plików, restore zweryfikowany): "
            f"ręcznie `git restore -- {' '.join(crlf_files[:3])}"
            f"{'...' if len(crlf_files) > 3 else ''}` "
            f"— tylko po Twojej zgodzie (Guardian NIE wykonuje tego automatycznie)."
        )

    unknown_eol = [f.path for f in audit.files if f.category == FileCategory.UNKNOWN_LINE_ENDINGS]
    if unknown_eol:
        actions.append(
            f"Pliki z niejednoznacznymi końcami linii ({len(unknown_eol)}): "
            f"{unknown_eol[0]}{'…' if len(unknown_eol) > 1 else ''} — "
            f"nie używaj git restore bez analizy Verification w raporcie."
        )

    ignore_tracked = [f.path for f in audit.files if f.category == FileCategory.IGNORE and f.status == "M"]
    if ignore_tracked:
        actions.append(
            f"Usuń ze śledzenia pliki dist/env: {', '.join(ignore_tracked)} — "
            f"`git restore -- {' '.join(ignore_tracked[:2])}` lub popraw .gitignore."
        )

    commit_docs = [f.path for f in audit.files if f.category == FileCategory.COMMIT and f.status == "??"]
    if commit_docs:
        actions.append(
            f"Rozważ commit {len(commit_docs)} raportów docs/ (np. po review): "
            f"{commit_docs[0]}" + (f" … +{len(commit_docs)-1}" if len(commit_docs) > 1 else "")
        )

    substantive = [f for f in audit.files if f.category == FileCategory.SUBSTANTIVE]
    if substantive:
        frontend = [f.path for f in substantive if f.path.startswith(FRONTEND_SRC_PREFIX)]
        backend = [f.path for f in substantive if f.path.startswith("app/")]
        if backend:
            actions.append("Backend zmieniony — przed deployem: rebuild api/worker na DS723+.")
        if frontend:
            actions.append("Frontend src zmieniony — przed deployem: `cd frontend-react && npm run build`.")

    if audit.behind > 0:
        actions.append(f"Repo behind origin/{TARGET_BRANCH} ({audit.behind}) — `git pull origin {TARGET_BRANCH}`.")
    if audit.ahead > 0:
        actions.append(f"Repo ahead ({audit.ahead}) — `git push origin {TARGET_BRANCH}` po review.")

    if audit.branch != TARGET_BRANCH:
        actions.append(f"Przełącz na branch `{TARGET_BRANCH}` przed deployem.")

    if not audit.dirty and audit.ahead == 0 and audit.behind == 0 and audit.branch == TARGET_BRANCH:
        actions.append("Worktree czysty i zsynchronizowany — brak wymaganych działań repo.")

    if not actions:
        actions.append("Brak szczegółowych rekomendacji — uruchom `guardian deploy check`.")

    return actions
