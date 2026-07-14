"""Layer 2 — sovereign-os inference router request-body bounds.

Validates `parse_content_length()` from scripts/inference/router.py, the
guard that replaced the unguarded `int(self.headers.get("Content-Length", 0))`
+ unbounded `rfile.read(length)` in `_do_post_inner`:

- a malformed Content-Length header no longer crashes the handler (was an
  uncaught ValueError → 500 / dropped connection); it is a clean 400.
- an oversize Content-Length no longer forces an unbounded allocation
  (memory-DoS); it is a clean 413.

Per SDD-994.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "inference"))

router = pytest.importorskip("router")


# ----------- absent / empty body → length 0, no error -----------

def test_absent_header_is_zero_length():
    assert router.parse_content_length(None) == (0, None)


def test_empty_header_is_zero_length():
    assert router.parse_content_length("") == (0, None)


# ----------- valid body → length, no error -----------

def test_valid_length_passes_through():
    length, err = router.parse_content_length("42")
    assert length == 42
    assert err is None


def test_length_at_cap_is_allowed():
    length, err = router.parse_content_length(str(router._MAX_BODY))
    assert length == router._MAX_BODY
    assert err is None


# ----------- malformed header → 400, never a crash -----------

def test_non_numeric_header_is_400_not_crash():
    length, err = router.parse_content_length("not-a-number")
    assert length is None
    assert err is not None and err[0] == 400


def test_whitespace_garbage_header_is_400():
    length, err = router.parse_content_length("12x")
    assert length is None
    assert err[0] == 400


def test_negative_length_is_400():
    length, err = router.parse_content_length("-1")
    assert length is None
    assert err[0] == 400


# ----------- oversize header → 413, bounded -----------

def test_oversize_length_is_413():
    length, err = router.parse_content_length(str(router._MAX_BODY + 1))
    assert length is None
    assert err[0] == 413


def test_absurd_length_is_413_not_allocation():
    # A client claiming a 1 TiB body must be rejected before any read().
    length, err = router.parse_content_length(str(1 << 40))
    assert length is None
    assert err[0] == 413


# ----------- custom cap honored -----------

def test_custom_max_body_boundary():
    assert router.parse_content_length("100", max_body=100) == (100, None)
    length, err = router.parse_content_length("101", max_body=100)
    assert length is None
    assert err[0] == 413
