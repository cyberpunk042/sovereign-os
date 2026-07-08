"""Cross-repo mirror path coherence — selfdef publisher ↔ sovereign-os
consumer binding.

selfdef publishes 10 mirror JSON files into a directory the operator's
deployment exposes at `/run/sovereign-os/selfdef-mirror/`. Sovereign-os
mirror consumer scripts (scripts/mirror/selfdef-*-mirror.py) read from
that directory by filename. The binding is bidirectional:

  selfdef PRODUCES: 9 files via crates/selfdef-daemon/src/
                    mirror_export_loop.rs (active-profile.json /
                    grants.json / capability-tokens.json /
                    sandboxes.json / quarantine.json /
                    trust-scores.json / audit.json / rules.json /
                    tui.json) + cli.json via crates/selfdef-daemon/
                    src/cli_mirror_publisher.rs.

  sovereign-os CONSUMES: 10 mirror paths via scripts/mirror/
                          selfdef-*-mirror.py.

The set MUST agree filename-by-filename, OR drift produces silent
broken-rendering on the cockpit (consumer reads a file the producer
never wrote = mirror_status=offline shown for a domain selfdef
actually publishes; producer writes a file no consumer reads = wasted
write + missed cockpit surface).

This sister-gate to test_selfdef_scheduler_metric_contract.py covers
the broader mirror-fleet path binding.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MIRROR_DIR = REPO_ROOT / "scripts" / "mirror"

SELFDEF_REPO_DEFAULT = REPO_ROOT.parent / "selfdef"
SELFDEF_REPO = Path(os.environ.get("SOVEREIGN_OS_SELFDEF_REPO", str(SELFDEF_REPO_DEFAULT)))

# Path the selfdef daemon writes into + the sovereign-os consumer
# reads from. Hard-coded into both sides; if either renames this
# directory the cockpit fleet breaks silently.
PUBLISH_DIR = "/run/sovereign-os/selfdef-mirror"

# Regex to extract filename from a `"/run/sovereign-os/selfdef-mirror/
# <name>.json"` literal.
PUBLISH_RE = re.compile(r'"/run/sovereign-os/selfdef-mirror/([a-z0-9-]+\.json)"')

# selfdef-side: extract filename from `const X_FILE: &str = "...json"`
# in mirror_export_loop.rs + `cli.json` literal in cli_mirror_publisher.rs.
PRODUCER_CONST_RE = re.compile(r'const\s+[A-Z_]+_FILE:\s*&str\s*=\s*"([a-z0-9-]+\.json)"')
PRODUCER_LITERAL_RE = re.compile(r'"([a-z0-9-]+\.json)"')


def _consumer_paths() -> set[str]:
    """Walk sovereign-os scripts/mirror/*.py and pull every
    `/run/sovereign-os/selfdef-mirror/<name>.json` literal."""
    paths: set[str] = set()
    if not MIRROR_DIR.is_dir():
        return paths
    for py in sorted(MIRROR_DIR.glob("*.py")):
        text = py.read_text(encoding="utf-8", errors="replace")
        paths.update(PUBLISH_RE.findall(text))
    return paths


def _producer_paths() -> set[str]:
    """Walk selfdef-daemon source for mirror-file filename declarations."""
    paths: set[str] = set()
    if not SELFDEF_REPO.is_dir():
        return paths
    export_loop = (
        SELFDEF_REPO
        / "crates"
        / "selfdef-daemon"
        / "src"
        / "mirror_export_loop.rs"
    )
    if export_loop.is_file():
        text = export_loop.read_text(encoding="utf-8", errors="replace")
        paths.update(PRODUCER_CONST_RE.findall(text))
    # cli.json is published by cli_mirror_publisher.rs via a literal.
    cli_publisher = (
        SELFDEF_REPO
        / "crates"
        / "selfdef-daemon"
        / "src"
        / "cli_mirror_publisher.rs"
    )
    if cli_publisher.is_file():
        text = cli_publisher.read_text(encoding="utf-8", errors="replace")
        # Look specifically for write_bytes_atomic(..., "<file>.json", ...)
        # — narrower than every JSON literal.
        for m in re.finditer(
            r'write_bytes_atomic\([^,]+,\s*"([a-z0-9-]+\.json)"',
            text,
        ):
            paths.add(m.group(1))
    return paths


def test_consumer_paths_present():
    """Sanity: sovereign-os consumer scripts publish-dir refs are found."""
    paths = _consumer_paths()
    assert paths, (
        f"no /run/sovereign-os/selfdef-mirror/*.json paths found under "
        f"{MIRROR_DIR} — has the publish directory been renamed?"
    )


def test_consumer_uses_canonical_publish_directory():
    """Every consumer literal points at the canonical
    /run/sovereign-os/selfdef-mirror/ directory (the path is part of
    the contract — silent rename anywhere here breaks the binding)."""
    mismatch: list[tuple[str, str]] = []
    if not MIRROR_DIR.is_dir():
        pytest.skip(f"{MIRROR_DIR} not present")
    for py in sorted(MIRROR_DIR.glob("*.py")):
        text = py.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'"(/[^"]+/selfdef-mirror/[^"]+\.json)"', text):
            literal = m.group(1)
            if not literal.startswith(PUBLISH_DIR + "/"):
                mismatch.append((py.relative_to(REPO_ROOT).as_posix(), literal))
    assert not mismatch, (
        f"consumer scripts reference selfdef-mirror paths NOT under "
        f"{PUBLISH_DIR}/: {mismatch}"
    )


@pytest.mark.skipif(
    not (SELFDEF_REPO / "crates" / "selfdef-daemon" / "src" / "mirror_export_loop.rs").is_file(),
    reason="selfdef repo not adjacent",
)
def test_every_consumer_path_has_producer_side():
    """Every filename the sovereign-os consumer reads must be PRODUCED
    by the selfdef daemon. Else the cockpit silently shows mirror_
    status=offline for a domain selfdef should be writing."""
    consumer = _consumer_paths()
    producer = _producer_paths()
    missing = consumer - producer
    assert not missing, (
        f"sovereign-os consumer reads mirror files selfdef daemon does "
        f"NOT produce (cockpit shows offline for files that should be "
        f"written): {sorted(missing)}"
    )


@pytest.mark.skipif(
    not (SELFDEF_REPO / "crates" / "selfdef-daemon" / "src" / "mirror_export_loop.rs").is_file(),
    reason="selfdef repo not adjacent",
)
def test_every_producer_path_has_consumer_side():
    """Every filename selfdef writes should have a sovereign-os
    consumer. Otherwise the producer wastes a write per cycle + the
    operator-visible cockpit surface is missing for that domain."""
    consumer = _consumer_paths()
    producer = _producer_paths()
    orphans = producer - consumer
    assert not orphans, (
        f"selfdef daemon writes mirror files no sovereign-os consumer "
        f"reads (operator-cockpit gap): {sorted(orphans)}"
    )
