/**
 * MemoryTable.jsx — light mode
 * Full-width bottom strip: Error Class | Root Cause | Fix Applied | Similarity bar
 */

function SimilarityBar({ value }) {
  const pct = Math.round(value * 100);
  if (pct === 0) return <span className="text-gray-300 text-xs">—</span>;

  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-600 tabular-nums w-8 text-right">{pct}%</span>
    </div>
  );
}

export default function MemoryTable({ memories }) {
  return (
    <div className="flex-none border-t border-gray-200 bg-white shadow-sm">

      {/* ── Header ── */}
      <div className="px-5 pt-3 pb-1 flex items-center gap-3">
        <p className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase">
          Mistake Memory Log
        </p>
        {memories.length > 0 && (
          <span className="text-[10px] text-gray-400">{memories.length} entries</span>
        )}
      </div>

      {/* ── Table ── */}
      <div className="overflow-auto" style={{ maxHeight: "160px" }}>
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase px-5 pb-2 pt-1 w-32">Error Class</th>
              <th className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase px-3 pb-2 pt-1">Root Cause</th>
              <th className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase px-3 pb-2 pt-1">Fix Applied</th>
              <th className="text-[10px] font-semibold tracking-widest text-gray-400 uppercase px-5 pb-2 pt-1 w-32">Similarity</th>
            </tr>
          </thead>
          <tbody>
            {memories.length === 0 && (
              <tr>
                <td colSpan={4} className="px-5 py-4 text-xs text-gray-400 text-center">
                  No mistakes stored yet — run the agent to populate this table.
                </td>
              </tr>
            )}
            {memories.map((m) => (
              <tr
                key={m.id}
                className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
              >
                <td className="px-5 py-2">
                  <span className="text-[11px] font-semibold font-mono text-red-500">{m.error_class}</span>
                </td>
                <td className="px-3 py-2 text-xs text-gray-600 truncate max-w-xs">{m.root_cause}</td>
                <td className="px-3 py-2 text-xs text-gray-600 truncate max-w-xs">{m.fix_applied}</td>
                <td className="px-5 py-2">
                  <SimilarityBar value={m.last_similarity} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
