import numpy as np
import pandas as pd
import pytest

from bus_check.analysis.headway_analysis import (
    compute_headway_metrics,
    compute_headways_from_arrivals,
    detect_stop_arrivals,
)


# --- compute_headway_metrics ---


def test_compute_headway_metrics_keys(sample_headways):
    metrics = compute_headway_metrics(sample_headways)
    expected_keys = {
        "mean_headway",
        "median_headway",
        "std_headway",
        "cv_headway",
        "pct_under_10",
        "pct_under_12",
        "pct_over_15",
        "pct_over_20",
        "max_headway",
        "bunching_rate",
        "excess_wait_time",
    }
    assert set(metrics.keys()) == expected_keys


def test_mean_headway(sample_headways):
    metrics = compute_headway_metrics(sample_headways)
    assert metrics["mean_headway"] == pytest.approx(sample_headways.mean())


def test_median_headway(sample_headways):
    metrics = compute_headway_metrics(sample_headways)
    assert metrics["median_headway"] == pytest.approx(sample_headways.median())


def test_std_headway(sample_headways):
    metrics = compute_headway_metrics(sample_headways)
    assert metrics["std_headway"] == pytest.approx(sample_headways.std())


def test_cv_headway(sample_headways):
    metrics = compute_headway_metrics(sample_headways)
    expected_cv = sample_headways.std() / sample_headways.mean()
    assert metrics["cv_headway"] == pytest.approx(expected_cv)


def test_pct_under_10(sample_headways):
    """% of headways <= 10 min."""
    metrics = compute_headway_metrics(sample_headways)
    count = (sample_headways <= 10).sum()
    expected = count / len(sample_headways) * 100
    assert metrics["pct_under_10"] == pytest.approx(expected)


def test_pct_under_12(sample_headways):
    """% of headways <= 12 min (grace period)."""
    metrics = compute_headway_metrics(sample_headways)
    count = (sample_headways <= 12).sum()
    expected = count / len(sample_headways) * 100
    assert metrics["pct_under_12"] == pytest.approx(expected)


def test_pct_over_15(sample_headways):
    """% of headways > 15 min."""
    metrics = compute_headway_metrics(sample_headways)
    count = (sample_headways > 15).sum()
    expected = count / len(sample_headways) * 100
    assert metrics["pct_over_15"] == pytest.approx(expected)


def test_pct_over_20(sample_headways):
    """% of headways > 20 min."""
    metrics = compute_headway_metrics(sample_headways)
    count = (sample_headways > 20).sum()
    expected = count / len(sample_headways) * 100
    assert metrics["pct_over_20"] == pytest.approx(expected)


def test_max_headway(sample_headways):
    metrics = compute_headway_metrics(sample_headways)
    assert metrics["max_headway"] == 18


def test_bunching_rate(sample_headways):
    """% of headways < 2 min."""
    metrics = compute_headway_metrics(sample_headways)
    # sample_headways has one value of 2 — bunching is STRICTLY < 2
    count = (sample_headways < 2).sum()
    expected = count / len(sample_headways) * 100
    assert metrics["bunching_rate"] == pytest.approx(expected)


def test_excess_wait_time(sample_headways):
    """EWT = sum(h_i^2) / (2 * sum(h_i)) - mean(h_i) / 2."""
    metrics = compute_headway_metrics(sample_headways)
    h = sample_headways
    expected_ewt = (h**2).sum() / (2 * h.sum()) - h.mean() / 2
    assert metrics["excess_wait_time"] == pytest.approx(expected_ewt)


def test_uniform_headways_zero_ewt():
    """Perfectly uniform headways should have EWT near 0."""
    uniform = pd.Series([10, 10, 10, 10, 10])
    metrics = compute_headway_metrics(uniform)
    assert metrics["excess_wait_time"] == pytest.approx(0.0)
    assert metrics["cv_headway"] == pytest.approx(0.0)


# --- detect_stop_arrivals ---


def test_detect_stop_arrivals_basic():
    """Detect when vehicles cross a reference pdist."""
    # Vehicle 100: approaches from far, crosses pdist=5000
    # Vehicle 200: approaches from far, crosses pdist=5000
    positions = pd.DataFrame(
        {
            "vid": ["100", "100", "100", "100", "200", "200", "200"],
            "tmstmp": [
                "20250401 08:00",
                "20250401 08:01",
                "20250401 08:02",
                "20250401 08:03",
                "20250401 08:10",
                "20250401 08:11",
                "20250401 08:12",
            ],
            "pdist": [4000, 4800, 5050, 6000, 4500, 4950, 5200],
            "rt": ["79"] * 7,
        }
    )
    arrivals = detect_stop_arrivals(positions, reference_pdist=5000, tolerance_feet=200)
    assert isinstance(arrivals, pd.DataFrame)
    assert "vid" in arrivals.columns
    assert "arrival_time" in arrivals.columns
    assert "pdist_at_arrival" in arrivals.columns
    # Should detect exactly 2 arrivals (one per vehicle)
    assert len(arrivals) == 2
    assert set(arrivals["vid"].tolist()) == {"100", "200"}


def test_detect_stop_arrivals_no_crossing():
    """Vehicle never reaches the reference pdist."""
    positions = pd.DataFrame(
        {
            "vid": ["100", "100", "100"],
            "tmstmp": ["20250401 08:00", "20250401 08:01", "20250401 08:02"],
            "pdist": [1000, 2000, 3000],
            "rt": ["79"] * 3,
        }
    )
    arrivals = detect_stop_arrivals(positions, reference_pdist=10000, tolerance_feet=200)
    assert len(arrivals) == 0


def test_detect_stop_arrivals_respects_tolerance():
    """Only detect arrivals within the tolerance window."""
    positions = pd.DataFrame(
        {
            "vid": ["100", "100"],
            "tmstmp": ["20250401 08:00", "20250401 08:01"],
            "pdist": [4000, 5150],  # 5150 is within 200 of 5000
            "rt": ["79"] * 2,
        }
    )
    arrivals = detect_stop_arrivals(positions, reference_pdist=5000, tolerance_feet=200)
    assert len(arrivals) == 1


# --- compute_headways_from_arrivals ---


def test_compute_headways_from_arrivals_basic():
    """Compute time gaps between consecutive arrival events."""
    arrivals = pd.DataFrame(
        {
            "vid": ["100", "200", "300"],
            "arrival_time": pd.to_datetime(
                ["2025-04-01 08:00", "2025-04-01 08:10", "2025-04-01 08:25"]
            ),
        }
    )
    headways = compute_headways_from_arrivals(arrivals)
    assert isinstance(headways, pd.Series)
    assert len(headways) == 2
    assert headways.iloc[0] == pytest.approx(10.0)
    assert headways.iloc[1] == pytest.approx(15.0)


def test_compute_headways_from_arrivals_single():
    """Single arrival yields empty headways."""
    arrivals = pd.DataFrame(
        {
            "vid": ["100"],
            "arrival_time": pd.to_datetime(["2025-04-01 08:00"]),
        }
    )
    headways = compute_headways_from_arrivals(arrivals)
    assert len(headways) == 0


def test_compute_headways_from_arrivals_unsorted():
    """Should sort by arrival_time before computing gaps."""
    arrivals = pd.DataFrame(
        {
            "vid": ["300", "100", "200"],
            "arrival_time": pd.to_datetime(
                ["2025-04-01 08:25", "2025-04-01 08:00", "2025-04-01 08:10"]
            ),
        }
    )
    headways = compute_headways_from_arrivals(arrivals)
    assert headways.iloc[0] == pytest.approx(10.0)
    assert headways.iloc[1] == pytest.approx(15.0)
