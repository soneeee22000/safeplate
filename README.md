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
allergens, looks up the manufacturer's declaration when the label doesn't resolve, **asks the
kitchen the one thing no label can tell it**, and answers in the diner's language — or refuses,
and says exactly why. Its most valuable output is often `DO NOT SERVE — I can't confirm`.

Built for the **Gemma 4 Hackathon | Paris**, Track 2 (Autonomous Agents), 42 Paris.

### Try it

|                      |                                                                                                                |
| -------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Operator console** | **<https://safeplate-ten.vercel.app/verify>** — open a case, watch the agent work, answer the kitchen yourself |
| **Project page**     | <https://safeplate-ten.vercel.app>                                                                             |

> These pages **replay a recorded run**. They are genuinely interactive — the trace prints step
> by step and the kitchen question waits for an answer you type — but Gemma is not executing
> behind them. The model is 7.2 GB behind Ollama with a local Tesseract binary, so the agent
> itself runs on a laptop, not on a web host. The interface says which mode it is in.

---

## The design decision

**Gemma 4 hears, understands and speaks. Deterministic tables decide whether anyone can eat
the food.**

| Gemma 4 E2B owns                                | The tables own                                     |
| ----------------------------------------------- | -------------------------------------------------- |
| Hearing the diner — audio in, any language      | **Whether an ingredient is a declarable allergen** |
| Turning that into `{dish, avoid, request_type}` | Whether it can be removed from the dish            |
| Choosing which tool to call next                | `casein → milk`, `pignons de pin → nuts`           |
| Saying the answer in the diner's own language   | Whether the verdict may ever be "safe"             |

A language model is never the last line of defence. The reasoning is learned; the safety call
is deterministic and auditable.

---

## One run, turn by turn

This is a real trace, replayed from `fixtures/`. Nothing below is illustrative.

> **Diner** — spoken, in French
> _« Je suis allergique au poisson. Vous pouvez faire le pad thaï sans nuoc-mâm ? »_

**Turn 1 · `understand_request` · GEMMA · 29.2 s**

Audio goes straight into Gemma. One call transcribes _and_ extracts intent, so "without the
nuoc-mâm" resolves against the dish it just heard named:

```json
{
  "language": "fr",
  "dish": "pad thai",
  "avoid": ["fish", "nuoc-mam"],
  "request_type": "modification"
}
```

**Turn 2 · `assess_dish` · RULE · <1 ms**

The model is not asked whether this is safe. A table is:

```json
{
  "outcome": "cannot_modify",
  "blocking": [{ "ingredient": "fish sauce", "role": "structural" }]
}
```

**Turn 3 · `lookup_product` · SERPAPI · FORCED**

Fish sauce arrives in a jar, so what is in it is the manufacturer's declaration, not our
table. The orchestrator compels this call — the model would skip it.

**Turn 4 · `escalate` · RULE · FORCED**

`forced_by: structural ingredient cannot be removed`. There is no path from here to "safe".

**Turn 5 · `compose_reply` · GEMMA · 57.4 s**

The verdict was fixed before this ran. Gemma's only job is to say it clearly, in French:

> _« Nous ne pouvons pas servir ceci comme demandé. La sauce de poisson est le sel et l'épine
> dorsale du pad thaï… Nous pouvons suggérer autre chose du menu. »_

**Five turns. Two by Gemma, two forced by the loop, one sub-millisecond table lookup that made
the actual decision.**

---

## The turn that is not a turn

Some questions have no document that answers them. Cross-contact is one:

> **Agent → kitchen**
> _"Falafel plate: can you do it as — serve with harissa instead? And is there cross-contact
> with sesame? Note: deep fryer shared with breaded and peanut-crusted items."_
>
> **Chef** — typed on the same screen
> _"Yes — dedicated pan, no sesame at that station, clean utensils."_
>
> **Agent → diner**
> _"The falafel plate can be prepared without sesame. The kitchen uses a dedicated pan…"_

The run **blocks** here. `status: awaiting_human`, and nothing is cleared until a person
answers. Every question is phrased so **"yes" means risk** — two questions with opposite
polarity cannot share one reading of the answer, and getting that backwards clears a dish
that should be refused.

Risk beats clearance whenever both appear. _"No shellfish in it but we share the oil"_ is a
refusal.

## Architecture

```mermaid
flowchart TD
    PHOTO["Label photo"] --> OCR["read_label<br/>Tesseract, 0.9s"]
    OCR -->|confidence below 0.75| RESHOOT["FORCED: ask for<br/>a second photo"]
    RESHOOT --> OCR
    OCR -->|text| GEMMA["structure_ingredients<br/>Gemma 4 E2B"]
    GEMMA --> MATCH["match_allergens<br/>EU-14 table, deterministic"]
    MATCH -->|unresolved token| LOOKUP["FORCED: lookup_product<br/>SerpApi"]
    MATCH -->|all resolved| ASK
    LOOKUP -->|sources conflict| STOP
    LOOKUP -->|declaration found| ASK["FORCED: ask_kitchen<br/>cross-contact, a human answers"]
    ASK -->|shared equipment| STOP["escalate<br/>DO NOT SERVE"]
    ASK -->|ruled out| CARD["verdict + evidence trace<br/>in the diner's language"]

    style STOP fill:#f6e2e0,stroke:#a02f28,color:#111
    style CARD fill:#e0efe6,stroke:#176b45,color:#111
    style MATCH fill:#eef1f5,stroke:#2a4c99,color:#111
    style ASK fill:#e8e9f7,stroke:#1f3a93,color:#111
```

Everything except `lookup_product` runs on-device. Every branch marked **FORCED** is compelled
by the orchestrator, not chosen by the model — see
[Escalation is enforced by the loop](#escalation-is-enforced-by-the-loop-not-by-the-model).

**`ask_kitchen` is the step that makes this more than a label reader.** A clean label never
clears a dish on its own, because cross-contact is not written on any label and never will be.

## System layers

Where each part runs, and what crosses a network boundary.

```mermaid
flowchart TB
    subgraph Diner["Diner's screen — table or kiosk"]
        ORDER["/order<br/>speak or type · 4 scripts"]
    end

    subgraph Staff["Staff device"]
        VERIFY["/verify<br/>trace + kitchen prompt"]
    end

    subgraph Service["FastAPI orchestrator — local"]
        LOOP["Agent loop<br/>forced escalation<br/>never returns 'safe' unearned"]
        GUARD["Refusal guardrail<br/>checks the model's own prose"]
    end

    subgraph Device["On-device — nothing leaves the machine"]
        GEMMA["Gemma 4 E2B via Ollama<br/>/v1 chat · input_audio · temp 0"]
        OCR["Tesseract<br/>eng + fra · 0.4s"]
        MENU["Symphony labels<br/>+ EU-14 table + synonyms<br/>DATA, not a prompt"]
    end

    subgraph Human["Not a system"]
        CHEF["The kitchen"]
    end

    subgraph Ext["External"]
        SERP["SerpApi<br/>manufacturer declarations<br/>cached to disk"]
    end

    ORDER -->|audio or text| LOOP
    VERIFY -->|audio or text| LOOP
    LOOP --> GEMMA
    LOOP --> OCR
    LOOP --> MENU
    LOOP -->|FORCED| SERP
    LOOP -->|FORCED · run blocks| CHEF
    CHEF -->|answer| LOOP
    LOOP --> GUARD
    GUARD -->|verdict + evidence + trace| ORDER
    GUARD -->|verdict + evidence + trace| VERIFY

    GEMMA -.->|hears · plans · speaks| LOOP
    MENU -.->|decides| LOOP

    style MENU fill:#eef1f5,stroke:#2a4c99,color:#111
    style CHEF fill:#e8e9f7,stroke:#1f3a93,color:#111
    style GUARD fill:#f6e2e0,stroke:#a02f28,color:#111
```

**Only `lookup_product` crosses the internet.** The model, the OCR and every safety decision
stay on the machine — no diner's health information is sent anywhere.

## A run, as a sequence

The vegan gnocchi case, exactly as the loop executes it.

```mermaid
sequenceDiagram
    actor D as Diner
    participant L as Orchestrator
    participant G as Gemma 4 E2B
    participant M as Symphony labels
    participant W as SerpApi
    actor K as Kitchen

    D->>L: audio — "I have a tree nut allergy.<br/>Is the gnocchis pesto vegan safe?"
    L->>G: understand_request(audio)
    G-->>L: {dish, avoid:[tree nuts], language} — 25s

    alt avoid is empty
        Note over L: FORCED — a dish cannot be<br/>checked against nothing
        L-->>D: needs_confirmation, ask again
    end

    L->>M: report(dish, avoid)
    M-->>L: label_conflict — pignons de pin<br/>declared:false (not in bold)

    alt packaged ingredient
        Note over L: FORCED by the loop,<br/>not chosen by the model
        L->>W: lookup_product(product)
        W-->>L: statements[] or unavailable
    end

    alt nothing on the label, workshop line silent
        Note over L: FORCED — run BLOCKS here
        L->>K: is there ANY way X reaches this plate?
        K-->>L: free text — risk beats clearance
    end

    L->>G: compose_reply(verdict, language)
    G-->>L: prose

    alt prose offers the refused dish
        Note over L: guardrail discards it,<br/>assembles from facts, translates
    end

    L-->>D: DO NOT SERVE + the reason,<br/>in the diner's language
```

**Every `FORCED` note is this file's control flow, not the model's judgement.** That is the
whole architecture in one word, repeated four times.

## Verdict states

There are three, and one of them is unreachable for most questions at Symphony.

```mermaid
stateDiagram-v2
    [*] --> Understanding
    Understanding --> NeedsConfirmation: no dish named
    Understanding --> NeedsConfirmation: no allergen understood
    Understanding --> Checking: dish + allergen known

    Checking --> DoNotServe: on the label
    Checking --> NeedsConfirmation: workshop declares it
    Checking --> AwaitingHuman: label silent

    AwaitingHuman --> DoNotServe: risk confirmed
    AwaitingHuman --> NeedsConfirmation: answer unclear
    AwaitingHuman --> Verified: risk ruled out by a person

    DoNotServe --> [*]
    NeedsConfirmation --> [*]
    Verified --> [*]

    note right of Verified
        Only reachable when a human
        ruled the risk out. No label,
        and no model, can reach it alone.
    end note
```

Every Symphony label carries the same workshop declaration — gluten, celery, mustard,
peanuts, fish, eggs, soya, milk, tree nuts, sesame. **For any of those ten, `Verified` is
unreachable by construction.** That is not a limitation to design around; it is the
manufacturer declining to guarantee, and the agent declining to guarantee on their behalf.

## Who it's for

```mermaid
flowchart LR
    S(["SERVER<br/>the only operator"])
    K(["CHEF<br/>answers one question"])
    D(["DINER<br/>receives, never operates"])

    U1["Open a case:<br/>allergen + language"]
    U2["Photograph the label"]
    U3["Answer the agent's<br/>cross-contact question"]
    U4["Receive the verdict<br/>in their own language"]

    S --> U1
    S --> U2
    K --> U3
    U4 --> D

    U2 -. triggers .-> U3
    U3 -. resolves .-> U4
```

**One device, one screen, three people served.** The server holds the phone. The chef answers on
that same screen — there is no second app. The diner never touches it.

A server holding a jar has no allergen training, no time, and often no shared language with the
person asking. Today the options are guess, refuse everything, or go find a chef. All three are
bad — and the first is the one that sends people to hospital.

SafePlate's job is not to be clever. It is to turn thirty seconds of guessing into a sourced
answer, or an honest refusal that a manager can stand behind.

## Why this matters commercially

|                   |                                                                                                                                                             |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Who pays**      | Restaurant groups and hospitality franchises — the buyer is whoever signs off on food-safety compliance, not the kitchen                                    |
| **Budget line**   | Food-safety training and compliance tooling, an existing line item                                                                                          |
| **The wedge**     | Allergen declaration is legally mandated in the EU under Regulation (EU) No 1169/2011 — the 14 allergens are not optional, so the obligation already exists |
| **Why on-device** | No per-query cost, no network dependency in a kitchen, no customer health data sent anywhere                                                                |
| **Defensibility** | The moat is the verified allergen taxonomy and the refusal policy, not the model — anyone can call an LLM, few will build the part that says _no_           |

**Stated honestly:** this is a hackathon prototype, not a validated product. Market size,
willingness to pay, and per-restaurant liability exposure are **assumptions we have not
tested** — no operator has been interviewed. The strongest evidence we have is that the legal
obligation is real and the current alternative is a server guessing.

## Escalation is enforced by the loop, not by the model

We measured this rather than assuming it. Given ingredients including `casein` and the
unresolved token `natural flavourings`, Gemma 4 E2B correctly called `match_allergens` — but
handed back `"unresolved": ["natural flavourings"]`, **it did not escalate.** It answered about
the casein and stopped.

So escalation is control flow, not a hope:

```python
if assessment.unknown_dish:   force("escalate")        # not "if the model decides to"
if not intent.avoid:          force("escalate")        # nothing to check is not a pass
if packaged_ingredient:       force("lookup_product")
if assessment.blocking:       force("escalate")
if clearable:                 force("ask_kitchen")     # always. a clean label clears nothing alone
```

### Three times the model tried to say yes

Each of these was measured during the build, not imagined afterwards.

**1. It offered the dish it had just refused.** Handed `do_not_serve` and the reason that fish
sauce is structural to pad thai, Gemma wrote:

> _"We can offer you the Pad Thai without any added fish sauce instead."_

That is the sentence that puts an allergic diner in an ambulance. Strengthening the system
prompt did not fix it. Restating the prohibition inside the facts block did not fix it.

**2. It implied a refusal had lifted.** After a _cross-contact_ refusal it wrote _"We can omit
the crushed peanuts if you would like"_ — subtler, and just as dangerous.

So the model's own prose gets a deterministic check. Any offer to make, serve or adjust the
refused dish discards the generated text for text assembled from facts — which is then
_translated_ rather than regenerated, because translation cannot invent an offer the source
does not contain.

**3. It checked a dish against nothing.** Given _"I have a tree nut allergy"_, it once returned
an empty `avoid` list, and the run carried on to the kitchen question with no allergen to ask
about. A case with nothing to check now stops rather than looking as though it was checked.

**A language model is never the last line of defence — and that has to include what it writes
about its own verdict.**

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
- **The agent asks a human** — cross-contact is evidence no document contains, so it stops and asks the kitchen
- **Refusal as a first-class outcome** — conflicting sources produce `DO NOT SERVE`, never an average
- **Multilingual output** — verdict rendered in the diner's language
- **Visible agent trace** — every tool call, result and decision shown, not summarised, with each
  step labelled by what produced it: Gemma, a deterministic rule, SerpApi, or a human

## Tech stack

| Layer             | Choice                               | Why                                                 |
| ----------------- | ------------------------------------ | --------------------------------------------------- |
| Model             | Gemma 4 **E2B** via Ollama           | Runs offline on a laptop; native function calling   |
| Model call        | Ollama HTTP `/api/chat` with `tools` | `think:false`, `temperature:0`                      |
| OCR               | Tesseract (`eng+fra`)                | E2B vision fails on dense print; Tesseract is 0.9 s |
| Orchestrator      | FastAPI                              | Owns control flow and forced escalation             |
| Allergen logic    | Plain Python table                   | Deterministic and auditable by design               |
| External evidence | SerpApi (`engine=google`)            | Manufacturer declarations the label omits           |
| Interface         | Next.js 16 · TypeScript · Tailwind 4 | Operator console + agent trace, deployed on Vercel  |

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
fixtures/           recorded runs — one refusal, one clearance. THE FROZEN CONTRACT.
web/                Next.js operator console and landing page
  src/lib/trace.ts        the same schema, typed
  src/lib/orchestrator.ts the FastAPI client + demo replay
docs/
  safeplate-mvp-decision.md  scope, persona, rubric mapping — read this first
  safeplate-spec.md          tool contracts, gate results, sequence diagram
tessdata/           Tesseract language data (eng, fra)
```

**`fixtures/trace-refusal.json` is the contract everything agrees on.** The Python loop emits
that shape and the interface renders it, so both sides were built in parallel without waiting
on each other. Start there.

Full technical spec, including the frozen tool contracts and the EU-14 allergen set:
**[`docs/safeplate-spec.md`](docs/safeplate-spec.md)**

### Running the interface

```bash
cd web
npm install
npm run dev          # http://localhost:3000/verify
```

It talks to the orchestrator at `http://127.0.0.1:8000` when that is up, and replays a recorded
case when it is not — labelled in the interface so the two are never confused. Point it
elsewhere with `NEXT_PUBLIC_ORCHESTRATOR_URL`.

The orchestrator contract the interface expects:

```
POST /api/case                  -> { run_id }
GET  /api/case/{run_id}         -> { status, pending_question?, trace }
POST /api/case/{run_id}/answer  -> { status, trace }
GET  /health
```

`status` is one of `running`, `awaiting_human`, `complete`, `failed`. A run genuinely stops on
`awaiting_human` until the kitchen answers.

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
