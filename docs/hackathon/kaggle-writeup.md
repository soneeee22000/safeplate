# SafePlate

## An allergen agent that refuses — because some ingredients _are_ the dish

**Track 2 — Autonomous Agents** · Gemma 4 Hackathon, Paris · 42 Paris

---

## The problem

A diner says, in a language the waiter doesn't speak: _"I'm allergic to nuts — is the vegan
gnocchi okay?"_

It is not. **Symphony.fr's "Gnocchis pesto vegan" contains pignons de pin — pine nuts.**
Vegan describes animal products, not allergens; a diner avoiding nuts reads _vegan_ and
relaxes. We did not invent that example. Symphony.fr catered this hackathon, and it is
printed on the label of the lunch we were served.

The waiter has thirty seconds, no allergen training, and a legal obligation not to guess.
The usual answers are all bad. Guess, and someone ends up in an ambulance. Refuse
everything, and you lose the table. Go find the chef, and you've abandoned four others.

And there is a subtler failure that allergen apps never model: **the answer here is no,
and not because of contamination.** Fish sauce is the salt and the entire seasoning base
of pad thai. Remove it and what reaches the table isn't pad thai, it's wet noodles. A
waiter who cheerfully says "no problem" is either lying or about to have the dish sent
back from the pass.

So the honest answer — _"no, that one can't be done, but let me suggest something else"_ —
is the useful one. Nothing we could find will say it.

## The solution

SafePlate takes the diner's spoken request in any language and runs it through a loop that
is **structurally incapable of saying "safe" when it isn't sure.** Three sources of truth,
strictly separated:

|                   | Owns                               | Why                                                                                |
| ----------------- | ---------------------------------- | ---------------------------------------------------------------------------------- |
| **Gemma 4 E2B**   | Hearing, understanding, explaining | Only a language model turns _"sans nuoc-mâm"_ into `{dish: pad thai, avoid: fish}` |
| **Lookup tables** | Every safety decision              | Auditable, diffable, cannot hallucinate                                            |
| **A human**       | Cross-contact                      | It is written on no label and never will be                                        |

**Gemma is the reasoning. It is never the last line of defence.**

## How Gemma 4 is used

Three distinct jobs, all load-bearing — remove any and the product stops working.

**1. It hears the diner.** Audio goes straight into Gemma. Ollama's native `/api/chat`
silently drops audio fields — it returns HTTP 200 and the model politely asks for audio it
never received — but the OpenAI-compatible endpoint's `input_audio` content parts do
deliver it. One call transcribes _and_ extracts intent, which matters: the model resolves
"without the fish sauce" against the dish it just heard named, something a
transcribe-then-parse pipeline has to rediscover.

**2. It decides what to call.** Native function calling drives the loop between the dish
table, the manufacturer lookup, and the kitchen.

**3. It speaks to the diner** in their own language, from facts it is handed — never from
facts it decides.

## Architecture

```
diner speaks (any language)
        │
        ▼
  understand_request   [GEMMA]   audio → {dish, avoid, request_type, language}
        │
        ▼
  assess_dish          [RULE]    structural | substitutable | removable
        │
        ├─ dish unknown ──────────── FORCED escalate → refuse, never infer a recipe
        ├─ packaged ingredient ───── FORCED lookup_product [SERPAPI]
        ├─ structural conflict ───── FORCED escalate → "no, and here is why"
        │
        ▼
  ask_kitchen          [HUMAN]   FORCED on every clearable case
        │
        ▼
  compose_reply        [GEMMA]   the verdict, in the diner's language
```

Every branch marked FORCED is compelled by the orchestrator. Which brings us to the
finding that shaped everything.

## The finding: a 5B model will not escalate on its own

We tested it rather than assuming. Handed a result containing an unresolved ingredient,
**E2B did not escalate.** It answered confidently about what it did know and stopped.

So escalation stopped being something we hope the model remembers and became control flow:

```python
if assessment.unknown_dish:   force("escalate")        # not "if the model decides to"
if packaged_ingredient:       force("lookup_product")
if assessment.blocking:       force("escalate")
if clearable:                 force("ask_kitchen")     # always. a clean table clears nothing alone
```

**The agent's reliability comes from the harness, not from hoping a small model plans
well.** Track 2 asks whether an agent survives contact with failure. A loop that
_guarantees_ escalation is a better answer than a model that usually remembers to.

## The challenge we did not expect

Late in the build, the smoke test caught this. Handed verdict `do_not_serve` and the
reason that fish sauce is structural to pad thai, Gemma wrote:

> _"We can offer you the Pad Thai without any added fish sauce instead."_

The model **contradicted the verdict it had just been given** — and it is the exact
sentence that puts an allergic diner in an ambulance. Strengthening the system prompt
didn't fix it. Restating the prohibition inside the facts block didn't fix it.

Then a second, subtler one: after a _cross-contact_ refusal, it offered _"We can omit the
crushed peanuts if you would like"_ — implying the refusal lifts.

So we did the same thing we do everywhere else: **put a deterministic check over the
model's output.** Any offer to make, serve or adjust the refused dish discards the
generated text in favour of text assembled from facts. That cost the diner their own
language, so the safe text is then _translated_ rather than regenerated — translation is
constrained, and cannot invent an offer the source doesn't contain.

**A language model is never the last line of defence — and that has to include what it
writes about its own verdict.** We'd stated that as a principle in the morning. By
afternoon the model had proved it twice.

## Measured, not assumed

|                                             |                                              |
| ------------------------------------------- | -------------------------------------------- |
| Structural refusal, end to end              | **54.1 s** · 5 steps · 2 by Gemma · 2 forced |
| Cleared via the kitchen                     | **47.1 s** · 6 steps · 2 by Gemma · 2 forced |
| `understand_request` (audio → intent)       | 21–32 s                                      |
| `compose_reply`                             | 26–29 s                                      |
| Every rule step (`assess_dish`, `escalate`) | **< 1 ms**                                   |

That last row is the point. **Every safety decision is sub-millisecond and deterministic.**
The seconds are all spent on understanding and speaking — the two things a language model
should be doing.

**Vision, re-tested and still rejected.** Once the OpenAI-compatible endpoint fixed audio,
we retried vision there too, on a real Symphony label. The image reached the model — it
described the picture — but it called a photographed ingredient panel _"a placeholder
graphic, not an actual food label"_ and read nothing. **Tesseract read the same photo in
0.4 s**, correctly transcribing `pignons de pin` and the full shared-facility line. So the
split is measured, not assumed: Gemma hears and speaks, Tesseract reads.

`think: false` is load-bearing — E2B otherwise emits chain-of-thought into a field nobody
reads, at roughly 3× the latency.

## Technical decisions

- **Dish structure is data, not generation.** A 5B model guessing at culinary structure is
  exactly the failure this project exists to prevent. Eight dishes, hand-encoded, each
  ingredient tagged with its role and — for structural ones — the reason a diner actually
  reads.
- **Poll, don't stream.** A run genuinely stops on `awaiting_human`. Polling represents
  that for free on both sides.
- **The interface was built against a frozen trace schema and hand-written fixtures**, so
  the loop and the UI were built in parallel and integrated without a rewrite.
- **SerpApi responses are cached to disk**, so the demo runs with the network off.

## What we would not claim

Eight dishes is a demonstration, not a menu. Cross-contact depends entirely on a human
answering honestly. No restaurant has used this. The refusal guardrail is conservative
pattern-matching over generated text — it will sometimes discard a perfectly good
sentence, which we consider the right direction to be wrong in.

## Links

- **Repo:** https://github.com/RitaTY/gemma4
- **Interactive demo:** https://safeplate-ten.vercel.app/verify

The agent itself runs locally — a 7.2 GB model behind Ollama cannot be hosted on a web
page. The deployed console runs live against the orchestrator when it is reachable and
replays a recorded case otherwise, and says on screen which mode it is in.
