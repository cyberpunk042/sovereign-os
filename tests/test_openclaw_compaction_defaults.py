import runpy
import unittest
from pathlib import Path
import yaml


ensure = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                           "scripts/inference/sync-openclaw-models.py"))["_ensure_compaction_defaults"]


class CompactionDefaultsTests(unittest.TestCase):
    def test_profile_switch_refreshes_cached_gateway_context(self):
        root = Path(__file__).resolve().parents[1]
        ctl = (root / "scripts/sovereign-osctl").read_text()
        self.assertIn('log_info "  refreshing GPU routes and served context limits..."', ctl)
        applier = (root / "scripts/iac/assets/gpu-route-apply.sh").read_text()
        self.assertNotIn('already registered (${_ep})"; continue', applier)

    def test_oracle_profile_has_room_for_tool_heavy_runs(self):
        path = Path(__file__).resolve().parents[1] / "profiles/orchestration/dual-agent-autocomplete.yaml"
        profile = yaml.safe_load(path.read_text())["orchestration_profile"]
        tiers = {a["tier"]: a for a in profile["allocations"]}
        self.assertEqual(tiers["oracle"]["max_model_len"], 131072)
        self.assertEqual(tiers["oracle"]["max_output_tokens"], 8192)
        self.assertEqual(profile["context_budget"]["initial_tokens"]["cuda:0"], 131072)
        self.assertEqual(tiers["logic"]["max_model_len"], 32768)
        self.assertTrue(tiers["embed"]["active"])
        self.assertTrue(tiers["rerank"]["active"])

    def test_unconfigured_install_gets_chunked_recovery(self):
        cfg, changes = {}, []
        ensure(cfg, changes)
        compaction = cfg["agents"]["defaults"]["compaction"]
        self.assertEqual(compaction["mode"], "safeguard")
        self.assertTrue(compaction["midTurnPrecheck"]["enabled"])
        self.assertEqual(compaction["keepRecentTokens"], 8000)
        self.assertEqual(compaction["recentTurnsPreserve"], 0)
        self.assertTrue(compaction["notifyUser"])
        self.assertEqual(len(changes), 5)
        ensure(cfg, changes)
        self.assertEqual(len(changes), 5)

    def test_operator_overrides_and_model_limits_are_preserved(self):
        cfg = {"agents": {"defaults": {"compaction": {
            "mode": "default", "notifyUser": False,
            "midTurnPrecheck": {"enabled": False}, "keepRecentTokens": 12000,
            "recentTurnsPreserve": 2,
        }}}, "models": {"contextWindow": 65536}}
        changes = []
        ensure(cfg, changes)
        self.assertEqual(changes, [])
        self.assertEqual(cfg["models"]["contextWindow"], 65536)
        self.assertEqual(cfg["agents"]["defaults"]["compaction"]["keepRecentTokens"], 12000)


if __name__ == "__main__":
    unittest.main()
