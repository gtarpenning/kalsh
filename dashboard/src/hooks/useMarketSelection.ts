import { useEffect, useState } from "react";
import type { Market } from "@/types/dashboard";

export function useMarketSelection(markets: Market[]) {
  const [selectedMarketId, setSelectedMarketId] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedMarketId && markets.length) {
      setSelectedMarketId(markets[0].id);
    }
  }, [markets, selectedMarketId]);

  return { selectedMarketId, setSelectedMarketId };
}
