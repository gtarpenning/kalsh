"""Feature builder and rule filter for Kalsh inspector tests."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class Trade:
    """Represents a normalized trade event."""

    market_id: str
    user_id: str
    quantity: int


@dataclass(frozen=True)
class UserMetrics:
    """Per-user totals for a single window."""

    user_id: str
    user_volume: int
    user_trade_count: int
    net_shares: int


@dataclass(frozen=True)
class WindowFeature:
    """Window-level aggregates spanning a fixed number of trades."""

    market_id: str
    window_id: int
    total_volume: int
    total_trade_count: int
    user_metrics: Tuple[UserMetrics, ...]


class FeatureBuilder:
    """Builds sliding-window aggregates from trade tapes."""

    def __init__(self, window_size: int):
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self.window_size = window_size

    def build(self, trades: Sequence[Trade]) -> List[WindowFeature]:
        """Return features derived from overlapping windows of trades."""

        if not trades:
            return []

        windows: List[WindowFeature] = []
        max_start = len(trades) - self.window_size
        for window_id in range(max_start + 1):
            window_trades = trades[window_id : window_id + self.window_size]
            window = self._aggregate_window(window_id, window_trades)
            windows.append(window)
        return windows

    def _aggregate_window(
        self, window_id: int, window_trades: Sequence[Trade]
    ) -> WindowFeature:
        if not window_trades:
            raise ValueError("window_trades must contain at least one trade")

        total_volume = 0
        total_trade_count = len(window_trades)
        user_stats: Dict[str, Tuple[int, int, int]] = {}

        for trade in window_trades:
            abs_size = abs(trade.quantity)
            total_volume += abs_size
            user_volume, trade_count, net_shares = user_stats.get(
                trade.user_id, (0, 0, 0)
            )
            user_volume += abs_size
            trade_count += 1
            net_shares += trade.quantity
            user_stats[trade.user_id] = (user_volume, trade_count, net_shares)

        metrics = tuple(
            UserMetrics(
                user_id=user,
                user_volume=volume,
                user_trade_count=trade_count,
                net_shares=net,
            )
            for user, (volume, trade_count, net) in sorted(user_stats.items())
        )

        return WindowFeature(
            market_id=window_trades[0].market_id,
            window_id=window_id,
            total_volume=total_volume,
            total_trade_count=total_trade_count,
            user_metrics=metrics,
        )


class RuleFilter:
    """Filters windows for dominance and sudden-growth cases."""

    def __init__(self, dominance_threshold: float = 0.75, sudden_growth_threshold: int = 4):
        if not 0.0 < dominance_threshold <= 1.0:
            raise ValueError("dominance_threshold must be between 0 and 1")
        if sudden_growth_threshold < 1:
            raise ValueError("sudden_growth_threshold must be positive")

        self._dominance_threshold = Fraction(dominance_threshold).limit_denominator()
        self._sudden_growth_threshold = sudden_growth_threshold

    def apply(self, windows: Iterable[WindowFeature]) -> List[Mapping[str, object]]:
        """Return cases that match either dominance or sudden-growth rules."""

        cases: List[Mapping[str, object]] = []
        previous_nets: Dict[str, int] = {}
        for window in windows:
            cases.extend(self._dominance_cases(window))
            cases.extend(self._growth_cases(window, previous_nets))
            for metric in window.user_metrics:
                previous_nets[metric.user_id] = metric.net_shares
        return cases

    def _dominance_cases(self, window: WindowFeature) -> List[Mapping[str, object]]:
        if window.total_volume == 0:
            return []

        cases: List[Mapping[str, object]] = []
        for metric in window.user_metrics:
            share = Fraction(metric.user_volume, window.total_volume)
            if share > self._dominance_threshold:
                reason = {
                    "rule": "dominance",
                    "share": (share.numerator, share.denominator),
                    "window_id": window.window_id,
                }
                cases.append(
                    {
                        "market_id": window.market_id,
                        "user_id": metric.user_id,
                        "window_id": window.window_id,
                        "rule": reason["rule"],
                        "reason": reason,
                    }
                )
        return cases

    def _growth_cases(
        self, window: WindowFeature, previous_nets: Mapping[str, int]
    ) -> List[Mapping[str, object]]:
        cases: List[Mapping[str, object]] = []
        for metric in window.user_metrics:
            prev = previous_nets.get(metric.user_id)
            if prev is None:
                continue
            growth = metric.net_shares - prev
            if growth >= self._sudden_growth_threshold:
                reason = {
                    "rule": "sudden_growth",
                    "growth": growth,
                    "window_id": window.window_id,
                }
                cases.append(
                    {
                        "market_id": window.market_id,
                        "user_id": metric.user_id,
                        "window_id": window.window_id,
                        "rule": reason["rule"],
                        "reason": reason,
                    }
                )
        return cases

