"""Shared API-daemon scaffold contract (F-2026-070, 2026-07-17).

The F-2026-070 audit reframed the "networking triplet merge": network-edge and
edge-firewall are concern-distinct daemons (disjoint endpoint sets) — NOT a fork.
The one real duplication was the ~170-line read-only HTTP daemon scaffold each
carried verbatim (metric emit + BaseHTTPRequestHandler boilerplate + serve()).
That scaffold now lives once in scripts/operator/_api_daemon.py and both daemons
build a DaemonSpec instead of re-implementing the plumbing.

This lint locks the dedup: the shared module exposes the scaffold API, both
daemons consume it, and neither has drifted back to a hand-rolled handler class.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OPERATOR = REPO / "scripts" / "operator"
SCAFFOLD = OPERATOR / "_api_daemon.py"
CONSUMERS = ["network-edge-api.py", "edge-firewall-api.py"]


def test_scaffold_exists_with_public_api():
    assert SCAFFOLD.is_file(), f"missing {SCAFFOLD}"
    spec = importlib.util.spec_from_file_location("_api_daemon", SCAFFOLD)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so the @dataclass string-annotation resolution finds
    # the module (this is exactly how the real daemons import it via sys.path).
    sys.modules["_api_daemon"] = mod
    spec.loader.exec_module(mod)
    assert hasattr(mod, "DaemonSpec"), "scaffold must export DaemonSpec"
    assert hasattr(mod, "serve"), "scaffold must export serve()"
    assert hasattr(mod, "make_handler"), "scaffold must export make_handler()"


def test_both_daemons_consume_the_scaffold():
    for name in CONSUMERS:
        body = (OPERATOR / name).read_text(encoding="utf-8")
        assert "import _api_daemon" in body, f"{name} does not import the scaffold"
        assert "_api_daemon.DaemonSpec(" in body, f"{name} does not build a DaemonSpec"
        assert "_api_daemon.serve(" in body, f"{name} does not delegate to shared serve()"


def test_daemons_no_longer_handroll_a_handler():
    """The whole point of the dedup: the daemons must NOT re-declare the
    BaseHTTPRequestHandler subclass / serve() boilerplate they used to carry."""
    for name in CONSUMERS:
        body = (OPERATOR / name).read_text(encoding="utf-8")
        # the class-definition pattern (not the bare word, which the module
        # docstring still mentions when explaining the stdlib basis)
        assert "(BaseHTTPRequestHandler)" not in body, (
            f"{name} still hand-rolls a handler class — scaffold not adopted"
        )
        assert "httpd.serve_forever" not in body, (
            f"{name} still hand-rolls serve() — scaffold not adopted"
        )


def test_scaffold_is_read_only_and_loopback_default():
    """The scaffold preserves the read-only + loopback doctrine: it rejects
    mutations and warns on a non-loopback bind."""
    body = SCAFFOLD.read_text(encoding="utf-8")
    for method in ("do_POST", "do_PUT", "do_DELETE", "do_PATCH"):
        assert method in body, f"scaffold must reject {method}"
    assert "_reject_mutation" in body and "405" in body
    assert "is NOT loopback" in body, "scaffold must warn on non-loopback bind"
