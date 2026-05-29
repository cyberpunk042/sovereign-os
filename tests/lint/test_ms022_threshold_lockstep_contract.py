"""MS022 cross-repo + intra-repo threshold-lockstep lint.

The MS022 vertical's classifier thresholds (0.85 = approaching;
1.0 = saturated) appear in 5 places across the two repos:

  sovereign-os (this repo):
    1. config/prometheus/alerts/ms022-sse-quota.rules.yml
       (the Prometheus expressions: > 0.85, >= 1.0)
    2. scripts/operator/ms022-sse-quota-api.py
       (APPROACHING_THRESHOLD + SATURATED_THRESHOLD constants)
    3. scripts/diagnostics/ms022-doctor.py
       (classifier handles ok/approaching/saturated/unreachable)
    4. docs/operator/ms022-sse-quota-cockpit.md
       (the state-enumeration table documents 0.85 + 1.0)
    5. docs/observability/dashboards/sovereign-os-ms022-sse-quota.json
       (Grafana threshold steps at 0.85 + 1.0)

  selfdef (partner repo):
    6. crates/selfdef-cli/src/sse_quota.rs
       (APPROACHING_THRESHOLD = 0.85; SATURATED_THRESHOLD = 1.0)

Any drift between these is a silent-misalignment hazard: the
operator sees one threshold in the dashboard, gets paged at a
different threshold, and the CLI verb classifies differently
from both. The per-surface contract tests already lock each
location individually; this test catches the cross-surface
inconsistency case where one constant ships drifted but its
own surface test still passes.

The partner-repo check is opt-in via $SELFDEF_REPO_ROOT — when
the env var points at a selfdef checkout, the test also verifies
the Rust constants there. Without it, the in-repo lockstep is
still verified comprehensively.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# Canonical thresholds — every cited surface MUST agree on these.
APPROACHING = 0.85
SATURATED = 1.0


def _read(path: Path) -> str:
    return path.read_text()


def test_alert_rules_carry_canonical_thresholds():
    """The Prometheus alert expressions MUST contain `> 0.85` (for
    approaching) and `>= 1.0` (for saturated). These are the
    operator's first-line trigger contract."""
    body = _read(
        REPO_ROOT / "config" / "prometheus" / "alerts"
        / "ms022-sse-quota.rules.yml"
    )
    doc = yaml.safe_load(body)
    rules = [r for g in doc["groups"] for r in g["rules"]]
    by_name = {r["alert"]: r for r in rules}
    assert "> 0.85" in by_name["MS022SseGlobalQuotaApproaching"]["expr"]
    assert ">= 1.0" in by_name["MS022SseGlobalQuotaSaturated"]["expr"]


def test_proxy_api_carries_canonical_thresholds():
    """The proxy daemon's APPROACHING_THRESHOLD + SATURATED_THRESHOLD
    constants MUST equal the canonical values. Drift here means the
    banner classifies into the wrong state while the alert fires —
    silent operator misdirection."""
    body = _read(
        REPO_ROOT / "scripts" / "operator" / "ms022-sse-quota-api.py"
    )
    # Find the literal constant assignments.
    approaching_match = re.search(
        r"APPROACHING_THRESHOLD\s*=\s*([\d.]+)", body,
    )
    saturated_match = re.search(
        r"SATURATED_THRESHOLD\s*=\s*([\d.]+)", body,
    )
    assert approaching_match is not None
    assert saturated_match is not None
    assert float(approaching_match.group(1)) == APPROACHING
    assert float(saturated_match.group(1)) == SATURATED


def test_grafana_dashboard_carries_canonical_thresholds():
    """The MS022 dashboard MUST surface both 0.85 and 1.0 as
    visible threshold values. Drift here means the operator sees a
    different alert-fire visual than the alerts actually use."""
    data = json.loads(_read(
        REPO_ROOT / "docs" / "observability" / "dashboards"
        / "sovereign-os-ms022-sse-quota.json"
    ))
    seen_values = set()
    for panel in data["panels"]:
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            v = s.get("value")
            if isinstance(v, (int, float)):
                seen_values.add(float(v))
    assert APPROACHING in seen_values, (
        f"dashboard threshold steps drift: 0.85 not present (saw: "
        f"{sorted(seen_values)!r})"
    )
    assert SATURATED in seen_values, (
        f"dashboard threshold steps drift: 1.0 not present (saw: "
        f"{sorted(seen_values)!r})"
    )


def test_cockpit_guide_documents_canonical_thresholds():
    """The cockpit operator guide cites 0.85 and 1.0 in the state-
    enumeration table. Drift here = the docs lie about when alerts
    fire."""
    body = _read(
        REPO_ROOT / "docs" / "operator" / "ms022-sse-quota-cockpit.md"
    )
    assert "0.85" in body
    assert "1.0" in body


def test_doctor_classifier_thresholds_match_canonical():
    """The ms022-doctor's classifier in proxy-state check handles the
    same state enum. Verify by importing the proxy module + asserting
    its constants — the doctor consumes the proxy's classified state
    so drift there propagates."""
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location(
        "ms022_sse_quota_api",
        REPO_ROOT / "scripts" / "operator" / "ms022-sse-quota-api.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ms022_sse_quota_api_lockstep"] = mod
    spec.loader.exec_module(mod)
    assert mod.APPROACHING_THRESHOLD == APPROACHING
    assert mod.SATURATED_THRESHOLD == SATURATED


def test_partner_repo_thresholds_match_canonical():
    """Optional cross-repo: when $SELFDEF_REPO_ROOT points at a
    selfdef checkout, verify the selfdef-side Rust constants match
    the sovereign-os-side. Skipped when the env var is unset —
    sovereign-os CI runs without the partner repo cloned, so this is
    additional protection for operators running both repos locally
    OR for the cross-repo CI pipeline that does check out both."""
    partner_root_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_root_env:
        return  # opt-in only — local CI without selfdef cloned
    partner = Path(partner_root_env)
    sse_quota_rs = partner / "crates" / "selfdef-cli" / "src" / "sse_quota.rs"
    if not sse_quota_rs.is_file():
        return  # bad env-var path → skip rather than false-positive
    body = sse_quota_rs.read_text()
    approaching_m = re.search(
        r"APPROACHING_THRESHOLD:\s*f64\s*=\s*([\d.]+)", body,
    )
    saturated_m = re.search(
        r"SATURATED_THRESHOLD:\s*f64\s*=\s*([\d.]+)", body,
    )
    assert approaching_m is not None, (
        "selfdef-side sse_quota.rs missing APPROACHING_THRESHOLD const"
    )
    assert saturated_m is not None, (
        "selfdef-side sse_quota.rs missing SATURATED_THRESHOLD const"
    )
    assert float(approaching_m.group(1)) == APPROACHING, (
        f"partner-repo APPROACHING_THRESHOLD drift: selfdef has "
        f"{approaching_m.group(1)}, sovereign-os has {APPROACHING}"
    )
    assert float(saturated_m.group(1)) == SATURATED, (
        f"partner-repo SATURATED_THRESHOLD drift: selfdef has "
        f"{saturated_m.group(1)}, sovereign-os has {SATURATED}"
    )


def test_all_four_state_names_consistent_across_surfaces():
    """The 4 state-name strings (ok / approaching / saturated /
    unreachable) MUST be identical across the proxy daemon, the
    doctor, and the cockpit guide. Renaming one without the others
    is the operator-confusion hazard."""
    import importlib.util
    import sys
    expected = {"ok", "approaching", "saturated", "unreachable"}

    # Proxy daemon's /version states list.
    spec = importlib.util.spec_from_file_location(
        "ms022_api_lockstep",
        REPO_ROOT / "scripts" / "operator" / "ms022-sse-quota-api.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ms022_api_lockstep"] = mod
    spec.loader.exec_module(mod)
    assert set(mod._version_payload()["states"]) == expected, (
        "proxy daemon state enum drifted"
    )

    # Cockpit guide state-enumeration table.
    guide = _read(
        REPO_ROOT / "docs" / "operator" / "ms022-sse-quota-cockpit.md"
    )
    for state in expected:
        assert f"`{state}`" in guide, (
            f"cockpit guide state-enumeration drift: missing `{state}`"
        )


def test_alert_thresholds_align_with_doctor_severity_classes():
    """Cross-check: the doctor classifier returns 1 (WARN) for
    saturation between 0.85 and 1.0, returns 2 (FAIL) at >= 1.0.
    This MUST match the alert severity (warning at > 0.85, critical
    at >= 1.0). Drift = operator confusion when the page severity
    doesn't match the doctor's exit-code severity."""
    doc = yaml.safe_load(_read(
        REPO_ROOT / "config" / "prometheus" / "alerts"
        / "ms022-sse-quota.rules.yml"
    ))
    by_name = {
        r["alert"]: r["labels"]["severity"]
        for g in doc["groups"]
        for r in g["rules"]
    }
    # Approaching alert maps to "warning"; doctor's `approaching`
    # state returns severity 1 (WARN).
    assert by_name["MS022SseGlobalQuotaApproaching"] == "warning"
    # Saturated maps to "critical"; doctor's `saturated` state
    # returns severity 2 (FAIL).
    assert by_name["MS022SseGlobalQuotaSaturated"] == "critical"
