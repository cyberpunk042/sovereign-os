"""Gateway route-parity contract (F-2026-094 / SDD-956).

The gateway API reference (`docs/src/ai-backend.md`) enumerates every `/v1/*`
surface. The pre-existing `test_ai_backend_docs_contract.py` only checks that a
**static hand-listed** subset of endpoints appears in the doc — so the doc can
still silently drift from the code (a route added / renamed / removed in the
daemon without a matching doc edit).

This lint closes that gap: it extracts the **served route set** directly from the
gateway daemon's dispatch (`sovereign-gatewayd/src/http.rs` — the
`match (method, route)` block — plus the streaming intercepts in `main.rs`),
extracts the route set documented in `ai-backend.md`, and asserts they are
**equal, both directions**:

  - a route served by the daemon but NOT in the reference → CI fails until it is
    documented (no undocumented surface);
  - a route documented in the reference but NOT served → CI fails until the doc
    is corrected (no fictional / renamed / removed route).

So `ai-backend.md` becomes an enforced contract, the same counts-as-contract
discipline as `test_context_md_counts.py` (SDD-952) and
`test_island_register.py` (SDD-955), applied to the HTTP surface.

Extraction is by route **string literal**, not Rust match-arm parsing, so it is
robust to formatting/refactors — it only reacts to a route actually being
added/renamed/removed. The `#[cfg(test)]` module of each source file is excluded
(its route strings exercise the same real routes, but excluding it keeps the
served set unambiguous).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GATEWAYD_SRC = REPO_ROOT / "crates" / "sovereign-gatewayd" / "src"
HTTP_RS = GATEWAYD_SRC / "http.rs"
MAIN_RS = GATEWAYD_SRC / "main.rs"
AI_BACKEND = REPO_ROOT / "docs" / "src" / "ai-backend.md"

# A gateway route path literal: the /v1/* surface plus the fixed operational
# routes (liveness / manifest / ledger / metrics) and the /mcp alias.
_ROUTE_RE = re.compile(
    r"/(?:v1/[a-z0-9_-]+(?:/[a-z0-9_-]+)?|metrics|health|manifest|admin/ledger|mcp)\b"
)


def _strip_test_module(rust: str) -> str:
    """Drop the `#[cfg(test)]` module (tests are the last item in these files),
    so route literals in test code don't muddy the served set."""
    i = rust.find("#[cfg(test)]")
    return rust[:i] if i != -1 else rust


def _routes(text: str) -> set[str]:
    return set(_ROUTE_RE.findall(text))


def _served_routes() -> set[str]:
    out: set[str] = set()
    for src in (HTTP_RS, MAIN_RS):
        out |= _routes(_strip_test_module(src.read_text(encoding="utf-8")))
    return out


def _documented_routes() -> set[str]:
    return _routes(AI_BACKEND.read_text(encoding="utf-8"))


def test_source_and_doc_files_exist():
    for p in (HTTP_RS, MAIN_RS, AI_BACKEND):
        assert p.is_file(), f"missing {p}"


def test_every_served_route_is_documented():
    undocumented = sorted(_served_routes() - _documented_routes())
    assert not undocumented, (
        f"gateway routes served by the daemon but NOT in the API reference "
        f"docs/src/ai-backend.md: {undocumented}. Add a row to its endpoint "
        f"table (the reference must delineate every /v1/* surface — F-2026-094)."
    )


def test_every_documented_route_is_served():
    fictional = sorted(_documented_routes() - _served_routes())
    assert not fictional, (
        f"routes documented in docs/src/ai-backend.md but NOT served by the "
        f"gateway dispatch (renamed / removed / typo?): {fictional}. Fix the "
        f"reference so it matches the daemon."
    )


def test_the_reasoning_surfaces_are_present():
    """The two reasoning surfaces the finding calls out by name must both be
    served + documented (guards against one being dropped in a refactor)."""
    served = _served_routes()
    for route in ("/v1/deliberate", "/v1/coat"):
        assert route in served, f"{route} no longer served by the gateway"
