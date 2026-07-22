#!/usr/bin/env python3
"""_action_exec.py — shared privileged-action execution primitive (Phase 0).

Realizes **R10274** (the sanctioned "mutation proxies via an MS003-signed
request" path, until now implemented only as clipboard-copy) so cockpit panels
can *functionally execute* a control instead of only copying its command. The
manual `change_cli` stays the documented fallback.

**R10212 is preserved, not broken.** The web still never *arbitrarily* mutates:
this primitive executes ONLY a control that is (1) present in
`config/control-systems.yaml`, (2) sovereign-os-OWNED (never selfdef-owned —
that boundary is a hard reject here), (3) called with placeholder values that
pass the control's own `options` allowlist / a strict regex, (4) for a
`privileged` control, accompanied by an operator-key presence + an explicit
confirmation.

Generalizes the one existing HTTP→privileged primitive
(`build-configurator-api.py` `_run_action()` / `RUN_ACTIONS`): fixed allowlist +
validated args + single-flight lock + operator-key injection + streamed result.

**Sudoer strategy (mechanism A, operator-review-pending):** privileged verbs run
via `sudo -n` against the NOPASSWD allowlist in
`config/sudoers.d/sovereign-os-cockpit` (DRAFT — must be reviewed before any
daemon is wired and before the `*-api` systemd units drop `NoNewPrivileges=true`,
which currently blocks sudo). Until then this module DRY-RUNs by default and is
imported by nothing live. Execution mechanism is isolated in `_privileged_argv()`
so B (helper daemon) / C (pkexec) remain drop-in swaps.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTROL_SYSTEMS_FILE = _REPO_ROOT / "config" / "control-systems.yaml"

# ── The load-bearing R10212 boundary ────────────────────────────────────────
# sovereign-os is the CONSUMER of the selfdef IPS. Controls whose state is
# owned by selfdef / tetragon are NEVER executed locally — they remain a
# signed proxy request to the selfdef producer (the panel copies the signed
# change_cli). This set is derived from the two controls whose `state_path`
# names selfdef units / tetragon; it is asserted against the registry by the
# unit tests so a future registry edit can't silently widen local execution.
SELFDEF_OWNED: frozenset[str] = frozenset({"selfdef", "perimeter"})

# Non-interactive elevation binary (mechanism A). Overridable for tests.
SUDO = os.environ.get("SOVEREIGN_OS_SUDO", "sudo")

# Global default: never execute unless a caller explicitly opts in. Phase 0
# ships DRY_RUN on so importing this module changes no host state.
_DEFAULT_DRY_RUN = os.environ.get("SOVEREIGN_OS_ACTION_EXEC_LIVE") != "1"

# Single-flight: one privileged action at a time across the process.
_RUN_LOCK = threading.Lock()

# A strict token for free-value placeholders (<value>, <slug>, <dashboard>,
# <key> when not in options). Deliberately narrow — no whitespace, no shell
# metacharacters, no path traversal.
_SAFE_VALUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@=-]*")

# operator-key presence (MS003) — presence only, material never read.
_OPERATOR_KEY_PATH = Path(
    os.environ.get("SOVEREIGN_OS_OPERATOR_KEY",
                   str(Path.home() / ".sovereign-os" / "operator.key")))
_OPERATOR_KEY_STATUS = Path("/run/sovereign-os/operator-key-status.json")

# ── compat pre-change gate (2026-07-19 follow-on to the compat module) ──────
# Before a control mutates, the proposed change is overlaid on best-effort
# current state and evaluated against config/compatibility.yaml. A
# force-severity finding REFUSES with reason + remediation (the operator's
# "suggest or even force something else off in order to enable one thing"),
# override-able per call with args={"compat_override": "true"} (audited via
# the compat-override metric outcome). warn/suggest findings ride the result.
# SOVEREIGN_OS_COMPAT_GATE=off disables; an unreadable compat registry
# degrades OPEN (the rail must not die with the gate).


def _notify_compat_reject(control_id: str, finding: dict[str, Any]) -> None:
    """A compat-gate REFUSAL emits through the notifykit channel stack when
    a config exists — the `compat-gate` trigger, so the operator can set
    frontmatter props on it (e.g. `sovereign-osctl notifykit trigger
    compat-gate important true`). Mirrors approval-decide's stage-gate
    trigger; notification must NEVER break the gate path."""
    cfg_path = os.environ.get(
        "SOVEREIGN_OS_NOTIFYKIT_CONFIG", "/etc/sovereign-os/notifykit.toml")
    if not os.path.isfile(cfg_path):
        return
    try:
        repo_root = Path(__file__).resolve().parents[2]
        import sys as _sys
        if str(repo_root) not in _sys.path:
            _sys.path.insert(0, str(repo_root))
        from tools.notifykit import ChannelRegistry, Event, NotifyConfig
        registry = ChannelRegistry(NotifyConfig.load(cfg_path))
        registry.dispatch(Event(
            title=f"compat-gate refused {control_id}: {finding['rule_id']}",
            message=(f"{finding['reason']} INSTEAD: {finding['remediation']}"),
            priority="high", urgency="normal",
            source="compat-gate",
        ))
    except Exception:  # noqa: BLE001 — never mask the gate result
        pass


def _compat_pre_change(control: dict, control_id: str,
                       args: dict[str, str]) -> dict[str, Any] | None:
    """Compat findings for this action, or None when the gate is off /
    unavailable / the proposed option cannot be derived. Never raises."""
    if os.environ.get("SOVEREIGN_OS_COMPAT_GATE", "on").lower() in ("off", "0"):
        return None
    try:
        import sys as _sys
        _here = str(Path(__file__).resolve().parent)
        if _here not in _sys.path:
            _sys.path.insert(0, _here)
        import compat  # scripts/operator/compat.py — same directory
    except Exception:  # noqa: BLE001 — gate degrades open, rail survives
        return None
    options = {str(o).lower() if isinstance(o, bool) else str(o)
               for o in (control.get("options") or [])}
    proposed_opt = next(
        (str(v) for v in args.values() if str(v) in options), None)
    if proposed_opt is None:
        # Toggle CLIs verb differently from their state options
        # (`dspark {enable|disable}` flips options ["on","off"]).
        verb_map = {"enable": "on", "disable": "off"}
        proposed_opt = next(
            (verb_map[str(v)] for v in args.values()
             if str(v) in verb_map and verb_map[str(v)] in options), None)
    try:
        res = compat.pre_change({control_id: proposed_opt})
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(res, dict) or not res.get("available"):
        return None
    if not res.get("findings"):
        return None
    return res


# ── registry ────────────────────────────────────────────────────────────────

def load_registry() -> dict[str, dict]:
    """control_id → control dict, from config/control-systems.yaml.
    Degrades to {} (never raises) when PyYAML or the file is unavailable."""
    try:
        import yaml  # PyYAML — declared prerequisite; optional at runtime
    except ImportError:
        return {}
    try:
        doc = yaml.safe_load(_CONTROL_SYSTEMS_FILE.read_text())
    except OSError:
        return {}
    return {s["id"]: s for s in (doc or {}).get("systems", []) if s.get("id")}


def operator_key_loaded() -> bool:
    """MS003 operator-key PRESENCE (never reads material). Env-injected key or
    a published status JSON or the key file existing all count as loaded."""
    if os.environ.get("SOVEREIGN_OS_MOK_KEY") or os.environ.get("SOVEREIGN_OS_PK_KEY"):
        return True
    try:
        if _OPERATOR_KEY_STATUS.is_file():
            st = json.loads(_OPERATOR_KEY_STATUS.read_text())
            if st.get("fingerprint") or st.get("loaded"):
                return True
    except (OSError, ValueError):
        pass
    return _OPERATOR_KEY_PATH.is_file()


# ── placeholder parsing + validation ────────────────────────────────────────

def _tokens(change_cli: str) -> list[str]:
    return change_cli.split()


def _placeholder_kind(tok: str) -> tuple[str, Any]:
    """('enum', {a,b}) for {a|b}; ('free', name) for <name>; ('lit', tok) else."""
    m = re.fullmatch(r"\{([a-z0-9|_-]+)\}", tok)
    if m:
        return "enum", set(m.group(1).split("|"))
    m = re.fullmatch(r"<([a-z0-9_-]+)>", tok)
    if m:
        return "free", m.group(1)
    return "lit", tok


def resolve_argv(control: dict, args: dict[str, str]) -> tuple[list[str] | None, str | None]:
    """Build the concrete argv for a control's change_cli by substituting +
    validating `args` (placeholder-name → value). Returns (argv, None) on
    success or (None, reason) on a validation failure.

    Enum placeholders ({on|off}) must match one alternative; the FIRST enum
    placeholder is keyed by the literal 'verb' (e.g. args={'verb':'on'}).
    Free placeholders (<id>, <mode>, <slug>, <key>, <value>, ...) are keyed by
    their name; a value is accepted if it is in the control's `options` list OR
    (for genuinely free values) matches the strict _SAFE_VALUE token.
    """
    change_cli = control.get("change_cli", "")
    if not change_cli:
        return None, "control has no change_cli"
    options = set(map(str, control.get("options", []) or []))
    out: list[str] = []
    enum_seen = 0
    for tok in _tokens(change_cli):
        kind, spec = _placeholder_kind(tok)
        if kind == "lit":
            out.append(tok)
            continue
        if kind == "enum":
            key = "verb" if enum_seen == 0 else f"verb{enum_seen}"
            enum_seen += 1
            val = str(args.get(key, "")).strip()
            if val not in spec:
                return None, f"{key}={val!r} not in {sorted(spec)}"
            out.append(val)
            continue
        # free placeholder <name>
        name = spec
        val = str(args.get(name, "")).strip()
        if not val:
            return None, f"missing value for <{name}>"
        if val in options:
            out.append(val)
            continue
        if _SAFE_VALUE.fullmatch(val):
            out.append(val)
            continue
        return None, f"<{name}>={val!r} rejected (not an option and not a safe token)"
    return out, None


# ── execution ────────────────────────────────────────────────────────────────

def _privileged_argv(argv: list[str], privileged: bool) -> list[str]:
    """Mechanism A: wrap privileged argv in `sudo -n` when we are not already
    root. Non-privileged controls run directly. (Mechanism B/C swap here.)"""
    if privileged and os.geteuid() != 0:
        return [SUDO, "-n", *argv]
    return argv


_METRIC_NAME = "sovereign_os_operator_cockpit_action_total"


def _emit_metric(control_id: str, outcome: str) -> None:
    """Best-effort Prometheus counter to the node_exporter textfile collector so
    the operator has observability into cockpit action attempts + rejects
    (outcome ∈ executed / dry-run / boundary-reject / validation-reject /
    compat-reject / compat-override / confirm-required / key-missing / busy /
    error / unknown-control). Reads
    SOVEREIGN_OS_METRICS_DIR at call time; never raises."""
    metrics_dir = os.environ.get(
        "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector")
    try:
        os.makedirs(metrics_dir, exist_ok=True)
        with open(os.path.join(metrics_dir, "sovereign-os-cockpit-action-exec.prom"), "a") as f:
            f.write(f'{_METRIC_NAME}{{control_id="{control_id}",outcome="{outcome}"}} 1\n')
    except OSError:
        pass


def _emit_audit(control_id: str, argv: list[str], exit_code: int | None,
                actor: str, dry_run: bool) -> None:
    """Best-effort OCSF-5001 (Configuration Change) audit span into the SAME
    M049 span log the D-05 traces + D-16 audit dashboards read
    (SOVEREIGN_OS_SPAN_STORE), in the canonical span schema used by
    scripts/manifest/dashboard-toggles.py — so cockpit-executed actions appear
    in the existing audit pipeline, not a sidecar log. Never raises."""
    if dry_run:
        return
    span_log = Path(os.environ.get(
        "SOVEREIGN_OS_SPAN_STORE", "/var/log/sovereign-os/spans.jsonl"))
    now = datetime.now(tz=timezone.utc)
    ms = int(time.time() * 1000)
    span = {
        "trace_id": f"cockpit-action-{ms:x}",
        "span_id": f"ca-{control_id}-{ms:x}",
        "parent_span_id": None,
        "operation": "cockpit_action",
        "start_ts": now.isoformat(),
        "duration_ms": 0,
        "severity": "info" if exit_code == 0 else "error",
        "actor": actor,
        "profile": os.environ.get("SOVEREIGN_OS_ACTIVE_PROFILE", "private"),
        "ocsf_class": "5001",
        "ocsf_payload": {"class_uid": 5001, "activity": "Update",
                         "control_id": control_id, "argv": argv,
                         "exit_code": exit_code,
                         "status": "r10274-signed-execute"},
        "attributes": {"control_id": control_id, "exit_code": exit_code},
        "schema_version": "1.0.0",
    }
    try:
        span_log.parent.mkdir(parents=True, exist_ok=True)
        with span_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(span) + "\n")
    except OSError:
        pass


# ── SDD-509 step-up MFA integration (opt-in; the pure logic lives in
#    lib/stepup.py). The step-up dir holds the enrolled TOTP secret + the
#    elevation ledger; overridable via SOVEREIGN_OS_STEPUP_DIR for tests. Its
#    intended home is a root-owned dir behind a verifier process. ──
_STEPUP_MOD: Any = None


def _stepup():
    """Lazily load lib/stepup.py (cached) without sys.path games."""
    global _STEPUP_MOD
    if _STEPUP_MOD is None:
        import importlib.util
        p = Path(__file__).resolve().parent / "lib" / "stepup.py"
        spec = importlib.util.spec_from_file_location("_action_exec_stepup", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _STEPUP_MOD = mod
    return _STEPUP_MOD


def _stepup_dir() -> Path:
    return Path(os.environ.get("SOVEREIGN_OS_STEPUP_DIR", "/run/sovereign-os/stepup"))


def _stepup_enabled() -> bool:
    """Step-up engages only once a factor is enrolled (a TOTP secret exists).
    Un-enrolled → the gate is a no-op and the rail behaves exactly as before."""
    try:
        return _stepup().is_enrolled(_stepup_dir())
    except Exception:  # never let a step-up fault break the exec rail
        return False


def _stepup_tier(control: dict) -> str:
    return _stepup().resolve_tier(control)


def _stepup_consume(actor: str) -> bool:
    su = _stepup()
    store = su.ElevationStore(_stepup_dir() / "elevations.json")
    return store.consume(actor, "step-up")


def _stepup_notify_config() -> Path:
    return Path(os.environ.get(
        "SOVEREIGN_OS_NOTIFYKIT_CONFIG", _REPO_ROOT / "config" / "notifykit.toml"))


def _stepup_factors() -> list[str]:
    """The factors currently available to satisfy a step-up (for the 401
    challenge): TOTP once enrolled (Phase A), plus any configured + enabled
    notifykit out-of-band channels — ``sms`` / ``email`` (Phase B)."""
    factors = ["totp"] if _stepup_enabled() else []
    try:
        factors += _stepup().available_otp_channels(_stepup_notify_config())
    except Exception:
        pass
    return factors


def execute(control_id: str, args: dict[str, str] | None = None, *,
            confirm: bool = False, actor: str = "operator",
            dry_run: bool | None = None, timeout: float = 30.0) -> dict[str, Any]:
    """Validate + (optionally) execute a control action. Returns a structured
    result. `dry_run` defaults to Phase-0-safe (execute only when the process
    opted in via SOVEREIGN_OS_ACTION_EXEC_LIVE=1 or an explicit dry_run=False).

    Result shape: {ok, code, control_id, argv, dry_run, ...} — `code` mirrors
    the HTTP status a daemon would return (200/400/403/404/409).
    """
    args = args or {}
    if dry_run is None:
        dry_run = _DEFAULT_DRY_RUN
    reg = load_registry()
    control = reg.get(control_id)
    if control is None:
        _emit_metric(control_id, "unknown-control")
        return {"ok": False, "code": 404, "control_id": control_id,
                "error": f"unknown control {control_id!r}",
                "known": sorted(reg)}

    # ── hard R10212 boundary — selfdef-owned NEVER executes locally ──
    if control_id in SELFDEF_OWNED:
        argv, _ = resolve_argv(control, args)
        _emit_metric(control_id, "boundary-reject")
        return {
            "ok": False, "code": 409, "boundary": True, "control_id": control_id,
            "error": ("selfdef-owned control — sovereign-os is the READ-ONLY "
                      "consumer (R10212). Copy the signed verb; mutation is an "
                      "MS003-signed proxy request to the selfdef producer, never "
                      "executed locally."),
            "proxy_cli": " ".join(argv) if argv else control.get("change_cli"),
        }

    argv, err = resolve_argv(control, args)
    if err:
        _emit_metric(control_id, "validation-reject")
        return {"ok": False, "code": 400, "control_id": control_id, "error": err,
                "options": control.get("options")}

    # ── compat pre-change gate — force findings refuse (with reason +
    #    remediation + audited override); warn/suggest ride the result ──
    compat_res = _compat_pre_change(control, control_id, args)
    if compat_res is not None and compat_res.get("gating"):
        override = str(args.get("compat_override", "")).lower() in ("1", "true", "yes")
        if not override:
            first = next(f for f in compat_res["findings"]
                         if f["severity"] == "force")
            _emit_metric(control_id, "compat-reject")
            _notify_compat_reject(control_id, first)
            # The RESOLUTION plan — "force something else off in order to
            # enable one thing": the verified steps (each an exec-rail call)
            # that would clear what this change introduces. Best-effort.
            resolution = None
            try:
                import compat as _compat_mod
                r = _compat_mod.resolve(compat_res.get("proposed") or {})
                if r.get("available") and r.get("plan"):
                    resolution = {"plan": r["plan"],
                                  "clean_after": r["clean_after"],
                                  "resolved_all": r["resolved_all"]}
            except Exception:  # noqa: BLE001 — the plan is advisory
                pass
            return {
                "ok": False, "code": 409, "control_id": control_id,
                "compat": compat_res,
                "resolution": resolution,
                "error": (f"compat gate: {first['rule_id']} ({first['verb']}) — "
                          f"{first['reason']}"),
                "remediation": first["remediation"],
                "override": "pass args={'compat_override': 'true'} to proceed "
                            "anyway (audited)",
            }
        _emit_metric(control_id, "compat-override")

    privileged = bool(control.get("privileged"))
    if privileged:
        if not operator_key_loaded():
            _emit_metric(control_id, "key-missing")
            return {"ok": False, "code": 403, "control_id": control_id,
                    "error": "privileged control requires the operator key to be "
                             "loaded (MS003 presence gate)"}
        if not confirm:
            _emit_metric(control_id, "confirm-required")
            return {"ok": False, "code": 403, "control_id": control_id,
                    "confirm_required": True, "argv": argv,
                    "error": "privileged control requires explicit confirm=true "
                             "(type-to-confirm on the panel)"}

    run_argv = _privileged_argv(argv, privileged)
    if dry_run:
        _emit_metric(control_id, "dry-run")
        result = {"ok": True, "code": 200, "control_id": control_id,
                  "dry_run": True, "argv": argv, "would_run": run_argv}
        if compat_res is not None:
            result["compat"] = compat_res
        return result

    # ── SDD-509 step-up gate — a `step-up`-tier control needs a live elevation
    #    (minted by a verified factor, e.g. TOTP), consumed single-use on real
    #    execution. OPT-IN + non-breaking: engages ONLY once a factor is
    #    enrolled (an un-enrolled box behaves exactly as before). Checked here,
    #    AFTER the dry-run return, so a preview never burns an elevation. ──
    if _stepup_enabled() and _stepup_tier(control) == "step-up":
        if not _stepup_consume(actor):
            _emit_metric(control_id, "step-up-required")
            return {"ok": False, "code": 401, "control_id": control_id,
                    "step_up_required": True, "tier": "step-up",
                    "error": ("step-up required — verify a factor (TOTP) to "
                              "elevate this high-privilege operation"),
                    "factors": _stepup_factors()}

    if not _RUN_LOCK.acquire(blocking=False):
        _emit_metric(control_id, "busy")
        return {"ok": False, "code": 409, "control_id": control_id,
                "error": "another cockpit action is already running"}
    try:
        proc = subprocess.run(run_argv, cwd=_REPO_ROOT, capture_output=True,
                              text=True, timeout=timeout, check=False)
        _emit_audit(control_id, argv, proc.returncode, actor, dry_run=False)
        _emit_metric(control_id, "executed" if proc.returncode == 0 else "error")
        result = {"ok": proc.returncode == 0,
                  "code": 200 if proc.returncode == 0 else 500,
                  "control_id": control_id, "argv": argv, "dry_run": False,
                  "exit_code": proc.returncode,
                  "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:]}
        if compat_res is not None:
            result["compat"] = compat_res
        return result
    except subprocess.TimeoutExpired:
        _emit_metric(control_id, "error")
        return {"ok": False, "code": 504, "control_id": control_id, "argv": argv,
                "error": f"action timed out after {timeout}s"}
    except OSError as e:
        _emit_metric(control_id, "error")
        return {"ok": False, "code": 500, "control_id": control_id, "argv": argv,
                "error": f"exec failed: {e}"}
    finally:
        _RUN_LOCK.release()


def owned_controls() -> dict[str, list[str]]:
    """{'local': [sovereign-os-owned ids], 'proxy': [selfdef-owned ids]} — the
    execution classification, for daemons/tests + the self-check."""
    reg = load_registry()
    local, proxy = [], []
    for cid in sorted(reg):
        (proxy if cid in SELFDEF_OWNED else local).append(cid)
    return {"local": local, "proxy": proxy}


# ── CLI self-check / dry-run harness ─────────────────────────────────────────

def _main(argv: list[str]) -> int:
    import argparse
    p = argparse.ArgumentParser(description="cockpit action-exec (Phase 0)")
    p.add_argument("--self-check", action="store_true")
    p.add_argument("--control")
    p.add_argument("--arg", action="append", default=[],
                   help="key=value placeholder (repeatable)")
    p.add_argument("--confirm", action="store_true")
    ns = p.parse_args(argv)
    if ns.self_check or not ns.control:
        reg = load_registry()
        print(json.dumps({
            "registry_loaded": bool(reg), "control_count": len(reg),
            "classification": owned_controls(),
            "operator_key_loaded": operator_key_loaded(),
            "default_dry_run": _DEFAULT_DRY_RUN,
        }, indent=2))
        return 0
    args = dict(kv.split("=", 1) for kv in ns.arg if "=" in kv)
    print(json.dumps(execute(ns.control, args, confirm=ns.confirm, dry_run=True),
                     indent=2))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv[1:]))
