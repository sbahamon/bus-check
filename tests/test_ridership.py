import json
import sqlite3
from unittest.mock import patch

import pandas as pd
import pytest
import responses

from bus_check.config import SODA_RIDERSHIP_ENDPOINT
from bus_check.data.db import create_schema, insert_ridership, query_ridership
from bus_check.data.ridership import (
    build_ridership_cache,
    fetch_all_routes,
    fetch_ridership,
    load_ridership,
)


# ---------------------------------------------------------------------------
# fetch_ridership
# ---------------------------------------------------------------------------

class TestFetchRidership:
    """Tests for fetch_ridership: SODA API querying with pagination."""

    @responses.activate
    def test_basic_fetch_returns_dataframe(self, ridership_sample_json):
        """fetch_ridership should return a DataFrame with correct dtypes."""
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=ridership_sample_json,
            status=200,
        )
        # Second call returns empty list to stop pagination
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=[],
            status=200,
        )

        df = fetch_ridership(
            routes=["79", "63"],
            start_date="2025-01-01",
            end_date="2025-04-30",
        )

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    @responses.activate
    def test_dtypes_are_correct(self, ridership_sample_json):
        """rides should be int, date should be datetime."""
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=ridership_sample_json,
            status=200,
        )
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=[],
            status=200,
        )

        df = fetch_ridership(
            routes=["79", "63"],
            start_date="2025-01-01",
            end_date="2025-04-30",
        )

        assert pd.api.types.is_integer_dtype(df["rides"])
        assert pd.api.types.is_datetime64_any_dtype(df["date"])

    @responses.activate
    def test_columns_present(self, ridership_sample_json):
        """DataFrame should contain route, date, daytype, rides columns."""
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=ridership_sample_json,
            status=200,
        )
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=[],
            status=200,
        )

        df = fetch_ridership(
            routes=["79", "63"],
            start_date="2025-01-01",
            end_date="2025-04-30",
        )

        for col in ["route", "date", "daytype", "rides"]:
            assert col in df.columns

    @responses.activate
    def test_where_clause_is_built_correctly(self, ridership_sample_json):
        """The SODA $where clause should filter by routes and date range."""
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=ridership_sample_json,
            status=200,
        )
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=[],
            status=200,
        )

        fetch_ridership(
            routes=["79", "63"],
            start_date="2025-01-01",
            end_date="2025-04-30",
        )

        # Inspect the first request's query params
        first_request = responses.calls[0].request
        params = first_request.params
        where = params.get("$where", "")
        assert "route" in where
        assert "'79'" in where or '"79"' in where
        assert "'63'" in where or '"63"' in where
        assert "2025-01-01" in where
        assert "2025-04-30" in where

    @responses.activate
    def test_pagination(self):
        """fetch_ridership should paginate when a full page is returned."""
        page1 = [
            {"route": "79", "date": "2025-01-06T00:00:00.000", "daytype": "W", "rides": "18500"},
        ] * 50000  # Full page triggers next request
        page2 = [
            {"route": "79", "date": "2025-02-06T00:00:00.000", "daytype": "W", "rides": "19000"},
        ]  # Partial page -- no further request needed

        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=page1,
            status=200,
        )
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=page2,
            status=200,
        )

        df = fetch_ridership(
            routes=["79"],
            start_date="2025-01-01",
            end_date="2025-03-01",
        )

        assert len(df) == 50001
        # Full first page triggers a second request; partial second page stops pagination
        assert len(responses.calls) == 2

    @responses.activate
    def test_app_token_header(self, ridership_sample_json):
        """When app_token is provided, it should be sent as X-App-Token header."""
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=ridership_sample_json,
            status=200,
        )
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=[],
            status=200,
        )

        fetch_ridership(
            routes=["79"],
            start_date="2025-01-01",
            end_date="2025-04-30",
            app_token="test-token-123",
        )

        first_request = responses.calls[0].request
        assert first_request.headers.get("X-App-Token") == "test-token-123"

    @responses.activate
    def test_no_app_token_header_when_none(self, ridership_sample_json):
        """When app_token is None, X-App-Token header should not be sent."""
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=ridership_sample_json,
            status=200,
        )
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=[],
            status=200,
        )

        fetch_ridership(
            routes=["79"],
            start_date="2025-01-01",
            end_date="2025-04-30",
        )

        first_request = responses.calls[0].request
        assert "X-App-Token" not in first_request.headers

    @responses.activate
    def test_empty_response_returns_empty_dataframe(self):
        """When SODA returns no data, an empty DataFrame should be returned."""
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=[],
            status=200,
        )

        df = fetch_ridership(
            routes=["999"],
            start_date="2025-01-01",
            end_date="2025-04-30",
        )

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


# ---------------------------------------------------------------------------
# build_ridership_cache
# ---------------------------------------------------------------------------

class TestBuildRidershipCache:
    """Tests for build_ridership_cache: download and store in SQLite."""

    @responses.activate
    def test_cache_populates_database(self, tmp_path, ridership_sample_json):
        """build_ridership_cache should insert rows into the SQLite database."""
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=ridership_sample_json,
            status=200,
        )
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=[],
            status=200,
        )

        db_path = str(tmp_path / "test.db")
        build_ridership_cache(db_path, start_date="2025-01-01")

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM ridership")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == len(ridership_sample_json)

    @responses.activate
    def test_cache_stores_correct_data(self, tmp_path, ridership_sample_json):
        """Cached rows should have correct route, date, daytype, rides values."""
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=ridership_sample_json,
            status=200,
        )
        responses.add(
            responses.GET,
            SODA_RIDERSHIP_ENDPOINT,
            json=[],
            status=200,
        )

        db_path = str(tmp_path / "test.db")
        build_ridership_cache(db_path, start_date="2025-01-01")

        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT route, rides FROM ridership WHERE route='79' ORDER BY date LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()

        assert row[0] == "79"
        assert row[1] == 18500


# ---------------------------------------------------------------------------
# fetch_all_routes
# ---------------------------------------------------------------------------

class TestFetchAllRoutes:
    """Tests for fetch_all_routes: SODA API querying without route filter."""

    @responses.activate
    def test_basic_fetch_returns_dataframe(self, ridership_sample_json):
        responses.add(responses.GET, SODA_RIDERSHIP_ENDPOINT, json=ridership_sample_json, status=200)
        responses.add(responses.GET, SODA_RIDERSHIP_ENDPOINT, json=[], status=200)

        df = fetch_all_routes(start_date="2025-01-01", end_date="2025-04-30")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(ridership_sample_json)

    @responses.activate
    def test_columns_and_dtypes(self, ridership_sample_json):
        responses.add(responses.GET, SODA_RIDERSHIP_ENDPOINT, json=ridership_sample_json, status=200)
        responses.add(responses.GET, SODA_RIDERSHIP_ENDPOINT, json=[], status=200)

        df = fetch_all_routes(start_date="2025-01-01", end_date="2025-04-30")

        for col in ["route", "date", "daytype", "rides"]:
            assert col in df.columns
        assert pd.api.types.is_integer_dtype(df["rides"])
        assert pd.api.types.is_datetime64_any_dtype(df["date"])

    @responses.activate
    def test_no_route_filter_in_where_clause(self, ridership_sample_json):
        """The $where clause should NOT contain a route filter."""
        responses.add(responses.GET, SODA_RIDERSHIP_ENDPOINT, json=ridership_sample_json, status=200)
        responses.add(responses.GET, SODA_RIDERSHIP_ENDPOINT, json=[], status=200)

        fetch_all_routes(start_date="2025-01-01", end_date="2025-04-30")

        first_request = responses.calls[0].request
        where = first_request.params.get("$where", "")
        assert "route" not in where.lower()
        assert "2025-01-01" in where
        assert "2025-04-30" in where

    @responses.activate
    def test_pagination(self):
        page1 = [
            {"route": "79", "date": "2025-01-06T00:00:00.000", "daytype": "W", "rides": "18500"},
        ] * 50000
        page2 = [
            {"route": "63", "date": "2025-02-06T00:00:00.000", "daytype": "W", "rides": "14000"},
        ]

        responses.add(responses.GET, SODA_RIDERSHIP_ENDPOINT, json=page1, status=200)
        responses.add(responses.GET, SODA_RIDERSHIP_ENDPOINT, json=page2, status=200)

        df = fetch_all_routes(start_date="2025-01-01", end_date="2025-03-01")

        assert len(df) == 50001
        assert len(responses.calls) == 2

    @responses.activate
    def test_app_token_header(self, ridership_sample_json):
        responses.add(responses.GET, SODA_RIDERSHIP_ENDPOINT, json=ridership_sample_json, status=200)
        responses.add(responses.GET, SODA_RIDERSHIP_ENDPOINT, json=[], status=200)

        fetch_all_routes(start_date="2025-01-01", end_date="2025-04-30", app_token="test-token")

        assert responses.calls[0].request.headers.get("X-App-Token") == "test-token"

    @responses.activate
    def test_empty_response_returns_empty_dataframe(self):
        responses.add(responses.GET, SODA_RIDERSHIP_ENDPOINT, json=[], status=200)

        df = fetch_all_routes(start_date="2099-01-01", end_date="2099-12-31")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        for col in ["route", "date", "daytype", "rides"]:
            assert col in df.columns


# ---------------------------------------------------------------------------
# load_ridership
# ---------------------------------------------------------------------------

class TestLoadRidership:
    """Tests for load_ridership: read from SQLite cache into DataFrame."""

    def test_load_all(self, in_memory_db):
        """load_ridership with no filters returns all data."""
        insert_ridership(in_memory_db, "79", "2025-04-01", "W", 15000)
        insert_ridership(in_memory_db, "79", "2025-04-02", "W", 15500)
        insert_ridership(in_memory_db, "63", "2025-04-01", "W", 12000)

        df = load_ridership(in_memory_db)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    def test_load_filtered_by_route(self, in_memory_db):
        """load_ridership with routes filter returns only matching routes."""
        insert_ridership(in_memory_db, "79", "2025-04-01", "W", 15000)
        insert_ridership(in_memory_db, "63", "2025-04-01", "W", 12000)

        df = load_ridership(in_memory_db, routes=["79"])

        assert len(df) == 1
        assert df.iloc[0]["route"] == "79"

    def test_load_filtered_by_date_range(self, in_memory_db):
        """load_ridership with date filters returns only matching dates."""
        insert_ridership(in_memory_db, "79", "2025-03-01", "W", 14000)
        insert_ridership(in_memory_db, "79", "2025-04-01", "W", 15000)
        insert_ridership(in_memory_db, "79", "2025-05-01", "W", 16000)

        df = load_ridership(
            in_memory_db,
            routes=["79"],
            start_date="2025-04-01",
            end_date="2025-04-30",
        )

        assert len(df) == 1
        assert df.iloc[0]["rides"] == 15000

    def test_load_returns_correct_dtypes(self, in_memory_db):
        """DataFrame from load_ridership should have correct dtypes."""
        insert_ridership(in_memory_db, "79", "2025-04-01", "W", 15000)

        df = load_ridership(in_memory_db)

        assert pd.api.types.is_integer_dtype(df["rides"])
        assert pd.api.types.is_datetime64_any_dtype(df["date"])

    def test_load_empty_returns_empty_dataframe(self, in_memory_db):
        """load_ridership on empty DB returns empty DataFrame."""
        df = load_ridership(in_memory_db)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
