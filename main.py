"""
FastAPI backend: /api/ingest, /api/query, /api/health, plus the static
frontend at "/".

Run with (from inside the hermes-agent checkout, or with it on PYTHONPATH):
    uv run python -m uvicorn main:app --reload

`AIAgent` instances are never reused across requests, and `run_conversation()`
is blocking, so both endpoints hand the work off to a worker thread via
`asyncio.to_thread`. The profile-switch lock in agents.py protects HERMES_HOME
across those threads.
"""
from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agents
import session_store
from config import settings

app = FastAPI(title="Hermes Ingest + Query API")


class QueryRequest(BaseModel):
    message: str
    session_id: str


class QueryResponse(BaseModel):
    answer: str


class IngestResponse(BaseModel):
    status: str
    final_response: str
    saved_raw_path: str


@app.get("/api/health")
def health() -> dict:
    checks = {
        "obsidian_vault_path_exists": settings.obsidian_vault_path.exists(),
        "raw_data_path_exists": settings.raw_data_path.exists(),
        "ingestion_profile_home_exists": settings.ingestion_profile_home.exists(),
        "query_profile_home_exists": settings.query_profile_home.exists(),
    }
    ok = all(checks.values())
    return {"status": "ok" if ok else "degraded", "checks": checks}


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)) -> IngestResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    # 1. Save the uploaded file into RAW_DATA_PATH.
    dest = settings.raw_data_path / file.filename
    try:
        with dest.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        await file.close()

    task_id = f"ingest-{uuid.uuid4()}"

    # 2-3. Build a fresh Ingestion Agent (in the ingestion profile) and run it.
    try:
        result = await asyncio.to_thread(agents.run_ingestion, dest, task_id)
    except Exception as exc:  # noqa: BLE001 - surface agent failures to the caller
        raise HTTPException(status_code=502, detail=f"Ingestion agent failed: {exc}") from exc

    return IngestResponse(
        status="ok",
        final_response=result.get("final_response", ""),
        saved_raw_path=str(dest),
    )


@app.post("/api/query", response_model=QueryResponse)
async def query(payload: QueryRequest) -> QueryResponse:
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty.")

    history = session_store.get_history(payload.session_id)

    try:
        result = await asyncio.to_thread(
            agents.run_query, payload.message, history, payload.session_id
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Query agent failed: {exc}") from exc

    session_store.set_history(payload.session_id, result.get("messages", []))

    return QueryResponse(answer=result.get("final_response", ""))


# Serve the simple frontend last, so it doesn't shadow the /api/* routes.
_static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
