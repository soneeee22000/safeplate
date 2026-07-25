# Comment to post on the Kaggle writeup

Paste as a public comment on
`https://www.kaggle.com/competitions/paris-gemma-4-hackathon/writeups/safeplate-agent`

Do **not** paste this into the writeup body. It is an addendum, posted after the
deadline, and it should be visibly that.

---

## Version A — short (recommended)

> Adding three measured details that did not make the writeup.
>
> **Gemma 4 E2B ingests the audio natively.** The diner speaks, and one call
> transcribes and extracts intent together — so "without the fish sauce" resolves
> against the dish it just heard named. Ollama's `/api/chat` silently drops audio
> fields (HTTP 200, and the model asks for audio it never received); the
> OpenAI-compatible `/v1/chat/completions` with `input_audio` parts does deliver
> it. That endpoint difference cost us an hour and is not documented anywhere we
> could find.
>
> **The guardrails exist because we watched the model fail, twice.** Handed
> `do_not_serve` and the reason that fish sauce is structural to pad thai, E2B
> wrote: _"We can offer you the Pad Thai without any added fish sauce instead."_
> After a cross-contact refusal it wrote _"We can omit the crushed peanuts if you
> would like"_ — subtler, and just as dangerous. Prompt fixes did not hold. A
> deterministic check now discards any generated text that offers what the loop
> refused, and the safe replacement is translated rather than regenerated,
> because translation cannot invent an offer the source does not contain.
>
> **The timing split is the architecture.** A full run is 47–54 s end to end,
> almost all of it Gemma hearing and speaking. Every deterministic safety
> decision in that run — allergen matching, escalation, verdict — is under a
> millisecond. 38 tests cover the Symphony menu, including that "vegan" does not
> imply nut-free.

---

## Version B — one paragraph, if the short one still feels long

> One detail that did not make the writeup: the guardrails exist because we
> watched the model fail. Handed `do_not_serve` and the reason that fish sauce is
> structural to pad thai, Gemma wrote _"We can offer you the Pad Thai without any
> added fish sauce instead."_ Prompt fixes did not hold, so a deterministic check
> now discards any generated text that offers what the loop refused. A full run
> is ~50 s, almost all of it the model hearing and speaking; every safety
> decision inside it is sub-millisecond.

---

## Before you post

Check the demo video link resolves in a **private/incognito window**. A demo
behind a login or set to Private is an eligibility condition, not a style nit —
_"the demo must be accessible without a login or paywall."_ If it is broken, fix
that link in the writeup itself; making a delivered artifact reachable is
correcting an error, not improving the entry.
