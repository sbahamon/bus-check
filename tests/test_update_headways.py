"""Tests for the headway site updater."""

from scripts.update_headways import (
    build_collection_stats,
    build_headway_data_js,
    update_headways_html,
    update_prose,
)


def test_build_headway_data_js_single_route():
    """Should produce valid JS array syntax for a single route."""
    data = [
        {
            "route": "79",
            "name": "79th",
            "phase": 1,
            "scheduled": 100,
            "observed": 74,
        }
    ]
    js = build_headway_data_js(data)
    assert "const HEADWAY_DATA = [" in js
    assert "route:'79'" in js
    assert "observed:74" in js
    assert js.endswith("];")


def test_build_headway_data_js_multiple_routes():
    """Should produce valid JS array with multiple entries."""
    data = [
        {"route": "79", "name": "79th", "phase": 1, "scheduled": 100, "observed": 74},
        {"route": "9", "name": "Ashland", "phase": 4, "scheduled": 97, "observed": 32},
    ]
    js = build_headway_data_js(data)
    assert "route:'79'" in js
    assert "route:'9'" in js
    assert js.count("{route:") == 2


def test_update_headways_html_replaces_data(tmp_path):
    """Should replace HEADWAY_DATA block in HTML file."""
    html = """<script>
const HEADWAY_DATA = [
  {route:'79', name:'79th', phase:1, scheduled:100, observed:50},
];
</script>
<p>Last updated January 2026</p>"""

    html_file = tmp_path / "headways.html"
    html_file.write_text(html)

    new_js = "const HEADWAY_DATA = [\n  {route:'79', name:'79th', phase:1, scheduled:100, observed:74},\n];"
    update_headways_html(str(html_file), new_js)

    updated = html_file.read_text()
    assert "observed:74" in updated
    assert "observed:50" not in updated


def test_update_headways_html_updates_date(tmp_path):
    """Should update the 'Last updated' date."""
    html = "<p>Last updated January 2026</p>\nconst HEADWAY_DATA = [];"
    html_file = tmp_path / "headways.html"
    html_file.write_text(html)

    update_headways_html(str(html_file), "const HEADWAY_DATA = [];")
    updated = html_file.read_text()
    # Should have current month/year instead of January 2026
    assert "Last updated January 2026" not in updated or "Last updated February 2026" in updated


def test_update_headways_html_no_match_raises(tmp_path):
    """Should raise if HEADWAY_DATA is not found."""
    html = "<p>No data here</p>"
    html_file = tmp_path / "headways.html"
    html_file.write_text(html)

    try:
        update_headways_html(str(html_file), "const HEADWAY_DATA = [];")
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "Could not find HEADWAY_DATA" in str(e)


# --- Collection stats ---


def test_build_collection_stats_computes_hours():
    """Should compute hours from first/last poll timestamps."""
    summary = {
        "total_positions": 50000,
        "first_poll": "2026-02-14T00:00:00+00:00",
        "last_poll": "2026-02-21T12:00:00+00:00",
    }
    stats = build_collection_stats(summary)
    assert stats["total_hours"] == 180  # 7.5 days = 180 hours
    assert stats["total_positions"] == 50000
    assert "Feb 14" in stats["date_range"]
    assert "21" in stats["date_range"]


def test_build_collection_stats_same_day():
    """Should handle single-day collection."""
    summary = {
        "total_positions": 358,
        "first_poll": "2026-02-14T00:31:00+00:00",
        "last_poll": "2026-02-14T00:31:00+00:00",
    }
    stats = build_collection_stats(summary)
    assert stats["total_hours"] == 0
    assert "Feb 14" in stats["date_range"]


def test_build_collection_stats_multi_month():
    """Should format date range across months."""
    summary = {
        "total_positions": 100000,
        "first_poll": "2026-01-28T10:00:00+00:00",
        "last_poll": "2026-03-15T18:00:00+00:00",
    }
    stats = build_collection_stats(summary)
    assert "Jan 28" in stats["date_range"]
    assert "Mar 15" in stats["date_range"]


# --- Prose updates ---


def test_update_prose_replaces_hours_and_dates():
    """Should replace hardcoded hours and date ranges in HTML."""
    html = (
        '<p>approximately <strong>45 hours</strong> across February 11&ndash;13, 2026.</p>'
        '<p>45 hours of data across three weekdays</p>'
        '<dd>CTA Bus Tracker API &middot; ~45 hours collected (Feb 11&ndash;13, 2026)</dd>'
    )
    stats = {
        "total_hours": 336,
        "total_positions": 100000,
        "date_range": "Feb 14&ndash;Mar 1, 2026",
        "is_preliminary": False,
    }
    result = update_prose(html, stats)
    assert "45 hours" not in result
    assert "336 hours" in result
    assert "Feb 14" in result


def test_update_prose_replaces_current_format():
    """Should replace the current 'of ... collection (DATE)' format."""
    html = (
        '<p>Currently approximately <strong>0 hours</strong> of automated collection (Feb 14, 2026).</p>'
        '<dd>CTA Bus Tracker API &middot; ~0 hours collected (Feb 14, 2026) &middot; Updated daily</dd>'
    )
    stats = {
        "total_hours": 65,
        "total_positions": 465000,
        "date_range": "Feb 11&ndash;14, 2026",
        "is_preliminary": True,
    }
    result = update_prose(html, stats)
    assert "0 hours" not in result
    assert "65 hours" in result
    assert "Feb 11" in result


def test_update_prose_idempotent():
    """Running update_prose twice with different stats should update correctly both times."""
    html = (
        '<p>Currently approximately <strong>45 hours</strong> across February 11&ndash;13, 2026.</p>'
        '<dd>CTA Bus Tracker API &middot; ~45 hours collected (Feb 11&ndash;13, 2026)</dd>'
        '<li>~45 hours of automated real-time collection so far.</li>'
    )
    stats_first = {
        "total_hours": 65,
        "total_positions": 465000,
        "date_range": "Feb 11&ndash;14, 2026",
        "is_preliminary": True,
    }
    result1 = update_prose(html, stats_first)
    assert "65 hours" in result1

    # Run again with new stats — should replace the first run's output
    stats_second = {
        "total_hours": 200,
        "total_positions": 800000,
        "date_range": "Feb 11&ndash;20, 2026",
        "is_preliminary": True,
    }
    result2 = update_prose(result1, stats_second)
    assert "65 hours" not in result2
    assert "200 hours" in result2
    assert "Feb 11&ndash;20" in result2


def test_update_prose_methodology_bullet():
    """Should replace the methodology page ~N hours bullet."""
    html = '<li><strong>Headway data is growing.</strong> ~0 hours of automated real-time collection so far. Data accumulates daily.</li>'
    stats = {
        "total_hours": 65,
        "total_positions": 465000,
        "date_range": "Feb 11&ndash;14, 2026",
        "is_preliminary": True,
    }
    result = update_prose(html, stats)
    assert "~65 hours of real-time collection (Feb 11" in result
    assert "automated" not in result


def test_update_prose_preliminary_caveat_stays_when_preliminary():
    """Should keep preliminary warning when < 336 hours."""
    html = (
        '    <div class="callout-warning">\n'
        '      <p><strong>Preliminary data.</strong> These results are based on approximately 45 hours of real-time data collection across February 11&ndash;13, 2026. Robust conclusions require at least two weeks of continuous monitoring. Treat these as early indicators, not definitive findings.</p>\n'
        '    </div>'
    )
    stats = {
        "total_hours": 100,
        "total_positions": 30000,
        "date_range": "Feb 14&ndash;20, 2026",
        "is_preliminary": True,
    }
    result = update_prose(html, stats)
    assert "Preliminary data" in result
    assert "100 hours" in result


def test_update_prose_preliminary_caveat_current_format():
    """Should update the callout even with the current 'automated' text format."""
    html = (
        '    <div class="callout-warning">\n'
        '      <p><strong>Preliminary data.</strong> These results are based on approximately 0 hours of automated real-time data collection (Feb 14, 2026). Collection runs every 30 minutes via GitHub Actions and this page updates daily. Robust conclusions require at least two weeks of continuous monitoring. Treat these as early indicators, not definitive findings.</p>\n'
        '    </div>'
    )
    stats = {
        "total_hours": 65,
        "total_positions": 465000,
        "date_range": "Feb 11&ndash;14, 2026",
        "is_preliminary": True,
    }
    result = update_prose(html, stats)
    assert "Preliminary data" in result
    assert "65 hours" in result
    assert "Robust conclusions" in result


def test_update_prose_preliminary_caveat_replaced_when_robust():
    """Should replace preliminary warning when >= 336 hours (2 weeks)."""
    html = (
        '    <div class="callout-warning">\n'
        '      <p><strong>Preliminary data.</strong> These results are based on approximately 65 hours of real-time data collection (Feb 11&ndash;14, 2026). Collection runs every 30 minutes via GitHub Actions and this page updates daily. Robust conclusions require at least two weeks of continuous monitoring. Treat these as early indicators, not definitive findings.</p>\n'
        '    </div>'
    )
    stats = {
        "total_hours": 500,
        "total_positions": 150000,
        "date_range": "Feb 14&ndash;Mar 7, 2026",
        "is_preliminary": False,
    }
    result = update_prose(html, stats)
    assert "Preliminary data" not in result
    assert "callout-info" in result
    assert "500 hours" in result
