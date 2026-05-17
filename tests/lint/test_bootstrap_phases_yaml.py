"""tests/lint/test_bootstrap_phases_yaml.py — R202 canonical phase
table schema lint.

config/bootstrap/phases.yaml is the canonical source for the master
spec § 12 5-phase pipeline (consumed by scripts/bootstrap/phases.sh
and scripts/bootstrap/run.sh via lib/load-phases.py).

This lint asserts the YAML's invariants so drift can't slip in:
  - exactly 5 phases, ids I..V in chronological order
  - every artifact path is a real file in-repo
  - no '|' character anywhere (the loader pipe-delimits)
  - non-empty name + description per phase
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
YAML_PATH = REPO_ROOT / "config" / "bootstrap" / "phases.yaml"
EXPECTED_IDS = ["I", "II", "III", "IV", "V"]


class PhasesYamlLint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with YAML_PATH.open() as fh:
            cls.doc = yaml.safe_load(fh)

    def test_top_level_phases_list(self) -> None:
        self.assertIn("phases", self.doc)
        self.assertIsInstance(self.doc["phases"], list)
        self.assertEqual(len(self.doc["phases"]), 5)

    def test_ids_match_chronological_master_spec(self) -> None:
        ids = [p["id"] for p in self.doc["phases"]]
        self.assertEqual(
            ids, EXPECTED_IDS,
            "master spec § 12 mandates I..V chronological ordering",
        )

    def test_each_phase_has_name_description_artifacts(self) -> None:
        for p in self.doc["phases"]:
            self.assertTrue(p.get("name"), f"phase {p['id']} missing name")
            self.assertTrue(p.get("description"), f"phase {p['id']} missing description")
            self.assertIsInstance(p.get("artifacts"), list)
            self.assertGreater(
                len(p["artifacts"]), 0,
                f"phase {p['id']} has no artifacts",
            )

    def test_no_pipe_in_any_field(self) -> None:
        # Loader pipe-delimits — a '|' anywhere corrupts the stream.
        for p in self.doc["phases"]:
            for field in (p["id"], p["name"], p["description"]):
                self.assertNotIn("|", field, f"'|' in {p['id']} field: {field}")
            for art in p["artifacts"]:
                self.assertNotIn("|", art, f"'|' in artifact path: {art}")

    def test_every_artifact_path_exists(self) -> None:
        for p in self.doc["phases"]:
            for art in p["artifacts"]:
                fp = REPO_ROOT / art
                self.assertTrue(
                    fp.exists(),
                    f"phase {p['id']} references missing artifact: {art}",
                )

    def test_preconditions_and_postconditions_present(self) -> None:
        # R203 — every phase carries pre/post-condition lists.
        for p in self.doc["phases"]:
            self.assertIsInstance(
                p.get("preconditions"), list,
                f"phase {p['id']} missing preconditions list",
            )
            self.assertGreater(
                len(p["preconditions"]), 0,
                f"phase {p['id']} preconditions is empty",
            )
            self.assertIsInstance(
                p.get("postconditions"), list,
                f"phase {p['id']} missing postconditions list",
            )
            self.assertGreater(
                len(p["postconditions"]), 0,
                f"phase {p['id']} postconditions is empty",
            )

    def test_no_duplicate_artifacts_within_phase(self) -> None:
        for p in self.doc["phases"]:
            self.assertEqual(
                len(p["artifacts"]), len(set(p["artifacts"])),
                f"phase {p['id']} has duplicate artifacts",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
