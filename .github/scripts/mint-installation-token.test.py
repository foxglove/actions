#!/usr/bin/env python3
"""Tests for installation-token permission parsing."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("mint-installation-token.py")
SPEC = importlib.util.spec_from_file_location("mint_installation_token", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
mint_installation_token = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mint_installation_token)


class LoadPermissionsTest(unittest.TestCase):
    def test_actions_write(self) -> None:
        self.assertEqual(
            mint_installation_token.load_permissions('{"actions":"write"}'),
            {"actions": "write"},
        )

    def test_rejects_empty_object(self) -> None:
        with self.assertRaises(SystemExit):
            mint_installation_token.load_permissions("{}")

    def test_rejects_non_object(self) -> None:
        with self.assertRaises(SystemExit):
            mint_installation_token.load_permissions('["actions"]')

    def test_rejects_invalid_json(self) -> None:
        with self.assertRaises(SystemExit):
            mint_installation_token.load_permissions("{")


if __name__ == "__main__":
    unittest.main()
