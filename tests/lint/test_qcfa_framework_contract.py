#!/usr/bin/env python3
"""
tests/lint/test_qcfa_framework_contract.py — the QCFA + interactive-clarification
framework (docs/standing-directives/2026-07-11-qcfa-interactive-clarification.md).

Guards the interaction model the operator made canonical: QCFA (Task / Context /
References / Framework-Evaluate) + AskUserQuestion (hold execution, interview) +
suggestions — one framework, two homes (the local sovereign AI + external agents).

  * the standing directive exists, covers both homes, and is registered;
  * the reusable QCFA/AUQ system-prompt scaffold exists and carries the frame;
  * prompt.py injects the scaffold as a leading system turn, OPT-IN
    (SOVEREIGN_OS_QCFA), never double-injecting over a caller-supplied system turn.

Stdlib + pytest only.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIRECTIVE = REPO / "docs" / "standing-directives" / "2026-07-11-qcfa-interactive-clarification.md"
SCAFFOLD = REPO / "config" / "prompts" / "qcfa-system-prompt.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_standing_directive_exists_and_covers_both_homes():
    assert DIRECTIVE.is_file(), "the QCFA standing directive is missing"
    doc = _read(DIRECTIVE).lower()
    for token in ("qcfa", "askuserquestion", "task", "context", "references",
                  "framework", "hold execution", "suggest", "iterate"):
        assert token in doc, f"directive missing the QCFA/AUQ element: {token!r}"
    # one framework, two homes
    assert "local sovereign ai" in doc, "must cover the local sovereign AI home"
    assert "external agent" in doc, "must cover the external-agents home"
    # registered in the directives index
    idx = _read(REPO / "docs" / "standing-directives" / "INDEX.md")
    assert "qcfa-interactive-clarification.md" in idx, "not registered in INDEX.md"


def test_scaffold_present_and_carries_the_frame():
    assert SCAFFOLD.is_file(), "the QCFA/AUQ scaffold is missing"
    sc = _read(SCAFFOLD).lower()
    for token in ("task", "context", "references", "hold execution",
                  "clarif", "suggest"):
        assert token in sc, f"scaffold missing the frame element: {token!r}"


def test_scaffold_specifies_the_renderable_envelope():
    # the model must emit questions in a machine-parseable envelope the chat
    # surface can render as interactive choices (not raw text / a code block).
    sc = _read(SCAFFOLD)
    assert "askuserquestion" in sc, "scaffold must name the parseable envelope"
    assert '"questions"' in sc and '"options"' in sc, "scaffold must define the JSON shape"


def test_all_chat_surfaces_render_auq_interactively():
    # every chat surface must render the clarification as interactive choices —
    # not raw text / a code block — with a graceful <pre> fallback if unparseable.
    for slug in ("code-console", "brain", "d-22-lm-status-operability"):
        body = _read(REPO / "webapp" / slug / "index.html")
        assert "askuserquestion" in body, f"{slug}: must detect the askuserquestion envelope"
        assert ("renderAssistantHTML" in body or "auqRenderHTML" in body), f"{slug}: no AUQ renderer"
        assert ("hydrateAUQ" in body or "auqHydrate" in body), f"{slug}: no AUQ hydrate (interactive)"
        assert ("cc-auq" in body or 'class="auq' in body), f"{slug}: no AUQ card markup"
        assert "<pre" in body, f"{slug}: no graceful code-block fallback (never raw-swallow a question)"


def test_prompt_injects_qcfa_opt_in_without_double_inject(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "_prompt_qcfa", REPO / "scripts" / "inference" / "prompt.py")
    p = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p)

    # OFF (default posture): the base-model chat is never degraded.
    monkeypatch.setattr(p, "QCFA_ENABLED", False)
    off = p._maybe_prepend_qcfa([{"role": "user", "content": "hi"}])
    assert [m["role"] for m in off] == ["user"], "must not inject when disabled"

    # ON: a leading system turn carrying the scaffold.
    monkeypatch.setattr(p, "QCFA_ENABLED", True)
    on = p._maybe_prepend_qcfa([{"role": "user", "content": "hi"}])
    assert [m["role"] for m in on] == ["system", "user"], "must prepend a system turn"
    assert on[0]["content"].strip(), "the injected system turn must be non-empty"

    # never double-inject: a caller-supplied system turn wins.
    kept = p._maybe_prepend_qcfa(
        [{"role": "system", "content": "CALLER"}, {"role": "user", "content": "hi"}])
    assert kept[0]["content"] == "CALLER", "caller system turn must win"

    # it is genuinely env-gated (opt-in), not hard-on.
    src = _read(REPO / "scripts" / "inference" / "prompt.py")
    assert "SOVEREIGN_OS_QCFA" in src and "chat = _maybe_prepend_qcfa(chat)" in src
