"""The battery, and two ways to trade it.

1. Perfect foresight: the most money it could possibly have made, knowing every
   future price. Solved exactly with dynamic programming over the state of charge.
2. Yesterday's shape: a realistic rule with no look-ahead. Charge in the
   half-hours that were cheapest yesterday, discharge in the ones that were dearest.

The gap between them is what a better price forecast is worth.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Battery:
    power_mw: float = 1.0               # maximum charge or discharge rate
    capacity_mwh: float = 2.0           # a "2-hour" battery
    round_trip_efficiency: float = 0.88  # share of energy bought that can be sold back
    degradation_gbp_per_mwh: float = 5.0  # wear cost charged on every MWh discharged

    @property
    def step_mwh(self) -> float:
        return self.power_mw * 0.5       # energy moved in one half-hour at full power

    @property
    def levels(self) -> int:
        return int(round(self.capacity_mwh / self.step_mwh)) + 1


def perfect_foresight(prices: np.ndarray, battery: Battery) -> np.ndarray:
    """Best possible action each half-hour: +1 charge, -1 discharge, 0 idle.

    Dynamic programming backwards in time over discrete state-of-charge levels,
    starting and ending empty. With full-power steps this is exact for the model.
    """
    n, levels, step = len(prices), battery.levels, battery.step_mwh
    buy_cost = prices * step / battery.round_trip_efficiency      # pay for losses when charging
    sell_value = prices * step - battery.degradation_gbp_per_mwh * step

    value = np.full(levels, -np.inf)
    value[0] = 0.0                                                # must finish empty
    choice = np.zeros((n, levels), dtype=np.int8)

    for t in range(n - 1, -1, -1):
        new = np.full(levels, -np.inf)
        for s in range(levels):
            options = {0: value[s]}
            if s + 1 < levels:
                options[1] = value[s + 1] - buy_cost[t]
            if s > 0:
                options[-1] = value[s - 1] + sell_value[t]
            best = max(options, key=options.get)
            new[s], choice[t, s] = options[best], best
        value = new

    actions, s = np.zeros(n, dtype=np.int8), 0                    # start empty
    for t in range(n):
        actions[t] = choice[t, s]
        s += actions[t]
    return actions


def yesterdays_shape(prices: np.ndarray, periods_per_day: int, battery: Battery) -> np.ndarray:
    """Realistic rule using only past prices: one full cycle a day.

    Look at yesterday and find the charging block and the later discharging block
    with the widest spread. If that spread would have covered losses and wear,
    trade the same two blocks today.
    """
    steps = battery.levels - 1                                    # half-hours needed to fill
    actions = np.zeros(len(prices), dtype=np.int8)
    for d in range(1, len(prices) // periods_per_day):
        y = prices[(d - 1) * periods_per_day: d * periods_per_day]
        block = np.convolve(y, np.ones(steps) / steps, mode="valid")   # average price of each block
        best, best_gain = None, 0.0
        for i in range(len(block)):
            later = block[i + steps:]
            if not len(later):
                break
            j = i + steps + int(np.argmax(later))
            gain = block[j] - battery.degradation_gbp_per_mwh - block[i] / battery.round_trip_efficiency
            if gain > best_gain:
                best, best_gain = (i, j), gain
        if best is None:                                          # no spread worth trading
            continue
        today, (i, j) = d * periods_per_day, best
        actions[today + i: today + i + steps] = 1
        actions[today + j: today + j + steps] = -1
    return actions


def profit(prices: np.ndarray, actions: np.ndarray, battery: Battery) -> float:
    step = battery.step_mwh
    bought = (actions == 1) * prices * step / battery.round_trip_efficiency
    sold = (actions == -1) * (prices * step - battery.degradation_gbp_per_mwh * step)
    return float(sold.sum() - bought.sum())


def cycles(actions: np.ndarray, battery: Battery) -> float:
    return float((actions == -1).sum() * battery.step_mwh / battery.capacity_mwh)
