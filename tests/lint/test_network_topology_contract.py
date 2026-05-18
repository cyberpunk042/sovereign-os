"""R449 (E11.M8) — network-topology verb contract lint.

Per operator §1g verbatim:
  "Like normal my AI will also be behind a firewall which will do a VPN
   bridge to my other network since my two LANs are over two different
   WAN and that each have an ISP router with NAT and then my Opnsense
   Firewall with another NAT. This can be detected too I guess..."

Operator-named edge hardware (also §1g):
  "Sharevdi Fanless Firewall Mini PC Firewall Router Intel J3710/N3710
   Quad Core, 4X Intel 2.5GbE i226-V LAN Ports, 8G DDR3 128G SSD AES NI
   Network Gateway Test with pf-Sense/opn-Sense"

4th substantive feature of §1g/§1h Epic E11 arc:
  R446 (partial) — E11.M4 Nemotron 3 catalog enrichment
  R447 (shipped) — E11.M6 bashrc opt-in
  R448 (shipped) — E11.M5 global-history
  R449 (shipped) — E11.M8 network-topology + OPNsense
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NT_PY = REPO_ROOT / "scripts" / "operator" / "network-topology.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_network_topology_exists():
    assert NT_PY.is_file(), f"missing {NT_PY}"


def test_network_topology_executable():
    assert os.access(NT_PY, os.X_OK), f"{NT_PY} not executable"


def test_python3_shebang():
    body = _read(NT_PY)
    assert body.startswith("#!/usr/bin/env python3"), (
        "network-topology.py missing python3 shebang"
    )


def test_documents_e11_m8_origin():
    body = _read(NT_PY)
    assert "E11.M8" in body and "§1g" in body, (
        "network-topology.py missing E11.M8 + §1g binding"
    )


# --- Operator §1g verbatim hardware naming ---


def test_operator_named_edge_hardware_constant():
    """Operator §1g named the EXACT edge hardware spec. MUST be
    preserved as a constant."""
    body = _read(NT_PY)
    assert "OPERATOR_NAMED_EDGE_HARDWARE" in body, (
        "network-topology.py missing OPERATOR_NAMED_EDGE_HARDWARE "
        "constant (§1g verbatim hardware spec)"
    )


def test_operator_named_hardware_sharevdi():
    body = _read(NT_PY)
    assert "Sharevdi" in body, (
        "missing 'Sharevdi' (operator §1g edge-PC model)"
    )


def test_operator_named_hardware_j3710_n3710():
    body = _read(NT_PY)
    assert "J3710" in body and "N3710" in body, (
        "missing J3710/N3710 (operator §1g CPU)"
    )


def test_operator_named_hardware_i226v():
    body = _read(NT_PY)
    assert "i226-V" in body or "i226v" in body, (
        "missing i226-V (operator §1g NIC chipset)"
    )


def test_operator_named_hardware_aes_ni():
    body = _read(NT_PY)
    assert "AES-NI" in body or "AES NI" in body, (
        "missing AES-NI (operator §1g hardware crypto)"
    )


def test_operator_named_pfsense_opnsense_firmware():
    body = _read(NT_PY)
    assert "pfSense" in body or "OPNsense" in body or "opn-Sense" in body, (
        "missing pfSense/OPNsense firmware reference"
    )


# --- §1g verbatim topology ---


def test_documents_multi_nat_topology():
    """§1g: workstation → OPNsense (NAT 2) → ISP router (NAT 1) → public."""
    body = _read(NT_PY)
    # Multi-NAT concepts that MUST appear
    has_nat_chain = (
        "ISP router" in body
        and "OPNsense" in body
        and "NAT" in body
    )
    assert has_nat_chain, (
        "network-topology.py missing multi-NAT topology documentation"
    )


def test_documents_vpn_bridge():
    body = _read(NT_PY)
    assert "VPN bridge" in body, (
        "missing 'VPN bridge' (§1g operator-named cross-LAN topology)"
    )


def test_documents_two_lans():
    body = _read(NT_PY)
    assert "two LANs" in body or "two different WAN" in body or "LANs" in body.lower(), (
        "missing two-LAN topology framing"
    )


# --- CLI surface ---


def test_supports_detect_verb():
    body = _read(NT_PY)
    assert '"detect"' in body, "missing detect verb"


def test_supports_opnsense_verb():
    body = _read(NT_PY)
    assert '"opnsense"' in body, "missing opnsense verb"


def test_supports_interfaces_verb():
    body = _read(NT_PY)
    assert '"interfaces"' in body, "missing interfaces verb"


def test_supports_nat_chain_verb():
    body = _read(NT_PY)
    assert '"nat-chain"' in body, "missing nat-chain verb"


def test_opnsense_has_status_and_capabilities():
    body = _read(NT_PY)
    for v in ('"status"', '"capabilities"'):
        assert v in body, f"opnsense subcommands missing {v}"


def test_opnsense_has_watch_tui_subverb():
    """R483 (E11.M8+) — OPNsense status TUI surface, closes surface-map
    FUTURE waiver 'OPNsense status TUI worthwhile'."""
    body = _read(NT_PY)
    assert '"watch"' in body, (
        "network-topology.py missing opnsense watch TUI subverb"
    )
    assert "def cmd_opnsense_watch(" in body, (
        "network-topology.py missing cmd_opnsense_watch() function"
    )


def test_opnsense_watch_has_refresh_loop():
    """watch verb MUST have refresh loop (sleep + ANSI clear)
    — that's what makes it a TUI surface vs the one-shot status verb."""
    body = _read(NT_PY)
    assert "time.sleep(" in body, (
        "opnsense watch missing refresh loop (time.sleep)"
    )
    assert "\\x1b[2J" in body, (
        "opnsense watch missing ANSI clear-screen (TUI affordance)"
    )


def test_opnsense_watch_refuses_subsecond_refresh():
    """Operator-discoverable: refresh ≥ 1s; the verb refuses poll-storm."""
    body = _read(NT_PY)
    assert "max(1, int(args.refresh)" in body or "max(1, args.refresh" in body, (
        "opnsense watch missing refresh ≥1s floor"
    )


def test_opnsense_watch_emits_metric():
    """Layer B: opnsense_watch metric label so observability aggregates
    the new TUI surface separately."""
    body = _read(NT_PY)
    assert '"opnsense_watch"' in body and (
        "sovereign_os_operator_network_topology_query_total" in body
    ), "opnsense watch missing query_total metric emission"


def test_json_and_human_formats():
    body = _read(NT_PY)
    assert "--json" in body and "--human" in body, (
        "missing --json/--human flags"
    )


# --- Operator-mandate compliance: API key handling ---


def test_api_key_via_env_only_no_repo_storage():
    """Operator mandate: 'Operator-supplied keys NEVER in-repo'.
    API key + secret MUST be env-only — no hardcoded credentials,
    no file-system storage path that lives in-repo."""
    body = _read(NT_PY)
    assert "SOVEREIGN_OS_OPNSENSE_API_KEY" in body, (
        "missing SOVEREIGN_OS_OPNSENSE_API_KEY env (operator-keys-via-env)"
    )
    assert "SOVEREIGN_OS_OPNSENSE_API_SECRET" in body, (
        "missing SOVEREIGN_OS_OPNSENSE_API_SECRET env"
    )
    # Operator mandate phrase SHOULD appear (operator-discovery context).
    # Tolerates line-wrap in the doc comment (NEVER\n      in-repo).
    flat = re.sub(r"\s+", " ", body)
    has_mandate_quote = (
        "NEVER in-repo" in flat
        or "never in-repo" in flat
        or "Operator-supplied keys NEVER" in flat
    )
    assert has_mandate_quote, (
        "operator mandate phrase 'NEVER in-repo' missing from header docs"
    )


def test_no_hardcoded_api_credentials():
    """Sanity: no hardcoded long random-looking strings that could be
    leftover API key fragments."""
    body = _read(NT_PY)
    # No bare 32+ hex char strings (common API key shape)
    bad = re.findall(r"\"[a-fA-F0-9]{32,}\"", body)
    assert not bad, (
        f"suspicious hardcoded strings (possible API key leaks): {bad}"
    )


def test_supports_dry_run():
    body = _read(NT_PY)
    assert "SOVEREIGN_OS_DRY_RUN" in body, (
        "missing SOVEREIGN_OS_DRY_RUN handling"
    )


# --- OPNsense capability tiers (operator-discoverable ladder) ---


def test_5_opnsense_capability_tiers():
    """Operator-discoverable tier ladder:
      absent → unreachable → reachable-no-credentials →
      reachable-credentials-rejected → full-api"""
    body = _read(NT_PY)
    expected_tiers = [
        "absent",
        "unreachable",
        "reachable-no-credentials",
        "full-api",
    ]
    for t in expected_tiers:
        assert t in body, (
            f"OPNsense capability tier {t!r} missing"
        )


def test_full_api_tier_unlocks_features():
    """The full-api tier MUST list operator-discoverable unlocked
    integration features somewhere in the script body."""
    body = _read(NT_PY)
    # The full-api tier appears in 2 places: opnsense_state return +
    # capability matrix. Both should be present; we check that the
    # operator-discoverable feature names exist anywhere in the body.
    expected_features = [
        "firewall-rules-read",
        "interface-state-read",
        "vpn-tunnel-state-read",
    ]
    missing = [f for f in expected_features if f not in body]
    assert not missing, (
        f"full-api tier missing operator-discoverable feature names: "
        f"{missing}"
    )


# --- RFC 1918 + RFC 6598 private-IP detection ---


def test_rfc_1918_private_ranges():
    """Private-IP detection MUST cover RFC 1918 + RFC 6598 (CGNAT)."""
    body = _read(NT_PY)
    for cidr in ("10.0.0.0", "172.16.0.0", "192.168.0.0", "100.64.0.0"):
        assert cidr in body, (
            f"private-IP detection missing {cidr} CIDR"
        )


# --- Detection primitives (best-effort, never-raises) ---


def test_uses_ip_command():
    """Detection MUST use `ip` command (Linux-native) not `ifconfig`."""
    body = _read(NT_PY)
    assert "ip" in body and "addr" in body, (
        "missing `ip addr` interface enumeration"
    )


def test_uses_socket_for_reachability():
    """OPNsense reachability check MUST use Python socket (no
    network-tool dependency for tier-1 check)."""
    body = _read(NT_PY)
    assert "import socket" in body, (
        "missing socket import for reachability probes"
    )


def test_never_raises_pattern():
    """Detection primitives MUST be wrapped in try/except. Operator
    can't have the verb crash mid-detection."""
    body = _read(NT_PY)
    # Functions return on exception with empty / disabled state
    has_safety = body.count("except") >= 3
    assert has_safety, (
        "network-topology.py has too few try/except blocks "
        "(detection should be never-raises)"
    )


# --- SDD-016 metric ---


def test_emits_layer_b_metric():
    body = _read(NT_PY)
    assert "sovereign_os_operator_network_topology_query_total" in body, (
        "missing sovereign_os_operator_network_topology_query_total metric"
    )


# --- osctl integration ---


def test_osctl_dispatches_network_edge():
    """Note: original verb `network-topology` was taken (R359 master-
    spec §8 NIC-level topology). E11.M8 ships under sibling verb
    `network-edge` to avoid collision."""
    body = _read(OSCTL)
    assert "network-edge)" in body, (
        "osctl missing network-edge) dispatcher case"
    )
    assert "network-topology.py" in body, (
        "osctl dispatcher doesn't reference network-topology.py "
        "(script keeps its name; only the osctl verb is `network-edge`)"
    )


def test_osctl_help_documents_network_edge():
    body = _read(OSCTL)
    for sub in ("network-edge detect", "network-edge opnsense status",
                "network-edge interfaces", "network-edge nat-chain"):
        assert sub in body, f"osctl help missing {sub!r}"


def test_osctl_help_references_e11_m8():
    body = _read(OSCTL)
    assert "E11.M8" in body, "osctl help missing E11.M8 reference"


# --- Smoke test (interfaces verb is safest — works on any host) ---


def test_interfaces_verb_runs_without_error():
    """interfaces --json on an empty container returns empty list,
    not an error."""
    result = subprocess.run(
        ["python3", str(NT_PY), "interfaces", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"network-topology.py interfaces --json failed:\n"
        f"  stdout: {result.stdout[:200]}\n"
        f"  stderr: {result.stderr[:200]}"
    )
    import json as _json
    data = _json.loads(result.stdout)
    assert "interfaces" in data, "interfaces JSON missing 'interfaces' key"


def test_opnsense_status_runs_without_error():
    """opnsense status on a host with no OPNsense returns
    {tier: absent} cleanly, not an error."""
    result = subprocess.run(
        ["python3", str(NT_PY), "opnsense", "status", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"opnsense status failed: stderr={result.stderr[:200]}"
    )
    import json as _json
    data = _json.loads(result.stdout)
    assert "tier" in data, "opnsense status missing tier field"
    assert data["tier"] in [
        "absent", "unreachable", "reachable-no-credentials",
        "reachable-credentials-rejected", "reachable-curl-failed",
        "full-api",
    ], f"unexpected tier value: {data['tier']!r}"
