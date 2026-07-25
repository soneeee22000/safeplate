# Séjour Pour Tous — Tuesday Setup (copy-paste)

Goal tonight: Gemma 4 E4B pulled + pinned, venv ready, **offline smoke test green.**
That's the gate to Wednesday (data). Everything below runs from the project root
`C:\Gemma4Hackathon`.

## 1. One-time: install Ollama (skip if `ollama --version` works)

```powershell
winget install Ollama.Ollama
```

## 2. Run the setup script (pulls the model, ~9.6 GB — big download)

```powershell
powershell -ExecutionPolicy Bypass -File .\setup\01-setup.ps1
```

What it does: checks Ollama → pulls `gemma4:e4b-it-q4_K_M` → writes the revision pin to
`setup\model-pin.txt` → prints the **real on-disk size** (check it leaves headroom on 16 GB) →
creates `.venv` and installs `setup\requirements.txt`.

If the E4B pull is too big/slow, pull the lighter fallback and re-run the smoke test — it
auto-detects it:

```powershell
ollama pull gemma4:e2b
```

## 3. THE GATE: turn WIFI OFF, then run the smoke test

```powershell
.\.venv\Scripts\python.exe .\setup\smoke_test.py
```

Expected: `[PASS] Tuesday gate green — offline generation + tool-calling both work.`

## What each result means

- **Both pass** → environment is solid, proceed to Wednesday (data ingest).
- **Generation passes, tool-call fails** → not fatal. Tool-calling is the runtime's most
  fragile part (per research). Plan B: the app orchestrator calls the engine directly, and
  we keep model-driven tool-calling only for the "Claude calls my MCP" showcase.
- **Generation fails offline** → model didn't pull or Ollama service isn't running
  (`ollama serve`). Fix before anything else — offline is the whole pitch.

## Pin note

`setup\model-pin.txt` records the model digest + date. If you re-pull closer to Saturday
(the research flagged a stealth tool-calling weight update), diff the digest and re-run the
smoke test — never demo a model you haven't smoke-tested.
