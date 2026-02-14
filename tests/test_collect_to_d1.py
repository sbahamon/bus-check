"""Tests for the D1 collection script."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts.collect_to_d1 import should_collect


@patch("scripts.collect_to_d1.chicago_now")
def test_should_collect_weekday_in_window(mock_now):
    """Weekday 10am Chicago time should be in service window."""
    mock_now.return_value = datetime(
        2026, 2, 16, 10, 0, tzinfo=ZoneInfo("America/Chicago")
    )  # Monday
    assert should_collect() is True


@patch("scripts.collect_to_d1.chicago_now")
def test_should_collect_weekday_before_window(mock_now):
    """Weekday 5am Chicago time should be outside service window."""
    mock_now.return_value = datetime(
        2026, 2, 16, 5, 0, tzinfo=ZoneInfo("America/Chicago")
    )
    assert should_collect() is False


@patch("scripts.collect_to_d1.chicago_now")
def test_should_collect_weekday_after_window(mock_now):
    """Weekday 10pm Chicago time should be outside service window."""
    mock_now.return_value = datetime(
        2026, 2, 16, 22, 0, tzinfo=ZoneInfo("America/Chicago")
    )
    assert should_collect() is False


@patch("scripts.collect_to_d1.chicago_now")
def test_should_collect_weekend_in_window(mock_now):
    """Saturday 10am Chicago time should be in service window."""
    mock_now.return_value = datetime(
        2026, 2, 14, 10, 0, tzinfo=ZoneInfo("America/Chicago")
    )  # Saturday
    assert should_collect() is True


@patch("scripts.collect_to_d1.chicago_now")
def test_should_collect_weekend_before_window(mock_now):
    """Saturday 8am Chicago time should be outside weekend window."""
    mock_now.return_value = datetime(
        2026, 2, 14, 8, 0, tzinfo=ZoneInfo("America/Chicago")
    )
    assert should_collect() is False
