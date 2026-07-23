"""Contract lint for the integration setup collector (config/integrations.yaml +
`sovereign-osctl setup` + /api/control/setup + the Setup pane).

Pins the chain so it can't silently break or leak:
  1. registry     — config/integrations.yaml shape (id/env_file/fields, kinds)
  2. collector    — setup.py subcommands + secret masking + registry-validated writes
  3. dispatch     — osctl `setup` verb + help + man ownership
  4. endpoint     — control-exec-api GET (read) + POST (redacted write) /api/control/setup
  5. pane         — the shared settings overlay Setup pane + sanctioned fetch
  6. sudoers      — the NOPASSWD allowlist carries `setup set/unset/complete`
Plus BEHAVIOUR (dry-run): unknown var refused; a secret value is never echoed.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "config" / "integrations.yaml"
SETUP_PY = REPO / "scripts" / "operator" / "setup.py"
OSCTL = REPO / "scripts" / "sovereign-osctl"
EXEC_API = REPO / "scripts" / "operator" / "control-exec-api.py"
APP_SHELL = REPO / "webapp" / "_shared" / "app-shell-snippet.html"
SUDOERS = REPO / "config" / "sudoers.d" / "sovereign-os-cockpit"
FEATURE_COV = REPO / "config" / "feature-coverage.yaml"


# ── 1. registry ─────────────────────────────────────────────────────
def test_registry_shape():
    doc = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    assert doc.get("schema_version"), "registry missing schema_version"
    its = doc.get("integrations")
    assert isinstance(its, list) and its, "registry has no integrations"
    seen = set()
    for it in its:
        for k in ("id", "label", "feature", "env_file", "fields"):
            assert k in it, f"integration {it.get('id')!r} missing {k!r}"
        assert it["id"] not in seen, f"duplicate integration id {it['id']!r}"
        seen.add(it["id"])
        assert it["env_file"].endswith(".env"), f"{it['id']}: env_file must be a *.env"
        assert it["fields"], f"{it['id']}: no fields"
        for f in it["fields"]:
            assert "name" in f, f"{it['id']}: field missing name"
            assert f.get("kind", "config") in ("secret", "config"), \
                f"{it['id']}.{f['name']}: kind must be secret|config"
    # the sharpest-gap integrations the operator called out must be present
    for must in ("ntfy", "resend", "twilio", "webhook", "huggingface"):
        assert must in seen, f"registry missing {must!r}"


# ── 2. collector ────────────────────────────────────────────────────
def test_setup_py_shape():
    body = SETUP_PY.read_text(encoding="utf-8")
    for sub in ("status", "list", "set", "unset", "wizard", "complete"):
        assert f'"{sub}"' in body, f"setup.py missing subcommand {sub!r}"
    assert "SOVEREIGN_OS_SETUP_DRYRUN" in body, "setup.py has no dry-run seam"
    # a secret's value must NOT be placed in the status payload
    assert 'kind") == "config"' in body or "kind'] == 'config'" in body or \
        'f.get("kind") == "config"' in body, "setup.py status must mask non-config values"


def test_setup_masks_secrets_and_refuses_unknown(tmp_path: Path):
    env = dict(os.environ, SOVEREIGN_OS_ETC=str(tmp_path))
    # a set + a status: the secret value must never appear in the JSON payload
    subprocess.run(["python3", str(SETUP_PY), "set",
                    "SOVEREIGN_OS_NOTIFY_NTFY_TOKEN", "tk_supersecret_xyz"],
                   env=env, check=True, capture_output=True, text=True)
    r = subprocess.run(["python3", str(SETUP_PY), "status", "--json"],
                       env=env, capture_output=True, text=True)
    assert "tk_supersecret_xyz" not in r.stdout, "secret value leaked into status --json"
    payload = json.loads(r.stdout)
    tok = None
    for it in payload["integrations"]:
        for f in it["fields"]:
            if f["name"].endswith("NTFY_TOKEN"):
                tok = f
    assert tok and tok["set"] is True and tok["value"] == "", \
        "secret must be reported set:true with an empty value"
    # unknown variable is refused
    r2 = subprocess.run(["python3", str(SETUP_PY), "set", "NOT_A_REAL_VAR", "x"],
                        env=env, capture_output=True, text=True)
    assert r2.returncode != 0, "setup set accepted an unknown variable"


# ── 3. dispatch ─────────────────────────────────────────────────────
def test_osctl_dispatches_and_documents_setup():
    body = OSCTL.read_text(encoding="utf-8")
    assert "  setup)" in body, "osctl has no setup) dispatch case"
    assert "scripts/operator/setup.py" in body, "osctl setup does not exec setup.py"
    assert "setup status" in body, "osctl help does not document setup"
    topics = json.loads((REPO / "docs" / "man" / "sovereign-osctl-command-topics.json").read_text())
    assert "setup" in topics["pages"]["operations"], "setup not owned by a man topic"


# ── 4. endpoint (read + redacted write) ─────────────────────────────
def test_control_api_serves_setup_read_and_redacted_write():
    body = EXEC_API.read_text(encoding="utf-8")
    assert '"/api/control/setup"' in body, "control-exec-api does not route /api/control/setup"
    assert "_handle_setup_write" in body, "no dedicated setup write handler"
    assert "_field_index" in body, "setup write must validate NAME against the registry"
    # the write path may READ body.get("value") (to pass as argv) but must NEVER put
    # it in the response or a log — the response carries name + ok/err only.
    handler = body.split("_handle_setup_write")[1].split("def do_POST")[0]
    assert 'resp["name"] = name' in handler, "setup write must return the name"
    assert 'resp["value"]' not in handler, "setup write must never return the value"
    assert "REDACT" in handler.upper() or "redact" in handler, \
        "setup write must document its redaction intent"


# ── 5. pane ─────────────────────────────────────────────────────────
def test_app_shell_has_setup_pane():
    body = APP_SHELL.read_text(encoding="utf-8")
    assert 'id="so-setup-open"' in body, "settings pane missing the Setup opener"
    assert "so-setup-modal" in body, "no Setup modal in the app-shell"
    assert "/api/control/setup" in body, "Setup pane never talks to /api/control/setup"


# ── 6. sudoers + accounting ─────────────────────────────────────────
def test_sudoers_allows_setup_writes():
    body = SUDOERS.read_text(encoding="utf-8")
    assert "sovereign-osctl setup set *" in body, "sudoers missing setup set"
    assert "sovereign-osctl setup complete" in body, "sudoers missing setup complete"


def test_feature_coverage_accounts_setup():
    body = FEATURE_COV.read_text(encoding="utf-8")
    assert "verb: setup" in body, "feature-coverage does not account the setup verb"


# ── 7. consumer wiring: the env files the collector writes must be LOADED ──
def test_service_env_files_are_loaded_by_a_unit():
    """Collecting a value is pointless if nothing loads it. Every env file a
    SERVICE integration writes to must be pulled in by a systemd unit via
    EnvironmentFile=- (the notify.env pattern). CLI-only integrations (opnsense)
    and self-managed ones (anthropic) are exempt."""
    units = " ".join(p.read_text(encoding="utf-8")
                      for p in (REPO / "systemd" / "system").glob("*.service"))
    doc = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    # env files whose consumers are unattended services (must be auto-loaded)
    service_env_files = {"notify.env", "model.env", "dashboard-auth.env", "jobs.env"}
    for it in doc["integrations"]:
        ef = it["env_file"]
        if ef in service_env_files:
            assert f"/etc/sovereign-os/{ef}" in units, (
                f"{it['id']}: no systemd unit loads /etc/sovereign-os/{ef} "
                "(EnvironmentFile=-) — the collected value would never reach the service"
            )
