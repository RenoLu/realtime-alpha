import type { ReactNode } from "react";

/** Render **bold** spans within a line of text. */
function inline(text: string): ReactNode[] {
  return text.split(/\*\*/).map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i} className="font-semibold text-slate-200">
        {part}
      </strong>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

/**
 * Minimal markdown for the agent's briefings: `## headings`, `**bold**`, and
 * blank-line-separated paragraphs. Deliberately tiny — no dependency — for the small,
 * known subset the model authors.
 */
export function Markdown({ text }: { text: string }) {
  const blocks = text
    .split(/\n\n+/)
    .map((b) => b.trim())
    // drop empties and any bare JSON verdict block (e.g. a trailing {"stance":...})
    .filter((b) => b && !(b.startsWith("{") && b.endsWith("}")));

  return (
    <div className="space-y-2 text-xs leading-relaxed text-slate-400">
      {blocks.map((block, i) =>
        block.startsWith("## ") ? (
          <h4 key={i} className="text-sm font-semibold text-slate-200">
            {block.slice(3)}
          </h4>
        ) : (
          <p key={i}>{inline(block)}</p>
        ),
      )}
    </div>
  );
}
