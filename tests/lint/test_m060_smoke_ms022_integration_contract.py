"""M060 smoke — MS022 SSE-quota probe integration contract.

Locks the MS022 chain extension added to
`scripts/diagnostics/m060-smoke.py` so one operator command (the same
m060-smoke verb) verifies BOTH the M060 cockpit-mirror chain AND the
MS022 SSE-quota chain shipped this milestone.

The smoke now:
  1. Probes the MS022 SSE-quota proxy daemon's `/api/ms022/state`
     endpoint (default http://localhost:7711; honors
     $SOVEREIGN_OS_MS022_PROXY_URL).
  2. Classifies the response into the canonical
     ok/approaching/saturated/unreachable enum (same 4-state set
     locked by ms022-sse-quota-api + the per-token-first ordering
     test).
  3. Emits a one-line operator summary alongside the M060 rows.
  4. Returns exit 1 if MS022 reports `saturated` — mirroring the
     doctor-fail exit-code contract so CI scripts can rely on a
     single exit code for "any observability vertical reports
     critical state".
  5. Honors `--skip-ms022` for hosts without MS022 deployed.

Drift in any of these surfaces breaks operator one-command triage
of the cross-repo observability chain.
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


def test_smoke_module_exposes_ms022_helpers():
    """The MS022 probe + summarize helpers + default URL constant
    MUST be present — surface contract for the new probe."""
    mod = _load_smoke()
    assert hasattr(mod, "probe_ms022_state")
    assert hasattr(mod, "summarize_ms022")
    assert hasattr(mod, "DEFAULT_MS022_PROXY_URL")
    assert hasattr(mod, "MS022_STATE_ENDPOINT")


def test_default_ms022_proxy_url_matches_systemd_unit_port():
    """The default MS022 proxy URL must use port 7711 — the same
    port the sovereign-ms022-sse-quota-api.service systemd unit
    binds. Drift = the smoke probes the wrong endpoint."""
    mod = _load_smoke()
    assert "7711" in mod.DEFAULT_MS022_PROXY_URL, (
        f"DEFAULT_MS022_PROXY_URL must reference port 7711 to match "
        f"the systemd unit; got {mod.DEFAULT_MS022_PROXY_URL!r}"
    )


def test_ms022_state_endpoint_canonical():
    """The state endpoint path must match the proxy daemon's route."""
    mod = _load_smoke()
    assert mod.MS022_STATE_ENDPOINT == "/api/ms022/state"


def test_probe_ms022_state_unreachable_is_honest():
    """When the proxy daemon is unreachable, probe returns
    reachable=False + error string + state=None. Never raises."""
    mod = _load_smoke()
    out = mod.probe_ms022_state("http://127.0.0.1:9", timeout=0.2)
    assert out["reachable"] is False
    assert out["state"] is None
    assert out["error"] is not None


def test_probe_ms022_state_parses_classification():
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
        "state": "approaching",
        "global": {"saturation": 0.87},
    })
    with patch("urllib.request.urlopen", return_value=_FakeResp(fake_body)):
        out = mod.probe_ms022_state("http://localhost:7711")
    assert out["reachable"] is True
    assert out["state"] == "approaching"
    assert out["error"] is None


def test_summarize_ms022_classifies_all_canonical_states():
    """The summary line carries OK/WARN/FAIL based on the 4-state
    enum. Lock the state→label mapping so drift here surfaces."""
    mod = _load_smoke()
    cases = [
        ("ok",          "OK"),
        ("approaching", "WARN"),
        ("saturated",   "FAIL"),
        ("unreachable", "WARN"),
    ]
    for state, marker in cases:
        result = {"reachable": True, "state": state, "error": None}
        summary = mod.summarize_ms022(result)
        assert marker in summary, (
            f"state {state!r} summary should contain {marker!r}; "
            f"got: {summary!r}"
        )


def test_summarize_ms022_unreachable_when_proxy_down():
    """When the proxy daemon is unreachable, the summary line marks
    UNREACHABLE so the operator sees it distinctly from a reachable
    proxy reporting state='unreachable' (which means selfdefd is
    unreachable but the proxy is up)."""
    mod = _load_smoke()
    result = {"reachable": False, "state": None, "error": "Connection refused"}
    summary = mod.summarize_ms022(result)
    assert "UNREACHABLE" in summary
    assert "proxy daemon down" in summary


def test_ms022_flag_surface_present():
    """The --skip-ms022 + --ms022-proxy-url flags must be wired."""
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
    assert "--skip-ms022" in help_text
    assert "--ms022-proxy-url" in help_text


def test_skip_ms022_returns_skipped_block():
    """When --skip-ms022 is set, main() emits ms022_sse_quota with
    skipped=True + result=None + failed=False."""
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
            "--skip-doctor-observers", "--skip-ms022", "--json",
        ])
    assert rc == 1  # all mirrors unreachable
    body = _json.loads(buf.getvalue())
    assert body["ms022_sse_quota"]["skipped"] is True
    assert body["ms022_sse_quota"]["result"] is None
    assert body["ms022_sse_quota"]["failed"] is False
    assert body["totals"]["ms022_failed"] == 0


def test_ms022_saturated_triggers_exit_one():
    """If MS022 reports state=saturated (proxy is up, quota maxed,
    clients getting 429), exit code is 1 — mirroring the doctor-fail
    exit-code contract so a single CI exit signals critical state
    across BOTH observability verticals."""
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
        return {"reachable": True, "state": "saturated", "error": None}

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         patch.object(mod, "probe_ms022_state",
                      side_effect=_stub_ms022_probe), \
         contextlib.redirect_stdout(buf):
        rc = mod.main(["--skip-doctor-observers"])
    assert rc == 1, (
        f"MS022 saturated must trigger exit 1; got {rc} with output:\n"
        f"{buf.getvalue()}"
    )


def test_ms022_ok_does_not_trigger_exit_one():
    """If MS022 reports state=ok and everything else is healthy,
    exit code is 0 — the smoke must NOT misfire on healthy state."""
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

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         patch.object(mod, "probe_ms022_state",
                      side_effect=_stub_ms022_probe), \
         contextlib.redirect_stdout(buf):
        rc = mod.main(["--skip-doctor-observers"])
    assert rc == 0, (
        f"MS022 ok with healthy mirrors must exit 0; got {rc} with "
        f"output:\n{buf.getvalue()}"
    )


def test_ms022_approaching_does_not_trigger_exit_one():
    """If MS022 reports state=approaching (≥85% saturation, warn-but-
    not-critical), exit code is 0 — only saturated is critical."""
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
        return {"reachable": True, "state": "approaching", "error": None}

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         patch.object(mod, "probe_ms022_state",
                      side_effect=_stub_ms022_probe), \
         contextlib.redirect_stdout(buf):
        rc = mod.main(["--skip-doctor-observers"])
    assert rc == 0, (
        f"MS022 approaching is warn-not-fail; must exit 0. got {rc} "
        f"with output:\n{buf.getvalue()}"
    )


def test_ms022_summary_line_includes_ms022_failed_counter():
    """The summary line (non-JSON output) must include
    ms022_failed=N alongside doctor_failed=N — symmetric counter
    for the second observability vertical."""
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

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         patch.object(mod, "probe_ms022_state",
                      side_effect=_stub_ms022_probe), \
         contextlib.redirect_stdout(buf):
        mod.main(["--skip-doctor-observers"])
    out = buf.getvalue()
    assert "ms022_failed=" in out, (
        f"summary line must include ms022_failed counter; got:\n{out}"
    )


def test_ms022_json_envelope_shape():
    """The JSON output must carry the ms022_sse_quota block with the
    canonical keys (skipped/result/failed) + ms022_failed in totals.
    Drift = downstream jq filters break."""
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

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         patch.object(mod, "probe_ms022_state",
                      side_effect=_stub_ms022_probe), \
         contextlib.redirect_stdout(buf):
        mod.main(["--skip-doctor-observers", "--json"])
    body = _json.loads(buf.getvalue())
    assert "ms022_sse_quota" in body
    assert set(body["ms022_sse_quota"].keys()) == {
        "skipped", "result", "failed",
    }
    assert body["ms022_sse_quota"]["skipped"] is False
    assert body["ms022_sse_quota"]["result"] is not None
    assert body["ms022_sse_quota"]["result"]["state"] == "ok"
    assert "ms022_failed" in body["totals"]


def test_ms022_proxy_url_env_var_documented():
    """The --ms022-proxy-url help text must mention the env var so
    operators can find it via --help. Drift = operators miss the
    override knob."""
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
    assert "SOVEREIGN_OS_MS022_PROXY_URL" in help_text, (
        "help text must document the SOVEREIGN_OS_MS022_PROXY_URL "
        "env var override knob"
    )
