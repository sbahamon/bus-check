from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class FrequentNetworkPhase:
    phase: int
    launch_date: date
    routes: list[str]
    label: str


FREQUENT_NETWORK_PHASES = [
    FrequentNetworkPhase(
        phase=1,
        launch_date=date(2025, 3, 23),
        routes=["J14", "34", "47", "54", "60", "63", "79", "95"],
        label="Phase 1 (Mar 23, 2025)",
    ),
    FrequentNetworkPhase(
        phase=2,
        launch_date=date(2025, 6, 15),  # Confirmed: Jun 15, 2025
        routes=["4", "20", "49", "66"],
        label="Phase 2 (Jun 2025)",
    ),
    FrequentNetworkPhase(
        phase=3,
        launch_date=date(2025, 8, 17),  # Confirmed: Aug 17, 2025
        routes=["53", "55", "77", "82"],
        label="Phase 3 (Aug 2025)",
    ),
    FrequentNetworkPhase(
        phase=4,
        launch_date=date(2025, 12, 21),
        routes=["9", "12", "72", "81"],
        label="Phase 4 (Dec 21, 2025)",
    ),
]

ALL_FREQUENT_ROUTES: list[str] = [
    route for phase in FREQUENT_NETWORK_PHASES for route in phase.routes
]

SERVICE_WINDOW_WEEKDAY = (6, 21)  # 6am–9pm
SERVICE_WINDOW_WEEKEND = (9, 21)  # 9am–9pm
HEADWAY_PROMISE_MINUTES = 10

SODA_RIDERSHIP_ENDPOINT = "https://data.cityofchicago.org/resource/jyb9-n7fm.json"
BUS_TRACKER_BASE_URL = "http://www.ctabustracker.com/bustime/api/v2"
GTFS_DOWNLOAD_URL = (
    "http://www.transitchicago.com/downloads/sch_data/google_transit.zip"
)


def get_phase_for_route(route: str) -> FrequentNetworkPhase | None:
    for phase in FREQUENT_NETWORK_PHASES:
        if route in phase.routes:
            return phase
    return None


def get_launch_date(route: str) -> date | None:
    phase = get_phase_for_route(route)
    return phase.launch_date if phase else None


def is_in_service_window(hour: int, is_weekday: bool) -> bool:
    start, end = SERVICE_WINDOW_WEEKDAY if is_weekday else SERVICE_WINDOW_WEEKEND
    return start <= hour < end
