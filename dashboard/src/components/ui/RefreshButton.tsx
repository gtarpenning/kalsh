interface RefreshButtonProps {
  onClick: () => void;
}

export default function RefreshButton({ onClick }: RefreshButtonProps) {
  return (
    <button
      aria-label="refresh dashboard state"
      onClick={onClick}
      className="rounded-full border border-zinc-200 px-3 py-1 text-xs font-semibold uppercase tracking-[0.5em] text-zinc-600 transition hover:border-zinc-400"
    >
      Refresh
    </button>
  );
}
