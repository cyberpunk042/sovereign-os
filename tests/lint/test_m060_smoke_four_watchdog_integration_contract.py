"""m060-smoke four-watchdog probe integration — contract test.

Locks the four-watchdog (IPS spine) chain extension added to
`scripts/diagnostics/m060-smoke.py` so one operator command (the
same m060-smoke verb) verifies ALL THREE observability verticals
shipped this milestone:

  M060 cockpit-mirror chain + MS022 SSE-quota chain + four-watchdog
  IPS-spine chain.

The smoke now:
  1. Probes the four-watchdog proxy daemon's
     /api/four-watchdog/state endpoint (default http://localhost:7712;
     honors $SOVEREIGN_OS_FOUR_WATCHDOG_PROXY_URL — drift-locked by
     the systemd-unit contract test which fixes port 7712).
  2. Classifies the response into the canonical 6-state enum
     (ok/warn/critical/observer-fault/unreachable/unknown) matching
     the proxy daemon's classifier (which itself matches the alert
     rules + Grafana dashboard via the cross-surface threshold-
     lockstep contract).
  3. Emits a one-line operator summary alongside the M060 + MS022
     rows.
  4. Returns exit 1 if four-watchdog reports `critical` OR
     `observer-fault` — mirroring the doctor-fail + MS022-saturated
     exit-code contract so CI scripts can rely on a single exit code
     for "ANY observability vertical reports critical state".
  5. Honors `--skip-four-watchdog` for hosts without four-watchdog
     deployed.

Drift in any of these surfaces breaks operator one-command triage of
the cross-repo observability chain.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_PATH = REPO_ROOT / "scripts" / "diagnostics" / "m060-smoke.py"


def _load_smoke():
    """Load the m060-smoke module by path (hyphen in filename blocks
    plain `import`)."""
    spec = importlib.util.spec_from_file_location("m060_smoke", SMOKE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["m060_smoke"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_smoke_module_exposes_four_watchdog_helpers():
    """The four-watchdog probe + summarize helpers + default URL
    constant MUST be present — surface contract for the new probe."""
    mod = _load_smoke()
    assert hasattr(mod, "probe_four_watchdog_state")
    assert hasattr(mod, "summarize_four_watchdog")
    assert hasattr(mod, "DEFAULT_FOUR_WATCHDOG_PROXY_URL")
    assert hasattr(mod, "FOUR_WATCHDOG_STATE_ENDPOINT")


def test_default_proxy_url_matches_systemd_unit_port():
    """The default proxy URL must use port 7712 — the same port the
    sovereign-four-watchdog-api.service systemd unit binds. Drift =
    the smoke probes the wrong endpoint."""
    mod = _load_smoke()
    assert "7712" in mod.DEFAULT_FOUR_WATCHDOG_PROXY_URL, (
        f"DEFAULT_FOUR_WATCHDOG_PROXY_URL must reference port 7712 to "
        f"match the systemd unit; got {mod.DEFAULT_FOUR_WATCHDOG_PROXY_URL!r}"
    )


def test_four_watchdog_state_endpoint_canonical():
    """The state endpoint path must match the proxy daemon's route."""
    mod = _load_smoke()
    assert mod.FOUR_WATCHDOG_STATE_ENDPOINT == "/api/four-watchdog/state"


def test_probe_four_watchdog_state_unreachable_is_honest():
    """When the proxy daemon is unreachable, probe returns
    reachable=False + error string + state=None. Never raises."""
    mod = _load_smoke()
    out = mod.probe_four_watchdog_state("http://127.0.0.1:9", timeout=0.2)
    assert out["reachable"] is False
    assert out["state"] is None
    assert out["error"] is not None


def test_probe_four_watchdog_parses_classification():
    """When the proxy returns a valid envelope, probe extracts the
    `state` field per the API contract."""
    mod = _load_smoke()
    import json as _json

    class _FakeResp:
        status = 200
        def __init__(self, body):
            self._body = body.encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return self._body

    fake_body = _json.dumps({
        "state": "warn",
        "metrics": {"worst_severity": 1},
    })
    with patch("urllib.request.urlopen", return_value=_FakeResp(fake_body)):
        out = mod.probe_four_watchdog_state("http://localhost:7712")
    assert out["reachable"] is True
    assert out["state"] == "warn"
    assert out["error"] is None


def test_summarize_four_watchdog_classifies_all_canonical_states():
    """The summary line carries OK/WARN/FAIL based on the 5-state
    enum (4 canonical + 'unreachable'). Lock the state→label
    mapping so drift here surfaces."""
    mod = _load_smoke()
    cases = [
        ("ok",             "OK"),
        ("warn",           "WARN"),
        ("critical",       "FAIL"),
        ("observer-fault", "FAIL"),
        ("unreachable",    "WARN"),
    ]
    for state, marker in cases:
        result = {"reachable": True, "state": state, "error": None}
        summary = mod.summarize_four_watchdog(result)
        assert marker in summary, (
            f"state {state!r} summary should contain {marker!r}; "
            f"got: {summary!r}"
        )


def test_summarize_four_watchdog_unreachable_when_proxy_down():
    """When the proxy daemon is unreachable, the summary line marks
    UNREACHABLE so the operator sees it distinctly from a reachable
    proxy reporting state='unreachable' (which means node_exporter
    unreachable from the proxy)."""
    mod = _load_smoke()
    result = {"reachable": False, "state": None, "error": "Connection refused"}
    summary = mod.summarize_four_watchdog(result)
    assert "UNREACHABLE" in summary
    assert "proxy daemon down" in summary


def test_four_watchdog_flag_surface_present():
    """The --skip-four-watchdog + --four-watchdog-proxy-url flags
    must be wired."""
    mod = _load_smoke()
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            mod.main(["--help"])
        except SystemExit:
            pass
    help_text = buf.getvalue()
    assert "--skip-four-watchdog" in help_text
    assert "--four-watchdog-proxy-url" in help_text


def test_skip_four_watchdog_returns_skipped_block():
    """When --skip-four-watchdog is set, main() emits four_watchdog
    block with skipped=True + result=None + failed=False."""
    mod = _load_smoke()
    import io
    import contextlib
    import json as _json

    def _stub_probe(*args, **kwargs):
        return {"reachable": False, "http_status": None, "error": "stubbed"}

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         contextlib.redirect_stdout(buf):
        rc = mod.main([
            "--skip-doctor-observers", "--skip-ms022",
            "--skip-four-watchdog", "--json",
        ])
    assert rc == 1  # all mirrors unreachable
    body = _json.loads(buf.getvalue())
    assert body["four_watchdog"]["skipped"] is True
    assert body["four_watchdog"]["result"] is None
    assert body["four_watchdog"]["failed"] is False
    assert body["totals"]["four_watchdog_failed"] == 0


def test_four_watchdog_critical_triggers_exit_one():
    """If four-watchdog reports state=critical, exit code is 1 —
    mirroring the doctor-fail + MS022-saturated exit-code contract
    so a single CI exit signals critical state across ALL THREE
    observability verticals."""
    mod = _load_smoke()
    import io
    import contextlib

    def _stub_probe(base_url, endpoint, timeout=3.0):
        return {
            "reachable":     True,
            "http_status":   200,
            "mirror_status": "online",
            "raw": {
                "captured_at": "2027-01-01T00:00:00Z",
                "state": "online",
                "artifacts_present": 10,
                "artifacts_expected": 10,
                "newest_age_seconds": 5,
            },
        }

    def _stub_ms022_probe(proxy_url, timeout=3.0):
        return {"reachable": True, "state": "ok", "error": None}

    def _stub_four_watchdog_probe(proxy_url, timeout=3.0):
        return {"reachable": True, "state": "critical", "error": None}

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         patch.object(mod, "probe_ms022_state",
                      side_effect=_stub_ms022_probe), \
         patch.object(mod, "probe_four_watchdog_state",
                      side_effect=_stub_four_watchdog_probe), \
         contextlib.redirect_stdout(buf):
        rc = mod.main(["--skip-doctor-observers"])
    assert rc == 1, (
        f"four-watchdog critical must trigger exit 1; got {rc} with "
        f"output:\n{buf.getvalue()}"
    )


def test_four_watchdog_observer_fault_triggers_exit_one():
    """If four-watchdog reports state=observer-fault (gauges stale,
    wrapper wedged), exit code is 1 — observer-fault takes precedence
    over rollup-severity per the honest-offline contract; the smoke
    must mirror that precedence in its exit-code logic."""
    mod = _load_smoke()
    import io
    import contextlib

    def _stub_probe(base_url, endpoint, timeout=3.0):
        return {
            "reachable":     True,
            "http_status":   200,
            "mirror_status": "online",
            "raw": {"captured_at": "2027-01-01T00:00:00Z"},
        }

    def _stub_ms022_probe(proxy_url, timeout=3.0):
        return {"reachable": True, "state": "ok", "error": None}

    def _stub_four_watchdog_probe(proxy_url, timeout=3.0):
        return {"reachable": True, "state": "observer-fault", "error": None}

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         patch.object(mod, "probe_ms022_state",
                      side_effect=_stub_ms022_probe), \
         patch.object(mod, "probe_four_watchdog_state",
                      side_effect=_stub_four_watchdog_probe), \
         contextlib.redirect_stdout(buf):
        rc = mod.main(["--skip-doctor-observers"])
    assert rc == 1, (
        f"four-watchdog observer-fault must trigger exit 1; got {rc} "
        f"with output:\n{buf.getvalue()}"
    )


def test_four_watchdog_ok_does_not_trigger_exit_one():
    """If four-watchdog reports state=ok and everything else is
    healthy, exit code is 0."""
    mod = _load_smoke()
    import io
    import contextlib

    def _stub_probe(base_url, endpoint, timeout=3.0):
        return {
            "reachable":     True,
            "http_status":   200,
            "mirror_status": "online",
            "raw": {
                "captured_at": "2027-01-01T00:00:00Z",
                "state": "online",
                "artifacts_present": 10,
                "artifacts_expected": 10,
                "newest_age_seconds": 5,
            },
        }

    def _stub_ms022_probe(proxy_url, timeout=3.0):
        return {"reachable": True, "state": "ok", "error": None}

    def _stub_four_watchdog_probe(proxy_url, timeout=3.0):
        return {"reachable": True, "state": "ok", "error": None}

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         patch.object(mod, "probe_ms022_state",
                      side_effect=_stub_ms022_probe), \
         patch.object(mod, "probe_four_watchdog_state",
                      side_effect=_stub_four_watchdog_probe), \
         contextlib.redirect_stdout(buf):
        rc = mod.main(["--skip-doctor-observers"])
    assert rc == 0, (
        f"four-watchdog ok with healthy mirrors must exit 0; got {rc}"
    )


def test_four_watchdog_warn_does_not_trigger_exit_one():
    """If four-watchdog reports state=warn (warn-not-fail per the
    alert severity ladder), exit code is 0."""
    mod = _load_smoke()
    import io
    import contextlib

    def _stub_probe(base_url, endpoint, timeout=3.0):
        return {
            "reachable":     True,
            "http_status":   200,
            "mirror_status": "online",
            "raw": {
                "captured_at": "2027-01-01T00:00:00Z",
                "state": "online",
                "artifacts_present": 10,
                "artifacts_expected": 10,
                "newest_age_seconds": 5,
            },
        }

    def _stub_ms022_probe(proxy_url, timeout=3.0):
        return {"reachable": True, "state": "ok", "error": None}

    def _stub_four_watchdog_probe(proxy_url, timeout=3.0):
        return {"reachable": True, "state": "warn", "error": None}

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         patch.object(mod, "probe_ms022_state",
                      side_effect=_stub_ms022_probe), \
         patch.object(mod, "probe_four_watchdog_state",
                      side_effect=_stub_four_watchdog_probe), \
         contextlib.redirect_stdout(buf):
        rc = mod.main(["--skip-doctor-observers"])
    assert rc == 0, (
        f"four-watchdog warn is warn-not-fail; must exit 0. got {rc}"
    )


def test_summary_line_includes_four_watchdog_failed_counter():
    """The summary line (non-JSON output) must include
    four_watchdog_failed=N alongside doctor_failed + ms022_failed."""
    mod = _load_smoke()
    import io
    import contextlib

    def _stub_probe(base_url, endpoint, timeout=3.0):
        return {
            "reachable":     True,
            "http_status":   200,
            "mirror_status": "online",
            "raw": {"captured_at": "2027-01-01T00:00:00Z"},
        }

    def _stub_ms022_probe(proxy_url, timeout=3.0):
        return {"reachable": True, "state": "ok", "error": None}

    def _stub_four_watchdog_probe(proxy_url, timeout=3.0):
        return {"reachable": True, "state": "ok", "error": None}

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         patch.object(mod, "probe_ms022_state",
                      side_effect=_stub_ms022_probe), \
         patch.object(mod, "probe_four_watchdog_state",
                      side_effect=_stub_four_watchdog_probe), \
         contextlib.redirect_stdout(buf):
        mod.main(["--skip-doctor-observers"])
    out = buf.getvalue()
    assert "four_watchdog_failed=" in out, (
        f"summary line must include four_watchdog_failed counter; "
        f"got:\n{out}"
    )


def test_json_envelope_shape_locked():
    """JSON output carries the four_watchdog block with canonical
    keys (skipped/result/failed) + four_watchdog_failed in totals."""
    mod = _load_smoke()
    import io
    import contextlib
    import json as _json

    def _stub_probe(base_url, endpoint, timeout=3.0):
        return {
            "reachable":     True,
            "http_status":   200,
            "mirror_status": "online",
            "raw": {"captured_at": "2027-01-01T00:00:00Z"},
        }

    def _stub_ms022_probe(proxy_url, timeout=3.0):
        return {"reachable": True, "state": "ok", "error": None}

    def _stub_four_watchdog_probe(proxy_url, timeout=3.0):
        return {"reachable": True, "state": "ok", "error": None}

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         patch.object(mod, "probe_ms022_state",
                      side_effect=_stub_ms022_probe), \
         patch.object(mod, "probe_four_watchdog_state",
                      side_effect=_stub_four_watchdog_probe), \
         contextlib.redirect_stdout(buf):
        mod.main(["--skip-doctor-observers", "--json"])
    body = _json.loads(buf.getvalue())
    assert "four_watchdog" in body
    assert set(body["four_watchdog"].keys()) == {
        "skipped", "result", "failed",
    }
    assert body["four_watchdog"]["skipped"] is False
    assert body["four_watchdog"]["result"] is not None
    assert body["four_watchdog"]["result"]["state"] == "ok"
    assert "four_watchdog_failed" in body["totals"]


def test_proxy_url_env_var_documented():
    """The --four-watchdog-proxy-url help text must mention the env
    var so operators can find it via --help."""
    mod = _load_smoke()
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            mod.main(["--help"])
        except SystemExit:
            pass
    help_text = buf.getvalue()
    assert "SOVEREIGN_OS_FOUR_WATCHDOG_PROXY_URL" in help_text, (
        "help text must document the SOVEREIGN_OS_FOUR_WATCHDOG_PROXY_URL "
        "env var override knob"
    )
