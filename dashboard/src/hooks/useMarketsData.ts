import { useEffect, useState } from "react";
import type { MarketsResponse, SortBy, SortOrder } from "@/types/dashboard";

interface UseMarketsDataOptions {
  sortBy?: SortBy;
  sortOrder?: SortOrder;
  status?: string | null;
  search?: string;
  limit?: number;
  offset?: number;
}

export function useMarketsData(options: UseMarketsDataOptions = {}) {
  const {
    sortBy = "volume",
    sortOrder = "desc",
    status = null,
    search = "",
    limit = 10,
    offset = 0,
  } = options;

  const [data, setData] = useState<MarketsResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const fetchMarkets = async () => {
    setLoading(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString(),
        sort_by: sortBy,
        sort_order: sortOrder,
      });

      if (status) params.append("status", status);
      if (search) params.append("search", search);

      const res = await fetch(`${apiUrl}/api/kalshi/markets?${params.toString()}`, {
        cache: "no-store",
      });

      if (!res.ok) {
        throw new Error("Failed to fetch markets");
      }

      const responseData: MarketsResponse = await res.json();
      setData(responseData);
      setError("");
    } catch (err) {
      console.error(err);
      setError("Unable to reach the Python API. Make sure it's running on port 8000.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchMarkets();
  }, [sortBy, sortOrder, status, search, limit, offset]);

  return { data, error, loading, refetch: fetchMarkets };
}
