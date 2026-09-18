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
        'id="applyFilters"',
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
    assert "Cena do:" in html
    assert "Wyświetlane lokale" in html
    assert "Łącznie w ofercie" in html
    assert "Zweryfikowane poprawnie" in html
    assert "Prawa do rzutu 2D" in html
    assert "function availabilityLabel(value)" in html
    assert "available') return 'Tak'" in html
    assert "unavailable') return 'Nie'" in html
    assert "DODANE:" in html
    assert "USUNIĘTE:" in html
    assert "ZMIENIONE:" in html
    assert "BEZ ZMIAN:" in html
