"""Tests for the Analyzer module: grounding, evidence discipline, and action filtering."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.analyzer import (
    analyze_results,
    build_fallback_analysis,
    validate_analysis,
)


class TestAnalyzer(unittest.TestCase):
    def setUp(self):
        self.sample_results = [
            {
                "command_id": "free",
                "command": "free -h",
                "return_code": 0,
                "success": True,
                "stdout": "Mem: 16Gi total, 15Gi used, 1Gi available\nSwap: 8Gi total, 6Gi used",
                "stderr": "",
                "timed_out": False,
            }
        ]

    def test_analysis_with_incomplete_evidence(self):
        """Test Case 18: Diagnostic analysis with incomplete or failed evidence."""
        failed_results = [
            {
                "command_id": "systemctl",
                "command": "systemctl --failed",
                "return_code": 1,
                "success": False,
                "stdout": "",
                "stderr": "Failed to connect to bus",
                "timed_out": False,
            }
        ]

        fallback = build_fallback_analysis(
            "why is my service failing?",
            failed_results,
            reason="Incomplete check",
        )
        self.assertFalse(fallback["enough_evidence"])
        self.assertEqual(len(fallback["diagnosis"]), 1)
        self.assertIn("did not complete successfully", fallback["diagnosis"][0]["problem"])

    def test_filter_unknown_recommended_commands(self):
        """Analyzer must discard unknown next-action commands recommended by model."""
        model_output = {
            "diagnosis": [
                {
                    "problem": "RAM pressure",
                    "severity": "high",
                    "evidence": "1Gi available",
                    "confidence": "high",
                }
            ],
            "summary": "System has low available RAM.",
            "next_actions": [
                {
                    "command_id": "free",
                    "options": ["-h"],
                    "reason": "Re-check memory",
                },
                {
                    "command_id": "htop",  # Unknown in knowledge base
                    "options": [],
                    "reason": "Inspect processes",
                },
                {
                    "command_id": "free",
                    "options": ["--invented-flag"],  # Invalid option
                    "reason": "Details",
                },
            ],
            "enough_evidence": True,
        }

        validated = validate_analysis(model_output)
        self.assertEqual(len(validated["next_actions"]), 1)
        self.assertEqual(validated["next_actions"][0]["command_id"], "free")
        self.assertEqual(validated["next_actions"][0]["options"], ["-h"])

    @patch("app.analyzer.ask")
    def test_analyzer_offline_fallback(self, mock_ask):
        """When LLM is unavailable, analyzer returns structured objective fallback."""
        mock_ask.side_effect = RuntimeError("Could not connect to Ollama")

        analysis = analyze_results("why is my RAM full?", self.sample_results)
        self.assertIn("diagnosis", analysis)
        self.assertIn("summary", analysis)
        self.assertFalse(analysis["enough_evidence"])
        self.assertTrue(len(analysis["diagnosis"]) > 0)


if __name__ == "__main__":
    unittest.main()

