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

    match = re.search(
        r"Cena lokalu.*?([\d\s]+[.,]\d{2})\s*zł",
        normalized,
        re.IGNORECASE,
    )
    if match:
        result["price_pln"] = parse_pl_number(match.group(1))

    match = re.search(
        r"Cena za 1m.*?([\d\s]+[.,]\d{2})\s*zł",
        normalized,
        re.IGNORECASE,
    )
    if match:
        result["price_per_m2_pln"] = parse_pl_number(match.group(1))

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
