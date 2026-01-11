import RefreshButton from "./RefreshButton";

interface DashboardHeaderProps {
  totalAnomalies: number;
  totalLargeOrders: number;
  onRefresh: () => void;
}

export default function DashboardHeader({
  totalAnomalies,
  totalLargeOrders,
  onRefresh,
}: DashboardHeaderProps) {
  return (
    <header className="space-y-3">
      <p className="text-xs font-semibold uppercase tracking-[0.6em] text-zinc-400">
        Kalshi anomaly cockpit
      </p>
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <h1 className="text-4xl font-bold text-zinc-900">
          Investigate anomalies from one screen
        </h1>
        <div className="flex items-center gap-3 text-sm text-zinc-500">
          <span>{totalAnomalies} anomaly snapshots</span>
          <span>·</span>
          <span>{totalLargeOrders} large orders</span>
          <RefreshButton onClick={onRefresh} />
        </div>
      </div>
      <p className="max-w-3xl text-sm leading-relaxed text-zinc-600">
        Run the pipeline to ingest markets and trades, then view the results
        in the database and market explorer.
      </p>
    </header>
  );
}
