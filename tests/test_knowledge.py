"""Tests for the knowledge base module and workflow matching."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.knowledge import (
    build_context,
    find_workflow,
    get_command,
    get_commands,
    get_supported_troubleshooting_areas,
    get_workflow,
    get_workflows,
    load_knowledge,
)


class TestKnowledge(unittest.TestCase):
    def test_load_knowledge(self):
        kb = load_knowledge()
        self.assertIn("commands", kb)
        self.assertIn("workflows", kb)
        self.assertGreater(len(kb["commands"]), 20)

    def test_get_commands_and_workflows(self):
        commands = get_commands()
        workflows = get_workflows()
        self.assertIn("df", commands)
        self.assertIn("uptime", commands)
        self.assertIn("free", commands)
        self.assertIn("system_slow", workflows)
        self.assertIn("memory_problem", workflows)

    def test_workflow_matching_test_cases(self):
        """Verify workflow matching handles realistic user phrasing for supported queries."""
        expected_matches = [
            ("Why is my system slow?", "system_slow"),
            ("Why is my RAM full?", "memory_problem"),
            ("My disk is full.", "disk_space"),
            ("Why is my internet not working?", "network_problem"),
            ("My Wi-Fi keeps disconnecting.", "wifi_problem"),
            ("My Bluetooth headphones keep disconnecting.", "bluetooth_problem"),
            ("Why is my system service failing?", "service_problem"),
            ("An application keeps crashing.", "application_crash"),
            ("Why is my laptop overheating?", "overheating_thermal"),
            ("Why is my battery draining fast?", "battery_power"),
            ("What ports are open?", "ports_listening_services"),
            ("Why is CPU usage high?", "cpu_bottleneck"),
            ("Why is my boot so slow?", "slow_boot_startup"),
            ("What OS am I running?", "os_distribution_info"),
            ("Cannot reach local router", "arp_network_neighbors"),
            ("Wrong system language", "locale_timezone_keyboard"),
        ]

        for query, expected_wid in expected_matches:
            with self.subTest(query=query):
                wid, w = find_workflow(query)
                self.assertEqual(
                    wid,
                    expected_wid,
                    f"Query '{query}' expected to match '{expected_wid}', got '{wid}'",
                )
                self.assertIsNotNone(w)

    def test_missing_and_unsupported_workflows(self):
        """Test Case 12: Missing workflows and unsupported queries return None."""
        unsupported_queries = [
            "How do I cook pasta?",
            "Overclock my GPU to 2000MHz",
            "Change my root password",
            "Install minecraft server",
            "",
            "   ",
        ]

        for query in unsupported_queries:
            with self.subTest(query=query):
                wid, w = find_workflow(query)
                self.assertIsNone(
                    wid,
                    f"Unsupported query '{query}' should return None, got '{wid}'",
                )
                self.assertIsNone(w)

    def test_supported_areas_listing(self):
        areas = get_supported_troubleshooting_areas()
        self.assertTrue(len(areas) > 5)
        self.assertTrue(any("memory_problem" in a for a in areas))

    def test_focused_context_building(self):
        """Verify build_context produces a concise context for a specific workflow."""
        context_mem = build_context("memory_problem")
        self.assertIn("active_workflow_id", context_mem)
        self.assertIn("free", context_mem)
        # Should be compact (< 10000 chars) instead of dumping full 55000 char DB
        self.assertLess(len(context_mem), 10000)


if __name__ == "__main__":
    unittest.main()

