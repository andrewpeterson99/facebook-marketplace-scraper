from playwright.sync_api import sync_playwright
import time
from bs4 import BeautifulSoup
import json
from decouple import config
import re
from pathlib import Path

import requests

email = config('EMAIL')
password = config('PASSWORD')

DISCORD_WEBHOOK_URL = config('DISCORD_WEBHOOK_URL')

# Directory to store raw JSON data
JSON_DATA_DIR = Path('json_data/')
JSON_DATA_DIR.mkdir(exist_ok=True)

SEEN_LISTINGS_FILE = Path('seen_listings.json')

def send_discord_notification(webhook_url: str, json_file_path: Path):
    """
    Reads all scraped data from a JSON file and sends a formatted notification
    to a Discord webhook, chunking listings into multiple embeds if necessary.
    """
    if not webhook_url:
        print("Warning: DISCORD_WEBHOOK_URL is not set. Skipping notification.")
        return

    try:
        with json_file_path.open('r', encoding='utf-8') as f:
            listings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading JSON file: {e}. Cannot send notification.")
        return

    # Prepare the data for Discord
    if not listings:
        data = {
            "content": f"✅ Scraping finished. No new car listings were found this time."
        }
    else:
        # --- Start of New Logic ---

        # Helper to split a list into chunks of a specific size
        def chunker(seq, size):
            return (seq[pos:pos + size] for pos in range(0, len(seq), size))

        # Discord allows max 10 embeds/message and 25 fields/embed.
        # We'll set a safe limit of 20 listings per embed.
        LISTINGS_PER_EMBED = 20
        embeds = []

        # Loop through each chunk of listings
        for i, listings_chunk in enumerate(chunker(listings, LISTINGS_PER_EMBED)):
            # Stop if we hit Discord's 10-embed limit per message
            if i >= 10:
                print(f"Warning: Found more than {10 * LISTINGS_PER_EMBED} listings. Notifying for the first {10 * LISTINGS_PER_EMBED}.")
                break
            
            # Create the embed object for this chunk
            embed = {
                "color": 3447003,  # A nice blue color
                "fields": []
            }
            
            # The very first embed gets the main title and a descriptive header
            if i == 0:
                embed["title"] = f"{len(listings)} new car listings"
                embed["description"] = "look at these cars:"

            # Add each listing in the current chunk as a field in the embed
            for listing in listings_chunk:
                price = listing.get('price', 'N/A')
                miles = f" - {listing.get('miles')}" if listing.get('miles') else ""
                embed["fields"].append({
                    "name": f"{listing.get('name', 'N/A')} — {price}",
                    "value": f"📍 {listing.get('location', 'N/A')}{miles}\n[View Listing]({listing.get('link', '#')})",
                    "inline": False
                })
            
            embeds.append(embed)

        data = {
            "content": "check these cars out <@175427752357265408>",
            "embeds": embeds  # Add our list of generated embeds
        }
        # --- End of New Logic ---

    # Send the POST request to the webhook (this part is unchanged)
    try:
        response = requests.post(webhook_url, json=data)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        print("Discord notification sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error sending Discord notification: {e}")

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

    seen_urls = load_seen_urls(SEEN_LISTINGS_FILE)
    print(f"State: Loaded {len(seen_urls)} previously seen listings.")

    new_listings = []

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
                title = listing.find('span', class_='x1lliihq x6ikm8r x10wlt62 x1n2onr6').text or "No Title"
                price = listing.find('span', class_='x193iq5w').text or "No Price"
                link_tag = listing.find('a', href=True)
                post_url = f"https://www.facebook.com{link_tag['href']}" if link_tag else "No URL"
                
                if not post_url or post_url in seen_urls:
                    continue  # Skip if we have no URL or we've already seen it.
                
                location = listing.find('span', class_='x1j85h84').text or "No Location"
                miles = next((st.text for st in listing.find_all('span', class_='x1j85h84') if 'miles' in st.text), "")

                if not filter_by_make(title):
                    continue

                new_listings.append({
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

    if not new_listings:
        print("State: No new listings found in this run.")
        return None
    
    print(f"State: Found {len(new_listings)} new listings!")
    
    # Add the newly found URLs to our master set
    for listing in new_listings:
        seen_urls.add(listing['link'])

    # Save JSON to data dir
    ts = time.strftime("%Y-%m-%d_%H-%M-%S")
    sanitized = re.sub(r'[^\w]+', '_', query)
    filename = JSON_DATA_DIR / f"{sanitized}_{ts}.json"
    with filename.open('w', encoding='utf-8') as f:
        json.dump(new_listings, f, indent=4)
    print(f"Results saved to: {filename}")

    save_seen_urls(SEEN_LISTINGS_FILE, seen_urls)

    print(f"State: Updated seen_listings.json. Total seen listings now: {len(seen_urls)}")

    return filename

def filter_by_make(title: str) -> bool:
    """
    Filter listings by make (Honda or Toyota).
    """
    title = title.lower()
    return 'honda' in title or 'toyota' in title


def load_seen_urls(filepath: Path) -> set:
    """Loads a set of URLs from our state file."""
    if not filepath.exists():
        return set()  # Return an empty set if the file doesn't exist
    try:
        with filepath.open('r', encoding='utf-8') as f:
            # A set is used for fast lookups (O(1) average time complexity)
            return set(json.load(f))
    except (json.JSONDecodeError, IOError):
        print(f"Warning: Could not read or parse {filepath}. Starting with a fresh state.")
        return set()

def save_seen_urls(filepath: Path, urls: set):
    """Saves a set of URLs back to our state file."""
    with filepath.open('w', encoding='utf-8') as f:
        # JSON doesn't know how to save a set, so we convert it to a list first
        json.dump(list(urls), f, indent=4)

if __name__ == "__main__":
    # Run crawler
    json_file = crawl_facebook_marketplace(
        'Provo', 'car', 10000, 1000
    )

    #now send a discord notification
    if json_file:
        send_discord_notification(DISCORD_WEBHOOK_URL, json_file)