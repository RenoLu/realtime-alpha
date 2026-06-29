import type { StrategyStat } from "../types";

function pct(x: number): string {
  return `${(x * 100).toFixed(0)}%`;
}

/** Live strategy leaderboard: ranked by directional accuracy, graded against realized prices. */
export function Leaderboard({ standings }: { standings: StrategyStat[] }) {
  if (standings.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          strategy leaderboard
        </h2>
        <p className="mt-3 text-sm text-slate-500">
          Scoring predictions against realized prices… (first results after one horizon elapses)
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
        strategy leaderboard
      </h2>
      <p className="mt-1 text-xs text-slate-600">
        directional accuracy on realized outcomes — the system grading itself, live
      </p>
      <table className="mt-3 w-full text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-wide text-slate-500">
            <th className="py-1 text-left font-medium">#</th>
            <th className="py-1 text-left font-medium">strategy</th>
            <th className="py-1 text-right font-medium">dir. acc</th>
            <th className="py-1 text-right font-medium">MAE</th>
            <th className="py-1 text-right font-medium">n</th>
          </tr>
        </thead>
        <tbody>
          {standings.map((s, i) => {
            const lead = i === 0;
            return (
              <tr
                key={s.strategy_id}
                className={`border-t border-slate-800/70 ${lead ? "text-slate-100" : "text-slate-300"}`}
              >
                <td className="py-1.5 tabular-nums text-slate-500">{i + 1}</td>
                <td className="py-1.5">
                  {s.strategy_id}
                  {lead && (
                    <span className="ml-2 rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-medium uppercase text-emerald-300 ring-1 ring-emerald-500/30">
                      leader
                    </span>
                  )}
                </td>
                <td className="py-1.5 text-right font-mono tabular-nums">
                  <span className={s.dir_acc >= 0.5 ? "text-emerald-400" : "text-rose-400"}>
                    {pct(s.dir_acc)}
                  </span>
                </td>
                <td className="py-1.5 text-right font-mono tabular-nums text-slate-400">
                  {(s.mae * 100).toFixed(3)}%
                </td>
                <td className="py-1.5 text-right font-mono tabular-nums text-slate-500">{s.n}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
