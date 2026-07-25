# LinkedIn — SafePlate

Copy one of these. **You post it; I don't.** All variants are written to be defensible if
someone clones the repo — it is described as a hackathon prototype, never as a product.

Repo: `https://github.com/RitaTY/gemma4`

---

## Variant A — the technical finding (recommended)

> Best hook. It's specific, it's a real measurement, and it's the kind of detail that makes
> engineers stop scrolling. Leads with what we learned, not with what we built.

We spent Saturday at the Gemma 4 hackathon at 42 Paris building an allergen agent, and the
most useful thing we found was a failure.

Gemma 4 E2B — a 2-billion-parameter model running entirely on a laptop — handles function
calling well. We gave it a jar's ingredient list and it correctly called our allergen matcher,
extracting every ingredient verbatim.

Then we handed the result back with one unresolved token: "natural flavourings."

It didn't escalate. It answered about the casein it *had* resolved, and stopped.

That one behaviour reshaped the architecture. We stopped asking the model to decide when to
seek more evidence and made it control flow:

    if result.unresolved:
        force_tool("lookup_product")
    if sources_conflict(evidence):
        force_tool("escalate")

The agent's reliability now comes from the harness, not from a small model remembering to plan
well. A loop that *guarantees* escalation beats a model that usually remembers.

Two other things we measured rather than assumed:

— Gemma 4 E2B's vision could not read a printed ingredient panel. It echoed the prompt and
emitted a digit sequence. Tesseract did the same image in 0.9 seconds.

— Passing `think: false` cut latency roughly 3x. The model emits a chain-of-thought into a
separate field you never see but still wait for.

The design that fell out: Gemma plans, reads and translates. A deterministic lookup table
decides whether an ingredient is a declarable allergen. A language model is never the last
line of defence — and the most valuable thing SafePlate outputs is often "I can't confirm this,
don't serve it."

Hackathon prototype, not a product. Code and the full spec are open:
github.com/RitaTY/gemma4

Built with Rita, Afaq and Yan.

#Gemma #LocalLLM #AIAgents #OnDeviceAI

---

## Variant B — short

> For when you want it read in one screen.

At the Gemma 4 hackathon at 42 Paris this weekend, building an allergen agent for restaurant
staff.

The finding that shaped everything: given an unresolved ingredient, a 2B model *didn't*
escalate to look it up. It answered what it could and stopped.

So escalation became control flow instead of a prompt. Reliability comes from the harness, not
from hoping a small model plans well.

Also measured: Gemma 4 E2B's vision couldn't read a printed ingredient panel — Tesseract did it
in 0.9s. And `think: false` cut latency about 3x.

The split we landed on: Gemma plans, reads and translates; a deterministic table decides
whether something is a declarable allergen. The model is never the last line of defence.

Prototype, not a product — but the refusal path is the part I'd keep.

github.com/RitaTY/gemma4

#Gemma #AIAgents #OnDeviceAI

---

## Variant C — product angle

> Leads with the human problem. Use this one if your audience is less technical.

A customer asks your server whether the dish contains nuts. They don't share a language. The
jar is labelled in a third one. Your server has thirty seconds, no allergen training, and a
legal obligation not to guess.

That's the problem we picked at the Gemma 4 hackathon at 42 Paris this weekend.

SafePlate photographs the label, reads it on-device, maps ingredients against the 14 allergens
the EU requires to be declared, and looks up the manufacturer's declaration when the label
doesn't resolve. It answers in the customer's language, with sources.

And when the sources disagree, it refuses. "Do not serve — I can't confirm" is a correct
answer, and it's the one most systems are too eager to skip.

Everything except the product lookup runs on a laptop with no network. No customer health
question leaves the building.

The engineering choice I'd defend hardest: Gemma 4 plans, reads and translates — but a plain
deterministic table decides whether an ingredient is an allergen. A language model should never
be the last line of defence on a question where being wrong sends someone to hospital.

Hackathon prototype with a team of four — Rita, Afaq, Yan and me. Open source:
github.com/RitaTY/gemma4

#AI #FoodSafety #Gemma #OnDeviceAI

---

## Notes before posting

- **Don't call it a product, a launch, or "shipping."** It's a one-day prototype. Every variant
  above already says so — keep that.
- **Don't add metrics that don't exist.** No accuracy figures, no user counts, no market size.
  The only numbers here (0.9s OCR, ~3x latency, 24.0s/7.3s) were measured today.
- **Tag your teammates** rather than naming them in plain text — Rita, Afaq and Yan should get
  the notification.
- If the repo is private at posting time, either make it public first or drop the link.
