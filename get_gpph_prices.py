import csv
import os
import time
import get_prices # Uses your existing tool

# --- CONFIGURATION ---
SESSION_CSV = "gpph_sessions.csv"
SNAPSHOT_DIR = "price_snapshots"

if not os.path.exists(SNAPSHOT_DIR): os.makedirs(SNAPSHOT_DIR)

def main():
    print("--- GP/Hour Price Fetcher (High Fidelity) ---")
    if not os.path.exists(SESSION_CSV): return print("No sessions file found. Run ingest first.")

    # 1. Find needed timestamps
    needed = set()
    with open(SESSION_CSV, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['wiki_pricing_timestamp']: needed.add(int(row['wiki_pricing_timestamp']))

    # 2. Check existing
    existing = {int(f.split('_')[1].split('.')[0]) for f in os.listdir(SNAPSHOT_DIR) if f.startswith("prices_")}
    missing = sorted(list(needed - existing))

    if not missing: return print("All price snapshots are up to date.")

    print(f"Downloading {len(missing)} snapshots...")
    for ts in missing:
        print(f"Fetching: {ts}")
        data, valid_ts = get_prices.fetch_prices(ts) # Calls your utility script
        
        if data:
            path = os.path.join(SNAPSHOT_DIR, f"prices_{valid_ts}.csv")
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                # CAPTURE EVERYTHING
                w.writerow(["item_id", "avgHighPrice", "highPriceVolume", "avgLowPrice", "lowPriceVolume"])
                
                for iid, d in data.items():
                    w.writerow([
                        iid,
                        d.get('avgHighPrice') or 0,
                        d.get('highPriceVolume') or 0,
                        d.get('avgLowPrice') or 0,
                        d.get('lowPriceVolume') or 0
                    ])
            time.sleep(1) # Politeness
        else:
            print(f"Warning: No data for {ts}")

if __name__ == "__main__":
    main()