"""Dashboard Bearer-token comparison must be constant-time (R250 auth).

scripts/dashboard/serve.py's `_authorized` gate compares the presented
Bearer token to the configured one. A plain `==` / `!=` short-circuits on
the first differing byte, leaking the token byte-by-byte to an attacker who
can time many requests — and the dashboard CAN be exposed off-loopback via
`--bind 0.0.0.0`. The comparison MUST use `hmac.compare_digest` (constant
time). This lint pins it so a refactor can't silently reintroduce a
timing-attackable `!= expected` on the token.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVE = REPO_ROOT / "scripts" / "dashboard" / "serve.py"


def _body() -> str:
    return SERVE.read_text(encoding="utf-8")


def test_serve_exists():
    assert SERVE.is_file(), f"missing {SERVE}"


def test_token_compare_is_constant_time():
    body = _body()
    assert "hmac.compare_digest(" in body, (
        "scripts/dashboard/serve.py no longer uses hmac.compare_digest for "
        "the Bearer-token check — a non-constant-time compare leaks the token "
        "to a timing attack. Use hmac.compare_digest(presented, expected)."
    )


def test_no_naive_token_equality():
    """Forbid `<token-ish> == expected` / `!= expected` — the naive compare
    the constant-time check replaced."""
    body = _body()
    naive = re.findall(r'(?:!=|==)\s*expected\b', body)
    assert not naive, (
        f"scripts/dashboard/serve.py compares a token to `expected` with a "
        f"naive operator {naive} — use hmac.compare_digest (constant time) so "
        f"the Bearer token can't be byte-by-byte timing-attacked."
    )
