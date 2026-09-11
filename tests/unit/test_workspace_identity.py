"""SDD-1000 workspace-authority contract."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE = Path(__file__).resolve().parents[2] / "scripts/openclaw/workspace_identity.py"
SPEC = importlib.util.spec_from_file_location("workspace_identity", MODULE)
assert SPEC and SPEC.loader
workspace_identity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workspace_identity)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sovereign-os"
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


def test_identity_uses_git_toplevel_for_a_nested_project_path(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    nested = repo / "profiles" / "orchestration"
    nested.mkdir(parents=True)
    monkeypatch.setattr(workspace_identity, "_git_toplevel", lambda _: repo)

    got = workspace_identity.workspace_identity(nested)

    assert got["repo_root"] == str(repo)
    assert got["write_root"] == str(repo)
    assert len(got["identity_digest"]) == 64


def test_resolve_write_records_prewrite_digest_and_never_mutates(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    target = repo / "profiles" / "profile.yaml"
    target.parent.mkdir()
    target.write_text("before\n", encoding="utf-8")
    monkeypatch.setattr(workspace_identity, "_git_toplevel", lambda _: repo)

    got = workspace_identity.resolve_write(repo, target)

    assert got["resolved_path"] == str(target)
    assert got["prewrite"]["exists"] is True
    assert got["prewrite"]["size_bytes"] == len("before\n")
    assert target.read_text(encoding="utf-8") == "before\n"


def test_shadow_workspace_target_is_rejected_even_when_a_matching_file_exists(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    shadow = tmp_path / "openclaw-workspace"
    shadow.mkdir()
    target = shadow / "profiles" / "orchestration" / "qwythos-three-card.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("", encoding="utf-8")
    monkeypatch.setattr(workspace_identity, "_git_toplevel", lambda _: repo)
    monkeypatch.setattr(workspace_identity, "_shadow_root", lambda: shadow)

    with pytest.raises(workspace_identity.WorkspaceError, match="shadow-workspace"):
        workspace_identity.resolve_write(repo, target)


def test_outside_path_and_non_regular_target_are_rejected(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    outside = tmp_path / "elsewhere.yaml"
    directory = repo / "profiles"
    directory.mkdir()
    monkeypatch.setattr(workspace_identity, "_git_toplevel", lambda _: repo)

    with pytest.raises(workspace_identity.WorkspaceError, match="outside-write-root"):
        workspace_identity.resolve_write(repo, outside)
    with pytest.raises(workspace_identity.WorkspaceError, match="not a regular file"):
        workspace_identity.resolve_write(repo, directory)
