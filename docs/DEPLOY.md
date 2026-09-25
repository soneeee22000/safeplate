# Deploying SafePlate

Two pieces, two hosts:

| Piece                                | Host                             | What runs                                                                   |
| ------------------------------------ | -------------------------------- | --------------------------------------------------------------------------- |
| Orchestrator (FastAPI, `safeplate/`) | Render, free web service, Docker | **Rules mode**: no Gemma. Typed text only, keyword intake, fixed sentences. |
| Interface (Next.js, `web/`)          | Vercel                           | Calls the orchestrator via `NEXT_PUBLIC_ORCHESTRATOR_URL`.                  |

The hosted agent does not run Gemma. Gemma 4 E2B is a 7.2 GB model and runs on a
laptop through Ollama; a free container cannot hold it. The safety decisions (dish
table, EU-14 allergens, forced SerpApi lookup, forced kitchen question, refusal)
are the same code in both modes. Only the hearing and the speaking change. The
interface must say so wherever the live agent is used, for example
"Live · rules mode — Gemma runs locally (see recorded runs)".

## 1. Orchestrator on Render

The repo root carries a `Dockerfile` and a `render.yaml` blueprint.

1. Render dashboard > **New** > **Blueprint**.
2. Connect GitHub and pick **soneeee22000/safeplate**, branch `main`.
3. Render reads `render.yaml` and proposes one web service,
   `safeplate-orchestrator` (Docker, free plan, Frankfurt, health check `/health`).
4. It asks for **`SERPAPI_KEY`** (declared `sync: false`). It is optional:
   leave it empty and the service still works, cache-first.
5. **Apply**. The first build takes a few minutes. When it is live, open
   `https://<service>.onrender.com/health`. Expected:

   ```json
   { "ok": true, "mode": "rules", "dishes": 8, "open_runs": 0 }
   ```

   `"mode": "rules"` is the check that matters. The service refuses to start on
   an unknown `SAFEPLATE_MODE`, so a typo fails loudly.

### Environment

| Variable                 | Value                                                    | Notes                                                                                                           |
| ------------------------ | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `SAFEPLATE_MODE`         | `rules`                                                  | Also baked into the image.                                                                                      |
| `SAFEPLATE_CORS_ORIGINS` | `https://safeplate-ten.vercel.app,http://localhost:3000` | Comma-separated. `*` is refused. Add a Vercel preview origin here if you want previews to reach the live agent. |
| `SERPAPI_KEY`            | optional                                                 | Without it, lookups are answered from `fixtures/serp/`, which ships in the image.                               |
| `SERPAPI_KEY_FALLBACK`   | optional                                                 | Used only when the first key is rejected or out of quota.                                                       |
| `PORT`                   | set by Render                                            | The container listens on `$PORT` (8000 when unset).                                                             |

### SerpApi without a key

`serp.py` resolves its cache as `<project root>/fixtures/serp`, where the project
root is the parent of the `safeplate` package. In the image that is
`/app/fixtures/serp`, copied in at build time. A cached query never touches the
network or needs a key; this is how the fish-sauce lookup behind the demo cases
runs. An uncached query with no key raises `SerpUnavailable`, and the loop treats
that as "unconfirmed", never as safe. With a key set, new non-empty results are
written to the cache (the service user owns that directory), but Render's disk is
ephemeral, so those additions are lost on the next deploy or restart. Commit new
cache files to the repo if they should persist.

### Free-tier cold start

A free Render service spins down after **15 minutes without traffic**. The next
request wakes it, which takes **about 50 seconds**. Render holds that request
open while the container boots; it does not fail fast. Open cases are held in
memory, so a spin-down also drops any case that was mid-flight.

How the interface should handle it:

- Probe `GET /health` on page load, which starts the wake-up before the visitor
  types anything.
- While the probe is outstanding, show that the live agent is waking (free tier,
  up to a minute) and let the visitor use the recorded Gemma runs in the
  meantime, badged "Recorded run · Gemma 4 E2B".
- When the probe returns `{"ok": true, "mode": "rules"}`, switch the live
  console on and label it as rules mode.
- If the probe fails or times out, stay on the recorded runs and say the live
  agent is unavailable. Never present a recorded run as live.

At the time of writing, `web/src/lib/orchestrator.ts` (`probeOrchestrator`) runs
one probe with no timeout and `web/src/components/live-console.tsx` falls back to
a recorded replay until it resolves. The wake-up message above is the target
behaviour for the interface work.

To keep it warm for a scheduled demo, open `/health` a minute beforehand.

### API shapes (for the interface)

All JSON. The case runs in the background; the interface polls.

**Open a case** — `POST /api/case`, multipart form, field `text`:

```bash
curl -X POST https://<service>.onrender.com/api/case \
  -F "text=I have a peanut allergy, can I eat the pad thai?"
# {"run_id": "SP-84DA4279"}
```

Sending `audio` instead of `text` returns 400 in rules mode (audio needs Gemma).
Neither field returns 400. When every held case is still waiting on a kitchen,
a new case returns 503.

**Poll** — `GET /api/case/{run_id}`:

```json
{
  "run_id": "SP-84DA4279",
  "status": "awaiting_human",
  "pending_question": "Pad thai: Prepare it with these changes: omit crushed peanuts. Is there ANY way peanuts could reach this plate — shared oil, fryer, board, utensils, or a pre-made component? Note: wok and fryer shared across the whole Thai section.",
  "trace": {
    "case_id": "SP-84DA4279",
    "restaurant": "SafePlate demo service",
    "dish": "Pad thai",
    "allergen": "peanuts",
    "diner_language": "en",
    "verdict": "needs_confirmation",
    "total_ms": 2356,
    "steps": [
      {
        "n": 1,
        "tool": "understand_request",
        "engine": "rule",
        "title": "...",
        "reasoning": "...",
        "forced": false,
        "args": {},
        "result": {},
        "duration_ms": 2,
        "note": "Rules mode — keyword matching, no model."
      },
      {
        "n": 2,
        "tool": "assess_dish",
        "engine": "rule",
        "forced": false,
        "...": "..."
      },
      {
        "n": 3,
        "tool": "ask_kitchen",
        "engine": "human",
        "forced": true,
        "forced_by": "cross_contact unknown for the requested allergen",
        "...": "..."
      }
    ],
    "evidence": [],
    "explanation": "",
    "explanation_en": ""
  }
}
```

`status` is `running`, `awaiting_human`, `complete` or `failed` (with `error`).
`pending_question` is present only while `awaiting_human`. `verdict` stays
`needs_confirmation` until something decides otherwise. When the loop forces a
SerpApi lookup (for example fish sauce), a `lookup_product` step with
`engine: "external"` appears and `evidence` holds the statements, each with
`source`, `url`, `text` and `trusted`. Unknown run ids return 404.

**Answer the kitchen** — `POST /api/case/{run_id}/answer`, JSON:

```bash
curl -X POST https://<service>.onrender.com/api/case/SP-84DA4279/answer \
  -H "Content-Type: application/json" -d '{"risk": "unsure"}'
```

`risk` is `none` (No risk), `risk` (Risk) or `unsure` (Unsure), with an optional
`note`. Free text in `answer` is still accepted and read fail-closed. The response
is the same shape as a poll, now `status: "complete"`:

```json
{
  "run_id": "SP-84DA4279",
  "status": "complete",
  "trace": {
    "verdict": "needs_confirmation",
    "steps": [
      "... ask_kitchen now has result {answered_by: chef, answer: unsure, risk: unsure}",
      "interpret_answer (rule)",
      "compose_reply (rule)"
    ],
    "explanation": "We cannot confirm this yet. The kitchen said: unsure",
    "explanation_en": "We cannot confirm this yet. The kitchen said: unsure"
  }
}
```

A second answer to the same case returns 409 and leaves the verdict as it is.
Any `risk` other than the three values returns 400.

**Other routes**: `GET /health`, `GET /api/dishes` (the eight demo dishes, as
`{"dishes": [{"key", "name", "cuisine"}]}`).

## 2. Interface on Vercel

1. Vercel project for `web/` > Settings > Environment Variables:
   `NEXT_PUBLIC_ORCHESTRATOR_URL=https://<service>.onrender.com` (no trailing
   slash), for Production.
2. `NEXT_PUBLIC_*` values are inlined at build time, so redeploy after setting it:

   ```bash
   cd web && npx vercel --prod
   ```

3. Check the site's origin is listed in `SAFEPLATE_CORS_ORIGINS` on Render. A
   missing origin shows up as a CORS error in the browser console, not as an
   HTTP error. The page cannot tell a CORS rejection from a sleeping host, so
   an unlisted origin (a Vercel preview such as `safeplate-git-*.vercel.app`,
   for example) shows "Waking the live agent" for the whole wake budget
   (`WAKE_BUDGET_MS` in `web/src/lib/orchestrator.ts`, 65 s) before it falls
   back to recorded runs. Add each preview origin you want to test live.

## Running the same image locally

```bash
docker build -t safeplate-api .
docker run --rm -p 8000:8000 safeplate-api
curl localhost:8000/health
```

Or without Docker:

```bash
SAFEPLATE_MODE=rules .venv/Scripts/python -m uvicorn safeplate.api:app --port 8000
```

For the full agent with Gemma 4 E2B hearing and speaking, run Ollama locally
with `gemma4:e2b` and leave `SAFEPLATE_MODE` at its default, `gemma`.
