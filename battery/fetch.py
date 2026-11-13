"""Download real GB half-hourly wholesale power prices from Elexon.

Source: Elexon Insights API, Market Index Data (provider APXMIDP), in £/MWh.
One request per day keeps each call small; results are cached in data/prices.csv
so the download only happens once.
"""

import json
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

URL = ("https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index"
       "?from={start}T00:00Z&to={end}T00:00Z&dataProviders=APXMIDP&format=json")


def _download_day(day: date) -> list[dict]:
    url = URL.format(start=day.isoformat(), end=(day + timedelta(days=1)).isoformat())
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)["data"]


def load_prices(start: date, end: date, cache: Path) -> pd.DataFrame:
    """Half-hourly prices from start (inclusive) to end (exclusive), sorted in time order."""
    if cache.exists():
        prices = pd.read_csv(cache, parse_dates=["start_time"])
        if prices["start_time"].min().date() <= start and prices["start_time"].max().date() >= end - timedelta(days=1):
            return _window(prices, start, end)

    rows, day = [], start
    while day < end:
        rows.extend(_download_day(day))
        print(f"\r  downloaded {day}", end="", flush=True)
        day += timedelta(days=1)
        time.sleep(0.1)  # be polite to the public API
    print()

    prices = (pd.DataFrame(rows)
              .rename(columns={"startTime": "start_time"})
              [["start_time", "price", "volume"]])
    prices["start_time"] = pd.to_datetime(prices["start_time"])
    # Elexon can repeat a period at a day boundary, and some periods report price 0 with no volume.
    prices = (prices.drop_duplicates("start_time")
                    .query("volume > 0")
                    .sort_values("start_time")
                    .reset_index(drop=True))
    cache.parent.mkdir(exist_ok=True)
    prices.to_csv(cache, index=False)
    return _window(prices, start, end)


def _window(prices: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    t = prices["start_time"].dt.tz_localize(None) if prices["start_time"].dt.tz else prices["start_time"]
    return prices[(t >= pd.Timestamp(start)) & (t < pd.Timestamp(end))].reset_index(drop=True)
