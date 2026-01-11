export type PipelineStatus = "idle" | "running" | "healthy" | "failed";

export interface PipelineRun {
  id: string;
  label: string;
  status: PipelineStatus;
  lastRun: string;
  duration: string;
  message: string;
}

export interface DatabaseSnapshot {
  table: string;
  rows: number;
  anomalies: number;
  lastUpdated: string;
  alertLevel?: "info" | "warning" | "critical";
}

export type OrderSide = "buy" | "sell";

export interface MarketOrder {
  id: string;
  owner: string;
  side: OrderSide;
  size: number;
  tradeCount?: number;
  avgPrice?: number;
  createdAt: string;
  flag?: "large" | "watch";
}

export interface Market {
  id: string;
  name: string;
  probability: number;
  volume: number;
  liquidity?: number;
  spread?: number | null;
  yesBid?: number | null;
  yesAsk?: number | null;
  noBid?: number | null;
  noAsk?: number | null;
  status?: string;
  closeTime?: string | null;
  seriesTicker?: string | null;
  lastFetched?: string | null;
  tradeCount?: number;
  description: string;
  tags: string[];
  orders: MarketOrder[];
}

export interface DashboardPayload {
  pipelineRuns: PipelineRun[];
  databaseSnapshots: DatabaseSnapshot[];
  markets: Market[];
}

export type SortBy = "volume" | "liquidity" | "probability" | "last_fetched";
export type SortOrder = "asc" | "desc";

export interface MarketsResponse {
  markets: Market[];
  total: number;
  limit: number;
  offset: number;
  sort_by: string;
  sort_order: string;
  last_sync: string | null;
}

export interface MarketFilters {
  sortBy: SortBy;
  sortOrder: SortOrder;
  status: string | null;
  search: string;
  limit: number;
  offset: number;
}
