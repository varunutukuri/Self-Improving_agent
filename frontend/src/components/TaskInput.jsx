/**
 * TaskInput.jsx — light mode
 * Task prompt textarea + language selector + max-iterations input + Run/Stop buttons.
 */

const LANGUAGES = [
  { value: "python",     label: "Python" },
  { value: "javascript", label: "JavaScript" },
  { value: "typescript", label: "TypeScript" },
  { value: "go",         label: "Go" },
  { value: "rust",       label: "Rust" },
];

export default function TaskInput({
  task, setTask,
  language, setLanguage,
  maxIterations, setMaxIterations,
  status,
  onRun, onStop,
}) {
  const isRunning = status === "running";

  return (
    <div className="flex flex-col gap-3">

      <label className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase">
        Natural Language Prompt
      </label>

      {/* ── Textarea ── */}
      <textarea
        value={task}
        onChange={(e) => setTask(e.target.value)}
        disabled={isRunning}
        placeholder="e.g. Write a function that returns the nth Fibonacci number. Handle edge cases for n=0 and n=1."
        className="w-full h-28 bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm text-gray-800 placeholder-gray-400 resize-none focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100 disabled:opacity-50 transition-colors"
      />

      {/* ── Controls row ── */}
      <div className="flex items-center gap-2">
        {/* Language selector */}
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          disabled={isRunning}
          className="h-8 bg-white border border-gray-200 rounded-md px-2 text-xs text-gray-700 focus:outline-none focus:border-blue-400 disabled:opacity-50 cursor-pointer shadow-sm"
        >
          {LANGUAGES.map((l) => (
            <option key={l.value} value={l.value}>{l.label}</option>
          ))}
        </select>

        {/* Run button */}
        <button
          onClick={onRun}
          disabled={isRunning || !task.trim()}
          className="flex items-center gap-1.5 flex-1 justify-center h-8 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-md transition-colors shadow-sm"
        >
          <span>{isRunning ? "●" : "▶"}</span>
          {isRunning ? "Running…" : "Run agent"}
        </button>

        {/* Stop button */}
        {isRunning && (
          <button
            onClick={onStop}
            className="h-8 px-3 bg-white hover:bg-gray-100 border border-gray-200 text-gray-600 text-xs font-semibold rounded-md transition-colors shadow-sm"
          >
            Stop
          </button>
        )}
      </div>

      {/* ── Max iterations control ── */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-gray-400">max</label>
        <input
          type="number"
          min={1}
          max={10}
          value={maxIterations}
          onChange={(e) => setMaxIterations(Math.max(1, Math.min(10, parseInt(e.target.value) || 1)))}
          disabled={isRunning}
          className="w-14 h-7 bg-white border border-gray-200 rounded-md px-2 text-xs text-gray-700 text-center focus:outline-none focus:border-blue-400 disabled:opacity-50 shadow-sm"
        />
        <label className="text-xs text-gray-400">iterations</label>
      </div>

    </div>
  );
}
