/**
 * StatusBar.jsx — light mode
 * Thin bottom status line: Iterations · Status · Memory entries · Memory hits · Tokens
 */

const STATUS_LABELS = {
  idle:     { label: "Idle",    color: "text-gray-400"   },
  running:  { label: "Running", color: "text-blue-600"   },
  complete: { label: "Solved",  color: "text-emerald-600" },
  error:    { label: "Failed",  color: "text-red-500"    },
};

function Dot() {
  return <span className="text-gray-300 mx-2">·</span>;
}

export default function StatusBar({
  iterations,
  maxIterations,
  status,
  memoryEntries,
  memoryHitCount,
  tokenEstimate,
}) {
  const completedIterations = iterations.length;
  const { label: statusLabel, color: statusColor } = STATUS_LABELS[status] || STATUS_LABELS.idle;

  return (
    <div className="flex-none h-8 flex items-center px-5 bg-white border-t border-gray-200 text-[11px] text-gray-400">

      <span>
        Iterations{" "}
        <span className="text-gray-600 tabular-nums font-medium">
          {completedIterations}/{maxIterations}
        </span>
      </span>

      <Dot />

      <span>
        Status: <span className={`font-medium ${statusColor}`}>{statusLabel}</span>
      </span>

      <Dot />

      <span>
        Memory entries:{" "}
        <span className="text-gray-600 tabular-nums font-medium">{memoryEntries}</span>
      </span>

      <Dot />

      <span>
        Memory hits:{" "}
        <span className="text-gray-600 tabular-nums font-medium">{memoryHitCount}</span>
      </span>

      <Dot />

      <span>
        Tokens used:{" "}
        <span className="text-gray-600 tabular-nums font-medium">~{tokenEstimate.toLocaleString()}</span>
      </span>

    </div>
  );
}
