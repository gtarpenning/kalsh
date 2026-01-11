"use client";

import { useState } from "react";
import DatabaseViewer from "@/components/database/DatabaseViewer";
import MarketExplorer from "@/components/markets/MarketExplorer";
import PipelinePanel from "@/components/pipeline/PipelinePanel";
import DashboardHeader from "@/components/ui/DashboardHeader";
import ErrorBanner from "@/components/ui/ErrorBanner";
import { useDashboardData } from "@/hooks/useDashboardData";
import { useMarketsData } from "@/hooks/useMarketsData";
import { usePipeline } from "@/hooks/usePipeline";
import { useMarketSelection } from "@/hooks/useMarketSelection";
import type { SortBy, SortOrder } from "@/types/dashboard";

export default function Home() {
  const { payload, error: dataError, lastRefresh, refreshData } = useDashboardData();
  const { isStarting, error: pipelineError, triggerPipeline } = usePipeline(refreshData);
  
  const [sortBy, setSortBy] = useState<SortBy>("volume");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const { data: marketsData, error: marketsError, refetch: refetchMarkets } = useMarketsData({
    sortBy,
    sortOrder,
    status: statusFilter,
    search,
    limit: 10,
  });

  const markets = marketsData?.markets || [];
  const { setSelectedMarketId } = useMarketSelection(markets);

  const handleSortChange = (newSortBy: SortBy, newSortOrder: SortOrder) => {
    setSortBy(newSortBy);
    setSortOrder(newSortOrder);
  };

  const handleRefresh = async () => {
    await Promise.all([refreshData(), refetchMarkets()]);
  };

  const totalAnomalies = payload.databaseSnapshots.reduce(
    (total, snapshot) => total + snapshot.anomalies,
    0
  );
  const totalLargeOrders = markets.reduce(
    (total, market) =>
      total + market.orders.filter((order) => order.flag === "large").length,
    0
  );
  const error = dataError || pipelineError || marketsError;

  return (
    <main className="min-h-screen bg-gradient-to-b from-zinc-50 via-white to-zinc-50">
      <div className="mx-auto max-w-6xl space-y-6 px-4 py-12 sm:px-6 lg:px-8">
        <DashboardHeader
          totalAnomalies={totalAnomalies}
          totalLargeOrders={totalLargeOrders}
          onRefresh={() => void refreshData()}
        />

        <ErrorBanner message={error} />

        <MarketExplorer
          markets={markets}
          onSelectMarket={setSelectedMarketId}
          search={search}
          onSearchChange={setSearch}
          onRefresh={handleRefresh}
          sortBy={sortBy}
          sortOrder={sortOrder}
          onSortChange={handleSortChange}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          lastSync={marketsData?.last_sync}
          totalMarkets={marketsData?.total}
        />

        <DatabaseViewer snapshots={payload.databaseSnapshots} />

        <PipelinePanel
          runs={payload.pipelineRuns}
          lastRefresh={lastRefresh}
          isStarting={isStarting}
          onStart={triggerPipeline}
        />
      </div>
    </main>
  );
}
