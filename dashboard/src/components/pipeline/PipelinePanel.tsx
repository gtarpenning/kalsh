"use client";

import { PipelineRun } from "@/types/dashboard";

const statusStyles: Record<PipelineRun["status"], string> = {
  idle: "bg-zinc-100 text-zinc-800",
  running: "bg-amber-100 text-amber-800",
  healthy: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-800",
};

interface PipelinePanelProps {
  runs: PipelineRun[];
  onStart: () => Promise<void>;
  isStarting: boolean;
  lastRefresh?: string;
}

export default function PipelinePanel({
  runs,
  onStart,
  isStarting,
  lastRefresh,
}: PipelinePanelProps) {
  return (
    <section className="rounded-3xl border border-zinc-200 bg-white/80 p-6 shadow-sm backdrop-blur">
      <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-zinc-500">
            Pipeline control
          </p>
          <h2 className="text-2xl font-semibold text-zinc-900">
            Anomaly evaluation
          </h2>
        </div>
        <p className="text-sm text-zinc-500">
          Synced {lastRefresh ?? "just now"}
        </p>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {runs.map((run) => (
          <article
            key={run.id}
            className="rounded-2xl border border-zinc-100 p-4 shadow-inner transition hover:border-zinc-300"
          >
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
                {run.label}
              </p>
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${statusStyles[run.status]}`}
              >
                {run.status}
              </span>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-zinc-600">
              {run.message}
            </p>
            <div className="mt-4 flex items-center justify-between text-xs text-zinc-500">
              <span>Last run {run.lastRun}</span>
              <span>{run.duration}</span>
            </div>
          </article>
        ))}
      </div>

      <div className="mt-6 border-t border-zinc-100 pt-5">
        <button
          className="inline-flex items-center justify-center rounded-2xl bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-500"
          onClick={() => void onStart()}
          disabled={isStarting}
        >
          {isStarting ? "Running pipeline..." : "Run pipeline"}
        </button>
      </div>
    </section>
  );
}
