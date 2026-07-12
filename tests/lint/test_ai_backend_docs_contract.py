#!/usr/bin/env python3
"""
tests/lint/test_ai_backend_docs_contract.py — the user-facing docs for using the
box as an AI backend + its reasoning/operability surfaces.

Guards that the two new mdBook chapters exist, are registered in the book TOC +
the README, cover the load-bearing content (editor wiring, the endpoint reference,
the CoAT ladder, Background Tasks, the Code Console), and — most importantly — that
every relative link in them RESOLVES (no broken cross-links / typos'd paths).

Stdlib + pytest only.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "docs" / "src"
AI = SRC / "ai-backend.md"
REASON = SRC / "reasoning-operability.md"
SUMMARY = SRC / "SUMMARY.md"
README = REPO / "README.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_pages_exist_registered_and_linked():
    assert AI.is_file() and REASON.is_file(), "the two AI-backend chapters must exist"
    toc = _read(SUMMARY)
    assert "ai-backend.md" in toc and "reasoning-operability.md" in toc, "not registered in SUMMARY.md"
    readme = _read(README)
    assert "docs/src/ai-backend.md" in readme, "README must link the AI-backend guide"
    assert "docs/src/reasoning-operability.md" in readme, "README must link the reasoning guide"


def test_ai_backend_covers_the_editor_wiring_and_endpoints():
    doc = _read(AI)
    for token in ("ANTHROPIC_BASE_URL", "VS Code", "Claude Code", "Cline",
                  "127.0.0.1:8787", "SOVEREIGN_GATEWAY_MODEL"):
        assert token in doc, f"AI-backend guide missing: {token!r}"
    # the endpoint reference must name every generating/decision surface
    for endpoint in ("/v1/messages", "/v1/models", "/v1/messages/count_tokens",
                     "/v1/chat/completions", "/v1/infer", "/v1/deliberate", "/v1/coat"):
        assert endpoint in doc, f"endpoint reference missing: {endpoint}"
    # the sovereign posture (never fabricated / loopback / no cloud spill)
    low = doc.lower()
    assert "never fabricated" in low or "sb-077" in low, "must state the never-fabricated posture"
    assert "loopback" in low, "must state loopback-trust"


def test_reasoning_page_covers_the_features():
    doc = _read(REASON)
    for token in ("CoAT", "Brain observatory", "Background Tasks", "Code Console",
                  "sovereign-osctl jobs", "/v1/coat"):
        assert token in doc, f"reasoning guide missing: {token!r}"
    # the full ladder is named
    for rung in ("CoT", "ToT", "MCTS", "C-MCTS"):
        assert rung in doc, f"reasoning ladder missing rung: {rung}"


def _relative_link_targets(md: str):
    # [text](target) where target is a local path (not http, not a bare #anchor)
    for m in re.finditer(r"\]\(([^)]+)\)", md):
        tgt = m.group(1).strip()
        if tgt.startswith("http://") or tgt.startswith("https://") or tgt.startswith("#"):
            continue
        yield tgt.split("#", 1)[0]  # drop any anchor


def test_all_relative_links_resolve():
    for page in (AI, REASON):
        base = page.parent
        for tgt in _relative_link_targets(_read(page)):
            if not tgt:
                continue
            resolved = (base / tgt).resolve()
            assert resolved.exists(), f"{page.name}: broken link → {tgt}"
