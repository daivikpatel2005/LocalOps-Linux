import json
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SCHEMA = BASE / "knowledge" / "schema.sql"
SEED = BASE / "knowledge" / "seed" / "initial_knowledge.json"
DB = BASE / "data" / "localops.db"


def main():
    if not SCHEMA.is_file() or SCHEMA.stat().st_size == 0:
        raise SystemExit("ERROR: knowledge/schema.sql is missing or empty.")

    if not SEED.is_file():
        raise SystemExit("ERROR: Knowledge seed file is missing.")

    knowledge = json.loads(SEED.read_text(encoding="utf-8"))
    commands = knowledge.get("commands")
    workflows = knowledge.get("workflows")

    if not isinstance(commands, dict) or not commands:
        raise SystemExit("ERROR: Seed has no commands.")

    if not isinstance(workflows, dict) or not workflows:
        raise SystemExit("ERROR: Seed has no workflows.")

    # Validate workflow references before opening the database for migration.
    for workflow_id, workflow in workflows.items():
        candidates = workflow.get("candidate_commands", [])
        if not isinstance(candidates, list):
            raise SystemExit(
                f"ERROR: Invalid candidate_commands in {workflow_id}."
            )

        candidate_ids = []
        for candidate in candidates:
            if isinstance(candidate, str):
                command_id = candidate
            elif isinstance(candidate, dict):
                command_id = candidate.get("command_id")
            else:
                raise SystemExit(
                    f"ERROR: Invalid candidate entry in {workflow_id}: "
                    f"{candidate!r}"
                )

            if not isinstance(command_id, str) or not command_id:
                raise SystemExit(
                    f"ERROR: Missing command_id in workflow {workflow_id}."
                )

            candidate_ids.append(command_id)

        unknown = set(candidate_ids) - set(commands)
        if unknown:
            raise SystemExit(
                f"ERROR: {workflow_id} references unknown commands: {unknown}"
            )

    DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        existing = connection.execute("""
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """).fetchall()

        if existing:
            raise SystemExit(
                "Migration stopped: database already has tables: "
                + ", ".join(row[0] for row in existing)
                + ". No existing tables were changed."
            )

        connection.executescript(
            SCHEMA.read_text(encoding="utf-8")
        )

        with connection:
            connection.executemany(
                "INSERT INTO metadata(key, value) VALUES (?, ?)",
                [
                    ("schema_version", str(knowledge.get("schema_version", "1.0"))),
                    ("source_file", "knowledge/seed/initial_knowledge.json"),
                ],
            )

            for command_id, command in commands.items():
                connection.execute("""
                    INSERT INTO commands (
                        command_id, description, category, risk,
                        read_only, requires_sudo,
                        requires_confirmation, definition_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    command_id,
                    str(command.get("description", "")),
                    str(command.get("category", "")),
                    str(command.get("risk", "unknown")),
                    int(bool(command.get("read_only", False))),
                    int(bool(command.get("requires_sudo", True))),
                    int(bool(command.get("requires_confirmation", True))),
                    json.dumps(command, ensure_ascii=False),
                ))

                options = command.get("options", {})
                if isinstance(options, dict):
                    for option_name, option in options.items():
                        connection.execute("""
                            INSERT INTO command_options (
                                command_id, option_name, option_json
                            ) VALUES (?, ?, ?)
                        """, (
                            command_id,
                            str(option_name),
                            json.dumps(option, ensure_ascii=False),
                        ))

            for workflow_id, workflow in workflows.items():
                candidates = workflow.get("candidate_commands", [])

                connection.execute("""
                    INSERT INTO workflows (
                        workflow_id, description, triggers_json,
                        candidate_commands_json, definition_json
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    workflow_id,
                    str(workflow.get("description", "")),
                    json.dumps(workflow.get("triggers", []), ensure_ascii=False),
                    json.dumps(candidates, ensure_ascii=False),
                    json.dumps(workflow, ensure_ascii=False),
                ))

                for position, candidate in enumerate(candidates):
                    command_id = (
                        candidate
                        if isinstance(candidate, str)
                        else candidate["command_id"]
                    )
                    connection.execute("""
                        INSERT INTO workflow_commands (
                            workflow_id, command_id, position
                        ) VALUES (?, ?, ?)
                    """, (workflow_id, command_id, position))

                rules = workflow.get("decision_rules", [])
                if rules:
                    rule_list = rules if isinstance(rules, list) else [rules]
                    for position, rule in enumerate(rule_list):
                        connection.execute("""
                            INSERT INTO decision_rules (
                                workflow_id, position, rule_json
                            ) VALUES (?, ?, ?)
                        """, (
                            workflow_id,
                            position,
                            json.dumps(rule, ensure_ascii=False),
                        ))

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        fk_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if integrity != "ok" or fk_errors:
            raise RuntimeError(
                f"Database verification failed: {integrity}; {fk_errors}"
            )

        print("Migration successful.")
        print("Commands:", connection.execute(
            "SELECT COUNT(*) FROM commands"
        ).fetchone()[0])
        print("Command options:", connection.execute(
            "SELECT COUNT(*) FROM command_options"
        ).fetchone()[0])
        print("Workflows:", connection.execute(
            "SELECT COUNT(*) FROM workflows"
        ).fetchone()[0])
        print("Workflow-command links:", connection.execute(
            "SELECT COUNT(*) FROM workflow_commands"
        ).fetchone()[0])
        print("Decision rules:", connection.execute(
            "SELECT COUNT(*) FROM decision_rules"
        ).fetchone()[0])
        print("Integrity:", integrity)
        print("Foreign-key violations:", len(fk_errors))
        print("Database:", DB)

    finally:
        connection.close()


if __name__ == "__main__":
    main()
