"""Agent-runtime model-backend hotswap contract (F-2026-116 / SDD-707).

Operator directive 2026-07-14: *"there should be a hotswap for [the] anthropic local ai
API vs the claude ai anthropic API for both. and it should be clear and easy how to swap
this"*. Both agent runtimes (OpenClaw + open-computer) must swap between the LOCAL model
(the on-box safety-spine gateway at :8787) and hosted Claude — easily, with the cloud key
NEVER baked. This also CORRECTS SDD-705/706, which pointed the runtimes at the raw vLLM
:8000 instead of the Anthropic-first gateway. This lint pins the whole chain:

  1. schema     — backend + anthropic_endpoint + anthropic_model on both blocks
  2. profile    — backend=local, local endpoint = the :8787 gateway (NOT raw :8000)
  3. engine     — agent-backend.py renders both providers + flips them; never bakes the key
  4. hooks      — both install hooks delegate to agent-backend.py (no lingering :8000)
  5. cli        — sovereign-osctl {openclaw,open-computer} backend {local|anthropic|show}
  6. units      — both runtimes EnvironmentFile the operator-supplied anthropic-key.env

Behaviour is exercised in dry-run: provision renders, swap flips the OpenClaw primary +
the open-computer OPENAI_BASE_URL, and the cloud key is written only via --key.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPO_ROOT / "schemas" / "profile.schema.yaml"
PROFILE = REPO_ROOT / "profiles" / "sain-01.yaml"
ENGINE = REPO_ROOT / "scripts" / "operator" / "agent-backend.py"
OPENCLAW_HOOK = REPO_ROOT / "scripts" / "hooks" / "post-install" / "openclaw-install.sh"
OC_HOOK = REPO_ROOT / "scripts" / "hooks" / "post-install" / "open-computer-install.sh"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
OPENCLAW_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-openclaw.service"
OC_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-open-computer.service"


# ---------- 1. schema ----------

def test_schema_backend_fields_both_blocks():
    doc = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    prov = doc["properties"]["provisioning"]["properties"]
    for block in ("openclaw", "open_computer"):
        props = prov[block]["properties"]
        assert props["backend"]["enum"] == ["local", "anthropic"], f"{block}.backend enum wrong"
        for f in ("anthropic_endpoint", "anthropic_model"):
            assert f in props, f"{block}.{f} missing from schema"


# ---------- 2. profile ----------

def test_profile_local_is_the_gateway_not_raw_vllm():
    doc = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    for block in ("openclaw", "open_computer"):
        b = doc["provisioning"][block]
        assert b["backend"] == "local", f"{block} default backend must be local"
        assert ":8787" in b["endpoint"], (
            f"{block} local endpoint {b['endpoint']!r} must be the :8787 safety-spine gateway (SDD-707 correction)"
        )
        assert ":8000" not in b["endpoint"], f"{block} still points at raw vLLM :8000 (SDD-705/706 regression)"
        assert "api.anthropic.com" in b["anthropic_endpoint"], f"{block} anthropic_endpoint not the hosted Claude API"


# ---------- 3. engine ----------

def test_engine_shape_and_no_baked_key():
    body = ENGINE.read_text(encoding="utf-8")
    for tok in ("provision", "def render_openclaw", "def render_open_computer",
                "anthropic-messages", "SOVEREIGN_OS_BACKEND_DRYRUN"):
        assert tok in body, f"agent-backend.py missing {tok!r}"
    # The cloud key must come from the env file / --key, never be a literal in the engine.
    assert "anthropic-key.env" in body, "engine must read the key from anthropic-key.env"
    assert not re.search(r"ANTHROPIC_API_KEY\s*=\s*[\"']sk-", body), "engine appears to bake a real key"


def test_engine_executable():
    assert ENGINE.is_file() and os.access(ENGINE, os.X_OK), "agent-backend.py missing or not executable"


# ---------- 4. hooks delegate, no lingering :8000 ----------

def test_hooks_delegate_and_drop_raw_vllm():
    for hook in (OPENCLAW_HOOK, OC_HOOK):
        body = hook.read_text(encoding="utf-8")
        assert "agent-backend.py" in body, f"{hook.name} does not delegate to agent-backend.py"
        assert ":8000" not in body, f"{hook.name} still references the raw vLLM :8000 (should be the :8787 gateway)"
        assert "provisioning." in body and "anthropic_endpoint" in body, f"{hook.name} does not read the anthropic config"


# ---------- 5. cli ----------

def test_osctl_backend_verbs():
    body = OSCTL.read_text(encoding="utf-8")
    # all four consumers dispatch a backend sub-verb to the engine
    assert body.count("agent-backend.py") >= 2, "osctl does not delegate backend to agent-backend.py"
    for verb in ("openclaw backend", "open-computer backend",
                 "claude-code backend", "vscode backend"):
        assert verb in body, f"osctl help missing the {verb!r} verb (SDD-600 Part 2)"


# ---------- 6. units carry the key file ----------

def test_units_environmentfile_the_key():
    for unit in (OPENCLAW_UNIT, OC_UNIT):
        body = unit.read_text(encoding="utf-8")
        assert "EnvironmentFile=-/etc/sovereign-os/anthropic-key.env" in body, (
            f"{unit.name} does not EnvironmentFile the operator-supplied anthropic key"
        )


# ---------- behaviour (dry-run) ----------

def _run(runtime: str, args: list[str], tmp: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update({
        "SOVEREIGN_OS_BACKEND_DRYRUN": "1",
        "SOVEREIGN_OS_ETC": str(tmp),
        "SOVEREIGN_OS_OPENCLAW_HOME": str(tmp / "oc-home"),
        "SOVEREIGN_OS_OPEN_COMPUTER_ROOT": str(tmp / "ocmp"),
        "SOVEREIGN_OS_OPEN_COMPUTER_ENV": str(tmp / "open-computer.env"),
        "SOVEREIGN_OS_ANTHROPIC_KEY_ENV": str(tmp / "anthropic-key.env"),
        "SOVEREIGN_OS_CLAUDE_CODE_ENV": str(tmp / "claude-code.env"),
        "SOVEREIGN_OS_VSCODE_CLINE_JSON": str(tmp / "vscode-cline-settings.json"),
    })
    return subprocess.run([sys.executable, str(ENGINE), runtime, *args],
                          capture_output=True, text=True, env=env, timeout=30)


def _provision_openclaw(tmp: Path):
    return _run("openclaw", ["provision", "--backend", "local",
                             "--local-endpoint", "http://127.0.0.1:8787", "--local-model", "local-oracle",
                             "--anthropic-endpoint", "https://api.anthropic.com",
                             "--anthropic-model", "claude-sonnet-4-6", "--gateway-port", "18789"], tmp)


def _openclaw_cfg(tmp: Path) -> dict:
    return json.loads((tmp / "oc-home" / ".openclaw" / "openclaw.json").read_text(encoding="utf-8"))


def test_openclaw_swap_flips_primary(tmp_path: Path):
    # A key must exist for the anthropic provider to be declared at all: an
    # unresolvable secret-ref is a hard startup failure for OpenClaw, so the
    # renderer refuses to write one. See
    # test_never_declares_a_provider_that_cannot_authenticate.
    (tmp_path / "anthropic-key.env").write_text("ANTHROPIC_API_KEY=sk-test\n", encoding="utf-8")
    assert _provision_openclaw(tmp_path).returncode == 0
    cfg = _openclaw_cfg(tmp_path)
    provs = cfg["models"]["providers"]
    # The provider is `sovereign`, not `local`: scripts/inference/
    # sync-openclaw-models.py mirrors the active profile's per-tier models into
    # models.providers.sovereign, and a renderer using a different name meant the
    # two halves of the system never saw the same config.
    assert set(provs) == {"sovereign", "anthropic"}, f"want both providers, got {list(provs)}"
    assert "127.0.0.1:8787" in provs["sovereign"]["baseUrl"]
    assert "api.anthropic.com" in provs["anthropic"]["baseUrl"]
    assert cfg["agents"]["defaults"]["model"]["primary"] == "sovereign/local-oracle"

    # swap to anthropic — a change of PRIMARY, nothing else
    r = _run("openclaw", ["anthropic"], tmp_path)
    assert r.returncode == 0
    cfg2 = _openclaw_cfg(tmp_path)
    assert cfg2["agents"]["defaults"]["model"]["primary"] == "anthropic/claude-sonnet-4-6"
    assert set(cfg2["models"]["providers"]) == {"sovereign", "anthropic"}, \
        "a swap must not remove the provider it swapped away from"


def test_openclaw_render_merges_and_never_clobbers(tmp_path: Path):
    """The renderer templated over the whole file. On a live box that erased the
    gateway auth token, every channel the operator had onboarded, and the
    per-tier models sync-openclaw-models.py maintains — after which that script
    found no sovereign provider and logged "skipping (ok)", so the D-21 profile
    mirroring stopped silently and permanently."""
    home = tmp_path / "oc-home" / ".openclaw"
    home.mkdir(parents=True)
    (home / "openclaw.json").write_text(json.dumps({
        "gateway": {"auth": {"mode": "token", "token": "SECRET-TOKEN"}, "port": 18789},
        "tools": {"custom": True},
        "models": {"providers": {"sovereign": {
            "baseUrl": "http://127.0.0.1:8787/v1",
            "api": "openai-completions",
            "models": [{"id": "gpu-oracle"}, {"id": "gpu-logic"}, {"id": "local-oracle"}],
        }}},
    }), encoding="utf-8")

    assert _provision_openclaw(tmp_path).returncode == 0
    cfg = _openclaw_cfg(tmp_path)
    assert cfg["gateway"]["auth"]["token"] == "SECRET-TOKEN", "the Control UI credential was destroyed"
    assert cfg["tools"] == {"custom": True}, "operator configuration was destroyed"
    sov = cfg["models"]["providers"]["sovereign"]
    assert [m["id"] for m in sov["models"]] == ["gpu-oracle", "gpu-logic", "local-oracle"], \
        "the profile-mirrored models were destroyed"
    # A WORKING provider keeps its dialect: re-asserting anthropic-messages from a
    # default would break a box that speaks openai-completions and works.
    assert sov["api"] == "openai-completions"
    assert sov["baseUrl"] == "http://127.0.0.1:8787/v1"


def test_cloud_is_selectable_but_never_automatic(tmp_path: Path):
    """An onboarding wizard had left fallbacks: ["claude-cli/…"], so a sovereign
    failure silently continued on the hosted API — cloud use at exactly the
    moment nobody is watching, on a box whose headline invariant is
    never_cloud_spill. Choosing a provider is deliberate; falling back is not."""
    home = tmp_path / "oc-home" / ".openclaw"
    home.mkdir(parents=True)
    (home / "openclaw.json").write_text(json.dumps({
        "agents": {"defaults": {"model": {
            "primary": "sovereign/gpu-oracle",
            "fallbacks": ["claude-cli/claude-opus-4-8"],
        }}},
    }), encoding="utf-8")
    assert _provision_openclaw(tmp_path).returncode == 0
    assert "fallbacks" not in _openclaw_cfg(tmp_path)["agents"]["defaults"]["model"]


def test_open_computer_swap_flips_base_url_and_key(tmp_path: Path):
    assert _run("open-computer", ["provision", "--backend", "local",
                                  "--local-endpoint", "http://127.0.0.1:8787/v1", "--local-model", "local-oracle",
                                  "--anthropic-endpoint", "https://api.anthropic.com/v1/",
                                  "--anthropic-model", "claude-sonnet-4-6", "--web-port", "9800"], tmp_path).returncode == 0
    env_local = (tmp_path / "open-computer.env").read_text(encoding="utf-8")
    assert "OPENAI_BASE_URL=http://127.0.0.1:8787/v1" in env_local, "local env not the gateway shim"
    # swap to anthropic WITH a key
    r = _run("open-computer", ["anthropic", "--key", "sk-ant-TESTONLY"], tmp_path)
    assert r.returncode == 0
    env_cloud = (tmp_path / "open-computer.env").read_text(encoding="utf-8")
    assert "OPENAI_BASE_URL=https://api.anthropic.com/v1/" in env_cloud, "swap did not flip OPENAI_BASE_URL"
    assert "OPENAI_API_KEY=sk-ant-TESTONLY" in env_cloud, "cloud key not injected on swap"
    # the key landed in the root-only key file, not the profile/hook
    assert "sk-ant-TESTONLY" in (tmp_path / "anthropic-key.env").read_text(encoding="utf-8")


def test_anthropic_without_key_warns(tmp_path: Path):
    _provision_openclaw(tmp_path)
    r = _run("openclaw", ["anthropic"], tmp_path)
    assert r.returncode == 0
    assert "no ANTHROPIC_API_KEY" in (r.stdout + r.stderr), "swapping to anthropic without a key should warn"


# ---------- SDD-600 Part 2: Claude Code + VSCode renderers ----------

def test_engine_has_the_two_new_renderers():
    body = ENGINE.read_text(encoding="utf-8")
    for tok in ("def render_claude_code", "def render_vscode",
                '"claude-code"', '"vscode"'):
        assert tok in body, f"agent-backend.py missing {tok!r} (SDD-600 Part 2)"


def _provision(runtime: str, tmp: Path, local_endpoint: str):
    return _run(runtime, ["provision", "--backend", "local",
                          "--local-endpoint", local_endpoint, "--local-model", "local-oracle",
                          "--anthropic-endpoint", "https://api.anthropic.com",
                          "--anthropic-model", "claude-sonnet-4-6"], tmp)


def test_claude_code_swap_writes_base_url(tmp_path: Path):
    assert _provision("claude-code", tmp_path, "http://127.0.0.1:8787").returncode == 0
    env_local = (tmp_path / "claude-code.env").read_text(encoding="utf-8")
    assert "ANTHROPIC_BASE_URL=http://127.0.0.1:8787" in env_local, "local must point at the on-box gateway"
    assert ":8000" not in env_local, "must not point at raw vLLM :8000"
    # swap to cloud → ANTHROPIC_BASE_URL cleared so Claude Code uses its default
    r = _run("claude-code", ["anthropic", "--key", "sk-ant-TESTONLY"], tmp_path)
    assert r.returncode == 0
    env_cloud = (tmp_path / "claude-code.env").read_text(encoding="utf-8")
    assert "ANTHROPIC_BASE_URL=\n" in env_cloud, "cloud must clear ANTHROPIC_BASE_URL"
    assert "ANTHROPIC_API_KEY=sk-ant-TESTONLY" in env_cloud, "cloud key not injected on swap"


def test_vscode_swap_renders_cline_fragment(tmp_path: Path):
    assert _provision("vscode", tmp_path, "http://127.0.0.1:8787").returncode == 0
    frag_local = (tmp_path / "vscode-cline-settings.json").read_text(encoding="utf-8")
    assert '"cline.anthropicBaseUrl": "http://127.0.0.1:8787"' in frag_local, "local must target the on-box gateway"
    assert '"cline.apiProvider": "anthropic"' in frag_local, "VSCode consumer speaks Anthropic (Cline/Claude Dev)"
    # swap to cloud
    r = _run("vscode", ["anthropic"], tmp_path)
    assert r.returncode == 0
    frag_cloud = (tmp_path / "vscode-cline-settings.json").read_text(encoding="utf-8")
    assert "api.anthropic.com" in frag_cloud, "cloud must target the hosted Claude endpoint"


def test_openclaw_home_prefers_a_config_that_exists(tmp_path: Path, monkeypatch):
    """OPENCLAW_HOME defaulted to /var/lib/sovereign-os/openclaw. OpenClaw is an
    `npm install -g` whose own onboard wizard writes to the operator's home, and
    on a real box the managed directory may not exist at all — so a swap wrote a
    perfectly correct config that nothing read. It appeared to work and changed
    nothing, which is worse than failing."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_ab_home", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    monkeypatch.delenv("SOVEREIGN_OS_OPENCLAW_HOME", raising=False)
    operator_home = tmp_path / "operator"
    (operator_home / ".openclaw").mkdir(parents=True)
    (operator_home / ".openclaw" / "openclaw.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SUDO_USER", "nobody")
    monkeypatch.setattr(mod.pwd, "getpwnam",
                        lambda n: type("P", (), {"pw_dir": str(operator_home)})())
    assert mod._openclaw_home() == operator_home, "must target the config that exists"

    # An explicit override always wins — the tests and the IaC rely on it.
    monkeypatch.setenv("SOVEREIGN_OS_OPENCLAW_HOME", str(tmp_path / "managed"))
    assert mod._openclaw_home() == tmp_path / "managed"


def test_swap_adopts_an_install_it_did_not_provision(tmp_path: Path, monkeypatch):
    """`swap` refused without a saved descriptor, which only `provision` writes.
    OpenClaw is normally installed by its OWN onboard wizard — that is how it got
    onto this box — so a working install had no descriptor and `openclaw backend
    local` answered "not provisioned, run: openclaw install" while the gateway
    was up and serving. Telling an operator to install what they already have is
    not a useful refusal."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_ab_adopt", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    home = tmp_path / "oc"
    (home / ".openclaw").mkdir(parents=True)
    (home / ".openclaw" / "openclaw.json").write_text(json.dumps({
        "gateway": {"port": 18789},
        "agents": {"defaults": {"model": {"primary": "sovereign/gpu-oracle"}}},
        "models": {"providers": {
            "sovereign": {"baseUrl": "http://127.0.0.1:8787/v1",
                          "models": [{"id": "gpu-oracle"}]},
            "anthropic": {"baseUrl": "https://api.anthropic.com",
                          "models": [{"id": "claude-opus-4-8"}]},
        }},
    }), encoding="utf-8")
    monkeypatch.setenv("SOVEREIGN_OS_OPENCLAW_HOME", str(home))

    d = mod._adopt_openclaw_desc()
    assert d["backend"] == "local"
    assert d["local"]["model"] == "gpu-oracle"
    assert d["anthropic"]["model"] == "claude-opus-4-8"
    assert d["gateway_port"] == 18789

    # Nothing to adopt ⇒ empty, so the honest "not provisioned" error still fires.
    monkeypatch.setenv("SOVEREIGN_OS_OPENCLAW_HOME", str(tmp_path / "absent"))
    assert mod._adopt_openclaw_desc() == {}


def test_descriptor_cache_failure_does_not_abort_the_swap(tmp_path: Path, monkeypatch):
    """The descriptor lives under /etc and the save ran BEFORE the render, so a
    non-root operator got a PermissionError traceback and an untouched config.
    Failing the work because the note about the work could not be filed is the
    wrong order of priorities."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_ab_desc", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "_desc_path", lambda r: Path("/proc/definitely-not-writable/x.json"))
    mod._save_desc("openclaw", {"backend": "local"})  # must not raise


def test_never_declares_a_provider_that_cannot_authenticate(tmp_path: Path, monkeypatch):
    """An `apiKey: "${ANTHROPIC_API_KEY}"` secret-ref with no such variable is not
    a warning to OpenClaw — it is a HARD startup failure:

        [secrets] SecretRefResolutionError: Environment variable
        "ANTHROPIC_API_KEY" is missing or empty
        openclaw-gateway.service: Main process exited, status=1/FAILURE

    Declaring it on a keyless box crash-looped the gateway until systemd's start
    limit stopped it. `openclaw gateway status` calls the same condition "feature
    will be unavailable", which is what made it look safe."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_ab_key", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    home = tmp_path / "oc"
    (home / ".openclaw").mkdir(parents=True)
    monkeypatch.setenv("SOVEREIGN_OS_OPENCLAW_HOME", str(home))
    monkeypatch.setenv("SOVEREIGN_OS_ANTHROPIC_KEY_ENV", str(tmp_path / "no-key.env"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(mod, "KEY_FILE", tmp_path / "no-key.env")

    desc = {"backend": "local", "local": {"model": "gpu-oracle"},
            "anthropic": {"model": "claude-opus-4-8"}, "gateway_port": 18789}
    cfg = json.loads(Path(mod.render_openclaw(desc)).read_text(encoding="utf-8"))
    assert "anthropic" not in cfg["models"]["providers"], \
        "a provider that cannot authenticate must not be declared"
    assert not [k for k in cfg["agents"]["defaults"]["models"] if k.startswith("anthropic/")]

    # With a key present it IS declared.
    (tmp_path / "no-key.env").write_text("ANTHROPIC_API_KEY=sk-test\n", encoding="utf-8")
    cfg2 = json.loads(Path(mod.render_openclaw(desc)).read_text(encoding="utf-8"))
    assert "anthropic" in cfg2["models"]["providers"]
    assert "anthropic/claude-opus-4-8" in cfg2["agents"]["defaults"]["models"]

    # ...and removing the key REPAIRS a config that would now break startup.
    (tmp_path / "no-key.env").write_text("", encoding="utf-8")
    cfg3 = json.loads(Path(mod.render_openclaw(desc)).read_text(encoding="utf-8"))
    assert "anthropic" not in cfg3["models"]["providers"], \
        "re-rendering must repair a config that cannot start, not preserve it"
