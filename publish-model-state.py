#!/usr/bin/env python3
"""Compatibility entry point for the installed model-state timer.

The timer deliberately invokes this stable, root-level path through the
live-linked /usr/local/lib/sovereign-os checkout.  Keep the implementation in
scripts/iac/assets so the IaC installer and the development checkout share it.
"""
from pathlib import Path
import runpy

runpy.run_path(
    str(Path(__file__).resolve().parent / "scripts" / "iac" / "assets" / "publish-model-state.py"),
    run_name="__main__",
)
