from pathlib import Path
import runpy
import tempfile
import unittest

resolve = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/models/hf-auth.py"))["token_environment"]


class HFAuthTests(unittest.TestCase):
    def test_precedence(self):
        self.assertEqual(resolve({"HF_TOKEN": "test-primary", "SOVEREIGN_OS_HF_TOKEN": "test-alias"})["HF_TOKEN"], "test-primary")
        self.assertEqual(resolve({"HUGGINGFACE_HUB_TOKEN": "test-legacy"})["HF_TOKEN"], "test-legacy")

    def test_private_file_and_no_shell_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.env"
            path.write_text('SOVEREIGN_OS_HF_TOKEN="test-file"\n')
            path.chmod(0o600)
            env = {"SOVEREIGN_OS_HF_ENV_FILE": str(path)}
            self.assertEqual(resolve(env)["HF_TOKEN"], "test-file")
            path.write_text('HF_TOKEN="$(false)"\n')
            self.assertEqual(resolve(env)["HF_TOKEN"], "$(false)")
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                resolve(env)

    def test_missing_file_preserves_sdk_login(self):
        self.assertNotIn("HF_TOKEN", resolve({"SOVEREIGN_OS_HF_ENV_FILE": "/nonexistent/hf-test.env"}))
