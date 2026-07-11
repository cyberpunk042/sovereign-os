"""SDD-067 — app-shell contract (the 5th canonical per-panel snippet).

Mirrors test_keyboard_nav_contract.py: a single source-of-truth block lives at
webapp/_shared/app-shell-snippet.html and is duplicated verbatim into each
ADOPTED panel's <body>. This lint enforces:

  * the canonical source exists and carries the BEGIN/END markers;
  * the catalog inside it covers the full D-00..D-25 panel set;
  * every ADOPTED panel embeds the BYTE-IDENTICAL block;
  * the chrome stays non-mutating (no fetch/XHR/form POST in the block) —
    per the design grammar, chrome navigates + explains, never executes.

Adoption is opt-in: only panels in ADOPTED_APP_SHELL_PANELS are checked, so
the ~50 not-yet-adopted panels stay green while the rollout proceeds one panel
at a time. Keep this list in lockstep with ADOPTED_PANELS in
scripts/webapp/sync-app-shell.py.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED = REPO_ROOT / "webapp" / "_shared" / "app-shell-snippet.html"

BEGIN = "<!-- APP-SHELL:BEGIN M067 -->"
END = "<!-- APP-SHELL:END M067 -->"
_BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)

# Opt-in adoption list — grow one/few at a time (lockstep with the generator).
ADOPTED_APP_SHELL_PANELS = [
    "course",
    "anti-minimization-audit", "auditor", "auth-tier", "build-configurator",
    "compliance", "cpu-features", "d-01-active-sessions", "d-02-profile-choices",
    "d-03-model-health", "d-04-costs", "d-05-traces", "d-06-pending-approvals",
    "d-07-memory-changes", "d-08-rollback-points", "d-09-hardware-pressure",
    "d-10-eval-history", "d-11-adapter-status", "d-12-networking",
    "d-13-filesystem-grants", "d-14-capability-tokens", "d-15-sandboxes",
    "d-16-audit", "d-17-quarantine", "d-18-trust-scores",
    "d-19-super-model-manifest", "d-20-peace-machine-health",
    "d-21-lm-orchestration", "d-22-lm-status-operability", "d-23-models-catalog",
    "d-24-cpu-features", "d-25-selfdef-management", "code-console", "doc-coverage",
    "edge-firewall", "emulate", "flash", "global-history", "master-dashboard",
    "models-catalog", "network-edge", "orchestration", "personalization",
    "profile-generation", "router", "runtime-modes", "selfdef-management",
    "science", "surface-map", "trinity", "ups", "ux-design-audit", "weaver",
]


def _canonical_block() -> str:
    src = SHARED.read_text(encoding="utf-8")
    m = _BLOCK_RE.search(src)
    assert m, f"canonical app-shell block markers missing in {SHARED}"
    return m.group(0)


def test_shared_app_shell_snippet_exists():
    """The canonical source-of-truth block MUST live at
    webapp/_shared/app-shell-snippet.html so adopters copy it verbatim and
    this contract has a single source of truth."""
    assert SHARED.is_file(), f"canonical app-shell snippet missing: {SHARED}"
    src = SHARED.read_text(encoding="utf-8")
    assert BEGIN in src and END in src, "app-shell snippet missing BEGIN/END markers"


def test_app_shell_catalog_covers_full_panel_set():
    """The sidemenu catalog MUST include every D-00..D-25 id so no panel is
    unreachable from the shell."""
    src = SHARED.read_text(encoding="utf-8")
    for n in range(0, 26):
        if n == 12:
            continue  # D-12 ships as the split panels D-12a / D-12b (below)
        did = f"D-{n:02d}"
        assert f"'{did}'" in src, f"app-shell catalog missing {did}"
    # the two D-12 split panels
    for did in ("D-12a", "D-12b"):
        assert f"'{did}'" in src, f"app-shell catalog missing {did}"


def test_app_shell_reuses_personalization_key():
    """The theme toggle MUST read/write the SAME personalization localStorage
    object the panels already use — one source of truth, no divergence."""
    src = SHARED.read_text(encoding="utf-8")
    assert "sovereign-os.personalization" in src, (
        "app-shell theme toggle must use the sovereign-os.personalization key"
    )


SANCTIONED_CHAT_FETCH = "/api/code-console/chat"


def test_app_shell_chrome_is_non_mutating():
    """Per the design grammar the chrome navigates + explains; it MUST NOT
    execute anything server-side — with ONE sanctioned exception (R10212):
    the Assistant "Ask" footer may POST to the loopback chat
    (/api/code-console/chat, 127.0.0.1 only), the same non-mutating inference
    read-compute the Code Console / D-22 panels use. No XHR / sendBeacon /
    form-POST, and no other or external fetch, is permitted."""
    block = _canonical_block()
    low = block.lower()
    for forbidden in ("xmlhttprequest", "navigator.sendbeacon", 'method="post"', "method='post'"):
        assert forbidden not in low, (
            f"app-shell block must be non-mutating; found: {forbidden}"
        )
    # every fetch() target MUST be the single sanctioned loopback chat path — a
    # string literal, never a template/variable/external URL that could hide egress.
    fetches = re.findall(r"fetch\(\s*(['\"])(.*?)\1", block)
    literal_fetch_count = len(re.findall(r"fetch\(", block))
    assert literal_fetch_count == len(fetches), (
        "every fetch() in the app-shell must take a string-literal URL "
        "(no template/variable target that could hide external egress)"
    )
    for _quote, url in fetches:
        assert url == SANCTIONED_CHAT_FETCH, (
            f"only the sanctioned loopback chat fetch ({SANCTIONED_CHAT_FETCH}) "
            f"is allowed in the app-shell; found fetch to: {url!r}"
        )


def test_app_shell_respects_reduced_motion():
    """Hover/transition feel MUST be gated behind prefers-reduced-motion."""
    src = SHARED.read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in src, (
        "app-shell must gate motion behind prefers-reduced-motion"
    )


def test_adopted_panels_embed_identical_block():
    """Every ADOPTED panel MUST embed the byte-identical canonical block."""
    block = _canonical_block()
    for slug in ADOPTED_APP_SHELL_PANELS:
        path = REPO_ROOT / "webapp" / slug / "index.html"
        assert path.is_file(), f"adopted panel missing: {path}"
        html = path.read_text(encoding="utf-8")
        m = _BLOCK_RE.search(html)
        assert m, f"{slug}: app-shell block missing (run sync-app-shell.py --apply)"
        assert m.group(0) == block, (
            f"{slug}: app-shell block differs from canonical "
            f"(run: python3 scripts/webapp/sync-app-shell.py --apply)"
        )


def test_adopted_panels_place_block_after_body():
    """The block MUST sit inside <body> (after the opening tag), never in
    <head> — the runtime reparent depends on it, and this proves the shell
    was injected non-destructively rather than displacing head content."""
    body_re = re.compile(r"(?mi)^[ \t]*<body[^>]*>")
    for slug in ADOPTED_APP_SHELL_PANELS:
        html = (REPO_ROOT / "webapp" / slug / "index.html").read_text(encoding="utf-8")
        bm = body_re.search(html)
        assert bm, f"{slug}: no <body> tag"
        blk = _BLOCK_RE.search(html)
        assert blk, f"{slug}: app-shell block missing"
        assert blk.start() > bm.end(), (
            f"{slug}: app-shell block must be after <body>, not in <head>"
        )
