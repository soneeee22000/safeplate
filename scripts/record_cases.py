"""Record real agent runs so the deployed demo can replay them offline.

The hosted page cannot run Gemma — the model is 7.2 GB behind a local Ollama.
What it can do is replay runs that genuinely happened, which is what this script
produces. Every trace here is the output of the real loop against the real
Symphony labels; none of it is written by hand.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from safeplate import loop  # noqa: E402

OUTPUT = Path(__file__).resolve().parent.parent / "web" / "src" / "data" / "symphony-cases.json"

#: (request, kitchen answer or None). The kitchen answer is only reached when the
#: label and the workshop declaration both come up silent.
CASES: list[tuple[str, str | None]] = [
    ("I have a tree nut allergy. Is the gnocchis pesto vegan safe for me?", None),
    ("I am coeliac. Can I eat the gnocchis pesto vegan?", None),
    ("I am allergic to fish. Can I have the paella?", None),
    ("I am allergic to shellfish. Can I eat the paella?",
     "Non - bac scelle en usine, aucun crustace dans ce plat ni en service"),
    ("I cannot eat dairy. Is the bolognaise okay?", None),
    ("Je suis allergique au celeri. Les pates bolognaises, c'est possible ?", None),
]


def record() -> list[dict]:
    traces: list[dict] = []
    for index, (request, answer) in enumerate(CASES, start=1):
        run = loop.Run(run_id=f"SP-DEMO-{index:02d}")
        loop.begin(run, text=request)
        if answer and run.status == "awaiting_human":
            loop.answer_kitchen(run, answer)

        trace = run.as_trace()
        trace["request"] = request
        traces.append(trace)
        print(f"{index}. {request[:52]:54} -> {trace['verdict']} ({len(trace['steps'])} steps)")
    return traces


if __name__ == "__main__":
    OUTPUT.write_text(
        json.dumps(record(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nwrote {OUTPUT}")
