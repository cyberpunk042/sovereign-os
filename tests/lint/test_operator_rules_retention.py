"""operator-rules — retain + re-apply the operator's Claude Code interaction
rules across a fresh flash.

The operator's behaviour rules (operator-is-the-driver, words-sacrosanct,
do-not-minimize, ask-when-unclear, no-random-side-quests, mid-work-messages-
are-interrupts, …) live in Claude Code per-project memory that a fresh flash
would wipe. sovereign-os versions them in ``assets/operator-memory/`` and
re-applies them on provision so the OS RETAINS them — with NO dependency on
root-modules.

These locks prove: the store is populated; a simulated fresh flash re-applies
every rule + MEMORY.md; re-apply is idempotent; capture round-trips; the
cross-module boundary vs root-modules holds (disjoint paths, collision
detected); and provision.sh wires both the always-on rules apply and the
opt-out, proxy-free root-modules endpoint install.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STORE = REPO / "assets" / "operator-memory"
MODULE = REPO / "scripts" / "operator" / "operator-rules.py"
OSCTL = REPO / "scripts" / "sovereign-osctl"
PROVISION = REPO / "scripts" / "install" / "provision.sh"

# The interaction rules that MUST ride along to a fresh flash (the operator's
# core discipline). first-image-build-status / single-os-pivot are project
# state that also ride ("all of them, no filtering") but these are the
# non-negotiable behaviour rules.
REQUIRED_RULES = {
    "operator-is-always-the-driver.md",
    "operator-words-are-sacrosanct.md",
    "do-not-minimize.md",
    "ask-questions-when-unclear.md",
    "no-random-side-quests.md",
    "clarify-dont-compensate.md",
    "drive-the-direction-with-momentum.md",
    "mid-work-messages-are-interrupts.md",
    "MEMORY.md",
}


def _run(args, env_extra=None, cwd=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(MODULE), *args],
        capture_output=True, text=True, timeout=30, env=env, cwd=cwd,
    )


def test_module_present_and_executable():
    assert MODULE.is_file(), f"missing {MODULE}"
    assert os.access(MODULE, os.X_OK), f"{MODULE} not executable"


def test_store_present_and_carries_the_rules():
    assert STORE.is_dir(), f"missing versioned store {STORE}"
    names = {p.name for p in STORE.glob("*.md")}
    missing = sorted(REQUIRED_RULES - names)
    assert not missing, (
        f"versioned rules store is missing required rule files: {missing}"
    )


def test_every_store_rule_is_substantive():
    """No empty / stub rule files ride to a fresh flash."""
    for p in STORE.glob("*.md"):
        assert len(p.read_text(encoding="utf-8").strip()) >= 40, (
            f"store rule {p.name} is too short/empty to be a real rule"
        )


def test_fresh_flash_reapplies_every_rule(tmp_path):
    """Simulate a fresh flash: empty per-project memory dir → apply → every
    versioned rule (incl MEMORY.md) lands with identical content."""
    fresh = tmp_path / "projects" / "-x" / "memory"
    r = _run(["apply"], {"SOVEREIGN_OS_CLAUDE_MEMORY_DIR": str(fresh)})
    assert r.returncode == 0, f"apply failed: {r.stderr}"
    applied = {p.name for p in fresh.glob("*.md")}
    store_names = {p.name for p in STORE.glob("*.md")}
    assert applied == store_names, (
        f"fresh-flash apply did not reproduce the store: "
        f"missing={sorted(store_names - applied)} extra={sorted(applied - store_names)}"
    )
    # content identical (byte-for-byte)
    for p in STORE.glob("*.md"):
        assert (fresh / p.name).read_bytes() == p.read_bytes(), (
            f"{p.name} content differs after apply"
        )
    assert (fresh / "MEMORY.md").is_file(), "MEMORY.md not re-applied"


def test_reapply_is_idempotent(tmp_path):
    fresh = tmp_path / "memory"
    env = {"SOVEREIGN_OS_CLAUDE_MEMORY_DIR": str(fresh)}
    assert _run(["apply"], env).returncode == 0
    second = _run(["apply"], env)
    assert second.returncode == 0
    assert "0 file(s) changed" in second.stdout, (
        f"second apply was not a no-op:\n{second.stdout}"
    )


def test_capture_round_trips(tmp_path):
    """capture versions a new live rule back into the store (so operator edits
    survive the next flash). Uses an isolated temp store so the repo is not
    mutated by the test."""
    store = tmp_path / "store"
    store.mkdir()
    (store / "seed.md").write_text("# seed\n\nexisting rule body long enough.\n")
    live = tmp_path / "live"
    live.mkdir()
    (live / "seed.md").write_text("# seed\n\nexisting rule body long enough.\n")
    (live / "new-rule.md").write_text("# new\n\na freshly authored live rule.\n")
    env = {
        "SOVEREIGN_OS_OPERATOR_MEMORY_STORE": str(store),
        "SOVEREIGN_OS_CLAUDE_MEMORY_DIR": str(live),
    }
    r = _run(["capture"], env)
    assert r.returncode == 0, f"capture failed: {r.stderr}"
    assert (store / "new-rule.md").is_file(), "capture did not version the new live rule"
    assert (store / "new-rule.md").read_text() == (live / "new-rule.md").read_text()


def test_compat_disjoint_against_real_live():
    """The default live memory dir must be disjoint from every root-modules
    global surface — the cross-module boundary that lets both coexist."""
    import json
    r = _run(["compat", "--json"])
    assert r.returncode == 0, f"compat reported a collision: {r.stdout}\n{r.stderr}"
    data = json.loads(r.stdout)
    assert data["disjoint"] is True, f"not disjoint: {data['problems']}"


def test_compat_detects_a_collision():
    """Guard must FAIL when our memory dir is pointed at a ghostproxy-owned
    ~/.claude/ surface (proves the compat check isn't a no-op)."""
    import json
    collide = str(Path.home() / ".claude" / "hooks")  # ghostproxy-owned
    r = _run(["compat", "--json"], {"SOVEREIGN_OS_CLAUDE_MEMORY_DIR": collide})
    assert r.returncode == 1, "compat should flag a ghostproxy-owned target"
    data = json.loads(r.stdout)
    assert data["disjoint"] is False and data["problems"], (
        "compat did not report the collision"
    )


def test_sovereign_osctl_dispatches_operator_rules():
    r = subprocess.run(
        [str(OSCTL), "operator-rules", "status"],
        capture_output=True, text=True, timeout=30, cwd=str(REPO),
    )
    assert r.returncode == 0, f"osctl operator-rules status failed: {r.stderr}"
    assert "store:" in r.stdout and "live:" in r.stdout
    bad = subprocess.run(
        [str(OSCTL), "operator-rules", "bogus"],
        capture_output=True, text=True, timeout=30, cwd=str(REPO),
    )
    assert bad.returncode == 2, "unknown subverb must exit 2"


def test_provision_wires_rules_apply_and_ghostproxy_endpoint():
    body = PROVISION.read_text(encoding="utf-8")
    # always-on rules re-apply
    assert "operator-rules.py apply" in body, (
        "provision.sh must re-apply the operator rules on a fresh flash"
    )
    # root-modules installed WITHOUT the proxy half
    assert "--mode endpoint" in body and "--no-bridge" in body and "--no-wifi" in body, (
        "provision.sh must install root-modules in endpoint mode with NO proxy "
        "(--mode endpoint --no-bridge --no-wifi)"
    )
    # default-on but opt-out + self-contained (rules never depend on ghostproxy)
    assert "PROVISION_GHOSTPROXY" in body, "root-modules must be opt-out-able"


def test_help_text_advertises_operator_rules():
    body = OSCTL.read_text(encoding="utf-8")
    assert "operator-rules status|apply|capture|compat" in body, (
        "sovereign-osctl help must advertise the operator-rules verb"
    )
