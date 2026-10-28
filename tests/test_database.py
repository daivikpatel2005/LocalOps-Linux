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
    get_connection,
    init_db,
    load_knowledge_from_db,
    sync_knowledge_to_db,
)


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


if __name__ == "__main__":
    unittest.main()

