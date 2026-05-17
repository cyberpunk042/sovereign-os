"""tests/lint/test_bootstrap_verify_grid_yaml.py — R207 verify-grid schema lint.

config/bootstrap/verify-grid.yaml is the canonical metadata source for
the master spec § 22 6-check operational grid (consumed by
scripts/bootstrap/verify.sh via lib/load-verify-grid.py and by
lib/render-verify-grid-md.py).

Lint enforces the YAML invariants the consumers depend on:
  - exactly 6 checks with IDs 01..06 in order
  - every required field present (id, name, master_spec_section,
    checks_what, skip_when)
  - tools_required is a list (may be empty)
  - no '|' character anywhere (loader pipe-delimits)
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
YAML_PATH = REPO_ROOT / "config" / "bootstrap" / "verify-grid.yaml"
EXPECTED_IDS = ["01", "02", "03", "04", "05", "06"]
REQUIRED_FIELDS = ("id", "name", "master_spec_section", "checks_what", "skip_when")


class VerifyGridYamlLint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with YAML_PATH.open() as fh:
            cls.doc = yaml.safe_load(fh)
        cls.checks = cls.doc["verify_grid"]["checks"]

    def test_six_checks_in_order(self) -> None:
        ids = [c["id"] for c in self.checks]
        self.assertEqual(ids, EXPECTED_IDS)

    def test_required_fields_present(self) -> None:
        for c in self.checks:
            for field in REQUIRED_FIELDS:
                self.assertIn(field, c, f"check {c.get('id')} missing {field}")
                self.assertTrue(c[field], f"check {c['id']} {field} is empty")

    def test_tools_required_is_list(self) -> None:
        for c in self.checks:
            tools = c.get("tools_required", [])
            self.assertIsInstance(
                tools, list, f"check {c['id']} tools_required not a list",
            )

    def test_no_pipe_in_any_field(self) -> None:
        for c in self.checks:
            for field in REQUIRED_FIELDS:
                self.assertNotIn(
                    "|", c[field], f"'|' in {c['id']}.{field}: {c[field]}",
                )

    def test_spec_section_cites_section_22(self) -> None:
        # Every check must cite the master spec § 22 sub-anchor.
        for c in self.checks:
            self.assertIn(
                "§ 22", c["master_spec_section"],
                f"check {c['id']} master_spec_section missing § 22 anchor",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
