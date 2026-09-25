"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ORCHESTRATOR_URL,
  wakeOrchestrator,
  type AgentMode,
} from "@/lib/orchestrator";

/** Where the console stands with the live agent. */
export type AgentConnection =
  | { kind: "connecting" }
  | { kind: "waking" }
  | { kind: "live"; mode: AgentMode }
  | {
      kind: "offline";
      reason: "unconfigured" | "unreachable" | "skipped" | "lost";
    };

const INITIAL: AgentConnection = ORCHESTRATOR_URL
  ? { kind: "connecting" }
  : { kind: "offline", reason: "unconfigured" };

/**
 * Finds out whether the live agent is up, waiting out a free-tier cold start
 * before settling on recorded runs.
 *
 * @returns The connection, a way to stop waiting, a way to try again, and a
 *   way to report that a live agent which had answered has stopped answering.
 */
export function useAgentConnection(): {
  connection: AgentConnection;
  skip: () => void;
  retry: () => void;
  markOffline: () => void;
} {
  const [connection, setConnection] = useState<AgentConnection>(INITIAL);
  const [attempt, setAttempt] = useState(0);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!ORCHESTRATOR_URL) return;
    const controller = new AbortController();
    controllerRef.current = controller;
    wakeOrchestrator(controller.signal, () =>
      setConnection({ kind: "waking" }),
    ).then((mode) => {
      if (controller.signal.aborted) return;
      setConnection(
        mode
          ? { kind: "live", mode }
          : { kind: "offline", reason: "unreachable" },
      );
    });
    return () => controller.abort();
  }, [attempt]);

  const skip = useCallback(() => {
    controllerRef.current?.abort();
    setConnection({ kind: "offline", reason: "skipped" });
  }, []);

  const retry = useCallback(() => {
    if (!ORCHESTRATOR_URL) return;
    setConnection({ kind: "connecting" });
    setAttempt((count) => count + 1);
  }, []);

  const markOffline = useCallback(() => {
    controllerRef.current?.abort();
    setConnection({ kind: "offline", reason: "lost" });
  }, []);

  return { connection, skip, retry, markOffline };
}
