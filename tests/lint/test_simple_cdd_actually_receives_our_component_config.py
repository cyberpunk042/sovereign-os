"""simple-cdd silently drops NONFREE — the config must go where it survives.

2026-07-29, after SEVEN failed Debian installer builds. Every one of them ran
to near-completion (1499 packages laid out, boot code added, base verified
installable) and died on the last check:

    ERROR: missing required packages from profile sovereign:
      amd64-microcode firmware-amd-graphics firmware-nvidia-graphics
      firmware-misc-nonfree intel-microcode

with all five packages sitting correctly in the local mirror.

debian-cd's tools/which_deb gates the non-free components on $ENV{NONFREE}.
/usr/bin/build-simple-cdd gets that variable wrong twice:

  * line 119  self.env.set("NONFREE", "")   -- clobbers the inherited env
  * line 144  only flips it on for the LITERAL component "non-free", never for
              "non-free-firmware" (a distinct component since Debian 12)

and simple_cdd/env.py:365-367 ignores a profile-conf value that is EQUAL to the
ambient environment, so setting it in BOTH places is the same as setting it in
neither.

The escape is the profile .conf, read after the clobber. This file pins that
arrangement, because every part of it looks redundant and each "cleanup" of it
costs another multi-hour build.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CDD = REPO_ROOT / "scripts" / "build" / "installer-cdd"
BUILD = CDD / "build.sh"
CONF = CDD / "profiles" / "sovereign.conf"
PACKAGES = CDD / "profiles" / "sovereign.packages"


def _assignments(text: str, var: str) -> list[str]:
    """Every `VAR=value` / `export VAR=value` assignment, comments stripped."""
    body = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    return re.findall(rf"^\s*(?:export\s+)?{var}=(.*)$", body, re.M)


def test_the_profile_conf_exists():
    assert CONF.is_file(), (
        "profiles/sovereign.conf must exist — it is the ONLY place NONFREE can "
        "be set where build-simple-cdd will not clobber it (line 119)"
    )


def test_nonfree_is_set_in_the_profile_conf():
    vals = _assignments(CONF.read_text(encoding="utf-8"), "NONFREE")
    assert vals, (
        "sovereign.conf must set NONFREE. Without a truthy NONFREE, debian-cd's "
        "which_deb drops non-free-firmware from the component list and the "
        "firmware packages are never placed on CD1 — the build fails at the "
        "very last step with 'missing required packages'."
    )
    assert vals[0].strip().strip("\"'") == "1", f"NONFREE must be 1, got {vals[0]!r}"


def test_nonfree_components_names_the_firmware_component():
    vals = _assignments(CONF.read_text(encoding="utf-8"), "NONFREE_COMPONENTS")
    assert vals, (
        "sovereign.conf must set NONFREE_COMPONENTS. which_deb does "
        "`split / /, $ENV{NONFREE_COMPONENTS} if $ENV{NONFREE}` — with NONFREE "
        "set and this unset it splits undef and DROPS the components, leaving "
        "only an 'uninitialized value' warning."
    )
    assert "non-free-firmware" in vals[0], (
        f"NONFREE_COMPONENTS must include non-free-firmware, got {vals[0]!r}"
    )


def test_build_sh_does_not_also_export_them():
    """The trap that makes belt-and-braces WORSE than nothing.

    simple_cdd/env.py:365-367 adopts a conf value only when it differs from the
    ambient environment:

        for key in new_env.keys() & os.environ.keys():
            if os.environ[key] == new_env[key]: continue

    So `export NONFREE=1` in build.sh makes sovereign.conf's identical NONFREE=1
    compare EQUAL, hit `continue`, and never be adopted — the clobbered "" from
    line 119 stands and the firmware silently vanishes.
    """
    text = BUILD.read_text(encoding="utf-8")
    for var in ("NONFREE", "NONFREE_COMPONENTS"):
        assert not _assignments(text, var), (
            f"build.sh must NOT set {var} — an ambient value equal to "
            "sovereign.conf's makes env.py:366 skip the conf entirely, and the "
            "line-119 clobber wins. It must be set ONLY in the profile conf."
        )


def test_non_free_proper_is_not_in_the_component_list():
    """Listing `non-free` flips NONFREE, but kills the build a different way.

    It is the obvious-looking fix and it does not work: nothing in this profile
    pulls a package from `non-free`, so the component mirrors EMPTY, CD1 gets no
    non-free/Packages.gz, and simple-cdd's dose3 distcheck dies on the missing
    input file. Use the profile conf instead.
    """
    vals = _assignments(BUILD.read_text(encoding="utf-8"), "mirror_components")
    assert vals, "build.sh must set mirror_components"
    comps = vals[0].strip().strip("\"'").split()
    assert "non-free" not in comps, (
        "mirror_components must not list bare `non-free`: no package in "
        "sovereign.packages comes from it, so the component mirrors empty and "
        "the dose3 distcheck dies on a missing Packages.gz. NONFREE is flipped "
        "via profiles/sovereign.conf instead."
    )
    assert "non-free-firmware" in comps, (
        "mirror_components must list non-free-firmware — the microcode and "
        "firmware-* packages the profile requires all live there"
    )


def test_every_listed_component_has_a_package_that_lands_in_it():
    """dose3 needs a Packages.gz per component; debian-cd only makes one if a
    package was actually placed there. An aspirational component is fatal.

    This is the failure that burned attempts 3-5: contrib and non-free were in
    the list with nothing to put in them.
    """
    vals = _assignments(BUILD.read_text(encoding="utf-8"), "mirror_components")
    comps = vals[0].strip().strip("\"'").split()
    pkgs = PACKAGES.read_text(encoding="utf-8")

    # One known-good witness per non-main component. main is never empty.
    witnesses = {
        "contrib": ["zfsutils-linux", "zfs-dkms"],
        "non-free-firmware": [
            "firmware-misc-nonfree", "firmware-amd-graphics",
            "intel-microcode", "amd64-microcode",
        ],
    }
    for comp in comps:
        if comp == "main":
            continue
        candidates = witnesses.get(comp)
        assert candidates is not None, (
            f"mirror_components lists {comp!r}, which this test has no witness "
            "for. Add one — and make sure sovereign.packages really pulls a "
            "package from it, or the build dies in dose3."
        )
        assert any(
            re.search(rf"^\s*{re.escape(c)}\s*$", pkgs, re.M) for c in candidates
        ), (
            f"mirror_components lists {comp!r} but sovereign.packages requests "
            f"none of {candidates}. The component will mirror EMPTY, CD1 will "
            f"have no {comp}/binary-amd64/Packages.gz, and simple-cdd's dose3 "
            "distcheck will die on the missing input file."
        )


def test_the_mechanism_actually_works_against_real_simple_cdd():
    """Prove it against simple-cdd's OWN code, not against our reading of it.

    Replays build-simple-cdd's exact sequence (clobber at :119, profile confs at
    :121-124, component scan at :141-144) through the real Environment class,
    plus the negative control that shows an ambient export defeats it.
    """
    import os
    pytest.importorskip("simple_cdd.env", reason="simple-cdd not installed")
    from simple_cdd.env import Environment
    import simple_cdd.variables as V

    registry = getattr(V, "VARIABLES", None) or V.variables
    saved = os.environ.pop("NONFREE", None)
    try:
        env = Environment(registry)
        env.set("NONFREE", "")                    # :119 clobber
        env.read_config_file(str(CONF))           # :121-124 profile confs
        for comp in ("main", "contrib", "non-free-firmware"):   # :141-144
            if comp == "non-free":
                env.set("NONFREE", "1")
        assert env.get("NONFREE") == "1", (
            "the profile conf did not survive build-simple-cdd's clobber — "
            "which_deb will drop non-free-firmware and the firmware packages "
            "will not be placed on CD1"
        )
        assert "non-free-firmware" in (env.get("NONFREE_COMPONENTS") or "")

        # Negative control: this is what an `export NONFREE=1` in build.sh does.
        os.environ["NONFREE"] = "1"
        ctl = Environment(registry)
        ctl.set("NONFREE", "")
        ctl.read_config_file(str(CONF))
        assert ctl.get("NONFREE") == "", (
            "negative control failed to reproduce: exporting NONFREE should "
            "make env.py:366 skip the conf. If this stops holding, the "
            "no-export rule above may be obsolete — re-derive it."
        )
    finally:
        os.environ.pop("NONFREE", None)
        if saved is not None:
            os.environ["NONFREE"] = saved
