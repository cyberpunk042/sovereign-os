"""Operator signing-key + root-password gate contract (2026-07-25 build failure).

WHAT BROKE: a panel build compiled the kernel for 30+ minutes, then died at
step 05 with "profile posture secure_boot=signed needs operator keys". The
system had a producer/consumer hole:

  • 05-substrate-prepare (mkosi-emit) READ /etc/sovereign-os/keys/mok.{key,crt}
  • 08-image-sign READ the same path
  • preflight-tpm told the operator "step 08 will auto-generate" — FALSE.
    Nothing generated anything, and 05 fails long before 08 would run.

So every consumer read a location no producer ever wrote, and the operator was
told to hand-run openssl. scripts/build/lib/operator-keys.sh is that missing
producer; both steps now go through it so they cannot drift apart again.

Behind it sat a SECOND gate of the same shape: mkosi-emit hard-fails without
SOVEREIGN_OS_ROOT_PASSWORD (a locked-root image boots to an unsatisfiable login
prompt) and the build panel exposed no way to supply one — a panel-launched
build could never clear step 05 regardless of what the operator did.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
KEYLIB = REPO_ROOT / "scripts" / "build" / "lib" / "operator-keys.sh"
MKOSI_EMIT = REPO_ROOT / "scripts" / "build" / "adapters" / "mkosi-emit.sh"
SIGN_STEP = REPO_ROOT / "scripts" / "build" / "08-image-sign.sh"
PREFLIGHT_TPM = REPO_ROOT / "scripts" / "hooks" / "pre-install" / "preflight-tpm.sh"
BUILD_API = REPO_ROOT / "scripts" / "operator" / "build-configurator-api.py"
BUILD_WEBAPP = REPO_ROOT / "webapp" / "build-configurator" / "index.html"

KEY_CONSUMERS = (MKOSI_EMIT, SIGN_STEP)


def test_key_library_exists_and_is_sourceable():
    assert KEYLIB.is_file(), "the operator-key producer library must exist"
    proc = subprocess.run(["bash", "-n", str(KEYLIB)], capture_output=True, text=True)
    assert proc.returncode == 0, f"operator-keys.sh does not parse:\n{proc.stderr}"


@pytest.mark.parametrize("consumer", KEY_CONSUMERS, ids=lambda p: p.name)
def test_every_key_consumer_uses_the_shared_producer(consumer: Path):
    """05 and 08 must both resolve keys through the ONE library.

    They previously hand-rolled the same discovery while neither could create
    the file they were discovering.
    """
    text = consumer.read_text(encoding="utf-8")
    assert "lib/operator-keys.sh" in text, (
        f"{consumer.name} must source scripts/build/lib/operator-keys.sh"
    )
    assert "ensure_operator_keys" in text, (
        f"{consumer.name} must call ensure_operator_keys so a missing key is "
        "minted rather than fatal"
    )


def test_preflight_no_longer_claims_step_08_autogenerates():
    """The false promise that cost a 30-minute kernel compile must stay gone."""
    text = PREFLIGHT_TPM.read_text(encoding="utf-8")
    live = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    assert "step 08 will auto-generate" not in live, (
        "preflight must not promise auto-generation by step 08 — step 05 fails "
        "first, and no step ever generated anything"
    )


def _mint_in(tmp: Path, *, as_root: bool) -> subprocess.CompletedProcess:
    """Run ensure_operator_keys against a sandbox key dir."""
    root_stub = "id() { echo 0; }\n" if as_root else ""
    script = (
        f". {KEYLIB}\n"
        f"{root_stub}"
        f'export SOVEREIGN_OS_KEY_DIR="{tmp}"\n'
        # capture ensure's own rc — a trailing echo would mask it
        "ensure_operator_keys signed; rc=$?\n"
        'echo "KEY=$SOVEREIGN_OS_MOK_KEY"\n'
        "exit $rc\n"
    )
    return subprocess.run(["bash", "-c", script], cwd=REPO_ROOT,
                          capture_output=True, text=True, timeout=120)


@pytest.mark.skipif(not shutil.which("openssl"), reason="openssl not installed")
def test_mints_a_usable_key_with_safe_permissions():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "keys"
        proc = _mint_in(tmp, as_root=True)
        assert proc.returncode == 0, proc.stderr
        key, crt = tmp / "mok.key", tmp / "mok.crt"
        assert key.is_file() and crt.is_file(), proc.stderr
        # the private key must never be group/world readable
        assert oct(key.stat().st_mode)[-3:] == "600", oct(key.stat().st_mode)
        # and it must be a real, long-lived cert
        out = subprocess.run(
            ["openssl", "x509", "-in", str(crt), "-noout", "-subject", "-enddate"],
            capture_output=True, text=True, check=True).stdout
        assert "sovereign-os operator MOK" in out


@pytest.mark.skipif(not shutil.which("openssl"), reason="openssl not installed")
def test_minting_is_idempotent():
    """A second call REUSES the key — regenerating would silently invalidate a
    certificate the operator already enrolled in firmware."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "keys"
        assert _mint_in(tmp, as_root=True).returncode == 0
        first = (tmp / "mok.key").read_bytes()
        assert _mint_in(tmp, as_root=True).returncode == 0
        assert (tmp / "mok.key").read_bytes() == first, "key was regenerated"


def test_declines_cleanly_when_it_cannot_mint():
    """Non-root must fail with a reason, not a traceback or a silent pass."""
    with tempfile.TemporaryDirectory() as td:
        proc = _mint_in(Path(td) / "keys", as_root=False)
        assert proc.returncode == 1
        assert "not root" in proc.stderr


def test_emit_error_points_at_the_real_cause():
    """The step-05 message must explain minting + name every escape hatch."""
    text = MKOSI_EMIT.read_text(encoding="utf-8")
    msg = text[text.index("needs an operator"):text.index("# ---- top-level mkosi.conf")]
    assert "operator-keys.sh" in msg, "must name the library that mints the key"
    assert "not running as\nroot" in msg or "NOT running as" in msg
    assert "SOVEREIGN_OS_MOK_KEY" in msg and "SOVEREIGN_OS_PK_KEY" in msg
    assert "secure_boot" in msg and "'none'" in msg, (
        "must offer the opt-out posture for a first build"
    )
    # SDD-015 posture is non-negotiable: never suggest keys in the repo.
    assert "NEVER stored in the repo" in msg


def test_panel_can_supply_the_root_password():
    """The gate behind the key gate: the panel had no field for it at all."""
    api = BUILD_API.read_text(encoding="utf-8")
    assert 'body.get("root_password")' in api, (
        "the build API must accept a root_password from the panel — without it "
        "no panel-launched build can clear step 05"
    )
    assert "SOVEREIGN_OS_ROOT_PASSWORD" in api
    assert "SOVEREIGN_OS_ALLOW_LOCKED_ROOT" in api, (
        "the explicit locked-root opt-in must also be reachable from the panel"
    )
    html = BUILD_WEBAPP.read_text(encoding="utf-8")
    assert 'id="root-password"' in html and 'type="password"' in html
    assert 'id="allow-locked-root"' in html
    assert "root_password:" in html, "the POST body must send the field"


def test_root_password_is_hashed_before_it_reaches_any_command_line():
    """Elevation passes env through `pkexec env K=V …` — argv is world-readable
    in `ps`, so the plaintext must be hashed in-process, over stdin."""
    api = BUILD_API.read_text(encoding="utf-8")
    blk = api[api.index('root_pw = body.get("root_password")'):][:1600]
    assert '"openssl", "passwd", "-6", "-stdin"' in blk, (
        "hash with `openssl passwd -6 -stdin` — never pass the secret as an argv"
    )
    assert "input=root_pw" in blk, "the plaintext must travel over stdin only"
    assert 'f"hashed:{hashed}"' in blk, "only the crypt hash may enter the env"
    # and the run log must never receive it
    log_region = api[api.index("logf.write"):api.index("logf.write") + 500]
    assert "root_password" not in log_region and "root_pw" not in log_region


@pytest.mark.parametrize("script", [KEYLIB, MKOSI_EMIT, SIGN_STEP, PREFLIGHT_TPM],
                         ids=lambda p: p.name)
def test_touched_shell_scripts_parse(script: Path):
    proc = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert proc.returncode == 0, f"{script.name} does not parse:\n{proc.stderr}"


def test_root_builds_do_not_write_bytecode_into_the_repo():
    """A root build must not leave root-owned __pycache__ in the working tree.

    The build runs as root (pkexec from the panel, sudo from the CLI) and imports
    repo Python; without this the operator ends up with root-owned .pyc files
    they can neither rewrite nor delete, and the Layer-1 suite fails with
    PermissionError on its own byte-compile check (seen 2026-07-25).
    """
    orch = (REPO_ROOT / "scripts" / "build" / "orchestrate.sh").read_text(encoding="utf-8")
    assert "export PYTHONDONTWRITEBYTECODE=1" in orch, (
        "orchestrate.sh must export PYTHONDONTWRITEBYTECODE=1 so an elevated "
        "build never drops root-owned bytecode into the operator's checkout"
    )
