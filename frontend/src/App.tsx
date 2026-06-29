import { SymbolCard } from "./components/SymbolCard";
import { useLive } from "./useLive";

const STATUS_COLOR = {
  connected: "bg-emerald-400",
  connecting: "bg-amber-400",
  disconnected: "bg-rose-500",
} as const;

export default function App() {
  const { status, symbols } = useLive();
  const cards = Object.values(symbols).sort((a, b) => a.symbol.localeCompare(b.symbol));

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      <header className="border-b border-slate-800 px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-50">realtime-alpha</h1>
            <p className="text-sm text-slate-500">live market predictions, graded against reality</p>
          </div>
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <span className={`h-2.5 w-2.5 rounded-full ${STATUS_COLOR[status]}`} />
            {status}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        {cards.length === 0 ? (
          <p className="text-slate-500">Waiting for live predictions…</p>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2">
            {cards.map((s) => (
              <SymbolCard key={s.symbol} s={s} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
