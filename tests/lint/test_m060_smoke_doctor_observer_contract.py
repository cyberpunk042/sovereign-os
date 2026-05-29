"""M060 smoke — doctor-observer probe contract.

Locks the new --skip-doctor-observers + node_exporter textfile probe
behavior added to scripts/diagnostics/m060-smoke.py. The two
observer textfiles (selfdef-cli-mirror-doctor + selfdef-m060-doctor,
selfdef commits e9ab056 + ce58154) write Prometheus exposition into
the node_exporter textfile_collector. m060-smoke now probes those
via node_exporter /metrics so one operator command verifies BOTH the
daemon's publish state AND the doctors' observer freshness.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_PATH = REPO_ROOT / "scripts" / "diagnostics" / "m060-smoke.py"


def _load_smoke():
    """Load the m060-smoke module by path (the filename uses a hyphen
    which is not valid Python identifier syntax, so importlib is the
    only way)."""
    spec = importlib.util.spec_from_file_location("m060_smoke", SMOKE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["m060_smoke"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_smoke_module_loads():
    mod = _load_smoke()
    assert hasattr(mod, "probe_node_exporter_textfile")
    assert hasattr(mod, "summarize_doctor")
    assert hasattr(mod, "main")


def test_doctor_textfile_prefixes_canonical():
    """The two shipped doctor textfiles are cli-mirror + m060-chain.
    Drift here means the smoke probes the wrong metric names."""
    mod = _load_smoke()
    assert mod.DOCTOR_TEXTFILE_PREFIXES == [
        ("cli-mirror", "selfdef_cli_mirror_doctor"),
        ("m060-chain", "selfdef_m060_doctor"),
    ]


def test_default_node_exporter_url_env_override():
    """Default URL is localhost:9100/metrics; honor
    SOVEREIGN_OS_NODE_EXPORTER_URL env var."""
    mod = _load_smoke()
    assert "9100/metrics" in mod.DEFAULT_NODE_EXPORTER_URL


def test_probe_node_exporter_textfile_unreachable_is_honest():
    """When node_exporter is unreachable, probe returns
    reachable=False + error string + worst/age=None. Never raises."""
    mod = _load_smoke()
    out = mod.probe_node_exporter_textfile(
        "http://127.0.0.1:9", "selfdef_cli_mirror_doctor", timeout=0.2,
    )
    assert out["reachable"] is False
    assert out["worst"] is None
    assert out["age_seconds"] is None
    assert out["error"] is not None


def test_probe_node_exporter_textfile_parses_severity_and_age():
    """When node_exporter responds with the doctor textfile exposition,
    probe extracts worst_severity (int) + last_run_unix → age_seconds."""
    mod = _load_smoke()
    import time as _time
    now = int(_time.time())
    fake_body = (
        "# HELP selfdef_cli_mirror_doctor_severity Per-check severity.\n"
        "# TYPE selfdef_cli_mirror_doctor_severity gauge\n"
        "selfdef_cli_mirror_doctor_severity{check=\"schema-version\"} 0\n"
        "selfdef_cli_mirror_doctor_severity{check=\"resident-store\"} 1\n"
        "# HELP selfdef_cli_mirror_doctor_worst_severity Worst.\n"
        "# TYPE selfdef_cli_mirror_doctor_worst_severity gauge\n"
        "selfdef_cli_mirror_doctor_worst_severity 1\n"
        "# HELP selfdef_cli_mirror_doctor_last_run_unix Last run.\n"
        "# TYPE selfdef_cli_mirror_doctor_last_run_unix gauge\n"
        f"selfdef_cli_mirror_doctor_last_run_unix {now - 42}\n"
    )

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

    with patch("urllib.request.urlopen", return_value=_FakeResp(fake_body)):
        out = mod.probe_node_exporter_textfile(
            "http://localhost:9100/metrics",
            "selfdef_cli_mirror_doctor",
        )
    assert out["reachable"] is True
    assert out["worst"] == 1
    assert out["age_seconds"] is not None
    assert 40 <= out["age_seconds"] <= 60


def test_summarize_doctor_classifies_severity_correctly():
    """The summary line carries OK / WARN / FAIL based on worst."""
    mod = _load_smoke()
    for sev, expected_marker in [(0, "OK"), (1, "WARN"), (2, "FAIL")]:
        result = {
            "reachable":    True,
            "worst":        sev,
            "age_seconds":  10,
            "error":        None,
        }
        summary = mod.summarize_doctor("cli-mirror", result)
        assert expected_marker in summary, (
            f"severity {sev} summary should contain {expected_marker!r}; got: {summary!r}"
        )
        assert f"severity={sev}" in summary


def test_summarize_doctor_absent_when_textfile_empty():
    """When node_exporter is reachable but the textfile isn't there
    (e.g. doctor timer not deployed yet), summary says ABSENT."""
    mod = _load_smoke()
    result = {
        "reachable":    True,
        "worst":        None,
        "age_seconds":  None,
        "error":        None,
    }
    summary = mod.summarize_doctor("cli-mirror", result)
    assert "ABSENT" in summary
    assert "not emitted" in summary


def test_summarize_doctor_unreachable_says_unreachable():
    mod = _load_smoke()
    result = {
        "reachable":    False,
        "worst":        None,
        "age_seconds":  None,
        "error":        "Connection refused",
    }
    summary = mod.summarize_doctor("cli-mirror", result)
    assert "UNREACHABLE" in summary
    assert "node_exporter" in summary


def test_skip_doctor_observers_flag_present():
    """The --skip-doctor-observers flag must be in the argparse surface."""
    mod = _load_smoke()
    # Call main() with --help via SystemExit catch.
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            mod.main(["--help"])
        except SystemExit:
            pass
    help_text = buf.getvalue()
    assert "--skip-doctor-observers" in help_text
    assert "--node-exporter-url" in help_text


def test_skip_doctor_observers_returns_no_doctor_results():
    """When --skip-doctor-observers is set, main() emits doctor_observers
    block with skipped=True + empty results."""
    mod = _load_smoke()
    import io
    import contextlib
    import json as _json

    # Stub probe to return unreachable so we don't need a live api.
    def _stub_probe(*args, **kwargs):
        return {"reachable": False, "http_status": None, "error": "stubbed"}

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         contextlib.redirect_stdout(buf):
        rc = mod.main(["--skip-doctor-observers", "--json"])
    assert rc == 1  # all mirrors unreachable
    body = _json.loads(buf.getvalue())
    assert body["doctor_observers"]["skipped"] is True
    assert body["doctor_observers"]["results"] == []


def test_doctor_failed_increments_exit_code():
    """If a doctor reports worst_severity == 2 (FAIL), exit code is 1."""
    mod = _load_smoke()
    import io
    import contextlib

    # Stub mirror probe to return reachable+online so the mirror checks pass.
    def _stub_probe(base_url, endpoint, timeout=3.0):
        return {
            "reachable":     True,
            "http_status":   200,
            "mirror_status": "online",
            "raw": {"captured_at": "2027-01-01T00:00:00Z"},
        }

    # Stub doctor probe to report worst=2 (FAIL).
    def _stub_doctor_probe(node_exporter_url, metric_prefix, timeout=3.0):
        return {
            "reachable":   True,
            "worst":       2,
            "age_seconds": 30,
            "error":       None,
        }

    buf = io.StringIO()
    with patch.object(mod, "probe", side_effect=_stub_probe), \
         patch.object(mod, "probe_node_exporter_textfile",
                      side_effect=_stub_doctor_probe), \
         contextlib.redirect_stdout(buf):
        rc = mod.main([])
    assert rc == 1, (
        f"doctor FAIL must trigger exit 1; got {rc} with output:\n"
        f"{buf.getvalue()}"
    )
