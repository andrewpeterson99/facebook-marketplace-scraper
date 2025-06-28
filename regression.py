import os
import json
import re
import pandas as pd
from pathlib import Path
from datetime import datetime
from sklearn.linear_model import LinearRegression
import winsound  # for alert sound on Windows

# Configuration
globals = {
    'JSON_DIR': Path('json_data/'),
    'ARCHIVE_DIR': Path('archive/'),
    'OUTPUT_DIR': Path('best_deal_output/'),
    'ALERT_THRESHOLD': -1500,  # residual less than this triggers alert
    'CURRENT_YEAR': 2025,
    'ALERTED_FILE': Path('alerted_deals.json')
}

globals['ARCHIVE_DIR'].mkdir(exist_ok=True)
globals['OUTPUT_DIR'].mkdir(exist_ok=True)
# Initialize alerted file as an empty dict if it doesn't exist
def init_alerted_file():
    if not globals['ALERTED_FILE'].exists():
        globals['ALERTED_FILE'].write_text(json.dumps({}))
init_alerted_file()


def load_alerted_links():
    try:
        data = json.loads(globals['ALERTED_FILE'].read_text())
        # expecting a dict: {link: alerted_at}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_alerted_links(links_dict):
    with globals['ALERTED_FILE'].open('w', encoding='utf-8') as f:
        json.dump(links_dict, f, indent=2)


def load_records(json_dir):
    files = json_dir.glob('*.json')
    records, seen_links = [], set()
    for fp in files:
        try:
            data = json.load(fp.open(encoding='utf-8'))
        except json.JSONDecodeError:
            print(f"Skipping invalid JSON: {fp}")
            continue
        for rec in data:
            if rec.get('name') == 'No Title' and rec.get('price') == 'No Price':
                continue
            link = rec.get('link')
            if not link or link in seen_links:
                continue
            seen_links.add(link)
            records.append(rec)
    return records


def preprocess_df(records):
    df = pd.DataFrame(records)
    df['price_val'] = pd.to_numeric(df['price'].str.replace(r"[^0-9.]", "", regex=True), errors='coerce')
    df['miles_val'] = pd.to_numeric(df['miles'].str.replace(r"[^0-9.]", "", regex=True), errors='coerce')
    df['year_val'] = pd.to_numeric(df['name'].str.extract(r"((?:19|20)\d{2})")[0], errors='coerce')
    df = df.dropna(subset=['price_val', 'miles_val', 'year_val'])
    df = df[df['year_val'] >= 2010]
    df['age'] = globals['CURRENT_YEAR'] - df['year_val']
    return df


def fit_and_score(df):
    X = df[['age', 'miles_val']].values
    y = df['price_val'].values
    model = LinearRegression().fit(X, y)
    df['predicted_price'] = model.predict(df[['age', 'miles_val']])
    df['residual'] = df['price_val'] - df['predicted_price']
    return df


def alert_if_needed(best_deals, alerted_dict):
    candidates = best_deals[best_deals['residual'] <= globals['ALERT_THRESHOLD']]
    new_deals = {}
    for link in candidates['link']:
        if link not in alerted_dict:
            alerted_dict[link] = datetime.now().isoformat()
            new_deals[link] = alerted_dict[link]
    if new_deals:
        print(f"*** ALERT: {len(new_deals)} new deal(s) found ***")
        for _ in range(3):
            winsound.Beep(1000, 300)
    return alerted_dict


def archive_records(records):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = globals['ARCHIVE_DIR'] / f'all_records_{ts}.json'
    with out_path.open('w', encoding='utf-8') as f:
        json.dump(records, f, indent=2)
    print(f"Archived {len(records)} records to {out_path}")


def main():
    records = load_records(globals['JSON_DIR'])
    archive_records(records)

    alerted_links = load_alerted_links()

    df = preprocess_df(records)
    df = fit_and_score(df)
    best_deals = df.nsmallest(25, 'residual')

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = globals['OUTPUT_DIR'] / f'{ts}_best_deals.csv'
    best_deals.to_csv(csv_path, index=False)
    print(f"Saved best deals to: {csv_path}")

    updated = alert_if_needed(best_deals, alerted_links)
    save_alerted_links(updated)

if __name__ == '__main__':
    main()
