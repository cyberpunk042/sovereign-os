"""Dashboard card registration coverage — every `card_*` function defined
in scripts/dashboard/serve.py MUST be registered in the CARDS list.

E4.M2 ("18 cards spanning every shipped axis") grew to 40 cards as
enforcement-layer + intelligence + hardware axes were added. The grid test
locks a `card_count >= 20` floor and the intel-cards test checks 5 specific
cards — but nothing guaranteed that a `card_*` function an author writes is
actually REGISTERED in CARDS. A defined-but-unregistered card is invisible
to the operator (the function exists, renders nothing on the dashboard) —
the silent minimization §1g forbids: the operator built a surface and it
never shows. Lock defined ⇄ registered so a new card can't ship unshown.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASH_DIR = REPO_ROOT / "scripts" / "dashboard"


def _serve_module():
    sys.path.insert(0, str(DASH_DIR))
    import serve  # type: ignore

    return serve


def test_every_card_function_is_registered_in_cards():
    serve = _serve_module()
    defined = {
        name
        for name, obj in inspect.getmembers(serve, inspect.isfunction)
        if name.startswith("card_") and obj.__module__ == serve.__name__
    }
    registered = {fn.__name__ for fn in serve.CARDS}

    orphans = sorted(defined - registered)
    assert not orphans, (
        f"card function(s) {orphans} are defined in serve.py but NOT in the "
        f"CARDS list — they render nothing on the dashboard (operator-"
        f"invisible). Add them to CARDS or remove the dead function."
    )

    phantoms = sorted(registered - defined)
    assert not phantoms, (
        f"CARDS references {phantoms} which are not `card_*` functions "
        f"defined in serve.py (broken registry)."
    )


def test_cards_list_is_nonempty_and_callables():
    serve = _serve_module()
    assert serve.CARDS, "CARDS list is empty"
    assert all(callable(fn) for fn in serve.CARDS), (
        "every CARDS entry must be a callable card_* function"
    )
