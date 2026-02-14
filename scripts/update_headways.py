"""Analyze headway data from D1 and update site/headways.html.

Reads vehicle positions from Cloudflare D1, runs the existing headway
analysis pipeline, and writes updated HEADWAY_DATA to the site.

Requires environment variables:
    CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, D1_DATABASE_ID
"""

import os
import re
import sys
from datetime import datetime

import pandas as pd

from bus_check.config import ALL_FREQUENT_ROUTES, get_phase_for_route
from bus_check.analysis.headway_analysis import (
    compute_headway_metrics,
    compute_headways_from_arrivals,
    detect_stop_arrivals,
    filter_arrivals_to_service_window,
)
from bus_check.data.d1_client import D1Client

# Route display names (matches site/headways.html)
ROUTE_NAMES = {
    "4": "Cottage Grove",
    "9": "Ashland",
    "12": "Roosevelt",
    "20": "Madison",
    "34": "South Michigan",
    "47": "47th",
    "49": "Western",
    "53": "Pulaski",
    "54": "Cicero",
    "55": "Garfield",
    "60": "Blue Island/26th",
    "63": "63rd",
    "66": "Chicago",
    "72": "North",
    "77": "Belmont",
    "79": "79th",
    "81": "Lawrence",
    "82": "Kimball/Homan",
    "95": "95th",
    "J14": "Jeffery Jump",
}


def compute_route_headway_data(d1: D1Client) -> list[dict]:
    """Compute headway metrics for all FN routes from D1 data."""
    results = []

    for route in ALL_FREQUENT_ROUTES:
        rows = d1.query_vehicle_positions_by_route(route)
        if not rows:
            print(f"  Route {route:>3s}: no data in D1")
            continue

        positions = pd.DataFrame(rows)
        if positions.empty or "pdist" not in positions.columns:
            continue

        positions["pdist"] = pd.to_numeric(positions["pdist"], errors="coerce")
        positions["tmstmp"] = pd.to_datetime(positions["tmstmp"])
        positions = positions.dropna(subset=["pdist"])

        if positions.empty:
            continue

        # Pick reference pdist at midpoint of observed range
        min_pdist = positions["pdist"].min()
        max_pdist = positions["pdist"].max()
        reference_pdist = int((min_pdist + max_pdist) / 2)

        try:
            arrivals = detect_stop_arrivals(
                positions, reference_pdist, tolerance_feet=500
            )
            if len(arrivals) < 2:
                print(
                    f"  Route {route:>3s}: only {len(arrivals)} arrival(s), skipping"
                )
                continue

            arrivals["arrival_time"] = pd.to_datetime(arrivals["arrival_time"])
            arrivals = filter_arrivals_to_service_window(arrivals)
            if len(arrivals) < 2:
                print(
                    f"  Route {route:>3s}: <2 arrivals in service window, skipping"
                )
                continue

            headways = compute_headways_from_arrivals(arrivals)
            headways = headways[headways <= 120]  # filter outliers

            if len(headways) == 0:
                continue

            metrics = compute_headway_metrics(headways)
            phase = get_phase_for_route(route)

            results.append(
                {
                    "route": route,
                    "name": ROUTE_NAMES.get(route, route),
                    "phase": phase.phase if phase else 0,
                    "scheduled": 100,
                    "observed": round(metrics["pct_under_10"]),
                }
            )
            print(
                f"  Route {route:>3s}: {round(metrics['pct_under_10'])}% <= 10 min "
                f"({len(headways)} headways)"
            )
        except Exception as e:
            print(f"  Route {route:>3s}: error: {e}")
            continue

    # Sort by observed descending (matches current headways.html layout)
    results.sort(key=lambda d: d["observed"], reverse=True)
    return results


def build_headway_data_js(data: list[dict]) -> str:
    """Build the JavaScript HEADWAY_DATA array string."""
    lines = []
    for d in data:
        lines.append(
            f"  {{route:'{d['route']}', name:'{d['name']}', "
            f"phase:{d['phase']}, scheduled:{d['scheduled']}, "
            f"observed:{d['observed']}}}"
        )
    return "const HEADWAY_DATA = [\n" + ",\n".join(lines) + ",\n];"


def update_headways_html(html_path: str, new_data_js: str) -> None:
    """Replace the HEADWAY_DATA block in headways.html."""
    with open(html_path, "r") as f:
        content = f.read()

    # Replace the HEADWAY_DATA declaration
    pattern = r"const HEADWAY_DATA = \[.*?\];"
    new_content, count = re.subn(pattern, new_data_js, content, flags=re.DOTALL)
    if count == 0:
        raise RuntimeError("Could not find HEADWAY_DATA in headways.html")

    # Update the "Last updated" line
    month_year = datetime.now().strftime("%B %Y")
    new_content = re.sub(
        r"Last updated \w+ \d{4}",
        f"Last updated {month_year}",
        new_content,
    )

    with open(html_path, "w") as f:
        f.write(new_content)


def main() -> int:
    cf_account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    cf_token = os.environ["CLOUDFLARE_API_TOKEN"]
    db_id = os.environ["D1_DATABASE_ID"]

    d1 = D1Client(account_id=cf_account, database_id=db_id, api_token=cf_token)

    # Log collection summary
    summary = d1.get_collection_summary()
    print(f"D1 data: {summary.get('total_positions', 0)} positions, "
          f"{summary.get('routes', 0)} routes, "
          f"{summary.get('first_poll', '?')} to {summary.get('last_poll', '?')}")

    # Compute headway metrics
    print("\nComputing headway metrics:")
    data = compute_route_headway_data(d1)
    if not data:
        print("\nNo headway data computed. Skipping site update.")
        return 0

    avg_observed = sum(d["observed"] for d in data) / len(data)
    print(f"\n{len(data)} routes analyzed. Average: {avg_observed:.1f}% <= 10 min")

    # Update headways.html
    site_dir = os.path.join(os.path.dirname(__file__), "..", "site")
    html_path = os.path.normpath(os.path.join(site_dir, "headways.html"))

    new_js = build_headway_data_js(data)
    update_headways_html(html_path, new_js)
    print(f"\nUpdated {html_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
