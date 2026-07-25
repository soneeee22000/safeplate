# SafePlate

**An allergen agent that routes around failure — and refuses when it can't be sure.**

[![License](https://img.shields.io/github/license/RitaTY/gemma4?style=flat-square)](LICENSE)
[![Model](https://img.shields.io/badge/Gemma%204-E2B%20local-1a73e8?style=flat-square)](https://ollama.com/library/gemma4)
[![Runtime](https://img.shields.io/badge/runtime-Ollama-000000?style=flat-square)](https://ollama.com)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab?style=flat-square)](https://python.org)
[![Last commit](https://img.shields.io/github/last-commit/RitaTY/gemma4?style=flat-square)](https://github.com/RitaTY/gemma4/commits/main)

A customer asks, in a language the server doesn't speak, whether a dish contains nuts. The
server has thirty seconds, a jar labelled in another language, and a legal obligation not to
guess.

SafePlate photographs the label, reads it on-device, maps ingredients to the EU's 14 declarable
allergens, looks up the manufacturer's declaration when the label doesn't resolve, and produces
a safety card in the customer's language — **or refuses, and says exactly why.** Its most
valuable output is often `DO NOT SERVE — I can't confirm`.

Built for the **Gemma 4 Hackathon | Paris**, Track 2 (Autonomous Agents), 42 Paris.

<!-- TODO: Add demo GIF -->

---

## The design decision

**Gemma 4 plans, reads, translates and chooses tools. A deterministic table decides whether an
ingredient is an allergen.**

| Gemma 4 E2B owns                             | The lookup table owns                   |
| -------------------------------------------- | --------------------------------------- |
| Reading OCR text into structured ingredients | **Whether an ingredient is declarable** |
| Translating staff to customer language       | `casein → milk`, `semolina → gluten`    |
| Choosing the next tool                       |                                         |
| Composing the explanation, or the refusal    |                                         |

A language model is never the last line of defence. The reasoning is learned; the safety call
is deterministic and auditable.

## Architecture

```mermaid
flowchart TD
    PHOTO["Label photo"] --> OCR["read_label<br/>Tesseract, 0.9s"]
    OCR -->|low confidence| RESHOOT["Recovery:<br/>ask for a new photo"]
    RESHOOT --> OCR
    OCR -->|text| GEMMA["Gemma 4 E2B<br/>structure ingredients"]
    GEMMA --> MATCH["match_allergens<br/>EU-14 table, deterministic"]
    MATCH -->|all resolved| CARD
    MATCH -->|unresolved| LOOKUP["lookup_product<br/>SerpApi"]
    LOOKUP -->|sources agree| CARD["Safety card<br/>+ agent trace"]
    LOOKUP -->|sources conflict| STOP["escalate<br/>DO NOT SERVE"]

    style STOP fill:#f6e2e0,stroke:#a02f28,color:#111
    style CARD fill:#e0efe6,stroke:#176b45,color:#111
    style MATCH fill:#eef1f5,stroke:#2a4c99,color:#111
```

Everything except `lookup_product` runs on-device. The dashed path is not an error case bolted
on afterwards — it is the behaviour the project is built around.

## Escalation is enforced by the loop, not by the model

We measured this rather than assuming it. Given ingredients including `casein` and the
unresolved token `natural flavourings`, Gemma 4 E2B correctly called `match_allergens` — but
handed back `"unresolved": ["natural flavourings"]`, **it did not escalate.** It answered about
the casein and stopped.

So escalation is control flow, not a hope:

```python
if result.unresolved:            # not "if the model decides to"
    force_tool("lookup_product")

if sources_conflict(evidence):
    force_tool("escalate")       # refuse; never average conflicting sources
```

**Reliability comes from the harness, not from a 2B model remembering to plan well.** Track 2
asks whether an agent survives contact with failure; a loop that _guarantees_ escalation is a
better answer than a model that usually remembers.

## Measured, not assumed

| Check                                | Result                                    |
| ------------------------------------ | ----------------------------------------- |
| E2B emits well-formed **tool calls** | Pass — arguments extracted verbatim       |
| E2B **consumes** tool results        | Pass — correct follow-up answer           |
| E2B **escalates unprompted**         | **Fail** — hence the forced loop above    |
| E2B **vision** on dense printed text | **Fail** — echoed the prompt, then digits |
| **Tesseract** OCR on a label         | Pass — **0.90 s**, clean transcription    |

Latency: **24.0 s** first tool-calling turn (schemas in context, model cold), **7.3 s** warm,
**0.90 s** OCR. A six-step run is roughly 60 s.

## Features

- **On-device label reading** — Tesseract (`eng+fra`); no photo leaves the machine
- **EU-14 allergen matching** — Regulation (EU) No 1169/2011, with synonym resolution
- **Guaranteed escalation** — unresolved ingredients always trigger an external lookup
- **Refusal as a first-class outcome** — conflicting sources produce `DO NOT SERVE`, never an average
- **Multilingual output** — verdict rendered in the customer's language
- **Visible agent trace** — every tool call, result and decision shown, not summarised

## Tech stack

| Layer             | Choice                               | Why                                                 |
| ----------------- | ------------------------------------ | --------------------------------------------------- |
| Model             | Gemma 4 **E2B** via Ollama           | Runs offline on a laptop; native function calling   |
| Model call        | Ollama HTTP `/api/chat` with `tools` | `think:false`, `temperature:0`                      |
| OCR               | Tesseract (`eng+fra`)                | E2B vision fails on dense print; Tesseract is 0.9 s |
| Orchestrator      | FastAPI                              | Owns control flow and forced escalation             |
| Allergen logic    | Plain Python table                   | Deterministic and auditable by design               |
| External evidence | SerpApi (`engine=google`)            | Manufacturer declarations the label omits           |

> **`think: false` is load-bearing.** Gemma 4 E2B otherwise emits a chain-of-thought into
> Ollama's separate `thinking` field — invisible output you still wait for, at roughly 3x the
> latency. The Ollama Python client (0.4.7) has no `think` parameter, which is why
> `safeplate/llm.py` calls the loopback HTTP API directly.

## Getting started

**Prerequisites:** Python 3.10+, [Ollama](https://ollama.com), and
[Tesseract OCR](https://github.com/tesseract-ocr/tesseract).

```bash
git clone git@github.com:RitaTY/gemma4.git
cd gemma4

ollama pull gemma4:e2b        # 7.2 GB
pip install -r requirements.txt
```

Tesseract's binary path and language data are set in `safeplate/config.py`; the `eng` and `fra`
data ship in `tessdata/`, so no extra download is needed.

```python
from safeplate.ocr import DocumentReader
from safeplate.llm import chat

label_text = DocumentReader().read("label.jpg")
reply = chat(system="Extract the ingredient list.", user=label_text)
```

Optional, for the external lookup only:

```bash
export SERPAPI_KEY=...
```

## Project structure

```
safeplate/          config · llm (tuned Ollama client) · ocr (Tesseract reader)
docs/
  safeplate-spec.md architecture, use-case and sequence diagrams, tool contracts
tessdata/           Tesseract language data (eng, fra)
```

Full technical spec, including the frozen tool contracts and the EU-14 allergen set:
**[`docs/safeplate-spec.md`](docs/safeplate-spec.md)**

## Team

Built at the Gemma 4 Hackathon, 42 Paris, by a team of four.

|                                                                         |                                                   |
| ----------------------------------------------------------------------- | ------------------------------------------------- |
| **Rita**                                                                | Product, frontend, agent trace view, pitch        |
| **Afaq**                                                                | SerpApi lookup, evidence normalisation, FastAPI   |
| **Yan**                                                                 | Agent loop, tool registry, forced escalation      |
| **Pyae Sone (Seon)** — [@soneeee22000](https://github.com/soneeee22000) | Gemma 4 integration, OCR, EU-14 table, evaluation |

## Provenance

`llm.py`, `ocr.py` and `config.py` were extracted from an earlier offline-document project by
[@soneeee22000](https://github.com/soneeee22000) and predate the hackathon. Everything else was
built during the event. Disclosed per competition rules §4.3.

## Licence

MIT — see [`LICENSE`](LICENSE).
