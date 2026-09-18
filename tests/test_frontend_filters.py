from pathlib import Path


def test_frontend_contains_search_and_filters():
    html = Path("web/index.html").read_text(encoding="utf-8")

    required_ids = [
        'id="searchCode"',
        'id="filterRooms"',
        'id="filterFloor"',
        'id="filterAvailability"',
        'id="areaMin"',
        'id="areaMax"',
        'id="priceMin"',
        'id="priceMax"',
        'id="sortBy"',
        'id="resetFilters"',
        'id="resultsCount"',
    ]

    for marker in required_ids:
        assert marker in html


def test_frontend_contains_filter_logic():
    html = Path("web/index.html").read_text(encoding="utf-8")

    assert "function getFilteredRecords()" in html
    assert "function renderRows()" in html
    assert "function bindFilters()" in html
    assert "Brak mieszkań spełniających wybrane kryteria." in html
