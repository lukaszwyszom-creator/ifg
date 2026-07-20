from __future__ import annotations

import argparse
import subprocess
import sys
import warnings
from pathlib import Path

from ifg_guardian import __version__
from ifg_guardian.config import DEFAULT_REMOTE_PATH, TARGET_BRANCH
from ifg_guardian.core.git import resolve_ds723_host
from ifg_guardian.modules.api_mobile import run_api_guardian
from ifg_guardian.modules.deferred_decisions import (
    run_deferred_add,
    run_deferred_cancel,
    run_deferred_done,
    run_deferred_list,
    run_deferred_repair,
    run_deferred_review,
    run_deferred_show,
    run_deferred_validate,
)
from ifg_guardian.modules.deploy import run_deploy_check
from ifg_guardian.modules.doctor import run_doctor
from ifg_guardian.modules.ifg_container_cutover import run_ifg_container_cutover, run_ifg_container_cutover_rollback
from ifg_guardian.modules.ifg_deploy_run import run_ifg_deploy_run
from ifg_guardian.modules.ifg_doctor import run_ifg_doctor
from ifg_guardian.modules.handoff_journal import (
    run_handoff_doctor,
    run_handoff_rebuild_index,
    run_handoff_rebuild_latest,
    run_handoff_validate,
)
from ifg_guardian.modules.ifg_handoff import run_ifg_handoff_latest
from ifg_guardian.modules.ifg_purchase_seller_city_backfill import (
    run_purchase_seller_city_backfill,
)
from ifg_guardian.modules.ifg_release_evaluate import run_ifg_release_evaluate, run_ifg_release_explain
from ifg_guardian.modules.ifg_release_plan import run_ifg_release_plan
from ifg_guardian.modules.ifg_env_reload import run_ifg_env_reload
from ifg_guardian.modules.ifg_smtp import run_ifg_smtp_check, run_ifg_smtp_report, run_ifg_smtp_test
from ifg_guardian.modules.frontend import run_frontend_check
from ifg_guardian.modules.ksef import run_ksef_check, run_ksef_sync
from ifg_guardian.modules.production import run_prod_health, run_prod_recover
from ifg_guardian.modules.production_audit import run_prod_audit
from ifg_guardian.modules.production_maintenance import (
    run_prod_maintenance_end,
    run_prod_maintenance_start,
    run_prod_maintenance_status,
)
from ifg_guardian.modules.production_monitor import (
    run_prod_monitor_check,
    run_prod_monitor_install,
    run_prod_monitor_status,
    run_prod_monitor_uninstall,
)
from ifg_guardian.modules.repo import run_repo_clean_dry_run, run_repo_status, run_repo_sync
from ifg_guardian.modules.repo_audit import run_repo_audit
from ifg_guardian.modules.repo_eol_check import run_repo_eol_check
from ifg_guardian.modules.plugins import run_plugin_list
from ifg_guardian.modules.workflow import run_workflow

PROGRESS_HELP = (
    "Emit [GWO_PROGRESS] live progress logs to stderr "
    "(default: enabled for long workflows such as deploy/recovery)"
)


def _add_progress_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=PROGRESS_HELP,
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Fullscreen live terminal dashboard (requires rich; implies --progress)",
    )


def _run_with_display(run_fn, args, **kwargs) -> int:
    if getattr(args, "dashboard", False):
        if getattr(args, "progress", None) is False:
            print("Cannot combine --dashboard with --no-progress.", file=sys.stderr)
            return 2
        from ifg_guardian.core.dashboard.session import run_with_live_dashboard

        kwargs["progress_enabled"] = True
        return run_with_live_dashboard(lambda: run_fn(**kwargs))

    kwargs.update(_progress_kw(args))
    return run_fn(**kwargs)


LEGACY_FLAGS = {
    "--deploy-check",
    "--ksef-async-check",
    "--repo-sync",
    "--fetch",
    "--remote",
    "--remote-host",
    "--remote-path",
}


def _warn_deprecated(flag: str, replacement: str) -> None:
    warnings.warn(
        f"{flag} is deprecated; use: {replacement}",
        DeprecationWarning,
        stacklevel=3,
    )


def _run_deploy_run(*, dry_run: bool, assume_yes: bool, remote_host: str | None) -> int:
    scripts = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, str(scripts / "guardian2.py"), "deploy-ksef"]
    if dry_run:
        cmd.append("--dry-run")
    if assume_yes:
        cmd.append("--yes")
    if remote_host:
        cmd.extend(["--remote-host", remote_host])
    return subprocess.call(cmd)


def _handle_legacy(argv: list[str]) -> int | None:
    """Map legacy flags to v3 commands. Returns None if not legacy mode."""
    if not argv:
        return None
    if argv[0] in ("repo", "deploy", "ksef", "prod", "frontend", "warehouse", "doctor", "ifg", "workflow", "plugin", "release", "deferred", "handoff", "version", "-h", "--help"):
        return None
    if not any(a in LEGACY_FLAGS or a.startswith("--remote") for a in argv):
        if not any(a.startswith("-") for a in argv):
            return run_api_guardian()
        return None

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--ksef-async-check", action="store_true")
    parser.add_argument("--deploy-check", action="store_true")
    parser.add_argument("--repo-sync", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--remote", choices=["ds723"])
    parser.add_argument("--remote-host", default=None)
    parser.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    args, _ = parser.parse_known_args(argv)

    host = resolve_ds723_host(args.remote_host)

    if args.deploy_check:
        _warn_deprecated("--deploy-check", "guardian deploy check")
        return run_deploy_check(remote_host=host, remote_path=args.remote_path)
    if args.ksef_async_check:
        _warn_deprecated("--ksef-async-check", "guardian ksef check")
        return run_ksef_check()
    if args.repo_sync:
        _warn_deprecated("--repo-sync", "guardian repo status [--fetch] [--remote ds723]")
        return run_repo_sync(
            do_fetch=args.fetch,
            remote=args.remote,
            remote_host=host,
            remote_path=args.remote_path,
        )
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guardian",
        description="IFG Guardian v3 — unified administrative CLI (read-only by default).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 scripts/guardian.py repo audit --fetch\n"
            "  python3 scripts/guardian.py deploy check\n"
            "  python3 scripts/guardian.py ksef check\n"
            "  python3 scripts/guardian.py doctor\n"
            "\n"
            "Legacy (deprecated):\n"
            "  python3 scripts/guardian.py --deploy-check\n"
            "  python3 scripts/guardian.py --repo-sync --fetch --remote ds723\n"
        ),
    )
    parser.add_argument("--version", action="store_true", help="Show version")
    sub = parser.add_subparsers(dest="domain")

    # repo
    repo = sub.add_parser("repo", help="Repository status and housekeeping (read-only)")
    repo_sub = repo.add_subparsers(dest="action", required=True)
    repo_status = repo_sub.add_parser("status", help="Git sync status")
    repo_status.add_argument("--fetch", action="store_true")
    repo_status.add_argument("--remote", choices=["ds723"])
    repo_status.add_argument("--remote-host", default=None)
    repo_status.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    repo_audit = repo_sub.add_parser("audit", help="Classify changes + risk report")
    repo_audit.add_argument("--fetch", action="store_true")
    repo_audit.add_argument("--dry-run", action="store_true", help="Simulate mutating intents (e.g. fetch)")
    repo_audit.add_argument("--json", action="store_true", help="JSON report from WorkflowTransaction")
    repo_audit.add_argument("--markdown", action="store_true", help="Markdown report from WorkflowTransaction")
    repo_audit.add_argument("--report", default=None, help="Report path (default: docs/guardian/REPO_AUDIT_*.md)")
    repo_eol = repo_sub.add_parser("eol-check", help="EOL-only vs logical diff check (repo.eol_check)")
    repo_eol.add_argument("--json", action="store_true", help="JSON output")
    repo_eol.add_argument("--markdown", action="store_true", help="Markdown to stdout")
    repo_eol.add_argument("--report", default=None, help="Report path (default: docs/guardian/EOL_CHECK_*.md)")
    repo_clean = repo_sub.add_parser("clean", help="Dry-run housekeeping preview")
    repo_clean.add_argument("--dry-run", action="store_true", default=True)

    # deploy
    deploy = sub.add_parser("deploy", help="Deploy verification and execution")
    deploy_sub = deploy.add_subparsers(dest="action", required=True)
    dc = deploy_sub.add_parser("check", help="Mac mini vs DS723+ (read-only)")
    dc.add_argument("--remote-host", default=None)
    dc.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    dr = deploy_sub.add_parser("run", help="Run deploy (mutating — guardian2)")
    dr.add_argument("--dry-run", action="store_true")
    dr.add_argument("--yes", action="store_true")
    dr.add_argument("--remote-host", default=None)

    # ksef
    ksef = sub.add_parser("ksef", help="KSeF checks")
    ksef_sub = ksef.add_subparsers(dest="action", required=True)
    ksef_sub.add_parser("check", help="Async sync + bundle check (read-only)")
    ksef_sync = ksef_sub.add_parser("sync", help="KSeF sync (placeholder etap 2)")
    ksef_sync.add_argument("--dry-run", action="store_true", default=True)

    # prod
    prod = sub.add_parser("prod", help="Production DS723+")
    prod_sub = prod.add_subparsers(dest="action", required=True)
    ph = prod_sub.add_parser("health", help="Containers + /health (read-only)")
    ph.add_argument("--remote-host", default=None)
    ph.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    pr = prod_sub.add_parser("recover", help="Recovery (mutating — requires --yes)")
    pr.add_argument("--dry-run", action="store_true")
    pr.add_argument("--yes", action="store_true")
    pr.add_argument("--remote-host", default=None)

    pm = prod_sub.add_parser("maintenance", help="Controlled maintenance mode")
    pm_sub = pm.add_subparsers(dest="maintenance_action", required=True)
    pm_start = pm_sub.add_parser("start", help="Start maintenance (marker then compose stop)")
    pm_start.add_argument("--reason", default=None, help="Optional maintenance reason")
    pm_start.add_argument("--yes", action="store_true")
    pm_start.add_argument("--dry-run", action="store_true")
    pm_start.add_argument("--remote-host", default=None)
    pm_start.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    pm_end = pm_sub.add_parser("end", help="End maintenance (recover then clear marker)")
    pm_end.add_argument("--yes", action="store_true")
    pm_end.add_argument("--dry-run", action="store_true")
    pm_end.add_argument("--remote-host", default=None)
    pm_end.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    pm_sub.add_parser("status", help="Maintenance marker status")

    pa = prod_sub.add_parser("audit", help="Runtime audit trail (JSON Lines)")
    pa.add_argument("--last", type=int, default=None, help="Show last N records")
    pa.add_argument("--since", default=None, help="Filter since duration, e.g. 24h")

    pmon = prod_sub.add_parser("monitor", help="Stateful runtime monitor (Mac mini)")
    pmon_sub = pmon.add_subparsers(dest="monitor_action", required=True)
    pmon_check = pmon_sub.add_parser("check", help="Single monitor iteration")
    pmon_check.add_argument("--remote-host", default=None)
    pmon_check.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    pmon_sub.add_parser("install", help="Install launchd schedule (5 min)")
    pmon_sub.add_parser("status", help="Monitor scheduler status")
    pmon_sub.add_parser("uninstall", help="Remove launchd schedule")

    # frontend / warehouse / doctor / version
    fe = sub.add_parser("frontend", help="Frontend checks")
    fe_sub = fe.add_subparsers(dest="action", required=True)
    fe_sub.add_parser("check", help="Dist freshness + connect fix")

    wh = sub.add_parser("warehouse", help="Warehouse module checks")
    wh_sub = wh.add_subparsers(dest="action", required=True)
    wh_sub.add_parser("check", help="Warehouse files presence")

    sub.add_parser("doctor", help="Run aggregate read-only checks (legacy → ifg.doctor)")
    sub.add_parser("version", help="Show Guardian version")

    rel = sub.add_parser("release", help="Release Engine decision workflows")
    rel_sub = rel.add_subparsers(dest="action", required=True)
    rel_eval = rel_sub.add_parser("evaluate", help="Evaluate deploy readiness (decision only)")
    rel_eval.add_argument("--fetch", action="store_true", help="git fetch before doctor dependency")
    rel_eval.add_argument("--json", action="store_true", help="JSON report from WorkflowTransaction")
    rel_eval.add_argument("--markdown", action="store_true", help="Markdown report from WorkflowTransaction")
    rel_eval.add_argument("--remote-host", default=None)
    rel_eval.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    rel_eval.add_argument("--report", default=None, help="Report path")
    rel_eval.add_argument(
        "--allow-dirty-build",
        action="store_true",
        help="Evaluate with explicit dirty-tree build override",
    )
    _add_progress_args(rel_eval)
    rel_explain = rel_sub.add_parser("explain", help="Explain active release policy rules")
    rel_explain.add_argument("--json", action="store_true", help="Print policy config as JSON")
    rel_sub.add_parser("stage", help="Planned: stage workflow (not implemented yet)")
    rel_sub.add_parser("approve", help="Planned: approval workflow (not implemented yet)")
    rel_sub.add_parser("production", help="Planned: production workflow (not implemented yet)")

    ifg = sub.add_parser("ifg", help="IFG domain workflows")
    ifg_sub = ifg.add_subparsers(dest="action", required=True)
    ifg_doc = ifg_sub.add_parser("doctor", help="IFG environment readiness diagnosis")
    ifg_doc.add_argument("--fetch", action="store_true", help="git fetch before repo checks")
    ifg_doc.add_argument("--dry-run", action="store_true", help="Simulate remote/mutating checks")
    ifg_doc.add_argument("--json", action="store_true", help="JSON report from WorkflowTransaction")
    ifg_doc.add_argument("--markdown", action="store_true", help="Markdown report from WorkflowTransaction")
    ifg_doc.add_argument("--remote-host", default=None)
    ifg_doc.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    ifg_doc.add_argument("--report", default=None, help="Report path (default: docs/guardian/IFG_DOCTOR_*.md)")
    _add_progress_args(ifg_doc)

    ifg_smtp = ifg_sub.add_parser("smtp", help="IFG SMTP diagnostics")
    ifg_smtp_sub = ifg_smtp.add_subparsers(dest="smtp_action", required=True)
    ifg_smtp_check = ifg_smtp_sub.add_parser("check", help="Validate production SMTP on DS723+ (default)")
    ifg_smtp_check.add_argument("--local", action="store_true", help="Use local .env.production instead of DS723+")
    ifg_smtp_check.add_argument("--json", action="store_true", help="JSON report")
    ifg_smtp_check.add_argument("--markdown", action="store_true", help="Markdown report")
    ifg_smtp_check.add_argument("--env-file", default=None, help="Local env file override (with --local)")
    ifg_smtp_check.add_argument("--remote-host", default=None)
    ifg_smtp_check.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    ifg_smtp_check.add_argument("--report", default=None, help="Report path (default: docs/guardian/IFG_SMTP_CHECK_*.md)")
    _add_progress_args(ifg_smtp_check)

    ifg_smtp_test = ifg_smtp_sub.add_parser("test", help="Send diagnostic test mail from production config (default)")
    ifg_smtp_test.add_argument("--local", action="store_true", help="Use local .env.production instead of DS723+")
    ifg_smtp_test.add_argument("--yes", action="store_true", help="Confirm sending test mail")
    ifg_smtp_test.add_argument("--dry-run", action="store_true", help="Validate only — do not send")
    ifg_smtp_test.add_argument("--json", action="store_true", help="JSON report")
    ifg_smtp_test.add_argument("--markdown", action="store_true", help="Markdown report")
    ifg_smtp_test.add_argument("--env-file", default=None, help="Local env file override (with --local)")
    ifg_smtp_test.add_argument("--remote-host", default=None)
    ifg_smtp_test.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    ifg_smtp_test.add_argument("--report", default=None, help="Report path (default: docs/guardian/IFG_SMTP_TEST_*.md)")
    _add_progress_args(ifg_smtp_test)

    ifg_smtp_report = ifg_smtp_sub.add_parser("report", help="Generate SMTP check markdown report (DS723+ default)")
    ifg_smtp_report.add_argument("--local", action="store_true", help="Use local .env.production instead of DS723+")
    ifg_smtp_report.add_argument("--env-file", default=None, help="Local env file override (with --local)")
    ifg_smtp_report.add_argument("--remote-host", default=None)
    ifg_smtp_report.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    ifg_smtp_report.add_argument("--report", default=None, help="Report output path")
    _add_progress_args(ifg_smtp_report)

    ifg_env = ifg_sub.add_parser("env", help="IFG environment administration")
    ifg_env_sub = ifg_env.add_subparsers(dest="env_action", required=True)
    ifg_env_reload = ifg_env_sub.add_parser(
        "reload",
        help="Reload api/worker after .env.production change (no deploy/build)",
    )
    ifg_env_reload.add_argument("--yes", action="store_true", help="Confirm LIVE env reload")
    ifg_env_reload.add_argument("--dry-run", action="store_true", help="Simulate env reload (no compose up)")
    ifg_env_reload.add_argument("--json", action="store_true", help="JSON report")
    ifg_env_reload.add_argument("--markdown", action="store_true", help="Markdown report")
    ifg_env_reload.add_argument("--remote-host", default=None)
    ifg_env_reload.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    ifg_env_reload.add_argument(
        "--report",
        default=None,
        help="Report path (default: docs/reports/YYYY-MM-DD_GWO-GUARDIAN-0079_ENV_RELOAD.md)",
    )
    _add_progress_args(ifg_env_reload)

    ifg_purchase = ifg_sub.add_parser("purchase", help="IFG purchase invoice data workflows")
    ifg_purchase_sub = ifg_purchase.add_subparsers(dest="purchase_action", required=True)
    ifg_purchase_city = ifg_purchase_sub.add_parser(
        "backfill-seller-city",
        help="Backfill seller_snapshot.city for purchase invoices (GWO-IFG-0029)",
    )
    ifg_purchase_city.add_argument(
        "--apply",
        action="store_true",
        help="Write city values (default: dry-run)",
    )
    ifg_purchase_city.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max empty-city candidates to consider",
    )

    ifg_rel = ifg_sub.add_parser("release", help="IFG release workflows")
    ifg_rel_sub = ifg_rel.add_subparsers(dest="release_action", required=True)
    ifg_plan = ifg_rel_sub.add_parser("plan", help="Build release plan (read-only)")
    ifg_plan.add_argument("--fetch", action="store_true", help="git fetch before doctor dependency")
    ifg_plan.add_argument("--json", action="store_true", help="JSON report from WorkflowTransaction")
    ifg_plan.add_argument("--markdown", action="store_true", help="Markdown report from WorkflowTransaction")
    ifg_plan.add_argument("--remote-host", default=None)
    ifg_plan.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    ifg_plan.add_argument("--report", default=None, help="Report path (default: docs/guardian/IFG_RELEASE_PLAN_*.md)")
    _add_progress_args(ifg_plan)

    ifg_dep = ifg_sub.add_parser("deploy", help="IFG deploy workflows")
    ifg_dep_sub = ifg_dep.add_subparsers(dest="deploy_action", required=True)
    ifg_dep_run = ifg_dep_sub.add_parser("run", help="Run IFG deploy (LIVE requires --yes)")
    ifg_dep_run.add_argument("--dry-run", action="store_true", help="Simulate deploy pipeline")
    ifg_dep_run.add_argument("--plan", action="store_true", help="Alias for --dry-run (no mutations)")
    ifg_dep_run.add_argument("--yes", action="store_true", help="Confirm LIVE deploy")
    ifg_dep_run.add_argument(
        "--allow-dirty-build",
        action="store_true",
        help="Allow production build/deploy from dirty working tree (logged override)",
    )
    ifg_dep_run.add_argument("--json", action="store_true", help="JSON report from WorkflowTransaction")
    ifg_dep_run.add_argument("--markdown", action="store_true", help="Markdown report from WorkflowTransaction")
    ifg_dep_run.add_argument("--remote-host", default=None)
    ifg_dep_run.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    ifg_dep_run.add_argument("--report", default=None, help="Report path (default: docs/guardian/IFG_DEPLOY_RUN_*.md)")
    _add_progress_args(ifg_dep_run)

    ifg_cut = ifg_sub.add_parser("cutover", help="Container Manager cutover (project ifg)")
    ifg_cut_sub = ifg_cut.add_subparsers(dest="cutover_action", required=True)
    ifg_cut_run = ifg_cut_sub.add_parser("run", help="Run cutover workflow (LIVE requires --yes)")
    ifg_cut_run.add_argument("--dry-run", action="store_true", help="Simulate all stages")
    ifg_cut_run.add_argument("--yes", action="store_true", help="Confirm LIVE cutover")
    ifg_cut_run.add_argument(
        "--confirm-functional",
        action="store_true",
        help="Operator attests functional IFG tests passed (required for --cleanup)",
    )
    ifg_cut_run.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove legacy docker-* after full validation",
    )
    ifg_cut_run.add_argument("--json", action="store_true", help="Markdown report to stdout")
    ifg_cut_run.add_argument("--remote-host", default=None)
    ifg_cut_run.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    ifg_cut_run.add_argument("--report", default=None, help="Report path (default: docs/guardian/IFG_CONTAINER_CUTOVER_*.md)")
    _add_progress_args(ifg_cut_run)
    ifg_cut_rb = ifg_cut_sub.add_parser("rollback", help="Rollback to pre-cutover compose project docker")
    ifg_cut_rb.add_argument("--dry-run", action="store_true")
    ifg_cut_rb.add_argument("--yes", action="store_true", help="Confirm LIVE rollback")
    ifg_cut_rb.add_argument("--remote-host", default=None)
    ifg_cut_rb.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)

    ifg_handoff = ifg_sub.add_parser("handoff", help="Cursor -> ChatGPT handoff reports")
    ifg_handoff_sub = ifg_handoff.add_subparsers(dest="handoff_action", required=True)
    ifg_handoff_latest = ifg_handoff_sub.add_parser("latest", help="Merge latest markdown reports")
    ifg_handoff_latest.add_argument("--limit", type=int, default=1, help="Max number of merged GWO task reports")
    ifg_handoff_latest.add_argument("--all", action="store_true", help="Ignore handoff state and include all reports")
    ifg_handoff_latest.add_argument("--reset", action="store_true", help="Reset handoff memory before selecting reports")
    ifg_handoff_latest.add_argument(
        "--report",
        default=None,
        help="Explicit workflow report path (skips discovery; must be a handoff candidate)",
    )
    ifg_handoff_latest.add_argument(
        "--clipboard",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Copy generated handoff markdown to clipboard on macOS (pbcopy)",
    )

    wf = sub.add_parser("workflow", help="Workflow engine commands")
    wf_sub = wf.add_subparsers(dest="action", required=True)
    wf_run = wf_sub.add_parser("run", help="Run a registered workflow")
    wf_run.add_argument("workflow_id", help="Workflow id (e.g. core.ping)")
    wf_run.add_argument("--dry-run", action="store_true", help="Simulate mutating intents")
    wf_run.add_argument("--plan", action="store_true", help="Plan mode (same pipeline as dry-run)")
    _add_progress_args(wf_run)

    plugin = sub.add_parser("plugin", help="Plugin management")
    plugin_sub = plugin.add_subparsers(dest="action", required=True)
    plugin_sub.add_parser("list", help="List registered plugins")

    deferred = sub.add_parser("deferred", help="Guardian Deferred Decisions (GDD) registry")
    deferred_sub = deferred.add_subparsers(dest="action", required=True)

    def_add = deferred_sub.add_parser("add", help="Add a deferred decision entry")
    def_add.add_argument("--project", default="IFG", help="Project name (default: IFG)")
    def_add.add_argument("--module", required=True, help="Module or area")
    def_add.add_argument(
        "--type",
        required=True,
        dest="decision_type",
        help="Architecture / UX / Performance / Refactor / Technical Debt / Process / Other",
    )
    def_add.add_argument("--priority", default="Medium", help="Low / Medium / High")
    def_add.add_argument("--reason", required=True, dest="defer_reason", help="Why deferred")
    def_add.add_argument("--description", required=True, help="Decision description")
    def_add.add_argument("--review-when", required=True, dest="review_when", help="When to revisit")
    def_add.add_argument("--source", required=True, help="Source GWO/report/review")

    def_list = deferred_sub.add_parser("list", help="List deferred decisions")
    def_list.add_argument("--project", default=None, help="Filter by project")
    def_list.add_argument("--status", default="OPEN", help="OPEN / DONE / CANCELLED / all")
    def_list.add_argument("--type", default=None, dest="decision_type", help="Filter by type")
    def_list.add_argument("--priority", default=None, help="Filter by priority")
    def_list.add_argument("--json", action="store_true", help="JSON output")

    def_show = deferred_sub.add_parser("show", help="Show one deferred decision")
    def_show.add_argument("item_id", help="GDD ID, e.g. GDD-0001")
    def_show.add_argument("--json", action="store_true", help="JSON output")

    def_done = deferred_sub.add_parser("done", help="Mark deferred decision as DONE")
    def_done.add_argument("item_id", help="GDD ID")

    def_cancel = deferred_sub.add_parser("cancel", help="Mark deferred decision as CANCELLED")
    def_cancel.add_argument("item_id", help="GDD ID")

    def_review = deferred_sub.add_parser("review", help="Review open deferred decisions")
    def_review.add_argument("--project", default=None, help="Filter by project (default: all)")
    def_review.add_argument("--json", action="store_true", help="JSON output")
    def_review.add_argument("--markdown", action="store_true", help="Markdown output")
    def_review.add_argument("--report", default=None, help="Write markdown report to path")

    deferred_sub.add_parser("validate", help="Validate GDD registry integrity")

    def_repair = deferred_sub.add_parser("repair", help="Propose or apply GDD registry repairs")
    def_repair.add_argument("--dry-run", action="store_true", help="Show proposed repairs only")
    def_repair.add_argument("--yes", action="store_true", help="Apply unambiguous repairs")

    handoff = sub.add_parser("handoff", help="Workflow handoff journal (Artifact Engine v1)")
    handoff_sub = handoff.add_subparsers(dest="action", required=True)
    handoff_sub.add_parser("validate", help="Validate handoff journal integrity")
    handoff_sub.add_parser("rebuild-index", help="Rebuild index.json from handoff files")
    handoff_sub.add_parser("rebuild-latest", help="Rebuild latest.md from latest handoff")
    handoff_sub.add_parser("doctor", help="Diagnose handoff journal issues")

    return parser


def _progress_kw(args) -> dict:
    progress = getattr(args, "progress", None)
    return {"progress_enabled": progress} if progress is not None else {}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    legacy = _handle_legacy(argv)
    if legacy is not None:
        return legacy

    parser = build_parser()
    if not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)

    if getattr(args, "version", False):
        print(f"IFG Guardian {__version__}")
        return 0

    domain = getattr(args, "domain", None)
    if domain is None:
        parser.print_help()
        return 0

    host = resolve_ds723_host(getattr(args, "remote_host", None))

    if domain == "repo":
        if args.action == "status":
            return run_repo_sync(
                do_fetch=args.fetch,
                remote=args.remote,
                remote_host=host,
                remote_path=args.remote_path,
            )
        if args.action == "audit":
            if args.json and args.markdown:
                print("Use either --json or --markdown, not both.", file=sys.stderr)
                return 2
            output_format = "json" if args.json else "markdown" if args.markdown else "terminal"
            report = Path(args.report) if args.report else None
            return run_repo_audit(
                do_fetch=args.fetch,
                dry_run=args.dry_run,
                output_format=output_format,
                report_path=report,
            )
        if args.action == "eol-check":
            if args.json and args.markdown:
                print("Use either --json or --markdown, not both.", file=sys.stderr)
                return 2
            output_format = "json" if args.json else "markdown" if args.markdown else "terminal"
            report = Path(args.report) if args.report else None
            return run_repo_eol_check(
                output_format=output_format,
                report_path=report,
            )
        if args.action == "clean":
            return run_repo_clean_dry_run()

    if domain == "deploy":
        if args.action == "check":
            return run_deploy_check(remote_host=host, remote_path=args.remote_path)
        if args.action == "run":
            return _run_deploy_run(dry_run=args.dry_run, assume_yes=args.yes, remote_host=host)

    if domain == "ksef":
        if args.action == "check":
            return run_ksef_check()
        if args.action == "sync":
            return run_ksef_sync(dry_run=True)

    if domain == "prod":
        if args.action == "health":
            return run_prod_health(remote_host=host, remote_path=args.remote_path)
        if args.action == "recover":
            if not args.yes and not args.dry_run:
                print("prod recover wymaga --yes (operacja mutująca).", file=sys.stderr)
                return 1
            return run_prod_recover(dry_run=args.dry_run, assume_yes=args.yes, remote_host=host)
        if args.action == "maintenance":
            if args.maintenance_action == "status":
                return run_prod_maintenance_status()
            if args.maintenance_action == "start":
                return run_prod_maintenance_start(
                    reason=args.reason,
                    assume_yes=args.yes,
                    dry_run=args.dry_run,
                    remote_host=host,
                    remote_path=args.remote_path,
                )
            if args.maintenance_action == "end":
                return run_prod_maintenance_end(
                    assume_yes=args.yes,
                    dry_run=args.dry_run,
                    remote_host=host,
                    remote_path=args.remote_path,
                )
        if args.action == "audit":
            since_hours = None
            if args.since:
                raw = str(args.since).strip().lower()
                if raw.endswith("h"):
                    since_hours = float(raw[:-1])
                else:
                    since_hours = float(raw)
            return run_prod_audit(last=args.last, since_hours=since_hours)
        if args.action == "monitor":
            if args.monitor_action == "check":
                return run_prod_monitor_check(remote_host=host, remote_path=args.remote_path)
            if args.monitor_action == "install":
                return run_prod_monitor_install()
            if args.monitor_action == "status":
                return run_prod_monitor_status()
            if args.monitor_action == "uninstall":
                return run_prod_monitor_uninstall()

    if domain == "frontend" and args.action == "check":
        return run_frontend_check()

    if domain == "warehouse" and args.action == "check":
        return run_warehouse_check()

    if domain == "doctor":
        return run_doctor(do_fetch=False)

    if domain == "release":
        if args.action == "evaluate":
            if args.json and args.markdown:
                print("Use either --json or --markdown, not both.", file=sys.stderr)
                return 2
            output_format = "json" if args.json else "markdown" if args.markdown else "terminal"
            report = Path(args.report) if args.report else None
            return _run_with_display(
                run_ifg_release_evaluate,
                args,
                do_fetch=args.fetch,
                output_format=output_format,
                report_path=report,
                remote_host=host,
                remote_path=args.remote_path,
                allow_dirty_build=args.allow_dirty_build,
            )
        if args.action == "explain":
            return run_ifg_release_explain(output_format="json" if args.json else "terminal")
        print(f"release {args.action} not implemented yet", file=sys.stderr)
        return 2

    if domain == "ifg" and args.action == "smtp":
        if getattr(args, "json", False) and getattr(args, "markdown", False):
            print("Use either --json or --markdown, not both.", file=sys.stderr)
            return 2
        output_format = "json" if getattr(args, "json", False) else "markdown" if getattr(args, "markdown", False) else "terminal"
        report = Path(args.report) if getattr(args, "report", None) else None
        env_file = Path(args.env_file) if getattr(args, "env_file", None) else None
        if args.smtp_action == "check":
            return _run_with_display(
                run_ifg_smtp_check,
                args,
                use_local=args.local,
                output_format=output_format,
                report_path=report,
                env_file=env_file,
                remote_host=host,
                remote_path=args.remote_path,
            )
        if args.smtp_action == "test":
            return _run_with_display(
                run_ifg_smtp_test,
                args,
                assume_yes=args.yes,
                dry_run=args.dry_run,
                use_local=args.local,
                output_format=output_format,
                report_path=report,
                env_file=env_file,
                remote_host=host,
                remote_path=args.remote_path,
            )
        if args.smtp_action == "report":
            return _run_with_display(
                run_ifg_smtp_report,
                args,
                use_local=args.local,
                report_path=report,
                env_file=env_file,
                remote_host=host,
                remote_path=args.remote_path,
            )
        print(f"smtp {args.smtp_action} not implemented", file=sys.stderr)
        return 2

    if domain == "ifg" and args.action == "env" and args.env_action == "reload":
        if getattr(args, "json", False) and getattr(args, "markdown", False):
            print("Use either --json or --markdown, not both.", file=sys.stderr)
            return 2
        output_format = (
            "json"
            if getattr(args, "json", False)
            else "markdown"
            if getattr(args, "markdown", False)
            else "terminal"
        )
        report = Path(args.report) if getattr(args, "report", None) else None
        return _run_with_display(
            run_ifg_env_reload,
            args,
            dry_run=args.dry_run,
            assume_yes=args.yes,
            output_format=output_format,
            report_path=report,
            remote_host=host,
            remote_path=args.remote_path,
        )

    if domain == "ifg" and args.action == "doctor":
        if args.json and args.markdown:
            print("Use either --json or --markdown, not both.", file=sys.stderr)
            return 2
        output_format = "json" if args.json else "markdown" if args.markdown else "terminal"
        report = Path(args.report) if args.report else None
        return _run_with_display(
            run_ifg_doctor,
            args,
            do_fetch=args.fetch,
            dry_run=args.dry_run,
            output_format=output_format,
            report_path=report,
            remote_host=host,
            remote_path=args.remote_path,
        )

    if domain == "ifg" and args.action == "release" and args.release_action == "plan":
        if args.json and args.markdown:
            print("Use either --json or --markdown, not both.", file=sys.stderr)
            return 2
        output_format = "json" if args.json else "markdown" if args.markdown else "terminal"
        report = Path(args.report) if args.report else None
        return _run_with_display(
            run_ifg_release_plan,
            args,
            do_fetch=args.fetch,
            output_format=output_format,
            report_path=report,
            remote_host=host,
            remote_path=args.remote_path,
        )

    if domain == "ifg" and args.action == "deploy" and args.deploy_action == "run":
        if args.json and args.markdown:
            print("Use either --json or --markdown, not both.", file=sys.stderr)
            return 2
        output_format = "json" if args.json else "markdown" if args.markdown else "terminal"
        report = Path(args.report) if args.report else None
        return _run_with_display(
            run_ifg_deploy_run,
            args,
            dry_run=args.dry_run or args.plan,
            assume_yes=args.yes,
            allow_dirty_build=args.allow_dirty_build,
            output_format=output_format,
            report_path=report,
            remote_host=host,
            remote_path=args.remote_path,
        )

    if domain == "ifg" and args.action == "cutover" and args.cutover_action == "run":
        output_format = "markdown" if args.json else "terminal"
        report = Path(args.report) if args.report else None
        return _run_with_display(
            run_ifg_container_cutover,
            args,
            dry_run=args.dry_run,
            assume_yes=args.yes,
            confirm_functional=args.confirm_functional,
            cleanup=args.cleanup,
            output_format=output_format,
            report_path=report,
            remote_host=host,
            remote_path=args.remote_path,
        )

    if domain == "ifg" and args.action == "cutover" and args.cutover_action == "rollback":
        return run_ifg_container_cutover_rollback(
            dry_run=args.dry_run,
            assume_yes=args.yes,
            remote_host=host,
            remote_path=args.remote_path,
        )

    if domain == "ifg" and args.action == "handoff" and args.handoff_action == "latest":
        if args.limit < 1:
            print("--limit must be >= 1", file=sys.stderr)
            return 2
        return run_ifg_handoff_latest(
            limit=args.limit,
            copy_to_clipboard=args.clipboard,
            include_all=args.all,
            reset_state=args.reset,
            explicit_report=args.report,
        )

    if domain == "ifg" and args.action == "purchase" and args.purchase_action == "backfill-seller-city":
        return run_purchase_seller_city_backfill(apply=args.apply, limit=args.limit)

    if domain == "workflow" and args.action == "run":
        return _run_with_display(
            run_workflow,
            args,
            workflow_id=args.workflow_id,
            dry_run=args.dry_run,
            plan=args.plan,
        )

    if domain == "plugin" and args.action == "list":
        return run_plugin_list()

    if domain == "deferred":
        if args.action == "add":
            return run_deferred_add(
                project=args.project,
                module=args.module,
                decision_type=args.decision_type,
                priority=args.priority,
                defer_reason=args.defer_reason,
                description=args.description,
                review_when=args.review_when,
                source=args.source,
            )
        if args.action == "list":
            status = None if str(args.status).lower() == "all" else args.status
            output_format = "json" if args.json else "terminal"
            return run_deferred_list(
                project=args.project,
                status=status,
                decision_type=args.decision_type,
                priority=args.priority,
                output_format=output_format,
            )
        if args.action == "show":
            output_format = "json" if args.json else "terminal"
            return run_deferred_show(
                item_id=args.item_id,
                output_format=output_format,
            )
        if args.action == "done":
            return run_deferred_done(item_id=args.item_id)
        if args.action == "cancel":
            return run_deferred_cancel(item_id=args.item_id)
        if args.action == "review":
            if args.json and args.markdown:
                print("Use either --json or --markdown, not both.", file=sys.stderr)
                return 2
            review_format = "json" if args.json else "markdown" if args.markdown else "terminal"
            report = Path(args.report) if args.report else None
            return run_deferred_review(
                project=args.project,
                report_path=report,
                output_format=review_format,
            )
        if args.action == "validate":
            return run_deferred_validate()
        if args.action == "repair":
            if args.dry_run and args.yes:
                print("Use either --dry-run or --yes, not both.", file=sys.stderr)
                return 2
            if not args.dry_run and not args.yes:
                print("Specify --dry-run or --yes.", file=sys.stderr)
                return 2
            return run_deferred_repair(apply=args.yes)

    if domain == "handoff":
        if args.action == "validate":
            return run_handoff_validate()
        if args.action == "rebuild-index":
            return run_handoff_rebuild_index()
        if args.action == "rebuild-latest":
            return run_handoff_rebuild_latest()
        if args.action == "doctor":
            return run_handoff_doctor()

    if domain == "version":
        print(f"IFG Guardian {__version__}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
