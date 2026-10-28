"""Tests for the Executor module: safety controls, timeouts, and failure handling."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.executor import ExecutionError, execute_command, execute_plan


class TestExecutor(unittest.TestCase):
    def setUp(self):
        self.valid_command_obj = {
            "command_id": "uptime",
            "command": "uptime",
            "argv": ["uptime"],
            "purpose": "Check system load",
            "risk": "low",
            "read_only": True,
            "requires_sudo": False,
            "requires_confirmation": True,
            "options": [],
        }

    def test_confirmation_strictly_required(self):
        """execute_plan requires confirm=True explicitly."""
        with self.assertRaises(ExecutionError) as ctx:
            execute_plan([self.valid_command_obj], confirm=False)
        self.assertIn("explicit user confirmation", str(ctx.exception))

    def test_non_read_only_rejected_by_executor(self):
        """Defense in depth: Executor rejects commands without read_only=True."""
        bad_cmd = dict(self.valid_command_obj)
        bad_cmd["read_only"] = False

        with self.assertRaises(ExecutionError) as ctx:
            execute_command(bad_cmd)
        self.assertIn("not read-only", str(ctx.exception))

    def test_sudo_rejected_by_executor(self):
        """Defense in depth: Executor rejects commands with requires_sudo=True."""
        bad_cmd = dict(self.valid_command_obj)
        bad_cmd["requires_sudo"] = True

        with self.assertRaises(ExecutionError) as ctx:
            execute_command(bad_cmd)
        self.assertIn("requires sudo", str(ctx.exception))

    def test_missing_metadata_rejected(self):
        """Commands without validator metadata are rejected."""
        unvalidated = {"command_id": "uptime", "command": "uptime"}
        with self.assertRaises(ExecutionError) as ctx:
            execute_command(unvalidated)
        self.assertIn("validation metadata", str(ctx.exception))

    @patch("subprocess.run")
    def test_subprocess_timeout_handled(self, mock_run):
        """Test Case 15: Subprocess timeouts."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["uptime"],
            timeout=30,
            output="partial output",
            stderr="timed out",
        )

        res = execute_command(self.valid_command_obj)
        self.assertTrue(res["timed_out"])
        self.assertFalse(res["success"])
        self.assertEqual(res["return_code"], 124)
        self.assertEqual(res["exit_code"], 124)
        self.assertIn("timed out after 30 seconds", res["stderr"])

    @patch("subprocess.run")
    def test_failed_command_execution(self, mock_run):
        """Test Case 16: Failed command execution (non-zero exit code)."""
        mock_proc = MagicMock()
        mock_proc.returncode = 2
        mock_proc.stdout = ""
        mock_proc.stderr = "Permission denied or internal error"
        mock_run.return_value = mock_proc

        res = execute_command(self.valid_command_obj)
        self.assertFalse(res["success"])
        self.assertEqual(res["return_code"], 2)
        self.assertEqual(res["exit_code"], 2)
        self.assertEqual(res["stderr"], "Permission denied or internal error")

    @patch("subprocess.run")
    def test_output_truncation(self, mock_run):
        """Verify massive outputs are truncated to avoid OOM."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "X" * 100000  # 100 KB
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        res = execute_command(self.valid_command_obj)
        self.assertIn("[Output truncated", res["stdout"])
        self.assertLess(len(res["stdout"]), 100000)

    @patch("subprocess.run")
    def test_batch_execution_continues_on_single_failure(self, mock_run):
        """Batch execution preserves earlier and later results even if one command fails."""
        mock_proc_ok = MagicMock(returncode=0, stdout="load average 1.0", stderr="")
        mock_proc_fail = MagicMock(returncode=1, stdout="", stderr="error occurred")
        mock_run.side_effect = [mock_proc_ok, mock_proc_fail]

        cmd2 = dict(self.valid_command_obj)
        results = execute_plan([self.valid_command_obj, cmd2], confirm=True)

        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]["success"])
        self.assertFalse(results[1]["success"])


if __name__ == "__main__":
    unittest.main()

