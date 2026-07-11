"""GDD-0010 — runtime status independent from release gate."""
from __future__ import annotations

from ifg_guardian.core.runtime_status import (
    ProductionRuntimeStatus,
    classify_runtime_status,
)


def _ps_line(service: str, state: str) -> str:
    return f"{service}\t{state}"


class TestClassifyRuntimeStatus:
    def test_all_stopped_is_production_stopped(self):
        ps = "\n".join(
            [
                _ps_line("api", "exited"),
                _ps_line("worker", "exited"),
                _ps_line("db", "exited"),
            ]
        )
        report = classify_runtime_status(ps, health_endpoint_ok=False)
        assert report.status == ProductionRuntimeStatus.PRODUCTION_STOPPED
        assert report.exit_code == 1
        assert set(report.stopped_services) == {"api", "worker", "db"}

    def test_all_running_healthy_is_production_running(self):
        ps = "\n".join(
            [
                _ps_line("api", "running (healthy)"),
                _ps_line("worker", "running"),
                _ps_line("db", "running (healthy)"),
            ]
        )
        report = classify_runtime_status(ps, health_endpoint_ok=True)
        assert report.status == ProductionRuntimeStatus.PRODUCTION_RUNNING
        assert report.exit_code == 0

    def test_partial_stop_is_degraded(self):
        ps = "\n".join(
            [
                _ps_line("api", "running (healthy)"),
                _ps_line("worker", "exited"),
                _ps_line("db", "running (healthy)"),
            ]
        )
        report = classify_runtime_status(ps, health_endpoint_ok=True)
        assert report.status == ProductionRuntimeStatus.PRODUCTION_DEGRADED
        assert "worker" in report.stopped_services

    def test_health_fail_while_running_is_degraded(self):
        ps = "\n".join(
            [
                _ps_line("api", "running"),
                _ps_line("worker", "running"),
                _ps_line("db", "running (healthy)"),
            ]
        )
        report = classify_runtime_status(ps, health_endpoint_ok=False)
        assert report.status == ProductionRuntimeStatus.PRODUCTION_DEGRADED

    def test_restart_policy_mismatch_surfaces(self):
        ps = "\n".join(
            [
                _ps_line("api", "running (healthy)"),
                _ps_line("worker", "running"),
                _ps_line("db", "running (healthy)"),
            ]
        )
        report = classify_runtime_status(
            ps,
            health_endpoint_ok=True,
            restart_policies={"api": "unless-stopped", "worker": "unless-stopped", "db": "unless-stopped"},
            expected_restart_policy="always",
        )
        assert report.status == ProductionRuntimeStatus.PRODUCTION_RUNNING
        assert len(report.restart_policy_mismatches) == 3

    def test_stopped_not_conflated_with_release_blocked(self):
        """PRODUCTION_STOPPED is runtime-only; release gate is separate."""
        ps = "\n".join(
            [
                _ps_line("api", "exited"),
                _ps_line("worker", "exited"),
                _ps_line("db", "exited"),
            ]
        )
        report = classify_runtime_status(ps)
        assert report.status.value != "PRODUCTION_BLOCKED"
        assert "PRODUCTION_BLOCKED" not in str(report.problems)
