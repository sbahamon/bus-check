"""Fetch and cache CTA ridership data from the Chicago Data Portal SODA API."""

import sqlite3

import pandas as pd
import requests

from bus_check.config import SODA_RIDERSHIP_ENDPOINT
from bus_check.data.db import create_schema, insert_ridership as db_insert_ridership, query_ridership


SODA_PAGE_SIZE = 50000


def fetch_ridership(
    routes: list[str],
    start_date: str,
    end_date: str,
    app_token: str | None = None,
) -> pd.DataFrame:
    """Query SODA API for ridership data with automatic pagination.

    Args:
        routes: List of route identifiers (e.g. ["79", "63"]).
        start_date: Start date as ISO string (e.g. "2025-01-01").
        end_date: End date as ISO string (e.g. "2025-04-30").
        app_token: Optional Socrata app token for higher rate limits.

    Returns:
        DataFrame with columns: route, date, daytype, rides.
        date is datetime64, rides is int.
    """
    # Build the $where clause
    route_list = ", ".join(f"'{r}'" for r in routes)
    where = (
        f"route in({route_list}) "
        f"AND date >= '{start_date}T00:00:00.000' "
        f"AND date <= '{end_date}T23:59:59.999'"
    )

    headers: dict[str, str] = {}
    if app_token:
        headers["X-App-Token"] = app_token

    all_rows: list[dict] = []
    offset = 0

    while True:
        params = {
            "$where": where,
            "$limit": str(SODA_PAGE_SIZE),
            "$offset": str(offset),
            "$order": "route,date",
        }

        resp = requests.get(
            SODA_RIDERSHIP_ENDPOINT,
            params=params,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        page = resp.json()

        if not page:
            break

        all_rows.extend(page)
        offset += len(page)

        if len(page) < SODA_PAGE_SIZE:
            break

    if not all_rows:
        return pd.DataFrame(columns=["route", "date", "daytype", "rides"])

    df = pd.DataFrame(all_rows)
    df["date"] = pd.to_datetime(df["date"])
    df["rides"] = df["rides"].astype(int)

    return df


def fetch_all_routes(
    start_date: str,
    end_date: str,
    app_token: str | None = None,
) -> pd.DataFrame:
    """Query SODA API for ridership data across ALL routes with automatic pagination.

    Unlike fetch_ridership(), this does not filter by route — it returns
    every route in the dataset for the given date range. Useful for
    control-group selection and system-wide analysis.

    Args:
        start_date: Start date as ISO string (e.g. "2023-01-01").
        end_date: End date as ISO string (e.g. "2025-11-30").
        app_token: Optional Socrata app token for higher rate limits.

    Returns:
        DataFrame with columns: route, date, daytype, rides.
        date is datetime64, rides is int.
    """
    where = (
        f"date >= '{start_date}T00:00:00.000' "
        f"AND date <= '{end_date}T23:59:59.999'"
    )

    headers: dict[str, str] = {}
    if app_token:
        headers["X-App-Token"] = app_token

    all_rows: list[dict] = []
    offset = 0

    while True:
        params = {
            "$where": where,
            "$limit": str(SODA_PAGE_SIZE),
            "$offset": str(offset),
            "$order": "route,date",
        }

        resp = requests.get(
            SODA_RIDERSHIP_ENDPOINT,
            params=params,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        page = resp.json()

        if not page:
            break

        all_rows.extend(page)
        offset += len(page)

        if len(page) < SODA_PAGE_SIZE:
            break

    if not all_rows:
        return pd.DataFrame(columns=["route", "date", "daytype", "rides"])

    df = pd.DataFrame(all_rows)
    df["date"] = pd.to_datetime(df["date"])
    df["rides"] = df["rides"].astype(int)

    return df


def build_ridership_cache(
    db_path: str,
    start_date: str = "2023-01-01",
) -> None:
    """Download all ridership data from SODA and store in SQLite.

    Args:
        db_path: Path to the SQLite database file.
        start_date: Start date for the data download.
    """
    conn = sqlite3.connect(db_path)
    create_schema(conn)

    # Fetch all routes — use empty where route filter, just date
    headers: dict[str, str] = {}
    all_rows: list[dict] = []
    offset = 0

    where = f"date >= '{start_date}T00:00:00.000'"

    while True:
        params = {
            "$where": where,
            "$limit": str(SODA_PAGE_SIZE),
            "$offset": str(offset),
            "$order": "route,date",
        }

        resp = requests.get(
            SODA_RIDERSHIP_ENDPOINT,
            params=params,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        page = resp.json()

        if not page:
            break

        all_rows.extend(page)
        offset += len(page)

        if len(page) < SODA_PAGE_SIZE:
            break

    for row in all_rows:
        date_str = row["date"][:10]  # "2025-01-06T00:00:00.000" -> "2025-01-06"
        db_insert_ridership(
            conn,
            route=row["route"],
            date=date_str,
            daytype=row["daytype"],
            rides=int(row["rides"]),
        )

    conn.close()


def load_ridership(
    db_conn: sqlite3.Connection,
    routes: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Load ridership data from SQLite cache.

    Args:
        db_conn: SQLite connection (or path string).
        routes: Optional list of routes to filter by.
        start_date: Optional start date filter.
        end_date: Optional end date filter.

    Returns:
        DataFrame with columns: route, date, daytype, rides.
        date is datetime64, rides is int.
    """
    rows = query_ridership(
        db_conn,
        routes=routes,
        start_date=start_date,
        end_date=end_date,
    )

    if not rows:
        return pd.DataFrame(columns=["route", "date", "daytype", "rides"])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["rides"] = df["rides"].astype(int)

    return df
