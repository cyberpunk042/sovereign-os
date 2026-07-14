"""Agent-layer operator-documentation contract (F-2026-117 / SDD-708).

The frontend selector (SDD-704) + OpenClaw (705) + open-computer (706) + the backend
hotswap (707) were fully wired into the IaC and the `sovereign-osctl` CLI, but a
double-check found they'd never reached the OPERATOR-FACING docs — only the design SDDs
and the CLI's own `--help`. This lint makes the operator documentation of the agent layer
a machine-checked contract, so it can't silently drift behind the CLI again
(infrastructure > instructions):

  * the AI-backend guide (docs/src/ai-backend.md) documents all four verbs + the
    key-never-baked discipline + the local↔anthropic swap;
  * the lifecycle handbook (docs/src/ops/manage.md) lists the verbs;
  * every agent-layer verb the CLI actually dispatches is documented in the guide;
  * the guide is reachable from SUMMARY.md.

Note the scope this closes: SDD-704..707's own contracts stop at the CLI help text; this
is the doc-side companion.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AI_BACKEND = REPO_ROOT / "docs" / "src" / "ai-backend.md"
MANAGE = REPO_ROOT / "docs" / "src" / "ops" / "manage.md"
PROFILE_DOC = REPO_ROOT / "docs" / "src" / "profiles" / "sain-01.md"
SUMMARY = REPO_ROOT / "docs" / "src" / "SUMMARY.md"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

# The agent-layer verbs an operator must be able to discover from the docs.
AGENT_VERBS = ("frontend", "openclaw", "open-computer", "backend")


def _ai() -> str:
    return AI_BACKEND.read_text(encoding="utf-8")


def test_ai_backend_documents_every_agent_verb():
    body = _ai()
    for v in AGENT_VERBS:
        assert v in body, f"docs/src/ai-backend.md does not document the '{v}' verb (operator-discovery gap)"


def test_ai_backend_documents_the_swap_and_key_discipline():
    body = _ai().lower()
    # the local↔anthropic hotswap
    assert "local" in body and "anthropic" in body and "backend" in body, (
        "ai-backend.md does not explain the local↔anthropic backend swap"
    )
    # the never-baked key discipline (the sovereignty-critical detail)
    assert "never baked" in body or "never bake" in body or "not baked" in body or "anthropic-key.env" in body, (
        "ai-backend.md does not document that the hosted-Claude key is operator-supplied / never baked"
    )


def test_manage_handbook_lists_the_agent_verbs():
    body = MANAGE.read_text(encoding="utf-8")
    for v in AGENT_VERBS:
        assert v in body, f"docs/src/ops/manage.md (the lifecycle handbook) omits the '{v}' verb"


def test_profile_doc_points_at_the_agent_layer():
    body = PROFILE_DOC.read_text(encoding="utf-8")
    assert "openclaw" in body and "frontend" in body, (
        "docs/src/profiles/sain-01.md does not mention the agent layer it bakes"
    )


def test_guide_reachable_from_summary():
    body = SUMMARY.read_text(encoding="utf-8")
    assert "ai-backend.md" in body, "ai-backend.md is not linked from the mdbook SUMMARY"


def test_every_dispatched_agent_verb_is_documented():
    """Drift guard: every top-level agent-layer verb the CLI dispatches (frontend /
    openclaw / open-computer) must appear in the operator guide. A new one added to the
    dispatcher without a doc line fails here."""
    osctl = OSCTL.read_text(encoding="utf-8")
    ai = _ai()
    dispatched = set()
    for name in ("frontend", "openclaw", "open-computer"):
        # `  <name>) cmd_...` or `  <name>) exec ...` in the main dispatch
        if re.search(rf"(?m)^\s*{re.escape(name)}\)\s+(cmd_|exec)", osctl):
            dispatched.add(name)
    assert dispatched, "no agent-layer verbs found in the dispatcher (sanity)"
    missing = [v for v in dispatched if v not in ai]
    assert not missing, f"agent-layer verbs dispatched by the CLI but undocumented in ai-backend.md: {missing}"
