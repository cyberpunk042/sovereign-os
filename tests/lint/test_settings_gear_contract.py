"""Header settings-gear + DEMO-toggle contract lint (SDD-124).

Pins the operator's requirements (2026-07-10): a settings gear right of "Assist"
in the shared header, opening a non-invasive pane whose first setting is a DEMO
on/off toggle — OFF by default ("I dont want demo by default / in prod"),
localStorage-backed, live-updating. The gear lives in the canonical app-shell
snippet and is distributed to every panel by sync-app-shell.py, so it is present
on ALL pages.

Per SB-077: the gear only flips the shared `sovereign-os.demo` flag; the badge +
sample data still come from each panel's own DEMO treatment. The gear itself
fabricates nothing and makes no network call.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SNIPPET = REPO_ROOT / "webapp" / "_shared" / "app-shell-snippet.html"


def _snippet() -> str:
    return SNIPPET.read_text(encoding="utf-8")


def test_gear_button_is_right_of_assist():
    body = _snippet()
    assert 'id="so-settings-toggle"' in body, "the header must carry the settings gear button"
    ai = body.index('id="so-assist-toggle"')
    gi = body.index('id="so-settings-toggle"')
    assert gi > ai, "the settings gear must be right of the Assist button"


def test_pane_is_non_invasive_and_hidden_by_default():
    body = _snippet()
    assert 'id="so-settings-pane"' in body, "the settings pane must exist"
    # declared hidden by default (opt-in to open) and NOT a full-screen modal
    assert re.search(r'id="so-settings-pane"[^>]*hidden', body), "the pane must be hidden by default"
    assert "#so-settings-pane{position:fixed" in body, "the pane must be an anchored popover (non-invasive)"
    # click-outside + Esc dismissal
    assert "setPaneOpen(false)" in body and "Escape" in body, "the pane must be dismissible (click-outside / Esc)"


def test_demo_toggle_is_off_by_default_localstorage_backed_and_live():
    body = _snippet()
    assert 'id="so-demo-switch"' in body and 'role="switch"' in body, "the DEMO switch must exist"
    # the shared demo flag key + schema guard, default OFF
    assert "sovereign-os.demo" in body and "DEMO_SCHEMA=1" in body
    assert re.search(r"function demoOn\(\)\s*\{[^}]*p\.schema===DEMO_SCHEMA&&p\.on", body), (
        "demoOn() must read the schema-guarded flag (default OFF)"
    )
    assert 'aria-checked="false"' in body, "the switch must render OFF by default (opt-in)"
    # writes localStorage on toggle + live-updates (soDemoApply hook or reload)
    assert re.search(r"function demoSet\(on\)\s*\{[^}]*localStorage\.setItem\(DEMO_KEY", body), (
        "demoSet() must persist the flag to localStorage"
    )
    assert "window.soDemoApply" in body and "location.reload()" in body, (
        "toggling must live-update (soDemoApply hook, else reload)"
    )


def test_gear_makes_no_network_call():
    """The gear/pane is presentation-only — it flips a flag, nothing else (R10212)."""
    body = _snippet()
    # isolate the settings block (from the gear comment to the sticky-close comment)
    start = body.index("Settings popover (⚙)") if "Settings popover" in body else body.index("id=\"so-settings-pane\"")
    seg = body[start: start + 3000]
    assert "fetch(" not in seg and "EventSource" not in seg and "XMLHttpRequest" not in seg, (
        "the settings gear must make no network call"
    )
