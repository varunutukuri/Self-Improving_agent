/**
 * App.jsx — Root layout (light mode)
 * header · (left panel | right panel) · memory table · status bar
 */
import { useState, useEffect, useCallback } from "react";
import { useAgentSocket } from "./hooks/useAgentSocket";
import LeftPanel     from "./components/LeftPanel";
import IterationCard from "./components/IterationCard";
import MemoryTable   from "./components/MemoryTable";
import StatusBar     from "./components/StatusBar";

export default function App() {
  const {
    iterations, status, streamingCode, statusMessage,
    currentIteration, tokenEstimate, memoryHitCount, memorySaveCount,
    runAgent, stop,
  } = useAgentSocket();

  const [task,          setTask]          = useState("");
  const [language,      setLanguage]      = useState("python");
  const [maxIterations, setMaxIterations] = useState(5);
  const [memories,      setMemories]      = useState([]);

  /* ── Fetch memories from backend ── */
  const fetchMemories = useCallback(async () => {
    try {
      const res = await fetch("http://localhost:8000/memories");
      if (res.ok) setMemories(await res.json());
    } catch {
      // backend may not be reachable; fail silently
    }
  }, []);

  // Refresh the memory table once the backend confirms a row was written
  useEffect(() => {
    if (memorySaveCount > 0) fetchMemories();
  }, [memorySaveCount, fetchMemories]);

  // Pre-populate on mount
  useEffect(() => { fetchMemories(); }, [fetchMemories]);

  /* ── Code shown in the left-panel Monaco editor ── */
  const displayCode         = streamingCode || iterations[iterations.length - 1]?.code || "";
  const displayIterationNum = streamingCode ? iterations.length + 1 : iterations.length || 1;
  const isRunning           = status === "running";

  const handleRun = () => runAgent(task, maxIterations);

  return (
    <div className="h-screen flex flex-col bg-gray-50 text-gray-900 overflow-hidden font-sans">

      {/* ── Header ── */}
      <header className="flex-none flex items-center justify-between px-5 h-11 bg-white border-b border-gray-200 shadow-sm">
        <div className="flex items-center gap-2.5">
          <span className="text-blue-600 font-bold text-sm tracking-wider">⬡ AIDEN</span>
          <span className="text-gray-300 text-xs">—</span>
          <span className="text-gray-500 text-xs tracking-wide">self-improving code agent</span>
        </div>
        <div className="flex items-center gap-2">
          {isRunning && (
            <span className="flex items-center gap-1.5 text-xs text-blue-600">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
              running
            </span>
          )}
          {status === "complete" && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-600">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              solved
            </span>
          )}
          {status === "error" && (
            <span className="flex items-center gap-1.5 text-xs text-red-500">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
              failed
            </span>
          )}
        </div>
      </header>

      {/* ── Main content: left + right panels ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left panel */}
        <LeftPanel
          task={task}               setTask={setTask}
          language={language}       setLanguage={setLanguage}
          maxIterations={maxIterations} setMaxIterations={setMaxIterations}
          status={status}
          onRun={handleRun}         onStop={stop}
          displayCode={displayCode}
          iterationNum={displayIterationNum}
        />

        {/* Right panel — iteration feed */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 bg-gray-50">

          <p className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase mb-1">
            Live Iteration Feed
          </p>

          {/* Empty / idle state */}
          {iterations.length === 0 && !isRunning && (
            <div className="flex-1 flex items-center justify-center">
              <p className="text-gray-400 text-sm">Enter a task and click Run Agent to start.</p>
            </div>
          )}

          {/* Generating placeholder — first iteration */}
          {isRunning && iterations.length === 0 && (
            <div className="border border-blue-200 rounded-xl bg-blue-50 px-4 py-3 flex items-center gap-3">
              <span className="text-gray-500 text-sm font-mono">Iteration {currentIteration}</span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-600 animate-pulse">
                GENERATING
              </span>
              {statusMessage && (
                <span className="text-xs text-gray-400 ml-auto">{statusMessage}</span>
              )}
            </div>
          )}

          {/* Completed iteration cards */}
          {iterations.map((event) => (
            <IterationCard
              key={`${event.iteration}-${event.status}`}
              event={event}
            />
          ))}

          {/* Generating placeholder — subsequent iterations */}
          {isRunning && iterations.length > 0 && streamingCode && (
            <div className="border border-blue-200 rounded-xl bg-blue-50 px-4 py-3 flex items-center gap-3">
              <span className="text-gray-500 text-sm font-mono">Iteration {iterations.length + 1}</span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-600 animate-pulse">
                GENERATING
              </span>
              {statusMessage && (
                <span className="text-xs text-gray-400 ml-auto">{statusMessage}</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Bottom strip: Mistake Memory Log ── */}
      <MemoryTable memories={memories} />

      {/* ── Status bar ── */}
      <StatusBar
        iterations={iterations}
        maxIterations={maxIterations}
        status={status}
        memoryEntries={memories.length}
        memoryHitCount={memoryHitCount}
        tokenEstimate={tokenEstimate}
      />
    </div>
  );
}
