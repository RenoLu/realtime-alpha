import { useEffect, useRef, useState } from "react";
import type { ConnStatus, PredictionMsg, SymbolState } from "./types";

const MAX_HISTORY = 60;

/** Subscribe to /ws and accumulate the latest prediction per (symbol, strategy). */
export function useLive() {
  const [status, setStatus] = useState<ConnStatus>("connecting");
  const [symbols, setSymbols] = useState<Record<string, SymbolState>>({});
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
        const m = JSON.parse(e.data) as PredictionMsg;
        if (m.type !== "prediction") return;
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
      };
    }

    connect();
    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, []);

  return { status, symbols };
}
