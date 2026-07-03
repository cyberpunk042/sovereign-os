"""tests/lint/test_root_ghostproxy_binding_contract.py — SDD-046 binding gate.

Locks the root-ghostproxy endpoint binding (proxy mode DISABLED, per the
operator directive 2026-07-03 verbatim: "Lets prepare root-ghostproxy for
sovereign-os usage, we will use use the repo without the proxy mode
enabled."):

  - both hooks exist + are executable (A3);
  - the mode is PINNED to endpoint in both hooks — never `auto`, never
    env-overridable (A2: SAIN-01's dual NICs would auto-promote to
    bridge, silently re-enabling the proxy half);
  - the install hook is triple-gated (report-only default; explicit
    CONFIRM env; SOVEREIGN_OS_DRY_RUN honored) and absent-tolerant;
  - the checkout dir is env-overridable (SOVEREIGN_OS_ROOT_GHOSTPROXY_DIR);
  - both hooks emit their Layer B metric families (A4);
  - the sain-01 profile wires the install hook at post_install_first_boot
    and the verify hook at post_install_recurrent with a schedule (A3);
  - SDD-046 exists and names both hook paths.

Why lint-tier: the binding consumes a SISTER repo's installer. A drifted
hook (mode unpinned, gate removed, profile de-wired) would not crash any
build — the node would just silently stop being AI-agent-safety-governed,
or worse, silently gain the proxy/IPS half the operator directed OFF.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_HOOK = REPO_ROOT / "scripts/hooks/post-install/root-ghostproxy-endpoint-install.sh"
VERIFY_HOOK = REPO_ROOT / "scripts/hooks/recurrent/root-ghostproxy-verify.sh"
SAIN01 = REPO_ROOT / "profiles/sain-01.yaml"
SDD_046 = REPO_ROOT / "docs/sdd/046-root-ghostproxy-endpoint-binding.md"


class RootGhostproxyBindingContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.install_src = INSTALL_HOOK.read_text(encoding="utf-8")
        cls.verify_src = VERIFY_HOOK.read_text(encoding="utf-8")
        cls.profile = yaml.safe_load(SAIN01.read_text(encoding="utf-8"))

    # --- A3: hooks exist + executable -------------------------------
    def test_install_hook_exists_and_executable(self):
        self.assertTrue(INSTALL_HOOK.is_file())
        self.assertTrue(os.access(INSTALL_HOOK, os.X_OK), "install hook must be executable")

    def test_verify_hook_exists_and_executable(self):
        self.assertTrue(VERIFY_HOOK.is_file())
        self.assertTrue(os.access(VERIFY_HOOK, os.X_OK), "verify hook must be executable")

    # --- A2: mode pinned to endpoint, never auto/env-overridable ----
    def test_mode_pinned_endpoint_in_both_hooks(self):
        for name, src in (("install", self.install_src), ("verify", self.verify_src)):
            self.assertIn('GHOSTPROXY_MODE="endpoint"', src,
                          f"{name} hook must pin GHOSTPROXY_MODE=endpoint")
            self.assertNotIn("SOVEREIGN_OS_GHOSTPROXY_MODE", src,
                             f"{name} hook must NOT make the mode env-overridable (SDD-046 A2)")
            self.assertNotIn("--mode auto", src,
                             f"{name} hook must never pass --mode auto")

    # --- triple-gate: report-only default + confirm + dry-run -------
    def test_install_hook_confirm_gated(self):
        self.assertIn("SOVEREIGN_OS_CONFIRM_GHOSTPROXY_INSTALL", self.install_src)
        self.assertIn('!= "YES"', self.install_src)

    def test_install_hook_honors_global_dry_run(self):
        self.assertIn("SOVEREIGN_OS_DRY_RUN", self.install_src)

    def test_install_hook_report_only_uses_upstream_dry_run(self):
        self.assertIn("--dry-run", self.install_src)

    def test_hooks_absent_tolerant(self):
        for name, src in (("install", self.install_src), ("verify", self.verify_src)):
            self.assertIn("emit_summary absent", src,
                          f"{name} hook must report (not fail) an absent checkout")

    # --- env-overridable checkout dir --------------------------------
    def test_checkout_dir_env_overridable(self):
        for src in (self.install_src, self.verify_src):
            self.assertIn("SOVEREIGN_OS_ROOT_GHOSTPROXY_DIR", src)

    # --- verify hook is observation, not remediation ------------------
    def test_verify_hook_read_only(self):
        self.assertIn("--check", self.verify_src)
        for mutating in ("--yes", "git merge", "systemctl restart"):
            self.assertNotIn(mutating, self.verify_src,
                             f"verify hook must stay read-only (found {mutating!r})")

    # --- A4: Layer B metrics ------------------------------------------
    def test_metric_families_emitted(self):
        self.assertIn("sovereign_os_ghostproxy_endpoint_install_result", self.install_src)
        self.assertIn("sovereign_os_ghostproxy_endpoint_install_last_run_timestamp", self.install_src)
        self.assertIn("sovereign_os_ghostproxy_endpoint_verify_result", self.verify_src)
        self.assertIn("sovereign_os_ghostproxy_endpoint_verify_last_run_timestamp", self.verify_src)

    # --- profile wiring ------------------------------------------------
    def test_sain01_wires_first_boot_install_hook(self):
        hooks = self.profile["hooks"]["post_install_first_boot"]
        entry = next((h for h in hooks if h["id"] == "root-ghostproxy-endpoint-install"), None)
        self.assertIsNotNone(entry, "sain-01 must wire root-ghostproxy-endpoint-install at first boot")
        self.assertEqual(entry["type"], "security")
        self.assertEqual(entry["script"],
                         "scripts/hooks/post-install/root-ghostproxy-endpoint-install.sh")

    def test_sain01_wires_recurrent_verify_hook(self):
        hooks = self.profile["hooks"]["post_install_recurrent"]
        entry = next((h for h in hooks if h["id"] == "root-ghostproxy-verify"), None)
        self.assertIsNotNone(entry, "sain-01 must wire root-ghostproxy-verify recurrent")
        self.assertEqual(entry["type"], "security")
        self.assertIn("schedule", entry)
        self.assertEqual(entry["script"],
                         "scripts/hooks/recurrent/root-ghostproxy-verify.sh")

    # --- SDD anchor ------------------------------------------------------
    def test_sdd_046_exists_and_names_both_hooks(self):
        self.assertTrue(SDD_046.is_file(), "SDD-046 must exist")
        sdd = SDD_046.read_text(encoding="utf-8")
        self.assertIn("root-ghostproxy-endpoint-install.sh", sdd)
        self.assertIn("root-ghostproxy-verify.sh", sdd)
        self.assertIn("--mode endpoint", sdd)


if __name__ == "__main__":
    unittest.main()
