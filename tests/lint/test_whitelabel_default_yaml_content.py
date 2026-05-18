"""R426 (E10.M70) — whitelabel/default.yaml content lint + 15th
bidirectional-consistency lint (whitelabel branding ↔ os-release
template ↔ rendered surfaces ↔ legal_floor in render.py).

Extends R387-R425 + R388/R407 operational-artifact pinning to:
  whitelabel/default.yaml          (the operator-named brand-baseline)
  whitelabel/default/templates/    (the template files referenced)

R388 covered whitelabel-default surface content; R407 covered the
render engine. R426 covers the BRIDGE — the default whitelabel YAML
that the render engine consumes.

15th bidirectional-consistency lint:
  whitelabel/default.yaml lists 5 templates under templates/
  Every template path MUST exist in whitelabel/default/templates/
  legal_floor.preserved[] list MUST match LEGAL_FLOOR_PATTERNS in
    scripts/whitelabel/render.py (drift = whitelabel can erase Debian
    legal-floor paths the render engine SHOULD have blocked but didn't)

If a future agent silently:
  - removes /etc/debian_version from legal_floor.preserved = render
    engine's legal-floor block becomes inert for the default whitelabel
  - changes os_id from 'sovereign' = ALL downstream branding artifacts
    silently drift to wrong identifier
  - drops the maintainer: cyberpunk042 = operator-named attribution
    erased
…the operator-named brand baseline silently drifts.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WL_DEFAULT_YAML = REPO_ROOT / "whitelabel" / "default.yaml"
WL_DEFAULT_DIR = REPO_ROOT / "whitelabel" / "default"
TEMPLATES_DIR = WL_DEFAULT_DIR / "templates"
RENDER_PY = REPO_ROOT / "scripts" / "whitelabel" / "render.py"


def _load() -> dict:
    return yaml.safe_load(WL_DEFAULT_YAML.read_text(encoding="utf-8")) or {}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_whitelabel_default_yaml_exists():
    assert WL_DEFAULT_YAML.is_file(), f"missing {WL_DEFAULT_YAML}"


def test_whitelabel_default_dir_exists():
    assert WL_DEFAULT_DIR.is_dir(), f"missing {WL_DEFAULT_DIR}"


def test_templates_dir_exists():
    assert TEMPLATES_DIR.is_dir(), f"missing {TEMPLATES_DIR}"


def test_whitelabel_default_yaml_parses():
    data = _load()
    assert data, "whitelabel/default.yaml empty or invalid YAML"


def test_schema_version_pinned():
    data = _load()
    assert data.get("schema_version") == "1.0.0", (
        f"whitelabel/default.yaml schema_version="
        f"{data.get('schema_version')!r} != 1.0.0"
    )


# --- Identity block ---


def test_identity_id_is_sovereign_default():
    """Operator-named: id MUST be 'sovereign-default'. Drift =
    composition reference fails when profile names this whitelabel."""
    data = _load()
    identity = data.get("identity") or {}
    assert identity.get("id") == "sovereign-default", (
        f"whitelabel/default.yaml identity.id="
        f"{identity.get('id')!r} != 'sovereign-default'"
    )


def test_identity_has_required_fields():
    """identity MUST have id + name + version + status + maintainer +
    description."""
    data = _load()
    identity = data.get("identity") or {}
    for field in ("id", "name", "version", "status",
                  "maintainer", "description"):
        assert identity.get(field), (
            f"whitelabel/default.yaml identity missing {field!r}"
        )


def test_identity_maintainer_is_operator():
    """Operator-named maintainer = cyberpunk042 (drift = attribution
    erased)."""
    data = _load()
    identity = data.get("identity") or {}
    assert identity.get("maintainer") == "cyberpunk042", (
        f"whitelabel/default.yaml identity.maintainer="
        f"{identity.get('maintainer')!r} != 'cyberpunk042' "
        f"(operator-named attribution)"
    )


def test_compliance_target_is_dfsg_only():
    """SDD-006 § 'Legal floor': default whitelabel targets DFSG-only
    (operator-named compliance baseline). Drift = relaxes the floor."""
    data = _load()
    assert data.get("compliance_target") == "dfsg-only", (
        f"whitelabel/default.yaml compliance_target="
        f"{data.get('compliance_target')!r} != 'dfsg-only'"
    )


# --- Branding block ---


def test_branding_has_required_fields():
    """Branding MUST have os_id + os_name + os_pretty_name + os_version
    + os_codename + vendor + home_url + bug_report_url + support_url +
    motd (the operator-named brand-baseline surface)."""
    data = _load()
    branding = data.get("branding") or {}
    required = [
        "os_id", "os_name", "os_pretty_name", "os_version",
        "os_codename", "vendor",
        "home_url", "bug_report_url", "support_url",
        "motd",
    ]
    for field in required:
        assert branding.get(field), (
            f"whitelabel/default.yaml branding missing {field!r}"
        )


def test_branding_os_id_is_sovereign():
    """Operator-named: os_id = 'sovereign'. Drift = downstream
    /etc/os-release ID= and all other branding artifacts silently
    use wrong identifier."""
    data = _load()
    branding = data.get("branding") or {}
    assert branding.get("os_id") == "sovereign", (
        f"whitelabel/default.yaml branding.os_id="
        f"{branding.get('os_id')!r} != 'sovereign'"
    )


def test_branding_os_codename_is_trinity():
    """Operator-named codename: 'trinity' (per § 17 Genesis Trinity).
    Drift loses the operator-named architectural reference."""
    data = _load()
    branding = data.get("branding") or {}
    assert branding.get("os_codename") == "trinity", (
        f"whitelabel/default.yaml branding.os_codename="
        f"{branding.get('os_codename')!r} != 'trinity' "
        f"(operator-named § 17 Genesis Trinity binding)"
    )


def test_branding_vendor_is_cyberpunk042():
    """Operator-named vendor — must match maintainer + ISO publisher
    in cloud-init (R414)."""
    data = _load()
    branding = data.get("branding") or {}
    assert branding.get("vendor") == "cyberpunk042", (
        f"whitelabel/default.yaml branding.vendor="
        f"{branding.get('vendor')!r} != 'cyberpunk042' "
        f"(operator-named — must match maintainer + cloud-init ISO publisher)"
    )


def test_branding_urls_point_at_github():
    """home_url + bug_report_url + support_url MUST be GitHub-hosted
    (operator-discoverable canonical references; drift to placeholder
    URLs = broken operator-discovery)."""
    data = _load()
    branding = data.get("branding") or {}
    for field in ("home_url", "bug_report_url", "support_url"):
        url = branding.get(field, "")
        assert "cyberpunk042/sovereign-os" in url, (
            f"whitelabel/default.yaml branding.{field}={url!r} "
            f"doesn't reference cyberpunk042/sovereign-os repo"
        )


# --- Templates ---


def test_yaml_lists_known_templates():
    """The YAML 'surfaces' block references template files. Each
    template MUST exist in whitelabel/default/templates/. Drift =
    render engine fails at runtime trying to read a missing template."""
    data = _load()
    surfaces = data.get("surfaces") or {}
    # Collect all referenced templates
    referenced_templates: set[str] = set()
    for path, decl in surfaces.items():
        if isinstance(decl, dict) and "template" in decl:
            referenced_templates.add(decl["template"])

    # Each MUST exist
    for tmpl in referenced_templates:
        # template paths may be relative to the YAML's directory
        p = WL_DEFAULT_YAML.parent / tmpl
        assert p.is_file(), (
            f"whitelabel/default.yaml references template {tmpl!r} "
            f"but it doesn't exist at {p} "
            f"(BIDIRECTIONAL CONSISTENCY VIOLATION)"
        )


def test_templates_dir_has_expected_files():
    """Operator-named template set: os-release / issue / motd /
    installer-welcome / dpkg-origins-sovereign."""
    expected = [
        "os-release.tmpl",
        "issue.tmpl",
        "motd.tmpl",
        "installer-welcome.tmpl",
        "dpkg-origins-sovereign.tmpl",
    ]
    for name in expected:
        p = TEMPLATES_DIR / name
        assert p.is_file(), (
            f"whitelabel/default/templates/{name} missing"
        )


def test_os_release_template_has_id_placeholder():
    """os-release.tmpl MUST reference ${os_id} (or similar) for
    substitution. Drift to hardcoded 'sovereign' string loses the
    operator-overridable surface."""
    p = TEMPLATES_DIR / "os-release.tmpl"
    text = _read(p)
    has_placeholder = (
        "${os_id}" in text
        or "${os_name}" in text
        or "${os_pretty_name}" in text
        or "$os_" in text
    )
    assert has_placeholder, (
        "os-release.tmpl missing ${os_*} placeholder "
        "(drift = hardcoded brand; whitelabel can't override)"
    )


# --- 15th bidirectional-consistency lint: legal_floor ↔ render.py ---


def test_bidirectional_legal_floor_with_render_py():
    """15th bidirectional-consistency lint:
      whitelabel/default.yaml legal_floor.preserved MUST be a subset
      of scripts/whitelabel/render.py LEGAL_FLOOR_PATTERNS
    (drift = whitelabel YAML claims to preserve a path the render
    engine doesn't actually block)."""
    data = _load()
    yaml_preserved = set(
        (data.get("legal_floor") or {}).get("preserved") or []
    )
    render_body = _read(RENDER_PY)
    # Each preserved path MUST appear in render.py's LEGAL_FLOOR_PATTERNS
    for path in yaml_preserved:
        assert path in render_body, (
            f"whitelabel/default.yaml legal_floor.preserved contains "
            f"{path!r} but it's NOT in render.py LEGAL_FLOOR_PATTERNS "
            f"(BIDIRECTIONAL CONSISTENCY VIOLATION: YAML claims "
            f"protection the render engine doesn't enforce)"
        )


def test_legal_floor_protects_debian_version():
    """Operator-named SDD-006 § 'Legal floor': /etc/debian_version
    MUST stay. Drift = Debian attribution erasure."""
    data = _load()
    preserved = (data.get("legal_floor") or {}).get("preserved") or []
    assert "/etc/debian_version" in preserved, (
        "whitelabel/default.yaml legal_floor missing /etc/debian_version "
        "(SDD-006 § 'Legal floor' verbatim)"
    )


def test_legal_floor_protects_debian_logos():
    """SDD-006 verbatim: debian-logo* + debian-swirl* MUST stay
    (Debian trademark policy)."""
    data = _load()
    preserved = (data.get("legal_floor") or {}).get("preserved") or []
    has_logo = any("debian-logo" in p for p in preserved)
    has_swirl = any("debian-swirl" in p for p in preserved)
    assert has_logo, (
        "whitelabel/default.yaml legal_floor missing debian-logo* "
        "(SDD-006 trademark protection)"
    )
    assert has_swirl, (
        "whitelabel/default.yaml legal_floor missing debian-swirl* "
        "(SDD-006 trademark protection)"
    )


def test_legal_floor_has_rationale():
    """legal_floor MUST document WHY (operator-discoverable rationale)."""
    data = _load()
    rationale = (data.get("legal_floor") or {}).get("rationale", "")
    assert rationale, (
        "whitelabel/default.yaml legal_floor missing rationale "
        "(operator-discovery: WHY are these paths protected)"
    )
    assert "Debian" in rationale or "DFSG" in rationale or "SDD-006" in rationale, (
        "whitelabel/default.yaml legal_floor rationale missing "
        "Debian/DFSG/SDD-006 reference"
    )
