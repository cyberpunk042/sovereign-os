"""Scratch-state activation must never reach host mutation commands."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProfileSwitchIsolation(unittest.TestCase):
    def test_scratch_state_fails_before_host_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            calls = scratch / "host-calls"
            binaries = scratch / "bin"
            binaries.mkdir()
            for name in ("systemctl", "sudo", "nvidia-smi", "install", "rsync"):
                executable = binaries / name
                executable.write_text(
                    '#!/bin/sh\nprintf "%s\\n" "$0" >> "$TEST_HOST_CALLS"\nexit 99\n'
                )
                executable.chmod(0o755)
            env = dict(os.environ, SOVEREIGN_OS_STATE_DIR=str(scratch / "state"),
                       TEST_HOST_CALLS=str(calls),
                       PATH=str(binaries) + os.pathsep + os.environ["PATH"])
            for profile in ("as-deployed", "qwythos-dual-memory", "qwen38-flash-next-256k"):
                result = subprocess.run(
                    ["bash", str(ROOT / "scripts/sovereign-osctl"), "trinity", "profile", "switch", profile],
                    env=env, capture_output=True, text=True, timeout=20,
                )
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("refusing live profile activation", result.stdout + result.stderr)
                self.assertFalse(calls.exists())
                self.assertFalse((scratch / "state").exists())
