"""Cloudflare D1 REST API client for vehicle position storage."""

import requests

D1_API_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query"


class D1Client:
    """Client for reading/writing vehicle positions to Cloudflare D1."""

    def __init__(self, account_id: str, database_id: str, api_token: str):
        self.url = D1_API_URL.format(
            account_id=account_id, database_id=database_id
        )
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def execute(self, sql: str, params: list | None = None) -> dict:
        """Execute a single SQL statement against D1."""
        body: dict = {"sql": sql}
        if params:
            body["params"] = params
        resp = requests.post(self.url, json=body, headers=self.headers)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            errors = data.get("errors", [])
            raise RuntimeError(f"D1 query failed: {errors}")
        return data["result"][0]

    def insert_vehicle_positions_batch(self, positions: list[dict]) -> int:
        """Insert vehicle positions in chunked multi-row INSERTs.

        D1 limits bound parameters to 100 per query. With 13 columns per row,
        we batch at 7 rows per INSERT (91 params) to stay within limits.
        """
        if not positions:
            return 0

        ROWS_PER_BATCH = 7  # 7 × 13 columns = 91 params (under D1's 100 limit)

        for i in range(0, len(positions), ROWS_PER_BATCH):
            chunk = positions[i : i + ROWS_PER_BATCH]
            placeholders = []
            params = []
            for p in chunk:
                placeholders.append("(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
                params.extend([
                    p["collected_at"],
                    p["vid"],
                    p["tmstmp"],
                    p["route"],
                    p.get("direction"),
                    p.get("destination"),
                    p["lat"],
                    p["lon"],
                    p.get("heading"),
                    p.get("speed"),
                    p.get("pdist"),
                    p.get("pattern_id"),
                    p.get("delayed", False),
                ])

            sql = (
                "INSERT INTO vehicle_positions "
                "(collected_at, vid, tmstmp, route, direction, destination, "
                "lat, lon, heading, speed, pdist, pattern_id, delayed) "
                f"VALUES {', '.join(placeholders)}"
            )
            self.execute(sql, params)

        return len(positions)

    def query_vehicle_positions_by_route(self, route: str) -> list[dict]:
        """Query all positions for a specific route."""
        sql = (
            "SELECT vid, tmstmp, pdist, route, direction "
            "FROM vehicle_positions WHERE route = ? ORDER BY collected_at"
        )
        result = self.execute(sql, [route])
        return result.get("results", [])

    def get_collection_summary(self) -> dict:
        """Get summary stats about collected data."""
        sql = """
            SELECT COUNT(*) as total_positions,
                   COUNT(DISTINCT collected_at) as polls,
                   COUNT(DISTINCT route) as routes,
                   MIN(collected_at) as first_poll,
                   MAX(collected_at) as last_poll
            FROM vehicle_positions
        """
        result = self.execute(sql)
        rows = result.get("results", [])
        return rows[0] if rows else {}
