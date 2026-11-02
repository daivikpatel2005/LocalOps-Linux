"""Knowledge base module for LocalOps.

Provides command definitions, safety metadata, workflow definitions,
and intelligent workflow matching. Backed by SQLite and synchronized
with knowledge/commands.json.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Optional

from .database import (
    DEFAULT_DB_PATH,
    DEFAULT_JSON_PATH,
    ensure_db_ready,
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

BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_FILE = BASE_DIR / "knowledge" / "commands.json"
DB_FILE = BASE_DIR / "knowledge" / "localops.db"

# In-memory cache for fast lookups
_CACHED_KNOWLEDGE: Optional[dict[str, Any]] = None

# Linguistic normalization maps for realistic phrasing
_STEM_MAP = {
    "crashing": "crash",
    "crashes": "crash",
    "crashed": "crash",
    "failing": "fail",
    "failed": "fail",
    "fails": "fail",
    "failure": "fail",
    "disconnecting": "disconnect",
    "disconnects": "disconnect",
    "disconnected": "disconnect",
    "freezing": "freeze",
    "freezes": "freeze",
    "frozen": "freeze",
    "ram": "memory",
    "mem": "memory",
    "wi-fi": "wifi",
    "wireless": "wifi",
    "apps": "app",
    "application": "app",
    "applications": "app",
    "program": "app",
    "programs": "app",
    "slowdown": "slow",
    "sluggish": "slow",
    "overheating": "overheat",
    "overheat": "overheat",
    "overheated": "overheat",
    "hot": "overheat",
    "temperature": "temp",
    "temperatures": "temp",
    "thermal": "temp",
    "fans": "fan",
    "fan": "fan",
    "battery": "battery",
    "draining": "drain",
    "drain": "drain",
    "drained": "drain",
    "charging": "charge",
    "charge": "charge",
    "disks": "disk",
    "drive": "disk",
    "drives": "disk",
    "storage": "disk",
    "inodes": "inode",
    "inode": "inode",
    "services": "service",
    "daemons": "service",
    "daemon": "service",
    "networking": "network",
    "internet": "network",
    "ports": "port",
    "port": "port",
    "sockets": "port",
    "socket": "port",
    "listening": "listen",
    "listen": "listen",
    "drivers": "driver",
    "driver": "driver",
    "modules": "module",
    "module": "module",
    "specs": "spec",
    "specifications": "spec",
    "specification": "spec",
    "bottlenecks": "bottleneck",
    "bottleneck": "bottleneck",
    "throttling": "throttle",
    "throttled": "throttle",
    "iowait": "iowait",
    "booting": "boot",
    "startup": "boot",
    "distro": "distro",
    "distribution": "distro",
    "distributions": "distro",
    "neighbor": "neighbor",
    "neighbors": "neighbor",
    "arp": "arp",
    "locale": "locale",
    "locales": "locale",
    "keymap": "keyboard",
    "keymaps": "keyboard",
    "keyboards": "keyboard",
    "timezone": "time",
    "timezones": "time",
}

_STOP_WORDS = {
    "is",
    "my",
    "the",
    "a",
    "an",
    "why",
    "what",
    "how",
    "keeps",
    "keep",
    "to",
    "in",
    "on",
    "of",
    "for",
    "and",
    "are",
    "does",
    "do",
    "it",
    "me",
}


def ensure_database_ready() -> None:
    """Ensure SQLite database is initialized and populated."""
    ensure_db_ready(DB_FILE, KNOWLEDGE_FILE)


def load_knowledge(force_reload: bool = False, use_db: bool = True) -> dict[str, Any]:
    """Load the complete LocalOps knowledge base, executing via SQLite."""
    global _CACHED_KNOWLEDGE

    if _CACHED_KNOWLEDGE is not None and not force_reload:
        return _CACHED_KNOWLEDGE

    if use_db:
        try:
            ensure_database_ready()
            data = load_knowledge_from_db(DB_FILE)
            if data and data.get("commands"):
                _CACHED_KNOWLEDGE = data
                return data
        except Exception:
            pass

    # Fallback to direct JSON only if DB is unavailable and commands.json exists
    if KNOWLEDGE_FILE.is_file():
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Knowledge base root must be a JSON object.")

        _CACHED_KNOWLEDGE = data
        return data

    raise FileNotFoundError(
        f"Neither SQLite database at {DB_FILE} nor JSON at {KNOWLEDGE_FILE} could be loaded."
    )


def get_commands() -> dict[str, Any]:
    """Return all known commands, querying SQLite directly."""
    try:
        ensure_database_ready()
        if is_database_populated(DB_FILE):
            return get_db_all_commands(DB_FILE)
    except Exception:
        pass
    knowledge = load_knowledge()
    return knowledge.get("commands", {})


def get_command(command_id: str) -> Optional[dict[str, Any]]:
    """Return one command definition directly from SQLite or None."""
    if not isinstance(command_id, str):
        return None
    try:
        ensure_database_ready()
        if is_database_populated(DB_FILE):
            cmd = get_db_command(command_id, DB_FILE)
            if cmd is not None:
                return cmd
    except Exception:
        pass
    commands = get_commands()
    return commands.get(command_id)


def get_workflows() -> dict[str, Any]:
    """Return all workflows, querying SQLite directly."""
    try:
        ensure_database_ready()
        if is_database_populated(DB_FILE):
            return get_db_all_workflows(DB_FILE)
    except Exception:
        pass
    knowledge = load_knowledge()
    return knowledge.get("workflows", {})


def get_workflow(workflow_id: str) -> Optional[dict[str, Any]]:
    """Return one workflow definition directly from SQLite or None."""
    if not isinstance(workflow_id, str):
        return None
    try:
        ensure_database_ready()
        if is_database_populated(DB_FILE):
            wf = get_db_workflow(workflow_id, DB_FILE)
            if wf is not None:
                return wf
    except Exception:
        pass
    workflows = get_workflows()
    return workflows.get(workflow_id)


def _tokenize_text(text: str) -> list[str]:
    """Tokenize and stem text for flexible natural language matching."""
    text = text.lower()
    text = text.replace("wi-fi", "wifi")
    # Replace non-alphanumeric chars with spaces
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens: list[str] = []
    for word in text.split():
        stemmed = _STEM_MAP.get(word, word)
        tokens.append(stemmed)
    return tokens


def find_workflow(
    user_request: str,
) -> tuple[Optional[str], Optional[dict[str, Any]]]:
    """
    Find the best matching workflow using intelligent natural-language trigger matching
    queried directly from SQLite.

    Handles phrasing variations, word order differences, word forms (stemming),
    and punctuation.

    Returns:
        (workflow_id, workflow) if a confident match is found,
        (None, None) otherwise.
    """
    if not isinstance(user_request, str):
        return None, None

    request_str = user_request.strip()
    if not request_str:
        return None, None

    q_tokens = _tokenize_text(request_str)
    if not q_tokens:
        return None, None

    q_norm = " ".join(q_tokens)
    q_content = [t for t in q_tokens if t not in _STOP_WORDS]

    # Query triggers directly from SQLite
    try:
        ensure_database_ready()
        trigger_pairs = (
            get_db_triggers(DB_FILE) if is_database_populated(DB_FILE) else []
        )
    except Exception:
        trigger_pairs = []

    if not trigger_pairs:
        # Fallback to in-memory workflows if DB trigger query is empty
        workflows = get_workflows()
        trigger_pairs = [
            (wid, trig)
            for wid, w in workflows.items()
            for trig in w.get("triggers", [])
        ]

    best_workflow_id: Optional[str] = None
    best_score = 0

    for workflow_id, trigger in trigger_pairs:
        if not isinstance(trigger, str) or not trigger.strip():
            continue

        # Check 1: Direct substring in raw or normalized query
        raw_trig_lower = trigger.lower().strip()
        if raw_trig_lower in request_str.lower():
            score = 100 + len(raw_trig_lower)
            if score > best_score:
                best_score = score
                best_workflow_id = workflow_id
            continue

        t_tokens = _tokenize_text(trigger)
        t_norm = " ".join(t_tokens)
        if t_norm and t_norm in q_norm:
            score = 90 + len(t_norm)
            if score > best_score:
                best_score = score
                best_workflow_id = workflow_id
            continue

        t_content = [t for t in t_tokens if t not in _STOP_WORDS]
        if not t_content:
            continue

        # Check 2: All content words in trigger are present in request
        if all(t in q_tokens for t in t_content):
            score = 50 + len(t_content) * 10
            if score > best_score:
                best_score = score
                best_workflow_id = workflow_id
            continue

        # Check 3: Overlap of content words (at least 2 matching and covering the core trigger)
        if q_content:
            overlap = set(t_content).intersection(q_content)
            if len(overlap) >= 2 and len(overlap) >= len(t_content) * 0.75:
                score = 30 + len(overlap) * 5
                if score > best_score:
                    best_score = score
                    best_workflow_id = workflow_id

    # Threshold: only accept confident matches (score >= 30)
    if best_score >= 30 and best_workflow_id:
        return best_workflow_id, get_workflow(best_workflow_id)

    return None, None


def get_supported_troubleshooting_areas() -> list[str]:
    """Return a list of human-readable supported diagnostic categories."""
    workflows = get_workflows()
    categories = []
    for wid, w in workflows.items():
        desc = w.get("description", wid)
        categories.append(f"- {wid}: {desc}")
    return categories


def build_context(workflow_id: Optional[str] = None) -> str:
    """
    Provide the SLM with a focused context queried directly from SQLite.

    If a workflow_id is provided, includes ONLY relevant candidate commands
    and decision rules to avoid overflowing the SLM context window.
    """
    if workflow_id:
        target_workflow = get_workflow(workflow_id)
        if target_workflow:
            candidates = target_workflow.get("candidate_commands", [])
            relevant_cmd_ids = {
                c.get("command_id") for c in candidates if c.get("command_id")
            }
            relevant_commands = {}
            for cid in relevant_cmd_ids:
                cmd_def = get_command(cid)
                if cmd_def:
                    relevant_commands[cid] = cmd_def

            context = {
                "schema_version": "1.0",
                "active_workflow_id": workflow_id,
                "workflow": target_workflow,
                "available_commands": relevant_commands,
            }
            return json.dumps(context, indent=2)

    # High-level concise context
    all_workflows = get_workflows()
    all_commands = get_commands()
    summary_workflows = {
        wid: {
            "description": w.get("description", ""),
            "candidate_command_ids": [
                c.get("command_id")
                for c in w.get("candidate_commands", [])
                if isinstance(c, dict)
            ],
        }
        for wid, w in all_workflows.items()
    }

    context = {
        "schema_version": "1.0",
        "workflows": summary_workflows,
        "commands": all_commands,
    }
    return json.dumps(context, indent=2)
