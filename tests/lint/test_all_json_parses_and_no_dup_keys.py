"""tests/lint/test_all_json_parses_and_no_dup_keys.py — repo-wide JSON
parse + duplicate-key gate.

sovereign-os ships 21 hand-maintained JSON documents — 19 of them the
Grafana cockpit dashboards under `docs/observability/dashboards/`, plus
the `.mcp.json` server map and the claude-code-env template. The
dashboards are imported verbatim into Grafana; the metric-inventory lint
checks the README inventory, but NOTHING validated that the dashboard
JSON itself parses, and nothing guarded duplicate object keys.

Why duplicate keys matter: `json.load` silently keeps only the LAST value
for a repeated key, dropping the earlier one with no error. In a Grafana
dashboard a duplicate panel `"id"` or a doubled `"targets"`/`"title"` key
silently drops a panel or a query — the dashboard imports fine but renders
wrong, with no syntax error to catch it. This gate makes both land RED:

  - every JSON document must parse;
  - no object may declare the same key twice (object_pairs_hook guard).

Stdlib-only (`json`); runs in the existing `pytest tests/lint` layer.
Parallels test_all_yaml_parses_and_no_dup_keys.py.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SKIP_DIRS = {"target", ".git", "node_modules", ".venv", "venv", "dist", "build"}


class DuplicateKeyError(Exception):
    pass


def _no_dup_keys(pairs: list[tuple[str, object]]) -> dict:
    seen: set[str] = set()
    for key, _value in pairs:
        if key in seen:
            raise DuplicateKeyError(f"duplicate key {key!r}")
        seen.add(key)
    return dict(pairs)


def _discover_json_files() -> list[Path]:
    out: list[Path] = []
    for path in REPO_ROOT.rglob("*.json"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(REPO_ROOT).parts):
            continue
        out.append(path)
    return sorted(out)


class AllJsonParsesAndNoDupKeys(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.files = _discover_json_files()

    def test_at_least_one_json_discovered(self) -> None:
        self.assertGreater(
            len(self.files), 0,
            "no JSON files discovered — discovery logic regressed",
        )

    def test_all_json_parses_and_has_no_duplicate_keys(self) -> None:
        failures: list[str] = []
        for fp in self.files:
            rel = fp.relative_to(REPO_ROOT)
            try:
                with fp.open(encoding="utf-8") as fh:
                    json.load(fh, object_pairs_hook=_no_dup_keys)
            except (DuplicateKeyError, json.JSONDecodeError, OSError) as e:
                failures.append(f"  {rel}: {str(e).splitlines()[0]}")
        self.assertEqual(
            failures, [],
            "JSON parse / duplicate-key failures:\n" + "\n".join(failures),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
