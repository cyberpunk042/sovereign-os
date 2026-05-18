"""R403 (E10.M47) — inference router operator-verbatim §17.1 + SDD-011 lint.

Extends R387-R402 operational-artifact pinning to:
  scripts/inference/router.py

The router is the operator-named §17.1 Trinity dispatcher + SDD-011
deterministic-routing contract. It encodes the binding between:
  - Tier names (operator-verbatim): pulse / logic_engine / oracle_core
  - Port allocations: 8081 / 8082 / 8083 (must match start-*.sh scripts)
  - SDD-011 routing rules (deterministic, operator-readable in one screen)

If a future agent silently:
  - changes TIER_ENDPOINTS ports (drift from start-pulse.sh:8081 etc.)
  - renames a tier ('pulse' → 'fast' breaks SDD-016 metric labels)
  - removes Rule 1 (ternary → Pulse) → bitnet requests go to GPU =
    operator-named CCD 0 SRP violated + 50× cost
  - removes Rule 4 (JSON → Logic Engine) → structured output goes to
    Pulse = bitnet doesn't do JSON well = silent quality regression
…the §17.1 / SDD-011 contract silently breaks.

Cross-script consistency: TIER_ENDPOINTS ports MUST equal the
defaults in start-pulse.sh (8081) / start-logic-engine.sh (8082) /
start-oracle-core.sh (8083). This is a bidirectional-consistency
invariant — router writes to those ports, scripts listen on them.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTER = REPO_ROOT / "scripts" / "inference" / "router.py"
PULSE = REPO_ROOT / "scripts" / "inference" / "start-pulse.sh"
LOGIC = REPO_ROOT / "scripts" / "inference" / "start-logic-engine.sh"
ORACLE = REPO_ROOT / "scripts" / "inference" / "start-oracle-core.sh"


def _read_router() -> str:
    assert ROUTER.is_file(), f"missing {ROUTER}"
    return ROUTER.read_text(encoding="utf-8")


def _extract_tier_endpoints() -> dict[str, str]:
    """Parse TIER_ENDPOINTS dict literal from router.py via AST."""
    tree = ast.parse(_read_router())
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            tgt = node.target
            if isinstance(tgt, ast.Name) and tgt.id == "TIER_ENDPOINTS" \
                    and isinstance(node.value, ast.Dict):
                out: dict[str, str] = {}
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                        out[k.value] = v.value
                return out
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "TIER_ENDPOINTS" \
                        and isinstance(node.value, ast.Dict):
                    out2: dict[str, str] = {}
                    for k, v in zip(node.value.keys, node.value.values):
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                            out2[k.value] = v.value
                    return out2
    raise AssertionError(
        "router.py missing TIER_ENDPOINTS dict literal "
        "(operator-named §17.1 tier→endpoint binding)"
    )


def test_router_file_exists():
    assert ROUTER.is_file(), f"missing {ROUTER}"


def test_tier_endpoints_dict_parsable():
    endpoints = _extract_tier_endpoints()
    assert endpoints, "router.py TIER_ENDPOINTS dict empty"


# --- Operator-named tier keys (§17.1 + SDD-011 verbatim) ---


def test_tier_pulse_key_present():
    endpoints = _extract_tier_endpoints()
    assert "pulse" in endpoints, (
        "router.py TIER_ENDPOINTS missing 'pulse' tier key "
        "(operator-named §17.1 — Pulse / bitnet.cpp tier)"
    )


def test_tier_logic_engine_key_present():
    endpoints = _extract_tier_endpoints()
    assert "logic_engine" in endpoints, (
        "router.py TIER_ENDPOINTS missing 'logic_engine' tier key "
        "(operator-named §17.1 — Logic Engine / RTX 3090 tier)"
    )


def test_tier_oracle_core_key_present():
    endpoints = _extract_tier_endpoints()
    assert "oracle_core" in endpoints, (
        "router.py TIER_ENDPOINTS missing 'oracle_core' tier key "
        "(operator-named §17.1 — Oracle Core / Blackwell tier)"
    )


# --- Port binding (bidirectional consistency with start-*.sh) ---


def test_pulse_endpoint_port_8081():
    endpoints = _extract_tier_endpoints()
    assert ":8081" in endpoints.get("pulse", ""), (
        f"router.py pulse endpoint MUST be on port 8081 "
        f"(got {endpoints.get('pulse')!r}); MUST match start-pulse.sh default"
    )


def test_logic_engine_endpoint_port_8082():
    endpoints = _extract_tier_endpoints()
    assert ":8082" in endpoints.get("logic_engine", ""), (
        f"router.py logic_engine endpoint MUST be on port 8082 "
        f"(got {endpoints.get('logic_engine')!r}); MUST match start-logic-engine.sh"
    )


def test_oracle_core_endpoint_port_8083():
    endpoints = _extract_tier_endpoints()
    assert ":8083" in endpoints.get("oracle_core", ""), (
        f"router.py oracle_core endpoint MUST be on port 8083 "
        f"(got {endpoints.get('oracle_core')!r}); MUST match start-oracle-core.sh"
    )


def test_endpoints_use_loopback_only():
    """Trinity endpoints MUST be on 127.0.0.1 (loopback) — operator
    §8 verbatim Zero-Trust: backends MUST NOT bind externally; only
    the router is reachable from non-loopback. Drift to 0.0.0.0
    exposes raw backends to the §8 network surface."""
    endpoints = _extract_tier_endpoints()
    trinity_keys = ["pulse", "logic_engine", "oracle_core"]
    for key in trinity_keys:
        ep = endpoints.get(key, "")
        assert "127.0.0.1" in ep, (
            f"router.py {key} endpoint MUST be loopback 127.0.0.1 "
            f"(got {ep!r}); drift to 0.0.0.0 exposes raw Trinity "
            f"backends to network = §8 Zero-Trust violation"
        )


def test_bidirectional_router_pulse_port_consistency():
    """The 8081 port MUST appear in BOTH:
      - router.py TIER_ENDPOINTS['pulse']
      - start-pulse.sh as PULSE_PORT default
    Drift between the two breaks routing silently."""
    assert ":8081" in _extract_tier_endpoints().get("pulse", "")
    assert "8081" in PULSE.read_text(encoding="utf-8"), (
        "start-pulse.sh missing port 8081 (router.py expects it there)"
    )


def test_bidirectional_router_logic_engine_port_consistency():
    assert ":8082" in _extract_tier_endpoints().get("logic_engine", "")
    assert "8082" in LOGIC.read_text(encoding="utf-8"), (
        "start-logic-engine.sh missing port 8082 (router.py expects it)"
    )


def test_bidirectional_router_oracle_core_port_consistency():
    assert ":8083" in _extract_tier_endpoints().get("oracle_core", "")
    assert "8083" in ORACLE.read_text(encoding="utf-8"), (
        "start-oracle-core.sh missing port 8083 (router.py expects it)"
    )


# --- SDD-011 routing rules (deterministic dispatch) ---


def test_classify_function_defined():
    """SDD-011 verbatim: classify(request_body) returns a tier name.
    Operator-readable, deterministic. Drift to an LLM-based dispatcher
    would break SDD-011 'no black-box dispatch' contract."""
    body = _read_router()
    assert "def classify(" in body, (
        "router.py missing classify() function "
        "(SDD-011 verbatim — deterministic dispatch entry point)"
    )


def test_classify_rule_1_ternary_routes_to_pulse():
    """SDD-011 routing Rule 1 verbatim:
      'ternary models always go to Pulse (CPU CCD 0)'
    Drift losing this rule sends bitnet to GPU → operator-named
    CCD 0 SRP violated + 50× cost regression."""
    body = _read_router()
    has_rule1 = (
        ("bitnet" in body.lower())
        and ("ternary" in body.lower() or "pulse" in body.lower())
    )
    assert has_rule1, (
        "router.py classify() missing SDD-011 Rule 1 (ternary/bitnet → "
        "Pulse). Drift would send CPU-tier model to GPU silently."
    )


def test_classify_rule_4_json_routes_to_logic_engine():
    """SDD-011 routing Rule 4 verbatim:
      'JSON / structured output → Logic Engine'
    Drift losing this sends structured-output requests to Pulse where
    bitnet has weak JSON adherence = silent quality regression."""
    body = _read_router()
    has_rule4 = (
        "json_object" in body
        or "response_format" in body
    )
    assert has_rule4, (
        "router.py classify() missing SDD-011 Rule 4 (JSON/structured → "
        "Logic Engine). Drift breaks structured-output quality."
    )


def test_no_blackbox_llm_dispatch():
    """SDD-011 verbatim: 'No black-box dispatch.' classify() MUST be
    deterministic — no LLM call inside the routing decision.
    Catches drift to an LLM-as-router pattern."""
    body = _read_router()
    forbidden = [
        "openai.ChatCompletion",
        "anthropic.messages.create",
        "client.chat.completions.create",
        "model='gpt",
    ]
    bad = [f for f in forbidden if f in body]
    assert not bad, (
        f"router.py has LLM-call in routing path: {bad}. "
        f"SDD-011 verbatim 'No black-box dispatch' violated — "
        f"classify() MUST be deterministic."
    )


def test_record_route_metric_label_uses_tier():
    """SDD-016 verbatim metric:
      sovereign_os_inference_route_total{tier="<tier>"}
    Drift to {model="..."} or removal of tier label breaks the
    Trinity Grafana dashboard's per-tier aggregation."""
    body = _read_router()
    metric_name = "sovereign_os_inference_route_total"
    assert metric_name in body, (
        f"router.py missing metric {metric_name} (SDD-016 verbatim — "
        f"operator-discovery per-tier routing observability)"
    )
    # The tier= label MUST appear in the metric line emission
    # (router.py uses an f-string so the source has '{{tier=' escaping)
    has_tier_label = (
        re.search(rf"{re.escape(metric_name)}\{{tier=", body)
        or re.search(rf"{re.escape(metric_name)}\{{\{{tier=", body)
    )
    assert has_tier_label, (
        f"router.py metric {metric_name} missing tier= label format. "
        f"Drift breaks Grafana per-tier filtering."
    )


def test_x_sovereign_routed_tier_response_header():
    """Operator-discovery surface: response header X-Sovereign-Routed-Tier
    lets the operator inspect which tier handled each request. Drift
    losing this header silently removes the §17.1 observability."""
    body = _read_router()
    assert "X-Sovereign-Routed-Tier" in body, (
        "router.py missing X-Sovereign-Routed-Tier response header "
        "(operator-discovery — per-request tier observability)"
    )


def test_tier_count_at_least_three_trinity():
    """The Trinity (Pulse + Logic Engine + Oracle Core) MUST be at
    least 3 tiers. Fallback tiers (llama_old / llama_fb) are optional
    extras. Drift collapsing to 2 tiers breaks §17.1 SRP architecture."""
    endpoints = _extract_tier_endpoints()
    trinity = {"pulse", "logic_engine", "oracle_core"}
    present = trinity & set(endpoints.keys())
    assert present == trinity, (
        f"router.py TIER_ENDPOINTS missing Trinity tiers: "
        f"{trinity - present}. §17.1 SRP architecture requires all 3."
    )
