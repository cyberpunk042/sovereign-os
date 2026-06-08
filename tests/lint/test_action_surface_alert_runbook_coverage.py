"""Every selfdef action-surface alert MUST have a resolvable runbook anchor.

The 11 selfdef responder action-surface alert families ship per-alert
``runbook_url`` annotations pointing at anchors in
``docs/operator/m060-deployment-guide.md``. Before this lint those 64
alerts pointed at anchors that did not exist — a paging hazard where an
operator hit by e.g. ``SelfdefTokenRevocationsStateDirMissing`` (critical,
"enforcement OFFLINE") clicked the runbook link and landed on nothing.

This is the action-surface sibling of
``test_m060_alert_runbook_coverage`` (which covers m060-chain-health).
It locks the rules-file ↔ deployment-guide anchors in lockstep: every
alert's ``runbook_url`` fragment must resolve to a heading in the guide,
and each must carry the standard Meaning/Diagnosis/Fix shape.

Proper-responsibility boundary: selfdef emits the textfile gauges these
alerts fire on; sovereign-os owns the alert rules + the operator runbook.

Run: ``pytest -xq tests/lint/test_action_surface_alert_runbook_coverage.py``
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ALERTS_DIR = REPO_ROOT / "config" / "prometheus" / "alerts"
GUIDE_PATH = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"

# The 11 selfdef responder action-surface alert families (SDD-070..078 +
# MFA/token revocations). Kept explicit (not globbed) so adding a new
# action-surface family is a deliberate act that extends this list and
# forces its runbook coverage.
ACTION_SURFACE_FILES = [
    "selfdef-apparmor-profile-pivots",
    "selfdef-bpf-map-element-clears",
    "selfdef-capability-drops",
    "selfdef-env-scrubs",
    "selfdef-kernel-keyring-evictions",
    "selfdef-mfa-grant-revocations",
    "selfdef-mount-bindings",
    "selfdef-netns-isolations",
    "selfdef-process-tree-freezes",
    "selfdef-socket-fd-revocations",
    "selfdef-token-revocations",
]


def _github_anchor(heading: str) -> str:
    """Reproduce GitHub's heading→anchor slugging."""
    a = heading.strip().lower()
    a = re.sub(r"[^\w\s-]", "", a)
    a = re.sub(r"\s", "-", a)  # GitHub replaces each space; does NOT collapse
    return a


def _guide_anchors() -> set[str]:
    text = GUIDE_PATH.read_text()
    return {
        _github_anchor(m.group(1))
        for m in re.finditer(r"(?m)^#{1,6}\s+(.*)$", text)
    }


def _alerts(file_base: str) -> list[dict]:
    doc = yaml.safe_load((ALERTS_DIR / f"{file_base}.rules.yml").read_text())
    return [r for g in doc["groups"] for r in g["rules"]]


def test_all_action_surface_alert_files_exist():
    for fb in ACTION_SURFACE_FILES:
        assert (ALERTS_DIR / f"{fb}.rules.yml").is_file(), f"missing alert file: {fb}"


def test_every_action_surface_alert_runbook_anchor_resolves():
    anchors = _guide_anchors()
    broken: list[str] = []
    total = 0
    for fb in ACTION_SURFACE_FILES:
        for r in _alerts(fb):
            total += 1
            url = r.get("annotations", {}).get("runbook_url", "")
            assert url, f"{fb}: alert {r['alert']} has no runbook_url"
            frag = url.split("#", 1)[1] if "#" in url else ""
            assert frag, f"{fb}: alert {r['alert']} runbook_url has no anchor"
            if frag not in anchors:
                broken.append(f"{fb}:{r['alert']} -> #{frag}")
    assert not broken, (
        f"{len(broken)}/{total} action-surface alert runbook anchors do not "
        f"resolve to a heading in {GUIDE_PATH.name}:\n" + "\n".join(broken)
    )


def test_each_action_surface_alert_section_has_meaning_and_fix():
    """The resolved section must actually help the operator: a heading
    alone is not a runbook. Require the Meaning + Fix scaffold under each
    alert's section."""
    text = GUIDE_PATH.read_text()
    # Map heading-anchor -> the block of text until the next heading.
    blocks: dict[str, str] = {}
    parts = re.split(r"(?m)^(#{2,6}\s+.*)$", text)
    # parts: [pre, heading1, body1, heading2, body2, ...]
    for i in range(1, len(parts), 2):
        heading = parts[i].lstrip("#").strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        blocks[_github_anchor(heading)] = body
    missing: list[str] = []
    for fb in ACTION_SURFACE_FILES:
        for r in _alerts(fb):
            frag = r.get("annotations", {}).get("runbook_url", "").split("#", 1)[-1]
            body = blocks.get(frag, "")
            if "**Meaning:**" not in body or "**Fix:**" not in body:
                missing.append(f"{fb}:{r['alert']}")
    assert not missing, (
        "action-surface runbook sections missing Meaning/Fix scaffold:\n"
        + "\n".join(missing)
    )
