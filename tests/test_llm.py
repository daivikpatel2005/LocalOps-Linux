"""Tests for LLM integration, connection handling, and JSON extraction."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.llm import ask, check_ollama, extract_json_from_text


class TestLLM(unittest.TestCase):
    def test_valid_json_extraction(self):
        """Test Case 2: Valid JSON extraction from various response structures."""
        # Clean JSON
        res1 = extract_json_from_text('{"problem": "high load", "plan": []}')
        self.assertEqual(res1["problem"], "high load")

        # Markdown fenced JSON (```json ... ```)
        fenced_json = """Here is your diagnostic plan:
```json
{
  "problem": "RAM is full",
  "assessment": "Testing memory",
  "workflow_id": "memory_problem",
  "plan": []
}
```
Hope this helps!"""
        res2 = extract_json_from_text(fenced_json)
        self.assertEqual(res2["problem"], "RAM is full")
        self.assertEqual(res2["workflow_id"], "memory_problem")

        # Markdown fenced JSON without 'json' tag
        plain_fence = "```\n{\"workflow_id\": \"disk_space\"}\n```"
        res3 = extract_json_from_text(plain_fence)
        self.assertEqual(res3["workflow_id"], "disk_space")

        # Preamble and trailing text without fences
        embedded = "Certainly! The plan is: {\"status\": \"ok\", \"count\": 42}. Let me know if you need more."
        res4 = extract_json_from_text(embedded)
        self.assertEqual(res4["status"], "ok")
        self.assertEqual(res4["count"], 42)

    def test_invalid_json_extraction(self):
        """Test Case 2: Invalid JSON handling."""
        invalid_texts = [
            "This is just plain text without any JSON.",
            "{key: 'unquoted key'}",
            "{broken json",
            "",
        ]

        for text in invalid_texts:
            with self.subTest(text=text):
                with self.assertRaises((json.JSONDecodeError, ValueError)):
                    extract_json_from_text(text)

    @patch("urllib.request.urlopen")
    def test_llm_connection_failure(self, mock_urlopen):
        """Test Case 1: LLM connection failures."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused [Errno 111]")

        with self.assertRaises(RuntimeError) as ctx:
            ask("Create a plan for memory pressure")

        self.assertIn("Could not connect to Ollama", str(ctx.exception))
        self.assertIn("Connection refused", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_check_ollama_unavailable(self, mock_urlopen):
        """Test check_ollama returns helpful message when offline."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        is_ready, msg = check_ollama("qwen3:1.7b")
        self.assertFalse(is_ready)
        self.assertIn("Could not connect", msg)
        self.assertIn("ollama serve", msg)

    @patch("urllib.request.urlopen")
    def test_check_ollama_model_missing(self, mock_urlopen):
        """Test check_ollama when server is up but model is not pulled."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"models": [{"name": "llama3:latest"}]}
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        is_ready, msg = check_ollama("qwen3:1.7b")
        self.assertFalse(is_ready)
        self.assertIn("model 'qwen3:1.7b' was not found", msg)
        self.assertIn("ollama pull qwen3:1.7b", msg)


if __name__ == "__main__":
    unittest.main()

