"""Workspace-hygiene baseline contract (F-2026-004 / SDD-974).

The Phase-1 audit found the crate workspace's hygiene *exemplary* and asked for
a lint so "the bar never silently drops". This is that contract. It recomputes
each invariant from the tree and fails CI on drift, in either direction, so the
baseline can neither rot nor be quietly weakened:

  1. the root `[workspace.lints.rust]` still declares `unsafe_code = "forbid"`
     and `missing_docs = "warn"` (the two load-bearing bans);
  2. every member crate manifest declares a `description`;
  3. every crate carries tests, except the one sanctioned exception
     (`sovereign-feature-selftest`, a marker crate by design);
  4. crate `.rs` sources are marker-free (`todo!()` / `unimplemented!()` /
     `FIXME` / `TODO`) — real work is tracked in SDDs/backlog, not code tombstones;
  5. crate `.rs` sources hardcode no `/home` `/Users` `/root` absolute paths;
  6. `unsafe` is confined to the single sanctioned carve-out (`sovereign-simd`,
     the one crate the operator permits `unsafe` in for AVX-512 intrinsics).

Invariant (6) is also the *compensating control* for a latent gap this audit
surfaced (F-2026-096): 202 cockpit crates do not declare `[lints] workspace =
true`, so they do not inherit the compile-time `unsafe_code = "forbid"` ban. The
inheritance itself is a manifest-unification follow-up owned elsewhere; until
then, this grep-level assertion guarantees at CI time that none of those crates
actually uses `unsafe` — the ban's practical guarantee holds repo-wide.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_CARGO = REPO_ROOT / "Cargo.toml"
CRATES = REPO_ROOT / "crates"

# Crates allowed to have no tests (marker / selftest crates, by design).
NO_TEST_ALLOWLIST = {"sovereign-feature-selftest"}
# The single sanctioned `unsafe` carve-out (operator decision — AVX-512).
UNSAFE_ALLOWLIST = {"sovereign-simd"}

_MARKER_RE = re.compile(r"\btodo!\s*\(|\bunimplemented!\s*\(|\bFIXME\b|\bTODO\b")
_ABS_PATH_RE = re.compile(r'"/(?:home|Users|root)/')
_UNSAFE_RE = re.compile(r"\bunsafe\s*(?:\{|fn\b|impl\b|trait\b)")


def _crate_dirs() -> list[Path]:
    return sorted(p for p in CRATES.iterdir() if (p / "Cargo.toml").is_file())


def _rs_sources(crate: Path) -> list[Path]:
    src = crate / "src"
    return sorted(src.rglob("*.rs")) if src.is_dir() else []


def _strip_noise(line: str) -> str:
    """Drop line-comment tails and string bodies so we match real code tokens,
    not prose in `//` comments or the word inside a `"..."` literal."""
    # cut at the first line-comment marker
    line = re.split(r"//", line, maxsplit=1)[0]
    # blank out double-quoted string bodies
    return re.sub(r'"[^"]*"', '""', line)


# --- 1. root workspace lints -------------------------------------------------

def test_root_declares_load_bearing_lints():
    body = ROOT_CARGO.read_text(encoding="utf-8")
    m = re.search(r"\[workspace\.lints\.rust\](.*?)(?:\n\[|\Z)", body, re.S)
    assert m, "root Cargo.toml has no [workspace.lints.rust] section"
    section = m.group(1)
    assert re.search(r'unsafe_code\s*=\s*"forbid"', section), (
        "root [workspace.lints.rust] no longer forbids unsafe_code — the "
        "repo-wide unsafe ban is load-bearing (SDD-974 / F-2026-004)"
    )
    assert re.search(r'missing_docs\s*=\s*"warn"', section), (
        "root [workspace.lints.rust] no longer warns on missing_docs "
        "(SDD-974 / F-2026-004)"
    )


# --- 2. every member declares a description ----------------------------------

def test_every_crate_declares_a_description():
    missing = [
        c.name
        for c in _crate_dirs()
        if not re.search(r"^\s*description", (c / "Cargo.toml").read_text(encoding="utf-8"), re.M)
    ]
    assert not missing, (
        f"{len(missing)} crate manifest(s) declare no description "
        f"(literal or `.workspace = true`): {missing[:10]}"
    )


# --- 3. every crate carries tests (except the allowlist) ---------------------

def test_every_crate_carries_tests():
    testless = []
    for c in _crate_dirs():
        has_test = any(
            re.search(r"#\[(?:test|cfg\(test\))", p.read_text(encoding="utf-8", errors="ignore"))
            for p in _rs_sources(c)
        )
        if not has_test:
            testless.append(c.name)
    unexpected = sorted(set(testless) - NO_TEST_ALLOWLIST)
    assert not unexpected, (
        f"{len(unexpected)} crate(s) carry no tests and are not in the "
        f"NO_TEST_ALLOWLIST: {unexpected[:10]}"
    )
    # keep the allowlist honest — it may not list crates that now have tests
    stale = sorted(NO_TEST_ALLOWLIST - set(testless))
    assert not stale, (
        f"NO_TEST_ALLOWLIST names crate(s) that now carry tests: {stale} — "
        f"drop them from the allowlist"
    )


# --- 4. marker-free crate sources --------------------------------------------

def test_crate_sources_are_marker_free():
    hits: list[str] = []
    for c in _crate_dirs():
        for p in _rs_sources(c):
            for n, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if _MARKER_RE.search(_strip_noise(line)):
                    hits.append(f"{p.relative_to(REPO_ROOT)}:{n}")
    assert not hits, (
        f"{len(hits)} code-marker(s) (todo!()/unimplemented!()/FIXME/TODO) in "
        f"crate sources — track work in SDDs/backlog, not code: {hits[:10]}"
    )


# --- 5. no hardcoded absolute home paths -------------------------------------

def test_crate_sources_have_no_absolute_home_paths():
    hits: list[str] = []
    for c in _crate_dirs():
        for p in _rs_sources(c):
            for n, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if _ABS_PATH_RE.search(line):
                    hits.append(f"{p.relative_to(REPO_ROOT)}:{n}")
    assert not hits, (
        f"{len(hits)} hardcoded /home|/Users|/root absolute path(s) in crate "
        f"sources — derive paths at runtime: {hits[:10]}"
    )


# --- 6. unsafe confined to the sanctioned carve-out --------------------------

def test_unsafe_is_confined_to_the_sanctioned_carveout():
    users = []
    for c in _crate_dirs():
        for p in _rs_sources(c):
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                if _UNSAFE_RE.search(_strip_noise(line)):
                    users.append(c.name)
                    break
            else:
                continue
            break
    unexpected = sorted(set(users) - UNSAFE_ALLOWLIST)
    assert not unexpected, (
        f"crate(s) use `unsafe` outside the sanctioned carve-out "
        f"{sorted(UNSAFE_ALLOWLIST)}: {unexpected} — 202 cockpit crates do not "
        f"inherit the compile-time ban (F-2026-096); this lint is the "
        f"repo-wide compensating control"
    )
    stale = sorted(UNSAFE_ALLOWLIST - set(users))
    assert not stale, (
        f"UNSAFE_ALLOWLIST names crate(s) that no longer use unsafe: {stale} — "
        f"drop them so the carve-out stays minimal"
    )
