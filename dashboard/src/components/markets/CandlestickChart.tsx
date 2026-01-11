"use client";

import { useEffect, useState } from "react";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";

interface Candlestick {
  timestamp: number;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  open_interest: number | null;
}

interface CandlestickChartProps {
  ticker: string;
}

export default function CandlestickChart({ ticker }: CandlestickChartProps) {
  const [candlesticks, setCandlesticks] = useState<Candlestick[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchCandlesticks = async () => {
      setLoading(true);
      setError("");
      
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const now = Math.floor(Date.now() / 1000);
        const sevenDaysAgo = now - 7 * 24 * 60 * 60;
        
        const res = await fetch(
          `${apiUrl}/api/kalshi/candlesticks/${ticker}?start_ts=${sevenDaysAgo}&end_ts=${now}&period_interval=1440`,
          { cache: "no-store" }
        );
        
        if (!res.ok) {
          throw new Error("Failed to fetch candlesticks");
        }
        
        const data = await res.json();
        
        if (data.error) {
          setError(`API Error: ${data.error}`);
          setCandlesticks([]);
        } else {
          setCandlesticks(data.candlesticks || []);
        }
      } catch (err) {
        console.error(err);
        setError("Unable to load candlestick data");
      } finally {
        setLoading(false);
      }
    };

    if (ticker) {
      void fetchCandlesticks();
    }
  }, [ticker]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-zinc-200 bg-white/80 p-8 text-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-zinc-300 border-r-transparent"></div>
        <p className="mt-3 text-sm text-zinc-500">Loading candlestick data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50/50 p-6">
        <p className="text-sm text-rose-600">{error}</p>
      </div>
    );
  }

  if (candlesticks.length === 0) {
    return (
      <div className="rounded-2xl border border-zinc-200 bg-zinc-50/50 p-8 text-center">
        <p className="text-sm text-zinc-500">
          No candlestick data available for this market
        </p>
        <p className="mt-2 text-xs text-zinc-400">
          This market may be too new or have insufficient trading history
        </p>
      </div>
    );
  }

  const chartData = candlesticks
    .filter((c) => c.close !== null)
    .map((c) => ({
      time: new Date(c.timestamp * 1000).toLocaleDateString(),
      price: c.close,
      volume: c.volume || 0,
    }));

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-zinc-200 bg-white/80 p-6">
        <div className="mb-4">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-zinc-500">
            Price history (7 days)
          </p>
          <h3 className="mt-1 text-lg font-semibold text-zinc-900">Market Candlesticks</h3>
        </div>
        
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 12, fill: "#71717a" }}
              stroke="#d4d4d8"
            />
            <YAxis
              tick={{ fontSize: 12, fill: "#71717a" }}
              stroke="#d4d4d8"
              domain={[0, 100]}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "white",
                border: "1px solid #e5e7eb",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value: number | undefined) => value !== undefined ? [`${value}¢`, "Price"] : ["", ""]}
            />
            <Area
              type="monotone"
              dataKey="price"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#colorPrice)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="rounded-2xl border border-zinc-200 bg-white/80 p-6">
        <div className="mb-4">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-zinc-500">
            Trading activity
          </p>
          <h3 className="mt-1 text-lg font-semibold text-zinc-900">Volume</h3>
        </div>
        
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="colorVolume" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 12, fill: "#71717a" }}
              stroke="#d4d4d8"
            />
            <YAxis
              tick={{ fontSize: 12, fill: "#71717a" }}
              stroke="#d4d4d8"
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "white",
                border: "1px solid #e5e7eb",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value: number | undefined) => value !== undefined ? [value.toLocaleString(), "Volume"] : ["", ""]}
            />
            <Area
              type="monotone"
              dataKey="volume"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#colorVolume)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
