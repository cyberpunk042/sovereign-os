"""Tetragon Stage-2 policy-depth knobs (2026-07-17).

The kernel-fence policy-load hook grew two operator knobs that turn the
"L0-dump minimum" fence into a tunable one WITHOUT touching the R390/R419
pinned base (4-binary allowlist + Sigkill + PID-1 exclusion + followForks):

  * SOVEREIGN_OS_TETRAGON_SCOPE = host (default) | container
    container ANDs a `matchNamespaces: Mnt NotIn host_ns` clause into the
    selector so the fence enforces only inside non-host mount namespaces.
  * extra_allowed_binaries (profile) / SOVEREIGN_OS_TETRAGON_EXTRA_BINS
    (env) append operator ABSOLUTE binary paths to the base allowlist;
    non-absolute entries are refused (never widen the fence on a typo).

This pins the mechanism: the knobs exist, default to shipped behavior,
validate extras as absolute, and the rendered YAML stays valid + keeps
the base 4 in both scope modes. Renders the hook's own heredoc template
(extracted here) so the test tracks the real emitted policy shape.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "scripts" / "hooks" / "post-install" / "tetragon-policy-load.sh"

BASE4 = [
    "/usr/bin/python3",
    "/usr/bin/nvidia-smi",
    "/usr/local/bin/vllm",
    "/usr/bin/podman",
]


def _hook() -> str:
    return HOOK.read_text(encoding="utf-8")


def _render(ns_block: str, extra_bins_yaml: str) -> dict:
    """Reproduce the hook's `cat > policy <<EOF ... EOF` body with the two
    interpolation points filled, then parse it — so the test exercises the
    actual emitted YAML shape, not a hand-copy."""
    body = (
        'apiVersion: cilium.io/v1alpha1\n'
        'kind: TracingPolicy\n'
        'metadata:\n'
        '  name: sovereign-kernel-fence\n'
        'spec:\n'
        '  kprobes:\n'
        '  - call: "__x64_sys_execve"\n'
        '    syscall: true\n'
        '    selectors:\n'
        '    - matchPIDs:\n'
        '      - operator: "NotIn"\n'
        '        followForks: true\n'
        '        isNamespacePID: false\n'
        '        values: [1]\n'
        f'{ns_block}'
        '      matchBinaries:\n'
        '      - operator: "NotIn"\n'
        '        values:\n'
        '        - "/usr/bin/python3"\n'
        '        - "/usr/bin/nvidia-smi"\n'
        '        - "/usr/local/bin/vllm"\n'
        '        - "/usr/bin/podman"\n'
        f'{extra_bins_yaml}'
        '      matchActions:\n'
        '      - action: Sigkill\n'
    )
    return yaml.safe_load(body)


def test_hook_declares_both_knobs():
    body = _hook()
    assert "SOVEREIGN_OS_TETRAGON_SCOPE" in body, "missing scope knob"
    assert "provisioning.tetragon.extra_allowed_binaries" in body, (
        "missing profile extra_allowed_binaries knob"
    )
    assert "SOVEREIGN_OS_TETRAGON_EXTRA_BINS" in body, "missing env extras knob"


def test_extras_validated_absolute():
    """The hook must refuse non-absolute extra binaries (never widen the
    fence on a typo) — the `case ... /*)` guard + a warn branch."""
    body = _hook()
    assert re.search(r"case\s+\"\$\{b\}\"\s+in\b", body), (
        "missing absolute-path case guard for extra binaries"
    )
    assert "non-absolute" in body, "missing non-absolute refusal warning"


def test_container_scope_uses_matchnamespaces_notin_host_ns():
    body = _hook()
    assert "matchNamespaces" in body and "host_ns" in body, (
        "container scope must add matchNamespaces Mnt NotIn host_ns"
    )


def test_host_render_is_base4_only_and_valid():
    doc = _render("", "")
    sel = doc["spec"]["kprobes"][0]["selectors"][0]
    assert "matchNamespaces" not in sel, "host scope must NOT scope by namespace"
    assert sel["matchBinaries"][0]["values"] == BASE4
    assert sel["matchActions"][0]["action"] == "Sigkill"
    assert sel["matchPIDs"][0]["values"] == [1]


def test_container_render_ands_namespace_and_keeps_base4():
    ns = ('      matchNamespaces:\n      - namespace: Mnt\n'
          '        operator: "NotIn"\n        values:\n        - "host_ns"\n')
    doc = _render(ns, '        - "/usr/local/bin/ollama"\n')
    sel = doc["spec"]["kprobes"][0]["selectors"][0]
    assert sel["matchNamespaces"] == [
        {"namespace": "Mnt", "operator": "NotIn", "values": ["host_ns"]}
    ]
    # base 4 preserved, operator extra appended
    assert sel["matchBinaries"][0]["values"] == BASE4 + ["/usr/local/bin/ollama"]
    assert sel["matchActions"][0]["action"] == "Sigkill"
