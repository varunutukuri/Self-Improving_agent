/**
 * LeftPanel.jsx — light mode
 * Left sidebar: task input controls on top, live code editor below.
 */
import CodePanel from "./CodePanel";
import TaskInput from "./TaskInput";

export default function LeftPanel({
  task, setTask,
  language, setLanguage,
  maxIterations, setMaxIterations,
  status,
  onRun, onStop,
  displayCode,
  iterationNum,
}) {
  const isRunning = status === "running";

  return (
    <div className="w-[420px] flex-none flex flex-col border-r border-gray-200 bg-white shadow-sm">

      {/* ── Task input section ── */}
      <div className="flex-none p-4 border-b border-gray-200">
        <p className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase mb-3">
          Task Input
        </p>
        <TaskInput
          task={task}               setTask={setTask}
          language={language}       setLanguage={setLanguage}
          maxIterations={maxIterations} setMaxIterations={setMaxIterations}
          status={status}
          onRun={onRun}             onStop={onStop}
        />
      </div>

      {/* ── Live code editor section ── */}
      <div className="flex-1 flex flex-col p-4 min-h-0">
        <p className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase mb-2 flex items-center gap-2">
          Generated Code
          {isRunning && (
            <span className="text-[10px] normal-case tracking-normal text-blue-500 font-mono">
              — Iteration {iterationNum}
            </span>
          )}
          {!isRunning && displayCode && (
            <span className="text-[10px] normal-case tracking-normal text-gray-400 font-mono">
              — Iteration {iterationNum}
            </span>
          )}
          {isRunning && (
            <span className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
          )}
        </p>

        <div className="flex-1 rounded-lg overflow-hidden border border-gray-200 min-h-0">
          <CodePanel
            code={displayCode}
            language={language}
            height="100%"
          />
        </div>
      </div>

    </div>
  );
}
