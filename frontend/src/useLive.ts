import { useEffect, useRef, useState } from "react";
import type { AlertMsg, ConnStatus, LiveMsg, StrategyStat, SymbolState } from "./types";

const MAX_HISTORY = 60;
const MAX_ALERTS = 5;

/** Subscribe to /ws and accumulate predictions, briefings, the leaderboard, and alerts. */
export function useLive() {
  const [status, setStatus] = useState<ConnStatus>("connecting");
  const [symbols, setSymbols] = useState<Record<string, SymbolState>>({});
  const [leaderboard, setLeaderboard] = useState<StrategyStat[]>([]);
  const [alerts, setAlerts] = useState<AlertMsg[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let closed = false;
    let reconnectTimer: number | undefined;

    function connect() {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/ws`);
      wsRef.current = ws;
      setStatus("connecting");

      ws.onopen = () => setStatus("connected");
      ws.onclose = () => {
        setStatus("disconnected");
        if (!closed) reconnectTimer = window.setTimeout(connect, 1500);
      };
      ws.onmessage = (e) => {
        const m = JSON.parse(e.data) as LiveMsg;
        if (m.type === "prediction") {
          setSymbols((prev) => {
            const cur =
              prev[m.symbol] ?? { symbol: m.symbol, price: 0, history: [], strategies: {} };
            const priceChanged = m.ref_price !== cur.price && m.ref_price > 0;
            const history = priceChanged
              ? [...cur.history, m.ref_price].slice(-MAX_HISTORY)
              : cur.history;
            return {
              ...prev,
              [m.symbol]: {
                ...cur,
                price: m.ref_price || cur.price,
                history,
                strategies: { ...cur.strategies, [m.strategy_id]: m },
              },
            };
          });
        } else if (m.type === "briefing") {
          setSymbols((prev) => {
            const cur =
              prev[m.symbol] ?? { symbol: m.symbol, price: 0, history: [], strategies: {} };
            return { ...prev, [m.symbol]: { ...cur, briefing: m } };
          });
        } else if (m.type === "leaderboard") {
          setLeaderboard(m.standings);
        } else if (m.type === "alert") {
          setAlerts((prev) => [m, ...prev].slice(0, MAX_ALERTS));
        }
      };
    }

    connect();
    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, []);

  return { status, symbols, leaderboard, alerts };
}
