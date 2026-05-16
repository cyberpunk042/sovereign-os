"""Unit test for R188 shared module-recommendation matrix
(scripts/hardware/lib/module-recommendations.py).

Pins the single source of truth that R185 + R186 both consume.
A change to the matrix must update this test — the test is the
operator-readable definition of the matrix.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/hardware/lib/module-recommendations.py"


@pytest.fixture(scope="module")
def modrec():
    spec = importlib.util.spec_from_file_location(
        "module_recommendations", str(MODULE_PATH)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- sain-01 profile ----------------------------------------------------------


def test_sain01_with_avx512_and_gpus_recommends_both(modrec):
    mods = modrec.recommend_modules("sain-01", has_avx512=True, gpu_count=2)
    assert mods == ["hardware-tune-cache", "bitnet-gpu-inference"]


def test_sain01_with_avx512_no_gpu_drops_bitnet(modrec):
    mods = modrec.recommend_modules("sain-01", has_avx512=True, gpu_count=0)
    assert mods == ["hardware-tune-cache"]


def test_sain01_without_avx512_recommends_nothing(modrec):
    mods = modrec.recommend_modules("sain-01", has_avx512=False, gpu_count=2)
    # Without AVX-512, neither hardware-tune-cache (needs VNNI per
    # selfdef module manifest) nor bitnet-gpu-inference (needs BF16)
    # would land. The matrix correctly returns empty.
    assert mods == []


# --- developer / headless profiles -------------------------------------------


def test_developer_with_avx512_recommends_tune_only(modrec):
    mods = modrec.recommend_modules("developer", has_avx512=True, gpu_count=2)
    # Developer profile never recommends bitnet-gpu-inference (the
    # operator may have a GPU for dev work but doesn't want
    # production-style ternary inference auto-applied).
    assert mods == ["hardware-tune-cache"]


def test_developer_without_avx512_recommends_nothing(modrec):
    mods = modrec.recommend_modules("developer", has_avx512=False, gpu_count=0)
    assert mods == []


def test_headless_with_avx512_recommends_tune_only(modrec):
    mods = modrec.recommend_modules("headless", has_avx512=True, gpu_count=0)
    assert mods == ["hardware-tune-cache"]


# --- minimal / old-workstation ------------------------------------------------


def test_minimal_recommends_nothing_regardless_of_hardware(modrec):
    assert modrec.recommend_modules("minimal", has_avx512=True, gpu_count=2) == []
    assert modrec.recommend_modules("minimal", has_avx512=False, gpu_count=0) == []


def test_old_workstation_recommends_nothing(modrec):
    assert modrec.recommend_modules("old-workstation", has_avx512=True, gpu_count=0) == []
    assert modrec.recommend_modules("old-workstation", has_avx512=False, gpu_count=0) == []


# --- error path ---------------------------------------------------------------


def test_unknown_profile_raises_value_error(modrec):
    with pytest.raises(ValueError, match="unknown profile"):
        modrec.recommend_modules("nonexistent", has_avx512=True, gpu_count=0)


# --- contract: VALID_PROFILES matches the matrix branches --------------------


def test_valid_profiles_constant_covers_all_branches(modrec):
    # Each profile in VALID_PROFILES must produce a valid result
    # (Optional empty list is fine; must NOT raise).
    for p in modrec.VALID_PROFILES:
        modrec.recommend_modules(p, has_avx512=True, gpu_count=2)
        modrec.recommend_modules(p, has_avx512=False, gpu_count=0)
