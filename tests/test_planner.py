"""Tests for the Planner module: schema enforcement, bounded retries, and error handling."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.planner import PlannerError, _validate_raw_plan_dict, create_plan


class TestPlanner(unittest.TestCase):
    def test_missing_planner_fields(self):
        """Test Case 3: Missing planner fields."""
        incomplete_plans = [
            {"assessment": "a", "workflow_id": None, "plan": []},  # missing problem
            {"problem": "p", "workflow_id": None, "plan": []},      # missing assessment
            {"problem": "p", "assessment": "a", "workflow_id": None}, # missing plan
            {"problem": "", "assessment": "a", "workflow_id": None, "plan": [{"command_id": "free", "options": []}]}, # empty problem
        ]

        for p in incomplete_plans:
            with self.subTest(plan=p):
                with self.assertRaises(PlannerError):
                    _validate_raw_plan_dict(p, "test query")

    def test_plan_returned_as_string(self):
        """Test Case 4: 'plan' returned as a string instead of a list."""
        bad_plan = {
            "problem": "RAM is full",
            "assessment": "Checking memory",
            "workflow_id": "memory_problem",
            "plan": "free -h",  # String instead of list!
        }

        with self.assertRaises(PlannerError) as ctx:
            _validate_raw_plan_dict(bad_plan, "why is my RAM full?")

        self.assertIn("Planner field 'plan' must be a list", str(ctx.exception))

    def test_plan_returned_as_object(self):
        """Test Case 5: 'plan' returned as an object instead of a list."""
        bad_plan = {
            "problem": "RAM is full",
            "assessment": "Checking memory",
            "workflow_id": "memory_problem",
            "plan": {  # Object instead of list!
                "command_id": "free",
                "options": ["-h"],
                "purpose": "Check RAM",
            },
        }

        with self.assertRaises(PlannerError) as ctx:
            _validate_raw_plan_dict(bad_plan, "why is my RAM full?")

        self.assertIn("Planner field 'plan' must be a list", str(ctx.exception))

    def test_empty_plan_rejected(self):
        """Test Case 6: Empty plans are rejected."""
        empty_plan = {
            "problem": "System is slow",
            "assessment": "No commands needed",
            "workflow_id": "system_slow",
            "plan": [],  # Empty list!
        }

        with self.assertRaises(PlannerError) as ctx:
            _validate_raw_plan_dict(empty_plan, "system slow")

        self.assertIn("empty diagnostic plan", str(ctx.exception))

    def test_empty_user_input_rejected(self):
        """Empty or whitespace-only user input rejected before calling model."""
        with self.assertRaises(ValueError):
            create_plan("")
        with self.assertRaises(ValueError):
            create_plan("   \n\t")

    @patch("app.planner.ask")
    def test_retry_on_malformed_llm_response(self, mock_ask):
        """Verify planner retries when LLM returns invalid JSON or structure."""
        # First call returns invalid JSON, second call returns valid JSON
        mock_ask.side_effect = [
            "Here is the plan: not valid json",
            json.dumps(
                {
                    "problem": "System is slow",
                    "assessment": "Investigating load",
                    "workflow_id": "system_slow",
                    "plan": [
                        {
                            "command_id": "uptime",
                            "options": [],
                            "purpose": "Check load average",
                        }
                    ],
                }
            ),
        ]

        plan = create_plan("why is my system slow?")
        self.assertEqual(plan["workflow_id"], "system_slow")
        self.assertEqual(len(plan["plan"]), 1)
        self.assertEqual(mock_ask.call_count, 2)

    def test_regression_why_is_my_ram_full(self):
        """Regression test for the exact user error: 'why is my RAM full?'."""
        plan = create_plan("why is my RAM full?")
        self.assertEqual(plan["workflow_id"], "memory_problem")
        self.assertIsInstance(plan["plan"], list)
        self.assertGreater(len(plan["plan"]), 0)
        command_ids = [c["command_id"] for c in plan["plan"]]
        self.assertIn("free", command_ids)

    @patch("app.planner.ask")
    def test_regression_my_internet_is_not_working(self, mock_ask):
        """Regression test for user issue: model omitting hyphen or invalid options in 'my internet is not working'."""
        # Simulate SLM generating "brief" without hyphen
        mock_ask.return_value = json.dumps(
            {
                "problem": "my internet is not working",
                "assessment": "network check",
                "workflow_id": "network_problem",
                "plan": [
                    {"command_id": "ip", "options": ["brief", "address"], "purpose": "Check IP addresses"},
                    {"command_id": "ip", "options": ["route"], "purpose": "Check routing"},
                ],
            }
        )

        plan = create_plan("my internet is not working")
        self.assertEqual(plan["workflow_id"], "network_problem")
        self.assertEqual(len(plan["plan"]), 2)

    @patch("app.planner.ask")
    def test_auto_recovery_when_model_persistently_returns_invalid_option(self, mock_ask):
        """When model stubbornly returns invalid options, fall back to verified workflow candidate commands."""
        mock_ask.return_value = json.dumps(
            {
                "problem": "my internet is not working",
                "assessment": "network check",
                "workflow_id": "network_problem",
                "plan": [
                    {"command_id": "ip", "options": ["--completely-invalid-flag"]}
                ],
            }
        )

        plan = create_plan("my internet is not working")
        self.assertEqual(plan["workflow_id"], "network_problem")
        # Should have fallen back to verified workflow candidate commands
        self.assertGreater(len(plan["plan"]), 1)
        command_ids = [c["command_id"] for c in plan["plan"]]
        self.assertIn("ip", command_ids)
        self.assertIn("nmcli", command_ids)


if __name__ == "__main__":
    unittest.main()

