import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from bus_check.data.db import create_schema

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def in_memory_db():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def ridership_sample_json():
    with open(FIXTURES_DIR / "ridership_sample.json") as f:
        return json.load(f)


@pytest.fixture
def ridership_sample_df(ridership_sample_json):
    df = pd.DataFrame(ridership_sample_json)
    df["date"] = pd.to_datetime(df["date"])
    df["rides"] = df["rides"].astype(int)
    return df


@pytest.fixture
def getvehicles_sample_json():
    with open(FIXTURES_DIR / "getvehicles_sample.json") as f:
        return json.load(f)


@pytest.fixture
def gtfs_sample_dir():
    return str(FIXTURES_DIR / "gtfs_sample")


@pytest.fixture
def sample_headways():
    """Synthetic headway data: mostly 8-12 min with some outliers."""
    return pd.Series(
        [8, 9, 10, 11, 10, 9, 8, 12, 15, 10, 9, 11, 10, 2, 18, 10, 9, 10, 11, 10]
    )
