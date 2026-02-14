"""Tests for the headway site updater."""

from scripts.update_headways import build_headway_data_js, update_headways_html


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
