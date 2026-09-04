/**
 * useAgentSocket.js
 * -----------------
 * Manages the WebSocket connection and all agent-run state.
 *
 * Event flow
 * ----------
 * token              → accumulates streamingCode (left panel Monaco)
 * status             → updates statusMessage + currentIteration
 * iteration_failed   → adds a card to iterations[] with analyzing=true
 * iteration_analysis → patches the matching card with critic rows
 * memory_saved       → bumps memorySaveCount, which triggers a /memories refetch
 * complete           → adds a final passing card, sets status=complete
 * max_iterations_reached → sets status=error
 *
 * Leak prevention
 * ---------------
 * Before a new socket is opened, the previous socket's handlers are nulled so
 * stale callbacks cannot fire after the new session starts.
 */
import { useState, useCallback, useRef } from "react";

export function useAgentSocket() {
  const [iterations,      setIterations]      = useState([]);
  const [status,          setStatus]          = useState("idle");
  const [streamingCode,   setStreamingCode]   = useState("");
  const [statusMessage,   setStatusMessage]   = useState("");
  const [currentIteration, setCurrentIteration] = useState(0);
  const [charCount,       setCharCount]       = useState(0);   // for token estimate
  const [memoryHitCount,  setMemoryHitCount]  = useState(0);
  const [memorySaveCount, setMemorySaveCount] = useState(0);   // triggers memory refetch

  const wsRef = useRef(null);

  const runAgent = useCallback((task, maxIterations = 5) => {
    // Tear down any existing socket cleanly
    if (wsRef.current) {
      wsRef.current.onmessage = null;
      wsRef.current.onclose   = null;
      wsRef.current.close();
    }

    // Reset all state for the new run
    setIterations([]);
    setStreamingCode("");
    setStatus("running");
    setStatusMessage("");
    setCurrentIteration(1);
    setCharCount(0);
    setMemoryHitCount(0);
    setMemorySaveCount(0);

    const ws = new WebSocket("ws://localhost:8000/ws/run");
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ task, max_iterations: maxIterations }));
    };

    ws.onmessage = (e) => {
      const event = JSON.parse(e.data);

      switch (event.type) {

        case "token":
          // Accumulate streamed tokens in the left panel Monaco editor
          setStreamingCode((prev) => prev + event.token);
          setCharCount((prev) => prev + event.token.length);
          break;

        case "status":
          setStatusMessage(event.message);
          if (event.iteration) setCurrentIteration(event.iteration);
          break;

        case "iteration_failed":
          // Add a card immediately; critic rows arrive via iteration_analysis
          setIterations((prev) => [
            ...prev,
            {
              ...event,
              analyzing:   true,   // shows shimmer until iteration_analysis arrives
              error_class: null,
              root_cause:  null,
              fix_hint:    null,
            },
          ]);
          setStreamingCode("");
          if (event.memory_hit) setMemoryHitCount((prev) => prev + 1);
          break;

        case "memory_saved":
          // Fired by the backend AFTER the row is committed. Refetching on
          // iteration_failed instead would query before the write lands and
          // leave the table one step behind.
          setMemorySaveCount((prev) => prev + 1);
          break;

        case "iteration_analysis":
          // Patch the existing card for this iteration with the critic output
          setIterations((prev) =>
            prev.map((it) =>
              it.iteration === event.iteration
                ? {
                    ...it,
                    analyzing:   false,
                    error_class: event.error_class,
                    root_cause:  event.root_cause,
                    fix_hint:    event.fix_hint,
                  }
                : it
            )
          );
          break;

        case "complete":
          setIterations((prev) => [...prev, event]);
          setStatus("complete");
          setStreamingCode("");
          setCurrentIteration(event.iteration);
          break;

        case "max_iterations_reached":
          setStatus("error");
          setStreamingCode("");
          break;

        case "error":
          setStatus("error");
          break;

        default:
          console.warn("[WS] unhandled event type:", event.type);
      }
    };

    ws.onclose = () => {
      setStatus((prev) => (prev === "running" ? "idle" : prev));
    };
  }, []);

  const stop = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
    }
    setStatus("idle");
    setStreamingCode("");
  }, []);

  // Approximate token count (4 chars ≈ 1 token)
  const tokenEstimate = Math.round(charCount / 4);

  return {
    iterations,
    status,
    streamingCode,
    statusMessage,
    currentIteration,
    tokenEstimate,
    memoryHitCount,
    memorySaveCount,
    runAgent,
    stop,
  };
}
