"""
Builds the two Hermes AIAgent instances (Ingestion / Query) and runs a single
turn on each.

Key constraint from the Hermes docs: profile selection happens ONLY through
the process-wide `HERMES_HOME` env var (there is no `profile=` kwarg on
`AIAgent`). Because it's process-wide, we serialize
"set HERMES_HOME -> construct AIAgent -> run_conversation()" behind a single
`threading.Lock` (Option A from the plan) so an ingest request and a query
request can never interleave and read each other's profile.

`enabled_toolsets` uses the REAL Hermes toolset names -- verified against the
hermes-agent source (toolsets.py), not guessed: "terminal" and "file" (NOT
"filesystem", which does not exist as a toolset).
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from run_agent import AIAgent

from config import settings

# Guards the critical section: env var mutation + agent construction + the
# blocking run_conversation() call. Only one profile can be "active" at a time.
_profile_switch_lock = threading.Lock()


def _build_ingestion_agent() -> AIAgent:
    return AIAgent(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        quiet_mode=True,
        skip_memory=True,
        skip_context_files=True,
        ephemeral_system_prompt=(
            f"You are an Ingestion Agent. Raw uploaded files live in "
            f"{settings.raw_data_path}. Your job is to read the given file, "
            f"extract/organize its content into a well-structured Obsidian "
            f"markdown note (with proper title, tags, and links if relevant), "
            f"and save it into {settings.obsidian_vault_path}. Confirm the "
            f"final saved file path in your response."
        ),
        enabled_toolsets=["terminal", "file"],
        max_iterations=50,
    )


def _build_query_agent() -> AIAgent:
    return AIAgent(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        quiet_mode=True,
        skip_memory=True,
        skip_context_files=True,
        ephemeral_system_prompt=(
            f"You are a Query Agent. Answer the user's questions using the "
            f"notes stored in the Obsidian vault at {settings.obsidian_vault_path}. "
            f"Search the vault for relevant notes before answering. Cite which "
            f"note(s) you used."
        ),
        # No "terminal" here on purpose -- read-only-ish, avoids accidental writes.
        enabled_toolsets=["file"],
        max_iterations=30,
    )


def run_ingestion(saved_raw_path: Path, task_id: str) -> Dict[str, Any]:
    """Set HERMES_HOME to the ingestion profile, build a fresh agent, run one turn."""
    with _profile_switch_lock:
        os.environ["HERMES_HOME"] = str(settings.ingestion_profile_home)
        agent = _build_ingestion_agent()
        result = agent.run_conversation(
            user_message=(
                f"Process the file at {saved_raw_path} and save an organized "
                f"note into the vault."
            ),
            task_id=task_id,
        )
    return result


def run_query(
    message: str,
    conversation_history: Optional[List[Dict[str, Any]]],
    session_id: str,
) -> Dict[str, Any]:
    """Set HERMES_HOME to the query profile, build a fresh agent, run one turn."""
    with _profile_switch_lock:
        os.environ["HERMES_HOME"] = str(settings.query_profile_home)
        agent = _build_query_agent()
        result = agent.run_conversation(
            user_message=message,
            conversation_history=conversation_history or [],
            task_id=session_id,
        )
    return result
