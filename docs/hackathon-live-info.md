# Gemma 4 Hackathon | Paris — official rules digest

**Authoritative source:** https://www.kaggle.com/competitions/paris-gemma-4-hackathon
(private competition — not indexed in Kaggle search; the link is the access).
Event page: https://luma.com/uypemayx · Read 2026-07-25.

---

## 🔴 Do these now

1. **JOIN the competition.** Click _Join Hackathon_ and accept the rules. As of reading:
   **9 entrants, 0 teams, 0 submissions.** Nobody has submitted yet.
2. **Every teammate registers individually** on their own Kaggle account _before_ joining a
   Team (Foundational Rules §5b). Rita and Adrian each need to do this themselves.
3. **Check the countdown clock on the page.** It read **"7 HOURS TO GO"** when the
   competition had been open 39 minutes — so the Final Submission Deadline lands around
   **18:00–18:30 Paris**, well before the event's 21:30 end. Do not assume you have until
   21:30. Read the live countdown and work backwards from it.
4. **Add an OSI-approved open-source LICENSE to the repo** — required by §1.7. A missing or
   non-compliant licence is an eligibility problem, not a style nit.

---

## ⚠️ Two corrections to what I told you earlier

**1. Paris _does_ have a Kaggle competition.** I previously concluded it didn't and that
submission was probably in-room/Discord. Wrong. It is a **private** competition, which is why
`gemma paris in:competitions` returned zero results. Submission is on Kaggle.

**2. The official rubric contains no score caps.** The "Caps at 3 / Caps at 2" lines on the
room slide are **not in the Kaggle rulebook**. The written rubric is a flat 100 points with no
cap mechanism. Treat the slide's caps as judges' in-room guidance — real signal about what
they care about, but **not** a rule that hard-limits your score. Notably this means
**Track 2 does not automatically cap a linear pipeline at 2** under the official rules.

**3. Pre-existing code is explicitly ALLOWED.** §4.3: _"The use of AI coding assistants,
automated machine-learning tools, external APIs, and pre-existing open-source components is
permitted if their use and licences comply with these Rules."_ The only constraint is that you
must **not misrepresent pre-existing work as original work** — i.e. disclose it.

**This resolves BLOCKER 3 in `hackathon-readiness-audit.md`.** You do not have to abandon the
~1,000 lines written 21–24 July. You do have to say plainly in the Writeup what existed before
today and what was built today. Disclose it in the "engineering process" section and it is a
non-issue.

---

## The event

|                          |                                                                                  |
| ------------------------ | -------------------------------------------------------------------------------- |
| **Name**                 | Gemma 4 Hackathon \| Paris                                                       |
| **Host**                 | Paris Python & ML Group + 42AI, with Google, Alien Intelligence, SerpApi, NVIDIA |
| **Kaggle host account**  | `sonny_01`                                                                       |
| **Date / venue**         | 25 July 2026 · 42 Paris · one-day, in-person                                     |
| **Judges**               | `sonny_01`, Alba María Téllez Fernández                                          |
| **Max team size**        | **5**                                                                            |
| **Submissions per team** | **1** Writeup, **1** track                                                       |

Framing from the host: _not_ about polished production code — _"a sprint to experiment,
learn, break things, and build a convincing solution to a real-world problem."_

---

## Prizes — full structure

Pool: **$3,500 cash + $2,500 SerpApi credits + $2,500 Alien Intelligence credits + one NVIDIA GeForce RTX 5080.**

| Track                            | 1st place                              | 2nd place                        |
| -------------------------------- | -------------------------------------- | -------------------------------- |
| **Edge / On-Device**             | $750 cash                              | $250 cash                        |
| **Autonomous Agents**            | $750 cash + $1,000 SerpApi credits     | $250 cash + $500 SerpApi credits |
| **Context Engineering for SLMs** | **$1,000 cash + $1,000 Alien credits** | $500 cash + $500 Alien credits   |

**This resolves the prize discrepancy I flagged in `alien-kit.md`:** the slide's "$1,500 cash"
is the Track 3 *cash pool* ($1,000 + $500). Alien's "€2,000" is 1st place's combined value
($1,000 cash + $1,000 credits). Both were right; neither was the per-place figure.

**Track 3 pays the most cash of any track.**

### Cross-track extras

- **SerpApi bonus:** the two highest-ranked eligible projects using SerpApi **across all
  tracks** each get 10,000 credits (~$250). Requires a _substantive, working_ integration
  visible in the repo and demo. An Autonomous Agents SerpApi track winner can't also take one.
- **NVIDIA GPU Challenge:** open to **all three tracks**. Best Gemma 4 deployment on an
  NVIDIA-compatible stack — SGLang, vLLM, TensorRT-LLM, Dynamo, NIM, or similar. Judged on
  effectiveness, speed, reliability, technical quality, demonstration.
- **A team may win one track award, and may also win the NVIDIA prize.**
- Starter/discovery credits (SerpApi $500, Alien $1,000) are request-based, **not guaranteed
  prizes**.

---

## The three tracks — pick exactly one

**Track 1 — Edge / On-Device.** Mobile, web, desktop or edge app running Gemma **locally**.
Strong entries make thoughtful use of on-device inference for privacy, offline access, low
latency, efficiency, or accessibility.

**Track 2 — Autonomous Agents.** Uses Gemma's function-calling and reasoning to plan, use
tools, hit external APIs, complete meaningful tasks. _"Should do more than generate text: it
should take useful, observable actions."_

**Track 3 — Context Engineering for SLMs** _(supported by Alien Intelligence)_. A system that
improves how Gemma **selects, structures, compresses, retrieves, or updates** context.
Eligible: memory, RAG, prompt and context optimization, dynamic tool context, agent traces.

> **§1.5, the eligibility trap:** _"Gemma 4 must be central to the submitted solution. Merely
> mentioning Gemma, calling it in a non-essential part of the project, or using another model
> as the substantive core of the solution is insufficient."_

---

## Rubric — 100 points

| Criterion                                                                                               | Points   |
| ------------------------------------------------------------------------------------------------------- | -------- |
| **Gemma Integration** — is Gemma 4 core, and used effectively (prompting, RAG, tool use, fine-tuning…)? | **0–30** |
| **Innovation & Impact** — meaningful problem? creative and relevant approach?                           | **0–30** |
| **Functionality** — does the prototype work? is the demo convincing?                                    | **0–20** |
| **Presentation & Writeup** — do writeup, demo and pitch explain problem and solution clearly?           | **0–20** |

**Tie-break order:** Gemma Integration → Innovation & Impact → Functionality → Presentation,
then panel deliberation. Track awards use this same rubric, "taking the track definition into
account."

**Read the weighting:** 60 of 100 points are Gemma Integration + Innovation & Impact. A
beautiful demo of a shallow idea loses to a real idea with Gemma genuinely at its core.

---

## Required deliverables — all three, or ineligible

**1. Kaggle Writeup** (create at `/competitions/paris-gemma-4-hackathon/writeups`, then
**Submit** top-right). Must have: title + subtitle; selected track; problem and solution;
architecture and engineering process; **specifically how Gemma 4 is used**; challenges and
technical decisions. **≤1,500 words.**

**2. Public code repository** — no login/paywall, sufficiently documented to understand _and
run_, showing the actual Gemma 4 implementation, carrying the OSI licence.

**3. Working demo** — any of: hosted app, functional Kaggle Notebook, **interactive terminal
recording**, demo files, or a short demo video. No login/paywall.

> **Terminal recordings count.** You do not need a hosted deployment. `setup/demo_copilot.py`
> recorded cleanly satisfies this, which removes a whole category of deadline risk.

**Drafts are not judged.** One Writeup per team; unsubmit/edit/resubmit freely before the
deadline. Attaching a private Kaggle resource to a public Writeup makes it public after the
deadline.

### Auto-ineligible (§5.1)

Late or still a draft · missing a deliverable · empty/private/inaccessible/undocumented repo ·
no working demo · doesn't meaningfully use Gemma 4 · over the word limit · licence or rule
violation · unverifiable by judges.

### §9 — secrets

_"Participants must not include confidential information, personal data they are not entitled
to publish, secrets, credentials, or private API keys in any Submission."_ The `.pkpass` in
this folder holds a live Luma auth token and a personal email — it is gitignored; keep it that
way.

---

## Strategic read for this team

**Track 3 is still the pick.** Highest cash ($1,000 vs $750), plus $1,000 Alien credits, and
the official definition — _"selects, structures, compresses, retrieves, or **updates**
context"_ — describes the as-of versioned retrieval engine almost word for word. A superseded
rule never occupying a context slot is textbook context engineering.

**The time math changed.** The deadline is ~18:00, not 21:30, and the Writeup, repo cleanup,
licence and demo recording all come out of that. Realistically **~4 hours of building**.
Functionality is 20 points and it is where half-finished pivots die.

**On the crisis first-aid idea:** it scores better on Innovation & Impact (30 pts) than French
paperwork does, and the existing engine transfers — retrieval over a provenance-carrying
corpus, cite-or-refuse grounding, and a numeric guardrail that checks a **dosage** instead of a
fee. The verified Arabic / Ukrainian / Burmese support becomes central rather than incidental.
It is a corpus swap, not a rewrite. But with ~4 hours and a team that hasn't agreed yet, that
is a real bet — and now that pre-existing code is explicitly allowed, the safe option is
genuinely safe.

Either way: **decide within the next 30 minutes.** The cost here is not the build, it's the
hour spent choosing.

**If you want the extra shot:** a substantive SerpApi integration makes you eligible for a
cross-track $250 credit award regardless of the track you pick. For a first-aid or legal
corpus, a live freshness check against current guidance is a natural, non-decorative fit.
