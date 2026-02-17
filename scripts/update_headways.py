"""Analyze headway data from D1 and update site/headways.html.

Reads vehicle positions from Cloudflare D1, runs the existing headway
analysis pipeline, and writes updated HEADWAY_DATA to the site.

Requires environment variables:
    CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, D1_DATABASE_ID
"""

import math
import os
import re
import sys
from datetime import datetime

import pandas as pd
from dateutil.parser import parse as parse_dt

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
            arrivals = detect_stop_arrivals(positions, reference_pdist)
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


def build_collection_stats(summary: dict) -> dict:
    """Compute human-readable collection stats from D1 summary."""
    first = parse_dt(summary["first_poll"])
    last = parse_dt(summary["last_poll"])
    total_hours = math.floor((last - first).total_seconds() / 3600)

    # Format date range: "Feb 14&ndash;Mar 1, 2026" or "Feb 14&ndash;21, 2026"
    if first.month == last.month and first.year == last.year:
        date_range = (
            f"{first.strftime('%b %-d')}&ndash;{last.strftime('%-d')}, "
            f"{last.strftime('%Y')}"
        )
    else:
        date_range = (
            f"{first.strftime('%b %-d')}&ndash;{last.strftime('%b %-d')}, "
            f"{last.strftime('%Y')}"
        )

    TWO_WEEKS_HOURS = 336  # 14 days × 24 hours
    return {
        "total_hours": total_hours,
        "total_positions": summary.get("total_positions", 0),
        "date_range": date_range,
        "is_preliminary": total_hours < TWO_WEEKS_HOURS,
    }


def update_prose(content: str, stats: dict) -> str:
    """Replace hardcoded collection stats in HTML with current values.

    All patterns are idempotent: they match both the original hand-written
    text AND their own previous output, so the script can run repeatedly.
    """
    hours = stats["total_hours"]
    date_range = stats["date_range"]

    # Pattern 1: "<strong>N hours</strong> of ... collection (DATE)."
    # Matches "across DATE." (original) and "of QUALIFIER collection (DATE)." (updated)
    content = re.sub(
        r"approximately <strong>\d+ hours</strong> (?:of [^.]+\.|across [^.]+\.)",
        f"approximately <strong>{hours} hours</strong> of real-time collection "
        f"({date_range}).",
        content,
    )

    # Pattern 2: "N hours of data across/collected ..."
    content = re.sub(
        r"\d+ hours of data (?:across|collected) [^.]+",
        f"{hours} hours of data collected ({date_range})",
        content,
    )

    # Pattern 3: "~N hours collected (DATE)" in footer
    content = re.sub(
        r"~\d+ hours collected \([^)]+\)",
        f"~{hours} hours collected ({date_range})",
        content,
    )

    # Pattern 4: "~N hours of [automated] real-time collection ..." in methodology
    content = re.sub(
        r"(?:Only )?~\d+ hours of (?:automated )?real-time collection[^.]*\.",
        f"~{hours} hours of real-time collection ({date_range}).",
        content,
    )

    # Pattern 5: Update the preliminary caveat based on data volume
    if not stats["is_preliminary"]:
        # Replace warning/info callout with info callout
        content = re.sub(
            r'<div class="callout-(?:warning|info)">\s*<p><strong>'
            r"(?:Preliminary data|Continuously updated)\.</strong>"
            r"[^<]*</p>\s*</div>",
            f'<div class="callout-info">\n'
            f"      <p><strong>Continuously updated.</strong> These results are based on "
            f"{hours} hours of real-time data collection "
            f"({date_range}). Data is collected every 5 minutes via a Cloudflare Worker and "
            f"this page updates daily.</p>\n"
            f"    </div>",
            content,
        )
    else:
        # Keep warning but update the stats between anchors
        content = re.sub(
            r"(<div\s+class=\"callout-warning\">\s*<p><strong>Preliminary data\.</strong>)"
            r".*?(Robust conclusions)",
            rf"\1 These results are based on approximately {hours} hours of "
            rf"real-time data collection ({date_range}). "
            rf"Collection runs every 5 minutes via a Cloudflare Worker and this page "
            rf"updates daily. \2",
            content,
            flags=re.DOTALL,
        )

    return content


def update_headways_html(
    html_path: str, new_data_js: str, stats: dict | None = None
) -> None:
    """Replace the HEADWAY_DATA block and prose in headways.html."""
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

    # Update prose (hours, dates, caveats) if stats provided
    if stats:
        new_content = update_prose(new_content, stats)

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

    # Compute collection stats for prose updates
    stats = build_collection_stats(summary)
    print(f"Collection: {stats['total_hours']} hours, {stats['date_range']}, "
          f"preliminary={stats['is_preliminary']}")

    # Update headways.html
    site_dir = os.path.join(os.path.dirname(__file__), "..", "site")
    html_path = os.path.normpath(os.path.join(site_dir, "headways.html"))

    new_js = build_headway_data_js(data)
    update_headways_html(html_path, new_js, stats)
    print(f"Updated {html_path}")

    # Update methodology.html prose (hours/dates only, no HEADWAY_DATA)
    meth_path = os.path.normpath(os.path.join(site_dir, "methodology.html"))
    if os.path.exists(meth_path):
        with open(meth_path, "r") as f:
            meth_content = f.read()
        meth_content = update_prose(meth_content, stats)
        month_year = datetime.now().strftime("%B %Y")
        meth_content = re.sub(
            r"Last updated \w+ \d{4}",
            f"Last updated {month_year}",
            meth_content,
        )
        with open(meth_path, "w") as f:
            f.write(meth_content)
        print(f"Updated {meth_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
