export interface PredictionMsg {
  type: "prediction";
  symbol: string;
  strategy_id: string;
  horizon_s: number;
  yhat: number;
  confidence: number;
  ts: number;
  ref_price: number;
  model_ver: string;
}

/** Off-path deep-analysis briefing (refreshed on a slow cadence by the scheduler). */
export interface BriefingMsg {
  type: "briefing";
  symbol: string;
  stance: string;
  yhat: number;
  confidence: number;
  briefing_md: string;
  ts: number;
}

/** One row of the live strategy leaderboard. */
export interface StrategyStat {
  strategy_id: string;
  n: number;
  dir_acc: number; // directional accuracy [0,1]
  mae: number;
  mean_confidence: number;
  calibration_gap: number;
  symbol: string;
}

export interface LeaderboardMsg {
  type: "leaderboard";
  standings: StrategyStat[];
}

export interface AlertMsg {
  type: "alert";
  symbol: string;
  kind: string;
  severity: string;
  message: string;
  ts: number;
}

export type LiveMsg = PredictionMsg | BriefingMsg | LeaderboardMsg | AlertMsg;

export type ConnStatus = "connecting" | "connected" | "disconnected";

export interface SymbolState {
  symbol: string;
  price: number;
  history: number[]; // recent ref_price values for the sparkline
  strategies: Record<string, PredictionMsg>;
  briefing?: BriefingMsg;
}
