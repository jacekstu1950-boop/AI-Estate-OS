import json
import re
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright

BASE_URL = "https://mieszkaj.skanska.pl/nasze-projekty/stilla/{code}/"


def clean_text(text):
    return " ".join(text.split())


def parse_pl_number(value):
    if value is None:
        return None
    value = value.replace("\xa0", " ").strip()
    value = value.replace(" ", "")
    value = value.replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def build_url(apartment_code):
    code = apartment_code.strip().upper()
    return BASE_URL.format(code=code)


def extract_money_values(text):
    values = re.findall(
        r"(?<!\d)(\d{1,3}(?:[\s\xa0]\d{3})*(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)\s*zł",
        text,
        re.IGNORECASE,
    )
    return [
        parsed
        for value in values
        if (parsed := parse_pl_number(value)) is not None
    ]


def extract_current_previous_and_lowest(section):
    lowest_match = re.search(
        r"Najniższa cena z 30 dni przed obniżką:\s*"
        r"(\d{1,3}(?:[\s\xa0]\d{3})*(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)\s*zł",
        section,
        re.IGNORECASE,
    )
    lowest = parse_pl_number(lowest_match.group(1)) if lowest_match else None

    visible_part = re.split(
        r"Najniższa cena z 30 dni przed obniżką:",
        section,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    displayed = extract_money_values(visible_part)

    current = None
    previous = None
    if len(displayed) >= 2:
        previous = displayed[0]
        current = displayed[1]
    elif displayed:
        current = displayed[0]

    return current, previous, lowest


def extract_apartment_data(text, apartment_code, source_url):
    apartment_code = apartment_code.strip().upper()
    result = {
        "developer": "Skanska",
        "project": None,
        "apartment_code": apartment_code,
        "building": None,
        "rooms": None,
        "floor": None,
        "area_m2": None,
        "price_pln": None,
        "price_per_m2_pln": None,
        "previous_price_pln": None,
        "previous_price_per_m2_pln": None,
        "lowest_price_30d_before_reduction_pln": None,
        "lowest_price_per_m2_30d_before_reduction_pln": None,
        "special_offer": False,
        "garden_m2": None,
        "availability": None,
        "source_url": source_url,
        "retrieved_at": datetime.now().isoformat(timespec="seconds"),
        "identity_status": "UNKNOWN",
        "evidence_status": "UNKNOWN",
        "floorplan_rights_status": "UNKNOWN",
        "conflicts": [],
        "notes": [],
    }

    normalized = clean_text(text)

    if apartment_code not in normalized:
        result["identity_status"] = "FAIL"
        result["notes"].append(
            f"Nie znaleziono kodu mieszkania {apartment_code} na stronie."
        )
        return result

    result["identity_status"] = "PASS"

    if re.search(r"\bStilla\b", normalized, re.IGNORECASE):
        result["project"] = "Stilla"

    match = re.search(r"Pokoje\s+(\d+)", normalized, re.IGNORECASE)
    if match:
        result["rooms"] = int(match.group(1))

    match = re.search(r"Budynek\s+([A-Z0-9-]+)", normalized, re.IGNORECASE)
    if match:
        result["building"] = match.group(1)

    match = re.search(r"Piętro\s+(parter|\d+)", normalized, re.IGNORECASE)
    if match:
        value = match.group(1)
        result["floor"] = 0 if value.lower() == "parter" else int(value)

    match = re.search(
        r"Powierzchnia\s+(\d+[.,]\d+)\s*m",
        normalized,
        re.IGNORECASE,
    )
    if match:
        result["area_m2"] = parse_pl_number(match.group(1))

    price_section = re.search(
        r"Cena lokalu(.*?)(?=Cena za 1m|Miejsce postojowe|Boks rowerowy|Prospekt informacyjny|$)",
        normalized,
        re.IGNORECASE,
    )
    if price_section:
        current, previous, lowest = extract_current_previous_and_lowest(
            price_section.group(1)
        )
        result["price_pln"] = current
        result["previous_price_pln"] = previous
        result["lowest_price_30d_before_reduction_pln"] = lowest

    ppm_section = re.search(
        r"Cena za 1m(?:2|²|\^\{2\})?(.*?)(?="
        r"Miejsce postojowe|Boks rowerowy|Prospekt informacyjny|"
        r"Budynek|Piętro|Ogródek|Dostępne|Sprzedane|Oferta specjalna|$)",
        normalized,
        re.IGNORECASE,
    )
    if ppm_section:
        current, previous, lowest = extract_current_previous_and_lowest(
            ppm_section.group(1)
        )
        result["price_per_m2_pln"] = current
        result["previous_price_per_m2_pln"] = previous
        result["lowest_price_per_m2_30d_before_reduction_pln"] = lowest

    if re.search(r"\bOferta specjalna\b", normalized, re.IGNORECASE):
        result["special_offer"] = True

    match = re.search(
        r"Ogródek\s+(\d+[.,]\d+)\s*m",
        normalized,
        re.IGNORECASE,
    )
    if match:
        result["garden_m2"] = parse_pl_number(match.group(1))

    if re.search(r"\bDostępne\b", normalized, re.IGNORECASE):
        result["availability"] = "available"
    elif re.search(r"\bSprzedane\b", normalized, re.IGNORECASE):
        result["availability"] = "sold"
    elif re.search(
        r"Umowa deweloperska|Planowane podpisanie umowy",
        normalized,
        re.IGNORECASE,
    ):
        result["availability"] = "reserved_or_contract_process"

    mandatory = [
        result["project"],
        result["apartment_code"],
        result["building"],
        result["floor"],
        result["rooms"],
        result["area_m2"],
    ]

    if all(value is not None for value in mandatory):
        result["evidence_status"] = "PASS"
    else:
        result["evidence_status"] = "UNKNOWN"
        result["notes"].append(
            "Nie wszystkie podstawowe pola zostały jednoznacznie odczytane."
        )

    return result


def fetch_apartment(apartment_code, headless=False):
    apartment_code = apartment_code.strip().upper()
    source_url = build_url(apartment_code)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            page.goto(source_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            try:
                cookie = page.locator(
                    "button:has-text('Zaakceptuj'), #onetrust-accept-btn-handler"
                ).first
                if cookie.is_visible(timeout=2000):
                    cookie.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            body_text = page.locator("body").inner_text()
            return extract_apartment_data(body_text, apartment_code, source_url)
        finally:
            browser.close()


def main():
    if len(sys.argv) < 2:
        print("Użycie: python skanska_adapter.py KOD_MIESZKANIA")
        raise SystemExit(1)

    apartment_code = sys.argv[1].strip().upper()
    print(f"\n--- SKANSKA ADAPTER v1 / TEST {apartment_code} ---")
    print(f"Otwieranie: {build_url(apartment_code)}")

    result = fetch_apartment(apartment_code, headless=False)

    print("\n--- WYNIK ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    filename = f"skanska_{apartment_code}_test.json"
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    print(f"\nZapisano: {filename}")


if __name__ == "__main__":
    main()
