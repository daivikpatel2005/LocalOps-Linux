"""Tests for the Confirmation module: user cancellation and explicit approvals."""

from __future__ import annotations

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.confirm import confirm_plan


class TestConfirm(unittest.TestCase):
    def setUp(self):
        self.sample_commands = [
            {
                "command_id": "uptime",
                "command": "uptime",
                "purpose": "Check system load",
                "risk": "low",
            }
        ]

    def test_user_cancellation(self):
        """Test Case 17: User cancellation with 'n', 'no', empty input, or arbitrary input."""
        denial_inputs = [
            "n",
            "N",
            "no",
            "No",
            "NO",
            "",
            "   ",
            "cancel",
            "abort",
            "maybe",
            "yess",
            "1",
        ]

        for denial in denial_inputs:
            with self.subTest(input_val=denial):
                with patch("builtins.input", return_value=denial), patch("sys.stdout", new_callable=io.StringIO):
                    approved = confirm_plan(self.sample_commands)
                    self.assertFalse(approved, f"Input '{denial}' should deny permission.")

    def test_user_approval(self):
        """Approval granted only on explicit 'y' or 'yes'."""
        approval_inputs = ["y", "Y", "yes", "YES", "Yes", "  y  "]

        for approval in approval_inputs:
            with self.subTest(input_val=approval):
                with patch("builtins.input", return_value=approval), patch("sys.stdout", new_callable=io.StringIO):
                    approved = confirm_plan(self.sample_commands)
                    self.assertTrue(approved, f"Input '{approval}' should grant permission.")

    def test_invalid_command_list(self):
        with self.assertRaises(ValueError):
            confirm_plan([])
        with self.assertRaises(ValueError):
            confirm_plan("not a list")


if __name__ == "__main__":
    unittest.main()
