from adapters.skanska_stilla_listing import extract_apartment_codes


def test_extracts_only_stilla_apartment_links():
    html = """
    <a href="/nasze-projekty/stilla/BA0122/">BA0122</a>
    <a href="/nasze-projekty/stilla/BA0005/">BA0005</a>
    <a href="/nasze-projekty/holm-house/HH0001/">HH0001</a>
    <div>BA9999 bez linku</div>
    """

    result = extract_apartment_codes(html)

    assert [item["apartment_code"] for item in result] == [
        "BA0005",
        "BA0122",
    ]


def test_deduplicates_codes():
    html = """
    <a href="/nasze-projekty/stilla/BA0122/">Lokal</a>
    <a href="https://mieszkaj.skanska.pl/nasze-projekty/stilla/BA0122/">
        Ten sam lokal
    </a>
    """

    result = extract_apartment_codes(html)

    assert len(result) == 1
    assert result[0]["apartment_code"] == "BA0122"
    assert result[0]["listing_status"] == "DISCOVERED"


def test_normalizes_lowercase_code():
    html = """
    <a href="/nasze-projekty/stilla/ba0005/">BA0005</a>
    """

    result = extract_apartment_codes(html)

    assert result[0]["apartment_code"] == "BA0005"


def test_does_not_treat_plain_text_as_apartment():
    html = """
    <div>Powierzchnia mieszkań 26 - 76 m²</div>
    <div>BA0122</div>
    """

    assert extract_apartment_codes(html) == []
