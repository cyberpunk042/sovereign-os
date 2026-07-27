"""The build panel must be able to build for a machine other than this one.

2026-07-27, operator: "would it install even if I wasn't on SAIN? I think I will
test with my other computer" — followed by "improve the build panel, more
compatibility in the build area".

The panel forwarded thirteen BAKE_* toggles and nothing about the TARGET. Every
ISO therefore carried the sain-01 box's identity and GPU workarounds: hostname
sovereign-os, user jfortin, nomodeset, amdgpu+nouveau blacklisted. On hardware
whose GPU driver actually binds, those cost acceleration for no benefit, and
there was no way to change them short of editing a preseed by hand.

Blank means "keep the built-in default", so an untouched panel builds exactly
what it always did. module_blacklist is the one exception: "none" means
blacklist NOTHING, a real choice on other hardware, so it is forwarded as an
empty string rather than dropped.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PANEL = REPO_ROOT / "webapp" / "build-configurator" / "index.html"
API = REPO_ROOT / "scripts" / "operator" / "build-configurator-api.py"

FIELDS = (("tgt-hostname", "hostname", "SOVEREIGN_OS_HOSTNAME"),
          ("tgt-username", "username", "SOVEREIGN_OS_USERNAME"),
          ("tgt-cmdline", "kernel_cmdline", "SOVEREIGN_OS_KERNEL_CMDLINE"),
          ("tgt-blacklist", "module_blacklist", "SOVEREIGN_OS_MODULE_BLACKLIST"),
          ("tgt-kdebs", "kernel_debs_dir", "SOVEREIGN_OS_KERNEL_DEBS_DIR"))


@pytest.mark.parametrize("elem,key,env", FIELDS)
def test_the_field_exists_and_reaches_the_build(elem: str, key: str, env: str):
    panel = PANEL.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    assert f'id="{elem}"' in panel, f"panel has no {elem} input"
    assert key in panel, f"panel never sends {key}"
    assert f'"{key}"' in api, f"the API ignores {key}"
    assert env in api, f"the API never forwards {env} to the build"


def test_every_target_field_is_validated():
    """These land in a preseed AND in shell. Reject, do not quote afterwards."""
    api = API.read_text(encoding="utf-8")
    for _, key, _ in FIELDS:
        block = api[api.index('("hostname"'):api.index("# Artifact shape")]
        assert key in block, f"{key} is not in the validated set"
    assert "re.match(_pattern" in api, "target fields must be pattern-checked"


def test_dangerous_values_cannot_pass_validation():
    """Injection attempts must be rejected by the patterns themselves."""
    api = API.read_text(encoding="utf-8")
    pats = dict(re.findall(r'\("(\w+)",\s+"SOVEREIGN_OS_\w+",\s+r"([^"]+)"\)', api))
    assert len(pats) >= 5, f"could not extract the patterns: {pats}"
    hostile = ["a;rm -rf /", "x`id`", "$(id)", "a|b", 'a"b', "a b c;d"]
    for key, pat in pats.items():
        for bad in hostile:
            assert not re.match(pat, bad), f"{key} accepts {bad!r}"


def test_blank_means_unchanged():
    """An untouched panel must produce the build it always did."""
    api = API.read_text(encoding="utf-8")
    assert 'if _key not in body:' in api and 'continue' in api, (
        "absent keys must be skipped, not coerced to empty strings"
    )
    assert '_key != "module_blacklist"' in api, (
        'an empty module_blacklist means "blacklist nothing" and must be '
        "forwarded; every other blank field means 'keep the default'"
    )
