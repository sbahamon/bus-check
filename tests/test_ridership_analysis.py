"""Tests for ridership_analysis module using synthetic DataFrame fixtures."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from bus_check.analysis.headway_analysis import compute_headway_metrics
from bus_check.analysis.ridership_analysis import (
    compute_yoy_change,
    prepare_did_data,
    select_control_routes,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def yoy_df():
    """Synthetic ridership data for year-over-year change tests.

    Route 79 with data in Jan-Mar 2024 (pre) and Jan-Mar 2025 (post).
    Launch date: 2025-01-01.  Pre avg weekday: 10000.  Post avg weekday: 12000.
    """
    rows = []
    # Pre-period: Jan-Mar 2024 weekday data (3 months after launch date minus 1 year)
    for day in range(1, 61):  # 60 weekdays
        rows.append({
            "route": "79",
            "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=day),
            "daytype": "W",
            "rides": 10000,
        })
    # Post-period: Jan-Mar 2025 weekday data (3 months after launch date)
    for day in range(0, 60):  # 60 weekdays
        rows.append({
            "route": "79",
            "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=day),
            "daytype": "W",
            "rides": 12000,
        })
    # Add some weekend data that should be excluded
    rows.append({
        "route": "79",
        "date": pd.Timestamp("2025-01-04"),
        "daytype": "A",
        "rides": 5000,
    })
    rows.append({
        "route": "79",
        "date": pd.Timestamp("2024-01-06"),
        "daytype": "U",
        "rides": 4000,
    })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.fixture
def control_selection_df():
    """Synthetic data for control route selection.

    Treated route "79" has avg weekday ridership of ~10000.
    Other routes have varying averages to test matching.
    """
    rows = []
    routes_and_avg = {
        "79": 10000,   # treated
        "60": 10200,   # close match
        "63": 9800,    # close match
        "8": 15000,    # further away
        "22": 10100,   # close match
        "66": 9900,    # close match
        "77": 5000,    # far away
        "9": 10050,    # close match
        "4": 25000,    # very far
        "20": 10500,   # moderate match
        "55": 9500,    # moderate match
        "12": 10300,   # close match
        "34": 9700,    # close match
        "47": 10400,   # close match
        "49": 11000,   # moderate match
        "53": 8000,    # moderate match
        "54": 10600,   # moderate match
        "72": 7000,    # far
        "81": 10150,   # close match
        "82": 9950,    # close match
    }

    for route, avg_rides in routes_and_avg.items():
        for day in range(30):
            rows.append({
                "route": route,
                "date": pd.Timestamp("2024-12-01") + pd.Timedelta(days=day),
                "daytype": "W",
                "rides": avg_rides,
            })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.fixture
def did_df():
    """Synthetic data for difference-in-differences preparation.

    Treated routes: "79", "63"  (phase 1 launch: 2025-03-23)
    Control routes: "8", "22"
    Data spans pre and post period.
    """
    rows = []
    all_routes = ["79", "63", "8", "22"]

    for route in all_routes:
        # Pre-period: Jan-Feb 2025
        for day in range(60):
            rows.append({
                "route": route,
                "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=day),
                "daytype": "W",
                "rides": 10000,
            })
        # Post-period: Apr-May 2025
        for day in range(60):
            rows.append({
                "route": route,
                "date": pd.Timestamp("2025-04-01") + pd.Timedelta(days=day),
                "daytype": "W",
                "rides": 12000 if route in ["79", "63"] else 10000,
            })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------------------
# compute_yoy_change
# ---------------------------------------------------------------------------

class TestComputeYoyChange:
    """Tests for compute_yoy_change."""

    def test_returns_dict_with_expected_keys(self, yoy_df):
        result = compute_yoy_change(
            yoy_df, route="79", launch_date=date(2025, 1, 1), months_window=3
        )

        assert isinstance(result, dict)
        expected_keys = {"route", "pre_avg", "post_avg", "abs_change", "pct_change"}
        assert set(result.keys()) == expected_keys

    def test_route_is_correct(self, yoy_df):
        result = compute_yoy_change(
            yoy_df, route="79", launch_date=date(2025, 1, 1), months_window=3
        )

        assert result["route"] == "79"

    def test_pre_avg_uses_prior_year_weekday(self, yoy_df):
        result = compute_yoy_change(
            yoy_df, route="79", launch_date=date(2025, 1, 1), months_window=3
        )

        # Pre-period weekday average should be 10000
        assert result["pre_avg"] == pytest.approx(10000, rel=0.01)

    def test_post_avg_uses_current_year_weekday(self, yoy_df):
        result = compute_yoy_change(
            yoy_df, route="79", launch_date=date(2025, 1, 1), months_window=3
        )

        # Post-period weekday average should be 12000
        assert result["post_avg"] == pytest.approx(12000, rel=0.01)

    def test_abs_change(self, yoy_df):
        result = compute_yoy_change(
            yoy_df, route="79", launch_date=date(2025, 1, 1), months_window=3
        )

        assert result["abs_change"] == pytest.approx(2000, rel=0.01)

    def test_pct_change(self, yoy_df):
        result = compute_yoy_change(
            yoy_df, route="79", launch_date=date(2025, 1, 1), months_window=3
        )

        # (12000 - 10000) / 10000 = 0.2 = 20%
        assert result["pct_change"] == pytest.approx(0.2, rel=0.01)

    def test_excludes_weekend_data(self, yoy_df):
        """Weekend/holiday data (daytype A/U) should not affect averages."""
        result = compute_yoy_change(
            yoy_df, route="79", launch_date=date(2025, 1, 1), months_window=3
        )

        # If weekend data were included, averages would differ from 10000/12000
        assert result["pre_avg"] == pytest.approx(10000, rel=0.01)
        assert result["post_avg"] == pytest.approx(12000, rel=0.01)


# ---------------------------------------------------------------------------
# select_control_routes
# ---------------------------------------------------------------------------

class TestSelectControlRoutes:
    """Tests for select_control_routes."""

    def test_returns_list_of_strings(self, control_selection_df):
        controls = select_control_routes(
            control_selection_df, treated_routes=["79"], n_controls=5
        )

        assert isinstance(controls, list)
        assert all(isinstance(r, str) for r in controls)

    def test_excludes_treated_routes(self, control_selection_df):
        controls = select_control_routes(
            control_selection_df, treated_routes=["79"], n_controls=15
        )

        assert "79" not in controls

    def test_returns_n_controls(self, control_selection_df):
        controls = select_control_routes(
            control_selection_df, treated_routes=["79"], n_controls=5
        )

        assert len(controls) == 5

    def test_closest_matches_come_first(self, control_selection_df):
        """Routes with ridership closest to treated should be selected."""
        controls = select_control_routes(
            control_selection_df, treated_routes=["79"], n_controls=5
        )

        # Routes very far from 10000 (like "4" at 25000 and "77" at 5000)
        # should NOT be in the top 5 controls
        assert "4" not in controls
        assert "77" not in controls

    def test_multiple_treated_routes(self, control_selection_df):
        """Should match on average across multiple treated routes."""
        controls = select_control_routes(
            control_selection_df, treated_routes=["79", "63"], n_controls=5
        )

        assert "79" not in controls
        assert "63" not in controls
        assert len(controls) == 5


# ---------------------------------------------------------------------------
# prepare_did_data
# ---------------------------------------------------------------------------

class TestPrepareDiDData:
    """Tests for prepare_did_data."""

    def test_returns_dataframe(self, did_df):
        phase_dates = {"79": date(2025, 3, 23), "63": date(2025, 3, 23)}
        result = prepare_did_data(
            did_df,
            treated_routes=["79", "63"],
            control_routes=["8", "22"],
            phase_dates=phase_dates,
        )

        assert isinstance(result, pd.DataFrame)

    def test_has_required_columns(self, did_df):
        phase_dates = {"79": date(2025, 3, 23), "63": date(2025, 3, 23)}
        result = prepare_did_data(
            did_df,
            treated_routes=["79", "63"],
            control_routes=["8", "22"],
            phase_dates=phase_dates,
        )

        for col in ["treated", "post", "treated_post"]:
            assert col in result.columns

    def test_treated_column(self, did_df):
        phase_dates = {"79": date(2025, 3, 23), "63": date(2025, 3, 23)}
        result = prepare_did_data(
            did_df,
            treated_routes=["79", "63"],
            control_routes=["8", "22"],
            phase_dates=phase_dates,
        )

        treated_rows = result[result["route"].isin(["79", "63"])]
        control_rows = result[result["route"].isin(["8", "22"])]

        assert treated_rows["treated"].all()
        assert not control_rows["treated"].any()

    def test_post_column(self, did_df):
        """post should be True for dates after the route's launch date."""
        phase_dates = {"79": date(2025, 3, 23), "63": date(2025, 3, 23)}
        result = prepare_did_data(
            did_df,
            treated_routes=["79", "63"],
            control_routes=["8", "22"],
            phase_dates=phase_dates,
        )

        # April data should be post
        apr_data = result[result["date"] >= pd.Timestamp("2025-04-01")]
        assert apr_data["post"].all()

        # January data should be pre
        jan_data = result[result["date"] < pd.Timestamp("2025-03-01")]
        assert not jan_data["post"].any()

    def test_treated_post_interaction(self, did_df):
        """treated_post should be True only for treated routes in post period."""
        phase_dates = {"79": date(2025, 3, 23), "63": date(2025, 3, 23)}
        result = prepare_did_data(
            did_df,
            treated_routes=["79", "63"],
            control_routes=["8", "22"],
            phase_dates=phase_dates,
        )

        # Only treated routes in post period should have treated_post=True
        tp = result[result["treated_post"]]
        assert tp["treated"].all()
        assert tp["post"].all()

    def test_only_includes_specified_routes(self, did_df):
        """Only treated and control routes should be in the output."""
        phase_dates = {"79": date(2025, 3, 23), "63": date(2025, 3, 23)}
        result = prepare_did_data(
            did_df,
            treated_routes=["79", "63"],
            control_routes=["8", "22"],
            phase_dates=phase_dates,
        )

        routes_in_result = set(result["route"].unique())
        assert routes_in_result == {"79", "63", "8", "22"}


# ---------------------------------------------------------------------------
# compute_headway_metrics
# ---------------------------------------------------------------------------

class TestComputeHeadwayMetrics:
    """Tests for compute_headway_metrics."""

    def test_returns_dict(self, sample_headways):
        result = compute_headway_metrics(sample_headways)
        assert isinstance(result, dict)

    def test_has_expected_keys(self, sample_headways):
        result = compute_headway_metrics(sample_headways)
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
        assert set(result.keys()) == expected_keys

    def test_mean(self, sample_headways):
        result = compute_headway_metrics(sample_headways)
        assert result["mean_headway"] == pytest.approx(sample_headways.mean(), rel=1e-6)

    def test_median(self, sample_headways):
        result = compute_headway_metrics(sample_headways)
        assert result["median_headway"] == pytest.approx(sample_headways.median(), rel=1e-6)

    def test_std(self, sample_headways):
        result = compute_headway_metrics(sample_headways)
        assert result["std_headway"] == pytest.approx(sample_headways.std(), rel=1e-6)

    def test_cv(self, sample_headways):
        """Coefficient of variation = std / mean."""
        result = compute_headway_metrics(sample_headways)
        expected_cv = sample_headways.std() / sample_headways.mean()
        assert result["cv_headway"] == pytest.approx(expected_cv, rel=1e-6)

    def test_pct_under_10(self, sample_headways):
        """Percentage of headways at or under 10 minutes."""
        result = compute_headway_metrics(sample_headways)
        expected = (sample_headways <= 10).sum() / len(sample_headways) * 100
        assert result["pct_under_10"] == pytest.approx(expected, rel=1e-6)

    def test_pct_over_15(self, sample_headways):
        """Percentage of headways over 15 minutes."""
        result = compute_headway_metrics(sample_headways)
        expected = (sample_headways > 15).sum() / len(sample_headways) * 100
        assert result["pct_over_15"] == pytest.approx(expected, rel=1e-6)

    def test_max(self, sample_headways):
        result = compute_headway_metrics(sample_headways)
        assert result["max_headway"] == sample_headways.max()

    def test_bunching_rate(self, sample_headways):
        """Bunching rate = percentage of headways under 2 minutes."""
        result = compute_headway_metrics(sample_headways)
        expected = (sample_headways < 2).sum() / len(sample_headways) * 100
        assert result["bunching_rate"] == pytest.approx(expected, rel=1e-6)

    def test_excess_wait_time(self, sample_headways):
        """Excess wait time = sum(h^2) / (2 * sum(h)) - mean(h) / 2.

        This measures additional wait above what a perfectly regular service
        would provide.
        """
        result = compute_headway_metrics(sample_headways)
        h = sample_headways
        expected = (h**2).sum() / (2 * h.sum()) - h.mean() / 2
        assert result["excess_wait_time"] == pytest.approx(expected, rel=1e-6)

    def test_all_uniform_headways(self):
        """With perfectly uniform headways, excess_wait_time should be ~0."""
        uniform = pd.Series([10, 10, 10, 10, 10])
        result = compute_headway_metrics(uniform)

        assert result["mean_headway"] == 10.0
        assert result["std_headway"] == 0.0
        assert result["cv_headway"] == 0.0
        assert result["excess_wait_time"] == pytest.approx(0.0, abs=1e-10)
        assert result["bunching_rate"] == 0.0
