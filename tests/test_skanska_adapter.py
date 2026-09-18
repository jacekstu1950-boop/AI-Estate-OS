from adapters.skanska_adapter import extract_apartment_data


def test_ba0122_parser_pass():
    text = """
    Stilla
    BA0122
    Budynek B
    Piętro 1
    Pokoje 2
    Powierzchnia 47,49 m²
    Cena lokalu 846 775,67 zł
    Cena za 1m² 17 830,61 zł
    Dostępne
    """
    result = extract_apartment_data(
        text,
        "BA0122",
        "https://mieszkaj.skanska.pl/nasze-projekty/stilla/BA0122/",
    )

    assert result["identity_status"] == "PASS"
    assert result["evidence_status"] == "PASS"
    assert result["project"] == "Stilla"
    assert result["building"] == "B"
    assert result["floor"] == 1
    assert result["rooms"] == 2
    assert result["area_m2"] == 47.49
    assert result["price_pln"] == 846775.67
    assert result["price_per_m2_pln"] == 17830.61
    assert result["availability"] == "available"
    assert result["floorplan_rights_status"] == "UNKNOWN"


def test_ba0005_ground_floor_pass():
    text = """
    Stilla
    BA0005
    Budynek B
    Piętro parter
    Pokoje 1
    Powierzchnia 28,89 m²
    Cena lokalu 544 523,63 zł
    Cena za 1m² 18 848,17 zł
    Dostępne
    """
    result = extract_apartment_data(
        text,
        "BA0005",
        "https://mieszkaj.skanska.pl/nasze-projekty/stilla/BA0005/",
    )

    assert result["identity_status"] == "PASS"
    assert result["evidence_status"] == "PASS"
    assert result["floor"] == 0
    assert result["rooms"] == 1
    assert result["area_m2"] == 28.89


def test_missing_apartment_code_fails_without_inventing_data():
    text = """
    Stilla
    Budynek B
    Piętro 1
    Pokoje 2
    Powierzchnia 47,49 m²
    """
    result = extract_apartment_data(
        text,
        "BA0123",
        "https://mieszkaj.skanska.pl/nasze-projekty/stilla/BA0123/",
    )

    assert result["identity_status"] == "FAIL"
    assert result["evidence_status"] == "UNKNOWN"
    assert result["project"] is None
    assert result["building"] is None
    assert result["rooms"] is None
    assert result["area_m2"] is None
