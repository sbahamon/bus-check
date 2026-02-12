"""CTA Bus Tracker API client."""

import requests

from bus_check.config import BUS_TRACKER_BASE_URL


class BusTrackerClient:
    """Client for the CTA Bus Tracker API v2."""

    BATCH_SIZE = 10  # Max routes per getvehicles call

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = BUS_TRACKER_BASE_URL

    def _request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make an HTTP GET request to the Bus Tracker API.

        Adds the API key and format=json to every request.
        Checks for API-level errors in the response body.
        Raises RuntimeError on API errors, requests exceptions on HTTP errors.
        """
        if params is None:
            params = {}
        params["key"] = self.api_key
        params["format"] = "json"

        url = f"{self.base_url}/{endpoint}"
        resp = requests.get(url, params=params)
        resp.raise_for_status()

        data = resp.json()
        bustime = data.get("bustime-response", {})

        if "error" in bustime:
            errors = bustime["error"]
            messages = [e.get("msg", str(e)) for e in errors]
            raise RuntimeError("; ".join(messages))

        return bustime

    def get_vehicles(self, routes: list[str]) -> list[dict]:
        """Get vehicle positions for the given routes.

        Handles chunking into batches of 10 routes per API call.
        Returns an empty list if no vehicles are found (rather than raising).
        """
        all_vehicles = []
        for i in range(0, len(routes), self.BATCH_SIZE):
            batch = routes[i : i + self.BATCH_SIZE]
            rt_param = ",".join(batch)
            try:
                data = self._request("getvehicles", {"rt": rt_param})
                vehicles = data.get("vehicle", [])
                # API returns a single dict instead of a list if only one vehicle
                if isinstance(vehicles, dict):
                    vehicles = [vehicles]
                all_vehicles.extend(vehicles)
            except RuntimeError as e:
                # "No data found" is not a real error — just means no buses on route
                if "No data found" in str(e):
                    continue
                raise
        return all_vehicles

    def get_routes(self) -> list[dict]:
        """Get all available bus routes."""
        data = self._request("getroutes")
        return data.get("routes", [])

    def get_directions(self, route: str) -> list[str]:
        """Get available directions for a route."""
        data = self._request("getdirections", {"rt": route})
        directions = data.get("directions", [])
        return [d["dir"] for d in directions]

    def get_stops(self, route: str, direction: str) -> list[dict]:
        """Get stops for a route/direction."""
        data = self._request("getstops", {"rt": route, "dir": direction})
        return data.get("stops", [])

    def get_predictions(self, stop_id: str, route: str = None) -> list[dict]:
        """Get arrival predictions for a stop."""
        params = {"stpid": stop_id}
        if route is not None:
            params["rt"] = route
        data = self._request("getpredictions", params)
        return data.get("prd", [])
