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
    init_db,
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
    """Ensure SQLite database is initialized and synchronized with commands.json."""
    if not DB_FILE.is_file():
        init_db(DB_FILE)
        sync_knowledge_to_db(KNOWLEDGE_FILE, DB_FILE)


def load_knowledge(force_reload: bool = False, use_db: bool = True) -> dict[str, Any]:
    """Load the complete LocalOps knowledge base, preferring SQLite."""
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
            # Fall back to direct JSON if DB fails
            pass

    if not KNOWLEDGE_FILE.is_file():
        raise FileNotFoundError(
            f"Knowledge file not found at: {KNOWLEDGE_FILE}"
        )

    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Knowledge base root must be a JSON object.")

    _CACHED_KNOWLEDGE = data
    return data


def get_commands() -> dict[str, Any]:
    """Return all known commands."""
    knowledge = load_knowledge()
    return knowledge.get("commands", {})


def get_command(command_id: str) -> Optional[dict[str, Any]]:
    """Return one command definition or None."""
    if not isinstance(command_id, str):
        return None
    commands = get_commands()
    return commands.get(command_id)


def get_workflows() -> dict[str, Any]:
    """Return all workflows."""
    knowledge = load_knowledge()
    return knowledge.get("workflows", {})


def get_workflow(workflow_id: str) -> Optional[dict[str, Any]]:
    """Return one workflow definition or None."""
    if not isinstance(workflow_id, str):
        return None
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
    Find the best matching workflow using intelligent natural-language trigger matching.

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

    workflows = get_workflows()

    best_workflow_id: Optional[str] = None
    best_workflow: Optional[dict[str, Any]] = None
    best_score = 0

    for workflow_id, workflow in workflows.items():
        triggers = workflow.get("triggers", [])
        if not isinstance(triggers, list):
            continue

        for trigger in triggers:
            if not isinstance(trigger, str) or not trigger.strip():
                continue

            # Check 1: Direct substring in raw or normalized query
            raw_trig_lower = trigger.lower().strip()
            if raw_trig_lower in request_str.lower():
                score = 100 + len(raw_trig_lower)
                if score > best_score:
                    best_score = score
                    best_workflow_id = workflow_id
                    best_workflow = workflow
                continue

            t_tokens = _tokenize_text(trigger)
            t_norm = " ".join(t_tokens)
            if t_norm and t_norm in q_norm:
                score = 90 + len(t_norm)
                if score > best_score:
                    best_score = score
                    best_workflow_id = workflow_id
                    best_workflow = workflow
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
                    best_workflow = workflow
                continue

            # Check 3: Overlap of content words (at least 2 matching and covering the core trigger)
            if q_content:
                overlap = set(t_content).intersection(q_content)
                if len(overlap) >= 2 and len(overlap) >= len(t_content) * 0.75:
                    score = 30 + len(overlap) * 5
                    if score > best_score:
                        best_score = score
                        best_workflow_id = workflow_id
                        best_workflow = workflow

    # Threshold: only accept confident matches (score >= 30)
    if best_score >= 30:
        return best_workflow_id, best_workflow

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
    Provide the SLM with a focused context.

    If a workflow_id is provided, includes ONLY relevant candidate commands
    and decision rules to avoid overflowing the SLM context window.
    """
    knowledge = load_knowledge()
    all_commands = knowledge.get("commands", {})
    all_workflows = knowledge.get("workflows", {})

    if workflow_id and workflow_id in all_workflows:
        target_workflow = all_workflows[workflow_id]
        candidates = target_workflow.get("candidate_commands", [])

        # Filter commands to candidate commands only
        relevant_cmd_ids = {c.get("command_id") for c in candidates if c.get("command_id")}
        relevant_commands = {
            cid: all_commands[cid]
            for cid in relevant_cmd_ids
            if cid in all_commands
        }

        context = {
            "schema_version": knowledge.get("schema_version", "1.0"),
            "active_workflow_id": workflow_id,
            "workflow": target_workflow,
            "available_commands": relevant_commands,
        }
    else:
        # High-level concise context
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
            "schema_version": knowledge.get("schema_version", "1.0"),
            "workflows": summary_workflows,
            "commands": all_commands,
        }

    return json.dumps(context, indent=2)
