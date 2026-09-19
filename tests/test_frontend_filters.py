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
        'id="activeFilters"',
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


def test_frontend_links_to_apartment_details():
    html = Path("web/index.html").read_text(encoding="utf-8")

    assert 'href="/mieszkanie/${encodeURIComponent(item.apartment_code)}"' in html


def test_apartment_detail_page_contains_required_sections():
    html = Path("web/apartment.html").read_text(encoding="utf-8")

    required_labels = [
        "Najważniejsze informacje",
        "Cena aktualna",
        "Cena przed obniżką",
        "Cena za m² aktualna",
        "Cena za m² przed obniżką",
        "Liczba pokoi",
        "Dostępne",
        "Oferta specjalna",
        "Ogródek",
        "Wiarygodność danych",
        "Tożsamość lokalu",
        "Dowody źródłowe",
        "Prawa do rzutu 2D",
        "Aktualizacja danych",
        "Otwórz ofertę dewelopera",
    ]

    for label in required_labels:
        assert label in html


def test_frontend_contains_active_filter_chips_logic():
    html = Path("web/index.html").read_text(encoding="utf-8")

    assert "function getActiveFilters()" in html
    assert "function renderActiveFilters()" in html
    assert "data-clear-filter" in html
    assert "Aktywne filtry:" in html
    assert "Brak aktywnych filtrów." in html


def test_frontend_contains_apartment_comparison():
    html = Path("web/index.html").read_text(encoding="utf-8")

    required_markers = [
        'id="compareStatus"',
        'id="compareButton"',
        'id="comparisonPanel"',
        'id="comparisonGrid"',
        'id="clearComparison"',
        'data-compare-code',
        'function updateCompareControls()',
        'function renderComparison()',
        'function clearComparison()',
        'Wybierz 2 lub 3 mieszkania do porównania.',
        'Porównanie mieszkań',
    ]

    for marker in required_markers:
        assert marker in html
