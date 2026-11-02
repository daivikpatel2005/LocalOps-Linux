"""SQLite database manager for LocalOps knowledge base.

Maintains structured tables for commands, options, combinations, workflows,
triggers, candidates, and decision rules with foreign-key constraints
and transactional integrity.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Optional

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "localops.db"
DEFAULT_JSON_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "commands.json"


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS commands (
    command_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    use_when_json TEXT NOT NULL DEFAULT '[]',
    risk TEXT NOT NULL,
    read_only INTEGER NOT NULL DEFAULT 1,
    requires_sudo INTEGER NOT NULL DEFAULT 0,
    requires_confirmation INTEGER NOT NULL DEFAULT 1,
    output_type TEXT NOT NULL DEFAULT 'text',
    output_key_fields_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS command_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id TEXT NOT NULL,
    option TEXT NOT NULL,
    description TEXT NOT NULL,
    option_type TEXT NOT NULL DEFAULT 'flag',
    combinable INTEGER NOT NULL DEFAULT 1,
    requires_json TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (command_id) REFERENCES commands (command_id) ON DELETE CASCADE,
    UNIQUE (command_id, option)
);

CREATE TABLE IF NOT EXISTS command_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id TEXT NOT NULL,
    example TEXT NOT NULL,
    FOREIGN KEY (command_id) REFERENCES commands (command_id) ON DELETE CASCADE,
    UNIQUE (command_id, example)
);

CREATE TABLE IF NOT EXISTS workflows (
    workflow_id TEXT PRIMARY KEY,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_triggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    trigger TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflows (workflow_id) ON DELETE CASCADE,
    UNIQUE (workflow_id, trigger)
);

CREATE TABLE IF NOT EXISTS workflow_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    command_id TEXT NOT NULL,
    options_json TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (workflow_id) REFERENCES workflows (workflow_id) ON DELETE CASCADE,
    FOREIGN KEY (command_id) REFERENCES commands (command_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS workflow_decision_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    condition TEXT NOT NULL,
    possible_problem TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflows (workflow_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cmd_options ON command_options(command_id);
CREATE INDEX IF NOT EXISTS idx_cmd_examples ON command_examples(command_id);
CREATE INDEX IF NOT EXISTS idx_wf_triggers ON workflow_triggers(workflow_id);
CREATE INDEX IF NOT EXISTS idx_wf_candidates ON workflow_candidates(workflow_id);
"""


def get_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Open and return a SQLite connection with foreign keys enabled."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path | str] = None) -> None:
    """Initialize database tables without destroying existing data."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def sync_knowledge_to_db(
    json_path: Optional[Path | str] = None,
    db_path: Optional[Path | str] = None,
) -> dict[str, int]:
    """
    Synchronize knowledge from commands.json into SQLite within a transaction.

    Rolls back automatically on failure without corrupting existing database data.
    Returns counts of synchronized records.
    """
    j_path = Path(json_path) if json_path else DEFAULT_JSON_PATH
    if not j_path.is_file():
        raise FileNotFoundError(f"Knowledge JSON file not found: {j_path}")

    with open(j_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Root JSON knowledge value must be an object.")

    commands = data.get("commands", {})
    workflows = data.get("workflows", {})
    schema_version = data.get("schema_version", "1.0")

    if not isinstance(commands, dict) or not isinstance(workflows, dict):
        raise ValueError("JSON 'commands' and 'workflows' must be objects.")

    # Consistency pre-validation before database write:
    for wid, w_info in workflows.items():
        candidates = w_info.get("candidate_commands", [])
        for cand in candidates:
            cid = cand.get("command_id")
            if cid not in commands:
                raise ValueError(
                    f"Workflow '{wid}' references non-existent command '{cid}'"
                )

    init_db(db_path)
    conn = get_connection(db_path)

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO schema_info (key, value) VALUES (?, ?)",
                ("schema_version", str(schema_version)),
            )

            # Clear existing data in reverse dependency order to sync clean state
            cursor.execute("DELETE FROM workflow_decision_rules")
            cursor.execute("DELETE FROM workflow_candidates")
            cursor.execute("DELETE FROM workflow_triggers")
            cursor.execute("DELETE FROM workflows")
            cursor.execute("DELETE FROM command_examples")
            cursor.execute("DELETE FROM command_options")
            cursor.execute("DELETE FROM commands")

            # 1. Insert commands
            cmd_count = 0
            opt_count = 0
            ex_count = 0
            for cid, c_info in commands.items():
                if not isinstance(cid, str) or not cid.strip():
                    raise ValueError("Command ID must be a non-empty string.")

                cursor.execute(
                    """
                    INSERT INTO commands (
                        command_id, description, category, use_when_json,
                        risk, read_only, requires_sudo, requires_confirmation,
                        output_type, output_key_fields_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cid,
                        c_info.get("description", ""),
                        c_info.get("category", ""),
                        json.dumps(c_info.get("use_when", [])),
                        c_info.get("risk", "unknown"),
                        1 if c_info.get("read_only", True) else 0,
                        1 if c_info.get("requires_sudo", False) else 0,
                        1 if c_info.get("requires_confirmation", True) else 0,
                        c_info.get("output", {}).get("type", "text"),
                        json.dumps(c_info.get("output", {}).get("key_fields", [])),
                    ),
                )
                cmd_count += 1

                # Options
                opts = c_info.get("options", {})
                for opt_name, opt_def in opts.items():
                    cursor.execute(
                        """
                        INSERT INTO command_options (
                            command_id, option, description, option_type,
                            combinable, requires_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cid,
                            opt_name,
                            opt_def.get("description", ""),
                            opt_def.get("type", "flag"),
                            1 if opt_def.get("combinable", True) else 0,
                            json.dumps(opt_def.get("requires", [])),
                        ),
                    )
                    opt_count += 1

                # Combinations / examples
                examples = c_info.get("combinations", {}).get("examples", [])
                for ex in examples:
                    cursor.execute(
                        """
                        INSERT INTO command_examples (command_id, example)
                        VALUES (?, ?)
                        """,
                        (cid, ex),
                    )
                    ex_count += 1

            # 2. Insert workflows
            wf_count = 0
            trig_count = 0
            cand_count = 0
            rule_count = 0

            for wid, w_info in workflows.items():
                if not isinstance(wid, str) or not wid.strip():
                    raise ValueError("Workflow ID must be a non-empty string.")

                cursor.execute(
                    "INSERT INTO workflows (workflow_id, description) VALUES (?, ?)",
                    (wid, w_info.get("description", "")),
                )
                wf_count += 1

                # Triggers
                triggers = w_info.get("triggers", [])
                for trig in triggers:
                    cursor.execute(
                        "INSERT INTO workflow_triggers (workflow_id, trigger) VALUES (?, ?)",
                        (wid, trig),
                    )
                    trig_count += 1

                # Candidates
                candidates = w_info.get("candidate_commands", [])
                for order, cand in enumerate(candidates, 1):
                    cursor.execute(
                        """
                        INSERT INTO workflow_candidates (
                            workflow_id, step_order, command_id, options_json
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            wid,
                            order,
                            cand.get("command_id"),
                            json.dumps(cand.get("options", [])),
                        ),
                    )
                    cand_count += 1

                # Decision rules
                rules = w_info.get("decision_rules", [])
                for rule in rules:
                    cursor.execute(
                        """
                        INSERT INTO workflow_decision_rules (
                            workflow_id, condition, possible_problem
                        ) VALUES (?, ?, ?)
                        """,
                        (wid, rule.get("condition", ""), rule.get("possible_problem", "")),
                    )
                    rule_count += 1

        return {
            "commands": cmd_count,
            "options": opt_count,
            "examples": ex_count,
            "workflows": wf_count,
            "triggers": trig_count,
            "candidates": cand_count,
            "rules": rule_count,
        }
    finally:
        conn.close()


def load_knowledge_from_db(db_path: Optional[Path | str] = None) -> dict[str, Any]:
    """
    Reconstruct the full knowledge dictionary from SQLite.

    Matches the format of commands.json.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()

        # Schema version
        cursor.execute("SELECT value FROM schema_info WHERE key = 'schema_version'")
        row = cursor.fetchone()
        schema_version = row["value"] if row else "1.0"

        # Commands
        cursor.execute("SELECT * FROM commands")
        commands: dict[str, Any] = {}
        for row in cursor.fetchall():
            cid = row["command_id"]
            commands[cid] = {
                "description": row["description"],
                "category": row["category"],
                "use_when": json.loads(row["use_when_json"]),
                "risk": row["risk"],
                "read_only": bool(row["read_only"]),
                "requires_sudo": bool(row["requires_sudo"]),
                "requires_confirmation": bool(row["requires_confirmation"]),
                "options": {},
                "combinations": {"examples": []},
                "output": {
                    "type": row["output_type"],
                    "key_fields": json.loads(row["output_key_fields_json"]),
                },
            }

        # Command options
        cursor.execute("SELECT * FROM command_options")
        for row in cursor.fetchall():
            cid = row["command_id"]
            opt = row["option"]
            if cid in commands:
                commands[cid]["options"][opt] = {
                    "description": row["description"],
                    "type": row["option_type"],
                    "combinable": bool(row["combinable"]),
                    "requires": json.loads(row["requires_json"]),
                }

        # Command examples
        cursor.execute("SELECT * FROM command_examples")
        for row in cursor.fetchall():
            cid = row["command_id"]
            if cid in commands:
                commands[cid]["combinations"]["examples"].append(row["example"])

        # Workflows
        cursor.execute("SELECT * FROM workflows")
        workflows: dict[str, Any] = {}
        for row in cursor.fetchall():
            wid = row["workflow_id"]
            workflows[wid] = {
                "description": row["description"],
                "triggers": [],
                "candidate_commands": [],
                "decision_rules": [],
            }

        # Triggers
        cursor.execute("SELECT * FROM workflow_triggers")
        for row in cursor.fetchall():
            wid = row["workflow_id"]
            if wid in workflows:
                workflows[wid]["triggers"].append(row["trigger"])

        # Candidates (ordered by step_order)
        cursor.execute("SELECT * FROM workflow_candidates ORDER BY step_order ASC")
        for row in cursor.fetchall():
            wid = row["workflow_id"]
            if wid in workflows:
                workflows[wid]["candidate_commands"].append(
                    {
                        "command_id": row["command_id"],
                        "options": json.loads(row["options_json"]),
                    }
                )

        # Decision rules
        cursor.execute("SELECT * FROM workflow_decision_rules")
        for row in cursor.fetchall():
            wid = row["workflow_id"]
            if wid in workflows:
                workflows[wid]["decision_rules"].append(
                    {
                        "condition": row["condition"],
                        "possible_problem": row["possible_problem"],
                    }
                )

        return {
            "schema_version": schema_version,
            "commands": commands,
            "workflows": workflows,
        }
    finally:
        conn.close()


def get_db_command(
    command_id: str, db_path: Optional[Path | str] = None
) -> Optional[dict[str, Any]]:
    """Fetch a single command and its options/examples directly from SQLite."""
    if not isinstance(command_id, str) or not command_id.strip():
        return None

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT command_id, description, category, use_when_json, risk,
                   read_only, requires_sudo, requires_confirmation,
                   output_type, output_key_fields_json
            FROM commands
            WHERE command_id = ?
            """,
            (command_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        # Options
        cursor.execute(
            """
            SELECT option, description, option_type, combinable, requires_json
            FROM command_options
            WHERE command_id = ?
            """,
            (command_id,),
        )
        options: dict[str, Any] = {}
        for opt_row in cursor.fetchall():
            options[opt_row["option"]] = {
                "description": opt_row["description"],
                "type": opt_row["option_type"],
                "combinable": bool(opt_row["combinable"]),
                "requires": json.loads(opt_row["requires_json"]),
            }

        # Examples
        cursor.execute(
            "SELECT example FROM command_examples WHERE command_id = ?",
            (command_id,),
        )
        examples = [ex_row["example"] for ex_row in cursor.fetchall()]

        return {
            "description": row["description"],
            "category": row["category"],
            "use_when": json.loads(row["use_when_json"]),
            "risk": row["risk"],
            "read_only": bool(row["read_only"]),
            "requires_sudo": bool(row["requires_sudo"]),
            "requires_confirmation": bool(row["requires_confirmation"]),
            "options": options,
            "combinations": {"examples": examples},
            "output": {
                "type": row["output_type"],
                "key_fields": json.loads(row["output_key_fields_json"]),
            },
        }
    finally:
        conn.close()


def get_db_all_commands(db_path: Optional[Path | str] = None) -> dict[str, Any]:
    """Fetch all command definitions directly from SQLite."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT command_id, description, category, use_when_json, risk,
                   read_only, requires_sudo, requires_confirmation,
                   output_type, output_key_fields_json
            FROM commands
            """
        )
        commands: dict[str, Any] = {}
        for row in cursor.fetchall():
            cid = row["command_id"]
            commands[cid] = {
                "description": row["description"],
                "category": row["category"],
                "use_when": json.loads(row["use_when_json"]),
                "risk": row["risk"],
                "read_only": bool(row["read_only"]),
                "requires_sudo": bool(row["requires_sudo"]),
                "requires_confirmation": bool(row["requires_confirmation"]),
                "options": {},
                "combinations": {"examples": []},
                "output": {
                    "type": row["output_type"],
                    "key_fields": json.loads(row["output_key_fields_json"]),
                },
            }

        # Options
        cursor.execute(
            "SELECT command_id, option, description, option_type, combinable, requires_json FROM command_options"
        )
        for opt_row in cursor.fetchall():
            cid = opt_row["command_id"]
            if cid in commands:
                commands[cid]["options"][opt_row["option"]] = {
                    "description": opt_row["description"],
                    "type": opt_row["option_type"],
                    "combinable": bool(opt_row["combinable"]),
                    "requires": json.loads(opt_row["requires_json"]),
                }

        # Examples
        cursor.execute("SELECT command_id, example FROM command_examples")
        for ex_row in cursor.fetchall():
            cid = ex_row["command_id"]
            if cid in commands:
                commands[cid]["combinations"]["examples"].append(ex_row["example"])

        return commands
    finally:
        conn.close()


def get_db_workflow(
    workflow_id: str, db_path: Optional[Path | str] = None
) -> Optional[dict[str, Any]]:
    """Fetch a single workflow definition directly from SQLite."""
    if not isinstance(workflow_id, str) or not workflow_id.strip():
        return None

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT workflow_id, description FROM workflows WHERE workflow_id = ?",
            (workflow_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        # Triggers
        cursor.execute(
            "SELECT trigger FROM workflow_triggers WHERE workflow_id = ?",
            (workflow_id,),
        )
        triggers = [t_row["trigger"] for t_row in cursor.fetchall()]

        # Candidate commands
        cursor.execute(
            """
            SELECT command_id, options_json
            FROM workflow_candidates
            WHERE workflow_id = ?
            ORDER BY step_order ASC
            """,
            (workflow_id,),
        )
        candidates = [
            {
                "command_id": c_row["command_id"],
                "options": json.loads(c_row["options_json"]),
            }
            for c_row in cursor.fetchall()
        ]

        # Decision rules
        cursor.execute(
            """
            SELECT condition, possible_problem
            FROM workflow_decision_rules
            WHERE workflow_id = ?
            ORDER BY id ASC
            """,
            (workflow_id,),
        )
        rules = [
            {
                "condition": r_row["condition"],
                "possible_problem": r_row["possible_problem"],
            }
            for r_row in cursor.fetchall()
        ]

        return {
            "description": row["description"],
            "triggers": triggers,
            "candidate_commands": candidates,
            "decision_rules": rules,
        }
    finally:
        conn.close()


def get_db_all_workflows(db_path: Optional[Path | str] = None) -> dict[str, Any]:
    """Fetch all workflows and their triggers, candidates, and decision rules directly from SQLite."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT workflow_id, description FROM workflows")
        workflows: dict[str, Any] = {}
        for row in cursor.fetchall():
            wid = row["workflow_id"]
            workflows[wid] = {
                "description": row["description"],
                "triggers": [],
                "candidate_commands": [],
                "decision_rules": [],
            }

        # Triggers
        cursor.execute("SELECT workflow_id, trigger FROM workflow_triggers")
        for t_row in cursor.fetchall():
            wid = t_row["workflow_id"]
            if wid in workflows:
                workflows[wid]["triggers"].append(t_row["trigger"])

        # Candidates
        cursor.execute(
            "SELECT workflow_id, command_id, options_json FROM workflow_candidates ORDER BY step_order ASC"
        )
        for c_row in cursor.fetchall():
            wid = c_row["workflow_id"]
            if wid in workflows:
                workflows[wid]["candidate_commands"].append(
                    {
                        "command_id": c_row["command_id"],
                        "options": json.loads(c_row["options_json"]),
                    }
                )

        # Decision rules
        cursor.execute(
            "SELECT workflow_id, condition, possible_problem FROM workflow_decision_rules ORDER BY id ASC"
        )
        for r_row in cursor.fetchall():
            wid = r_row["workflow_id"]
            if wid in workflows:
                workflows[wid]["decision_rules"].append(
                    {
                        "condition": r_row["condition"],
                        "possible_problem": r_row["possible_problem"],
                    }
                )

        return workflows
    finally:
        conn.close()


def get_db_triggers(db_path: Optional[Path | str] = None) -> list[tuple[str, str]]:
    """Return all (workflow_id, trigger) pairs directly from SQLite."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT workflow_id, trigger FROM workflow_triggers")
        return [(row["workflow_id"], row["trigger"]) for row in cursor.fetchall()]
    finally:
        conn.close()


def dump_db_to_json(
    db_path: Optional[Path | str] = None, json_path: Optional[Path | str] = None
) -> None:
    """Export current SQLite tables to a formatted commands.json file atomically."""
    j_path = Path(json_path) if json_path else DEFAULT_JSON_PATH
    data = load_knowledge_from_db(db_path)
    temp_json = j_path.with_suffix(".tmp")
    with open(temp_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    temp_json.replace(j_path)


def is_database_populated(db_path: Optional[Path | str] = None) -> bool:
    """Check if the SQLite database exists and contains command records."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    if not path.is_file():
        return False
    try:
        conn = get_connection(path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM commands")
            count = cursor.fetchone()[0]
            return count > 0
        finally:
            conn.close()
    except Exception:
        return False


def ensure_db_ready(
    db_path: Optional[Path | str] = None, json_path: Optional[Path | str] = None
) -> None:
    """Ensure SQLite database is initialized and populated."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    if is_database_populated(path):
        return

    # If DB is not populated, try seeding from commands.json if available
    j_path = Path(json_path) if json_path else DEFAULT_JSON_PATH
    if j_path.is_file():
        init_db(path)
        sync_knowledge_to_db(j_path, path)
    else:
        init_db(path)


