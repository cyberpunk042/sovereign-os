"""Layer 2 — whitelabel render engine.

Validates the substrate-agnostic render engine from
scripts/whitelabel/render.py per SDD-007. Covers all 7 strategies +
legal-floor enforcement.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "whitelabel"))

yaml = pytest.importorskip("yaml")
render = pytest.importorskip("render")


def _wl(extra: dict | None = None) -> dict:
    """Minimal valid whitelabel dict for testing."""
    base = {
        "schema_version": "1.0.0",
        "identity": {
            "id": "test",
            "name": "Test",
            "version": "0.1.0",
            "status": "draft",
            "maintainer": "test",
            "description": "x" * 50,
        },
        "branding": {
            "os_id": "test",
            "os_name": "Test OS",
            "os_pretty_name": "Test OS v0.1",
            "os_version": "0.1",
        },
        "surfaces": {},
    }
    if extra:
        base.update(extra)
    return base


def _profile(extra: dict | None = None) -> dict:
    base = {
        "whitelabel": {"profile": "test", "legal_compliance": "dfsg-only"},
    }
    if extra:
        base.update(extra)
    return base


# ----------- legal floor enforcement -----------

@pytest.mark.parametrize(
    "forbidden_path",
    [
        "/etc/debian_version",
        "/usr/share/doc/glibc/copyright",
        "/usr/share/man/man1/apt.1",
        "/usr/share/icons/hicolor/debian-logo.svg",
        "/usr/share/icons/hicolor/debian-swirl-128.png",
    ],
)
def test_legal_floor_violations_are_detected(forbidden_path):
    """violates_legal_floor() must return True for protected paths."""
    assert render.violates_legal_floor(forbidden_path)


@pytest.mark.parametrize(
    "allowed_path",
    ["/etc/os-release", "/etc/issue", "/etc/motd", "/usr/share/plymouth/themes/sovereign/sovereign.script"],
)
def test_legal_floor_allows_normal_surfaces(allowed_path):
    """violates_legal_floor() must NOT trigger on rebrandable surfaces."""
    assert not render.violates_legal_floor(allowed_path)


# ----------- template substitution -----------

def test_template_substitution_renders_vars():
    branding = {"os_id": "sovereign", "os_name": "Sovereign OS"}
    content = "ID=${os_id}\nNAME=${os_name}"
    result = render.render_template_substitution(branding, content)
    assert "ID=sovereign" in result
    assert "NAME=Sovereign OS" in result


def test_template_substitution_leaves_unknown_vars():
    """safe_substitute should leave undefined vars unchanged."""
    branding = {"os_id": "sovereign"}
    content = "ID=${os_id}\nUNDEFINED=${unknown_var}"
    result = render.render_template_substitution(branding, content)
    assert "ID=sovereign" in result
    assert "${unknown_var}" in result  # left unchanged


# ----------- compliance-target mismatch detection -----------

def test_compliance_mismatch_fails():
    """Profile says dfsg-only but whitelabel says internal-only → fail."""
    wl = _wl({"compliance_target": "internal-only"})
    profile = _profile()  # dfsg-only

    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        with pytest.raises(SystemExit) as excinfo:
            render.build_changeset(profile, wl, td)
        assert excinfo.value.code == 3


def test_compliance_match_passes():
    """Same compliance posture on both sides → no fail."""
    wl = _wl({"compliance_target": "dfsg-only"})
    profile = _profile()
    with tempfile.TemporaryDirectory() as td:
        cs = render.build_changeset(profile, wl, pathlib.Path(td))
    assert isinstance(cs, render.Changeset)


# ----------- changeset building -----------

def test_template_substitution_strategy_populates_pre_build_files():
    wl = _wl(
        {
            "surfaces": {
                "/etc/os-release": {
                    "strategy": "template-substitution",
                    "content": "ID=${os_id}\n",
                    "when": "pre-build",
                }
            }
        }
    )
    profile = _profile()
    with tempfile.TemporaryDirectory() as td:
        cs = render.build_changeset(profile, wl, pathlib.Path(td))
    assert "/etc/os-release" in cs.pre_build_files
    assert "ID=test\n" == cs.pre_build_files["/etc/os-release"]


def test_build_time_flag_strategy_populates_env():
    wl = _wl(
        {
            "surfaces": {
                "kernel-buildflags": {
                    "strategy": "build-time-flag",
                    "flags": {"KBUILD_BUILD_USER": "${os_id}"},
                    "when": "pre-build",
                }
            }
        }
    )
    profile = _profile()
    with tempfile.TemporaryDirectory() as td:
        cs = render.build_changeset(profile, wl, pathlib.Path(td))
    assert cs.build_time_env == {"KBUILD_BUILD_USER": "test"}


def test_first_boot_script_strategy_collects_scripts():
    wl = _wl(
        {
            "surfaces": {
                "first-boot-greeting": {
                    "strategy": "first-boot-script",
                    "script": "scripts/whitelabel/first-boot-greeting.sh",
                    "when": "post-install",
                }
            }
        }
    )
    profile = _profile()
    with tempfile.TemporaryDirectory() as td:
        cs = render.build_changeset(profile, wl, pathlib.Path(td))
    assert "scripts/whitelabel/first-boot-greeting.sh" in cs.first_boot_scripts


def test_must_not_touch_strategy_records_declaration():
    """SDD-007 strategy 7: declarative opt-out — whitelabel explicitly
    declines to override a surface. Tracked but emits no file content."""
    wl = _wl(
        {
            "surfaces": {
                "/usr/share/locale/de/LC_MESSAGES": {
                    "strategy": "must-not-touch",
                    "reason": "preserve upstream German translations",
                    "when": "pre-build",
                }
            }
        }
    )
    profile = _profile()
    with tempfile.TemporaryDirectory() as td:
        cs = render.build_changeset(profile, wl, pathlib.Path(td))
    # No file content emitted
    assert "/usr/share/locale/de/LC_MESSAGES" not in cs.pre_build_files
    # But a tracking entry is recorded in package_actions
    must_not_touch_entries = [a for a in cs.package_actions if a.get("type") == "must-not-touch"]
    assert len(must_not_touch_entries) == 1
    assert must_not_touch_entries[0]["path"] == "/usr/share/locale/de/LC_MESSAGES"
    assert "preserve upstream" in must_not_touch_entries[0]["reason"]


def test_must_not_touch_without_reason_uses_default():
    """Reason field is optional; gets a default explanation."""
    wl = _wl(
        {
            "surfaces": {
                "/usr/share/wallpapers/upstream": {
                    "strategy": "must-not-touch",
                    "when": "pre-build",
                }
            }
        }
    )
    profile = _profile()
    with tempfile.TemporaryDirectory() as td:
        cs = render.build_changeset(profile, wl, pathlib.Path(td))
    entries = [a for a in cs.package_actions if a.get("type") == "must-not-touch"]
    assert len(entries) == 1
    assert entries[0]["reason"] == "explicit no-op declaration"


def test_install_time_substitution_strategy_collects_entries():
    wl = _wl(
        {
            "surfaces": {
                "hostname-default": {
                    "strategy": "install-time-substitution",
                    "operation": "preseed",
                    "key": "d-i netcfg/get_hostname",
                    "value": "${os_id}",
                    "when": "during-install",
                }
            }
        }
    )
    profile = _profile()
    with tempfile.TemporaryDirectory() as td:
        cs = render.build_changeset(profile, wl, pathlib.Path(td))
    assert len(cs.install_time) == 1
    assert cs.install_time[0]["key"] == "d-i netcfg/get_hostname"
    assert cs.install_time[0]["value"] == "test"  # rendered


# ----------- legal-floor enforcement in build_changeset -----------

def test_render_refuses_legal_floor_surface():
    """Whitelabel that tries to override a legal-floor path must fail build."""
    wl = _wl(
        {
            "surfaces": {
                "/etc/debian_version": {
                    "strategy": "template-substitution",
                    "content": "fake-version\n",
                    "when": "pre-build",
                }
            }
        }
    )
    profile = _profile()
    with tempfile.TemporaryDirectory() as td:
        with pytest.raises(SystemExit) as excinfo:
            render.build_changeset(profile, wl, pathlib.Path(td))
        assert excinfo.value.code == 4
