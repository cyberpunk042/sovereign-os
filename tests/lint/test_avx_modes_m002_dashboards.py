"""The avx-modes panel carries all 9 M002 dashboard surfaces (bucket 4).

The milestone lists 9 `dashboard`-type features (F00090/095/108/118/128/137/144/
153/162). Each has an operator-facing surface on the /avx-modes cockpit panel.
This pins that none can be silently dropped, and that the compute mirrors
(round engine + FNV-1a fingerprint) are wired into the page.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PANEL = REPO / "webapp" / "avx-modes" / "index.html"

# (feature id, a stable marker that must appear in the panel)
SURFACES = [
    ("F00090", "Lane fields (M00012"),
    ("F00095", "cw-fields"),                 # control-word bit-layout inspector
    ("F00108", "per-lane heatmap (M00015"),
    ("F00118", "cw-lut"),                    # 64-entry LUT inspector
    ("F00128", "DNA visualizer (M00018"),
    ("F00137", "ZMM layout assignment (M00019"),
    ("F00144", "step timeline (M00020"),
    ("F00153", "Shift-cost comparison (M00021"),
    ("F00162", "Rule-word width comparison (M00022"),
]


def test_panel_present():
    assert PANEL.is_file(), f"missing {PANEL}"


def test_all_nine_m002_dashboard_surfaces_present():
    html = PANEL.read_text(encoding="utf-8")
    missing = [f"{fid} ({marker!r})" for fid, marker in SURFACES if marker not in html]
    assert not missing, (
        "avx-modes panel is missing M002 dashboard surface(s): " + ", ".join(missing)
    )


def test_compute_mirrors_are_wired():
    html = PANEL.read_text(encoding="utf-8")
    # the round engine + fingerprint mirrors must be inline (the surfaces compute
    # live from the same bit-logic as the crate/CLI, not static mockups)
    for marker in ("function roundUpdate", "function laneFingerprint",
                   "function extractFeatures", "function advanceRng"):
        assert marker in html, f"panel lost its compute mirror: {marker}"


def test_no_aggressive_word_break():
    # cousin of test_text_wrap_contract — the new viz uses overflow-wrap:anywhere
    html = PANEL.read_text(encoding="utf-8")
    assert "word-break:break-all" not in html.replace(" ", "")


# M007 + M008 surfaces (the branch scheduler + AVX-512 cheats)
M78_SURFACES = [
    ("F00605", "VPTERNLOG fuse-policy (M00114"),
    ("F00615", "VPCOMPRESS sparse→dense (M00116"),
    ("M007", "M007 8-step branch loop (E0052"),
    ("F00623", "Token-law bitset (M00117"),
    ("M00122", "Bloom overlap (M00122"),
    ("M00113", "Bitfields-as-microcode (M00113"),
    ("M085-T1", "T1 VNNI INT8 dot (M085"),
    ("M085-T2", "T2 attention-mask fuse (M085"),
]


def test_m007_m008_surfaces_present():
    html = PANEL.read_text(encoding="utf-8")
    missing = [f"{fid} ({marker!r})" for fid, marker in M78_SURFACES if marker not in html]
    assert not missing, "avx-modes panel is missing M007/M008 surface(s): " + ", ".join(missing)
