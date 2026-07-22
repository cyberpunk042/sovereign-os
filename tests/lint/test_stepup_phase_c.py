"""SDD-509 Phase C — the operator-facing surface: status helper + factor
dispatcher + the source pins for the step-up modal (shared control-surface)
and the config/enrollment pane (auth-tier panel).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STEPUP = REPO / "scripts" / "operator" / "lib" / "stepup.py"
CS_JS = REPO / "webapp" / "_shared" / "control-surface.js"
AUTH_TIER = REPO / "webapp" / "auth-tier" / "index.html"
EXEC_API = REPO / "scripts" / "operator" / "control-exec-api.py"


def _load():
    spec = importlib.util.spec_from_file_location("stepup_pc", STEPUP)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ── status helper ────────────────────────────────────────────────────────────

def test_status_starts_empty_and_fills_after_enrollment(tmp_path):
    m = _load()
    controls = [
        {"id": "os-profile", "auth": "step-up", "privileged": True},
        {"id": "runtime-mode", "auth": "step-up"},
        {"id": "flex-profile", "privileged": False},
        {"id": "selfdef", "privileged": True},  # proxy-only, never step-up
    ]
    st = m.status(tmp_path, tmp_path / "no.toml", controls=controls)
    assert st["enrolled"] is False and st["factors"] == []
    assert st["break_glass_remaining"] == 0
    assert st["elevation_window_seconds"] == 300
    # only the two step-up-tier controls; selfdef (proxy-only) excluded
    assert st["step_up_controls"] == ["os-profile", "runtime-mode"]

    m.enroll(tmp_path)
    m.generate_break_glass(tmp_path, count=10)
    st2 = m.status(tmp_path, tmp_path / "no.toml", controls=controls)
    assert st2["enrolled"] is True
    assert "totp" in st2["factors"] and "breakglass" in st2["factors"]
    assert st2["break_glass_remaining"] == 10


def test_verify_factor_dispatch_routes_each_family(tmp_path):
    m = _load()
    # totp
    secret, _ = m.enroll(tmp_path)
    import time
    code = m.totp_code(secret, time.time())
    assert m.verify_factor_and_elevate(tmp_path, tmp_path / "n.toml", "op", "totp", code) is True
    # breakglass
    codes = m.generate_break_glass(tmp_path, count=3)
    assert m.verify_factor_and_elevate(tmp_path, tmp_path / "n.toml", "op", "breakglass", codes[0]) is True
    # an unknown factor → None (not set up), never a crash
    assert m.verify_factor_and_elevate(tmp_path, tmp_path / "n.toml", "op", "smoke", "x") is None


# ── the step-up modal lives in the shared control-surface ────────────────────

def test_control_surface_carries_the_step_up_modal():
    js = CS_JS.read_text(encoding="utf-8")
    assert "function askStepUp(" in js, "the step-up modal must live in control-surface.js"
    assert "step_up_required" in js, "execAction must branch on the 401 step_up_required"
    # the modal rides the SAME sanctioned write endpoint (no new POST verb)
    assert "function stepupPost(" in js and "stepup: stepup" in js
    # exactly one POST verb in the whole component (single-POST doctrine)
    import re
    assert re.findall(r'method:\s*["\'](POST|PUT|DELETE|PATCH)["\']', js) == ["POST"]
    # the successful verify re-runs the action so the elevation is consumed
    assert "execAction(card, sys, opts, confirmed)" in js


# ── the config/enrollment pane lives in the auth-tier panel ──────────────────

def test_auth_tier_carries_the_step_up_config_pane():
    html = AUTH_TIER.read_text(encoding="utf-8")
    assert 'id="stepup-pane"' in html, "auth-tier must mount the step-up config pane"
    assert "/api/control/stepup" in html, "the pane must read the step-up status endpoint"
    # enrollment + regenerate ride the sanctioned exec endpoint via a stepup body
    packed = html.replace(" ", "")
    assert 'action:"enroll"' in packed, "the pane must drive enroll through the exec rail"
    assert 'action:"regenerate_break_glass"' in packed, "the pane must offer break-glass regen"
    assert "/api/control/execute" in html, "the pane mutates only via the sanctioned endpoint"


def test_exec_api_serves_the_step_up_routes():
    src = EXEC_API.read_text(encoding="utf-8")
    assert "/api/control/stepup" in src, "daemon must serve the read-only status route"
    assert "_handle_stepup(" in src and 'body.get("stepup")' in src, (
        "step-up auth sub-actions must ride the /api/control/execute body"
    )
    # verify / request_otp / enroll / regenerate all handled
    for action in ('"verify"', '"request_otp"', '"enroll"', '"regenerate_break_glass"'):
        assert action in src, f"stepup handler missing action {action}"
