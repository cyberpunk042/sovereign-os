import runpy
import unittest
from pathlib import Path


ensure = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                           "scripts/inference/sync-openclaw-models.py"))["_ensure_compaction_defaults"]


class CompactionDefaultsTests(unittest.TestCase):
    def test_unconfigured_install_gets_chunked_recovery(self):
        cfg, changes = {}, []
        ensure(cfg, changes)
        compaction = cfg["agents"]["defaults"]["compaction"]
        self.assertEqual(compaction["mode"], "safeguard")
        self.assertNotIn("midTurnPrecheck", compaction)
        self.assertTrue(compaction["notifyUser"])
        self.assertEqual(len(changes), 2)
        ensure(cfg, changes)
        self.assertEqual(len(changes), 2)

    def test_operator_overrides_and_model_limits_are_preserved(self):
        cfg = {"agents": {"defaults": {"compaction": {
            "mode": "default", "notifyUser": False,
            "midTurnPrecheck": {"enabled": False}, "keepRecentTokens": 12000,
        }}}, "models": {"contextWindow": 65536}}
        changes = []
        ensure(cfg, changes)
        self.assertEqual(changes, [])
        self.assertEqual(cfg["models"]["contextWindow"], 65536)
        self.assertEqual(cfg["agents"]["defaults"]["compaction"]["keepRecentTokens"], 12000)


if __name__ == "__main__":
    unittest.main()
