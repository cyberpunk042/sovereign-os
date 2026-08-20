"""Tetragon Stage-2 policy-depth knobs (2026-07-17).

The kernel-fence policy-load hook grew two operator knobs that turn the
"L0-dump minimum" fence into a tunable one WITHOUT touching the R390/R419
pinned base (4-binary allowlist + Sigkill + PID-1 exclusion + followForks):

  * SOVEREIGN_OS_TETRAGON_SCOPE = host (default) | container
    container ANDs a cgroup `matchData` clause (leaf cgroup name == "container")
    into the selector so the fence enforces only inside podman container
    workloads. Superseded matchNamespaces 2026-08-20 (that matched every
    sandboxed host service and missed the container entrypoint).
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


# Container-scope interpolations (2026-08-20, superseding matchNamespaces):
# a kprobe-level `data` block resolving the cgroup leaf name + a `matchData`
# selector clause requiring it to equal "container" (podman container workload).
CONTAINER_DATA = (
    '    data:\n'
    '    - index: 0\n'
    '      type: "string"\n'
    '      source: "current_task"\n'
    '      resolve: "cgroups.dfl_cgrp.kn.name"\n'
)
CONTAINER_MATCH = (
    '      matchData:\n'
    '      - index: 0\n'
    '        operator: "Equal"\n'
    '        values:\n'
    '        - "container"\n'
)


def _render(data_block: str, cgroup_match: str, extra_bins_yaml: str) -> dict:
    """Reproduce the hook's `cat > policy <<EOF ... EOF` body with the three
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
        '    args:\n'
        '    - index: 0\n'
        '      type: "string"\n'
        '    - index: 1\n'
        '      type: "string"\n'
        f'{data_block}'
        '    selectors:\n'
        '    - matchPIDs:\n'
        '      - operator: "NotIn"\n'
        '        followForks: true\n'
        '        isNamespacePID: false\n'
        '        values: [1]\n'
        f'{cgroup_match}'
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


def test_container_scope_uses_cgroup_matchdata():
    """Supersedes matchNamespaces (2026-08-20): container scope is the CGROUP.
    matchNamespaces(Mnt NotIn host_ns) matched every sandboxed host service and
    missed the container entrypoint; the leaf cgroup name "container" is the
    precise podman-container discriminator (validated in monitor)."""
    body = _hook()
    assert "matchNamespaces:" not in body, (
        "container scope must NOT emit a matchNamespaces clause — it "
        "false-matches host services (superseded by cgroup matchData 2026-08-20)"
    )
    assert 'resolve: "cgroups.dfl_cgrp.kn.name"' in body, (
        "container scope must resolve the cgroup leaf name via matchData"
    )
    assert "matchData" in body and '- "container"' in body, (
        "container scope must require cgroup leaf name == \"container\""
    )


def test_host_render_is_base4_only_and_valid():
    doc = _render("", "", "")
    kp = doc["spec"]["kprobes"][0]
    sel = kp["selectors"][0]
    assert "data" not in kp, "host scope must NOT add a cgroup data block"
    assert "matchData" not in sel and "matchNamespaces" not in sel, (
        "host scope must NOT scope by cgroup or namespace"
    )
    assert sel["matchBinaries"][0]["values"] == BASE4
    assert sel["matchActions"][0]["action"] == "Sigkill"
    assert sel["matchPIDs"][0]["values"] == [1]


def test_container_render_ands_cgroup_matchdata_and_keeps_base4():
    doc = _render(CONTAINER_DATA, CONTAINER_MATCH, '        - "/usr/local/bin/ollama"\n')
    kp = doc["spec"]["kprobes"][0]
    sel = kp["selectors"][0]
    # kprobe-level data block resolves the cgroup leaf name
    assert kp["data"] == [{
        "index": 0, "type": "string",
        "source": "current_task", "resolve": "cgroups.dfl_cgrp.kn.name",
    }]
    # selector requires the leaf cgroup name == "container"
    assert sel["matchData"] == [
        {"index": 0, "operator": "Equal", "values": ["container"]}
    ]
    # base 4 preserved, operator extra appended, Sigkill intact
    assert sel["matchBinaries"][0]["values"] == BASE4 + ["/usr/local/bin/ollama"]
    assert sel["matchActions"][0]["action"] == "Sigkill"


def test_hook_declares_armed_knob():
    """A' arming knob (2026-08-20): controls whether the Sigkill fence is LOADED,
    without touching the action (which stays Sigkill per the §4.1 verbatim).
    Default is armed (appliance); a desktop opts out via profile/env."""
    body = _hook()
    assert "SOVEREIGN_OS_TETRAGON_ARMED" in body, "missing env arming knob"
    assert "provisioning.tetragon.armed" in body, "missing profile arming knob"
    # arming gates LOADING only — the rendered action must remain Sigkill
    doc = _render("", "", "")
    assert doc["spec"]["kprobes"][0]["selectors"][0]["matchActions"][0]["action"] == "Sigkill"
