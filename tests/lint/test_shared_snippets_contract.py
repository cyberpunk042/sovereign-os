"""Shared-snippet sync + drift contract (F-2026-073 / F-2026-074, 2026-07-17).

F-2026-073 flagged five `webapp/_shared/` snippet families as byte-duplicated
with (claimed) no sync tool and no drift gate. Empirically the five split by how
their duplication is actually managed, and this lint closes the genuine gaps:

  * a11y — 22 panels were missing the WCAG 2.4.1 skip-link entirely (F-2026-074).
    scripts/webapp/sync-snippet.py injects the MARKED canonical a11y block into
    them; this lint runs the tool's own --check drift gate and asserts EVERY
    panel now carries the skip-link.
  * demo-mode.js/css — opt-in, inlined byte-identical where present; this lint is
    the verbatim drift gate they lacked (a panel that carries the demo badge must
    carry the canonical block byte-for-byte).
  * control-surface.js/css — already inlined 61/61 and gated by
    test_control_surface_component.py; asserted present here as the gate-of-record.
  * nav / responsive — the canonical _shared file is NOT the byte-source of what
    panels carry (0/61 verbatim); documented here as needing a real reconciliation
    pass, not a mechanical gate, so the gap is visible instead of silently green.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "scripts" / "webapp" / "sync-snippet.py"
SHARED = REPO / "webapp" / "_shared"
WEBAPP = REPO / "webapp"


def _tool():
    spec = importlib.util.spec_from_file_location("sync_snippet", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _panels():
    return [d for d in sorted(WEBAPP.iterdir())
            if d.is_dir() and d.name != "_shared" and (d / "index.html").is_file()]


# --- a11y family (marker-managed, F-2026-074) ---


def test_tool_exists():
    assert TOOL.is_file(), f"missing {TOOL}"


def test_a11y_family_registered_and_marked():
    mod = _tool()
    assert "a11y" in mod.FAMILIES, "a11y family not registered"
    fam = mod.FAMILIES["a11y"]
    src = (SHARED / fam["file"]).read_text(encoding="utf-8")
    assert fam["begin"] in src and fam["end"] in src, "a11y canonical missing markers"
    block = mod._canonical_block(fam)
    assert block.startswith(fam["begin"]) and block.endswith(fam["end"])


def test_a11y_no_drift_in_adopted_panels():
    """CI gate: every a11y-adopted panel's block == canonical. Runs the tool's
    own --check so the test + the operator command share one source of truth."""
    r = subprocess.run(
        [sys.executable, str(TOOL), "--check"],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, (
        f"a11y snippet drift — run `python3 scripts/webapp/sync-snippet.py "
        f"--apply`\n{r.stdout}\n{r.stderr}"
    )


def test_skip_link_present_in_every_panel():
    """F-2026-074: the skip-link must be present in EVERY cockpit panel now."""
    missing = [p.name for p in _panels()
               if "so-skip-link" not in (p / "index.html").read_text(encoding="utf-8")]
    assert not missing, f"panels still missing the WCAG 2.4.1 skip-link: {missing}"


def test_a11y_adopters_carry_marked_block():
    """The back-ported panels carry the MARKED a11y block (so the gate manages
    them) — not just some ad-hoc skip-link."""
    mod = _tool()
    begin = mod.FAMILIES["a11y"]["begin"]
    for slug in mod.FAMILIES["a11y"]["adopted"]:
        idx = WEBAPP / slug / "index.html"
        assert idx.is_file() and begin in idx.read_text(encoding="utf-8"), (
            f"a11y adopter {slug} does not carry the marked block"
        )


# --- demo-mode family (verbatim drift gate — the gap it lacked) ---


# Panels that carry an OLDER demo-mode packaging (the SDD-116/119 combined
# comment+css+js block) rather than the byte-current canonical _shared copies.
# Grandfathered as a RATCHET: these two are the pre-existing drift F-2026-073
# flagged; a real reconciliation pass (rewriting their demo-mode section) is
# tracked as remaining. The gate below still fails on ANY NEW drifter, so the
# duplication can only shrink from here, never grow.
_DEMO_MODE_KNOWN_DRIFT = {"warp", "personalization"}


def test_demo_mode_verbatim_where_present():
    """The drift gate demo-mode lacked: a panel carrying the demo-mode badge MUST
    inline the canonical demo-mode.js + demo-mode.css byte-for-byte, EXCEPT the
    grandfathered known-drift panels. A new drifter (not on the allowlist) fails —
    so this ratchets the duplication down and never lets fresh drift in."""
    js = (SHARED / "demo-mode.js").read_text(encoding="utf-8").strip()
    css = (SHARED / "demo-mode.css").read_text(encoding="utf-8").strip()
    new_drift = []
    adopters = 0
    still_drifting = set()
    for p in _panels():
        html = (p / "index.html").read_text(encoding="utf-8")
        if "so-demo-badge" not in html:
            continue
        adopters += 1
        drifted = (js not in html) or (css not in html)
        if not drifted:
            continue
        if p.name in _DEMO_MODE_KNOWN_DRIFT:
            still_drifting.add(p.name)
        else:
            new_drift.append(p.name)
    assert adopters >= 1, "no demo-mode adopters found — registry/probe changed?"
    assert not new_drift, (
        f"NEW demo-mode byte-drift vs canonical _shared: {new_drift} — re-inline "
        f"the canonical webapp/_shared/demo-mode.{{js,css}} into these panels"
    )
    # Ratchet integrity: don't let the allowlist rot — if a grandfathered panel
    # was reconciled, drop it from _DEMO_MODE_KNOWN_DRIFT.
    stale = _DEMO_MODE_KNOWN_DRIFT - still_drifting
    assert not stale, (
        f"these panels no longer drift — remove them from _DEMO_MODE_KNOWN_DRIFT: {stale}"
    )


# --- control-surface family (gated already — asserted as gate-of-record) ---


def test_control_surface_gate_of_record_exists():
    """control-surface.js/css are inlined 61/61 and gated by
    test_control_surface_component.py — assert that gate still exists so this
    finding's coverage claim can't silently regress."""
    gate = REPO / "tests" / "lint" / "test_control_surface_component.py"
    assert gate.is_file(), "control-surface verbatim gate missing"
    body = gate.read_text(encoding="utf-8")
    assert "test_every_panel_inlines_the_control_surface" in body, (
        "control-surface verbatim-inline gate removed"
    )


# --- nav / responsive (honest remaining — divergent, not mechanically gateable) ---


def test_nav_responsive_divergence_is_documented():
    """nav/responsive canonical _shared files are NOT the byte-source of panel
    content (0/61 verbatim). Rather than a false-green gate, the tool documents
    this as needing reconciliation. Assert the doc note is present so the gap
    stays visible."""
    tool_src = TOOL.read_text(encoding="utf-8")
    assert "genuinely divergent" in tool_src and "reconciliation" in tool_src, (
        "nav/responsive divergence note removed from sync-snippet.py"
    )
