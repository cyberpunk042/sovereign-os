"""Cockpit DEMO-mode contract lint (SDD-116).

Pins the SB-077 reconciliation for DEMO mode: opt-in (off by default), ALWAYS
badged, and the DEMO render path makes NO network call (the sample data is
client-side constants; R10212 strengthened). The shared helper is canonical in
webapp/_shared/demo-mode.{js,css}; Code Console is the first consumer + the
personalization panel carries the global toggle.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Per SB-077 (sacrosanct): never fabricate data presented as real — DEMO data is
labelled sample data, opt-in, always badged, never confusable with live telemetry.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_JS = REPO_ROOT / "webapp" / "_shared" / "demo-mode.js"
SHARED_CSS = REPO_ROOT / "webapp" / "_shared" / "demo-mode.css"
CODE_CONSOLE = REPO_ROOT / "webapp" / "code-console" / "index.html"
PERSONALIZATION = REPO_ROOT / "webapp" / "personalization" / "index.html"

BADGE_TEXT = "sample data — not real telemetry"


def test_shared_helper_present_and_opt_in():
    js = SHARED_JS.read_text(encoding="utf-8")
    css = SHARED_CSS.read_text(encoding="utf-8")
    assert "sovereign-os.demo" in js, "the demo flag must live in localStorage sovereign-os.demo"
    assert "window.soDemo" in js, "the shared helper must expose window.soDemo"
    # opt-in: on() returns a truthy only when the stored flag is explicitly on
    assert re.search(r"function on\(\)\s*\{[^}]*p\.on", js, re.DOTALL), (
        "soDemo.on() must read the stored flag (opt-in; default off)"
    )
    assert "#so-demo-badge" in css and "so-demo-badge" in js, "the DEMO badge must be defined + rendered"
    assert BADGE_TEXT in js, "the badge must carry the unmistakable 'not real telemetry' label (SB-077)"
    # the helper itself must make NO network call
    assert "fetch(" not in js and "EventSource" not in js and "XMLHttpRequest" not in js, (
        "the demo helper must make no network call"
    )


def test_code_console_demo_is_opt_in_badged_and_offline():
    body = CODE_CONSOLE.read_text(encoding="utf-8")
    # inlines the shared helper + the badge
    assert "window.soDemo" in body and "#so-demo-badge" in body
    assert BADGE_TEXT in body
    # a demoActive() gate exists
    assert "function demoActive()" in body
    # sample data uses obvious placeholders (never confusable with real ids)
    assert "DEMO_SESSIONS" in body and "demo-session-01" in body
    # the DEMO render short-circuit in refresh() makes NO fetch (client-side only)
    m = re.search(r"if \(demoActive\(\)\) \{(.*?)\n    \}", body, re.DOTALL)
    assert m, "refresh() must contain a demoActive() short-circuit"
    assert "fetch(" not in m.group(1), "the DEMO render path must make NO fetch (SB-077 / R10212)"
    # no EventSource opens while DEMO is active
    assert re.search(r"if \(!demoActive\(\)\) \{\s*try \{\s*const es = new EventSource", body), (
        "the panel must open NO EventSource in DEMO mode (zero network calls)"
    )
    # the composer gives a canned DEMO reply with no fetch
    assert re.search(r"if \(demoActive\(\)\) \{[^}]*\[DEMO\]", body, re.DOTALL), (
        "the composer must return a canned [DEMO] reply in DEMO mode (no model call)"
    )


def test_personalization_carries_the_global_toggle():
    body = PERSONALIZATION.read_text(encoding="utf-8")
    assert 'id="demo-control"' in body, "personalization must carry the DEMO on/off toggle"
    assert 'data-demo="on"' in body and 'data-demo="off"' in body
    assert "window.soDemo" in body, "personalization must inline the shared demo helper"
    assert "window.soDemo.set(" in body, "the toggle must write the demo flag"
    # off is the default-selected button (opt-in)
    assert re.search(r'data-demo="off"[^>]*class="demo-btn on"', body), (
        "DEMO must default to OFF in the toggle (opt-in)"
    )


def test_d21_lm_orchestration_demo(): 
    """SDD-117 — D-21 reuses the shared helper for DEMO mode: opt-in, badged,
    sample grid/profiles/features with placeholder ids, and NO network call in
    the demo path (no fetch, no EventSource)."""
    body = (REPO_ROOT / "webapp" / "d-21-lm-orchestration" / "index.html").read_text(encoding="utf-8")
    assert "window.soDemo" in body and BADGE_TEXT in body
    assert "function demoActive()" in body
    assert "DEMO_GRID" in body and "demo/" in body  # obvious placeholder model ids
    m = re.search(r"if \(demoActive\(\)\) \{(.*?)\n    \}", body, re.DOTALL)
    assert m and "fetch(" not in m.group(1) and "fetchJson(" not in m.group(1), (
        "the D-21 DEMO render path must make NO fetch (SB-077 / R10212)"
    )
    assert re.search(r"if \(!demoActive\(\)\) \{\s*try \{\s*const es = new EventSource", body), (
        "D-21 must open NO EventSource in DEMO mode"
    )


def test_d22_lm_status_operability_demo():
    """SDD-118 — D-22 reuses the shared helper for DEMO mode: opt-in, badged,
    sample devices with placeholder ids + latency/heatmap, and NO network call in
    the demo path (no fetch, no EventSource; canned [DEMO] chat reply)."""
    body = (REPO_ROOT / "webapp" / "d-22-lm-status-operability" / "index.html").read_text(encoding="utf-8")
    assert "window.soDemo" in body and BADGE_TEXT in body
    assert "function demoActive()" in body
    assert "DEMO_DEVICES" in body and "demo/" in body
    m = re.search(r"if \(demoActive\(\)\) \{(.*?)\n    \}", body, re.DOTALL)
    assert m and "fetchDevices(" not in m.group(1) and "fetch(" not in m.group(1), (
        "the D-22 DEMO render path must make NO fetch (SB-077 / R10212)"
    )
    assert re.search(r"if \(!demoActive\(\)\) \{\s*try \{\s*const es = new EventSource", body), (
        "D-22 must open NO EventSource in DEMO mode"
    )
    assert re.search(r"if \(demoActive\(\)\) \{[^}]*\[DEMO\]", body, re.DOTALL), (
        "the D-22 chat must return a canned [DEMO] reply in DEMO mode (no model call)"
    )


def test_d03_model_health_demo():
    """SDD-119 (DEMO batch 1) — D-03 Model Health reuses the shared helper: opt-in,
    badged, sample health with placeholder ids, and NO network call in the demo path
    (no fetch, no EventSource). The helper loads in <head> so window.soDemo exists
    before the panel script's first refresh()."""
    body = (REPO_ROOT / "webapp" / "d-03-model-health" / "index.html").read_text(encoding="utf-8")
    assert "window.soDemo" in body and BADGE_TEXT in body
    assert "function demoActive()" in body
    assert "DEMO_HEALTH" in body and "demo/" in body
    # the demo short-circuit selects sample data with no fetch
    assert re.search(r"demoActive\(\)\s*\?\s*DEMO_HEALTH\s*:\s*await fetchHealth\(\)", body), (
        "refresh() must select DEMO_HEALTH (no fetch) when demo is active"
    )
    # the EventSource is skipped in demo (zero network)
    assert re.search(r"if \(demoActive\(\)\) throw new Error\('DEMO", body), (
        "D-03 must open NO EventSource in DEMO mode"
    )
    # the helper is inlined in <head> (before the panel script) so soDemo exists first
    head = body[:body.index("</head>")]
    assert "window.soDemo" in head, "the demo helper must load in <head> before the panel script"


def test_d23_models_catalog_demo():
    """SDD-120 (DEMO batch 1 cont.) — D-23 Models Catalog reuses the shared helper:
    opt-in, badged, sample catalog with placeholder ids, NO network in the demo path
    (no fetch, no EventSource), helper in <head>."""
    body = (REPO_ROOT / "webapp" / "d-23-models-catalog" / "index.html").read_text(encoding="utf-8")
    assert "window.soDemo" in body and BADGE_TEXT in body
    assert "function demoActive()" in body
    assert "DEMO_CATALOG" in body and "demo/" in body
    m = re.search(r"if \(demoActive\(\)\) \{(.*?)\n    \}", body, re.DOTALL)
    assert m and "fetch(" not in m.group(1), "the D-23 DEMO render path must make NO fetch"
    assert re.search(r"if \(!demoActive\(\)\) \{\s*try \{\s*const es = new EventSource", body), (
        "D-23 must open NO EventSource in DEMO mode"
    )
    assert "window.soDemo" in body[:body.index("</head>")], "helper must load in <head>"


def _assert_head_demo(slug, demo_const):
    body = (REPO_ROOT / "webapp" / slug / "index.html").read_text(encoding="utf-8")
    assert "window.soDemo" in body and BADGE_TEXT in body, f"{slug}: helper/badge"
    assert "function demoActive()" in body, f"{slug}: demoActive gate"
    assert demo_const in body and "demo/" in body, f"{slug}: sample data placeholders"
    assert "window.soDemo" in body[:body.index("</head>")], f"{slug}: helper must load in <head>"
    return body


def test_d10_eval_history_demo():
    """SDD-120 — D-10 Eval History: badged sample evals, no fetch/EventSource in demo."""
    body = _assert_head_demo("d-10-eval-history", "DEMO_EVALS")
    assert re.search(r"demoActive\(\)\s*\?\s*DEMO_EVALS\s*:\s*await fetchEvals\(\)", body)
    assert re.search(r"if \(demoActive\(\)\) throw new Error\('DEMO", body), "no EventSource in demo"


def test_d11_adapter_status_demo():
    """SDD-120 — D-11 Adapter Status: badged sample inventory, no fetch/EventSource in demo."""
    body = _assert_head_demo("d-11-adapter-status", "DEMO_ADAPTERS")
    assert re.search(r"demoActive\(\)\s*\?\s*DEMO_ADAPTERS\s*:\s*await fetchAdapters\(\)", body)
    assert re.search(r"if \(demoActive\(\)\) throw new Error\('DEMO", body), "no EventSource in demo"


def test_models_catalog_demo():
    """SDD-120 — models-catalog: badged sample catalog via load() short-circuit, no fetch in demo."""
    body = _assert_head_demo("models-catalog", "DEMO_MODELS")
    m = re.search(r"if \(demoActive\(\)\) \{(.*?)\n    return;\n  \}", body, re.DOTALL)
    assert m and "fetch(" not in m.group(1), "the models-catalog DEMO load path must make NO fetch"


# ── SDD-121 (DEMO batch 2 — hardware + compute posture) ────────────────────────

def test_d09_hardware_pressure_demo():
    """SDD-121 — D-09 Hardware Pressure: badged sample PSI/CCD/GPU/ZFS/backpressure,
    refresh() short-circuit (no fetchPressure), /api/hardware/stream skipped in demo."""
    body = _assert_head_demo("d-09-hardware-pressure", "DEMO_PRESSURE")
    assert re.search(r"demoActive\(\)\s*\?\s*DEMO_PRESSURE\s*:\s*await fetchPressure\(\)", body)
    assert "if (!demoActive()) try {\n  const es = new EventSource('/api/hardware/stream')" in body, (
        "D-09 must skip the hardware EventSource in demo"
    )


def test_runtime_modes_demo():
    """SDD-121 — runtime-modes: badged sample active mode + modes grid; both render
    fns short-circuit before any /api/runtime-modes fetch in demo."""
    body = _assert_head_demo("runtime-modes", "DEMO_MODES")
    assert body.count("if (demoActive()) {") >= 2, "both render fns need a demo short-circuit"
    assert "for (const mode of DEMO_MODES.modes)" in body


def test_orchestration_demo():
    """SDD-121 — orchestration: badged sample rules+metrics via load() ternary, no fetch in demo."""
    body = _assert_head_demo("orchestration", "DEMO_ORCH")
    assert re.search(r"demoActive\(\)\s*\?\s*DEMO_ORCH\s*:\s*await", body), (
        "orchestration load() must select DEMO_ORCH (no fetch) in demo"
    )


def test_d24_cpu_features_demo():
    """SDD-121 — D-24 CPU Features: badged sample probe/workloads/advisory via refresh()
    short-circuit (render(DEMO_CPU...)), /api/cpu-features/stream skipped in demo."""
    body = _assert_head_demo("d-24-cpu-features", "DEMO_CPU")
    assert "render(DEMO_CPU.probe, DEMO_CPU.workloads, DEMO_CPU.advisory)" in body
    assert "if (!demoActive()) try { const es = new EventSource('/api/cpu-features/stream')" in body, (
        "D-24 must skip the cpu-features EventSource in demo"
    )


def test_cpu_features_demo():
    """SDD-121 — cpu-features: badged sample AVX posture via load() ternary, no fetch in demo."""
    body = _assert_head_demo("cpu-features", "DEMO_AVX")
    assert re.search(r"demoActive\(\)\s*\?\s*DEMO_AVX\s*:\s*await", body), (
        "cpu-features load() must select DEMO_AVX (no fetch) in demo"
    )


def test_d04_costs_demo():
    """SDD-121 — D-04 Costs: badged sample today/projects/profiles/models/trend/policy via
    refresh() short-circuit (no fetchCosts), /api/costs/stream skipped in demo."""
    body = _assert_head_demo("d-04-costs", "DEMO_COSTS")
    assert re.search(r"demoActive\(\)\s*\?\s*DEMO_COSTS\s*:\s*await fetchCosts\(\)", body)
    assert "if (!demoActive()) try {\n  const es = new EventSource('/api/costs/stream')" in body, (
        "D-04 must skip the costs EventSource in demo"
    )
