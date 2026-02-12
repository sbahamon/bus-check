import json
from pathlib import Path

import pytest
import responses

from bus_check.config import BUS_TRACKER_BASE_URL
from bus_check.data.bus_tracker import BusTrackerClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"
BASE = BUS_TRACKER_BASE_URL


@pytest.fixture
def client():
    return BusTrackerClient(api_key="TEST_KEY")


@pytest.fixture
def sample_vehicles():
    with open(FIXTURES_DIR / "getvehicles_sample.json") as f:
        return json.load(f)


# --- _request / error handling ---


@responses.activate
def test_request_raises_on_api_error(client):
    responses.add(
        responses.GET,
        f"{BASE}/getroutes",
        json={"bustime-response": {"error": [{"msg": "Invalid API key"}]}},
        status=200,
    )
    with pytest.raises(RuntimeError, match="Invalid API key"):
        client.get_routes()


@responses.activate
def test_request_raises_on_http_error(client):
    responses.add(
        responses.GET,
        f"{BASE}/getroutes",
        json={},
        status=500,
    )
    with pytest.raises(Exception):
        client.get_routes()


# --- get_vehicles ---


@responses.activate
def test_get_vehicles_returns_vehicle_list(client, sample_vehicles):
    responses.add(
        responses.GET,
        f"{BASE}/getvehicles",
        json=sample_vehicles,
        status=200,
    )
    vehicles = client.get_vehicles(["79", "63"])
    assert len(vehicles) == 4
    assert vehicles[0]["vid"] == "8001"
    assert vehicles[0]["rt"] == "79"


@responses.activate
def test_get_vehicles_chunks_into_batches_of_10(client, sample_vehicles):
    """When given >10 routes, should make multiple API calls."""
    # 15 routes -> 2 calls (10 + 5)
    routes = [str(i) for i in range(15)]

    responses.add(
        responses.GET,
        f"{BASE}/getvehicles",
        json=sample_vehicles,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE}/getvehicles",
        json={"bustime-response": {"vehicle": [{"vid": "9999", "rt": "14"}]}},
        status=200,
    )

    vehicles = client.get_vehicles(routes)
    assert len(responses.calls) == 2
    # First batch should have 10 routes comma-joined
    first_call_params = responses.calls[0].request.params
    assert len(first_call_params["rt"].split(",")) == 10
    # Second batch should have 5 routes
    second_call_params = responses.calls[1].request.params
    assert len(second_call_params["rt"].split(",")) == 5
    # All vehicles combined
    assert len(vehicles) == 5  # 4 + 1


@responses.activate
def test_get_vehicles_empty_response(client):
    """API may return error instead of vehicle list when no vehicles found."""
    responses.add(
        responses.GET,
        f"{BASE}/getvehicles",
        json={"bustime-response": {"error": [{"msg": "No data found for parameter"}]}},
        status=200,
    )
    vehicles = client.get_vehicles(["999"])
    assert vehicles == []


# --- get_routes ---


@responses.activate
def test_get_routes(client):
    responses.add(
        responses.GET,
        f"{BASE}/getroutes",
        json={
            "bustime-response": {
                "routes": [
                    {"rt": "79", "rtnm": "79th", "rtclr": "#ff0000", "rtdd": "79"},
                    {"rt": "63", "rtnm": "63rd", "rtclr": "#00ff00", "rtdd": "63"},
                ]
            }
        },
        status=200,
    )
    routes = client.get_routes()
    assert len(routes) == 2
    assert routes[0]["rt"] == "79"


# --- get_directions ---


@responses.activate
def test_get_directions(client):
    responses.add(
        responses.GET,
        f"{BASE}/getdirections",
        json={
            "bustime-response": {
                "directions": [
                    {"dir": "Eastbound"},
                    {"dir": "Westbound"},
                ]
            }
        },
        status=200,
    )
    directions = client.get_directions("79")
    assert directions == ["Eastbound", "Westbound"]


# --- get_stops ---


@responses.activate
def test_get_stops(client):
    responses.add(
        responses.GET,
        f"{BASE}/getstops",
        json={
            "bustime-response": {
                "stops": [
                    {"stpid": "4567", "stpnm": "79th & Western", "lat": 41.75, "lon": -87.68},
                ]
            }
        },
        status=200,
    )
    stops = client.get_stops("79", "Eastbound")
    assert len(stops) == 1
    assert stops[0]["stpid"] == "4567"


# --- get_predictions ---


@responses.activate
def test_get_predictions(client):
    responses.add(
        responses.GET,
        f"{BASE}/getpredictions",
        json={
            "bustime-response": {
                "prd": [
                    {
                        "tmstmp": "20250401 08:00",
                        "typ": "A",
                        "stpid": "4567",
                        "stpnm": "79th & Western",
                        "vid": "8001",
                        "dstp": 1500,
                        "rt": "79",
                        "des": "Lakefront",
                        "prdtm": "20250401 08:05",
                    }
                ]
            }
        },
        status=200,
    )
    predictions = client.get_predictions("4567", route="79")
    assert len(predictions) == 1
    assert predictions[0]["vid"] == "8001"


@responses.activate
def test_get_predictions_without_route(client):
    responses.add(
        responses.GET,
        f"{BASE}/getpredictions",
        json={"bustime-response": {"prd": [{"vid": "8001"}]}},
        status=200,
    )
    predictions = client.get_predictions("4567")
    assert len(predictions) == 1
    # Should not have rt param in the request
    params = responses.calls[0].request.params
    assert "rt" not in params


# --- api_key is always sent ---


@responses.activate
def test_api_key_always_sent(client):
    responses.add(
        responses.GET,
        f"{BASE}/getroutes",
        json={"bustime-response": {"routes": []}},
        status=200,
    )
    client.get_routes()
    params = responses.calls[0].request.params
    assert params["key"] == "TEST_KEY"
    assert params["format"] == "json"
