# SafePlate

**An allergen agent that routes around failure and refuses when it can't be sure.**

Built for the **Gemma 4 Hackathon | Paris** (42 Paris, 25 July 2026) ·
**Track 2 — Autonomous Agents**

A customer asks, in a language the server doesn't speak, whether a dish contains nuts. The
server photographs the jar. SafePlate reads the label locally, maps ingredients to the EU's 14
declarable allergens, looks up the manufacturer's declaration when the label doesn't resolve,
and produces a printable safety card in the customer's language — or refuses to answer and
says so.

Gemma 4 plans, reads, translates and chooses tools. **A lookup table — not the model — decides
whether an ingredient is an allergen.**

---

## Start here

**[`docs/safeplate-spec.md`](docs/safeplate-spec.md)** — the handoff document. Gate results,
architecture, diagrams, frozen tool contracts, stack, ownership, timeline.

| Path                                                        | What it is                                               |
| ----------------------------------------------------------- | -------------------------------------------------------- |
| `docs/safeplate-spec.md`                                    | **The spec.** Read this first.                           |
| `docs/hackathon-live-info.md`                               | Rules, rubric, deadline, submission requirements         |
| `docs/team.md`                                              | Teammate profiles                                        |
| `pitch/team-onepager.html`                                  | The team proposal (published as an Artifact)             |
| `sejour_pour_tous/`                                         | Shared engine — OCR, Ollama client, guardrail, grounding |
| `setup/` · `tests/` · `ui/` · `mcp_server.py` · `tessdata/` | Tooling, tests, UI skeleton, MCP, OCR data               |
| `archive/`                                                  | Superseded work. Gitignored, nothing deleted.            |

---

## Verified today — measured, not assumed

| Check                                        | Result                                                   |
| -------------------------------------------- | -------------------------------------------------------- |
| Gemma 4 E2B emits well-formed **tool calls** | ✅ arguments extracted verbatim                          |
| E2B **consumes** tool results                | ✅ correct follow-up answer                              |
| E2B **escalates unprompted**                 | ❌ **it does not** — the loop must force it              |
| E2B **vision** on dense printed text         | ❌ fails badly — do not use for labels                   |
| **Tesseract** OCR                            | ✅ **0.90 s**, clean transcription                       |
| SerpApi _nutrition_ endpoint                 | ⚠️ returns nutrition, **no allergen field** — wrong tool |

**Latency:** first tool-calling turn 24.0 s (schemas + cold model), warm turns 7.3 s, OCR
0.90 s. A six-step run is ≈60 s. Re-time on the final prompt before quoting it.

> **The architectural consequence:** a 2B model can't be trusted to remember to escalate, so
> escalation is deterministic and enforced by the orchestrator. The agent's reliability comes
> from the harness, not from hoping the model plans well — which is a better answer to Track
> 2's "does it survive contact with failure?" than a model that usually remembers.

---

## Setup

Install Ollama and `ollama pull gemma4:e2b`; install Tesseract (binary expected at
`C:\Program Files\Tesseract-OCR\tesseract.exe`, language data in `tessdata/`);
`pip install -r requirements.txt`. See `setup/SETUP.md`.

The model is **7.2 GB and lives on one laptop** — demo from that machine; everyone else
develops against the HTTP interface.

Always call Ollama with **`think: false`** and **`temperature: 0`**. E2B otherwise emits a
hidden chain-of-thought that costs ~3× latency for output you never see.

---

## Submission checklist

- [ ] All members joined the Kaggle competition individually, team formed
- [ ] Kaggle Writeup — **Track 2**, ≤1,500 words. Drafts are not judged.
- [ ] Public repo — documented, OSI licence (MIT, present)
- [ ] Working demo — a terminal recording is an accepted format
- [ ] Pre-existing components disclosed in the engineering-process section
