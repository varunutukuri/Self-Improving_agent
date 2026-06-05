/**
 * CodePanel.jsx
 * -------------
 * Read-only Monaco editor for displaying generated code.
 * Accepts an optional `height` prop so it can fill a flex container
 * (pass "100%" from LeftPanel) or use a fixed pixel height for cards.
 */
import Editor from "@monaco-editor/react";

export default function CodePanel({ code, language = "python", height = "300px" }) {
  return (
    <div className="rounded-lg overflow-hidden border border-[#1a1a30] h-full">
      <Editor
        height={height}
        language={language}
        value={code || ""}
        theme="light"
        options={{
          readOnly:             true,
          minimap:              { enabled: false },
          scrollBeyondLastLine: false,
          fontSize:             13,
          lineNumbers:          "on",
          padding:              { top: 8, bottom: 8 },
          renderLineHighlight:  "none",
        }}
      />
    </div>
  );
}
