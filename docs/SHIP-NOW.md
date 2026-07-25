# Ship checklist — run these yourself

**Deadline 18:00 GMT+2.** My Bash tool is failing intermittently, so run these in
the session with a leading `!` (e.g. `! git status`), or in any terminal at
`C:\Gemma4Hackathon`.

Everything below is already written and tested on disk. What is left is commit,
deploy, submit.

---

## 0. Secrets — 1 minute

**Vercel needs no secrets.** The frontend never calls SerpApi; the Python
orchestrator does, and that runs on your laptop. There is nothing to configure in
the Vercel dashboard.

Create `C:\Gemma4Hackathon\.env` (gitignored — never commit it, never paste a key
into chat):

```
SERPAPI_KEY=your_own_key
SERPAPI_KEY_FALLBACK=your_friends_key
```

The fallback is used **only** when the first key returns 401/403 (bad key) or 429
(monthly quota). It is a failover, not a way to double the 250-search budget — so
only use your friend's key if they actually agreed to that.

`safeplate/config.py` loads `.env` automatically, with no new dependency. A real
shell variable still overrides the file. If no key is set at all, the lookup
degrades to "unconfirmed", which is a safe state — never to "safe".

Verify:

```bash
.venv/Scripts/python -c "from safeplate import serp; print(len(serp.api_keys()), 'keys')"
```

---

## 1. Commit and push (2 min)

Run the tests first — they should report **38 passed**:

```bash
.venv/Scripts/python -m pytest tests/ -q
```

Then:

```bash
git add safeplate/menu_symphony.py safeplate/languages.py safeplate/allergens.py safeplate/loop.py safeplate/voice.py safeplate/serp.py safeplate/config.py .env.example tests/test_menu_symphony.py docs/product-symphony.md docs/kaggle-writeup.md docs/SHIP-NOW.md web/src/components/diner-order.tsx web/src/app/order/page.tsx fixtures web/src/data
git commit -m "feat: Symphony.fr menu, four-language support, diner ordering companion"
git push origin main
```

Confirm no secret got staged — this must print nothing:

```bash
git diff --cached --name-only | grep -E "^\.env$"
```

## 2. Build and deploy (5 min)

```bash
cd web
npm run build
npx vercel --prod --yes
cd ..
```

Then confirm both pages are public — **must return 200 and show SafePlate**, not a
Vercel login:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://safeplate-ten.vercel.app/order
curl -s https://safeplate-ten.vercel.app/order | grep -o "<title>[^<]*</title>"
```

> ⚠️ Only `https://safeplate-ten.vercel.app` is public. The
> `safeplate-<hash>-sones-projects-*.vercel.app` URLs sit behind Vercel
> Deployment Protection and serve a login page — **linking one is
> auto-ineligible** under the "no login or paywall" rule. And
> `safeplate.vercel.app` (no `-ten`) is somebody else's product.

## 3. Submit on Kaggle (10 min) — THE ONLY THING THAT CAN MAKE US INELIGIBLE

Nothing else on this list matters if this is not done. **A draft is not judged.**

1. Go to https://www.kaggle.com/competitions/paris-gemma-4-hackathon/writeups
2. **New Writeup**
3. Title: `SafePlate` · Subtitle: `An allergen agent that refuses — because some ingredients are the dish`
4. Select track: **Track 2 — Autonomous Agents**
5. Paste the body of `docs/kaggle-writeup.md` (1157 words, under the 1500 limit)
6. Attachments → Project Links:
   - Repo: `https://github.com/RitaTY/gemma4`
   - Demo: `https://safeplate-ten.vercel.app/order`
7. **Submit** — top right. Confirm it no longer says "draft".

## 4. Optional, only if time remains

Add your SerpApi key so the lookup step shows real evidence instead of
"unavailable" — this is what qualifies for the cross-track SerpApi credit:

```bash
echo "SERPAPI_KEY=your_key_here" > .env
```

`.env` is gitignored. Do not paste the key into chat.

Record the terminal demo:

```bash
.venv/Scripts/python -m uvicorn safeplate.api:app --port 8000
# in another terminal:
curl -X POST http://127.0.0.1:8000/api/case -F "text=I have a tree nut allergy. Is the gnocchis pesto vegan safe for me?"
```

---

## What to say in the pitch

**Open with the vegan gnocchi.** It is the whole product in one sentence:

> Symphony.fr's _Gnocchis pesto vegan_ contains pignons de pin — pine nuts. It is
> in the ingredient list but **not** in the bold allergen text. A diner avoiding
> nuts reads "vegan" and relaxes. This is the lunch we were served today.

Then the three things that make it an agent and not a lookup:

1. **Gemma hears the diner directly.** Audio into the model, any language,
   transcription and intent in one call. Ollama's `/api/chat` silently drops audio
   — the OpenAI-compatible endpoint delivers it.
2. **Escalation is control flow, not hope.** We measured E2B failing to escalate
   on its own, so the orchestrator forces it. Every FORCED badge in the trace is
   the harness, not the model.
3. **The model does not get the last word on safety — including about its own
   output.** Handed `do_not_serve`, Gemma wrote _"We can offer you the Pad Thai
   without any added fish sauce instead."_ A deterministic check now discards any
   text that offers what the loop refused.

Then the honest close: **every Symphony label says the workshop handles all ten
allergen classes.** So for a severe allergy the answer is almost always "we cannot
guarantee this" — and an agent that says so plainly is worth more than one that
says "safe".

## Numbers you can quote

|                                     |                                            |
| ----------------------------------- | ------------------------------------------ |
| Structural refusal, end to end      | 54.1 s                                     |
| Cleared via the kitchen             | 47.1 s                                     |
| Every deterministic safety decision | **< 1 ms**                                 |
| Tesseract on a real Symphony label  | 0.4 s, correct                             |
| Gemma vision on the same label      | failed — called it "a placeholder graphic" |
| Symphony menu tests                 | 38 passing                                 |
