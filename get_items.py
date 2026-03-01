import requests
import csv
import os

# --- CONFIGURATION ---
OUTPUT_FILE = "items.csv"
USER_AGENT = "brutal-black-dragon-tracker - @sdrawkcabdet"
API_URL = "https://prices.runescape.wiki/api/v1/osrs/mapping"

def fetch_item_mapping():
    print(f"Fetching item mapping from {API_URL}...")
    
    headers = {'User-Agent': USER_AGENT}
    try:
        response = requests.get(API_URL, headers=headers)
        response.raise_for_status()
        data = response.json()
        print(f"Successfully fetched {len(data)} items.")
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []

def save_to_csv(data):
    if not data:
        print("No data to save.")
        return

    # Define the columns we care about
    headers = ["id", "name", "members", "value", "highalch", "lowalch", "limit", "examine"]
    
    print(f"Saving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)
    
    print("Done.")

if __name__ == "__main__":
    items = fetch_item_mapping()
    save_to_csv(items)