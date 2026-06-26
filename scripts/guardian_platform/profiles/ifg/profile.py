from __future__ import annotations

from guardian_platform.core.profiles.base import GuardianProfile
from guardian_platform.core.registry.commands import CommandSpec
from guardian_platform.core.registry.profiles import ProfileRegistrationContext
from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.profiles.ifg.commands.deploy_check import run_deploy_check
from guardian_platform.profiles.ifg.commands.deploy_run import run_deploy_run_cmd
from guardian_platform.profiles.ifg.commands.doctor import run_doctor
from guardian_platform.profiles.ifg.commands.repo_audit import run_repo_audit_cmd
from guardian_platform.profiles.ifg.commands.frontend_check import run_frontend_check
from guardian_platform.profiles.ifg.commands.ksef_check import run_ksef_check
from guardian_platform.profiles.ifg.commands.prod_health import run_prod_health
from guardian_platform.profiles.ifg.commands.prod_recover import run_prod_recover_cmd
from guardian_platform.profiles.ifg.commands.repo_cleanup import run_repo_cleanup_cmd
from guardian_platform.profiles.ifg.workflows.deploy_run import IFG_DEPLOY_RUN_WORKFLOW
from guardian_platform.profiles.ifg.workflows.prod_recover import IFG_PROD_RECOVER_WORKFLOW


def _cmd_ping(ctx: CommandContext) -> int:
    print("ifg profile active (M3 mutating)")
    return 0


class IFGProfile(GuardianProfile):
    @property
    def id(self) -> str:
        return "ifg"

    @property
    def version(self) -> str:
        return "0.5.1-cleanup-boundary"

    @property
    def description(self) -> str:
        return "IFG profile — cleanup advisor + M3 commands"

    def register(self, ctx: ProfileRegistrationContext) -> None:
        ctx.workflows.register(IFG_DEPLOY_RUN_WORKFLOW)
        ctx.workflows.register(IFG_PROD_RECOVER_WORKFLOW)

        specs = [
            CommandSpec("ifg", ("ping",), _cmd_ping, help="IFG profile heartbeat"),
            CommandSpec("ifg", ("doctor",), run_doctor, help="IFG environment diagnosis (read-only)"),
            CommandSpec("ifg", ("deploy", "check"), run_deploy_check, help="Mac vs remote deploy readiness"),
            CommandSpec(
                "ifg",
                ("deploy", "run"),
                run_deploy_run_cmd,
                help="Execute IFG deploy pipeline",
                mutating=True,
                supports_dry_run=True,
            ),
            CommandSpec("ifg", ("frontend", "check"), run_frontend_check, help="Frontend dist freshness"),
            CommandSpec("ifg", ("ksef", "check"), run_ksef_check, help="KSeF async sync checks"),
            CommandSpec("ifg", ("prod", "health"), run_prod_health, help="Remote containers + /health"),
            CommandSpec(
                "ifg",
                ("prod", "recover"),
                run_prod_recover_cmd,
                help="Recover production services on DS723+",
                mutating=True,
                supports_dry_run=True,
            ),
            CommandSpec("ifg", ("repo", "audit"), run_repo_audit_cmd, help="Repository audit with IFG rules"),
            CommandSpec(
                "ifg",
                ("repo", "cleanup"),
                run_repo_cleanup_cmd,
                help="IFG repository cleanup advisor (Repo Graph + policy)",
                mutating=True,
                supports_dry_run=True,
            ),
        ]
        for spec in specs:
            ctx.commands.register(spec)
