"""Contract lint for the UPS graceful-shutdown ORCHESTRATION (SDD-026 Z-18).

The graceful soft-exit is a chain of pieces that are only useful WIRED TOGETHER:
guard → warn(all mediums) + schedule-manifest(staged soft-exit) → router-drain →
poweroff. Each link has broken at least once in development (stale unit names in
the manifest, the guard firing a bare `shutdown -h`, a missing `notify send`
verb). This locks every link so a future edit can't silently unwire it.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_manifest_uses_real_units_and_full_soft_exit():
    m = _read("config/shutdown-manifest.toml.example")
    # the CORRECT unit names (the old example had these wrong)
    assert "sovereign-router.service" in m, "manifest must stop the real router unit"
    assert "sovereign-dashboards.service" in m, "manifest must stop the real dashboards unit"
    assert "sovereign-inference-router" not in m, "stale unit name (sovereign-inference-router)"
    assert "sovereign-dashboard.service" not in m, "stale unit name (singular sovereign-dashboard)"
    # backends must be unloaded (frees VRAM)
    for backend in ("oracle-core", "logic-engine", "pulse"):
        assert f"sovereign-{backend}.service" in m, f"manifest must unload {backend}"
    # the staged shape: drain in-flight → warn → poweroff
    assert "drain-inference.sh" in m, "manifest must drain in-flight inference"
    assert "graceful-warn.sh" in m, "manifest must announce across mediums"
    assert "systemctl poweroff" in m, "manifest must terminate in poweroff"


def test_manifest_validates_via_schedule_manifest():
    import subprocess, sys, os
    env = dict(os.environ, SOVEREIGN_OS_SHUTDOWN_MANIFEST=str(
        REPO / "config" / "shutdown-manifest.toml.example"))
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts/power/schedule-manifest.py"), "list", "--json"],
        capture_output=True, text=True, env=env, timeout=30)
    import json
    doc = json.loads(r.stdout)
    assert doc["valid"], f"manifest invalid: {doc.get('validation_errors')}"
    assert doc["step_count"] >= 10, "expected a full staged sequence"


def test_guard_orchestrates_not_bare_shutdown():
    g = _read("scripts/hooks/recurrent/power-shutdown-guard.sh")
    # the primary critical path invokes the staged orchestrator
    assert "schedule-manifest" in g, "guard must invoke the schedule-manifest orchestrator"
    assert "apply --confirm" in g, "guard must run the manifest with --confirm"
    # it warns across mediums before firing (both attention + imminent)
    assert "graceful-warn.sh" in g, "guard must warn via graceful-warn.sh"
    assert "approaching" in g and "imminent" in g, "guard must warn at both stages"
    # re-entry protection so the minutely timer can't restack a shutdown
    assert "shutdown-in-progress" in g, "guard must guard against re-entry"


def test_warn_and_drain_helpers_present_and_observable():
    for rel in ("scripts/power/graceful-warn.sh", "scripts/power/drain-inference.sh"):
        p = REPO / rel
        assert p.is_file(), f"missing {rel}"
        assert os.access(p, os.X_OK), f"{rel} must be executable"
        body = p.read_text(encoding="utf-8")
        assert "observability.sh" in body and "emit_metric" in body, \
            f"{rel} must emit a Layer B metric"


def test_warn_helper_hits_every_medium():
    w = _read("scripts/power/graceful-warn.sh")
    assert "dispatch.py" in w and "send" in w, "warn must fan via notify send"
    assert "wall" in w, "warn must broadcast to logged-in terminals"
    assert "/dev/console" in w, "warn must write the physical console"
    assert "notify-send" in w, "warn must push desktop notifications"


def test_router_has_flag_gated_drain():
    r = _read("scripts/inference/router.py")
    assert "_is_draining" in r, "router must have a drain gate"
    assert "/drain-status" in r, "router must expose /drain-status for the orchestrator"
    assert "_INFLIGHT" in r, "router must track in-flight requests"
    # the gate must be FLAG-gated (zero behavior change when absent)
    assert "SOVEREIGN_OS_ROUTER_DRAIN_FLAG" in r, "drain must be flag-gated (no default behavior change)"


def test_notify_has_send_verb():
    d = _read("scripts/notify/dispatch.py")
    assert "def cmd_send" in d, "dispatch.py must implement the send verb"
    assert '"send"' in d and "func=cmd_send" in d, "send must be a wired CLI subverb"
    osctl = _read("scripts/sovereign-osctl")
    assert "send" in osctl and "dispatch.py" in osctl, "osctl must route notify send"


def test_power_status_warns_before_shutdown():
    ps = _read("scripts/hardware/power-status.py")
    assert "warn_lead_minutes" in ps, "advisories must read warn_lead_minutes"
    assert "warn_at_minutes" in ps, "advisories must surface the effective warn threshold"
    # the effective warn must be computed as shutdown + lead (fires BEFORE shutdown)
    assert "shutdown_min_min + warn_lead_min" in ps, \
        "effective warn threshold must be shutdown_minutes + warn_lead_minutes"


def test_feature_toggle_is_honored():
    # profile master toggle + env override both gate the whole feature
    emit = _read("scripts/build/adapters/mkosi-emit.sh")
    assert "power_feature_on" in emit, "mkosi-emit must read the power master toggle"
    assert "SOVEREIGN_OS_POWER_FEATURE" in emit, "mkosi-emit must honor the env override"
    schema = _read("schemas/profile.schema.yaml")
    assert "enabled" in schema, "schema power block must allow the enabled toggle"
