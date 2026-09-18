import argparse
import json
import re
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from adapters.skanska_adapter import fetch_apartment

STILLA_URL = "https://mieszkaj.skanska.pl/nasze-projekty/stilla/"

APARTMENT_LINK_RE = re.compile(
    r'href=["\']([^"\']*/nasze-projekty/stilla/([A-Z]{2}\d{4})/?[^"\']*)["\']',
    re.IGNORECASE,
)


def extract_apartment_codes(html):
    """
    Wyciąga kody lokali wyłącznie z linków prowadzących do stron
    konkretnych mieszkań Stilla. Sam kod nie jest jeszcze dowodem,
    że lokal jest aktualnie dostępny.
    """
    found = {}

    for href, code in APARTMENT_LINK_RE.findall(html):
        normalized_code = code.upper()
        canonical_url = urljoin(STILLA_URL, href)
        found[normalized_code] = canonical_url

    return [
        {
            "apartment_code": code,
            "source_url": found[code],
            "listing_status": "DISCOVERED",
        }
        for code in sorted(found)
    ]


def discover_apartment_codes(headless=True, max_scrolls=12):
    """
    Otwiera oficjalną stronę inwestycji Stilla i zbiera linki lokali.
    Nie obchodzi ograniczeń dostępu i nie pobiera rzutów 2D.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        try:
            page = browser.new_page()
            page.goto(
                STILLA_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            page.wait_for_timeout(2500)

            try:
                cookie = page.locator(
                    "button:has-text('Zaakceptuj'), #onetrust-accept-btn-handler"
                ).first
                if cookie.is_visible(timeout=2000):
                    cookie.click()
                    page.wait_for_timeout(750)
            except Exception:
                pass

            previous_height = 0

            for _ in range(max_scrolls):
                current_height = page.evaluate("document.body.scrollHeight")

                if current_height == previous_height:
                    break

                previous_height = current_height
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(750)

            html = page.content()
            return extract_apartment_codes(html)

        finally:
            browser.close()


def verify_discovered_apartments(records, headless=True, limit=None):
    """
    Weryfikuje odkryte kody przez istniejący SkanskaAdapter.
    Do wyniku trafia pełny rezultat PASS / FAIL / UNKNOWN.
    """
    selected = records[:limit] if limit is not None else records
    verified = []

    for record in selected:
        result = fetch_apartment(
            record["apartment_code"],
            headless=headless,
        )
        verified.append(result)

    return verified


def main():
    parser = argparse.ArgumentParser(
        description="Wykrywa kody mieszkań Skanska Stilla."
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Uruchamia Playwright z widocznym oknem przeglądarki.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Weryfikuje każdy wykryty kod przez SkanskaAdapter.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Opcjonalny limit lokali do weryfikacji.",
    )

    args = parser.parse_args()
    headless = not args.show_browser

    discovered = discover_apartment_codes(headless=headless)

    print("\n--- SKANSKA STILLA LISTING v1 ---")
    print(f"Wykryto kodów lokali: {len(discovered)}")
    print(json.dumps(discovered, ensure_ascii=False, indent=2))

    with open(
        "skanska_stilla_discovered.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(discovered, file, ensure_ascii=False, indent=2)

    print("\nZapisano: skanska_stilla_discovered.json")

    if args.verify:
        verified = verify_discovered_apartments(
            discovered,
            headless=headless,
            limit=args.limit,
        )

        with open(
            "skanska_stilla_verified.json",
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(verified, file, ensure_ascii=False, indent=2)

        pass_count = sum(
            item["identity_status"] == "PASS"
            and item["evidence_status"] == "PASS"
            for item in verified
        )
        fail_count = sum(item["identity_status"] == "FAIL" for item in verified)
        unknown_count = len(verified) - pass_count - fail_count

        print(
            f"\nWeryfikacja: PASS={pass_count}, "
            f"FAIL={fail_count}, UNKNOWN={unknown_count}"
        )
        print("Zapisano: skanska_stilla_verified.json")


if __name__ == "__main__":
    main()
