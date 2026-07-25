"""MCP server for Séjour Pour Tous — the sponsor-facing surface.

Exposes the offline as-of engine as Model Context Protocol tools, so any MCP client
(Claude, Mistral, ChatGPT) can pull versioned, provenance-carrying French immigration
rules straight into its context — Alien Intelligence's exact thesis: licensed, domain
-specific, metered content delivered over MCP. Everything answered here runs locally.

Run (stdio):  .venv\\Scripts\\python.exe mcp_server.py
Register in an MCP client by pointing it at that command.
"""

from __future__ import annotations

from fastmcp import FastMCP

from sejour_pour_tous.pipeline import DocCopilot
from sejour_pour_tous.retrieval import AsOfStore

mcp = FastMCP("Séjour Pour Tous")

_store: AsOfStore | None = None
_copilot: DocCopilot | None = None


def get_store() -> AsOfStore:
    """Lazily open the shared as-of store."""
    global _store
    if _store is None:
        _store = AsOfStore()
    return _store


def get_copilot() -> DocCopilot:
    """Lazily construct the shared document copilot."""
    global _copilot
    if _copilot is None:
        _copilot = DocCopilot()
    return _copilot


@mcp.tool
def list_procedures() -> list[str]:
    """List the immigration procedures this server has grounded rules for."""
    return get_store().procedures()


@mcp.tool
def rules_in_force(procedure: str, as_of_date: str) -> dict:
    """Return the rules in force for a procedure on a date (ISO 'YYYY-MM-DD').

    Only the version valid on that date is returned — superseded versions are filtered out
    in SQL before ranking — and each rule carries its source and validity window.
    """
    rules = get_store().in_force(procedure, as_of_date)
    return {
        "procedure": procedure,
        "as_of_date": as_of_date,
        "rules": [
            {"topic": r.topic, "text": r.text, "source_id": r.source_id,
             "source_url": r.source_url, "valid_from": r.valid_from, "valid_to": r.valid_to}
            for r in rules
        ],
    }


@mcp.tool
def explain_document(image_path: str, as_of_date: str, lang: str = "English") -> dict:
    """Read a local French document image and explain it, grounded, or refuse.

    ``image_path`` is a path on this machine (the document never leaves it). Returns the
    plain-language guidance, the filing deadline, and the sources — or a refusal if the
    document is not one the corpus can ground.
    """
    exp = get_copilot().explain(image_path, as_of_date, lang)
    return {
        "refused": exp.refused,
        "guidance": exp.guidance,
        "deadline": exp.deadline,
        "citations": [
            {"source_id": c.source_id, "source_url": c.source_url,
             "valid_from": c.valid_from, "valid_to": c.valid_to}
            for c in exp.citations
        ],
    }


if __name__ == "__main__":
    mcp.run()
