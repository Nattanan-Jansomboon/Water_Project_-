"""
Shared environment/config loading for the Hermes Ingestion + Query backend.

All paths and secrets are pulled from `.env` (see `.env.example`). Nothing here
touches `HERMES_HOME` directly -- that is set right before each `AIAgent()` is
constructed, inside `agents.py`, per the profile-switching rule in the plan.

Model provider: this points at a custom OpenAI-compatible endpoint
(LLM_BASE_URL / LLM_API_KEY / LLM_MODEL), not OpenRouter/OpenAI/Anthropic
directly. Verified against the hermes-agent source (agent/agent_init.py,
_resolve_api_mode): a base_url that doesn't match any known provider hostname
(api.anthropic.com, api.x.ai, chatgpt.com, *.amazonaws.com, etc.) falls
through to the standard "chat_completions" wire format -- i.e. plain
OpenAI-style /chat/completions -- which is what this expects. `provider` is
left unset on purpose so that fallback applies.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


@dataclass(frozen=True)
class Settings:
    obsidian_vault_path: Path
    #raw_data_path: Path
    ingestion_profile_home: Path
    query_profile_home: Path
    llm_base_url: str
    llm_api_key: str
    llm_model: str


def load_settings() -> Settings:
    obsidian_vault_path = Path(_require_env("OBSIDIAN_VAULT_PATH"))
    #raw_data_path = Path(_require_env("RAW_DATA_PATH"))

    # Profile homes are what gets assigned to HERMES_HOME before each agent
    # is constructed (see agents.py). Defaults match the paths given in the
    # plan, but are overridable via .env so this isn't hardcoded to one box.
    ingestion_profile_home = Path(
        os.environ.get("INGESTION_HERMES_HOME", "/home/hp/.hermes/profiles/water_llm")
    )
    query_profile_home = Path(
        os.environ.get("QUERY_HERMES_HOME", "/home/hp/.hermes/profiles/water_llm_qa")
    )

    # Custom OpenAI-compatible endpoint -- all three required, no fallback to
    # OPENROUTER_API_KEY/OPENAI_API_KEY/ANTHROPIC_API_KEY, since this is a
    # specific self-hosted/third-party server, not one of those providers.
    llm_base_url = _require_env("LLM_BASE_URL")
    llm_api_key = _require_env("LLM_API_KEY")
    llm_model = _require_env("LLM_MODEL")

    # Make sure the raw-data upload dir exists; the vault dir we only check,
    # since creating a vault directory implicitly would be surprising.
    #raw_data_path.mkdir(parents=True, exist_ok=True)

    return Settings(
        obsidian_vault_path=obsidian_vault_path,
        #raw_data_path=raw_data_path,
        ingestion_profile_home=ingestion_profile_home,
        query_profile_home=query_profile_home,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
    )


settings = load_settings()
