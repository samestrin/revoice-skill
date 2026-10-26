"""Shared test helpers.

The helper scripts have hyphens in their names, so they cannot be imported
with a plain ``import``; load them from their file path instead.
"""
from __future__ import annotations
import contextlib
import importlib.util
import io
import sys
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures"
SKILL = TESTS.parent
BUILD = SKILL / "build"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_main(mod, *argv: str):
    """Call mod.main() with argv; return (result, stdout)."""
    out = io.StringIO()
    with mock.patch.object(sys, "argv", [mod.__file__, *argv]), contextlib.redirect_stdout(out):
        result = mod.main()
    return result, out.getvalue()
