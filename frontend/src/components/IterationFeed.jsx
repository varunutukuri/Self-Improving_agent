/**
 * IterationFeed.jsx
 * -----------------
 * Renders the full list of completed iteration cards plus a live streaming
 * card while the LLM is generating code.  Also shows terminal status messages
 * (complete / error) below the cards.
 */
import IterationCard from "./IterationCard";
import CodePanel from "./CodePanel";

export default function IterationFeed({ iterations, streamingCode, status, statusMessage }) {
  const isEmpty = iterations.length === 0 && !streamingCode;

  return (
    <div className="flex flex-col gap-4">

      {/* Empty state — shown before the first run */}
      {isEmpty && status === "idle" && (
        <div className="text-center text-gray-600 mt-20 text-sm">
          Enter a task and click Run Agent to start.
        </div>
      )}

      {/* Completed iteration cards */}
      {iterations.map((event) => (
        <IterationCard key={`${event.iteration}-${event.status}`} event={event} />
      ))}

      {/* Live streaming card — visible while the LLM is generating */}
      {streamingCode && (
        <div className="border border-blue-800 rounded-xl bg-gray-900 overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3 border-b border-blue-800">
            <span className="text-gray-400 text-sm font-mono">
              Iteration {iterations.length + 1}
            </span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-900 text-blue-300 animate-pulse">
              GENERATING
            </span>
            {statusMessage && (
              <span className="text-xs text-gray-500 ml-auto">{statusMessage}</span>
            )}
          </div>
          <div className="p-4">
            <CodePanel code={streamingCode} />
          </div>
        </div>
      )}

      {/* Terminal status banners */}
      {status === "complete" && (
        <div className="text-center text-green-400 text-sm py-4">
          ✓ All tests passed
        </div>
      )}
      {status === "error" && (
        <div className="text-center text-red-400 text-sm py-4">
          Max iterations reached — could not solve the task.
        </div>
      )}

    </div>
  );
}
