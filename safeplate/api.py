"""FastAPI surface for the agent loop.

Matches the contract the interface already codes against, so the two were built
in parallel without waiting on each other:

    POST /api/case                  -> { run_id }
    GET  /api/case/{run_id}         -> { status, pending_question?, trace }
    POST /api/case/{run_id}/answer  -> { status, trace }
        body (JSON or form): { risk: none|risk|unsure, note? } or { answer }
    GET  /health

The case itself runs after `POST /api/case` has answered, so a model call that
takes a minute never holds the request open; the interface polls the run.

Runs are held in memory, capped in number and in age. A restart losing an open
case is the correct trade for not standing up a database. The cap never drops a
case a kitchen may still be answering: finished cases go first, and once only
open ones are left a new case is refused rather than one of them evicted.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError

from . import config, loop
from .dishes import DISHES

#: Cases held at once. Once reached, the oldest finished case is dropped first.
MAX_RUNS = 200
#: How long a case stays pollable, in seconds.
RUN_TTL_SECONDS = 60 * 60
#: Largest audio upload accepted. A spoken request is seconds long; 10 MB is
#: minutes of uncompressed WAV.
MAX_AUDIO_BYTES = 10 * 1024 * 1024
DEFAULT_AUDIO_FORMAT = "wav"
HTTP_PAYLOAD_TOO_LARGE = 413
HTTP_CONFLICT = 409
HTTP_SERVICE_UNAVAILABLE = 503
#: Statuses a case can be dropped in before its age runs out: nothing more
#: will happen to it.
FINISHED_STATUSES = frozenset({"complete", "failed"})

app = FastAPI(title="SafePlate orchestrator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(config.CORS_ORIGINS),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

RUNS: dict[str, loop.Run] = {}


class AnswerRequest(BaseModel):
    """The kitchen's reply: a structured `risk` choice, or free text in `answer`."""

    answer: str | None = None
    risk: str | None = None
    note: str | None = None


def _state(run: loop.Run) -> dict[str, Any]:
    """The run as the interface polls it: status, the open question, the trace."""
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
    return {"ok": True, "mode": config.SAFEPLATE_MODE, "dishes": len(DISHES),
            "open_runs": len(RUNS)}


@app.get("/api/dishes")
def list_dishes() -> dict[str, Any]:
    """The menu the agent can actually reason about — it refuses anything else."""
    return {
        "dishes": [
            {"key": key, "name": dish.name, "cuisine": dish.cuisine}
            for key, dish in DISHES.items()
        ]
    }


def _prune_runs(now: float) -> None:
    """Make room for one more case under `MAX_RUNS`, or refuse it.

    Expired cases go first, whatever their state, then the oldest finished ones.
    A case still waiting on the kitchen is never evicted to make room: the new
    case is refused instead, so an answer never lands on a 404.

    Raises:
        HTTPException: 503 when every case held is still open.
    """
    expired = [run_id for run_id, run in RUNS.items()
               if now - run.started > RUN_TTL_SECONDS]
    for run_id in expired:
        del RUNS[run_id]
    finished = [run_id for run_id, run in RUNS.items() if run.status in FINISHED_STATUSES]
    while len(RUNS) >= MAX_RUNS and finished:
        del RUNS[finished.pop(0)]
    if len(RUNS) >= MAX_RUNS:
        raise HTTPException(status_code=HTTP_SERVICE_UNAVAILABLE,
                            detail="too many open cases; try again shortly")


async def _read_audio(audio: UploadFile) -> tuple[bytes, str]:
    """The uploaded bytes and their format, refusing anything over `MAX_AUDIO_BYTES`."""
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=HTTP_PAYLOAD_TOO_LARGE,
                            detail=f"audio is larger than {MAX_AUDIO_BYTES} bytes")
    audio_format = DEFAULT_AUDIO_FORMAT
    if audio.filename and "." in audio.filename:
        audio_format = audio.filename.rsplit(".", 1)[-1].lower()
    return data, audio_format


def _carry_case(run: loop.Run, audio: bytes | None, text: str | None,
                audio_format: str) -> None:
    """Run the loop after the response has gone, failing closed on any crash.

    An exception here would otherwise leave the run polling as `running`
    forever. A failed run carries no verdict, so the trace reads
    `needs_confirmation` and nothing is ever cleared by an error.
    """
    try:
        loop.begin(run, audio=audio, text=text, audio_format=audio_format)
    except Exception as error:  # noqa: BLE001 - any crash must end as `failed`
        run.status = "failed"
        run.error = f"the case could not be completed: {error}"


@app.post("/api/case")
async def open_case(
    background_tasks: BackgroundTasks,
    audio: UploadFile | None = None,
    text: str | None = Form(default=None),
) -> dict[str, str]:
    """Start a case from the diner speaking, or from typed text.

    Returns the run id at once; the loop runs in the background and the
    interface polls `GET /api/case/{run_id}` for where it stopped.
    """
    if audio is None and not (text or "").strip():
        raise HTTPException(status_code=400, detail="send either audio or text")

    audio_bytes, audio_format = None, DEFAULT_AUDIO_FORMAT
    if audio is not None:
        audio_bytes, audio_format = await _read_audio(audio)
        if loop.rules_mode():
            raise HTTPException(status_code=400, detail=loop.AUDIO_NEEDS_GEMMA)

    _prune_runs(time.time())
    run = loop.Run(run_id=f"SP-{uuid.uuid4().hex[:8].upper()}")
    RUNS[run.run_id] = run

    background_tasks.add_task(_carry_case, run, audio_bytes, text, audio_format)
    return {"run_id": run.run_id}


@app.get("/api/case/{run_id}")
def get_case(run_id: str) -> dict[str, Any]:
    """The run's current state, for the interface to poll."""
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="no such run")
    return _state(run)


async def _read_answer(request: Request) -> AnswerRequest:
    """Accept the answer as a JSON body or as form fields, whichever was sent."""
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            payload: Any = await request.json()
        except ValueError as error:
            raise HTTPException(status_code=400, detail="body is not JSON") from error
    else:
        payload = dict(await request.form())

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be an object")
    try:
        return AnswerRequest.model_validate(payload)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error


async def _answer(run: loop.Run, answer: str, risk: str | None) -> dict[str, Any]:
    """Hand the answer to the loop; 409 when the case is not waiting for one.

    The loop claims the run atomically, so of two answers racing for the same
    case exactly one is applied and the other is told so.
    """
    try:
        await run_in_threadpool(loop.answer_kitchen, run, answer, risk=risk)
    except loop.NotAwaitingAnswer as error:
        raise HTTPException(status_code=HTTP_CONFLICT, detail=str(error)) from error
    return _state(run)


@app.post("/api/case/{run_id}/answer")
async def answer_case(run_id: str, request: Request) -> dict[str, Any]:
    """The kitchen answers, and the case finishes.

    A structured `risk` (`none`, `risk` or `unsure`, with an optional `note`) is
    preferred. Free text in `answer` is still accepted and read fail-closed. A
    case that is not waiting for an answer, including one another answer has
    already claimed, returns 409 and keeps its verdict.
    """
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="no such run")
    body = await _read_answer(request)

    if body.risk is not None:
        risk = body.risk.strip().lower()
        if risk not in loop.RISK_VERDICTS:
            raise HTTPException(status_code=400, detail="risk must be none, risk or unsure")
        return await _answer(run, (body.note or body.answer or "").strip(), risk)

    answer = (body.answer or "").strip()
    if not answer:
        raise HTTPException(status_code=400, detail="empty answer")
    return await _answer(run, answer, None)
