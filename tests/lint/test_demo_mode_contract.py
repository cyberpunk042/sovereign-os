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

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_JS = REPO_ROOT / "webapp" / "_shared" / "demo-mode.js"
SHARED_CSS = REPO_ROOT / "webapp" / "_shared" / "demo-mode.css"
CODE_CONSOLE = REPO_ROOT / "webapp" / "code-console" / "index.html"
PERSONALIZATION = REPO_ROOT / "webapp" / "personalization" / "index.html"
MANIFEST = REPO_ROOT / "scripts" / "webapp" / "demo-panels.json"

BADGE_TEXT = "sample data — not real telemetry"


def _load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["panels"]


def test_manifest_covers_exactly_the_demo_capable_panels():
    """scripts/webapp/demo-panels.json (the single source of truth shared with
    demo-capture.mjs) must list EXACTLY the panels that carry the demo helper —
    no drift in either direction. Adding a panel to the rollout means adding it
    here, so the capture tool + this lint pick it up automatically."""
    manifest_slugs = {p["slug"] for p in _load_manifest()}
    on_disk = {
        idx.parent.name
        for idx in (REPO_ROOT / "webapp").glob("*/index.html")
        if "so-demo-badge" in idx.read_text(encoding="utf-8")
        and idx.parent.name != "personalization"  # global toggle, not a demo-data panel
    }
    only_manifest = manifest_slugs - on_disk
    only_disk = on_disk - manifest_slugs
    assert not only_manifest and not only_disk, (
        f"manifest/disk drift — only in manifest: {sorted(only_manifest)}; "
        f"only on disk (add to demo-panels.json): {sorted(only_disk)}"
    )


def test_manifest_panels_satisfy_the_generic_demo_contract():
    """Every manifest panel passes the generic demo contract (helper + badge,
    demoActive() gate, DEMO_<X> with demo/ placeholders; helper in <head> unless
    the panel predates the SDD-119 head rule — headInjected:false). This grows
    automatically with the rollout; per-panel bespoke asserts (EventSource guards /
    ternaries) stay as the explicit cases below."""
    for p in _load_manifest():
        slug, const = p["slug"], p["demoConst"]
        body = (REPO_ROOT / "webapp" / slug / "index.html").read_text(encoding="utf-8")
        assert "window.soDemo" in body and BADGE_TEXT in body, f"{slug}: helper/badge"
        assert "function demoActive()" in body, f"{slug}: demoActive gate"
        assert const in body and ("demo/" in body or "demo-" in body), (
            f"{slug}: {const} + obvious demo/ or demo- placeholder ids"
        )
        if p.get("headInjected", True):
            assert "window.soDemo" in body[: body.index("</head>")], (
                f"{slug}: helper must load in <head> (SDD-119 rule)"
            )


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


# ── SDD-122 (DEMO batch 3 — punchy verdicts + compute meta) ────────────────────

def test_d01_active_sessions_demo():
    """SDD-122 — D-01 Active Sessions: badged sample summary+sessions via refresh()
    short-circuit (no fetchSessions), /api/sessions/stream skipped in demo."""
    body = _assert_head_demo("d-01-active-sessions", "DEMO_SESSIONS")
    assert re.search(r"demoActive\(\)\s*\?\s*DEMO_SESSIONS\s*:\s*await fetchSessions\(\)", body)
    assert "if (!demoActive()) try {\n  const es = new EventSource('/api/sessions/stream')" in body, (
        "D-01 must skip the sessions EventSource in demo"
    )


def test_d20_peace_machine_health_demo():
    """SDD-122 — D-20 Peace Machine Health: badged sample verdict via load() short-circuit,
    no /api/d-20/snapshot fetch in demo."""
    body = _assert_head_demo("d-20-peace-machine-health", "DEMO_D20")
    m = re.search(r"if \(demoActive\(\)\) \{ seed = Object\.assign\(seed, DEMO_D20\);(.*?)return; \}", body, re.DOTALL)
    assert m and "fetch(" not in m.group(1), "D-20 demo branch must make NO fetch"


def test_d18_trust_scores_demo():
    """SDD-122 — D-18 Trust Scores: badged sample tiles/tools via load() short-circuit,
    no /api/d-18/snapshot fetch in demo."""
    body = _assert_head_demo("d-18-trust-scores", "DEMO_D18")
    m = re.search(r"if \(demoActive\(\)\) \{ seed = Object\.assign\(seed, DEMO_D18\);(.*?)return; \}", body, re.DOTALL)
    assert m and "fetch(" not in m.group(1), "D-18 demo branch must make NO fetch"


def test_d19_super_model_manifest_demo():
    """SDD-122 — D-19 Super-Model Manifest: badged sample version/phases/milestones via
    load() short-circuit, no /api/d-19/snapshot fetch in demo."""
    body = _assert_head_demo("d-19-super-model-manifest", "DEMO_D19")
    m = re.search(r"if \(demoActive\(\)\) \{\n      snap = Object\.assign\(snap, DEMO_D19\);(.*?)return;\n    \}", body, re.DOTALL)
    assert m and "fetch(" not in m.group(1), "D-19 demo branch must make NO fetch"


def test_d02_profile_choices_demo():
    """SDD-122 — D-02 Profile Choices: badged sample active profile via refresh() short-circuit,
    no /api/profile/show fetch in demo."""
    body = _assert_head_demo("d-02-profile-choices", "DEMO_PROFILE")
    assert re.search(r"demoActive\(\)\s*\?\s*DEMO_PROFILE\s*:\s*await fetchActiveProfile\(\)", body)


def test_profile_generation_demo():
    """SDD-122 — profile-generation: badged sample allocations via load() ternary, no fetch in demo."""
    body = _assert_head_demo("profile-generation", "DEMO_PROFGEN")
    assert re.search(r"demoActive\(\)\s*\?\s*DEMO_PROFGEN\s*:\s*await", body), (
        "profile-generation load() must select DEMO_PROFGEN (no fetch) in demo"
    )


# ── SDD-125 (DEMO batch 4 — selfdef mirror family) ─────────────────────────────

def test_selfdef_mirror_family_demo_branches_make_no_fetch():
    """SDD-125 — the five uniform `/api/d-XX/snapshot` mirror panels select the DEMO
    seed with NO fetch in the demo path (the else-branch holds the real fetch)."""
    for slug, const in [
        ("d-13-filesystem-grants", "DEMO_D13"), ("d-14-capability-tokens", "DEMO_D14"),
        ("d-15-sandboxes", "DEMO_D15"), ("d-16-audit", "DEMO_D16"), ("d-17-quarantine", "DEMO_D17"),
    ]:
        body = (REPO_ROOT / "webapp" / slug / "index.html").read_text(encoding="utf-8")
        assert "window.soDemo" in body[: body.index("</head>")], f"{slug}: helper in <head>"
        assert f"if (demoActive()) {{ seed = Object.assign(seed, {const}); }}" in body, (
            f"{slug}: demo branch must select {const} with no fetch"
        )


def test_d12_networking_demo_branch_and_sse_guard():
    """SDD-125 — d-12 (outlier): demo applies the sample snapshot with no fetch, and the
    /api/d-12/stream EventSource is skipped in demo."""
    body = (REPO_ROOT / "webapp" / "d-12-networking" / "index.html").read_text(encoding="utf-8")
    assert "window.soDemo" in body[: body.index("</head>")], "d-12: helper in <head>"
    assert "if (demoActive()) { applySnapshot(DEMO_D12);" in body, "d-12 demo branch must applySnapshot(DEMO_D12)"
    assert "if (!demoActive()) startSSE();" in body, "d-12 must skip the SSE stream in demo"


# ── SDD-126 (DEMO batch 5a — edge/mgmt) + UX fixes ─────────────────────────────

def test_batch5a_demo_branches_make_no_fetch():
    """SDD-126 — the five edge/mgmt panels short-circuit to their DEMO const before any
    fetch (two aggregators destructure the merged const; three single-endpoint panels
    render the const directly)."""
    for slug, marker in [
        ("edge-firewall", "const {version,state,candidates,recommend} = DEMO_EDGE_FIREWALL;"),
        ("network-edge", "const {version,interfaces,natChain,opnStatus,opnCaps,detect} = DEMO_NETWORK_EDGE;"),
        ("selfdef-management", "if (demoActive()) { const d = DEMO_SELFDEF;"),
        ("ups", "if (demoActive()) { render(DEMO_UPS);"),
        ("science", "if (demoActive()) { render(DEMO_SCIENCE);"),
    ]:
        body = (REPO_ROOT / "webapp" / slug / "index.html").read_text(encoding="utf-8")
        assert "window.soDemo" in body[: body.index("</head>")], f"{slug}: helper in <head>"
        assert marker in body, f"{slug}: demo short-circuit ({marker[:40]}…)"


def test_demo_badge_renders_bottom_center():
    """SDD-126 — the DEMO badge sits bottom-center (not top-right, where it covered the
    settings gear). Pin the canonical CSS so it can't regress."""
    css = SHARED_CSS.read_text(encoding="utf-8")
    assert "#so-demo-badge" in css
    assert "bottom:" in css and "left: 50%" in css and "translateX(-50%)" in css, (
        "the badge must be anchored bottom-center"
    )
    assert "top: calc(var(--so-header-h" not in css, "the badge must not be pinned top-right anymore"
