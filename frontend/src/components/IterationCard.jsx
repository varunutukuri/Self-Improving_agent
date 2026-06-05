/**
 * IterationCard.jsx — light mode
 *
 * Sections
 * 1. Header        — "Iteration N" + pass/fail badge with counts
 * 2. Test pills    — per-test pass/fail pills
 * 3. Memory banner — amber strip when a past pattern was retrieved
 * 4. Critic rows   — error class / root cause / fix hint (shimmer while analyzing)
 */

function TestPill({ name, passed }) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full ${
        passed
          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
          : "bg-red-50 text-red-600 border border-red-200"
      }`}
    >
      {passed ? "✓" : "✗"} {name}
    </span>
  );
}

function CriticRow({ label, value, shimmer }) {
  return (
    <div className="flex items-start gap-3 text-xs">
      <span className="w-20 flex-none text-gray-400 font-medium pt-0.5">{label}</span>
      {shimmer ? (
        <div className="flex-1 h-4 shimmer rounded" />
      ) : (
        <span className="flex-1 text-gray-700 leading-relaxed">{value || "—"}</span>
      )}
    </div>
  );
}

export default function IterationCard({ event }) {
  const passed      = event.status === "passed";
  const analyzing   = event.analyzing;
  const testCases   = event.test_cases || [];
  const totalTests  = testCases.length;
  const passedTests = testCases.filter((t) => t.passed).length;
  const failedTests = totalTests - passedTests;

  return (
    <div className="border border-gray-200 rounded-xl bg-white overflow-hidden shadow-sm">

      {/* ── 1. Header ── */}
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-100">
        <span className="text-gray-500 text-sm font-mono">Iteration {event.iteration}</span>

        {passed ? (
          <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 border border-emerald-200">
            {totalTests > 0 ? `${passedTests} / ${totalTests} tests passed` : "PASSED"}
          </span>
        ) : (
          <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-600 border border-red-200">
            {totalTests > 0 ? `${failedTests} / ${totalTests} tests failed` : "FAILED"}
          </span>
        )}
      </div>

      {/* ── 2. Test pills ── */}
      {testCases.length > 0 && (
        <div className="px-4 py-2.5 border-b border-gray-100 flex flex-wrap gap-1.5 bg-gray-50">
          {testCases.map((tc, i) => (
            <TestPill key={i} name={tc.name} passed={tc.passed} />
          ))}
        </div>
      )}

      {/* ── 3. Memory hit banner ── */}
      {event.memory_hit && event.similarity_score != null && (
        <div className="px-4 py-2.5 border-b border-amber-200 bg-amber-50 flex items-start gap-2">
          <span className="text-amber-500 text-xs mt-0.5">◆</span>
          <p className="text-xs text-amber-800 leading-relaxed">
            <span className="font-semibold text-amber-700">
              Memory hit — {(event.similarity_score * 100).toFixed(1)}% similarity
            </span>{" "}
            to a past mistake — applying known fix pattern
          </p>
        </div>
      )}

      {/* ── 4. Critic rows ── */}
      {!passed && (
        <div className="px-4 py-3 flex flex-col gap-2.5">
          <CriticRow label="error class" value={event.error_class} shimmer={analyzing} />
          <CriticRow label="root cause"  value={event.root_cause}  shimmer={analyzing} />
          <CriticRow label="fix hint"    value={event.fix_hint}    shimmer={analyzing} />
        </div>
      )}

    </div>
  );
}
