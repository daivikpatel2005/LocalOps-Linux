"""Configuration settings for LocalOps.

Provides centralized, configurable parameters with environment variable overrides
while ensuring strict offline and local operation defaults.
"""

from __future__ import annotations

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
COMMANDS_JSON_PATH = KNOWLEDGE_DIR / "commands.json"
SQLITE_DB_PATH = KNOWLEDGE_DIR / "localops.db"

# LLM Configuration
DEFAULT_MODEL = os.getenv("LOCALOPS_MODEL", "qwen3:1.7b")
OLLAMA_HOST = os.getenv("LOCALOPS_OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_GENERATE_URL = f"{OLLAMA_HOST}/api/generate"
OLLAMA_TAGS_URL = f"{OLLAMA_HOST}/api/tags"

# Timeouts and Limits
LLM_TIMEOUT_SECONDS = int(os.getenv("LOCALOPS_LLM_TIMEOUT", "60"))
COMMAND_TIMEOUT_SECONDS = int(os.getenv("LOCALOPS_COMMAND_TIMEOUT", "30"))
MAX_OUTPUT_BYTES = int(os.getenv("LOCALOPS_MAX_OUTPUT_BYTES", "65536"))  # 64 KB
MAX_PLANNER_RETRIES = int(os.getenv("LOCALOPS_MAX_RETRIES", "1"))

