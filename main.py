"""How much could a battery have earned trading GB power prices?

    python main.py                       # the last 12 full months
    python main.py --start 2025-01-01 --end 2026-01-01
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from battery.fetch import load_prices
from battery.model import Battery, cycles, perfect_foresight, profit, yesterdays_shape

ROOT = Path(__file__).parent


def main() -> None:
    first_of_month = date.today().replace(day=1)
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, default=first_of_month.replace(year=first_of_month.year - 1))
    parser.add_argument("--end", type=date.fromisoformat, default=first_of_month)
    args = parser.parse_args()

    print(f"Loading GB prices {args.start} to {args.end}…")
    prices = load_prices(args.start, args.end, ROOT / "data" / "prices.csv")
    p = prices["price"].to_numpy()
    days = (args.end - args.start).days
    battery = Battery()

    best = perfect_foresight(p, battery)
    rule = yesterdays_shape(p, periods_per_day=48, battery=battery)

    scale = 365 / days / battery.power_mw          # annualised £ per MW of battery
    rows = [("Perfect foresight (ceiling)", best), ("Yesterday's shape (realistic)", rule)]
    print(f"\n{battery.power_mw:g} MW / {battery.capacity_mwh:g} MWh battery, "
          f"{battery.round_trip_efficiency:.0%} round-trip efficiency, £{battery.degradation_gbp_per_mwh:g}/MWh wear cost")
    print(f"{len(p):,} half-hours, average price £{p.mean():.2f}/MWh\n")
    for name, actions in rows:
        print(f"  {name:31s} £{profit(p, actions, battery) * scale:>9,.0f} per MW per year   "
              f"{cycles(actions, battery) / days:.2f} cycles/day")
    capture = profit(p, rule, battery) / profit(p, best, battery)
    print(f"\n  The simple rule captures {capture:.0%} of the perfect-foresight ceiling.")

    # Monthly chart
    prices = prices.assign(best=best, rule=rule)
    prices["month"] = prices["start_time"].dt.strftime("%Y-%m")
    monthly = prices.groupby("month").apply(
        lambda g: (profit(g["price"].to_numpy(), g["best"].to_numpy(), battery),
                   profit(g["price"].to_numpy(), g["rule"].to_numpy(), battery)),
        include_groups=False)
    months = list(monthly.index)
    x = np.arange(len(months))
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(x - 0.2, [v[0] / 1000 for v in monthly], 0.4, label="Perfect foresight", color="#2457C5")
    ax.bar(x + 0.2, [v[1] / 1000 for v in monthly], 0.4, label="Yesterday's shape", color="#B5651D")
    ax.set_xticks(x, months, rotation=45, ha="right")
    ax.set_ylabel("£ thousand per MW")
    ax.set_title("Monthly arbitrage revenue, 1 MW / 2 MWh battery, GB market index price")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    (ROOT / "output").mkdir(exist_ok=True)
    fig.savefig(ROOT / "output" / "monthly_revenue.png", dpi=150)
    print("\n  Chart saved to output/monthly_revenue.png")


if __name__ == "__main__":
    main()
