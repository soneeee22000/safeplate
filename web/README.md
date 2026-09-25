# SafePlate web

The front end for SafePlate, a hackathon project: an allergen agent on Gemma 4 E2B where the model only hears and speaks and deterministic code decides.

Next.js 16, React 19, Tailwind 4.

## Routes

| Route     | What it is                                                              |
| --------- | ----------------------------------------------------------------------- |
| `/`       | Landing page                                                            |
| `/verify` | The server's screen. Runs the live agent, or replays recorded runs      |
| `/order`  | Diner-facing experiment. Mostly replays recordings; not in the main nav |

## Live vs replay

- **Live:** the page talks to the FastAPI orchestrator (`safeplate/api.py`) at `NEXT_PUBLIC_ORCHESTRATOR_URL`. The hosted orchestrator runs in **rules mode**, with no Gemma, because Gemma 4 E2B is 7.2 GB and runs on a laptop. The UI says so wherever the live agent answers.
- **Replay:** when no orchestrator is reachable, `/verify` replays real recorded runs from `src/data/*.json`. Each one is badged with the engine that recorded it: `Recorded run · Gemma 4 E2B` or `Recorded run · rules mode`.

In `next dev` the orchestrator URL defaults to `http://127.0.0.1:8000`. In a production build with no URL set, the page goes straight to replays.

## Run locally

```bash
# from the repo root: the orchestrator, keyless
SAFEPLATE_MODE=rules .venv/Scripts/python -m uvicorn safeplate.api:app --port 8000

# in web/
npm install
npm run dev        # http://localhost:3000
```

## Deploy

```bash
# Vercel project env: NEXT_PUBLIC_ORCHESTRATOR_URL=https://<your-render-service>.onrender.com
npx vercel --prod
```

The orchestrator deploys to Render from `render.yaml`. The backend's `SAFEPLATE_CORS_ORIGINS` must include the Vercel origin. See `../docs/DEPLOY.md`.

## Checks

```bash
npm run lint
npm run build
```
