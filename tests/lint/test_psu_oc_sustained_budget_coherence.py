"""PSU overclock-mode sustained-budget coherence (mandate E1.M33).

Two tools model the operator's reference PSU (be Quiet! Dark Power Pro 13):
  - psu-oc.py registry: `rated_oc_mode_watts == rated_standard_watts`
    (the OC switch is a multi-rail->single-rail consolidation — NO
    sustained-output shift; peak shifts via ATX 3.1, not sustained).
  - power-status.py: applies `overclock_multiplier` to the SUSTAINED rated
    wattage when OC is enabled.

Operator mandate E1.M33 (verbatim) is the authority: the OC switch
"combines multiple +12V rails into one stronger rail" and "raises max safe
gpu_oc_multiplier ceiling" — it lifts PER-RAIL / GPU-OC headroom, NOT the
sustained total. So power-status's `overclock_multiplier` must DEFAULT to
1.0 (no sustained lift), agreeing with psu-oc. It previously defaulted to
1.10, over-stating the sustained budget by ~10% (1600->1760 W) — the unsafe
direction, contradicting both the mandate and psu-oc. This lint pins the
coherence so the +10% default can't creep back.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
POWER_STATUS = REPO_ROOT / "scripts" / "hardware" / "power-status.py"
PSU_OC = REPO_ROOT / "scripts" / "hardware" / "psu-oc.py"
EXAMPLE = REPO_ROOT / "config" / "power.toml.example"


def test_power_status_default_multiplier_is_unity():
    body = POWER_STATUS.read_text(encoding="utf-8")
    m = re.search(
        r'psu\.get\(\s*["\']overclock_multiplier["\']\s*,\s*([0-9.]+)\s*\)',
        body)
    assert m, "could not find overclock_multiplier default in power-status.py"
    default = float(m.group(1))
    assert default == 1.0, (
        f"power-status.py defaults overclock_multiplier to {default}, but the "
        f"reference PSU's OC mode does NOT raise the SUSTAINED budget (mandate "
        f"E1.M33 + psu-oc.py: rail consolidation, rated_oc == rated_standard). "
        f"A >1.0 default over-states the sustained budget (the unsafe "
        f"direction). Keep the default 1.0; PSUs that genuinely lift sustained "
        f"output set it explicitly in power.toml."
    )


def test_example_documents_unity_default():
    body = EXAMPLE.read_text(encoding="utf-8")
    m = re.search(r'(?m)^\s*overclock_multiplier\s*=\s*([0-9.]+)', body)
    assert m, "power.toml.example does not set overclock_multiplier"
    assert float(m.group(1)) == 1.0, (
        f"power.toml.example documents overclock_multiplier={m.group(1)} — must "
        f"be 1.0 (no sustained lift) for the reference PSU. An operator copying "
        f"the example would otherwise over-state their sustained PSU budget."
    )


def test_psu_oc_reference_spec_has_no_sustained_shift():
    """The authority the default mirrors: the be Quiet! Dark Power Pro 13
    entry must keep rated_oc_mode_watts == rated_standard_watts. If a future
    edit makes them differ, the power-status default + this contract must be
    revisited together (the two tools would then genuinely disagree)."""
    body = PSU_OC.read_text(encoding="utf-8")
    # Find the be Quiet! block and the two rated_* fields within it.
    blk = re.search(
        r'"model":\s*"be Quiet! Dark Power Pro 13[^"]*".*?"oc_mode_semantics"',
        body, re.S)
    assert blk, "could not locate the be Quiet! Dark Power Pro 13 spec block"
    std = re.search(r'"rated_standard_watts":\s*([0-9]+)', blk.group(0))
    oc = re.search(r'"rated_oc_mode_watts":\s*([0-9]+)', blk.group(0))
    assert std and oc, "rated_standard_watts / rated_oc_mode_watts not found"
    assert std.group(1) == oc.group(1), (
        f"psu-oc.py reference PSU now has rated_oc_mode_watts={oc.group(1)} != "
        f"rated_standard_watts={std.group(1)} — if OC mode genuinely shifts the "
        f"sustained rating, power-status.py's default overclock_multiplier (and "
        f"the mandate E1.M33 framing) must be revisited to stay coherent."
    )
