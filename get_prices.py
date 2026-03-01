import requests
import csv
import argparse
import time
from datetime import datetime
import os

# --- CONFIGURATION ---
USER_AGENT = "brutal-black-dragon-tracker - @sdrawkcabdet"
API_URL = "https://prices.runescape.wiki/api/v1/osrs/1h"

def get_timestamp(date_str=None):
    """Parses a date string or returns current time if None."""
    if date_str:
        # Try parsing standard formats
        try:
            dt = datetime.fromisoformat(date_str)
        except ValueError:
            try:
                # Try common human format: "YYYY-MM-DD HH:MM"
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            except ValueError:
                print("Error: Could not parse date. Use 'YYYY-MM-DD HH:MM' or ISO format.")
                exit(1)
    else:
        dt = datetime.now()
        
    return int(dt.timestamp())

def fetch_prices(timestamp):
    # Round down to nearest 3600s (1 hour)
    bucket_timestamp = timestamp - (timestamp % 3600)
    readable_time = datetime.fromtimestamp(bucket_timestamp).strftime('%Y-%m-%d %H:%M')
    
    print(f"Target Time: {readable_time}")
    print(f"Bucket Timestamp: {bucket_timestamp}")
    
    headers = {'User-Agent': USER_AGENT}
    params = {'timestamp': bucket_timestamp}
    
    try:
        response = requests.get(API_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('data', {}), bucket_timestamp
    except requests.exceptions.RequestException as e:
        print(f"Error fetching prices: {e}")
        return {}, bucket_timestamp

def save_prices_csv(price_data, timestamp, folder=None):
    if not price_data:
        print("No price data found for this timestamp.")
        return

    # Use Unix Timestamp for filename
    filename = f"prices_{timestamp}.csv"
    
    # Prepend folder if provided
    if folder:
        # Create folder if it doesn't exist
        if not os.path.exists(folder):
            os.makedirs(folder)
        filepath = os.path.join(folder, filename)
    else:
        filepath = filename
    
    human_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
    print(f"Saving {len(price_data)} prices to {filepath} ({human_time})...")
    
    with open(filepath, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["item_id", "avgHighPrice", "highPriceVolume", "avgLowPrice", "lowPriceVolume"])
        
        for item_id, stats in price_data.items():
            writer.writerow([
                item_id,
                stats.get('avgHighPrice', 0) or 0,
                stats.get('highPriceVolume', 0) or 0,
                stats.get('avgLowPrice', 0) or 0,
                stats.get('lowPriceVolume', 0) or 0
            ])
    
    print("Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch OSRS item prices for a specific time.")
    parser.add_argument("time", nargs="?", help="Time string (e.g. '2026-02-04 18:30'). Defaults to now.")
    
    args = parser.parse_args()
    
    ts = get_timestamp(args.time)
    prices, valid_ts = fetch_prices(ts)
    save_prices_csv(prices, valid_ts)