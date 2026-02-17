import numpy as np
import pandas as pd
import pytest

from bus_check.analysis.headway_analysis import (
    compute_headway_metrics,
    compute_headways_from_arrivals,
    detect_stop_arrivals,
    filter_arrivals_to_service_window,
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
    """Detect when vehicles cross a reference pdist, with interpolated times."""
    # Vehicle 100: pdist crosses 5000 between obs at 4800 (08:01) and 5050 (08:02)
    # Vehicle 200: pdist crosses 5000 between obs at 4950 (08:11) and 5200 (08:12)
    positions = pd.DataFrame(
        {
            "vid": ["100", "100", "100", "100", "200", "200", "200"],
            "tmstmp": pd.to_datetime([
                "2025-04-01 08:00",
                "2025-04-01 08:01",
                "2025-04-01 08:02",
                "2025-04-01 08:03",
                "2025-04-01 08:10",
                "2025-04-01 08:11",
                "2025-04-01 08:12",
            ]),
            "pdist": [4000, 4800, 5050, 6000, 4500, 4950, 5200],
            "rt": ["79"] * 7,
        }
    )
    arrivals = detect_stop_arrivals(positions, reference_pdist=5000)
    assert isinstance(arrivals, pd.DataFrame)
    assert "vid" in arrivals.columns
    assert "arrival_time" in arrivals.columns
    assert "pdist_at_arrival" in arrivals.columns
    assert len(arrivals) == 2
    assert set(arrivals["vid"].tolist()) == {"100", "200"}


def test_detect_stop_arrivals_no_crossing():
    """Vehicle never reaches the reference pdist."""
    positions = pd.DataFrame(
        {
            "vid": ["100", "100", "100"],
            "tmstmp": pd.to_datetime([
                "2025-04-01 08:00", "2025-04-01 08:01", "2025-04-01 08:02",
            ]),
            "pdist": [1000, 2000, 3000],
            "rt": ["79"] * 3,
        }
    )
    arrivals = detect_stop_arrivals(positions, reference_pdist=10000)
    assert len(arrivals) == 0


def test_detect_stop_arrivals_interpolation_accuracy():
    """Arrival time is linearly interpolated between the two bounding observations."""
    # pdist goes from 4000 to 6000 over 10 minutes, reference=5000
    # fraction = (5000-4000)/(6000-4000) = 0.5 → arrival at midpoint (08:05)
    positions = pd.DataFrame(
        {
            "vid": ["100", "100"],
            "tmstmp": pd.to_datetime([
                "2025-04-01 08:00", "2025-04-01 08:10",
            ]),
            "pdist": [4000, 6000],
            "rt": ["79"] * 2,
        }
    )
    arrivals = detect_stop_arrivals(positions, reference_pdist=5000)
    assert len(arrivals) == 1
    expected_time = pd.Timestamp("2025-04-01 08:05")
    assert arrivals["arrival_time"].iloc[0] == expected_time
    assert arrivals["pdist_at_arrival"].iloc[0] == 5000


def test_detect_stop_arrivals_interpolation_asymmetric():
    """Interpolation works correctly when the crossing is not at the midpoint."""
    # pdist 2000 → 10000, reference=4000 → fraction = 2000/8000 = 0.25
    # 10 minutes * 0.25 = 2.5 minutes after 08:00 → 08:02:30
    positions = pd.DataFrame(
        {
            "vid": ["100", "100"],
            "tmstmp": pd.to_datetime([
                "2025-04-01 08:00", "2025-04-01 08:10",
            ]),
            "pdist": [2000, 10000],
            "rt": ["79"] * 2,
        }
    )
    arrivals = detect_stop_arrivals(positions, reference_pdist=4000)
    assert len(arrivals) == 1
    expected_time = pd.Timestamp("2025-04-01 08:02:30")
    assert arrivals["arrival_time"].iloc[0] == expected_time


def test_detect_stop_arrivals_multiple_trips():
    """Same vehicle crosses reference twice (two separate trips with pdist reset)."""
    positions = pd.DataFrame(
        {
            "vid": ["100"] * 6,
            "tmstmp": pd.to_datetime([
                "2025-04-01 08:00",  # trip 1: approaching
                "2025-04-01 08:10",  # trip 1: crossed reference
                "2025-04-01 08:20",  # trip 1: past reference
                "2025-04-01 10:00",  # trip 2: pdist reset, approaching again
                "2025-04-01 10:05",  # trip 2: still approaching
                "2025-04-01 10:10",  # trip 2: crossed reference
            ]),
            "pdist": [3000, 7000, 9000, 1000, 4000, 6000],
            "rt": ["79"] * 6,
        }
    )
    arrivals = detect_stop_arrivals(positions, reference_pdist=5000)
    assert len(arrivals) == 2
    assert all(arrivals["vid"] == "100")
    # First crossing: (3000→7000), fraction=0.5, time=08:05
    assert arrivals["arrival_time"].iloc[0] == pd.Timestamp("2025-04-01 08:05")
    # Second crossing: (4000→6000), fraction=0.5, time=10:07:30
    assert arrivals["arrival_time"].iloc[1] == pd.Timestamp("2025-04-01 10:07:30")


def test_detect_stop_arrivals_jitter_no_false_double():
    """Pdist jitter near reference doesn't produce false duplicate arrivals."""
    # Bus oscillates near reference=30000 within a short time window.
    # Only the first crossing should count; subsequent crossings within
    # 30 minutes of the same vehicle are suppressed.
    positions = pd.DataFrame(
        {
            "vid": ["100"] * 4,
            "tmstmp": pd.to_datetime([
                "2025-04-01 08:00",
                "2025-04-01 08:05",
                "2025-04-01 08:10",
                "2025-04-01 08:15",
            ]),
            "pdist": [29800, 30200, 29900, 30100],
            "rt": ["79"] * 4,
        }
    )
    arrivals = detect_stop_arrivals(positions, reference_pdist=30000)
    # Only the first crossing (29800→30200) should be detected
    assert len(arrivals) == 1


def test_detect_stop_arrivals_empty_input():
    """Empty positions DataFrame returns empty arrivals."""
    positions = pd.DataFrame(columns=["vid", "tmstmp", "pdist", "rt"])
    arrivals = detect_stop_arrivals(positions, reference_pdist=5000)
    assert len(arrivals) == 0
    assert list(arrivals.columns) == ["vid", "arrival_time", "pdist_at_arrival"]


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


# --- filter_arrivals_to_service_window ---


def test_filter_arrivals_to_service_window_weekday():
    """Weekday: 6am-9pm window. 5:30am and 9:30pm/11pm out, 8am/12pm in."""
    arrivals = pd.DataFrame(
        {
            "vid": ["A", "B", "C", "D", "E"],
            "arrival_time": pd.to_datetime(
                [
                    "2025-04-02 05:30",  # Wed, out (before 6am)
                    "2025-04-02 08:00",  # Wed, in
                    "2025-04-02 12:00",  # Wed, in
                    "2025-04-02 21:30",  # Wed, out (after 9pm)
                    "2025-04-02 23:00",  # Wed, out
                ]
            ),
            "pdist_at_arrival": [100, 200, 300, 400, 500],
        }
    )
    result = filter_arrivals_to_service_window(arrivals)
    assert len(result) == 2
    assert list(result["vid"]) == ["B", "C"]


def test_filter_arrivals_to_service_window_weekend():
    """Weekend: 9am-9pm window. 7am/8:59am out, 9am/2pm in, 9pm out."""
    arrivals = pd.DataFrame(
        {
            "vid": ["A", "B", "C", "D", "E"],
            "arrival_time": pd.to_datetime(
                [
                    "2025-04-05 07:00",  # Sat, out (before 9am)
                    "2025-04-05 08:59",  # Sat, out (before 9am)
                    "2025-04-05 09:00",  # Sat, in
                    "2025-04-05 14:00",  # Sat, in
                    "2025-04-05 21:00",  # Sat, out (at 9pm = hour 21)
                ]
            ),
            "pdist_at_arrival": [100, 200, 300, 400, 500],
        }
    )
    result = filter_arrivals_to_service_window(arrivals)
    assert len(result) == 2
    assert list(result["vid"]) == ["C", "D"]


def test_filter_arrivals_to_service_window_empty():
    """Empty DataFrame in → empty DataFrame out."""
    arrivals = pd.DataFrame(columns=["vid", "arrival_time", "pdist_at_arrival"])
    result = filter_arrivals_to_service_window(arrivals)
    assert len(result) == 0
    assert list(result.columns) == ["vid", "arrival_time", "pdist_at_arrival"]


def test_filter_arrivals_to_service_window_all_outside():
    """All arrivals at 3am on a weekday → empty result."""
    arrivals = pd.DataFrame(
        {
            "vid": ["A", "B", "C"],
            "arrival_time": pd.to_datetime(
                [
                    "2025-04-01 03:00",  # Tue 3am
                    "2025-04-01 03:10",
                    "2025-04-01 03:20",
                ]
            ),
            "pdist_at_arrival": [100, 200, 300],
        }
    )
    result = filter_arrivals_to_service_window(arrivals)
    assert len(result) == 0


def test_filter_arrivals_to_service_window_preserves_columns():
    """All expected columns (vid, arrival_time, pdist_at_arrival) are preserved."""
    arrivals = pd.DataFrame(
        {
            "vid": ["A"],
            "arrival_time": pd.to_datetime(["2025-04-01 10:00"]),  # Tue 10am, in
            "pdist_at_arrival": [5000],
        }
    )
    result = filter_arrivals_to_service_window(arrivals)
    assert len(result) == 1
    assert set(result.columns) == {"vid", "arrival_time", "pdist_at_arrival"}
    assert result["vid"].iloc[0] == "A"
    assert result["pdist_at_arrival"].iloc[0] == 5000


def test_filter_arrivals_to_service_window_mixed_days():
    """Weekday 7am (in), Saturday 7am (out), Saturday 10am (in)."""
    arrivals = pd.DataFrame(
        {
            "vid": ["A", "B", "C"],
            "arrival_time": pd.to_datetime(
                [
                    "2025-04-01 07:00",  # Tue 7am — in (weekday 6-21)
                    "2025-04-05 07:00",  # Sat 7am — out (weekend 9-21)
                    "2025-04-05 10:00",  # Sat 10am — in (weekend 9-21)
                ]
            ),
            "pdist_at_arrival": [100, 200, 300],
        }
    )
    result = filter_arrivals_to_service_window(arrivals)
    assert len(result) == 2
    assert list(result["vid"]) == ["A", "C"]
