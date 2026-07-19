"""Shared control-surface component + universal adoption (SDD-045 §2/§4, Phase C).

The control-surface renders config/control-systems.yaml (served at GET
/control-systems) as the Controls surface — the operator's "everything can be
turned on/off + tons of modes and profiles". Per the single-file sovereignty
doctrine it is INLINED into every panel (no <script src>), from a canonical
source in webapp/_shared/ that a lockstep lint keeps in sync.

Locks: canonical source present, same-origin + read-only, endpoint served,
and EVERY panel inlines the component verbatim (so all dashboards are control
surfaces) with no external script.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEBAPP = REPO / "webapp"
JS_SRC = WEBAPP / "_shared" / "control-surface.js"
CSS_SRC = WEBAPP / "_shared" / "control-surface.css"
API = REPO / "scripts" / "operator" / "build-configurator-api.py"
REGISTRY = REPO / "config" / "control-systems.yaml"


def _panels() -> list[Path]:
    return sorted(
        d / "index.html" for d in WEBAPP.iterdir()
        if d.is_dir() and not d.name.startswith("_") and (d / "index.html").is_file()
    )


def test_canonical_source_files_exist():
    assert JS_SRC.is_file(), f"missing canonical {JS_SRC}"
    assert CSS_SRC.is_file(), f"missing canonical {CSS_SRC}"


def test_component_is_same_origin_only():
    body = JS_SRC.read_text(encoding="utf-8")
    for m in re.finditer(r'fetch\(\s*(["\'])([^"\']+)\1', body):
        target = m.group(2)
        assert target.startswith("/") and "//" not in target, (
            f"control-surface.js fetch target {target!r} is not same-origin"
        )
    for host in ("http://", "https://", "cdn.", "unpkg", "jsdelivr"):
        assert host not in body, f"control-surface.js references external {host!r}"


def test_component_executes_via_sanctioned_endpoint_and_keeps_copy_fallback():
    """R10274: the control-surface now EXECUTES a control (the sanctioned
    same-origin control-exec-api POST) while keeping the copyable command as a
    labelled fallback. R10212 is preserved by test_component_preserves_boundary
    below (proxy-only controls get no execute) — the web still never
    *arbitrarily* mutates; it posts only to the one allowlisted exec daemon."""
    body = JS_SRC.read_text(encoding="utf-8")
    # copy fallback stays
    assert "clipboard" in body, "component must keep the change_cli copy fallback"
    # the ONLY mutating request is the sanctioned same-origin exec endpoint
    assert "/api/control/execute" in body, (
        "control-surface.js must POST to the sanctioned same-origin control-exec-api"
    )
    posts = re.findall(r'method:\s*["\'](POST|PUT|DELETE|PATCH)["\']', body)
    assert posts == ["POST"], (
        f"control-surface.js must issue exactly one POST (to the exec daemon), got {posts}"
    )


def test_component_preserves_boundary():
    """R10212: selfdef/perimeter are signed-proxy ONLY — the component must
    render no execute affordance for them. The client boundary set must mirror
    the server's _action_exec.SELFDEF_OWNED (strict equality drift-guarded in
    tests/lint/test_control_surface_execute_boundary.py)."""
    body = JS_SRC.read_text(encoding="utf-8")
    assert "PROXY_ONLY" in body and '"selfdef"' in body and '"perimeter"' in body, (
        "component must carry the selfdef/perimeter proxy-only boundary"
    )
    assert "execute_local" in body and "isProxyOnly" in body, (
        "component must gate the execute affordance on the proxy-only boundary"
    )


def test_component_renders_the_copy_command():
    body = JS_SRC.read_text(encoding="utf-8")
    assert "change_cli" in body and "data-cmd" in body and "cs-cmd" in body, (
        "control-surface.js must render change_cli as a copy-command control"
    )


def test_component_does_not_duplicate_buttons_as_inert_pills():
    """An option already rendered as a one-click button must NOT ALSO appear as a
    grey `.cs-opt` pill (a duplicated value reads as clickable-but-dead). The
    component derives the enum button values and filters them out of the pill row,
    keeping pills only for options with no button (free-input hint / semantic
    label like a toggle's on/off vs its enable/disable verb)."""
    body = JS_SRC.read_text(encoding="utf-8")
    assert "buttonVals" in body and "filter(" in body, (
        "cardHtml must filter option pills against the enum button values so "
        "button options aren't duplicated as inert grey pills"
    )


def test_api_serves_control_systems_endpoint():
    body = API.read_text(encoding="utf-8")
    assert "/control-systems" in body and "_load_control_systems" in body, (
        "API must serve /control-systems from config/control-systems.yaml"
    )


def test_every_panel_inlines_the_control_surface():
    """SDD-045 'ALL DASHBOARDS ALMOST SHOULD HAVE FEATURES OPTIONS AND
    PROFILES' — every panel must carry the control surface, INLINED verbatim
    from the canonical source (single-file doctrine + lockstep), with no
    external <script src>."""
    js = JS_SRC.read_text(encoding="utf-8").strip()
    css = CSS_SRC.read_text(encoding="utf-8").strip()
    src_re = re.compile(r'<script[^>]*\bsrc\s*=\s*["\'][^"\']*\.js["\']', re.IGNORECASE)
    missing_component, missing_css, has_src, missing_container = [], [], [], []
    for panel in _panels():
        html = panel.read_text(encoding="utf-8")
        slug = panel.parent.name
        if js not in html:
            missing_component.append(slug)
        if css not in html:
            missing_css.append(slug)
        if 'id="control-surface"' not in html:
            missing_container.append(slug)
        if src_re.search(html):
            has_src.append(slug)
    assert not missing_component, f"panels not inlining the component (lockstep drift?): {missing_component}"
    assert not missing_css, f"panels not inlining the component CSS: {missing_css}"
    assert not missing_container, f"panels without a #control-surface container: {missing_container}"
    assert not has_src, f"panels with a forbidden external <script src=.js>: {has_src}"


def test_master_dashboard_shows_all_controls_others_filter():
    """The aggregator renders ALL controls (renderControls, no filter); every
    other panel filters to its slug via filterSlug."""
    md = (WEBAPP / "master-dashboard" / "index.html").read_text(encoding="utf-8")
    assert "renderControls" in md, "master-dashboard must render the full control surface"
    # a representative scoped panel filters by its slug
    rm = (WEBAPP / "runtime-modes" / "index.html").read_text(encoding="utf-8")
    assert "filterSlug:'runtime-modes'" in rm, "runtime-modes must filter to its own controls"
