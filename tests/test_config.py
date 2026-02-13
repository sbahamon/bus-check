from datetime import date

from bus_check.config import (
    ALL_FREQUENT_ROUTES,
    FREQUENT_NETWORK_PHASES,
    HEADWAY_PROMISE_MINUTES,
    SERVICE_WINDOW_WEEKDAY,
    SERVICE_WINDOW_WEEKEND,
    get_phase_for_route,
    get_launch_date,
    is_in_service_window,
)


def test_all_frequent_routes_has_20():
    assert len(ALL_FREQUENT_ROUTES) == 20


def test_all_frequent_routes_no_duplicates():
    assert len(ALL_FREQUENT_ROUTES) == len(set(ALL_FREQUENT_ROUTES))


def test_phases_cover_all_routes():
    routes_from_phases = []
    for phase in FREQUENT_NETWORK_PHASES:
        routes_from_phases.extend(phase.routes)
    assert sorted(routes_from_phases) == sorted(ALL_FREQUENT_ROUTES)


def test_phases_are_chronologically_ordered():
    dates = [p.launch_date for p in FREQUENT_NETWORK_PHASES]
    assert dates == sorted(dates)


def test_phase_1_launch_date():
    assert FREQUENT_NETWORK_PHASES[0].launch_date == date(2025, 3, 23)


def test_phase_2_launch_date():
    assert FREQUENT_NETWORK_PHASES[1].launch_date == date(2025, 6, 15)


def test_phase_3_launch_date():
    assert FREQUENT_NETWORK_PHASES[2].launch_date == date(2025, 8, 17)


def test_phase_4_launch_date():
    assert FREQUENT_NETWORK_PHASES[3].launch_date == date(2025, 12, 21)


def test_headway_promise():
    assert HEADWAY_PROMISE_MINUTES == 10


def test_service_window_weekday():
    assert SERVICE_WINDOW_WEEKDAY == (6, 21)


def test_service_window_weekend():
    assert SERVICE_WINDOW_WEEKEND == (9, 21)


def test_get_phase_for_route_phase_1():
    phase = get_phase_for_route("79")
    assert phase.phase == 1


def test_get_phase_for_route_phase_4():
    phase = get_phase_for_route("9")
    assert phase.phase == 4


def test_get_phase_for_route_j14():
    phase = get_phase_for_route("J14")
    assert phase.phase == 1


def test_get_phase_for_route_route_20_phase_2():
    """Route 20 was moved from Phase 3 to Phase 2 (confirmed Jun 2025 batch)."""
    phase = get_phase_for_route("20")
    assert phase.phase == 2


def test_get_phase_for_route_route_53_phase_3():
    """Route 53 was moved from Phase 2 to Phase 3 (confirmed Aug 17 batch)."""
    phase = get_phase_for_route("53")
    assert phase.phase == 3


def test_get_phase_for_route_unknown():
    assert get_phase_for_route("999") is None


def test_get_launch_date():
    assert get_launch_date("54") == date(2025, 3, 23)
    assert get_launch_date("66") == FREQUENT_NETWORK_PHASES[1].launch_date
    assert get_launch_date("999") is None


def test_is_in_service_window_weekday():
    assert is_in_service_window(hour=8, is_weekday=True) is True
    assert is_in_service_window(hour=6, is_weekday=True) is True
    assert is_in_service_window(hour=20, is_weekday=True) is True
    assert is_in_service_window(hour=5, is_weekday=True) is False
    assert is_in_service_window(hour=21, is_weekday=True) is False


def test_is_in_service_window_weekend():
    assert is_in_service_window(hour=10, is_weekday=False) is True
    assert is_in_service_window(hour=9, is_weekday=False) is True
    assert is_in_service_window(hour=8, is_weekday=False) is False
    assert is_in_service_window(hour=21, is_weekday=False) is False
