from playwright.sync_api import sync_playwright
import time
from bs4 import BeautifulSoup
import json
from decouple import config
import re
import argparse
from pathlib import Path

# Import regression pipeline
import regression

email = config('EMAIL')
password = config('PASSWORD')

# Directory to store raw JSON data
JSON_DATA_DIR = Path('json_data/')
JSON_DATA_DIR.mkdir(exist_ok=True)

def crawl_facebook_marketplace(city: str, query: str, max_price: int, min_price: int) -> Path:
    cities = {
        'New York': 'nyc',
        'Los Angeles': 'la',
        'Las Vegas': 'vegas',
        'Chicago': 'chicago',
        'Houston': 'houston',
        'San Antonio': 'sanantonio',
        'Miami': 'miami',
        'Orlando': 'orlando',
        'San Diego': 'sandiego',
        'Arlington': 'arlington',
        'Balitmore': 'baltimore',
        'Cincinnati': 'cincinnati',
        'Denver': 'denver',
        'Fort Worth': 'fortworth',
        'Jacksonville': 'jacksonville',
        'Memphis': 'memphis',
        'Nashville': 'nashville',
        'Philadelphia': 'philly',
        'Portland': 'portland',
        'San Jose': 'sanjose',
        'Tucson': 'tucson',
        'Atlanta': 'atlanta',
        'Boston': 'boston',
        'Columnbus': 'columbus',
        'Detroit': 'detroit',
        'Honolulu': 'honolulu',
        'Kansas City': 'kansascity',
        'New Orleans': 'neworleans',
        'Phoenix': 'phoenix',
        'Seattle': 'seattle',
        'Washington DC': 'dc',
        'Milwaukee': 'milwaukee',
        'Sacremento': 'sac',
        'Austin': 'austin',
        'Charlotte': 'charlotte',
        'Dallas': 'dallas',
        'El Paso': 'elpaso',
        'Indianapolis': 'indianapolis',
        'Louisville': 'louisville',
        'Minneapolis': 'minneapolis',
        'Oaklahoma City': 'oklahoma',
        'Pittsburgh': 'pittsburgh',
        'San Francisco': 'sanfrancisco',
        'Tampa': 'tampa',
        'Salt Lake City': 'saltlakecity',
        'Provo': 'provo',
    }

    if city in cities:
        city_param = cities[city]
    else:
        print(f"Warning: '{city}' is not a directly supported city. The scraper might still work, but results could be less localized.")
        city_param = city.capitalize()

    marketplace_url = (
        f'https://www.facebook.com/marketplace/106066949424984/search/'
        f'?query={query}&maxPrice={max_price}&minPrice={min_price}&exact=false'
    )
    parsed = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(marketplace_url)

        print("Waiting for page to load...")
        time.sleep(5)

        # apply filters
        try:
            close_button = page.locator('div[aria-label="Close"]')
            if close_button.count() > 0:
                close_button.first.click()
                time.sleep(1)

           # 1. Click the "Date listed" button to open its options.
            #    get_by_role is perfect for buttons.
            date_listed_button = page.get_by_role("button", name="Date listed", exact=True)
            date_listed_button.click()
            # 2. Select the "Last 7 days" option.
            #    Playwright's click action automatically waits for the element to be visible,
            #    so time.sleep(1) is not needed. get_by_text is great for options in a menu.
            last_7_days_option = page.get_by_text("Last 7 days", exact=True)
            last_7_days_option.click()

            # 3. Click the "Sort by" button to open its options.
            #    Again, we apply the exact same fix that worked for "Date listed".
            sort_by_button = page.get_by_role("button", name="Sort by", exact=True)
            sort_by_button.click()

            # 4. Select the sorting method.
            #    We use get_by_text again for the option that appears.
            newest_first_option = page.get_by_text("Date listed: Newest first", exact=True)
            newest_first_option.click()

        except Exception as e:
            print(f"Error during sorting/filtering: {e}")

        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        listings = soup.find_all('div', class_='x9f619 x78zum5 x1r8uery xdt5ytf x1iyjqo2 xs83m0k x135b78x x11lfxj5 x1iorvi4 xjkvuk6 xnpuxes x1cjf5ee x17dddeq')

        for listing in listings:
            try:
                title = listing.find('span', class_='x1lliihq').text or "No Title"
                price = listing.find('span', class_='x193iq5w').text or "No Price"
                link_tag = listing.find('a', href=True)
                post_url = f"https://www.facebook.com{link_tag['href']}" if link_tag else "No URL"
                location = listing.find('span', class_='x1j85h84').text or "No Location"
                miles = next((st.text for st in listing.find_all('span', class_='x1j85h84') if 'miles' in st.text), "")

                parsed.append({
                    'name': title,
                    'price': price,
                    'location': location,
                    'title': title,
                    'link': post_url,
                    'miles': miles
                })
            except Exception as e:
                print(f"Error parsing listing: {e}")

        browser.close()

    # Save JSON to data dir
    ts = time.strftime("%Y-%m-%d_%H-%M-%S")
    sanitized = re.sub(r'[^\w]+', '_', query)
    filename = JSON_DATA_DIR / f"{sanitized}_{ts}.json"
    with filename.open('w', encoding='utf-8') as f:
        json.dump(parsed, f, indent=4)
    print(f"Results saved to: {filename}")

    return filename

if __name__ == "__main__":
    # Run crawler
    json_file = crawl_facebook_marketplace(
        'Provo', 'car', 8000, 2000
    )

    # TODO: now run the regression by calling the main() function
    # from regression.py to process all JSON in json_data/
    print("Running regression pipeline...")
    regression.main()
