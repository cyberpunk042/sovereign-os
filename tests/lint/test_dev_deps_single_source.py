"""Dev/test-dependency single-source lint (F-2026-022 / F-2026-056 / SDD-963).

The repo's Python test/lint harness needs exactly three packages: pytest, pyyaml,
jsonschema. Historically CI installed them with an inline
`pip install pytest pyyaml jsonschema` repeated in four jobs, while nothing
installed them for a local developer at all — so `make lint` on a fresh clone
died with ModuleNotFoundError, and CI's set could drift away from whatever a
developer happened to have installed.

SDD-963 makes `requirements-dev.txt` the ONE source: `make dev-deps` installs
from it and every CI job installs from it. This lint keeps that single-source
property true — it fails if:

  * requirements-dev.txt goes missing or stops covering {pytest, pyyaml, jsonschema};
  * any CI test job reintroduces an inline `pip install pytest|pyyaml|jsonschema`
    instead of `-r requirements-dev.txt` (the drift reopening);
  * the `make dev-deps` target disappears or stops installing from the file;
  * the friendly `_require-pytest` guard on the pytest-invoking make targets is lost.

So the local dev env and the CI env can never silently diverge again.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REQ_DEV = REPO_ROOT / "requirements-dev.txt"
TEST_YML = REPO_ROOT / ".github" / "workflows" / "test.yml"
MAKEFILE = REPO_ROOT / "Makefile"

# The packages the repo's own test/lint harness depends on.
REQUIRED_DEPS = {"pytest", "pyyaml", "jsonschema"}


def _req_dev_packages() -> set[str]:
    """Package names declared in requirements-dev.txt (comments/blank lines stripped,
    version specifiers and extras removed, lowercased)."""
    pkgs: set[str] = set()
    for raw in REQ_DEV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # strip inline comments, version specifiers, extras
        line = line.split("#", 1)[0].strip()
        name = re.split(r"[<>=!~;\[ ]", line, 1)[0].strip().lower()
        if name:
            pkgs.add(name)
    return pkgs


def test_requirements_dev_covers_the_harness_deps():
    assert REQ_DEV.is_file(), f"missing {REQ_DEV} (SDD-963 single source of dev deps)"
    pkgs = _req_dev_packages()
    missing = REQUIRED_DEPS - pkgs
    assert not missing, (
        f"requirements-dev.txt is missing harness deps {sorted(missing)}; "
        f"declared: {sorted(pkgs)}"
    )


def test_ci_has_no_inline_pytest_install():
    """No CI job may reintroduce an inline pip-install of the harness triple; all
    test-dep installs must reference requirements-dev.txt (the single source)."""
    body = TEST_YML.read_text(encoding="utf-8")
    # any `pip install ... <one of the triple> ...` that is NOT `-r requirements-dev.txt`
    offenders: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if "pip install" not in s:
            continue
        if "requirements-dev.txt" in s:
            continue
        if re.search(r"\bpip install\b.*\b(pytest|pyyaml|jsonschema)\b", s):
            offenders.append(s)
    assert not offenders, (
        "test.yml installs harness deps inline instead of `-r requirements-dev.txt` "
        f"(reopens the drift): {offenders}"
    )


def test_ci_installs_from_requirements_dev():
    """At least one job actually installs from the file (so it's wired, not orphaned)."""
    body = TEST_YML.read_text(encoding="utf-8")
    assert "pip install -r requirements-dev.txt" in body, (
        "no CI job installs `-r requirements-dev.txt`; the single source is unwired"
    )


def test_makefile_dev_deps_target():
    body = MAKEFILE.read_text(encoding="utf-8")
    assert re.search(r"(?m)^dev-deps:", body), "Makefile has no `dev-deps` target"
    assert "pip install -r requirements-dev.txt" in body, (
        "`make dev-deps` does not install from requirements-dev.txt"
    )


def test_makefile_pytest_targets_are_guarded():
    """lint / unit / dashboards-lint must depend on the _require-pytest friendly guard
    so a fresh clone gets `run make dev-deps`, not a raw ModuleNotFoundError."""
    body = MAKEFILE.read_text(encoding="utf-8")
    assert re.search(r"(?m)^_require-pytest:", body), "missing `_require-pytest` guard target"
    for target in ("lint", "unit", "dashboards-lint"):
        m = re.search(rf"(?m)^{target}:[^\n]*", body)
        assert m, f"Makefile has no `{target}` target"
        assert "_require-pytest" in m.group(0), (
            f"`{target}` target is not guarded by _require-pytest: {m.group(0)!r}"
        )
