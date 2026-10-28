"""End-to-end integration tests with mocked LLM and subprocesses."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.analyzer import analyze_results
from app.confirm import confirm_plan
from app.executor import execute_plan
from app.planner import create_plan
from app.validator import validate_plan


class TestEndToEnd(unittest.TestCase):
    @patch("app.planner.ask")
    @patch("subprocess.run")
    @patch("app.analyzer.ask")
    def test_complete_troubleshooting_flow_approved(
        self,
        mock_analyzer_ask,
        mock_subproc_run,
        mock_planner_ask,
    ):
        """Test Case 19: Complete troubleshooting session from request to diagnosis."""
        # 1. Mock Planner SLM response
        mock_planner_ask.return_value = json.dumps(
            {
                "problem": "Why is my system slow?",
                "assessment": "Checking load, RAM, and filesystem capacity.",
                "workflow_id": "system_slow",
                "plan": [
                    {
                        "command_id": "uptime",
                        "options": [],
                        "purpose": "Check system load average",
                    },
                    {
                        "command_id": "free",
                        "options": ["-h"],
                        "purpose": "Check RAM and swap usage",
                    },
                ],
            }
        )

        # 2. Mock Subprocess Execution
        mock_proc_uptime = MagicMock(
            returncode=0,
            stdout="15:30:00 up 10 days, load average: 1.20, 1.50, 1.30",
            stderr="",
        )
        mock_proc_free = MagicMock(
            returncode=0,
            stdout="Mem: 16Gi total, 8Gi used, 8Gi available\nSwap: 4Gi total, 0Gi used",
            stderr="",
        )
        mock_subproc_run.side_effect = [mock_proc_uptime, mock_proc_free]

        # 3. Mock Analyzer SLM response
        mock_analyzer_ask.return_value = json.dumps(
            {
                "diagnosis": [
                    {
                        "problem": "Load is normal",
                        "severity": "low",
                        "evidence": "Load average 1.20 is within expected thresholds.",
                        "confidence": "high",
                    }
                ],
                "summary": "Initial checks indicate normal CPU load and adequate memory headroom.",
                "next_actions": [],
                "enough_evidence": True,
            }
        )

        # Execute Pipeline:
        user_request = "Why is my system slow?"

        # Step 1: Plan
        plan = create_plan(user_request)
        self.assertEqual(plan["workflow_id"], "system_slow")

        # Step 2: Validate
        validated_commands = validate_plan(plan)
        self.assertEqual(len(validated_commands), 2)
        self.assertEqual(validated_commands[0]["command"], "uptime")
        self.assertEqual(validated_commands[1]["command"], "free -h")

        # Step 3: Confirm (simulating user answering 'y')
        with patch("builtins.input", return_value="y"):
            approved = confirm_plan(validated_commands)
        self.assertTrue(approved)

        # Step 4: Execute
        results = execute_plan(validated_commands, confirm=approved)
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]["success"])
        self.assertTrue(results[1]["success"])
        self.assertIn("load average", results[0]["stdout"])

        # Step 5: Analyze
        analysis = analyze_results(user_request, results)
        self.assertTrue(analysis["enough_evidence"])
        self.assertEqual(len(analysis["diagnosis"]), 1)
        self.assertEqual(analysis["diagnosis"][0]["severity"], "low")

    @patch("app.planner.ask")
    def test_complete_troubleshooting_flow_cancelled(self, mock_planner_ask):
        """Verify pipeline terminates safely without execution when user answers 'n'."""
        mock_planner_ask.return_value = json.dumps(
            {
                "problem": "RAM is full",
                "assessment": "Check memory",
                "workflow_id": "memory_problem",
                "plan": [
                    {
                        "command_id": "free",
                        "options": ["-h"],
                        "purpose": "Check memory",
                    }
                ],
            }
        )

        plan = create_plan("why is my RAM full?")
        validated = validate_plan(plan)

        with patch("builtins.input", return_value="n"):
            approved = confirm_plan(validated)

        self.assertFalse(approved)
        # Verify executor refuses without confirmation
        from app.executor import ExecutionError
        with self.assertRaises(ExecutionError):
            execute_plan(validated, confirm=approved)


if __name__ == "__main__":
    unittest.main()

