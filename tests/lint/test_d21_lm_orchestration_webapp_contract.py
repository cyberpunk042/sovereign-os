"""D-21 lm-orchestration webapp surface contract lint.

Pins the D-21 "Language Model Orchestration" cockpit panel to the
sovereignty-clean webapp doctrine: single-file monochrome SPA served by
its API daemon under /webapp/ from the SAME host:port binding as the JSON
endpoints, zero external dependencies, same-origin fetches only, READ-ONLY
(model→hardware assignment is MS003-signed CLI verbs, never web mutations
— R10212).

The panel composes THREE shipped sources (no new data model): the
model-health core (assignment grid), the runtime-modes profile lister
(M076 profiles row), and /proc/cpuinfo (AVX-512 features).

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_HTML = REPO_ROOT / "webapp" / "d-21-lm-orchestration" / "index.html"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "lm-orchestration-api.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "LM_ORCH_API_BIND": "127.0.0.1",
        "LM_ORCH_API_PORT": str(port),
        "SOVEREIGN_OS_METRICS_DIR": "/tmp/sovereign-os-test-metrics",
        "PATH": "/usr/bin:/bin",
    }
    proc = subprocess.Popen(
        ["python3", str(API_DAEMON)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 6
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/healthz", timeout=0.5
            ) as r:
                if r.status == 200:
                    return proc
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("lm-orchestration-api failed to start within 6s")


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"D-21 webapp asset missing: {WEBAPP_HTML}"


def test_webapp_html_is_html5():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>")
    assert "<html lang=" in body
    assert 'name="viewport"' in body


def test_webapp_carries_sovereign_meta_tags():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'name="x-sovereign-module"' in body
    assert "d-21-lm-orchestration-webapp" in body
    assert 'name="x-sovereign-shipped-in"' in body
    assert "D-21" in body
    assert 'name="x-sovereign-standing-rule"' in body
    assert "We do not minimize anything." in body


def test_webapp_has_zero_external_dependencies():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    forbidden_hosts = [
        "https://cdn.", "http://cdn.", "https://cdnjs.",
        "https://unpkg.", "https://fonts.googleapis.",
        "https://fonts.gstatic.", "https://ajax.googleapis.",
        "https://code.jquery.", "https://stackpath.",
        "https://maxcdn.", "https://bootstrapcdn.",
        "https://use.fontawesome.", "//cdn.",
    ]
    for host in forbidden_hosts:
        assert host not in body, f"webapp must NOT reference external host {host!r}"
    assert re.search(r'<script[^>]+src="https?://', body) is None
    assert re.search(r'<link[^>]+href="https?://', body) is None


def test_webapp_fetches_only_same_origin_endpoints():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for m in re.finditer(r'fetch\(\s*(["\'])([^"\']+)\1', body):
        target = m.group(2)
        assert target.startswith("/"), f"fetch() target {target!r} not same-origin"
        assert "//" not in target


def test_webapp_is_read_only_and_clipboard_actions():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "/api/lm-orchestration/grid" in body
    assert re.search(r'fetch\(\s*["\']/(set|apply|mutate)', body) is None, (
        "webapp leaks a mutation verb as fetch() target (R10212 violation)"
    )
    assert "navigator.clipboard.writeText" in body, (
        "Apply must clipboard-copy the MS003-signed profile verb"
    )


def test_webapp_declares_canonical_palette_and_mono():
    """SDD-040 palette contract — the panel must declare --mono + the
    canonical dark-palette hex so the operator UX stays consistent."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "--mono:" in body
    for token in ("--good:#7ad17a", "--bad:#ff7676", "--warn:#e6c062"):
        assert token in body, f"missing canonical palette token {token}"


def test_webapp_inlines_control_surface():
    """SDD-045 — the panel must inline the shared control-surface component
    + carry the #control-surface container, filtered to its slug."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'id="control-surface"' in body
    assert "SovereignControlSurface" in body
    assert "filterSlug:'d-21-lm-orchestration'" in body


def test_api_daemon_serves_webapp_path():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/webapp/", timeout=3
        ) as r:
            assert r.status == 200
            assert "text/html" in r.headers.get("Content-Type", "")
            body = r.read().decode("utf-8")
            assert "<!DOCTYPE html>" in body or "<!doctype html>" in body
            assert "d-21-lm-orchestration" in body
            assert "We do not minimize anything." in body
            assert r.headers.get("X-Sovereign-Module") == \
                "d-21-lm-orchestration-webapp"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_grid_endpoint_shape():
    """/api/lm-orchestration/grid returns the GPU0/GPU1/EXT_GPU/CPU0 cells,
    each with 3 Model slots for the present devices."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/lm-orchestration/grid", timeout=3
        ) as r:
            data = json.loads(r.read())
        slots = [c["slot"] for c in data.get("cells", [])]
        assert slots == ["GPU0", "GPU1", "EXT_GPU", "CPU0"], f"cells: {slots}"
        for c in data["cells"]:
            if c.get("present"):
                assert len(c.get("models", [])) == 3
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_profiles_and_features_endpoints():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/lm-orchestration/profiles", timeout=3
        ) as r:
            prof = json.loads(r.read())
        assert "profiles" in prof and isinstance(prof["profiles"], list)
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/lm-orchestration/features", timeout=3
        ) as r:
            feat = json.loads(r.read())
        assert "cpu" in feat and "gpu" in feat
        # AVX-512 VNNI (VPDPBUSD) capability descriptor must be surfaced.
        assert any("avx512_vnni" == c.get("flag") for c in feat["cpu"])
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_is_read_only():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/lm-orchestration/grid", method="POST", data=b"{}"
        )
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = e.code == 405
        assert raised, "POST must be rejected 405 (read-only cockpit)"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_version_advertises_webapp_surface():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/version", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert "webapp" in data.get("surfaces", [])
        assert "D-21" in data.get("shipped_in", "")
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_surface_map_registers_module():
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "lm-orchestration", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage lm-orchestration failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    matrix = entry.get("matrix", [])
    webapp_row = next((r for r in matrix if r.get("surface") == "webapp"), None)
    assert webapp_row is not None and webapp_row.get("state") == "shipped"


def test_webapp_quotes_standing_rule_in_footer():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "<footer" in body and "</footer>" in body
    footer = body[body.index("<footer"): body.index("</footer>")]
    assert "We do not minimize anything." in footer


def test_nav_registry_includes_d21():
    nav = (REPO_ROOT / "webapp" / "_shared" / "nav-snippet.html").read_text()
    assert "d-21-lm-orchestration" in nav


# ── SDD-111: full-layout delivery (de-minimization per the operator's design) ──

def test_apply_is_centered_in_the_quadrant():
    """The Apply control sits centered INSIDE the 2×2 grid (design), not above it —
    a `.grid-quad` relative wrapper holds `#grid` + an absolutely-centered
    `.apply-wrap`. Apply still routes to the wired exec-rail control (R10212)."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "grid-quad" in body, "the Apply must be centered via a .grid-quad wrapper"
    assert re.search(r'\.apply-wrap\s*\{[^}]*position:\s*absolute', body), (
        "the Apply overlay must be absolutely centered in the quadrant"
    )
    assert "jumpToControl('runtime-mode')" in body or 'jumpToControl("runtime-mode")' in body, (
        "Apply must still route to the wired runtime-mode exec-rail control (R10212)"
    )


def test_each_cell_shows_an_explicit_mode_field():
    """The design shows an explicit per-cell `Mode:` field (not just a derived
    inline string). cellHtml() must render a labelled Mode row."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert re.search(r'Mode:</span>\s*\$\{esc\(c\.mode', body), (
        "each present cell must render an explicit `Mode:` field from real state"
    )


def test_features_cpu_is_tiered_with_honest_deferred_rowhammer():
    """Features-CPU groups the REAL AVX-512 flags under authored T1/T2/T3 tiers,
    and shows an explicit honest-deferred `Rowhammer` row (no producer → never a
    fabricated ✓ — SB-077)."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for tier in ("T1 ·", "T2 ·", "T3 ·"):
        assert tier in body, f"Features-CPU must show the {tier} tier"
    assert "Rowhammer" in body, "the design's Rowhammer row must be present"
    # the Rowhammer row is honest-deferred, not a fabricated capability tick
    assert re.search(r'Rowhammer[^<]*</span>\s*<span class="deferred"', body), (
        "Rowhammer must render as an explicit honest-deferred row (SB-077), never a ✓"
    )


def test_grid_always_visible_when_daemon_down():
    """The 2×2 assignment grid must ALWAYS render — even with the daemon
    unreachable — via a FIXED_CELLS fallback + an initial paint, never
    collapsing to only the centered Apply button (the operator's verbatim bug:
    "I dont see the grid... only an Apply button"). SB-077 honest — slots."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "FIXED_CELLS" in body, "a fixed 4-cell topology fallback must exist"
    for slot in ("GPU0", "GPU1", "EXT_GPU", "CPU0"):
        assert re.search(r"slot:\s*['\"]" + slot + r"['\"]", body), (
            f"FIXED_CELLS must include the {slot} SRP cell"
        )
    assert re.search(
        r"data\.cells\.length\s*\)\s*\?\s*data\.cells\s*:\s*FIXED_CELLS", body
    ), "renderGrid() must render FIXED_CELLS when data.cells is empty"
    assert "renderGrid({})" in body, (
        "an initial paint of the fixed grid must run before the live fetch"
    )


def test_features_and_profiles_sections_never_collapse_when_offline():
    """The Features-CPU tier scaffold + Rowhammer row and the Profiles section
    must render even with no live data (daemon offline) — an honest — per flag
    and an honest "profiles unavailable" placeholder, never a single collapsed
    line (the operator's "seeing all sections with all content"; SB-077)."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    # Features-CPU no longer early-returns a lone "not readable" line: the tiers
    # loop runs unconditionally (probed flag controls the value, not the render).
    assert "const probed = cpu.length > 0" in body, (
        "renderFeatures must always render the tier scaffold, gating only the value"
    )
    assert re.search(r"present:\s*probed\s*\?", body), (
        "each flag must show live state when probed, else an honest — (present:null)"
    )
    # Profiles honest placeholder when the live list is empty.
    assert "profiles unavailable" in body, (
        "the Profiles section must show an honest placeholder when offline, not collapse"
    )
