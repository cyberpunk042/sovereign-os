"""M060 R10137/R10140/R10141 — personalization webapp + apply-snippet contract.

The operator's standing direction (2026-05-19) catalogues 3 non-negotiable
personalization R-rows:

  R10137 — Dashboard styling — dark mode + light mode + auto-from-system
  R10140 — Dashboard styling — operator-configurable accent color
  R10141 — Dashboard styling — operator-configurable typography scale

This contract guards:

  1. The personalization control surface at /webapp/personalization/
     ships the 3 controls (theme + accent + typography).
  2. The apply-snippet is embedded in the master-dashboard <head> so
     prefs apply pre-paint (no FOUC) on the cockpit's entry point.
  3. Per-dashboard rollout: each D-NN dashboard that adopts the
     snippet reads from the SAME localStorage key (sovereign-os.
     personalization, schema v1) so prefs are coherent across all
     surfaces.

Per "Respect the projects": personalization is a CLIENT-SIDE preference
layer (localStorage on the operator's browser). The server NEVER mutates
prefs and the apply-snippet NEVER ships prefs anywhere — read-only doctrine
applies to this surface like every other cockpit webapp.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONALIZATION = REPO_ROOT / "webapp" / "personalization" / "index.html"
MASTER_DASHBOARD = REPO_ROOT / "webapp" / "master-dashboard" / "index.html"

# The single source of truth for the localStorage key + schema version.
EXPECTED_KEY = "sovereign-os.personalization"
EXPECTED_SCHEMA = "1"


def test_personalization_page_exists():
    assert PERSONALIZATION.is_file(), (
        f"personalization control surface missing: {PERSONALIZATION}"
    )


def test_personalization_page_ships_three_controls():
    """R10137 + R10140 + R10141 — all 3 controls present."""
    html = PERSONALIZATION.read_text(encoding="utf-8")
    # R10137 theme: 3 buttons (auto/dark/light)
    for theme in ("data-theme=\"auto\"", "data-theme=\"dark\"", "data-theme=\"light\""):
        assert theme in html, f"R10137 missing theme button: {theme}"
    # R10140 accent: swatches + custom hex input
    assert "accent-control" in html and "swatches" in html, (
        "R10140 missing accent swatch control"
    )
    assert "accent-custom" in html and "#RRGGBB" in html.upper() or "rrggbb" in html.lower(), (
        "R10140 missing custom-hex accent input"
    )
    # R10141 typography: at least 3 scale buttons (compact/default/large)
    for scale in ("data-scale=\"0.85\"", "data-scale=\"1\"", "data-scale=\"1.15\""):
        assert scale in html, f"R10141 missing typography button: {scale}"


def test_personalization_page_uses_canonical_localstorage_key():
    """All apply-snippets must read/write the SAME localStorage key
    so prefs are coherent across the cockpit. Schema-version v1."""
    html = PERSONALIZATION.read_text(encoding="utf-8")
    assert EXPECTED_KEY in html, (
        f"personalization page must use canonical localStorage key "
        f"{EXPECTED_KEY!r}"
    )
    assert "SCHEMA_V = 1" in html or "SCHEMA_V=1" in html, (
        "personalization page must declare schema v1"
    )


def test_personalization_page_supports_import():
    """SDD-105 — the export→import round-trip is complete: the page ships a
    validated paste-JSON import that reuses the existing apply chain and
    honest-rejects invalid input (never partially-applies)."""
    html = PERSONALIZATION.read_text(encoding="utf-8")
    # the import UI: a button + a paste textarea + an apply button
    assert 'id="import-btn"' in html, "personalization must ship an import button"
    assert 'id="import-json"' in html and "textarea" in html, (
        "personalization import must offer a paste textarea"
    )
    assert 'id="import-apply"' in html, "personalization import must have an apply button"
    # validate-then-apply: parse + schema check + field validation
    assert "JSON.parse" in html, "import must JSON.parse the pasted profile"
    assert "SCHEMA_V" in html, "import must validate the schema version"
    assert "#RRGGBB" in html.upper() or "[0-9a-fA-F]{6}" in html, (
        "import must validate the accent hex"
    )
    # reuse the existing apply chain (no new apply logic)
    for helper in ("applyPrefs(", "renderAll(", "savePrefs("):
        assert helper in html, f"import must reuse {helper} (the existing apply chain)"
    # symmetric to the existing clipboard export
    assert "export-btn" in html, "the export half of the round-trip must remain"


def test_personalization_file_roundtrip():
    """SDD-107 — a file round-trip beside the clipboard/paste one: a Blob-download
    export + a FileReader-upload import that reuses the SAME validator."""
    html = PERSONALIZATION.read_text(encoding="utf-8")
    # file export: a button + a Blob download
    assert 'id="export-file"' in html, "personalization must ship a file-download export"
    assert "new Blob(" in html and "createObjectURL" in html and "revokeObjectURL" in html, (
        "the file export must build + revoke a Blob object URL"
    )
    # file import: a hidden <input type=file> + a FileReader
    assert 'id="import-file"' in html and 'type="file"' in html, (
        "personalization must offer a file-upload input"
    )
    assert "FileReader" in html and "readAsText" in html, (
        "the file import must read the file with FileReader"
    )
    # ONE validator for both paths — paste + file both call applyImportedText
    assert "function applyImportedText(" in html, (
        "the validator must be extracted into applyImportedText (shared by paste + file)"
    )
    assert html.count("applyImportedText(") >= 3, (
        "applyImportedText must be defined + called by BOTH the paste and file import paths"
    )
    # the clipboard/paste round-trip still stands
    assert 'id="export-btn"' in html and 'id="import-apply"' in html


def test_personalization_page_is_client_side_only():
    """Server NEVER mutates prefs. The page must NOT POST/PUT/DELETE
    to any /api/ endpoint."""
    html = PERSONALIZATION.read_text(encoding="utf-8")
    # Exclude the shared app-shell chrome (governed by test_app_shell_contract;
    # its one sanctioned loopback Assistant chat is not a personalization mutation).
    html = re.sub(r"<!-- APP-SHELL:BEGIN M067 -->.*?<!-- APP-SHELL:END M067 -->",
                  "", html, flags=re.DOTALL)
    for forbidden in ("method: 'POST'", "method:'POST'", "method=\"POST\"",
                      "method: 'PUT'", "method:'PUT'", "method=\"PUT\"",
                      "method: 'DELETE'", "method:'DELETE'", "method=\"DELETE\""):
        assert forbidden not in html, (
            f"personalization is CLIENT-SIDE only; found server-mutation: {forbidden!r}"
        )


def test_master_dashboard_embeds_apply_snippet():
    """The master-dashboard (cockpit entry point) MUST embed the
    apply-snippet in <head> so prefs apply pre-paint."""
    html = MASTER_DASHBOARD.read_text(encoding="utf-8")
    head_split = html.split("</head>", 1)
    assert len(head_split) == 2, "master-dashboard <head> not found"
    head = head_split[0]
    assert EXPECTED_KEY in head, (
        "master-dashboard <head> must contain the personalization apply-snippet"
    )
    # apply-snippet writes to documentElement attributes/style
    assert "setAttribute('data-theme'" in head or "setAttribute(\"data-theme\"" in head, (
        "apply-snippet must set data-theme on documentElement"
    )
    assert "setProperty('--accent'" in head or "setProperty(\"--accent\"" in head, (
        "apply-snippet must set --accent custom property"
    )
    assert "--font-scale" in head, (
        "apply-snippet must set --font-scale custom property"
    )


def test_master_dashboard_honors_font_scale():
    """Master-dashboard's html/body font-size MUST honor the --font-scale
    custom property (calc(... * var(--font-scale))) so R10141 actually
    takes effect."""
    html = MASTER_DASHBOARD.read_text(encoding="utf-8")
    # Look for calc(<base> * var(--font-scale)) on html or body font-size
    assert "calc(14px * var(--font-scale" in html or \
           "calc(14px*var(--font-scale" in html, (
        "master-dashboard must honor --font-scale in its base font-size "
        "(via calc(14px * var(--font-scale, 1)))"
    )


def test_master_dashboard_honors_light_theme():
    """Master-dashboard MUST declare a html[data-theme=\"light\"] override
    so R10137 light mode actually renders."""
    html = MASTER_DASHBOARD.read_text(encoding="utf-8")
    assert "html[data-theme=\"light\"]" in html or \
           "html[data-theme='light']" in html, (
        "master-dashboard must declare html[data-theme=\"light\"] override "
        "for R10137 light mode"
    )


def test_master_dashboard_links_to_personalization():
    """A discoverable link to /webapp/personalization/ MUST be present
    in master-dashboard so the operator can reach the controls without
    typing the URL by hand."""
    html = MASTER_DASHBOARD.read_text(encoding="utf-8")
    assert "../personalization/" in html or \
           "/webapp/personalization/" in html, (
        "master-dashboard must link to /webapp/personalization/"
    )


def test_personalization_page_metadata_cites_catalog():
    """Operator-§1g visibility: the personalization page MUST cite its
    catalog source (M060 R10137/R10140/R10141) in its meta."""
    html = PERSONALIZATION.read_text(encoding="utf-8")
    assert "R10137" in html and "R10140" in html and "R10141" in html, (
        "personalization page must cite all 3 catalog R-rows"
    )
    assert "M060" in html, "personalization page must cite M060 milestone"


# Rollout tracker — every D-NN dashboard that has adopted the
# apply-snippet shows here. The list grows as the rollout proceeds;
# the contract guarantees adopters carry the snippet with the same
# canonical key + schema (so prefs are coherent across surfaces).
ADOPTED_DASHBOARDS = [
    "master-dashboard",
    # D-01..D-11 (sovereign-os-native D-NN dashboards):
    "d-01-active-sessions",
    "d-02-profile-choices",
    "d-03-model-health",
    "d-04-costs",
    "d-05-traces",
    "d-06-pending-approvals",
    "d-07-memory-changes",
    "d-08-rollback-points",
    "d-09-hardware-pressure",
    "d-10-eval-history",
    "d-11-adapter-status",
    # D-12 split-pattern (network-edge + edge-firewall together
    # serve the D-12 networking cockpit per M060 R10112-R10113):
    "network-edge",
    "edge-firewall",
    "d-12-networking",
    # M060 cross-repo mirror dashboards (6):
    "d-13-filesystem-grants",
    "d-14-capability-tokens",
    "d-15-sandboxes",
    "d-16-audit",
    "d-17-quarantine",
    "d-18-trust-scores",
    # D-19..D-29 (remaining D-NN dashboards):
    "d-19-super-model-manifest",
    "d-20-peace-machine-health",
    "d-21-lm-orchestration",
    "d-22-lm-status-operability",
    "d-23-models-catalog",
    "d-24-cpu-features",
    "d-25-selfdef-management",
    "d-26-friction-audit",
    "d-27-guardian",
    "d-28-perimeter",
    "d-29-scheduler",
    # Orthogonal cockpit webapps (operator-facing):
    "auditor",
    "ux-design-audit",
    "anti-minimization-audit",
    "compliance",
    "global-history",
    "surface-map",
    "router",
    "doc-coverage",
    "weaver",
    "trinity",
    "auth-tier",
    "build-configurator",
    "code-console",
    "rustdoc-panel",
]


def test_adopted_dashboards_embed_canonical_apply_snippet():
    """Every dashboard listed in ADOPTED_DASHBOARDS MUST embed the
    apply-snippet with the canonical localStorage key + schema-v1
    check + the 4 documentElement applications (data-theme + --accent
    + --so-accent + --font-scale)."""
    for slug in ADOPTED_DASHBOARDS:
        path = REPO_ROOT / "webapp" / slug / "index.html"
        assert path.is_file(), f"adopted dashboard missing: {path}"
        html = path.read_text(encoding="utf-8")
        head = html.split("</head>", 1)[0]
        assert EXPECTED_KEY in head, (
            f"{slug}: apply-snippet missing canonical localStorage key"
        )
        assert "SCHEMA_V = 1" in head or "SCHEMA_V=1" in head, (
            f"{slug}: apply-snippet must declare schema v1"
        )
        # The 4 documentElement applications
        assert "setAttribute('data-theme'" in head or 'setAttribute("data-theme"' in head, (
            f"{slug}: apply-snippet must set data-theme"
        )
        assert "--accent" in head, f"{slug}: apply-snippet must set --accent"
        assert "--so-accent" in head, f"{slug}: apply-snippet must set --so-accent"
        assert "--font-scale" in head, f"{slug}: apply-snippet must set --font-scale"


def test_adopted_dashboards_honor_font_scale():
    """Every adopted dashboard's base html/body font-size MUST honor
    --font-scale so R10141 actually takes effect there."""
    for slug in ADOPTED_DASHBOARDS:
        path = REPO_ROOT / "webapp" / slug / "index.html"
        html = path.read_text(encoding="utf-8")
        assert "calc(14px * var(--font-scale" in html or \
               "calc(14px*var(--font-scale" in html, (
            f"{slug}: must honor --font-scale in base font-size for R10141"
        )


def test_adopted_dashboards_honor_light_theme():
    """Every adopted dashboard MUST declare a html[data-theme=\"light\"]
    override so R10137 light mode actually renders there."""
    for slug in ADOPTED_DASHBOARDS:
        path = REPO_ROOT / "webapp" / slug / "index.html"
        html = path.read_text(encoding="utf-8")
        assert 'html[data-theme="light"]' in html or \
               "html[data-theme='light']" in html, (
            f"{slug}: must declare html[data-theme=\"light\"] for R10137"
        )
