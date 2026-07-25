"""FastAPI surface for the agent loop.

Matches the contract the interface already codes against, so the two were built
in parallel without waiting on each other:

    POST /api/case                  -> { run_id }
    GET  /api/case/{run_id}         -> { status, pending_question?, trace }
    POST /api/case/{run_id}/answer  -> { status, trace }
    GET  /health

Runs are held in memory. This is a one-day prototype and a restart losing an
open case is the correct trade for not standing up a database.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import loop
from .dishes import DISHES

app = FastAPI(title="SafePlate orchestrator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # prototype: the interface may be served from anywhere
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS: dict[str, loop.Run] = {}


class AnswerRequest(BaseModel):
    answer: str


def _state(run: loop.Run) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": run.run_id,
        "status": run.status,
        "trace": run.as_trace(),
    }
    if run.pending_question:
        payload["pending_question"] = run.pending_question
    if run.error:
        payload["error"] = run.error
    return payload


@app.get("/health")
def health() -> dict[str, Any]:
    """Lets the interface tell live mode from replay mode."""
    return {"ok": True, "dishes": len(DISHES), "open_runs": len(RUNS)}


@app.get("/api/dishes")
def list_dishes() -> dict[str, Any]:
    """The menu the agent can actually reason about — it refuses anything else."""
    return {
        "dishes": [
            {"key": key, "name": dish.name, "cuisine": dish.cuisine}
            for key, dish in DISHES.items()
        ]
    }


@app.post("/api/case")
async def open_case(
    audio: UploadFile | None = None,
    text: str | None = Form(default=None),
) -> dict[str, str]:
    """Start a case from the diner speaking, or from typed text."""
    if audio is None and not (text or "").strip():
        raise HTTPException(status_code=400, detail="send either audio or text")

    run = loop.Run(run_id=f"SP-{uuid.uuid4().hex[:8].upper()}")
    RUNS[run.run_id] = run

    audio_bytes = await audio.read() if audio is not None else None
    audio_format = "wav"
    if audio is not None and audio.filename and "." in audio.filename:
        audio_format = audio.filename.rsplit(".", 1)[-1].lower()

    loop.begin(run, audio=audio_bytes, text=text, audio_format=audio_format)
    return {"run_id": run.run_id}


@app.get("/api/case/{run_id}")
def get_case(run_id: str) -> dict[str, Any]:
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="no such run")
    return _state(run)


@app.post("/api/case/{run_id}/answer")
def answer_case(run_id: str, request: AnswerRequest) -> dict[str, Any]:
    """The kitchen answers, and the case finishes."""
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="no such run")
    if not request.answer.strip():
        raise HTTPException(status_code=400, detail="empty answer")

    loop.answer_kitchen(run, request.answer.strip())
    return _state(run)
