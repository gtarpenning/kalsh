import { useEffect, useState } from "react";
import type { DashboardPayload } from "@/types/dashboard";

const initialPayload: DashboardPayload = {
  pipelineRuns: [],
  databaseSnapshots: [],
  markets: [],
};

export function useDashboardData() {
  const [payload, setPayload] = useState<DashboardPayload>(initialPayload);
  const [error, setError] = useState("");
  const [lastRefresh, setLastRefresh] = useState("just now");

  const refreshData = async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const res = await fetch(`${apiUrl}/api/kalshi/dashboard-data`, {
        cache: "no-store",
      });
      if (!res.ok) {
        throw new Error("failed to fetch dashboard data");
      }
      const data: DashboardPayload = await res.json();
      setPayload(data);
      setError("");
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (err) {
      console.error(err);
      setError("Unable to reach the Python API. Make sure it's running on port 8000.");
    }
  };

  useEffect(() => {
    void refreshData();
  }, []);

  return { payload, error, lastRefresh, refreshData };
}
