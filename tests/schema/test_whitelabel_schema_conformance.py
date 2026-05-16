"""Layer 1 — whitelabel YAML schema-conformance + legal-floor enforcement."""

from __future__ import annotations

import pathlib

import pytest

try:
    import yaml
except ImportError:
    pytest.skip("python3-yaml not installed", allow_module_level=True)

try:
    import jsonschema
except ImportError:
    pytest.skip("python3-jsonschema not installed", allow_module_level=True)


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
WHITELABEL_DIR = REPO_ROOT / "whitelabel"
SCHEMA_FILE = REPO_ROOT / "schemas" / "whitelabel.schema.yaml"

# Legal-floor patterns per SDD-006 § Legal floor — whitelabels MUST
# NOT declare surface entries matching any of these.
LEGAL_FLOOR = [
    "/etc/debian_version",
    "/usr/share/doc/",
    "/usr/share/man/",
    "debian-logo",
    "debian-swirl",
]


def _load_yaml(path: pathlib.Path):
    with path.open() as f:
        return yaml.safe_load(f)


def _all_whitelabel_files() -> list[pathlib.Path]:
    return sorted(WHITELABEL_DIR.glob("*.yaml"))


@pytest.fixture(scope="module")
def schema():
    return _load_yaml(SCHEMA_FILE)


@pytest.mark.parametrize("wl_file", _all_whitelabel_files(), ids=lambda p: p.stem)
def test_whitelabel_validates_against_schema(wl_file, schema):
    instance = _load_yaml(wl_file)
    jsonschema.Draft202012Validator(schema).validate(instance)


@pytest.mark.parametrize("wl_file", _all_whitelabel_files(), ids=lambda p: p.stem)
def test_whitelabel_respects_legal_floor(wl_file):
    """No surface entry may match a legal-floor path pattern."""
    instance = _load_yaml(wl_file)
    surfaces = instance.get("surfaces") or {}
    for surface_path in surfaces.keys():
        for forbidden in LEGAL_FLOOR:
            assert forbidden not in surface_path, (
                f"whitelabel '{wl_file.stem}' surface '{surface_path}' "
                f"violates legal floor pattern '{forbidden}'"
            )


@pytest.mark.parametrize("wl_file", _all_whitelabel_files(), ids=lambda p: p.stem)
def test_whitelabel_branding_required_fields(wl_file):
    """branding block must include os_id, os_name, os_pretty_name, os_version."""
    instance = _load_yaml(wl_file)
    branding = instance.get("branding") or {}
    for required in ("os_id", "os_name", "os_pretty_name", "os_version"):
        assert required in branding, f"branding.{required} missing in {wl_file.stem}"


def test_default_whitelabel_motd_is_operator_verbatim():
    """default.yaml must include the operator's verbatim motd."""
    instance = _load_yaml(WHITELABEL_DIR / "default.yaml")
    motd = (instance.get("branding") or {}).get("motd", "") or ""
    assert "quality over quantity" in motd, (
        "default whitelabel must include operator-verbatim motd "
        "('We want quality over quantity and honesty over cheats and lies...')"
    )
    assert "honesty over cheats" in motd
