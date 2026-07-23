"""SDD-510 (M00155 F00793/4/5) — the `sovereign-osctl token-law` verb.

The operator handle on the token-law engine's mask-layer selection. `layers`
resolves the active selection (flag > env > profile > all) with no daemon;
`fuse` probes the checkpoint-free route (degrading cleanly when it's down).
Exercised via subprocess.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLI = REPO / "scripts" / "operator" / "token-law-cli.py"
OSCTL = REPO / "scripts" / "sovereign-osctl"


def _run(*args, env_extra=None):
    env = {"PATH": "/usr/bin:/bin"}
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, str(CLI), *args],
                          capture_output=True, text=True, timeout=15, env=env)


def test_layers_default_is_all():
    # with no flag, no env, and a profile that carries no token-law knob
    # (a nonexistent id resolves to nothing), the fallback is ALL layers.
    r = _run("layers", "--json", env_extra={"SOVEREIGN_OS_RUNTIME_PROFILE": "no-such-profile"})
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["active"] == ["grammar", "regex", "denylist", "regex_denylist", "policy"]
    assert out["source"] == "default(all)"


def test_layers_flag_wins_and_aliases_map():
    # milestone aliases: safety→denylist+regex_denylist, tool→regex
    r = _run("layers", "--token-law-mask-layers", "safety,tool", "--json")
    out = json.loads(r.stdout)
    assert out["active"] == ["regex", "denylist", "regex_denylist"]
    assert out["source"] == "--token-law-mask-layers"


def test_env_overrides_when_no_flag():
    r = _run("layers", "--json", env_extra={"SOVEREIGN_TOKEN_LAW_MASK_LAYERS": "grammar"})
    out = json.loads(r.stdout)
    assert out["active"] == ["grammar"] and out["source"] == "env"


def test_flag_beats_env():
    r = _run("layers", "--token-law-mask-layers", "policy", "--json",
             env_extra={"SOVEREIGN_TOKEN_LAW_MASK_LAYERS": "grammar"})
    out = json.loads(r.stdout)
    assert out["active"] == ["policy"] and out["source"] == "--token-law-mask-layers"


def test_profile_knob_is_read():
    # the shipped high-concurrency-burst profile pins grammar,schema,tool,safety
    r = _run("layers", "--json",
             env_extra={"SOVEREIGN_OS_RUNTIME_PROFILE": "high-concurrency-burst"})
    out = json.loads(r.stdout)
    assert out["source"] == "profile"
    assert out["active"] == ["grammar", "regex", "denylist", "regex_denylist"]


def test_unknown_layer_is_rejected():
    r = _run("layers", "--token-law-mask-layers", "grammar,teleport")
    assert r.returncode == 2 and "unknown mask layer" in r.stderr


def test_fuse_degrades_when_gateway_down():
    # point at a closed port → clean non-zero, not a crash
    r = _run("fuse", "--vocab", "a,b", "--regex", "[a-z]+", "--addr", "127.0.0.1:1")
    assert r.returncode == 1 and "unreachable" in r.stderr


def test_fuse_needs_a_vocab():
    assert _run("fuse", "--regex", "[a-z]+").returncode == 2


def test_osctl_dispatches_token_law():
    body = OSCTL.read_text(encoding="utf-8")
    assert "token-law)" in body and "scripts/operator/token-law-cli.py" in body
    assert "token-law layers" in body  # discoverable in the COMMANDS help block
