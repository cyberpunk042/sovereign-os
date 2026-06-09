"""Cockpit queue-script ⇄ dashboard-card data contract.

Each `scripts/cockpit/*queue*.py` is the sovereign-os cockpit consumer for
one selfdef pending-action queue (blockset / quarantine / token-revocation
/ ...). The dashboard `card_*_queue()` functions in scripts/dashboard/
serve.py run the script via `_run_json_at(...)` and pass its JSON straight
through to the card's `data`, with a fallback of `{"queue": [], "count": 0}`.
The frontend renders `data.queue` (the rows) + `data.count` (the badge).

So a queue script that emits a DIFFERENT top-level shape (renames `queue`,
drops `count`) makes its card render the empty fallback even when the
selfdef side has pending decisions — an operator-invisible queue, the §1g
minimization (a built operator surface that silently shows nothing). Lock
the contract: every cockpit queue script must emit both `queue` and
`count` at the JSON top level.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COCKPIT = REPO_ROOT / "scripts" / "cockpit"

# A queue script renders its JSON via json.dumps({... "queue": ..., "count":
# ...}). We require both literal keys to appear in a json.dumps / dict body.
_QUEUE_KEY = re.compile(r'["\']queue["\']\s*:')
_COUNT_KEY = re.compile(r'["\']count["\']\s*:')


def _queue_scripts() -> list[Path]:
    return sorted(p for p in COCKPIT.glob("*queue*.py")
                  if "__pycache__" not in p.parts)


def test_some_queue_scripts_exist():
    assert len(_queue_scripts()) >= 5, (
        f"only found {len(_queue_scripts())} cockpit queue scripts — "
        f"path/glob drift?"
    )


def test_every_queue_script_emits_queue_and_count():
    missing: list[str] = []
    for p in _queue_scripts():
        text = p.read_text(encoding="utf-8")
        has_q = _QUEUE_KEY.search(text) is not None
        has_c = _COUNT_KEY.search(text) is not None
        if not (has_q and has_c):
            lack = []
            if not has_q:
                lack.append("queue")
            if not has_c:
                lack.append("count")
            missing.append(f"{p.name} (missing: {', '.join(lack)})")
    assert not missing, (
        "cockpit queue script(s) do not emit the card data contract "
        "`{queue, count}` — their dashboard card_*_queue will render the "
        "empty fallback even with pending decisions:\n"
        + "\n".join(f"  - {m}" for m in missing)
    )
