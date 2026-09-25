import { ImageResponse } from "next/og";

export const alt =
  "A recorded rules-mode SafePlate ticket stamped DO NOT SERVE, beside the line: the model hears and speaks, the code decides.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/**
 * The image renderer cannot read CSS custom properties, so these mirror the
 * console, paper, ink and refuse tokens in globals.css. Keep them in step.
 */
const TOKENS = {
  console: "#10100e",
  paper: "#f2ede3",
  paperShade: "#e4ddcf",
  ink: "#16150f",
  inkMuted: "#6b675c",
  refuse: "#b02a20",
  muted: "#9a968b",
} as const;

const TICKET_LINES = [
  { title: "Rules read the typed request", tag: "Rule" },
  { title: "The dish table decides", tag: "Rule" },
  { title: "SerpApi: fish sauce", tag: "Forced" },
  { title: "Refuse rather than guess", tag: "Forced" },
] as const;

/** Social card: a refusal ticket and the one-line thesis. */
export default function OpengraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        gap: 64,
        padding: "0 72px",
        background: TOKENS.console,
        color: TOKENS.paper,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
        <div style={{ fontSize: 30, color: TOKENS.muted }}>SafePlate</div>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            marginTop: 24,
            fontSize: 66,
            fontWeight: 700,
            lineHeight: 1.05,
            letterSpacing: -2,
          }}
        >
          <span>The model hears and speaks.</span>
          <span>The code decides.</span>
        </div>
        <div style={{ marginTop: 36, fontSize: 28, color: TOKENS.muted }}>
          Rules mode ticket · Gemma 4 E2B runs locally
        </div>
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: 400,
          padding: "30px 32px",
          background: TOKENS.paper,
          color: TOKENS.ink,
          transform: "rotate(2deg)",
        }}
      >
        <div
          style={{
            fontSize: 16,
            color: TOKENS.inkMuted,
            letterSpacing: 1,
            marginBottom: 10,
          }}
        >
          RECORDED RUN · RULES MODE
        </div>
        <div style={{ fontSize: 34, fontWeight: 700 }}>Pad thai</div>
        <div style={{ fontSize: 20, color: TOKENS.inkMuted, marginTop: 4 }}>
          Asked about: fish
        </div>
        <div
          style={{ display: "flex", flexDirection: "column", marginTop: 16 }}
        >
          {TICKET_LINES.map((line) => (
            <div
              key={line.title}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "10px 0",
                borderTop: `1px solid ${TOKENS.paperShade}`,
                fontSize: 20,
              }}
            >
              <span>{line.title}</span>
              <span
                style={{
                  color:
                    line.tag === "Forced" ? TOKENS.refuse : TOKENS.inkMuted,
                }}
              >
                {line.tag}
              </span>
            </div>
          ))}
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            marginTop: 22,
            padding: "12px 0",
            border: `5px solid ${TOKENS.refuse}`,
            color: TOKENS.refuse,
            fontSize: 40,
            fontWeight: 700,
            letterSpacing: 1,
            transform: "rotate(-4deg)",
          }}
        >
          DO NOT SERVE
        </div>
      </div>
    </div>,
    size,
  );
}
