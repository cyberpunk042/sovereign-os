#!/usr/bin/env python3
"""sync-app-shell.py — SDD-067 app-shell distributor (the 5th canonical
per-panel snippet).

Injects the canonical app-shell block (webapp/_shared/app-shell-snippet.html,
between the APP-SHELL:BEGIN / APP-SHELL:END markers, inclusive) as the first
child of each adopted panel's <body>. Idempotent: a panel that already carries
a block gets it REPLACED, so re-running is a no-op when nothing changed.

Per the sovereignty-clean doctrine there is no shared runtime asset — the block
is DUPLICATED verbatim into every adopted panel and enforced identical by
tests/lint/test_app_shell_contract.py.

Mutation discipline (mirrors the repo's other mutating tools):
  * DRY-RUN by default — prints WOULD; requires --apply to write.
  * Reports WOULD/DID/SKIP <path>: <reason> per panel.
  * --check verifies every adopted panel's block matches canonical
    (exit 1 on drift) and writes nothing.

Usage:
  python3 scripts/webapp/sync-app-shell.py                 # dry-run over the adopted list
  python3 scripts/webapp/sync-app-shell.py --apply         # write the adopted list
  python3 scripts/webapp/sync-app-shell.py --panel d-04-costs --apply
  python3 scripts/webapp/sync-app-shell.py --check         # CI-style drift check
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP = REPO_ROOT / "webapp"
SNIPPET = WEBAPP / "_shared" / "app-shell-snippet.html"

BEGIN = "<!-- APP-SHELL:BEGIN M067 -->"
END = "<!-- APP-SHELL:END M067 -->"

# Panels that have adopted the app-shell. Grow this list one (or a few) at a
# time; only listed panels are touched — the rest stay exactly as they are.
# Keep in lockstep with tests/lint/test_app_shell_contract.py.
ADOPTED_PANELS = [
    "course",
    "anti-minimization-audit", "auditor", "auth-tier", "brain", "build-configurator",
    "compliance", "cpu-features", "d-01-active-sessions", "d-02-profile-choices",
    "d-03-model-health", "d-04-costs", "d-05-traces", "d-06-pending-approvals",
    "d-07-memory-changes", "d-08-rollback-points", "d-09-hardware-pressure",
    "d-10-eval-history", "d-11-adapter-status", "d-12-networking",
    "d-13-filesystem-grants", "d-14-capability-tokens", "d-15-sandboxes",
    "d-16-audit", "d-17-quarantine", "d-18-trust-scores",
    "d-19-super-model-manifest", "d-20-peace-machine-health",
    "d-21-lm-orchestration", "d-22-lm-status-operability", "d-23-models-catalog",
    "d-24-cpu-features", "d-25-selfdef-management", "code-console", "doc-coverage",
    "edge-firewall", "emulate", "flash", "global-history", "master-dashboard",
    "models-catalog", "network-edge", "orchestration", "personalization",
    "profile-generation", "router", "runtime-modes", "selfdef-management",
    "science", "surface-map", "trinity", "ups", "ux-design-audit", "weaver",
    "feature-test-lab",
]

_BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
# Anchor to a real <body> tag at the start of a line (optionally indented) so we
# never match a literal "<body>" that appears inside a <head> comment/string.
_BODY_RE = re.compile(r"^[ \t]*<body[^>]*>", re.IGNORECASE | re.MULTILINE)


def canonical_block() -> str:
    src = SNIPPET.read_text(encoding="utf-8")
    i, j = src.find(BEGIN), src.find(END)
    if i < 0 or j < 0:
        sys.exit(f"FATAL: markers not found in {SNIPPET}")
    return src[i : j + len(END)]


def _panel_path(slug: str) -> Path:
    return WEBAPP / slug / "index.html"


def render(html: str, block: str) -> tuple[str, str]:
    """Return (new_html, action). action ∈ replace|insert|unchanged."""
    if _BLOCK_RE.search(html):
        new = _BLOCK_RE.sub(lambda _m: block, html, count=1)
        return new, ("unchanged" if new == html else "replace")
    m = _BODY_RE.search(html)
    if not m:
        return html, "no-body"
    at = m.end()
    new = html[:at] + "\n" + block + html[at:]
    return new, "insert"


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync the app-shell block into adopted cockpit panels.")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--panel", action="append", default=None, help="panel slug (repeatable); default = the adopted list")
    ap.add_argument("--all", action="store_true", help="operate over the full adopted list")
    ap.add_argument("--check", action="store_true", help="verify blocks match canonical; write nothing; exit 1 on drift")
    args = ap.parse_args()

    block = canonical_block()
    targets = args.panel if args.panel else ADOPTED_PANELS

    drift, changed = [], 0
    for slug in targets:
        path = _panel_path(slug)
        if not path.is_file():
            print(f"SKIP {slug}: index.html not found")
            continue
        html = path.read_text(encoding="utf-8")

        if args.check:
            found = _BLOCK_RE.search(html)
            if not found:
                print(f"DRIFT {slug}: no app-shell block")
                drift.append(slug)
            elif found.group(0) != block:
                print(f"DRIFT {slug}: block differs from canonical")
                drift.append(slug)
            else:
                print(f"OK    {slug}")
            continue

        new, action = render(html, block)
        if action == "no-body":
            print(f"SKIP {slug}: no <body> tag")
            continue
        if action == "unchanged":
            print(f"SKIP {slug}: already current")
            continue
        changed += 1
        if args.apply:
            path.write_text(new, encoding="utf-8")
            print(f"DID  {action} {path.relative_to(REPO_ROOT)}")
        else:
            print(f"WOULD {action} {path.relative_to(REPO_ROOT)}")

    if args.check:
        if drift:
            print(f"\n{len(drift)} panel(s) drifted from canonical — run: python3 scripts/webapp/sync-app-shell.py --apply")
            return 1
        print("\nall adopted panels current.")
        return 0

    if not args.apply and changed:
        print(f"\n{changed} panel(s) WOULD change — re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
