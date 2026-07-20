# spark/features.py
# Plain-Python versions of feature formulas — unit test these before porting to Spark windows.

import statistics

def price_velocity(prices: list[float], window_seconds: float) -> float:
    """
    Feature 1: rate of change of price over a window.
    prices: ordered list of prices within the window (oldest -> newest)
    window_seconds: duration of the window in seconds
    Returns: (last_price - first_price) / window_seconds
    """
    if len(prices) < 2 or window_seconds <= 0:
        return 0.0
    return (prices[-1] - prices[0]) / window_seconds


def volume_surge_zscore(current_volume: float, historical_volumes: list[float]) -> float:
    """
    Feature 2: z-score of current volume vs a rolling historical window (e.g. 1hr of 1-min buckets).
    current_volume: volume in the most recent bucket
    historical_volumes: prior bucket volumes (not including current)
    Returns: z-score; 0.0 if insufficient history or zero variance
    """
    if len(historical_volumes) < 2:
        return 0.0
    mean = statistics.mean(historical_volumes)
    stdev = statistics.stdev(historical_volumes)
    if stdev == 0:
        return 0.0
    return (current_volume - mean) / stdev