/**
 * MemoryLog.jsx
 * -------------
 * Collapsible panel that fetches and displays stored error memories from the
 * backend.  Memories are only fetched when the panel is first opened, so
 * there is no background polling and no risk of fetch requests accumulating
 * after the component unmounts.
 */
import { useState, useEffect } from "react";

export default function MemoryLog() {
  const [isOpen,    setIsOpen]    = useState(false);
  const [memories,  setMemories]  = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  /** Fetch memories from the backend.  Silently swallows network errors. */
  const fetchMemories = async () => {
    setIsLoading(true);
    try {
      const res = await fetch("http://localhost:8000/memories");
      if (res.ok) {
        setMemories(await res.json());
      }
    } catch {
      // Backend may not be reachable yet — fail silently.
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch once each time the panel is opened
  useEffect(() => {
    if (isOpen) fetchMemories();
  }, [isOpen]);

  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      {/* Toggle button */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm text-gray-400 hover:text-gray-200 transition-colors"
      >
        <span>Memory Log</span>
        <span>{isOpen ? "▼" : "▶"}</span>
      </button>

      {/* Expandable content */}
      {isOpen && (
        <div className="border-t border-gray-800 p-3 max-h-64 overflow-y-auto">
          {isLoading && (
            <p className="text-xs text-gray-500">Loading...</p>
          )}

          {!isLoading && memories.length === 0 && (
            <p className="text-xs text-gray-600">No memories stored yet.</p>
          )}

          {memories.map((memory) => (
            <div key={memory.id} className="mb-3 pb-3 border-b border-gray-800 last:border-0">
              <p className="text-xs text-gray-400 line-clamp-2">{memory.error_text}</p>
              <p className="text-xs text-gray-600 mt-1">
                {memory.success_count} successful fix{memory.success_count !== 1 ? "es" : ""}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
