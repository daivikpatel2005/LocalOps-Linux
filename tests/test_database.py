"""Tests for SQLite database initialization, integrity, and transaction rollback."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database import (
    dump_db_to_json,
    ensure_db_ready,
    get_connection,
    get_db_all_commands,
    get_db_all_workflows,
    get_db_command,
    get_db_triggers,
    get_db_workflow,
    init_db,
    is_database_populated,
    load_knowledge_from_db,
    sync_knowledge_to_db,
)
from app.knowledge import build_context, find_workflow, get_command, get_workflow
from app.validator import validate_plan


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_localops.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_database_initialization_and_integrity(self):
        """Test Case 13: Database initialization and integrity."""
        # 1. Initialize DB tables
        init_db(self.db_path)
        self.assertTrue(self.db_path.is_file())

        # 2. Sync from commands.json
        counts = sync_knowledge_to_db(db_path=self.db_path)
        self.assertGreater(counts["commands"], 0)
        self.assertGreater(counts["workflows"], 0)

        # 3. Verify integrity of loaded data
        reloaded = load_knowledge_from_db(self.db_path)
        self.assertEqual(len(reloaded["commands"]), counts["commands"])
        self.assertEqual(len(reloaded["workflows"]), counts["workflows"])

        # Check df command structure
        df_cmd = reloaded["commands"].get("df")
        self.assertIsNotNone(df_cmd)
        self.assertTrue(df_cmd["read_only"])
        self.assertFalse(df_cmd["requires_sudo"])
        self.assertIn("-h", df_cmd["options"])

    def test_database_transaction_rollback(self):
        """Test Case 14: Database transaction rollback on invalid sync data."""
        init_db(self.db_path)
        sync_knowledge_to_db(db_path=self.db_path)
        initial_knowledge = load_knowledge_from_db(self.db_path)
        initial_cmd_count = len(initial_knowledge["commands"])

        # Create a corrupted JSON file referencing a non-existent command in a workflow
        bad_json_path = Path(self.temp_dir.name) / "bad_commands.json"
        with open(bad_json_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "schema_version": "1.0",
                    "commands": initial_knowledge["commands"],
                    "workflows": {
                        "corrupted_workflow": {
                            "description": "Corrupted test",
                            "triggers": ["test"],
                            "candidate_commands": [
                                {
                                    "command_id": "non_existent_unregistered_command",
                                    "options": [],
                                }
                            ],
                            "decision_rules": [],
                        }
                    },
                },
                f,
            )

        # Sync should fail and roll back cleanly
        with self.assertRaises(ValueError) as ctx:
            sync_knowledge_to_db(json_path=bad_json_path, db_path=self.db_path)

        self.assertIn("non-existent command", str(ctx.exception))

        # Check database still contains the original data
        reloaded = load_knowledge_from_db(self.db_path)
        self.assertEqual(len(reloaded["commands"]), initial_cmd_count)

    def test_foreign_key_enforcement(self):
        """Test that foreign keys are enforced by SQLite."""
        init_db(self.db_path)
        conn = get_connection(self.db_path)
        try:
            with conn:
                # Inserting an option for a non-existent command must fail
                with self.assertRaises(Exception):
                    conn.execute(
                        "INSERT INTO command_options (command_id, option, description) VALUES (?, ?, ?)",
                        ("non_existent_cmd", "-v", "test"),
                    )
        finally:
            conn.close()

    def test_direct_db_command_queries(self):
        """Test direct SQLite queries for single and all commands."""
        init_db(self.db_path)
        sync_knowledge_to_db(db_path=self.db_path)

        cmd = get_db_command("ip", db_path=self.db_path)
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd["category"], "network")
        self.assertTrue(cmd["read_only"])
        self.assertFalse(cmd["requires_sudo"])
        self.assertIn("route", cmd["options"])
        self.assertIn("-brief", cmd["options"])
        self.assertIn("ip -brief address", cmd["combinations"]["examples"])

        # Non-existent command returns None
        self.assertIsNone(get_db_command("non_existent_binary", db_path=self.db_path))

        all_cmds = get_db_all_commands(db_path=self.db_path)
        self.assertGreaterEqual(len(all_cmds), 40)
        self.assertIn("df", all_cmds)
        self.assertIn("uptime", all_cmds)

    def test_direct_db_workflow_queries(self):
        """Test direct SQLite queries for single and all workflows."""
        init_db(self.db_path)
        sync_knowledge_to_db(db_path=self.db_path)

        wf = get_db_workflow("network_problem", db_path=self.db_path)
        self.assertIsNotNone(wf)
        self.assertIn("internet is not working", wf["triggers"])
        self.assertGreater(len(wf["candidate_commands"]), 0)
        self.assertGreater(len(wf["decision_rules"]), 0)

        # Step order preservation
        cmd_ids = [c["command_id"] for c in wf["candidate_commands"]]
        self.assertEqual(cmd_ids[0], "ip")

        # Non-existent workflow returns None
        self.assertIsNone(get_db_workflow("ghost_workflow", db_path=self.db_path))

        all_wfs = get_db_all_workflows(db_path=self.db_path)
        self.assertGreaterEqual(len(all_wfs), 25)
        self.assertIn("system_slow", all_wfs)
        self.assertIn("memory_problem", all_wfs)

    def test_direct_db_triggers(self):
        """Test retrieving all workflow triggers from SQLite."""
        init_db(self.db_path)
        sync_knowledge_to_db(db_path=self.db_path)

        triggers = get_db_triggers(db_path=self.db_path)
        self.assertGreater(len(triggers), 200)
        self.assertIn(("network_problem", "internet is not working"), triggers)

    def test_dump_db_to_json(self):
        """Test exporting SQLite tables back to JSON."""
        init_db(self.db_path)
        sync_knowledge_to_db(db_path=self.db_path)

        export_json = Path(self.temp_dir.name) / "exported_commands.json"
        dump_db_to_json(db_path=self.db_path, json_path=export_json)
        self.assertTrue(export_json.is_file())

        with open(export_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("commands", data)
        self.assertIn("workflows", data)
        self.assertIn("ip", data["commands"])
        self.assertIn("network_problem", data["workflows"])

    def test_pure_sqlite_operation_without_json(self):
        """Verify LocalOps runs purely from SQLite even if commands.json is missing."""
        import unittest.mock as mock

        # Mock KNOWLEDGE_FILE in app.knowledge to a non-existent file
        non_existent_json = Path(self.temp_dir.name) / "does_not_exist.json"
        self.assertFalse(non_existent_json.is_file())

        with mock.patch("app.knowledge.KNOWLEDGE_FILE", non_existent_json):
            # 1. get_command works from DB
            cmd = get_command("ip")
            self.assertIsNotNone(cmd)
            self.assertIn("route", cmd["options"])

            # 2. get_workflow works from DB
            wf = get_workflow("network_problem")
            self.assertIsNotNone(wf)

            # 3. find_workflow works from DB triggers
            wid, matched_wf = find_workflow("my internet is not working")
            self.assertEqual(wid, "network_problem")
            self.assertIsNotNone(matched_wf)

            # 4. build_context works from DB
            context_str = build_context("network_problem")
            self.assertIn("ip", context_str)
            self.assertIn("route", context_str)

            # 5. Validator works purely from DB metadata
            validated = validate_plan(
                {
                    "problem": "my internet is not working",
                    "assessment": "network troubleshooting",
                    "workflow_id": "network_problem",
                    "plan": [
                        {
                            "command_id": "ip",
                            "options": ["route"],
                            "purpose": "Verify default routing table",
                        }
                    ],
                }
            )
            self.assertEqual(len(validated), 1)
            self.assertEqual(validated[0]["command_id"], "ip")
            self.assertEqual(validated[0]["argv"], ["ip", "route"])
            self.assertTrue(validated[0]["read_only"])
            self.assertFalse(validated[0]["requires_sudo"])



if __name__ == "__main__":
    unittest.main()

