"""Tests for the Validator module: security boundaries, allow-lists, and injection protection."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.validator import ValidationError, validate_plan


class TestValidator(unittest.TestCase):
    def test_valid_plan_passes(self):
        plan = {
            "problem": "Check system health",
            "assessment": "Basic triage",
            "workflow_id": "system_slow",
            "plan": [
                {"command_id": "uptime", "options": [], "purpose": "Check load"},
                {"command_id": "free", "options": ["-h"], "purpose": "Check RAM"},
                {"command_id": "df", "options": ["-h"], "purpose": "Check disk"},
            ],
        }

        validated = validate_plan(plan)
        self.assertEqual(len(validated), 3)
        self.assertEqual(validated[0]["command_id"], "uptime")
        self.assertEqual(validated[0]["argv"], ["uptime"])
        self.assertEqual(validated[1]["argv"], ["free", "-h"])
        self.assertEqual(validated[2]["argv"], ["df", "-h"])
        for cmd in validated:
            self.assertTrue(cmd["read_only"])
            self.assertFalse(cmd["requires_sudo"])

    def test_unknown_commands_rejected(self):
        """Test Case 7: Unknown commands rejected."""
        unknown_plans = [
            {"command_id": "nmap", "options": []},
            {"command_id": "curl", "options": ["http://evil.com"]},
            {"command_id": "rm", "options": ["-rf", "/"]},
            {"command_id": "bash", "options": ["-c", "id"]},
        ]

        for item in unknown_plans:
            with self.subTest(command=item["command_id"]):
                plan = {
                    "problem": "test",
                    "assessment": "test",
                    "workflow_id": None,
                    "plan": [item],
                }
                with self.assertRaises(ValidationError) as ctx:
                    validate_plan(plan)
                self.assertIn("Unknown command ID", str(ctx.exception))

    def test_invalid_options_rejected(self):
        """Test Case 8: Invalid options rejected."""
        invalid_opt_plans = [
            {"command_id": "free", "options": ["--dangerous"]},
            {"command_id": "df", "options": ["-x", "ext4"]},
            {"command_id": "uptime", "options": ["-v"]},
        ]

        for item in invalid_opt_plans:
            with self.subTest(item=item):
                plan = {
                    "problem": "test",
                    "assessment": "test",
                    "workflow_id": None,
                    "plan": [item],
                }
                with self.assertRaises(ValidationError) as ctx:
                    validate_plan(plan)
                self.assertIn("not allowed", str(ctx.exception))

    def test_invalid_command_combinations_rejected(self):
        """Test Case 9: Invalid command combinations rejected."""
        # Options might individually exist or be known, but combination is not an allowed example
        plan = {
            "problem": "test",
            "assessment": "test",
            "workflow_id": None,
            "plan": [
                {"command_id": "free", "options": ["-h", "-h"]},
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            validate_plan(plan)
        self.assertIn("Command combination not allowed", str(ctx.exception))

    def test_shell_injection_attempts(self):
        """Test Case 10: Shell injection attempts rejected."""
        injection_plans = [
            {"command_id": "free; rm -rf /", "options": []},
            {"command_id": "uptime && whoami", "options": []},
            {"command_id": "df`reboot`", "options": []},
            {"command_id": "ps $(rm -rf /)", "options": []},
            {"command_id": "free", "options": ["-h; whoami"]},
            {"command_id": "free", "options": ["`id`"]},
            {"command_id": "free", "options": ["$USER"]},
            {"command_id": "free", "options": ["> /tmp/pwn"]},
        ]

        for item in injection_plans:
            with self.subTest(item=item):
                plan = {
                    "problem": "test",
                    "assessment": "test",
                    "workflow_id": None,
                    "plan": [item],
                }
                with self.assertRaises(ValidationError) as ctx:
                    validate_plan(plan)
                # Must be rejected either by shell metacharacter check or unknown command check
                self.assertTrue(
                    any(
                        kw in str(ctx.exception)
                        for kw in ["whitespace", "shell", "not allowed", "Unknown"]
                    )
                )

    def test_command_chaining_and_pipeline_attempts(self):
        """Test Case 11: Command chaining and pipeline attempts rejected."""
        chain_plans = [
            {"command_id": "uptime | grep load", "options": []},
            {"command_id": "free | tee /tmp/log", "options": []},
            {"command_id": "ps aux || echo fail", "options": []},
        ]

        for item in chain_plans:
            with self.subTest(item=item):
                plan = {
                    "problem": "test",
                    "assessment": "test",
                    "workflow_id": None,
                    "plan": [item],
                }
                with self.assertRaises(ValidationError) as ctx:
                    validate_plan(plan)

    def test_cannot_override_trusted_metadata(self):
        """Model cannot mark an unapproved action as read_only=True or requires_sudo=False."""
        forged_plan = {
            "problem": "Try to run sudo",
            "assessment": "Attempting forge",
            "workflow_id": None,
            "plan": [
                {
                    "command_id": "free",
                    "options": ["-h"],
                    "read_only": False,     # forged field
                    "requires_sudo": True,   # forged field
                    "risk": "critical",     # forged field
                }
            ],
        }

        validated = validate_plan(forged_plan)
        # Trusted metadata from knowledge base must be used!
        self.assertTrue(validated[0]["read_only"])
        self.assertFalse(validated[0]["requires_sudo"])
        self.assertEqual(validated[0]["risk"], "safe")

    def test_option_prefix_normalization(self):
        """Verify that SLM omitting leading hyphens (e.g. 'brief' -> '-brief', 'h' -> '-h') is normalized."""
        plan = {
            "problem": "my internet is not working",
            "assessment": "network check",
            "workflow_id": "network_problem",
            "plan": [
                {"command_id": "ip", "options": ["brief", "address"], "purpose": "Check IP addresses"},
                {"command_id": "free", "options": ["h"], "purpose": "Check RAM"},
            ],
        }

        validated = validate_plan(plan)
        self.assertEqual(validated[0]["command"], "ip -brief address")
        self.assertEqual(validated[0]["argv"], ["ip", "-brief", "address"])
        self.assertEqual(validated[1]["command"], "free -h")
        self.assertEqual(validated[1]["argv"], ["free", "-h"])


if __name__ == "__main__":
    unittest.main()
