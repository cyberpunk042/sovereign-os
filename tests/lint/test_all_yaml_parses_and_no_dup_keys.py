"""tests/lint/test_all_yaml_parses_and_no_dup_keys.py — repo-wide YAML
parse + duplicate-key gate.

sovereign-os ships ~30 YAML documents that drive runtime behavior:
build/runtime profiles (`profiles/`, `profiles/mixins/`,
`profiles/runtime/`), JSON-schema mirrors (`schemas/`), cloud-init seeds
(`config/cloud-init/`), the bootstrap phase/verify tables
(`config/bootstrap/`), the whitelabel manifest, the model registry, and
the GitHub workflows. A handful of them have content-specific lints
(bootstrap phases/verify-grid, whitelabel default content) — but most had
NO gate ensuring they even parse, and NONE guarded against duplicate
mapping keys.

Why this matters: a YAML doc that fails to parse does not crash its
consumer loudly — a malformed profile/mixin/cloud-init seed is silently
skipped or falls back to a default, so an operator's intended setting
quietly disappears. A DUPLICATE mapping key is worse: PyYAML's default
loader accepts it and keeps only the LAST value, dropping the earlier one
with no error — so two `kernel:` or two `runtime:` keys silently collapse
to one. This gate makes both land RED:

  - every YAML document must parse (covers single- and multi-doc files);
  - no mapping may declare the same key twice (custom strict loader).

Uses only PyYAML (CI installs `pyyaml`); no extra lint dependency.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
# Directories that never hold source-of-truth YAML we author.
_SKIP_DIRS = {"target", ".git", "node_modules", ".venv", "venv", "dist", "build"}
_YAML_SUFFIXES = (".yaml", ".yml", ".yml.template", ".yaml.template")


class DuplicateKeyError(Exception):
    pass


class _StrictUniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys instead of
    silently keeping the last one."""


def _construct_mapping_no_dups(loader, node, deep=False):
    seen: set = set()
    for key_node, _value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise DuplicateKeyError(
                f"duplicate key {key!r} at {key_node.start_mark}"
            )
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_StrictUniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_no_dups,
)


def _discover_yaml_files() -> list[Path]:
    out: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(REPO_ROOT).parts):
            continue
        if path.name.endswith(_YAML_SUFFIXES):
            out.append(path)
    return sorted(out)


class AllYamlParsesAndNoDupKeys(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.files = _discover_yaml_files()

    def test_at_least_one_yaml_discovered(self) -> None:
        # Guard against a glob/skip regression silently emptying the set
        # and making this whole gate a no-op.
        self.assertGreater(
            len(self.files), 0,
            "no YAML files discovered — discovery logic regressed",
        )

    def test_all_yaml_parses_and_has_no_duplicate_keys(self) -> None:
        failures: list[str] = []
        for fp in self.files:
            rel = fp.relative_to(REPO_ROOT)
            try:
                with fp.open(encoding="utf-8") as fh:
                    list(yaml.load_all(fh, Loader=_StrictUniqueKeyLoader))
            except (DuplicateKeyError, yaml.YAMLError, OSError) as e:
                failures.append(f"  {rel}: {str(e).splitlines()[0]}")
        self.assertEqual(
            failures, [],
            "YAML parse / duplicate-key failures:\n" + "\n".join(failures),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
