"""Łączy git scope + remote image inspect → ImageRebuildGateResult."""
from __future__ import annotations

from ifg_guardian.plugins.ifg.deploy_decision.git_scope import (
    current_git_head,
    list_committed_image_context_changes,
    list_dirty_image_context_files,
    list_image_context_changed_files,
)
from ifg_guardian.plugins.ifg.deploy_decision.image_inspect import (
    DeployedImageInfo,
    inspect_deployed_api_image,
)
from ifg_guardian.plugins.ifg.deploy_decision.image_rebuild_gate import (
    ImageRebuildGateResult,
    evaluate_image_rebuild_gate,
)


def resolve_image_rebuild_gate(
    *,
    remote_host: str | None = None,
    remote_path: str | None = None,
    defer_remote_verify: bool = False,
    deployed_info: DeployedImageInfo | None = None,
) -> ImageRebuildGateResult:
    """Pełna ocena hard-gate (lokalny git + opcjonalnie DS723+ image labels).

    ``defer_remote_verify=True`` — lokalny doctor bez wymuszenia SSH; deploy LIVE = False.
    """
    image_changes = list_image_context_changed_files()
    dirty = list_dirty_image_context_files()
    committed = list_committed_image_context_changes()
    expected = current_git_head()

    if deployed_info is not None:
        deployed_inspect_ok = deployed_info.inspect_ok
        deployed_revision = deployed_info.git_commit
    elif defer_remote_verify:
        deployed_inspect_ok = False
        deployed_revision = None
    else:
        info = inspect_deployed_api_image(remote_host=remote_host, remote_path=remote_path)
        deployed_inspect_ok = info.inspect_ok
        deployed_revision = info.git_commit

    return evaluate_image_rebuild_gate(
        image_context_changes=image_changes,
        dirty_image_context_files=dirty,
        expected_revision=expected,
        deployed_revision=deployed_revision,
        deployed_inspect_ok=deployed_inspect_ok,
        committed_image_context_changes=committed,
        defer_remote_verify=defer_remote_verify,
    )
