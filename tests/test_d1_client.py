"""Tests for D1Client — Cloudflare D1 REST API client."""

import json

import pytest
import responses

from bus_check.data.d1_client import D1Client

TEST_ACCOUNT = "test-account-id"
TEST_DB = "test-db-id"
TEST_TOKEN = "test-api-token"
D1_URL = f"https://api.cloudflare.com/client/v4/accounts/{TEST_ACCOUNT}/d1/database/{TEST_DB}/query"


@pytest.fixture
def d1_client():
    return D1Client(
        account_id=TEST_ACCOUNT,
        database_id=TEST_DB,
        api_token=TEST_TOKEN,
    )


@responses.activate
def test_execute_success(d1_client):
    """execute() should POST SQL and return the first result."""
    responses.add(
        responses.POST,
        D1_URL,
        json={"success": True, "result": [{"results": [{"count": 42}]}]},
        status=200,
    )
    result = d1_client.execute("SELECT COUNT(*) as count FROM vehicle_positions")
    assert result["results"][0]["count"] == 42


@responses.activate
def test_execute_sends_auth_header(d1_client):
    """execute() should include Bearer token in Authorization header."""
    responses.add(
        responses.POST, D1_URL, json={"success": True, "result": [{}]}, status=200
    )
    d1_client.execute("SELECT 1")
    assert (
        responses.calls[0].request.headers["Authorization"] == f"Bearer {TEST_TOKEN}"
    )


@responses.activate
def test_execute_sends_params(d1_client):
    """execute() should include params in the request body."""
    responses.add(
        responses.POST, D1_URL, json={"success": True, "result": [{}]}, status=200
    )
    d1_client.execute("SELECT * FROM vp WHERE route = ?", ["79"])
    body = json.loads(responses.calls[0].request.body)
    assert body["params"] == ["79"]


@responses.activate
def test_execute_api_error_raises(d1_client):
    """execute() should raise RuntimeError on D1 API error."""
    responses.add(
        responses.POST,
        D1_URL,
        json={"success": False, "errors": [{"message": "syntax error"}]},
        status=200,
    )
    with pytest.raises(RuntimeError, match="D1 query failed"):
        d1_client.execute("INVALID SQL")


@responses.activate
def test_execute_http_error_raises(d1_client):
    """execute() should raise on HTTP errors."""
    responses.add(responses.POST, D1_URL, status=500)
    with pytest.raises(Exception):
        d1_client.execute("SELECT 1")


@responses.activate
def test_insert_vehicle_positions_batch(d1_client):
    """insert_vehicle_positions_batch should send a multi-row INSERT."""
    responses.add(
        responses.POST, D1_URL, json={"success": True, "result": [{}]}, status=200
    )
    positions = [
        {
            "collected_at": "2026-02-13T10:00:00+00:00",
            "vid": "8001",
            "tmstmp": "20260213 10:00",
            "route": "79",
            "direction": "Eastbound",
            "destination": "Lakefront",
            "lat": 41.75,
            "lon": -87.65,
            "heading": 90,
            "speed": 25,
            "pdist": 15000,
            "pattern_id": "7901",
            "delayed": False,
        },
        {
            "collected_at": "2026-02-13T10:00:00+00:00",
            "vid": "8002",
            "tmstmp": "20260213 10:00",
            "route": "63",
            "direction": "Westbound",
            "destination": "Chicago",
            "lat": 41.78,
            "lon": -87.60,
            "heading": 270,
            "speed": 15,
            "pdist": 20000,
            "pattern_id": "6301",
            "delayed": False,
        },
    ]
    count = d1_client.insert_vehicle_positions_batch(positions)
    assert count == 2
    body = json.loads(responses.calls[0].request.body)
    assert "INSERT INTO vehicle_positions" in body["sql"]
    assert len(body["params"]) == 26  # 13 columns x 2 rows


def test_insert_empty_batch(d1_client):
    """insert_vehicle_positions_batch with empty list should return 0 without API call."""
    count = d1_client.insert_vehicle_positions_batch([])
    assert count == 0


@responses.activate
def test_insert_batch_chunks_large_batches(d1_client):
    """insert_vehicle_positions_batch should chunk into groups of 7 rows."""
    # Add enough mock responses for the expected number of chunks
    for _ in range(3):  # 15 rows / 7 per chunk = 3 chunks (7 + 7 + 1)
        responses.add(
            responses.POST,
            D1_URL,
            json={"success": True, "result": [{}]},
            status=200,
        )
    positions = [
        {
            "collected_at": f"2026-02-13T10:00:0{i}+00:00",
            "vid": str(8000 + i),
            "tmstmp": "20260213 10:00",
            "route": "79",
            "direction": "East",
            "destination": "Lakefront",
            "lat": 41.75,
            "lon": -87.65,
            "heading": 90,
            "speed": 25,
            "pdist": 15000,
            "pattern_id": "7901",
            "delayed": False,
        }
        for i in range(15)
    ]
    count = d1_client.insert_vehicle_positions_batch(positions)
    assert count == 15
    assert len(responses.calls) == 3  # 7 + 7 + 1
    # First chunk should have 7 rows = 91 params
    body0 = json.loads(responses.calls[0].request.body)
    assert len(body0["params"]) == 91
    # Last chunk should have 1 row = 13 params
    body2 = json.loads(responses.calls[2].request.body)
    assert len(body2["params"]) == 13


@responses.activate
def test_query_vehicle_positions_by_route(d1_client):
    """query_vehicle_positions_by_route should filter by route."""
    responses.add(
        responses.POST,
        D1_URL,
        json={
            "success": True,
            "result": [
                {
                    "results": [
                        {
                            "vid": "8001",
                            "tmstmp": "20260213 10:00",
                            "pdist": 15000,
                            "route": "79",
                            "direction": "East",
                        }
                    ]
                }
            ],
        },
        status=200,
    )
    rows = d1_client.query_vehicle_positions_by_route("79")
    assert len(rows) == 1
    assert rows[0]["route"] == "79"
    body = json.loads(responses.calls[0].request.body)
    assert body["params"] == ["79"]


@responses.activate
def test_get_collection_summary(d1_client):
    """get_collection_summary should return stats dict."""
    responses.add(
        responses.POST,
        D1_URL,
        json={
            "success": True,
            "result": [
                {
                    "results": [
                        {
                            "total_positions": 464674,
                            "polls": 1468,
                            "routes": 20,
                            "first_poll": "2026-02-11T21:57:17+00:00",
                            "last_poll": "2026-02-13T18:21:39+00:00",
                        }
                    ]
                }
            ],
        },
        status=200,
    )
    summary = d1_client.get_collection_summary()
    assert summary["total_positions"] == 464674
    assert summary["routes"] == 20
