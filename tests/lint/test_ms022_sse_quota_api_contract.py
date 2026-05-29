"""MS022 SSE quota API + master-dashboard banner — contract test.

Locks the parser + state-classifier + JSON shape that the
master-dashboard's MS022 banner consumes. The producer
selfdef commit 77b4499 ships 6 Prometheus gauges; this script
parses them + emits a stable JSON envelope.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_PATH = REPO_ROOT / "scripts" / "operator" / "ms022-sse-quota-api.py"
MASTER_DASHBOARD = REPO_ROOT / "webapp" / "master-dashboard" / "index.html"


def _load_api():
    spec = importlib.util.spec_from_file_location("ms022_sse_quota_api", API_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ms022_sse_quota_api"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_api_module_loads():
    mod = _load_api()
    assert hasattr(mod, "probe")
    assert hasattr(mod, "_parse_metrics")
    assert hasattr(mod, "_classify_state")


def test_thresholds_match_alert_rules():
    """The api's threshold constants MUST match the alert rules.
    Drift = banner says ok while Prometheus is firing — silent
    operator misdirection."""
    mod = _load_api()
    assert mod.APPROACHING_THRESHOLD == 0.85
    assert mod.SATURATED_THRESHOLD == 1.0


def test_parse_extracts_six_gauges_from_exposition():
    """The parser correctly extracts each producer-side gauge."""
    mod = _load_api()
    body = """\
# HELP selfdef_sse_subscribers_global_active Foo.
# TYPE selfdef_sse_subscribers_global_active gauge
selfdef_sse_subscribers_global_active 25
# HELP selfdef_sse_subscribers_global_cap Foo.
# TYPE selfdef_sse_subscribers_global_cap gauge
selfdef_sse_subscribers_global_cap 100
# HELP selfdef_sse_subscribers_global_saturation Foo.
# TYPE selfdef_sse_subscribers_global_saturation gauge
selfdef_sse_subscribers_global_saturation 0.250000
# HELP selfdef_sse_subscribers_per_token_cap Foo.
# TYPE selfdef_sse_subscribers_per_token_cap gauge
selfdef_sse_subscribers_per_token_cap 8
# HELP selfdef_sse_subscribers_per_token Foo.
# TYPE selfdef_sse_subscribers_per_token gauge
selfdef_sse_subscribers_per_token{token_fp="aaaa1111"} 4
selfdef_sse_subscribers_per_token{token_fp="bbbb2222"} 8
selfdef_sse_subscribers_per_token{token_fp="cccc3333"} 1
# HELP selfdef_sse_subscribers_per_token_saturated Foo.
# TYPE selfdef_sse_subscribers_per_token_saturated gauge
selfdef_sse_subscribers_per_token_saturated 1
"""
    out = mod._parse_metrics(body)
    assert out["global_active"] == 25
    assert out["global_cap"] == 100
    assert abs(out["global_saturation"] - 0.25) < 1e-6
    assert out["per_token_cap"] == 8
    assert out["per_token_saturated"] == 1
    assert len(out["per_token_counts"]) == 3
    # Sorted by descending subscribers.
    assert out["per_token_counts"][0] == {"token_fp": "bbbb2222", "subscribers": 8}
    assert out["per_token_counts"][1]["subscribers"] == 4
    assert out["per_token_counts"][2]["subscribers"] == 1


def test_classify_state_ok_below_approaching_threshold():
    mod = _load_api()
    parsed = {
        "global_saturation": 0.5,
        "per_token_saturated": 0,
    }
    assert mod._classify_state(parsed) == "ok"


def test_classify_state_approaching_above_threshold_but_below_saturation():
    mod = _load_api()
    parsed = {
        "global_saturation": 0.9,  # > 0.85 but < 1.0
        "per_token_saturated": 0,
    }
    assert mod._classify_state(parsed) == "approaching"


def test_classify_state_approaching_when_any_token_saturated():
    """Even with global saturation below 0.85, a per-token saturated
    state lifts the overall classification to approaching — that
    operator is being throttled NOW."""
    mod = _load_api()
    parsed = {
        "global_saturation": 0.2,
        "per_token_saturated": 1,
    }
    assert mod._classify_state(parsed) == "approaching"


def test_classify_state_saturated_at_full_cap():
    mod = _load_api()
    parsed = {
        "global_saturation": 1.0,
        "per_token_saturated": 5,
    }
    assert mod._classify_state(parsed) == "saturated"


def test_classify_state_unreachable_when_metrics_absent():
    """When the producer hasn't published (selfdefd down OR
    node_exporter not running), saturation is None — the state
    is `unreachable`, NOT `ok` (which would be misleading)."""
    mod = _load_api()
    parsed = {
        "global_saturation": None,
        "per_token_saturated": 0,
    }
    assert mod._classify_state(parsed) == "unreachable"


def test_probe_returns_unreachable_envelope_on_fetch_failure(monkeypatch):
    """When _fetch_metrics_text returns None (daemon unreachable),
    probe() returns the canonical unreachable envelope with state=
    unreachable + null metrics + a non-empty detail line."""
    mod = _load_api()
    monkeypatch.setattr(mod, "_fetch_metrics_text", lambda: None)
    out = mod.probe()
    assert out["state"] == "unreachable"
    assert out["metrics"] is None
    assert out["detail"]


def test_probe_returns_classified_state_on_success(monkeypatch):
    mod = _load_api()
    body = (
        "selfdef_sse_subscribers_global_active 90\n"
        "selfdef_sse_subscribers_global_cap 100\n"
        "selfdef_sse_subscribers_global_saturation 0.900000\n"
        "selfdef_sse_subscribers_per_token_cap 8\n"
        "selfdef_sse_subscribers_per_token_saturated 0\n"
    )
    monkeypatch.setattr(mod, "_fetch_metrics_text", lambda: body)
    out = mod.probe()
    assert out["state"] == "approaching"
    assert out["metrics"]["global_active"] == 90
    assert out["thresholds"]["approaching"] == 0.85


def test_version_payload_states_match_classifier_states():
    """The /version endpoint advertises the same states the
    classifier returns. Drift here = operator misdirection."""
    mod = _load_api()
    payload = mod._version_payload()
    assert set(payload["states"]) == {"ok", "approaching", "saturated", "unreachable"}


# ---------------------------------------------------------------------------
# Master-dashboard banner integration — locks the wire shape between
# the producer metric names, the proxy JSON shape, and the banner DOM.
# ---------------------------------------------------------------------------


def test_master_dashboard_has_ms022_banner():
    """The master-dashboard MUST carry the MS022 banner DIV so the
    operator sees SSE quota state on D-00, not just in Grafana."""
    body = MASTER_DASHBOARD.read_text()
    assert 'id="ms022-sse-quota-banner"' in body, (
        "master-dashboard missing the MS022 SSE quota banner DIV"
    )
    for child_id in ("ms022-sse-label", "ms022-sse-detail", "ms022-sse-active"):
        assert f'id="{child_id}"' in body, (
            f"master-dashboard banner missing child {child_id}"
        )


def test_master_dashboard_polls_canonical_endpoint():
    """The banner JS MUST fetch /api/ms022/sse-quota (the contract
    this api script serves)."""
    body = MASTER_DASHBOARD.read_text()
    assert "/api/ms022/sse-quota" in body, (
        "master-dashboard banner not wired to /api/ms022/sse-quota"
    )


def test_master_dashboard_renderer_is_called_on_each_tick():
    """The renderMS022SseQuotaBanner function MUST be invoked inside
    renderM060Grid so the banner refreshes on the same 30s cadence
    as the M060 banner."""
    body = MASTER_DASHBOARD.read_text()
    assert "renderMS022SseQuotaBanner()" in body, (
        "master-dashboard renderer not wired into the refresh loop"
    )


def test_master_dashboard_links_to_grafana_dashboard():
    """The banner footer MUST link to the MS022 Grafana dashboard
    (uid sovereign-os-ms022-sse-quota shipped commit 69f8dba) so
    operators drill from the banner straight to the panel."""
    body = MASTER_DASHBOARD.read_text()
    assert "sovereign-os-ms022-sse-quota" in body, (
        "master-dashboard banner missing Grafana dashboard deep-link"
    )
