"""
jumia-kenya-scraper
-------------------
Scrapes Jumia Kenya smartphone listing pages (default: pages 1-2, 100+ phones)
using a real Chromium browser (Playwright) because Jumia blocks plain requests.
Saves name, price, discount and link to Excel (.xlsx) and CSV.
 
Usage:
    py scraper.py                 # pages 1-2
    py scraper.py --pages 3       # pages 1-3
    py scraper.py --headless      # hide the browser window (may get blocked)
"""
 
import argparse
import re
import time
from pathlib import Path
 
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
 
BASE_URL = "https://www.jumia.co.ke"
LISTING_URL = BASE_URL + "/smartphones/?page={page}"
OUTPUT_DIR = Path("data")
 
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
 
 
def fetch_page(browser_page, page: int, retries: int = 3) -> str:
    """Open one listing page in the browser and return its HTML."""
    url = LISTING_URL.format(page=page)
    for attempt in range(1, retries + 1):
        try:
            browser_page.goto(url, wait_until="domcontentloaded", timeout=60000)
            browser_page.wait_for_selector("article.prd", timeout=30000)
            # scroll down so lazy-loaded items appear
            for _ in range(4):
                browser_page.mouse.wheel(0, 2500)
                browser_page.wait_for_timeout(800)
            return browser_page.content()
        except Exception as error:
            print(f"  attempt {attempt}/{retries} failed: {str(error)[:100]}")
            time.sleep(3 * attempt)
    raise RuntimeError(f"Could not fetch {url}")
 
 
def price_to_int(text: str):
    """'KSh 12,999' -> 12999 (None if no digits found)."""
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None
 
 
def parse_products(html: str) -> list[dict]:
    """Extract every product card from one listing page."""
    soup = BeautifulSoup(html, "html.parser")
    products = []
 
    for card in soup.select("article.prd"):
        link_tag = card.select_one("a.core")
        name_tag = card.select_one(".name")
        price_tag = card.select_one(".prc")
        old_price_tag = card.select_one(".old")
        discount_tag = card.select_one(".bdg._dsct")
 
        if not (link_tag and name_tag and price_tag):
            continue  # skip ads / malformed cards
 
        href = link_tag.get("href", "")
        discount_text = discount_tag.get_text(strip=True) if discount_tag else ""
 
        products.append(
            {
                "name": name_tag.get_text(strip=True),
                "price_ksh": price_to_int(price_tag.get_text()),
                "old_price_ksh": price_to_int(old_price_tag.get_text()) if old_price_tag else None,
                "discount": discount_text or "No discount",
                "link": href if href.startswith("http") else BASE_URL + href,
            }
        )
    return products
 
 
def scrape(pages: int, headless: bool) -> pd.DataFrame:
    all_products = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="en-KE",
            viewport={"width": 1366, "height": 900},
        )
        browser_page = context.new_page()
 
        for page in range(1, pages + 1):
            print(f"Scraping page {page}...")
            html = fetch_page(browser_page, page)
            found = parse_products(html)
            print(f"  found {len(found)} phones")
            all_products.extend(found)
            time.sleep(2)  # be polite to the server
 
        browser.close()
 
    df = pd.DataFrame(all_products)
    if df.empty:
        return df
    df = df.drop_duplicates(subset="link").reset_index(drop=True)
    df.index += 1
    df.index.name = "no"
    return df
 
 
def save(df: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M")
    xlsx_path = OUTPUT_DIR / f"jumia_smartphones_{stamp}.xlsx"
    csv_path = OUTPUT_DIR / f"jumia_smartphones_{stamp}.csv"
 
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Smartphones")
        sheet = writer.sheets["Smartphones"]
        for column, width in {"A": 6, "B": 60, "C": 14, "D": 16, "E": 12, "F": 70}.items():
            sheet.column_dimensions[column].width = width
        sheet.freeze_panes = "A2"
 
    df.to_csv(csv_path, encoding="utf-8-sig")  # utf-8-sig so Excel reads it correctly
    print(f"\nSaved {len(df)} phones to:\n  {xlsx_path}\n  {csv_path}")
 
 
def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Jumia Kenya smartphones.")
    parser.add_argument("--pages", type=int, default=2, help="number of pages (default: 2)")
    parser.add_argument("--headless", action="store_true", help="hide the browser window")
    args = parser.parse_args()
 
    df = scrape(args.pages, args.headless)
    if df.empty:
        print("No products found. Jumia may have changed its HTML or blocked the request.")
        return
    save(df)
 
 
if __name__ == "__main__":
    main()
 