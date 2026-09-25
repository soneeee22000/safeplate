# Recording the demo

**Target: one take, 90–120 seconds.** The rules accept "an interactive terminal
recording ... or a short demo video". A screen recording of the real app is
faster and more convincing than anything animated.

Verified running at 16:53: Ollama 0.32.3, orchestrator on :8000, dev server on
:3000. If you are reading this later, run the pre-flight below first.

---

## 1. Pre-flight — 2 minutes

Three things must be up. Check all three in one go:

```bash
curl -s http://127.0.0.1:11434/api/version    # Ollama
curl -s http://127.0.0.1:8000/health          # orchestrator
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/order   # web
```

Expected: a version, `{"ok":true,"dishes":8,...}`, and `200`.

Start whichever is missing, each in its own terminal:

```bash
# Ollama (usually already running as a service)
ollama serve

# Orchestrator — from C:\Gemma4Hackathon
.venv/Scripts/python -m uvicorn safeplate.api:app --host 127.0.0.1 --port 8000

# Web — from C:\Gemma4Hackathon\web
npm run dev
```

**Warm the model before recording.** The first call after a cold start pays an
extra ~20 s while the 7.2 GB model loads. Fire one throwaway request so the
recording does not open on a long stall:

```bash
curl -s -X POST http://127.0.0.1:8000/api/case -F "text=warmup, is the paella ok for fish" > /dev/null
```

Ollama holds the model in RAM for 30 minutes after that, so record within the
half hour.

---

## 2. Set the screen up

- Record **`http://localhost:3000/order`** — the local one, which runs live.
  **Not** the Vercel URL, which replays recordings.
- Confirm the banner is **green**: _"Live — Gemma 4 E2B is hearing and reasoning
  on this machine."_ Amber means the orchestrator is not reachable and you would
  be recording a replay.
- Browser at 100 % zoom, close other tabs, hide bookmarks (`Ctrl+Shift+B`).
- Full screen the browser (`F11`) so no desktop clutter is in frame.

---

## 3. Start recording

**Windows Game Bar — no install:**

| Key             | Does                                        |
| --------------- | ------------------------------------------- |
| `Win + Alt + R` | Start / stop recording                      |
| `Win + G`       | Open the overlay if the hotkey does nothing |
| `Win + Alt + M` | Toggle the microphone                       |

Turn the **microphone on** — narration is most of the value.

Files land in:

```
%USERPROFILE%\Videos\Captures\
```

> Game Bar records the **focused window**, not the whole desktop, and will not
> record File Explorer or the desktop itself. Click the browser first.

**If Game Bar is disabled:** Settings → Gaming → Game Bar → on. Or use OBS.

**ffmpeg alternative** (if you have it, gives a clean full-screen capture):

```bash
ffmpeg -f gdigrab -framerate 30 -i desktop -c:v libx264 -preset ultrafast -pix_fmt yuv420p demo.mp4
```

Press `q` in that terminal to stop.

---

## 4. The script — two takes, one recording

### Take 1 — the refusal (60 s)

1. Land on `/order`. Say: **"This is Symphony.fr, the caterer that fed this
   hackathon. These are their three real dishes, and this is their real label
   text."**
2. Tap **Gnocchis pesto vegan**.
3. Type or say: **"I have a tree nut allergy. Is the gnocchis pesto vegan safe
   for me?"**
4. Press **Ask**.
5. **Talk over the wait** — Gemma takes ~25 s to hear and structure the request,
   and another ~25 s to compose the answer. Fill it with the point:

   > "Gemma is doing the listening here — audio straight into the model, any
   > language, transcription and intent in one call. While it works: this dish is
   > sold as vegan, and vegan is a claim about animal products, not allergens.
   > The pesto is made with pignons de pin — pine nuts. They are not an EU-14
   > allergen, so the label is right not to bold them — and many tree-nut-allergic
   > diners avoid them all the same. No rule settles that, so the agent asks."

6. Land on the verdict: **NEEDS CONFIRMATION**, with the pine nuts named as an
   advisory and the workshop declaration quoted.
7. Point at the **FORCED** badges: **"Those are the orchestrator, not the model.
   We measured Gemma failing to escalate on its own, so escalation is control
   flow."**

### Take 2 — it asks a human (40 s)

1. Scroll up, tap **Paëlla poisson chorizo et poulet**.
2. Ask: **"I am allergic to shellfish. Can I eat the paella?"**
3. It stops and asks the kitchen — say: **"Cross-contact is not on any label and
   never will be. The label is silent on shellfish and the workshop line does not
   cover it, so the agent will not guess. It asks a person."**
4. Type the chef's answer: `Non - bac scellé en usine, aucun crustacé`
5. It clears. **"And that is the only way anything ever gets cleared here."**

### Close (10 s)

> "Every Symphony label says the workshop handles all ten allergen classes. So
> for a severe allergy the honest answer is usually 'we cannot guarantee this' —
> and an agent that says that plainly is worth more than one that says 'safe'."

---

## 5. After recording

1. Play it back. Check the audio recorded and the verdict is legible.
2. If a take stalled, re-record just that one — do not ship a stall.
3. Trim in Photos (`Win + E` → the file → Edit) or Clipchamp if needed. Optional.
4. Attach to the Kaggle Writeup under **Attachments**, or upload to YouTube
   unlisted and paste the link.

---

## If something breaks mid-record

| Symptom                                  | Cause                                                                       | Fix                                                                               |
| ---------------------------------------- | --------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Banner is amber                          | Orchestrator down                                                           | Restart uvicorn, reload the page                                                  |
| Stuck on "checking…" past 90 s           | Model cold or Ollama died                                                   | `curl http://127.0.0.1:11434/api/version`, re-warm                                |
| "not on our verified list"               | Orchestrator running stale code                                             | Kill uvicorn and restart it                                                       |
| Verdict is right but the wording is flat | The refusal guardrail discarded Gemma's text and used the assembled version | Not a bug — that is the safety check working, and it is worth saying so on camera |

**Fallback if the live run will not cooperate:** record the Vercel page at
`https://safeplate-ten.vercel.app/order` instead. It replays real runs. Say
"recorded run" on camera — never call it live.
