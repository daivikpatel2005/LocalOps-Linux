import json
import sqlite3
from pathlib import Path
from urllib.parse import quote


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_FILE = BASE_DIR / "data" / "localops.db"


def _connect():
    """Open the knowledge database in read-only mode."""

    if not DATABASE_FILE.is_file():
        raise FileNotFoundError(
            f"LocalOps knowledge database not found: {DATABASE_FILE}"
        )

    database_uri = (
        "file:"
        + quote(str(DATABASE_FILE.resolve()), safe="/")
        + "?mode=ro"
    )

    connection = sqlite3.connect(database_uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _decode_metadata_value(key, value):
    """Decode JSON-encoded metadata while preserving legacy strings."""

    if key in {"name", "description", "policy"}:
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    # schema_version was stored as a plain string by the migration.
    return value


def load_knowledge():
    """Load the complete knowledge base from SQLite."""

    with _connect() as connection:
        metadata_rows = connection.execute(
            "SELECT key, value FROM metadata"
        ).fetchall()

        metadata = {
            row["key"]: _decode_metadata_value(
                row["key"], row["value"]
            )
            for row in metadata_rows
        }

        command_rows = connection.execute("""
            SELECT command_id, definition_json
            FROM commands
            ORDER BY command_id
        """).fetchall()

        workflow_rows = connection.execute("""
            SELECT workflow_id, definition_json
            FROM workflows
            ORDER BY workflow_id
        """).fetchall()

    commands = {
        row["command_id"]: json.loads(row["definition_json"])
        for row in command_rows
    }

    workflows = {
        row["workflow_id"]: json.loads(row["definition_json"])
        for row in workflow_rows
    }

    return {
        "schema_version": metadata.get("schema_version", "unknown"),
        "name": metadata.get("name", ""),
        "description": metadata.get("description", ""),
        "policy": metadata.get("policy", {}),
        "commands": commands,
        "workflows": workflows,
    }


def get_commands():
    """Return all known command definitions."""

    return load_knowledge().get("commands", {})


def get_command(command_id):
    """Return one command definition, or None if unknown."""

    return get_commands().get(command_id)


def get_workflows():
    """Return all workflow definitions."""

    return load_knowledge().get("workflows", {})


def get_workflow(workflow_id):
    """Return one workflow definition, or None if unknown."""

    return get_workflows().get(workflow_id)


def find_workflow(user_request):
    """
    Find the best matching workflow using trigger phrases.

    Returns (workflow_id, workflow), or (None, None).
    """

    if not isinstance(user_request, str):
        return None, None

    request = user_request.lower().strip()
    workflows = get_workflows()

    best_workflow_id = None
    best_workflow = None
    best_score = 0

    for workflow_id, workflow in workflows.items():
        triggers = workflow.get("triggers", [])

        if not isinstance(triggers, list):
            continue

        score = 0

        for trigger in triggers:
            if not isinstance(trigger, str):
                continue

            trigger = trigger.lower().strip()

            if trigger and trigger in request:
                score += len(trigger)

        if score > best_score:
            best_score = score
            best_workflow_id = workflow_id
            best_workflow = workflow

    return best_workflow_id, best_workflow


def build_context():
    """Build the command and workflow context for the local SLM."""

    knowledge = load_knowledge()

    context = {
        "schema_version": knowledge.get("schema_version"),
        "commands": knowledge.get("commands", {}),
        "workflows": knowledge.get("workflows", {}),
    }

    return json.dumps(context, indent=2, ensure_ascii=False)
