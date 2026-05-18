"""R431 (E10.M75) — architecture-qa catalog contract lint.

Extends R387-R430 + R423 operational-artifact pinning to:
  scripts/intelligence/architecture-qa.py  (master catalog: Q-NN
                                            questions + C-NN concepts
                                            + gotchas)

R423 covered the verbatim-render AGGREGATOR that pulls from this
module. R431 covers the CATALOG SOURCE itself — the 27 operator-named
concepts (C-01..C-27 — operator framing across § 13-17 of master spec)
+ 4 verbatim Q&A entries + 3 operational gotchas.

Each catalog entry MUST have:
  - id   (operator-named slug: Q-NN / C-NN / G-NN)
  - name OR question (the operator-discoverable handle)
  - tags (searchable index)
  - spec_ref (binding to master spec §)

Operator-verbatim contract:
  > "Each entry binds: id + question/answer + tags + spec_ref"
  > "operator-verbatim question (NO REPHRASING)"
  > "operator-verbatim answer (NO REPHRASING)"

If a future agent silently:
  - rephrases a question/answer = catalog drifts from operator-verbatim
  - drops a concept = R423 verbatim-render emits a shorter surface
  - adds an ID without master spec binding = catalog has orphan entries
…the operator-named catalog source silently shrinks.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AQA_PY = REPO_ROOT / "scripts" / "intelligence" / "architecture-qa.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("aqa", AQA_PY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- Structural ---


def test_architecture_qa_py_exists():
    assert AQA_PY.is_file(), f"missing {AQA_PY}"


def test_module_exports_three_catalogs():
    """The module MUST export ARCHITECTURE_QUESTIONS,
    ARCHITECTURE_GOTCHAS, ARCHITECTURE_CONCEPTS. Drift renaming =
    R423 verbatim-render aggregator's getattr() returns empty + lint
    silently passes."""
    mod = _load_module()
    for attr in ("ARCHITECTURE_QUESTIONS",
                 "ARCHITECTURE_GOTCHAS",
                 "ARCHITECTURE_CONCEPTS"):
        assert hasattr(mod, attr), (
            f"architecture-qa.py missing {attr} export "
            f"(R423 aggregator looks up this name)"
        )


def test_concepts_catalog_non_trivial():
    """27 operator-named C-NN concepts (§13-17 verbatim framing).
    Drift below ~20 = catalog shrunk."""
    mod = _load_module()
    concepts = mod.ARCHITECTURE_CONCEPTS
    assert len(concepts) >= 20, (
        f"ARCHITECTURE_CONCEPTS only {len(concepts)} entries "
        f"(operator-named ~27-entry catalog; drift = shrinkage)"
    )


# --- Per-concept required fields ---


def test_every_concept_has_id():
    mod = _load_module()
    for c in mod.ARCHITECTURE_CONCEPTS:
        assert c.get("id"), f"concept missing id: {c}"


def test_concept_ids_follow_c_nn_pattern():
    """Operator-named slug pattern: C-NN (where NN = 01..27)."""
    mod = _load_module()
    pattern = re.compile(r"^C-\d{2}$")
    for c in mod.ARCHITECTURE_CONCEPTS:
        cid = c.get("id", "")
        assert pattern.match(cid), (
            f"concept id={cid!r} doesn't match C-NN pattern "
            f"(operator-named slug convention)"
        )


def test_concept_ids_unique():
    """No duplicate concept IDs. Drift = R423 aggregator emits the
    same item twice."""
    mod = _load_module()
    ids = [c.get("id") for c in mod.ARCHITECTURE_CONCEPTS]
    assert len(ids) == len(set(ids)), (
        f"duplicate concept IDs: "
        f"{[i for i in ids if ids.count(i) > 1]}"
    )


def test_every_concept_has_name():
    mod = _load_module()
    for c in mod.ARCHITECTURE_CONCEPTS:
        assert c.get("name"), (
            f"concept {c.get('id')!r} missing name"
        )


def test_every_concept_has_explanation():
    """Operator-verbatim explanation MUST be non-empty."""
    mod = _load_module()
    for c in mod.ARCHITECTURE_CONCEPTS:
        explanation = c.get("explanation", "")
        assert explanation and len(explanation) >= 20, (
            f"concept {c.get('id')!r} missing/trivial explanation"
        )


def test_every_concept_has_spec_ref():
    """Operator-discoverable: each concept binds to a master spec §.
    Drift = catalog without spec anchors loses traceability."""
    mod = _load_module()
    for c in mod.ARCHITECTURE_CONCEPTS:
        spec_ref = c.get("spec_ref", "")
        assert spec_ref, (
            f"concept {c.get('id')!r} missing spec_ref"
        )
        # Should reference master spec §, macro-arc plan, hook drop,
        # operator dump, or another operator-named source-of-truth
        has_anchor = (
            "§" in spec_ref
            or "master spec" in spec_ref.lower()
            or "macro-arc" in spec_ref.lower()
            or "macro_arc" in spec_ref.lower()
            or "operator" in spec_ref.lower()
            or "dump" in spec_ref.lower()
            or "hook" in spec_ref.lower()
            or "plan" in spec_ref.lower()
        )
        assert has_anchor, (
            f"concept {c.get('id')!r} spec_ref={spec_ref!r} doesn't "
            f"reference master spec § / macro-arc / operator dump "
            f"(operator-discovery context)"
        )


def test_every_concept_has_tags():
    """tags[] non-empty (searchable index)."""
    mod = _load_module()
    for c in mod.ARCHITECTURE_CONCEPTS:
        tags = c.get("tags") or []
        assert tags, (
            f"concept {c.get('id')!r} missing tags (searchable index)"
        )


# --- Per-question required fields ---


def test_every_question_has_required_fields():
    mod = _load_module()
    for q in mod.ARCHITECTURE_QUESTIONS:
        assert q.get("id"), f"question missing id: {q}"
        assert q.get("question"), f"question {q.get('id')!r} missing question text"
        assert q.get("answer"), f"question {q.get('id')!r} missing answer"
        assert q.get("spec_ref"), f"question {q.get('id')!r} missing spec_ref"


def test_question_ids_follow_q_nn_pattern():
    mod = _load_module()
    pattern = re.compile(r"^Q-\d{2}$")
    for q in mod.ARCHITECTURE_QUESTIONS:
        qid = q.get("id", "")
        assert pattern.match(qid), (
            f"question id={qid!r} doesn't match Q-NN pattern"
        )


# --- Per-gotcha required fields ---


def test_every_gotcha_has_required_fields():
    mod = _load_module()
    for g in mod.ARCHITECTURE_GOTCHAS:
        assert g.get("id"), f"gotcha missing id: {g}"
        assert g.get("name"), f"gotcha {g.get('id')!r} missing name"


# --- Operator-named § 13-17 concept coverage ---


def test_concepts_cover_section_15_ternary():
    """§ 15 verbatim: 1-Bit Paradigm. At least one concept MUST
    reference § 15 / ternary."""
    mod = _load_module()
    has_s15 = any(
        "15" in c.get("spec_ref", "") or "ternary" in c.get("name", "").lower()
        for c in mod.ARCHITECTURE_CONCEPTS
    )
    assert has_s15, (
        "ARCHITECTURE_CONCEPTS missing § 15 / ternary coverage "
        "(operator-named 1-Bit Paradigm)"
    )


def test_concepts_cover_section_16_avx512():
    """§ 16: AVX-512 Hardware Fusion. At least one concept."""
    mod = _load_module()
    has_s16 = any(
        "16" in c.get("spec_ref", "") or "avx512" in c.get("name", "").lower()
        for c in mod.ARCHITECTURE_CONCEPTS
    )
    assert has_s16, (
        "ARCHITECTURE_CONCEPTS missing § 16 / AVX-512 coverage"
    )


def test_concepts_cover_section_17_trinity():
    """§ 17: Genesis Trinity. At least one concept."""
    mod = _load_module()
    has_s17 = any(
        "17" in c.get("spec_ref", "")
        or "trinity" in c.get("name", "").lower()
        or "trinity" in (c.get("tags") or [])
        for c in mod.ARCHITECTURE_CONCEPTS
    )
    assert has_s17, (
        "ARCHITECTURE_CONCEPTS missing § 17 / Trinity coverage"
    )


# --- Operator-verbatim "NO REPHRASING" contract ---


def test_module_documents_no_rephrasing_contract():
    """Header MUST document the operator-verbatim contract
    ('NO REPHRASING' or equivalent)."""
    body = AQA_PY.read_text(encoding="utf-8")
    has_contract = (
        "NO REPHRASING" in body
        or "no rephrasing" in body.lower()
        or "verbatim" in body.lower()
    )
    assert has_contract, (
        "architecture-qa.py missing operator-verbatim 'NO REPHRASING' "
        "contract documentation (drift = future agent rephrases "
        "operator-exact text)"
    )


def test_module_documents_per_entry_binding():
    """Module documents per-entry contract:
       id + question/answer/name + tags + spec_ref."""
    body = AQA_PY.read_text(encoding="utf-8")
    for field in ("id", "tags", "spec_ref"):
        assert field in body, (
            f"architecture-qa.py header missing {field!r} contract "
            f"documentation"
        )


# --- spec_ref hygiene ---


def test_no_fabricated_spec_ref_high_numbers():
    """Catches drift to fabricated section numbers (§ 9999 etc.).
    Master spec sections are §1-§23 + dump-tail."""
    mod = _load_module()
    # Find any §N where N > 30 — likely fabricated
    for c in mod.ARCHITECTURE_CONCEPTS:
        spec_ref = c.get("spec_ref", "")
        for m in re.finditer(r"§\s*(\d+)", spec_ref):
            n = int(m.group(1))
            assert n <= 30, (
                f"concept {c.get('id')!r} spec_ref={spec_ref!r} "
                f"references § {n} which is out of range (master spec "
                f"sections cap ~ § 23 — likely fabricated)"
            )


def test_no_empty_explanations():
    """An empty explanation makes the concept catalog entry
    inert. Drift = operator-pull verbs show C-NN with no body."""
    mod = _load_module()
    for c in mod.ARCHITECTURE_CONCEPTS:
        explanation = (c.get("explanation") or "").strip()
        assert len(explanation) > 0, (
            f"concept {c.get('id')!r} has empty explanation"
        )


def test_questions_answers_non_trivial():
    """operator-verbatim answer MUST be non-trivial (>20 chars)."""
    mod = _load_module()
    for q in mod.ARCHITECTURE_QUESTIONS:
        answer = (q.get("answer") or "").strip()
        assert len(answer) > 20, (
            f"question {q.get('id')!r} has trivial answer "
            f"(operator-verbatim answer should be substantive)"
        )
