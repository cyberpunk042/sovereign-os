#!/usr/bin/env python3
"""scripts/operator/edge-firewall.py — R451 (E11.M9).

Operator §1g verbatim:
  "even if there isn't an Edge firewall its possible to install the
   equivalent or even more advanced if we want on this machine if we
   would be ready to pay the performance price but that it will accept
   the Edge Firewall and its level, even if its not a full IPS since
   its a 'Sharevdi Fanless Firewall Mini PC Firewall Router Intel
   J3710/N3710 Quad Core, 4X Intel 2.5GbE i226-V LAN Ports, 8G DDR3
   128G SSD AES NI Network Gateway Test with pf-Sense/opn-Sense' and
   has limitations, it being 'fanless&cheap' but interesting to do the
   networting and VPN bridge part, and we can still offer to install
   our own other module and do whatever we want on the AI workstation
   no matter the edge router or firewall detected and bridge state and
   rules and etc."

The §1g surface for the operator-discoverable workstation-side
edge-firewall alternative. Pairs with R449 (network-edge detection):
R449 detects what's UPSTREAM; R451 advises what to install on the
WORKSTATION ITSELF given upstream state.

Operator-named candidates (4 install-class options, from lightweight
to heavy):
  1. nftables-baseline    — stateful Linux firewall (kernel-native;
                             negligible performance cost)
  2. fail2ban             — log-driven SSH/HTTP brute-force ban
                             (low overhead)
  3. crowdsec             — community-curated IP reputation +
                             behavioral analysis (moderate overhead)
  4. suricata             — full IDS/IPS engine (HIGH overhead —
                             operator pays performance price per §1g
                             verbatim "if we would be ready to pay
                             the performance price")

CLI:
  edge-firewall.py state [--json|--human]
                            What's installed locally + what's detected
                            upstream (via R449 network-edge bridge).

  edge-firewall.py candidates [--json|--human]
                            Enumerate the 4 install-class options +
                            their contract (perf cost, threat model,
                            operator §1g binding).

  edge-firewall.py recommend [--json|--human]
                            Operator-discoverable: given local +
                            upstream state, what should I install?
                            Returns prioritized list.

  edge-firewall.py install-plan <candidate> [--json|--human]
                            For one candidate, render the apt + config
                            install plan. Operator-runnable; NEVER
                            executes by default.

  edge-firewall.py install <candidate> [--apply --confirm-install]
                            [--json|--human]
                            Triple-gated installer (--apply +
                            --confirm-install + DRY_RUN respected).
                            Operator-named "performance cost"
                            disclosure required.

Exit codes:
  0 ok
  1 unknown subcommand / unknown candidate
  2 install blocked (gates missing) or environmental failure
  3 candidate already installed (no-op)

Layer B metric (SDD-016):
  sovereign_os_operator_edge_firewall_query_total{verb,candidate,result}

Operator-environment env vars:
  SOVEREIGN_OS_EDGE_FIREWALL_DRY_RUN  Logs intent; no apt/config writes.
  SOVEREIGN_OS_DRY_RUN                Same effect (sovereign-wide).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

# Metrics output dir
METRICS_DIR = pathlib.Path(os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
))
DRY_RUN = bool(
    os.environ.get("SOVEREIGN_OS_DRY_RUN")
    or os.environ.get("SOVEREIGN_OS_EDGE_FIREWALL_DRY_RUN")
)

# Pair with R449 detection (we shell out, never import — keeps
# this script standalone)
NETWORK_EDGE_PY = (
    pathlib.Path(__file__).resolve().parent / "network-topology.py"
)

# 4 operator-named candidates (low → high overhead)
CANDIDATES = [
    {
        "id": "nftables-baseline",
        "level": 1,
        "label": "nftables baseline (kernel-native stateful firewall)",
        "kind": "kernel-firewall",
        "perf_cost": "negligible (kernel-native packet filtering)",
        "threat_model": (
            "Per-port allow/deny + stateful connection tracking; blocks "
            "unsolicited inbound. Does NOT do signature-based IDS, log "
            "correlation, or behavioral analysis."
        ),
        "operator_named_use": (
            "Always-on baseline. Even when an upstream edge firewall "
            "is present, nftables locally is operator's defense-in-depth "
            "layer against LAN-side lateral movement."
        ),
        "install_summary": "apt install nftables; enable systemd unit",
        "apt_packages": ["nftables"],
        "systemd_units": ["nftables.service"],
        "config_paths": ["/etc/nftables.conf"],
    },
    {
        "id": "fail2ban",
        "level": 2,
        "label": "fail2ban (log-driven brute-force ban)",
        "kind": "log-reactive",
        "perf_cost": "low (Python daemon reading journals; ~50 MB RAM)",
        "threat_model": (
            "Watches log files (sshd, web, etc.) for failed-auth patterns; "
            "temp-bans source IPs via firewall hook. Does NOT inspect "
            "packet contents; reacts only to logged events."
        ),
        "operator_named_use": (
            "Recommended for any sovereign-os profile exposing SSH or "
            "web dashboards. Cheap insurance against scripted brute-force."
        ),
        "install_summary": (
            "apt install fail2ban; enable jails for sshd + any exposed "
            "web service"
        ),
        "apt_packages": ["fail2ban"],
        "systemd_units": ["fail2ban.service"],
        "config_paths": ["/etc/fail2ban/jail.d/sovereign-os.local"],
    },
    {
        "id": "crowdsec",
        "level": 3,
        "label": "crowdsec (community IP reputation + behavioral)",
        "kind": "behavioral-ips",
        "perf_cost": (
            "moderate (Go daemon + bouncer; ~200-400 MB RAM; CPU on "
            "log analysis; community blocklist pull traffic)"
        ),
        "threat_model": (
            "Reads logs like fail2ban PLUS subscribes to a community-"
            "curated IP reputation blocklist. Behavioral scenarios "
            "detect patterns across log sources. Optional bouncers "
            "enforce at firewall / nginx / cloudflare layer."
        ),
        "operator_named_use": (
            "Worth installing when the operator is exposing dashboards "
            "to the internet (even through a tunnel) and wants "
            "proactive defense beyond per-host log triggers."
        ),
        "install_summary": (
            "apt install crowdsec crowdsec-firewall-bouncer-nftables; "
            "register with central API (optional)"
        ),
        "apt_packages": ["crowdsec", "crowdsec-firewall-bouncer-nftables"],
        "systemd_units": ["crowdsec.service",
                          "crowdsec-firewall-bouncer.service"],
        "config_paths": ["/etc/crowdsec/", "/etc/crowdsec/bouncers/"],
    },
    {
        "id": "suricata",
        "level": 4,
        "label": "suricata (full IDS/IPS with signature engine)",
        "kind": "deep-packet-ips",
        "perf_cost": (
            "HIGH (multi-threaded C engine; signature DB; can saturate "
            "1-2 CPU cores at 10GbE line rate; ~1-2 GB RAM with default "
            "ET-Open ruleset). Per operator §1g 'pay the performance "
            "price'."
        ),
        "threat_model": (
            "Deep-packet inspection with thousands of signatures (ET-"
            "Open / Talos / commercial feeds). Can run as IDS (alert) "
            "or IPS (drop) inline. Catches signature-known attacks at "
            "the wire. The class operator §1g compares with 'a full "
            "IPS' the edge Sharevdi mini PC cannot provide."
        ),
        "operator_named_use": (
            "When the operator's edge firewall is the fanless+cheap "
            "Sharevdi mini PC (no IPS capability per §1g hardware "
            "limitations) AND the operator accepts the performance "
            "price for full IPS coverage on the workstation itself."
        ),
        "install_summary": (
            "apt install suricata suricata-update; pull ET-Open ruleset; "
            "configure interface(s) for inline or sniffer mode"
        ),
        "apt_packages": ["suricata", "suricata-update"],
        "systemd_units": ["suricata.service"],
        "config_paths": ["/etc/suricata/suricata.yaml",
                          "/etc/suricata/rules/"],
    },
]

KNOWN_CANDIDATE_IDS = [c["id"] for c in CANDIDATES]


def _emit_metric(name: str, verb: str, candidate: str, result: str) -> None:
    """Best-effort SDD-016 metric write; never raises."""
    if DRY_RUN:
        sys.stderr.write(
            f"  would emit: {name}"
            f"{{verb=\"{verb}\",candidate=\"{candidate}\",result=\"{result}\"}} 1\n"
        )
        return
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        prom = METRICS_DIR / "sovereign-os-operator-edge-firewall.prom"
        line = (
            f'{name}'
            f'{{verb="{verb}",candidate="{candidate}",result="{result}"}} 1\n'
        )
        tmp = prom.with_suffix(".prom.tmp")
        tmp.write_text(line)
        tmp.replace(prom)
    except OSError:
        pass


# -------------------- detection primitives --------------------


def _which(binary: str) -> str | None:
    """Find a binary on PATH; never raises."""
    p = shutil.which(binary)
    return p


def _systemctl_state(unit: str) -> str:
    """Best-effort systemctl is-active; returns 'unavailable' if no
    systemctl. Never raises."""
    if not _which("systemctl"):
        return "no-systemctl"
    try:
        r = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True, text=True, timeout=2,
        )
        out = (r.stdout or r.stderr or "").strip()
        return out or "unknown"
    except (subprocess.SubprocessError, OSError):
        return "probe-failed"


def detect_local_state() -> dict:
    """What edge-firewall-class tools are installed/active locally."""
    out = {}
    for c in CANDIDATES:
        # Each candidate has a primary binary check
        primary_binary = {
            "nftables-baseline": "nft",
            "fail2ban": "fail2ban-client",
            "crowdsec": "cscli",
            "suricata": "suricata",
        }.get(c["id"])
        installed = primary_binary is not None and _which(primary_binary) is not None
        units_state = {}
        for unit in c.get("systemd_units") or []:
            units_state[unit] = _systemctl_state(unit)
        out[c["id"]] = {
            "installed": installed,
            "primary_binary": primary_binary,
            "primary_binary_path": _which(primary_binary) if primary_binary else None,
            "units": units_state,
            "any_unit_active": any(
                v == "active" for v in units_state.values()
            ),
        }
    return out


def detect_upstream_state() -> dict:
    """Shell out to R449 (network-edge) to get upstream state."""
    if not NETWORK_EDGE_PY.is_file():
        return {"available": False, "reason": "R449 script missing"}
    try:
        r = subprocess.run(
            ["python3", str(NETWORK_EDGE_PY), "opnsense", "status",
             "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return {"available": False, "reason": f"R449 rc={r.returncode}"}
        upstream = json.loads(r.stdout or "{}")
        return {
            "available": True,
            "tier": upstream.get("tier", "unknown"),
            "host": upstream.get("host"),
        }
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        return {"available": False, "reason": "R449 probe failed"}


# -------------------- recommendation logic --------------------


def recommend_for_state(local: dict, upstream: dict) -> list[dict]:
    """Operator-discoverable recommendation: given current local state +
    upstream state, what should the operator install (or what's missing)?

    Returns ordered list (highest-priority first)."""
    recs = []

    upstream_tier = (upstream or {}).get("tier", "absent")
    upstream_present = upstream_tier in (
        "reachable-no-credentials", "reachable-credentials-rejected",
        "full-api"
    )

    # ALWAYS recommend nftables baseline if not installed
    if not local.get("nftables-baseline", {}).get("installed"):
        recs.append({
            "candidate": "nftables-baseline",
            "priority": 1,
            "rationale": (
                "Always recommended. Kernel-native stateful firewall; "
                "negligible performance cost. Even if edge firewall "
                "is present upstream, nftables is defense-in-depth "
                "against LAN-side lateral movement."
            ),
            "operator_decision": "install",
        })

    # Recommend fail2ban if SSH is exposed (heuristic: sshd unit active)
    sshd_state = _systemctl_state("sshd") if _which("systemctl") else "?"
    if not local.get("fail2ban", {}).get("installed") and (
        sshd_state == "active" or sshd_state == "?"
    ):
        recs.append({
            "candidate": "fail2ban",
            "priority": 2,
            "rationale": (
                "SSH is (or likely is) active. fail2ban gives cheap "
                "insurance against brute-force. ~50 MB RAM cost."
            ),
            "operator_decision": "install",
        })

    # Recommend crowdsec if any dashboards expected to expose
    # (heuristic — operator-overridable; we surface the recommendation
    # without enforcing)
    if not local.get("crowdsec", {}).get("installed"):
        recs.append({
            "candidate": "crowdsec",
            "priority": 3,
            "rationale": (
                "Recommended once any sovereign-os dashboard is exposed "
                "beyond loopback. Community-curated IP reputation gives "
                "proactive defense; moderate cost (~200-400 MB RAM)."
            ),
            "operator_decision": "evaluate",
        })

    # Suricata: recommend ONLY when upstream is the §1g 'fanless+cheap'
    # tier (no full IPS upstream) AND operator has indicated willingness
    # to pay performance price (we surface the option; never auto-install)
    if not local.get("suricata", {}).get("installed"):
        # The operator's edge per §1g is the Sharevdi mini PC — a tier
        # that LACKS full IPS. So if upstream is at any tier (even
        # full-api OPNsense API), we still surface suricata as "the
        # full-IPS option" — the operator explicitly said §1g that
        # the edge "is not a full IPS".
        priority = 4
        rationale_parts = []
        if upstream_tier == "absent":
            priority = 3  # bump up if NO upstream edge at all
            rationale_parts.append(
                "No upstream edge firewall detected — suricata fills "
                "the IPS gap."
            )
        else:
            rationale_parts.append(
                "Upstream edge present but operator §1g named it 'not a "
                "full IPS' (Sharevdi mini PC class). suricata adds full "
                "IPS coverage on the workstation."
            )
        rationale_parts.append(
            "Performance price (§1g): ~1-2 CPU cores + 1-2 GB RAM; "
            "operator-discoverable trade-off."
        )
        recs.append({
            "candidate": "suricata",
            "priority": priority,
            "rationale": " ".join(rationale_parts),
            "operator_decision": "evaluate-perf-cost",
        })

    # Sort by priority (low number = higher priority)
    recs.sort(key=lambda r: r["priority"])
    return recs


# -------------------- CLI verbs --------------------


def cmd_state(args) -> int:
    local = detect_local_state()
    upstream = detect_upstream_state()
    out = {
        "local": local,
        "upstream": upstream,
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── edge-firewall.state ──")
        print(f"  Upstream tier (via R449): {upstream.get('tier', '?')}")
        print(f"  Local candidates:")
        for cid, info in local.items():
            active = "✓ active" if info.get("any_unit_active") else (
                "installed (inactive)" if info.get("installed") else "absent"
            )
            print(f"    {cid:<22} {active}")
    _emit_metric(
        "sovereign_os_operator_edge_firewall_query_total",
        "state", "all", "ok",
    )
    return 0


def cmd_candidates(args) -> int:
    if args.fmt == "json":
        print(json.dumps({"candidates": CANDIDATES}, indent=2))
    else:
        print(f"── edge-firewall.candidates ({len(CANDIDATES)} options, "
              f"low → high overhead) ──")
        for c in CANDIDATES:
            print(f"  {c['level']}  {c['id']:<22} {c['label']}")
            print(f"     perf cost: {c['perf_cost']}")
            print(f"     threat model: {c['threat_model'][:80]}...")
    _emit_metric(
        "sovereign_os_operator_edge_firewall_query_total",
        "candidates", "all", "ok",
    )
    return 0


def cmd_recommend(args) -> int:
    local = detect_local_state()
    upstream = detect_upstream_state()
    recs = recommend_for_state(local, upstream)
    out = {
        "upstream_tier": upstream.get("tier", "unknown"),
        "recommendations": recs,
        "count": len(recs),
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── edge-firewall.recommend (upstream={upstream.get('tier', '?')}) ──")
        if not recs:
            print("  (all candidates already installed; no actions)")
        for r in recs:
            print(f"  [P{r['priority']}] {r['candidate']:<22} → {r['operator_decision']}")
            print(f"     {r['rationale']}")
    _emit_metric(
        "sovereign_os_operator_edge_firewall_query_total",
        "recommend", "all", "ok",
    )
    return 0


def _candidate(cid: str) -> dict | None:
    for c in CANDIDATES:
        if c["id"] == cid:
            return c
    return None


def cmd_install_plan(args) -> int:
    cand = _candidate(args.candidate)
    if cand is None:
        sys.stderr.write(
            f"unknown candidate: {args.candidate!r}\n"
            f"known: {', '.join(KNOWN_CANDIDATE_IDS)}\n"
        )
        _emit_metric(
            "sovereign_os_operator_edge_firewall_query_total",
            "install_plan", args.candidate, "unknown-candidate",
        )
        return 1
    plan = {
        "candidate": cand["id"],
        "label": cand["label"],
        "perf_cost_disclosed": cand["perf_cost"],
        "apt_packages": cand["apt_packages"],
        "systemd_units": cand["systemd_units"],
        "config_paths_touched": cand["config_paths"],
        "install_steps": [
            f"apt-get update",
            f"apt-get install -y {' '.join(cand['apt_packages'])}",
            *[f"systemctl enable {u}" for u in cand["systemd_units"]],
            *[f"systemctl start {u}" for u in cand["systemd_units"]],
        ],
        "rollback_steps": [
            *[f"systemctl stop {u}" for u in cand["systemd_units"]],
            *[f"systemctl disable {u}" for u in cand["systemd_units"]],
            f"apt-get remove -y {' '.join(cand['apt_packages'])}",
        ],
        "next_action": (
            f"Run: sovereign-osctl edge-firewall install {cand['id']} "
            f"--apply --confirm-install"
        ),
    }
    if args.fmt == "json":
        print(json.dumps(plan, indent=2))
    else:
        print(f"── edge-firewall.install-plan {cand['id']} ──")
        print(f"  perf cost: {cand['perf_cost']}")
        print(f"  apt: {' '.join(cand['apt_packages'])}")
        print(f"  units: {', '.join(cand['systemd_units'])}")
        print(f"  install steps:")
        for s in plan["install_steps"]:
            print(f"    $ {s}")
        print(f"  next: {plan['next_action']}")
    _emit_metric(
        "sovereign_os_operator_edge_firewall_query_total",
        "install_plan", cand["id"], "ok",
    )
    return 0


def cmd_install(args) -> int:
    cand = _candidate(args.candidate)
    if cand is None:
        sys.stderr.write(
            f"unknown candidate: {args.candidate!r}\n"
        )
        _emit_metric(
            "sovereign_os_operator_edge_firewall_query_total",
            "install", args.candidate, "unknown-candidate",
        )
        return 1

    # Already installed → no-op (rc=3)
    local = detect_local_state()
    if local.get(cand["id"], {}).get("installed"):
        sys.stderr.write(
            f"{cand['id']} already installed; no-op\n"
        )
        _emit_metric(
            "sovereign_os_operator_edge_firewall_query_total",
            "install", cand["id"], "already-installed",
        )
        return 3

    # Triple-gate: --apply + --confirm-install
    if not args.apply or not args.confirm_install:
        plan = {
            "candidate": cand["id"],
            "preview": True,
            "perf_cost": cand["perf_cost"],
            "next_action": (
                "Re-run with --apply --confirm-install to commit. "
                "Operator-named §1g performance-price disclosure required."
            ),
        }
        if args.fmt == "json":
            print(json.dumps(plan, indent=2))
        else:
            print(f"── edge-firewall.install PREVIEW {cand['id']} ──")
            print(f"  perf cost (§1g disclosure): {cand['perf_cost']}")
            print(f"  next: --apply --confirm-install to commit")
        _emit_metric(
            "sovereign_os_operator_edge_firewall_query_total",
            "install", cand["id"], "preview",
        )
        return 0

    if DRY_RUN:
        sys.stderr.write(
            f"DRY-RUN — would apt install {' '.join(cand['apt_packages'])} + "
            f"enable {', '.join(cand['systemd_units'])}\n"
        )
        _emit_metric(
            "sovereign_os_operator_edge_firewall_query_total",
            "install", cand["id"], "dry-run",
        )
        return 0

    # Real install (apt + systemctl)
    if os.geteuid() != 0:
        sys.stderr.write(
            "install requires root; re-run with sudo\n"
        )
        _emit_metric(
            "sovereign_os_operator_edge_firewall_query_total",
            "install", cand["id"], "needs-root",
        )
        return 2

    for step in [
        ["apt-get", "update"],
        ["apt-get", "install", "-y", *cand["apt_packages"]],
        *[["systemctl", "enable", u] for u in cand["systemd_units"]],
        *[["systemctl", "start", u] for u in cand["systemd_units"]],
    ]:
        sys.stderr.write(f"  $ {' '.join(step)}\n")
        try:
            r = subprocess.run(step, timeout=300)
            if r.returncode != 0:
                sys.stderr.write(
                    f"step failed (rc={r.returncode}): {' '.join(step)}\n"
                )
                _emit_metric(
                    "sovereign_os_operator_edge_firewall_query_total",
                    "install", cand["id"], "step-failed",
                )
                return 2
        except (subprocess.SubprocessError, OSError) as e:
            sys.stderr.write(f"step error: {e}\n")
            _emit_metric(
                "sovereign_os_operator_edge_firewall_query_total",
                "install", cand["id"], "step-error",
            )
            return 2

    print(f"  installed {cand['id']} (units: {', '.join(cand['systemd_units'])})")
    _emit_metric(
        "sovereign_os_operator_edge_firewall_query_total",
        "install", cand["id"], "applied",
    )
    return 0


def _wizard_clear():
    """ANSI clear-screen + cursor-home. The TUI-surface affordance."""
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()


def _wizard_prompt(question: str, default: str, no_input: bool) -> str:
    """Operator prompt with default. In no-input mode (--accept-default or
    SOVEREIGN_OS_DRY_RUN=1) returns default without reading stdin."""
    if no_input:
        print(f"{question} [{default}] (auto: {default})")
        return default
    try:
        ans = input(f"{question} [{default}]: ").strip()
    except EOFError:
        ans = ""
    return ans or default


def cmd_wizard(args) -> int:
    """R482 (E11.M9+) — install-wizard TUI surface.

    Operator-§1g: surface-map waiver-slot 'tui: FUTURE — install-wizard
    TUI worthwhile' is closed by this verb. Four-page interactive walk:

      Page 1: detected state (local + upstream tier)
      Page 2: per-state recommendations (P1 / P2 priorities)
      Page 3: candidate-pick + install-plan preview (perf-cost
              disclosure per §1g 'pay the performance price')
      Page 4: triple-gate confirm — operator types 'install' verbatim
              to commit; anything else exits as a preview

    Non-interactive modes (for L3 / scripted operator use):
      --accept-default              auto-pick the top recommendation;
                                     never prompt; exit at page 3 preview
      SOVEREIGN_OS_DRY_RUN=1         exits after page 3 without prompts

    The triple-gate (--apply + --confirm-install + typed 'install') is
    enforced even in interactive mode — the wizard hands control to
    `cmd_install` for the actual apt+systemctl, never bypasses it.
    """
    no_input = (
        args.accept_default
        or os.environ.get("SOVEREIGN_OS_DRY_RUN", "") == "1"
        or not sys.stdin.isatty()
    )

    # Page 1: state
    _wizard_clear()
    print("── edge-firewall.wizard  PAGE 1/4: detected state ──\n")
    local = detect_local_state()
    upstream = detect_upstream_state()
    print(f"  Upstream tier (via R449 network-edge): "
          f"{upstream.get('tier', 'unknown')}")
    print(f"  Local candidates:")
    for cid, info in local.items():
        active = "✓ active" if info.get("any_unit_active") else (
            "installed (inactive)" if info.get("installed") else "absent"
        )
        print(f"    {cid:<22} {active}")
    print()
    _wizard_prompt("press Enter to continue", "", no_input)

    # Page 2: recommendations
    _wizard_clear()
    print("── edge-firewall.wizard  PAGE 2/4: recommendations ──\n")
    recs = recommend_for_state(local, upstream)
    if not recs:
        print("  (all candidates already installed; nothing to do)")
        _emit_metric(
            "sovereign_os_operator_edge_firewall_query_total",
            "wizard", "all", "no-recs",
        )
        return 0
    for r in recs:
        print(f"  [P{r['priority']}] {r['candidate']:<22} "
              f"→ {r['operator_decision']}")
        print(f"     {r['rationale']}\n")
    top = recs[0]["candidate"]
    print(f"  Default pick (highest priority): {top}")
    print()
    _wizard_prompt("press Enter to continue", "", no_input)

    # Page 3: candidate-pick + install-plan
    _wizard_clear()
    print("── edge-firewall.wizard  PAGE 3/4: candidate + install-plan ──\n")
    candidate = _wizard_prompt(
        f"pick candidate ({', '.join(KNOWN_CANDIDATE_IDS)})",
        top, no_input,
    )
    cand = _candidate(candidate)
    if cand is None:
        sys.stderr.write(f"unknown candidate: {candidate!r}\n")
        _emit_metric(
            "sovereign_os_operator_edge_firewall_query_total",
            "wizard", candidate, "unknown-candidate",
        )
        return 1
    print(f"\n  {cand['label']}")
    print(f"  perf cost (§1g disclosure): {cand['perf_cost']}")
    print(f"  apt: {' '.join(cand['apt_packages'])}")
    print(f"  units: {', '.join(cand['systemd_units'])}")
    print(f"  install steps:")
    for s in [
        f"apt-get update",
        f"apt-get install -y {' '.join(cand['apt_packages'])}",
        *[f"systemctl enable {u}" for u in cand['systemd_units']],
        *[f"systemctl start {u}" for u in cand['systemd_units']],
    ]:
        print(f"    $ {s}")
    print()
    _emit_metric(
        "sovereign_os_operator_edge_firewall_query_total",
        "wizard", cand["id"], "preview",
    )

    # Page 4: triple-gate confirm
    if no_input or DRY_RUN:
        print(f"  (no-input mode — wizard exits at preview; "
              f"to commit, run: sovereign-osctl edge-firewall install "
              f"{cand['id']} --apply --confirm-install)")
        return 0
    print("── edge-firewall.wizard  PAGE 4/4: confirm ──\n")
    print(f"  Type 'install' verbatim to commit; anything else exits.")
    confirm = _wizard_prompt("confirm", "abort", no_input=False)
    if confirm != "install":
        print(f"  → aborted (typed {confirm!r}); no changes made.")
        _emit_metric(
            "sovereign_os_operator_edge_firewall_query_total",
            "wizard", cand["id"], "aborted",
        )
        return 0

    # Hand off to cmd_install — never bypass the triple-gate.
    class _InstallArgs:
        pass
    install_args = _InstallArgs()
    install_args.candidate = cand["id"]
    install_args.apply = True
    install_args.confirm_install = True
    install_args.fmt = "human"
    rc = cmd_install(install_args)
    _emit_metric(
        "sovereign_os_operator_edge_firewall_query_total",
        "wizard", cand["id"], "applied" if rc == 0 else "install-rc-nonzero",
    )
    return rc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="edge-firewall.py",
        description=(
            "R451 (E11.M9) — workstation-side edge-firewall alternative "
            "(§1g 'install the equivalent or even more advanced on this "
            "machine if we would be ready to pay the performance price')"
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_fmt(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--json", dest="fmt", action="store_const",
                       const="json")
        g.add_argument("--human", dest="fmt", action="store_const",
                       const="human")
        sp.set_defaults(fmt="human")

    sp_state = sub.add_parser("state", help="local + upstream state")
    add_fmt(sp_state)

    sp_cand = sub.add_parser("candidates",
                              help="enumerate 4 install-class options")
    add_fmt(sp_cand)

    sp_rec = sub.add_parser("recommend",
                             help="operator-discoverable recommendation")
    add_fmt(sp_rec)

    sp_plan = sub.add_parser("install-plan",
                              help="render apt + systemctl steps")
    sp_plan.add_argument("candidate")
    add_fmt(sp_plan)

    sp_inst = sub.add_parser("install",
                              help="triple-gated installer")
    sp_inst.add_argument("candidate")
    sp_inst.add_argument("--apply", action="store_true")
    sp_inst.add_argument("--confirm-install", action="store_true")
    add_fmt(sp_inst)

    sp_wiz = sub.add_parser("wizard",
                             help="R482: install-wizard TUI surface")
    sp_wiz.add_argument("--accept-default", action="store_true",
                         help="auto-pick top recommendation; non-interactive")
    add_fmt(sp_wiz)

    args = p.parse_args(argv)
    if args.cmd == "state":
        return cmd_state(args)
    if args.cmd == "candidates":
        return cmd_candidates(args)
    if args.cmd == "recommend":
        return cmd_recommend(args)
    if args.cmd == "install-plan":
        return cmd_install_plan(args)
    if args.cmd == "install":
        return cmd_install(args)
    if args.cmd == "wizard":
        return cmd_wizard(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
