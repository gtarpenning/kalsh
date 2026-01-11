"use client";

import { Fragment, useState } from "react";
import { Market, SortBy, SortOrder } from "@/types/dashboard";
import CandlestickChart from "./CandlestickChart";

interface MarketExplorerProps {
  markets: Market[];
  onSelectMarket: (id: string) => void;
  search: string;
  onSearchChange: (value: string) => void;
  onRefresh: () => Promise<void>;
  sortBy?: SortBy;
  sortOrder?: SortOrder;
  onSortChange?: (sortBy: SortBy, sortOrder: SortOrder) => void;
  statusFilter?: string | null;
  onStatusFilterChange?: (status: string | null) => void;
  lastSync?: string | null;
  totalMarkets?: number;
}

const sidePill: Record<"buy" | "sell", string> = {
  buy: "bg-emerald-100 text-emerald-700",
  sell: "bg-rose-100 text-rose-700",
};

export default function MarketExplorer({
  markets,
  onSelectMarket,
  search,
  onSearchChange,
  onRefresh,
  sortBy = "volume",
  sortOrder = "desc",
  onSortChange,
  statusFilter = null,
  onStatusFilterChange,
  lastSync,
  totalMarkets,
}: MarketExplorerProps) {
  const [expandedMarketId, setExpandedMarketId] = useState<string | null>(null);

  const handleSortChange = (newSortBy: SortBy) => {
    if (!onSortChange) return;
    
    if (sortBy === newSortBy) {
      onSortChange(newSortBy, sortOrder === "desc" ? "asc" : "desc");
    } else {
      onSortChange(newSortBy, "desc");
    }
  };

  const formatLastSync = (isoString: string | null | undefined) => {
    if (!isoString) return "Never";
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  const toggleExpand = (marketId: string) => {
    setExpandedMarketId(expandedMarketId === marketId ? null : marketId);
    onSelectMarket(marketId);
  };

  const totalLargeOrders = markets.reduce(
    (total, market) => total + market.orders.filter((order) => order.flag === "large").length,
    0
  );

  return (
    <section className="rounded-3xl border border-zinc-200 bg-white/80 shadow-sm backdrop-blur">
      <div className="flex flex-col gap-4 border-b border-zinc-200 p-6 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-zinc-500">
            Market intelligence
          </p>
          <h2 className="text-2xl font-semibold text-zinc-900">
            Kalshi market explorer
          </h2>
          {lastSync && (
            <p className="mt-1 text-xs text-zinc-500">
              Last synced: {formatLastSync(lastSync)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-2xl bg-zinc-100 px-3 py-1 text-xs font-semibold text-zinc-600">
            {markets.length} {totalMarkets ? `of ${totalMarkets}` : ""} markets
          </span>
          <span className="rounded-2xl bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
            {totalLargeOrders} large orders
          </span>
          <button
            aria-label="refresh markets"
            onClick={() => void onRefresh()}
            className="rounded-full border border-zinc-200 px-3 py-1 text-xs font-semibold uppercase tracking-[0.5em] text-zinc-600 transition hover:border-zinc-400 hover:bg-zinc-50"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="border-b border-zinc-200 p-6 space-y-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
              Sort by:
            </span>
            <div className="flex gap-2">
              {(["volume", "liquidity", "probability"] as SortBy[]).map((sort) => (
                <button
                  key={sort}
                  onClick={() => handleSortChange(sort)}
                  className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                    sortBy === sort
                      ? "bg-zinc-900 text-white"
                      : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
                  }`}
                >
                  {sort.charAt(0).toUpperCase() + sort.slice(1)}
                  {sortBy === sort && (
                    <span className="ml-1">{sortOrder === "desc" ? "↓" : "↑"}</span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {onStatusFilterChange && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                Status:
              </span>
              <div className="flex gap-2">
                {[
                  { value: null, label: "All" },
                  { value: "open", label: "Open" },
                  { value: "closed", label: "Closed" },
                  { value: "settled", label: "Settled" },
                ].map((option) => (
                  <button
                    key={option.label}
                    onClick={() => onStatusFilterChange(option.value)}
                    className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                      statusFilter === option.value
                        ? "bg-zinc-900 text-white"
                        : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <input
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search markets by name, description, or tags..."
          className="w-full rounded-2xl border border-zinc-200 px-4 py-3 text-sm text-zinc-700 transition focus:border-zinc-500 focus:outline-none"
        />
      </div>

      {markets.length === 0 ? (
        <div className="border-t border-zinc-100 bg-zinc-50/50 p-8 text-center">
          <p className="text-sm text-zinc-500">No markets found. Try adjusting your search.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-zinc-200 bg-zinc-50/80 text-left text-xs font-semibold uppercase tracking-[0.2em] text-zinc-600">
              <tr>
                <th className="px-6 py-3">Market</th>
                <th className="px-6 py-3 text-center">Probability</th>
                <th className="px-6 py-3 text-center">Spread</th>
                <th className="px-6 py-3 text-right">Volume</th>
                <th className="px-6 py-3 text-right">Liquidity</th>
                <th className="px-6 py-3 text-center">Trades</th>
                <th className="px-6 py-3 text-center">Large</th>
                <th className="px-6 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {markets.map((market) => {
                const isExpanded = expandedMarketId === market.id;
                const largeOrderCount = market.orders.filter((order) => order.flag === "large").length;
                const totalTraders = market.orders.length;

                return (
                  <Fragment key={market.id}>
                    <tr
                      className={`cursor-pointer transition ${
                        isExpanded
                          ? "bg-zinc-900/5"
                          : "hover:bg-zinc-50"
                      }`}
                      onClick={() => toggleExpand(market.id)}
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="font-semibold text-zinc-900 truncate">{market.name}</p>
                            <div className="mt-1 flex items-center gap-2 text-xs text-zinc-500">
                              <span className="font-mono">{market.id}</span>
                              {market.yesBid !== null && market.yesAsk !== null && (
                                <span className="text-zinc-400">
                                  {market.yesBid}¢ / {market.yesAsk}¢
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <div className="inline-flex flex-col items-center">
                          <div className="flex items-center gap-1">
                            <span className="text-lg font-bold text-zinc-900">
                              {market.probability.toFixed(1)}
                            </span>
                            <span className="text-xs text-zinc-500">%</span>
                          </div>
                          {market.yesBid !== null && market.yesAsk !== null && (
                            <div className="mt-0.5 text-[10px] text-zinc-400">
                              Y: {market.yesBid}¢
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        {market.spread !== null && market.spread !== undefined ? (
                          <span className={`inline-flex items-center gap-0.5 rounded-full px-2 py-1 text-sm font-semibold ${
                            market.spread < 3 ? "bg-emerald-100 text-emerald-700" :
                            market.spread < 10 ? "bg-blue-100 text-blue-700" :
                            "bg-amber-100 text-amber-700"
                          }`}>
                            {market.spread.toFixed(1)}<span className="text-[10px]">¢</span>
                          </span>
                        ) : (
                          <span className="text-sm text-zinc-400">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex flex-col items-end">
                          <span className="font-semibold text-zinc-900">
                            {market.volume.toLocaleString()}
                          </span>
                          {market.tradeCount !== undefined && market.tradeCount > 0 && (
                            <span className="text-xs text-zinc-500">
                              {market.tradeCount} trades
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right">
                        {market.liquidity && market.liquidity > 0 ? (
                          <span className="font-semibold text-blue-700">
                            {market.liquidity.toLocaleString()}
                          </span>
                        ) : (
                          <span className="text-sm text-zinc-400">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-sm font-semibold text-zinc-700">
                          {totalTraders}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        {largeOrderCount > 0 ? (
                          <span className="rounded-full bg-amber-100 px-2.5 py-1 text-sm font-semibold text-amber-700">
                            {largeOrderCount}
                          </span>
                        ) : (
                          <span className="text-sm text-zinc-400">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-col gap-1">
                          <span className={`inline-flex items-center justify-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                            market.status === "open" ? "bg-emerald-100 text-emerald-700" :
                            market.status === "closed" ? "bg-zinc-100 text-zinc-600" :
                            market.status === "settled" ? "bg-blue-100 text-blue-700" :
                            "bg-zinc-100 text-zinc-600"
                          }`}>
                            {market.status || "unknown"}
                          </span>
                        </div>
                      </td>
                    </tr>

                    {isExpanded && (
                      <tr className="bg-zinc-50/50">
                        <td colSpan={6} className="px-6 py-5">
                          <div className="space-y-6">
                            <CandlestickChart ticker={market.id} />

                            {market.orders.length > 0 ? (
                              <div>
                                <p className="mb-3 text-xs font-semibold uppercase tracking-[0.3em] text-zinc-500">
                                  Top traders ({market.orders.length})
                                </p>
                                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                                  {market.orders.map((order) => (
                                    <div
                                      key={order.id}
                                      className="rounded-2xl border border-zinc-200 bg-white p-4 transition hover:border-zinc-300"
                                    >
                                      <div className="flex items-start justify-between">
                                        <div className="flex-1 min-w-0">
                                          <p className="font-semibold text-zinc-900 truncate text-xs font-mono">
                                            {order.owner}
                                          </p>
                                          <p className="mt-1 text-sm text-zinc-600">
                                            {order.size.toLocaleString()} contracts
                                          </p>
                                          {order.tradeCount && order.tradeCount > 1 && (
                                            <p className="mt-0.5 text-xs text-zinc-500">
                                              {order.tradeCount} trades
                                              {order.avgPrice !== undefined && (
                                                <span className="ml-1">
                                                  @ ${order.avgPrice.toFixed(2)}
                                                </span>
                                              )}
                                            </p>
                                          )}
                                          <p className="mt-1 text-xs text-zinc-500">{order.createdAt}</p>
                                        </div>
                                        <div className="flex flex-col items-end gap-1">
                                          <span
                                            className={`rounded-full px-2 py-0.5 text-xs font-semibold ${sidePill[order.side]}`}
                                          >
                                            {order.side}
                                          </span>
                                          {order.flag && (
                                            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
                                              {order.flag}
                                            </span>
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ) : (
                              <p className="text-center text-sm text-zinc-500">
                                No trader data available for this market.
                              </p>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
