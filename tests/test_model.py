import numpy as np

from battery.model import Battery, cycles, perfect_foresight, profit, yesterdays_shape

LOSSLESS = Battery(power_mw=1, capacity_mwh=1, round_trip_efficiency=1.0, degradation_gbp_per_mwh=0)


def test_buys_low_sells_high():
    prices = np.array([10, 10, 100, 100])
    actions = perfect_foresight(prices, LOSSLESS)
    assert list(actions) == [1, 1, -1, -1]
    assert profit(prices, actions, LOSSLESS) == 90.0  # 1 MWh bought at 10, sold at 100


def test_never_sells_before_buying():
    prices = np.array([100, 100, 10, 10])
    actions = perfect_foresight(prices, LOSSLESS)
    assert profit(prices, actions, LOSSLESS) == 0.0


def test_skips_spread_too_small_to_cover_losses():
    lossy = Battery(power_mw=1, capacity_mwh=1, round_trip_efficiency=0.8, degradation_gbp_per_mwh=0)
    prices = np.array([100, 100, 110, 110])  # 10% spread, 20% losses
    assert profit(prices, perfect_foresight(prices, lossy), lossy) == 0.0


def test_ends_empty_and_never_overfills():
    prices = np.random.default_rng(0).uniform(0, 200, 500)
    actions = perfect_foresight(prices, Battery())
    charge = np.cumsum(actions)
    assert charge.min() >= 0 and charge.max() <= Battery().levels - 1 and charge[-1] == 0


def test_rule_uses_only_yesterdays_prices():
    day = [10] * 4 + [100] * 4
    prices = np.array(day * 2, dtype=float)
    actions = yesterdays_shape(prices, periods_per_day=8, battery=LOSSLESS)
    assert not actions[:8].any()              # day one has no history, so no trades
    assert profit(prices, actions, LOSSLESS) > 0
    assert cycles(actions, LOSSLESS) == 1.0
