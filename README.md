# SafePlate

**An allergen agent that routes around failure and refuses when it can't be sure.**

Gemma 4 Hackathon | Paris · **Track 2 — Autonomous Agents** · 42 Paris, 25 July 2026

---

A customer asks, in a language the server doesn't speak, whether a dish contains nuts. The
server has thirty seconds, a jar labelled in another language, and a legal obligation not to
guess.

SafePlate photographs the label, reads it locally, maps ingredients to the EU's 14 declarable
allergens, looks up the manufacturer's declaration when the label doesn't resolve, and produces
a safety card in the customer's language — **or refuses to answer and says why.**

Its most valuable output is often `DO NOT SERVE — I can't confirm`.

## The design decision

**Gemma 4 plans, reads, translates and chooses tools. A deterministic lookup table decides
whether an ingredient is an allergen.**

| Gemma 4 E2B owns                             | The table owns                                     |
| -------------------------------------------- | -------------------------------------------------- |
| Reading OCR text into structured ingredients | **Whether an ingredient is a declarable allergen** |
| Translating staff ↔ customer language        | `casein → milk`, `semolina → gluten`               |
| Choosing the next tool                       |                                                    |
| Composing the explanation or the refusal     |                                                    |

A language model is never the last line of defence. The reasoning is learned; the safety call
is deterministic and auditable.

## Escalation is enforced by the loop, not by the model

We measured this rather than assuming it. Given ingredients including `casein` and the
unresolved token `natural flavourings`, Gemma 4 E2B correctly called `match_allergens` — but
when handed back `"unresolved": ["natural flavourings"]`, **it did not escalate.** It answered
about the casein and stopped.

So escalation is control flow, not a hope:

```python
if result.unresolved:            # not "if the model decides to"
    force_tool("lookup_product")
if sources_conflict(evidence):
    force_tool("escalate")       # refuse; never average conflicting sources
```

**The agent's reliability comes from the harness, not from a 2B model remembering to plan
well.** Track 2 asks whether an agent survives contact with failure — a loop that _guarantees_
escalation is a better answer than a model that usually remembers.

## Measured, not assumed

| Check                                | Result                          |
| ------------------------------------ | ------------------------------- |
| E2B emits well-formed **tool calls** | ✅ arguments extracted verbatim |
| E2B **consumes** tool results        | ✅ correct follow-up            |
| E2B **escalates unprompted**         | ❌ it does not — see above      |
| E2B **vision** on dense printed text | ❌ fails badly — not used       |
| **Tesseract** OCR on a label         | ✅ **0.90 s**, clean            |

**Latency:** 24.0 s first tool-calling turn (schemas in context, model cold), **7.3 s** warm,
0.90 s OCR. A six-step run is ≈60 s.

## Architecture

```
photo ──► read_label (Tesseract) ──► Gemma 4: structure ingredients
                │ low confidence                    │
                └──► RECOVERY: re-shoot             ▼
                                          match_allergens (EU-14 table)
                                                    │
                             unresolved? ──FORCED──► lookup_product (SerpApi)
                                                    │
                        sources conflict? ──────────► escalate → DO NOT SERVE
                                                    │
                                                    ▼
                                    safety card + full agent trace
```

Everything except `lookup_product` runs on-device. Full diagrams, frozen tool contracts and the
EU-14 allergen set are in **[`docs/safeplate-spec.md`](docs/safeplate-spec.md)**.

## Run it

Requires [Ollama](https://ollama.com) and Tesseract.

```bash
ollama pull gemma4:e2b
pip install -r requirements.txt
```

Tesseract binary is expected at `C:\Program Files\Tesseract-OCR\tesseract.exe`; language data
ships in `tessdata/`. Both paths are set in `safeplate/config.py`.

```python
from safeplate.ocr import LabelReader
from safeplate.llm import ...
```

> **Always call the model with `think: false` and `temperature: 0`.** Gemma 4 E2B otherwise
> emits a hidden chain-of-thought into Ollama's separate `thinking` field — invisible output you
> still wait for, at roughly 3× the latency. The Ollama Python client (0.4.7) has no `think`
> parameter, which is why `safeplate/llm.py` calls the loopback HTTP API directly.

## Layout

```
safeplate/     config · llm (tuned Ollama client) · ocr (Tesseract reader)
docs/          safeplate-spec.md — architecture, diagrams, tool contracts
tessdata/      Tesseract language data (eng, fra)
```

## Provenance

`llm.py`, `ocr.py` and `config.py` were extracted from an earlier offline-document project by
the same author and predate the hackathon. Everything else is built during the event.
Disclosed per competition rules §4.3.

## Licence

MIT — see [`LICENSE`](LICENSE).
