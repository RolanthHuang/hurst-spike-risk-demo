"""Numerical primitives used by the public demo.

The code intentionally accepts only already-normalized, pseudonymized events.
It does not contain production table names, credentials, or fixed file paths.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np


def hurst_dfa(
    values: Iterable[float],
    min_scale: int = 4,
    max_scale: int | None = None,
    n_scales: int = 10,
) -> float:
    """Estimate the Hurst exponent with first-order DFA.

    The centered series is first integrated into a profile. A line is fitted
    and removed in each non-overlapping window, then log(F(s)) is regressed on
    log(s). NaN is returned when the series does not contain enough usable
    scales or variation.
    """

    x = np.asarray(list(values), dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 16 or np.allclose(x, x[0]):
        return float("nan")

    profile = np.cumsum(x - np.mean(x))
    upper = min(x.size // 4, max_scale or x.size // 4)
    if upper <= min_scale:
        return float("nan")

    scales = np.unique(
        np.floor(np.geomspace(min_scale, upper, num=n_scales)).astype(int)
    )
    usable_scales: list[int] = []
    fluctuations: list[float] = []

    for scale in scales:
        segment_count = x.size // scale
        if segment_count < 2:
            continue

        residual_variances: list[float] = []
        time_index = np.arange(scale, dtype=float)
        for start in range(0, segment_count * scale, scale):
            segment = profile[start : start + scale]
            slope, intercept = np.polyfit(time_index, segment, 1)
            trend = slope * time_index + intercept
            residual_variances.append(float(np.mean((segment - trend) ** 2)))

        fluctuation = float(np.sqrt(np.mean(residual_variances)))
        if fluctuation > 0 and np.isfinite(fluctuation):
            usable_scales.append(int(scale))
            fluctuations.append(fluctuation)

    if len(usable_scales) < 3:
        return float("nan")

    exponent, _ = np.polyfit(
        np.log(np.asarray(usable_scales, dtype=float)),
        np.log(np.asarray(fluctuations, dtype=float)),
        1,
    )
    return float(exponent)


def fractal_dimension_from_hurst(hurst: float) -> float:
    """Return D = 2 - H for a self-affine one-dimensional graph."""

    return float(2.0 - hurst)


def _squared_loss(values: list[float], center: float) -> float:
    if not values:
        return 0.0
    return float(np.mean([(value - center) ** 2 for value in values]))


def recursive_tri_partition_baseline(
    history: Iterable[float],
    *,
    max_window: int = 25,
    tail_fraction: float = 0.10,
    min_tail_size: int = 5,
) -> float:
    """Estimate a local count regime using recursive three-way partitioning.

    This is a stabilized, documented version of the exploratory estimator. It
    minimizes within-regime squared error around the minimum, global mean, and
    maximum. The upper two regimes are recursively inspected only while they
    remain sufficiently large. The mean of the most populated final regime is
    used as the baseline.
    """

    values = [float(value) for value in history if np.isfinite(value)]
    values = values[-max_window:]
    if not values:
        return 0.0
    if len(values) < 6 or np.allclose(values, values[0]):
        return float(np.mean(values))

    original_size = len(values)

    def recurse(current: list[float], depth: int = 0) -> float:
        if len(current) < 6 or depth >= 20:
            return float(np.mean(current))

        ordered = sorted(current)
        minimum, maximum = ordered[0], ordered[-1]
        core = ordered[1:-1]
        if len(core) < 3:
            return float(np.mean(current))

        global_mean = float(np.mean(current))
        best: tuple[float, int, int] | None = None
        for first_end in range(1, len(core) - 1):
            for second_end in range(first_end + 1, len(core)):
                low_core = core[:first_end]
                middle = core[first_end:second_end]
                high_core = core[second_end:]
                loss = (
                    _squared_loss(low_core, minimum)
                    + _squared_loss(middle, global_mean)
                    + _squared_loss(high_core, maximum)
                )
                candidate = (loss, first_end, second_end)
                if best is None or candidate < best:
                    best = candidate

        if best is None:
            return float(np.mean(current))

        _, first_end, second_end = best
        regimes = [
            [minimum] + core[:first_end],
            core[first_end:second_end],
            core[second_end:] + [maximum],
        ]
        upper_tail = regimes[1] + regimes[2]
        if (
            len(upper_tail) > min_tail_size
            and len(upper_tail) / original_size > tail_fraction
            and len(upper_tail) < len(current)
        ):
            return recurse(upper_tail, depth + 1)

        dominant = max(regimes, key=lambda regime: (len(regime), np.mean(regime)))
        return float(np.mean(dominant))

    return recurse(values)


def spike_flags(
    counts: Iterable[float],
    *,
    jump_ratio: float = 3.0,
    target_window: int = 25,
    warmup: int = 5,
    min_spike_count: int = 4,
) -> tuple[np.ndarray, np.ndarray]:
    """Flag delta-like jumps relative to the preceding local regime."""

    series = np.asarray(list(counts), dtype=float)
    flags = np.zeros(series.size, dtype=bool)
    baselines = np.full(series.size, np.nan, dtype=float)

    for index in range(warmup, series.size):
        history = series[max(0, index - target_window) : index]
        baseline = recursive_tri_partition_baseline(
            history, max_window=target_window
        )
        baselines[index] = baseline
        effective_baseline = max(baseline, 1.0)
        flags[index] = bool(
            series[index] >= min_spike_count
            and series[index] > jump_ratio * effective_baseline
        )

    return flags, baselines

