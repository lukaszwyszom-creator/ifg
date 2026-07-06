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
from ifg_guardian.modules.deploy import run_deploy_check
from ifg_guardian.modules.doctor import run_doctor
from ifg_guardian.modules.ifg_container_cutover import run_ifg_container_cutover, run_ifg_container_cutover_rollback
from ifg_guardian.modules.ifg_deploy_run import run_ifg_deploy_run
from ifg_guardian.modules.ifg_doctor import run_ifg_doctor
from ifg_guardian.modules.ifg_release_plan import run_ifg_release_plan
from ifg_guardian.modules.frontend import run_frontend_check
from ifg_guardian.modules.ksef import run_ksef_check, run_ksef_sync
from ifg_guardian.modules.production import run_prod_health, run_prod_recover
from ifg_guardian.modules.repo import run_repo_clean_dry_run, run_repo_status, run_repo_sync
from ifg_guardian.modules.repo_audit import run_repo_audit
from ifg_guardian.modules.repo_eol_check import run_repo_eol_check
from ifg_guardian.modules.plugins import run_plugin_list
from ifg_guardian.modules.workflow import run_workflow

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
    if argv[0] in ("repo", "deploy", "ksef", "prod", "frontend", "warehouse", "doctor", "ifg", "workflow", "plugin", "version", "-h", "--help"):
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

    # frontend / warehouse / doctor / version
    fe = sub.add_parser("frontend", help="Frontend checks")
    fe_sub = fe.add_subparsers(dest="action", required=True)
    fe_sub.add_parser("check", help="Dist freshness + connect fix")

    wh = sub.add_parser("warehouse", help="Warehouse module checks")
    wh_sub = wh.add_subparsers(dest="action", required=True)
    wh_sub.add_parser("check", help="Warehouse files presence")

    sub.add_parser("doctor", help="Run aggregate read-only checks (legacy → ifg.doctor)")
    sub.add_parser("version", help="Show Guardian version")

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

    ifg_rel = ifg_sub.add_parser("release", help="IFG release workflows")
    ifg_rel_sub = ifg_rel.add_subparsers(dest="release_action", required=True)
    ifg_plan = ifg_rel_sub.add_parser("plan", help="Build release plan (read-only)")
    ifg_plan.add_argument("--fetch", action="store_true", help="git fetch before doctor dependency")
    ifg_plan.add_argument("--json", action="store_true", help="JSON report from WorkflowTransaction")
    ifg_plan.add_argument("--markdown", action="store_true", help="Markdown report from WorkflowTransaction")
    ifg_plan.add_argument("--remote-host", default=None)
    ifg_plan.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    ifg_plan.add_argument("--report", default=None, help="Report path (default: docs/guardian/IFG_RELEASE_PLAN_*.md)")

    ifg_dep = ifg_sub.add_parser("deploy", help="IFG deploy workflows")
    ifg_dep_sub = ifg_dep.add_subparsers(dest="deploy_action", required=True)
    ifg_dep_run = ifg_dep_sub.add_parser("run", help="Run IFG deploy (LIVE requires --yes)")
    ifg_dep_run.add_argument("--dry-run", action="store_true", help="Simulate deploy pipeline")
    ifg_dep_run.add_argument("--yes", action="store_true", help="Confirm LIVE deploy")
    ifg_dep_run.add_argument("--json", action="store_true", help="JSON report from WorkflowTransaction")
    ifg_dep_run.add_argument("--markdown", action="store_true", help="Markdown report from WorkflowTransaction")
    ifg_dep_run.add_argument("--remote-host", default=None)
    ifg_dep_run.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)
    ifg_dep_run.add_argument("--report", default=None, help="Report path (default: docs/guardian/IFG_DEPLOY_RUN_*.md)")

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
    ifg_cut_rb = ifg_cut_sub.add_parser("rollback", help="Rollback to pre-cutover compose project docker")
    ifg_cut_rb.add_argument("--dry-run", action="store_true")
    ifg_cut_rb.add_argument("--yes", action="store_true", help="Confirm LIVE rollback")
    ifg_cut_rb.add_argument("--remote-host", default=None)
    ifg_cut_rb.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH)

    wf = sub.add_parser("workflow", help="Workflow engine commands")
    wf_sub = wf.add_subparsers(dest="action", required=True)
    wf_run = wf_sub.add_parser("run", help="Run a registered workflow")
    wf_run.add_argument("workflow_id", help="Workflow id (e.g. core.ping)")
    wf_run.add_argument("--dry-run", action="store_true", help="Simulate mutating intents")
    wf_run.add_argument("--plan", action="store_true", help="Plan mode (same pipeline as dry-run)")

    plugin = sub.add_parser("plugin", help="Plugin management")
    plugin_sub = plugin.add_subparsers(dest="action", required=True)
    plugin_sub.add_parser("list", help="List registered plugins")

    return parser


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

    if domain == "frontend" and args.action == "check":
        return run_frontend_check()

    if domain == "warehouse" and args.action == "check":
        return run_warehouse_check()

    if domain == "doctor":
        return run_doctor(do_fetch=False)

    if domain == "ifg" and args.action == "doctor":
        if args.json and args.markdown:
            print("Use either --json or --markdown, not both.", file=sys.stderr)
            return 2
        output_format = "json" if args.json else "markdown" if args.markdown else "terminal"
        report = Path(args.report) if args.report else None
        return run_ifg_doctor(
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
        return run_ifg_release_plan(
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
        return run_ifg_deploy_run(
            dry_run=args.dry_run,
            assume_yes=args.yes,
            output_format=output_format,
            report_path=report,
            remote_host=host,
            remote_path=args.remote_path,
        )

    if domain == "ifg" and args.action == "cutover" and args.cutover_action == "run":
        output_format = "markdown" if args.json else "terminal"
        report = Path(args.report) if args.report else None
        return run_ifg_container_cutover(
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

    if domain == "workflow" and args.action == "run":
        return run_workflow(args.workflow_id, dry_run=args.dry_run, plan=args.plan)

    if domain == "plugin" and args.action == "list":
        return run_plugin_list()

    if domain == "version":
        print(f"IFG Guardian {__version__}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
