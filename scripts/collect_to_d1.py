"""Collect CTA vehicle positions and write to Cloudflare D1.

Intended to run as a GitHub Actions step.
Requires environment variables:
    CTA_API_KEY, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, D1_DATABASE_ID
"""

import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from bus_check.config import ALL_FREQUENT_ROUTES, is_in_service_window
from bus_check.data.bus_tracker import BusTrackerClient
from bus_check.data.d1_client import D1Client


def chicago_now() -> datetime:
    """Get current time in Chicago (America/Chicago)."""
    return datetime.now(ZoneInfo("America/Chicago"))


def should_collect() -> bool:
    """Check if we are within CTA Frequent Network service hours."""
    now = chicago_now()
    is_weekday = now.weekday() < 5
    return is_in_service_window(now.hour, is_weekday)


def main() -> int:
    if not should_collect():
        now = chicago_now()
        print(
            f"Outside service window (Chicago time: {now.strftime('%A %H:%M')}). "
            "Skipping."
        )
        return 0

    # Load credentials
    cta_key = os.environ["CTA_API_KEY"]
    cf_account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    cf_token = os.environ["CLOUDFLARE_API_TOKEN"]
    db_id = os.environ["D1_DATABASE_ID"]

    # Poll CTA Bus Tracker
    bus_client = BusTrackerClient(api_key=cta_key)
    vehicles = bus_client.get_vehicles(ALL_FREQUENT_ROUTES)

    if not vehicles:
        print("No vehicles returned from CTA API.")
        return 0

    collected_at = datetime.now(timezone.utc).isoformat()

    # Transform to position dicts matching D1 schema
    positions = []
    for v in vehicles:
        positions.append(
            {
                "collected_at": collected_at,
                "vid": str(v.get("vid", "")),
                "tmstmp": str(v.get("tmstmp", "")),
                "route": str(v.get("rt", "")),
                "direction": v.get("rtdir"),
                "destination": v.get("des"),
                "lat": float(v.get("lat", 0)),
                "lon": float(v.get("lon", 0)),
                "heading": int(v["hdg"]) if "hdg" in v else None,
                "speed": int(v["spd"]) if "spd" in v else None,
                "pdist": int(v["pdist"]) if "pdist" in v else None,
                "pattern_id": str(v["pid"]) if "pid" in v else None,
                "delayed": bool(v.get("dly", False)),
            }
        )

    # Write to D1
    d1 = D1Client(account_id=cf_account, database_id=db_id, api_token=cf_token)
    count = d1.insert_vehicle_positions_batch(positions)
    print(f"Collected {count} vehicle positions at {collected_at}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
