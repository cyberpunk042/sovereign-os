"""SDD-303 — Warp management reality loop + real controls + gallery.

Covers the warp_manage.py surfaces the cockpit now depends on:
  * shared render store resolution (env > machine > per-user) — the fix for
    the root read-daemon and the user exec-rail disagreeing about reality,
  * structured render opts (--device/--quality/--look/--time) validated by
    whitelist, with a hard error (never passthrough) on a bad value,
  * the gallery readers (list_renders / render_image) and their path discipline,
  * status freshness (catalog rev vs checkout rev → fresh/stale/unknown),
  * warp sync guardrails (https-GitHub source only; refuses dirty ground).
"""
import importlib.util
import json
from pathlib import Path


def module():
    path = Path(__file__).resolve().parents[2] / "scripts/warp/warp_manage.py"
    spec = importlib.util.spec_from_file_location("warp_manage_sdd303", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── shared render store ──────────────────────────────────────────────────────

def test_store_env_override_wins(monkeypatch, tmp_path):
    mod = module()
    monkeypatch.setenv("SOVEREIGN_WARP_RENDER_STORE", str(tmp_path / "custom"))
    assert mod.render_store() == tmp_path / "custom"


def test_machine_store_beats_per_user_when_present(monkeypatch, tmp_path):
    mod = module()
    monkeypatch.delenv("SOVEREIGN_WARP_RENDER_STORE", raising=False)
    machine = tmp_path / "var-lib-warp-renders"
    machine.mkdir()
    monkeypatch.setattr(mod, "MACHINE_RENDER_STORE", machine)
    assert mod.render_store() == machine


def test_falls_back_to_user_store(monkeypatch, tmp_path):
    mod = module()
    monkeypatch.delenv("SOVEREIGN_WARP_RENDER_STORE", raising=False)
    monkeypatch.setattr(mod, "MACHINE_RENDER_STORE", tmp_path / "absent")
    assert ".local/state" in str(mod.render_store())


# ── structured render options ────────────────────────────────────────────────

def test_opts_parsed_into_runner_args_and_metadata(monkeypatch, tmp_path):
    mod = module()
    monkeypatch.setattr(mod, "render_store", lambda: tmp_path)
    monkeypatch.setattr(mod, "shaders_root", lambda: tmp_path)
    monkeypatch.setattr(mod, "_validate_scene", lambda scene: None)
    seen = {}

    def runner(name, args, *rest):
        seen["args"] = args
        Path(args[args.index("--out") + 1]).write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        return 0

    monkeypatch.setattr(mod, "_run_runner", runner)
    rc = mod.cmd_render("atom", False,
                        ["--device", "cuda", "--quality", "ultra",
                         "--look", "cinematic", "--time", "2.5"])
    assert rc == 0
    a = seen["args"]
    assert a[:10] == ["--scene", "atom", "--device", "cuda", "--quality", "ultra",
                      "--look", "cinematic", "--time", "2.5"]
    latest = mod.latest_render()
    assert latest["opts"] == {"device": "cuda", "quality": "ultra",
                              "look": "cinematic", "time": "2.5"}


def test_bad_option_is_error_not_passthrough(monkeypatch):
    mod = module()
    monkeypatch.setattr(mod, "_validate_scene", lambda scene: None)
    calls = []
    monkeypatch.setattr(mod, "_run_runner", lambda *a: calls.append(a) or 0)
    assert mod.cmd_render("atom", False, ["--device", "quantum"]) == 2
    assert mod.cmd_render("atom", False, ["--time", "yesterday"]) == 2
    assert mod.cmd_render("atom", False, ["--look"]) == 2
    assert calls == []  # nothing reached the runner


def test_unknown_args_keep_legacy_passthrough(monkeypatch, tmp_path):
    mod = module()
    monkeypatch.setattr(mod, "_validate_scene", lambda scene: None)
    monkeypatch.setattr(mod, "shaders_root", lambda: tmp_path)
    seen = []
    monkeypatch.setattr(mod, "_run_runner",
                        lambda name, args, *rest: seen.append(args) or 0)
    assert mod.cmd_render("atom", False, ["--gif", "x.gif"]) == 0
    assert seen == [["--scene", "atom", "--gif", "x.gif"]]


# ── gallery readers ──────────────────────────────────────────────────────────

def _seed(mod, tmp_path, scene, ident, opts=None):
    meta = {"id": ident, "scene": scene,
            "created_at": f"2026-10-0{ident[-1]}T00:00:00+00:00"}
    if opts:
        meta["opts"] = opts
    (tmp_path / f"{ident}.json").write_text(json.dumps(meta))
    (tmp_path / f"{ident}.png").write_bytes(b"\x89PNG\r\n\x1a\nimg")


def test_list_renders_sorted_newest_first_with_guards(monkeypatch, tmp_path):
    mod = module()
    monkeypatch.setattr(mod, "render_store", lambda: tmp_path)
    _seed(mod, tmp_path, "atom", "a" * 32)
    _seed(mod, tmp_path, "alien", "b" * 32, opts={"device": "cpu"})
    (tmp_path / "junk.json").write_text(json.dumps({"id": "../escape"}))       # bad id
    (tmp_path / ("c" * 32 + ".json")).write_text(json.dumps({"id": "c" * 32, "scene": "ghost"}))  # no PNG
    rs = mod.list_renders()
    assert [r["scene"] for r in rs] == ["alien", "atom"]  # created_at sort
    assert rs[0]["opts"]["device"] == "cpu"
    assert all(r["bytes"] > 0 for r in rs)


def test_render_image_rejects_bad_ids_and_symlinks(monkeypatch, tmp_path):
    mod = module()
    monkeypatch.setattr(mod, "render_store", lambda: tmp_path)
    assert mod.render_image("../secret") is None
    assert mod.render_image("") is None
    _seed(mod, tmp_path, "atom", "d" * 32)
    assert mod.render_image("d" * 32)[:4] == b"\x89PNG"
    target = tmp_path / ("e" * 32 + ".png")
    target.symlink_to(tmp_path / "outside.png")
    (tmp_path / "outside.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    assert mod.render_image("e" * 32) is None


def test_legacy_manifest_less_pngs_are_recovered(monkeypatch, tmp_path):
    mod = module()
    monkeypatch.setattr(mod, "render_store", lambda: tmp_path)
    (tmp_path / "atom-987e37da.png").write_bytes(b"\x89PNG\r\n\x1a\nold")
    (tmp_path / "not-a-render.png").write_bytes(b"\x89PNG\r\n\x1a\nx")
    rs = mod.list_renders()
    assert len(rs) == 1  # strict filename shape, not any PNG
    entry = rs[0]
    assert entry["scene"] == "atom" and entry["id_partial"] is True
    assert mod.render_image_by_name("atom-987e37da.png")[:4] == b"\x89PNG"
    assert mod.render_image_by_name("../outside.png") is None
    assert mod.render_image_by_name("not-a-render.png") is None


# ── status freshness ─────────────────────────────────────────────────────────

def test_status_freshness_states(monkeypatch, capsys):
    mod = module()
    monkeypatch.setattr(mod, "load_catalog",
                        lambda: {"scenes": [], "libs": [], "project": "p",
                                 "source_git_rev": "1" * 40})
    monkeypatch.setattr(mod, "shaders_root", lambda: Path("/x"))
    monkeypatch.setattr(mod, "checkout_rev", lambda r: "1" * 40)
    mod.cmd_status(True)
    assert json.loads(capsys.readouterr().out)["catalog_freshness"] == "fresh"
    monkeypatch.setattr(mod, "checkout_rev", lambda r: "2" * 40)
    mod.cmd_status(True)
    assert json.loads(capsys.readouterr().out)["catalog_freshness"] == "stale"
    monkeypatch.setattr(mod, "checkout_rev", lambda r: None)
    mod.cmd_status(True)
    assert json.loads(capsys.readouterr().out)["catalog_freshness"] == "unknown"


# ── sync guardrails ──────────────────────────────────────────────────────────

def test_sync_refuses_non_github_source(monkeypatch, capsys):
    mod = module()
    monkeypatch.setattr(mod, "load_catalog", lambda: {"source": "git@evil.example:x/y"})
    assert mod.cmd_sync(None, False) == 2
    assert "refusing sync" in capsys.readouterr().err


def test_sync_refuses_existing_non_git_dir(monkeypatch, tmp_path, capsys):
    mod = module()
    monkeypatch.setattr(mod, "load_catalog",
                        lambda: {"source": "https://github.com/o/r"})
    dest = tmp_path / "occupied"
    dest.mkdir()
    (dest / "file").write_text("x")
    assert mod.cmd_sync(str(dest), False) == 2
    assert "not a git checkout" in capsys.readouterr().err
