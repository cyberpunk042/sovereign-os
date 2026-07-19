"""R385 (E10.M29) — config example file consistency lint.

Every `config/<name>.toml.example` file MUST:
  1. Exist (sanity: directory has the example file)
  2. Be valid TOML (parseable by Python's tomllib)
  3. Be non-empty (≥10 lines of operator-readable content)
  4. Have header comments explaining what it overlays
  5. Mention "operator" or "overlay" or "/etc/sovereign-os/" in comments
     (operator-discovery: example file MUST guide operator)

Plus inverse check: every example file MUST have a corresponding script
that loads it via operator_overlay (no orphan examples).

This is the EXISTING-EXAMPLES discipline. The broader "every overlay-
using script needs an example" gap is too aggressive (51 scripts have
minimal overlay surface that doesn't merit an example). Future round
can tighten if needed.
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    import tomllib  # type: ignore
except ImportError:
    import tomli as tomllib  # type: ignore[import]

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


def _existing_examples() -> list[Path]:
    return sorted(CONFIG_DIR.glob("*.toml.example"))


def _overlay_names_in_scripts() -> set[str]:
    """Parse all .py files under scripts/ for load_with_overlay('name', ...)."""
    out: set[str] = set()
    for pyfile in (REPO_ROOT / "scripts").rglob("*.py"):
        try:
            body = pyfile.read_text(encoding="utf-8")
        except Exception:
            continue
        out.update(re.findall(
            r"""load_with_overlay\(\s*['"]([\w-]+)['"]""", body))
    return out


def test_config_dir_exists():
    assert CONFIG_DIR.is_dir(), f"missing {CONFIG_DIR}"


def test_at_least_15_examples_shipped():
    """Sanity: by this stage we should have ≥15 example files."""
    examples = _existing_examples()
    assert len(examples) >= 15, (
        f"only {len(examples)} config/*.toml.example files; expected ≥15"
    )


def test_every_example_is_valid_toml():
    """Every example file MUST be parseable as TOML. Catches: stale
    examples with syntax errors after refactors."""
    bad: list[tuple[str, str]] = []
    for f in _existing_examples():
        try:
            with f.open("rb") as fp:
                tomllib.load(fp)
        except Exception as e:
            bad.append((f.name, str(e)[:100]))
    assert not bad, (
        f"config/*.toml.example files with TOML syntax errors: {bad}"
    )


def test_every_example_non_empty():
    """Every example file MUST have ≥10 lines (operator-readable
    content; not a stub)."""
    bad: list[tuple[str, int]] = []
    for f in _existing_examples():
        line_count = len(f.read_text(encoding="utf-8").splitlines())
        if line_count < 10:
            bad.append((f.name, line_count))
    assert not bad, (
        f"config/*.toml.example files with <10 lines (operator-readable "
        f"floor): {bad}. Each example should have at least header "
        f"comments + ≥1 documented knob."
    )


def test_every_example_has_header_comment():
    """Every example file MUST start with a header comment (line 1 or 2)
    explaining what it overlays. Catches: example created without
    explanatory header."""
    bad: list[str] = []
    for f in _existing_examples():
        first_lines = "\n".join(
            f.read_text(encoding="utf-8").splitlines()[:5])
        if "#" not in first_lines:
            bad.append(f.name)
    assert not bad, (
        f"config/*.toml.example files missing header comment in first 5 "
        f"lines: {bad}"
    )


def test_every_example_mentions_operator_or_overlay():
    """Every example MUST mention 'operator' / 'overlay' / '/etc/' in
    comments (operator-discovery: explains usage)."""
    bad: list[str] = []
    for f in _existing_examples():
        body = f.read_text(encoding="utf-8").lower()
        if not any(token in body for token in
                    ("operator", "overlay", "/etc/sovereign-os", "/etc/")):
            bad.append(f.name)
    assert not bad, (
        f"config/*.toml.example files don't mention "
        f"operator/overlay/etc: {bad}. Add header comments explaining "
        f"how the operator uses the file."
    )


def test_every_example_has_corresponding_overlay_call():
    """Every example MUST have a corresponding script that loads it
    via load_with_overlay('name', ...). Catches: orphan example
    after script rename."""
    overlay_names = _overlay_names_in_scripts()
    orphans: list[str] = []
    # Allowed orphans (legacy / non-overlay examples documented elsewhere)
    allowed_orphans = {
        "dashboard-auth",     # consumed via different load path
        "gpu-policy",         # consumed via render-asymmetric.sh
        "install-layers",     # consumed via build pipeline
        "kernel-tuning",      # consumed via grub-cfg / sysctl
        "known-boards",       # consumed by bios-info via Path read
        "notify",             # consumed by R254 directly
        "power",              # consumed via systemd env file
        "ram",                # consumed via R257 memory-profile
        "shutdown-manifest",  # consumed by R262 drain manifest
        "cost-policy",        # read via tomllib by cost-tracker.py + cost-policy.py
        "notifykit",          # read via tomllib by tools/notifykit/config.py (2026-07-19 shared notification library)
        "wikis",              # read via tomllib by tools/wikiops.py (2026-07-19 wiki-operability target registry)
    }
    for f in _existing_examples():
        stem = f.stem.replace(".toml", "")
        if stem in allowed_orphans:
            continue
        if stem not in overlay_names:
            orphans.append(stem)
    assert not orphans, (
        f"config/*.toml.example files with no corresponding "
        f"load_with_overlay caller: {orphans}. Either add to "
        f"allowed_orphans (with documented reason) OR remove the "
        f"example."
    )
