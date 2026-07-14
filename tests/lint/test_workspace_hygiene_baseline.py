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

  7. every member crate inherits the workspace lints at compile time
     (`[lints] workspace = true`), except the one sanctioned carve-out
     (`sovereign-simd`, which declares its own `[lints.rust] unsafe_code =
     "allow"`) — so the `unsafe_code = "forbid"` ban is enforced by the
     COMPILER on every other crate, not merely observed by a grep.

Invariant (7) closes F-2026-096 (SDD-710): the audit found 202 cockpit crates
declaring no `[lints]` table, so the compile-time `unsafe_code = "forbid"` ban
did not reach them — the ban's repo-wide guarantee rested on invariant (6)'s
grep alone. SDD-710 swept `[lints] workspace = true` into all of them, and this
invariant now pins that at CI time so a NEW crate without the inherit line fails
here. Invariant (6) is retained as a defence-in-depth co-guarantee (it also
catches an `unsafe` slipped into `sovereign-simd`-adjacent code or a manifest
edited to opt out), not merely a compensating control.
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


# --- 7. every crate inherits the workspace lints at COMPILE time -------------
# (F-2026-096 closed by SDD-710) — the manifest-level guarantee behind (6).

def _declares_workspace_lints(cargo_toml: Path) -> bool:
    """True iff the manifest carries `[lints]` with `workspace = true`. Parsed,
    not grepped, so whitespace/ordering can't fool it."""
    try:
        import tomllib
        data = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - a manifest that won't parse fails elsewhere
        return False
    return data.get("lints", {}).get("workspace") is True


def test_every_crate_inherits_workspace_lints_at_compile_time():
    """Every member crate MUST declare `[lints] workspace = true` so the root
    `unsafe_code = "forbid"` ban is enforced by the compiler — except the single
    sanctioned carve-out, which declares its own per-crate lint override. A new
    crate that forgets the inherit line (the F-2026-096 gap) fails here."""
    missing = [
        c.name for c in _crate_dirs()
        if c.name not in UNSAFE_ALLOWLIST
        and not _declares_workspace_lints(c / "Cargo.toml")
    ]
    assert not missing, (
        f"{len(missing)} crate(s) do not declare `[lints] workspace = true`, so "
        f"they do not inherit the compile-time `unsafe_code = \"forbid\"` ban "
        f"(F-2026-096 / SDD-710): {sorted(missing)[:10]}"
    )


def test_the_unsafe_carveout_opts_out_of_the_forbid_ban_explicitly():
    """The one carve-out must declare its own `[lints.rust] unsafe_code =
    "allow"` (not silently omit `[lints]`), so its exception is auditable in the
    manifest rather than implicit."""
    import tomllib
    for name in UNSAFE_ALLOWLIST:
        manifest = CRATES / name / "Cargo.toml"
        assert manifest.is_file(), f"carve-out crate {name} not found at {manifest}"
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
        rust = data.get("lints", {}).get("rust", {})
        allow = rust.get("unsafe_code")
        # tomllib maps a bare string; a table-with-level parses to a dict
        level = allow.get("level") if isinstance(allow, dict) else allow
        assert level == "allow", (
            f"{name} is the sanctioned unsafe carve-out but its manifest does not "
            f"declare `[lints.rust] unsafe_code = \"allow\"` (got {allow!r}) — the "
            f"exception must be explicit + auditable, not an omitted [lints] table"
        )
