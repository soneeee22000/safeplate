"""FastAPI backend for the Séjour Pour Tous demo — fully offline.

Three endpoints keep the demo snappy: /api/analyze runs OCR+understanding once (slow),
/api/rules is an instant as-of SQL lookup (drives the slider's €75↔€100 flip), and
/api/explain produces the grounded cite-or-refuse answer on demand. Uploaded documents
stay on disk locally and are never sent anywhere.

Run:  .venv\\Scripts\\python.exe -m uvicorn ui.server:app --port 8000
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from sejour_pour_tous.models import Citation, DocFacts, Rule
from sejour_pour_tous.pipeline import DocCopilot

app = FastAPI(title="Séjour Pour Tous")
_copilot = DocCopilot()
_facts_by_doc: dict[str, DocFacts] = {}  # in-memory session store (demo scope)
_INDEX = Path(__file__).parent / "index.html"


class DocRequest(BaseModel):
    """Body identifying an analyzed document and the as-of date."""

    doc_id: str
    as_of: str
    lang: str = "English"


def _facts_dict(f: DocFacts) -> dict:
    """Serialize document facts for the client (raw OCR text omitted)."""
    return {"document_type": f.document_type, "procedure": f.procedure,
            "validity_from": f.validity_from, "validity_to": f.validity_to,
            "authorizes_work": f.authorizes_work, "summary": f.summary}


def _rule_dict(r: Rule) -> dict:
    """Serialize an in-force rule for the client."""
    return {"topic": r.topic, "text": r.text, "source_id": r.source_id,
            "source_url": r.source_url, "valid_from": r.valid_from, "valid_to": r.valid_to}


def _citation_dict(c: Citation) -> dict:
    """Serialize a citation for the client."""
    return {"source_id": c.source_id, "source_url": c.source_url,
            "valid_from": c.valid_from, "valid_to": c.valid_to}


def _load_facts(doc_id: str) -> DocFacts:
    """Fetch stored facts or raise 404 if the document was never analyzed."""
    facts = _facts_by_doc.get(doc_id)
    if facts is None:
        raise HTTPException(status_code=404, detail="Unknown doc_id — analyze first.")
    return facts


@app.get("/")
def index() -> FileResponse:
    """Serve the single-page demo UI."""
    return FileResponse(_INDEX)


@app.post("/api/analyze")
async def analyze(file: UploadFile) -> JSONResponse:
    """OCR + understand an uploaded document once; return its facts and an id."""
    suffix = Path(file.filename or "doc.png").suffix or ".png"
    tmp = Path(tempfile.gettempdir()) / f"spt_{uuid.uuid4().hex}{suffix}"
    tmp.write_bytes(await file.read())
    facts = _copilot.understand_document(tmp)
    doc_id = uuid.uuid4().hex
    _facts_by_doc[doc_id] = facts
    return JSONResponse({"doc_id": doc_id, "facts": _facts_dict(facts),
                         "covered": _copilot.rules_in_force(facts, "2026-01-01") != []})


@app.post("/api/rules")
def rules(req: DocRequest) -> JSONResponse:
    """Instant as-of lookup: the rules in force for this document on ``as_of``."""
    facts = _load_facts(req.doc_id)
    in_force = _copilot.rules_in_force(facts, req.as_of)
    return JSONResponse({"as_of": req.as_of, "rules": [_rule_dict(r) for r in in_force]})


@app.post("/api/explain")
def explain(req: DocRequest) -> JSONResponse:
    """Grounded cite-or-refuse explanation for this document as of ``as_of``."""
    facts = _load_facts(req.doc_id)
    in_force = _copilot.rules_in_force(facts, req.as_of)
    exp = _copilot._explainer.explain(facts, in_force, req.lang)  # noqa: SLF001
    return JSONResponse({"refused": exp.refused, "guidance": exp.guidance,
                         "deadline": exp.deadline,
                         "citations": [_citation_dict(c) for c in exp.citations],
                         "redacted_claims": list(exp.redacted_claims)})
