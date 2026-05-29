"""AppArmor master-dashboard banner — contract test."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = REPO_ROOT / "webapp" / "master-dashboard" / "index.html"


def _read():
    return DASHBOARD.read_text()


def test_banner_dom_present():
    body = _read()
    assert 'id="apparmor-banner"' in body
    assert 'role="status"' in body
    assert 'aria-live="polite"' in body


def test_banner_labels_present():
    body = _read()
    for id_ in ("apparmor-label", "apparmor-detail", "apparmor-mode"):
        assert f'id="{id_}"' in body


def test_banner_links_to_grafana_dashboard():
    body = _read()
    assert "/d/sovereign-os-selfdef-apparmor" in body


def test_render_function_present():
    body = _read()
    assert "async function renderApparmorBanner()" in body


def test_render_invoked_from_grid_refresh():
    body = _read()
    grid_start = body.find("async function renderM060Grid()")
    assert grid_start != -1
    next_fn = body.find("\nasync function ", grid_start + 1)
    grid_body = body[grid_start:next_fn if next_fn > 0 else len(body)]
    assert "renderApparmorBanner()" in grid_body


def test_render_function_handles_all_6_canonical_states():
    body = _read()
    fn_start = body.find("async function renderApparmorBanner()")
    next_fn = body.find("\nasync function ", fn_start + 1)
    fn_body = body[fn_start:next_fn if next_fn > 0 else len(body)]
    for state in ("ok", "complain", "not-loaded", "observer-fault",
                  "unreachable", "unknown"):
        assert f'"{state}"' in fn_body, (
            f"renderApparmorBanner missing state {state!r}"
        )


def test_banner_css_covers_all_6_canonical_states():
    body = _read()
    for state in ("ok", "complain", "not-loaded", "observer-fault",
                  "unreachable", "unknown"):
        selector = f".apparmor-banner.{state}"
        assert selector in body, f"banner CSS missing class {selector!r}"


def test_render_parses_4_canonical_gauges():
    """The render function MUST parse all 4 canonical gauges
    (emit_failed + loaded + enforce + complain). Drift = banner
    misclassifies state."""
    body = _read()
    fn_start = body.find("async function renderApparmorBanner()")
    next_fn = body.find("\nasync function ", fn_start + 1)
    fn_body = body[fn_start:next_fn if next_fn > 0 else len(body)]
    for gauge in (
        "selfdef_apparmor_textfile_emit_failed",
        "selfdef_apparmor_profile_loaded",
        "selfdef_apparmor_profile_enforce",
        "selfdef_apparmor_profile_complain",
    ):
        assert gauge in fn_body, f"render missing gauge {gauge}"


def test_render_targets_canonical_profile_name():
    """The render function must reference selfdefd. The path may be
    regex-escaped (\\/usr\\/bin\\/selfdefd) — accept either form."""
    body = _read()
    fn_start = body.find("async function renderApparmorBanner()")
    next_fn = body.find("\nasync function ", fn_start + 1)
    fn_body = body[fn_start:next_fn if next_fn > 0 else len(body)]
    assert (
        "/usr/bin/selfdefd" in fn_body
        or "\\/usr\\/bin\\/selfdefd" in fn_body
    ), "render must target the canonical /usr/bin/selfdefd profile"


def test_banner_complain_state_takes_precedence_correctly():
    """Render logic MUST classify observer-fault FIRST (honest-offline),
    then not-loaded, then complain — the precedence order matches the
    alert precedence."""
    body = _read()
    fn_start = body.find("async function renderApparmorBanner()")
    next_fn = body.find("\nasync function ", fn_start + 1)
    fn_body = body[fn_start:next_fn if next_fn > 0 else len(body)]
    # observer-fault check appears before not-loaded check appears
    # before complain check.
    of = fn_body.find('"observer-fault"')
    nl = fn_body.find('"not-loaded"')
    co = fn_body.find('"complain"')
    assert 0 < of < nl < co, (
        f"render precedence drift: observer-fault={of} not-loaded={nl} "
        f"complain={co}"
    )


def test_render_complain_documents_aa_enforce_restore_command():
    """Complain-state detail line MUST mention aa-enforce so operators
    see the restore command directly on the master dashboard."""
    body = _read()
    fn_start = body.find("async function renderApparmorBanner()")
    next_fn = body.find("\nasync function ", fn_start + 1)
    fn_body = body[fn_start:next_fn if next_fn > 0 else len(body)]
    assert "aa-enforce" in fn_body
