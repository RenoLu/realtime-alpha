import type { BriefingMsg, SymbolState } from "../types";
import { Markdown } from "./Markdown";
import { Sparkline } from "./Sparkline";

function fmtPrice(p: number): string {
  return p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function SymbolCard({ s }: { s: SymbolState }) {
  const strategies = Object.values(s.strategies).sort((a, b) =>
    a.strategy_id.localeCompare(b.strategy_id),
  );

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-slate-100">{s.symbol}</h2>
        <span className="font-mono text-xl tabular-nums text-slate-100">${fmtPrice(s.price)}</span>
      </div>

      <div className="mt-3">
        <Sparkline values={s.history} />
      </div>

      <div className="mt-4 space-y-2">
        {strategies.map((p) => {
          const dir = p.yhat > 0 ? "up" : p.yhat < 0 ? "down" : "flat";
          const color =
            dir === "up" ? "text-emerald-400" : dir === "down" ? "text-rose-400" : "text-slate-400";
          const arrow = dir === "up" ? "▲" : dir === "down" ? "▼" : "—";
          return (
            <div key={p.strategy_id} className="flex items-center justify-between text-sm">
              <span className="text-slate-300">{p.strategy_id}</span>
              <div className="flex items-center gap-4">
                <span className={`font-mono tabular-nums ${color}`}>
                  {arrow} {(p.yhat * 100).toFixed(3)}%
                </span>
                <div className="flex items-center gap-1" title="confidence">
                  <div className="h-1.5 w-16 rounded bg-slate-800">
                    <div
                      className="h-1.5 rounded bg-sky-500"
                      style={{ width: `${Math.round(p.confidence * 100)}%` }}
                    />
                  </div>
                  <span className="w-8 text-right font-mono text-xs text-slate-500">
                    {(p.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {s.briefing && <Briefing b={s.briefing} />}

      <div className="mt-3 text-right text-xs text-slate-600">
        horizon {strategies[0]?.horizon_s ?? 60}s
      </div>
    </div>
  );
}

const STANCE_STYLE: Record<string, string> = {
  bullish: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  bearish: "bg-rose-500/15 text-rose-300 ring-rose-500/30",
  neutral: "bg-slate-500/15 text-slate-300 ring-slate-500/30",
};

function Briefing({ b }: { b: BriefingMsg }) {
  const style = STANCE_STYLE[b.stance] ?? STANCE_STYLE.neutral;
  // The model authors a markdown narrative; the mock backend leaves it empty / a JSON stub.
  const md = b.briefing_md.trim();
  const hasNarrative = md.length > 0 && !md.startsWith("{");
  return (
    <details open className="mt-4 border-t border-slate-800 pt-3">
      <summary className="mb-2 flex cursor-pointer list-none items-center justify-between text-sm">
        <span className="font-medium text-slate-300">AI analysis</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium uppercase ring-1 ${style}`}>
          {b.stance}
        </span>
      </summary>
      {hasNarrative ? (
        <Markdown text={b.briefing_md} />
      ) : (
        <p className="text-xs text-slate-600">
          No narrative yet (mock model — run with RTA_MODEL=agent or add API credit).
        </p>
      )}
    </details>
  );
}
