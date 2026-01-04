from typing import List

from kalsh.rules import FeatureBuilder, RuleFilter, Trade


def _dominance_trades() -> List[Trade]:
    return [
        Trade(market_id="mkt", user_id="user_top", quantity=8),
        Trade(market_id="mkt", user_id="user_other", quantity=1),
        Trade(market_id="mkt", user_id="user_top", quantity=2),
        Trade(market_id="mkt", user_id="user_other", quantity=1),
        Trade(market_id="mkt", user_id="user_top", quantity=1),
    ]


def _balanced_trades() -> List[Trade]:
    return [
        Trade(market_id="mkt", user_id="u1", quantity=1),
        Trade(market_id="mkt", user_id="u2", quantity=1),
        Trade(market_id="mkt", user_id="u3", quantity=1),
        Trade(market_id="mkt", user_id="u1", quantity=1),
        Trade(market_id="mkt", user_id="u2", quantity=1),
        Trade(market_id="mkt", user_id="u3", quantity=1),
    ]


def _growth_trades() -> List[Trade]:
    return [
        Trade(market_id="mkt", user_id="burst", quantity=1),
        Trade(market_id="mkt", user_id="burst", quantity=1),
        Trade(market_id="mkt", user_id="burst", quantity=1),
        Trade(market_id="mkt", user_id="burst", quantity=5),
        Trade(market_id="mkt", user_id="burst", quantity=5),
    ]


def test_dominance_rule_detects_single_user() -> None:
    builder = FeatureBuilder(window_size=3)
    windows = builder.build(_dominance_trades())
    cases = RuleFilter(dominance_threshold=0.75).apply(windows)

    dominance_cases = [case for case in cases if case["rule"] == "dominance"]
    assert dominance_cases, "Expected a dominance case when one user controls most volume"

    case = dominance_cases[0]
    assert case["market_id"] == "mkt"
    assert case["user_id"] == "user_top"
    assert case["reason"] == {"rule": "dominance", "share": (10, 11), "window_id": 0}


def test_dominance_rule_ignores_even_distribution() -> None:
    builder = FeatureBuilder(window_size=3)
    windows = builder.build(_balanced_trades())
    cases = RuleFilter(dominance_threshold=0.75).apply(windows)

    assert not any(case["rule"] == "dominance" for case in cases)


def test_sudden_growth_rule_detects_burst() -> None:
    builder = FeatureBuilder(window_size=3)
    windows = builder.build(_growth_trades())
    cases = RuleFilter(sudden_growth_threshold=4).apply(windows)

    growth_cases = [case for case in cases if case["rule"] == "sudden_growth"]
    assert growth_cases, "Expected sudden growth case for burst window"

    reason = growth_cases[0]["reason"]
    assert reason == {"rule": "sudden_growth", "growth": 4, "window_id": 1}

