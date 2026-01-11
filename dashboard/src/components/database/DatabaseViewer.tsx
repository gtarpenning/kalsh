"use client";

import { DatabaseSnapshot } from "@/types/dashboard";

const alertStyles: Record<"info" | "warning" | "critical", string> = {
  critical: "bg-rose-100 text-rose-700",
  warning: "bg-amber-100 text-amber-700",
  info: "bg-zinc-100 text-zinc-700",
};

interface DatabaseViewerProps {
  snapshots: DatabaseSnapshot[];
}

export default function DatabaseViewer({ snapshots }: DatabaseViewerProps) {
  const leaderboards = snapshots
    .slice()
    .sort((a, b) => b.anomalies - a.anomalies)
    .slice(0, 2);

  const hotTables = snapshots.filter(
    (snap) => snap.alertLevel && snap.alertLevel !== "info"
  );

  return (
    <section className="rounded-3xl border border-zinc-200 bg-white/80 p-6 shadow-sm backdrop-blur">
      <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-zinc-500">
            Database view
          </p>
          <h2 className="text-2xl font-semibold text-zinc-900">
            Storage surface
          </h2>
        </div>
        <p className="text-sm text-zinc-500">Last pulled in real time</p>
      </div>

      <div className="mt-6 grid gap-5 md:grid-cols-[2fr_1fr]">
        <div className="rounded-2xl border border-zinc-100 p-5 shadow-inner">
          <div className="mb-4 flex items-center justify-between text-xs uppercase tracking-widest text-zinc-500">
            <span>Snapshots</span>
            <span>Rows / anomalies</span>
          </div>
          <div className="flex flex-col gap-3">
            {snapshots.map((snapshot) => (
              <article key={snapshot.table} className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-zinc-900">
                    {snapshot.table}
                  </p>
                  <p className="text-xs text-zinc-500">
                    {snapshot.lastUpdated}.
                  </p>
                </div>
                <div className="flex flex-col items-end text-xs text-zinc-500">
                  <span>{snapshot.rows.toLocaleString()} rows</span>
                  <span className="text-zinc-700">
                    {snapshot.anomalies} alerts
                  </span>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-4 rounded-2xl border border-zinc-100 p-5">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.3em] text-zinc-500">
              Anomaly hotspots
            </p>
            {hotTables.length === 0 ? (
              <p className="text-sm text-zinc-600">No elevated tables detected.</p>
            ) : (
              hotTables.map((snapshot) => (
                <div
                  key={snapshot.table}
                  className="rounded-xl border border-zinc-100 p-3 text-sm"
                >
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-zinc-900">
                      {snapshot.table}
                    </p>
                    <span
                      className={`rounded-full px-2 py-1 text-[11px] font-semibold ${snapshot.alertLevel ? alertStyles[snapshot.alertLevel] : alertStyles.info}`}
                    >
                      {snapshot.alertLevel || "info"}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-500">
                    {snapshot.anomalies} alerts since ingestion.
                  </p>
                </div>
              ))
            )}
          </div>

          <div className="border-t border-zinc-100 pt-4">
            <p className="text-xs uppercase tracking-[0.3em] text-zinc-500">
              Leaderboard
            </p>
            <div className="mt-2 space-y-2 text-sm text-zinc-700">
              {leaderboards.map((snapshot) => (
                <p key={snapshot.table}>
                  {snapshot.table} · {snapshot.anomalies} recent concerns
                </p>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
