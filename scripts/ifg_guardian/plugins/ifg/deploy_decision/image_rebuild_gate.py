"""Hard gate: kiedy Guardian musi przebudować obraz API/worker.

Reguły (GWO-GUARDIAN-0080):
1. Porównuj kontekst obrazu z wersją wdrożoną (label), nie tylko „czy są lokalne diffy”.
2. Zmiana w kontekście Docker (np. ``app/``) → wymusza rebuild.
3. Dirty tree NIGDY nie powoduje SKIP dla zmian image-context; niejednoznaczność → FAIL.
4. Brak możliwości odczytu labelu wdrożonego obrazu przy podejrzeniu zmian → FAIL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ImageRebuildDecision(str, Enum):
    ALLOW_SKIP = "ALLOW_SKIP"
    REQUIRE_REBUILD = "REQUIRE_REBUILD"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ImageRebuildGateResult:
    decision: ImageRebuildDecision
    reason: str
    trigger_files: list[str] = field(default_factory=list)
    expected_revision: str | None = None
    deployed_revision: str | None = None
    ambiguity: str | None = None

    @property
    def requires_rebuild(self) -> bool:
        return self.decision == ImageRebuildDecision.REQUIRE_REBUILD

    @property
    def is_failure(self) -> bool:
        return self.decision == ImageRebuildDecision.FAIL


def evaluate_image_rebuild_gate(
    *,
    image_context_changes: list[str],
    dirty_image_context_files: list[str],
    expected_revision: str,
    deployed_revision: str | None,
    deployed_inspect_ok: bool,
    committed_image_context_changes: list[str] | None = None,
    defer_remote_verify: bool = False,
) -> ImageRebuildGateResult:
    """Ocena hard-gate dla rebuildu API/worker.

    Parameters
    ----------
    image_context_changes:
        Wszystkie zmiany image-context (commit vs origin + dirty tracked + untracked).
    dirty_image_context_files:
        Tylko niezacommitowane (tracked dirty + untracked) w image-context.
    expected_revision:
        ``git rev-parse HEAD`` (docelowy SHA źródeł po pullu).
    deployed_revision:
        Label ``ifg.git.commit`` / OCI revision z działającego obrazu (lub None).
    deployed_inspect_ok:
        Czy udało się odczytać metadane obrazu na DS723+.
    committed_image_context_changes:
        Opcjonalnie: zmiany już w commitach względem origin (bez dirty).
        Gdy None — wyliczane jako image_context_changes minus dirty.
    defer_remote_verify:
        Gdy True (np. lokalny doctor bez SSH) i brak lokalnych zmian image-context —
        ALLOW_SKIP z odroczeniem weryfikacji labelu do ``deploy run``.
        Deploy LIVE zawsze ustawia False.
    """
    expected = (expected_revision or "").strip()
    dirty = _unique(dirty_image_context_files)
    all_changes = _unique(image_context_changes)
    if committed_image_context_changes is None:
        dirty_set = set(dirty)
        committed = [p for p in all_changes if p not in dirty_set]
    else:
        committed = _unique(committed_image_context_changes)

    # 1) Dirty image-context: nigdy SKIP. Jeśli zmiany nie są w commitach → FAIL
    #    (build na DS723 robi git pull — nie widzi lokalnego dirty z Mac mini).
    if dirty:
        only_dirty = [p for p in dirty if p not in set(committed)]
        if only_dirty:
            return ImageRebuildGateResult(
                decision=ImageRebuildDecision.FAIL,
                reason=(
                    "Image-context ma niezacommitowane zmiany — deploy na DS723+ nie może ich "
                    "uwzględnić w docker build (git pull). Zacommituj lub schowaj zmiany w "
                    f"kontekście obrazu: {_short_files(only_dirty)}"
                ),
                trigger_files=only_dirty,
                expected_revision=expected or None,
                deployed_revision=deployed_revision,
                ambiguity="dirty_image_context_not_in_commits",
            )
        # Dirty pokrywa się z committed — wymagaj rebuild (nigdy SKIP).
        return ImageRebuildGateResult(
            decision=ImageRebuildDecision.REQUIRE_REBUILD,
            reason=(
                "Image-context zmieniony (w tym dirty) — docker build api/worker wymagany; "
                f"pliki: {_short_files(all_changes or dirty)}"
            ),
            trigger_files=all_changes or dirty,
            expected_revision=expected or None,
            deployed_revision=deployed_revision,
        )

    # 2) Czyste drzewo, ale są committed zmiany image-context vs origin → rebuild
    if committed or all_changes:
        return ImageRebuildGateResult(
            decision=ImageRebuildDecision.REQUIRE_REBUILD,
            reason=(
                "Image-context zmieniony względem bazy deploy — docker build api/worker wymagany; "
                f"pliki: {_short_files(committed or all_changes)}"
            ),
            trigger_files=committed or all_changes,
            expected_revision=expected or None,
            deployed_revision=deployed_revision,
        )

    # 3) Brak lokalnych zmian image-context — porównaj z wdrożonym obrazem
    if not expected:
        return ImageRebuildGateResult(
            decision=ImageRebuildDecision.FAIL,
            reason="Nie można ustalić oczekiwanego git revision (git rev-parse HEAD failed)",
            ambiguity="missing_expected_revision",
        )

    if defer_remote_verify and not deployed_inspect_ok:
        return ImageRebuildGateResult(
            decision=ImageRebuildDecision.ALLOW_SKIP,
            reason=(
                "Image-context bez lokalnych zmian; weryfikacja labelu wdrożonego obrazu "
                "odroczona do deploy run"
            ),
            expected_revision=expected,
            ambiguity="deferred_remote_image_verify",
        )

    if not deployed_inspect_ok:
        return ImageRebuildGateResult(
            decision=ImageRebuildDecision.FAIL,
            reason=(
                "Nie można odczytać labelu wdrożonego obrazu ifg-api — odmowa SKIP docker build "
                "(niejednoznaczna zgodność obrazu ze źródłami)"
            ),
            expected_revision=expected,
            deployed_revision=None,
            ambiguity="deployed_image_inspect_failed",
        )

    deployed = (deployed_revision or "").strip()
    if not deployed or deployed in {"unknown", "null", "None"}:
        return ImageRebuildGateResult(
            decision=ImageRebuildDecision.REQUIRE_REBUILD,
            reason=(
                "Wdrożony obraz ifg-api nie ma labelu ifg.git.commit — wymuszam rebuild "
                f"(expected HEAD={expected[:12]})"
            ),
            expected_revision=expected,
            deployed_revision=deployed or None,
            ambiguity="missing_image_git_label",
        )

    if not _revisions_match(expected, deployed):
        return ImageRebuildGateResult(
            decision=ImageRebuildDecision.REQUIRE_REBUILD,
            reason=(
                f"Obraz produkcyjny (revision={deployed[:12]}) ≠ HEAD ({expected[:12]}) — "
                "docker build api/worker wymagany"
            ),
            expected_revision=expected,
            deployed_revision=deployed,
        )

    return ImageRebuildGateResult(
        decision=ImageRebuildDecision.ALLOW_SKIP,
        reason=(
            f"Image-context bez zmian; wdrożony obraz ma ifg.git.commit={deployed[:12]} "
            f"zgodny z HEAD"
        ),
        expected_revision=expected,
        deployed_revision=deployed,
    )


def verify_deployed_image_matches_expected(
    *,
    expected_revision: str,
    deployed_revision: str | None,
    rebuild_was_required: bool,
    image_id: str | None = None,
) -> tuple[bool, str]:
    """Post-deploy: label obrazu musi zgadzać się z oczekiwanym SHA."""
    expected = (expected_revision or "").strip()
    deployed = (deployed_revision or "").strip()
    if not expected:
        return False, "Brak expected_revision do weryfikacji obrazu"
    if not deployed or deployed in {"unknown", "null", "None"}:
        return False, (
            "Wdrożony obraz nie ma labelu ifg.git.commit — weryfikacja post-deploy nieudana"
            + (f" (image_id={image_id[:19]}…)" if image_id else "")
        )
    if not _revisions_match(expected, deployed):
        return False, (
            f"Niezgodność obrazu po deployu: expected={expected[:12]} "
            f"deployed_label={deployed[:12]}"
            + ("; rebuild był wymagany" if rebuild_was_required else "")
        )
    return True, (
        f"Obraz zgodny: ifg.git.commit={deployed[:12]}"
        + (f" image_id={image_id[:19]}…" if image_id else "")
    )


def _revisions_match(expected: str, deployed: str) -> bool:
    exp = expected.strip().lower()
    dep = deployed.strip().lower()
    if not exp or not dep:
        return False
    return exp == dep or exp.startswith(dep) or dep.startswith(exp)


def _unique(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in paths:
        path = (raw or "").strip().replace("\\", "/").lstrip("./")
        if not path or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _short_files(files: list[str], *, limit: int = 6) -> str:
    if not files:
        return "(brak)"
    shown = files[:limit]
    extra = f" (+{len(files) - limit} more)" if len(files) > limit else ""
    return ", ".join(shown) + extra
