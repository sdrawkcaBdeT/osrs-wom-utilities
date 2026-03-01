import pandas as pd
import os

# --- CONFIGURATION ---
SESSIONS = "gpph_sessions.csv"
LEDGER = "gpph_ledger_raw.csv"
ITEMS = "items.csv"
SNAPSHOT_DIR = "price_snapshots"
OUTPUT_FILE = "gpph_enriched.csv"

def main():
    print("--- GP/Hour Enrichment (Hourly Mode) ---")
    
    # 1. Load Data
    try:
        df_sess = pd.read_csv(SESSIONS)
        df_ledg = pd.read_csv(LEDGER)
        df_items = pd.read_csv(ITEMS)
    except FileNotFoundError as e:
        return print(f"Missing required file: {e}")

    # 2. Merge Metadata
    print("Merging Sessions and Item Names...")
    df = pd.merge(df_ledg, df_sess[['session_uuid', 'name', 'local_start_time', 'wiki_pricing_timestamp']], on='session_uuid', how='left')
    
    df = pd.merge(df, df_items[['id', 'name']], left_on='item_id', right_on='id', how='left')
    df.rename(columns={'name_y': 'item_name', 'name_x': 'session_name'}, inplace=True)
    df.drop(columns=['id'], inplace=True)

    # 3. Calculate HOURLY Keys
    print("Mapping 5m Session Times to 1h Market Snapshots...")
    
    # Convert the 5m timestamp from the session file to an Hourly timestamp
    # Logic: timestamp - (timestamp % 3600)
    df['hourly_ts'] = df['wiki_pricing_timestamp'].apply(lambda x: int(x) - (int(x) % 3600))

    # 4. Load Price Cache
    print("Loading Price History...")
    price_cache = {} 
    required_ts = df['hourly_ts'].unique()
    
    found_count = 0
    for ts in required_ts:
        path = os.path.join(SNAPSHOT_DIR, f"prices_{ts}.csv")
        if os.path.exists(path):
            found_count += 1
            # Load full price rows
            price_cache[ts] = pd.read_csv(path).set_index('item_id').to_dict('index')
        else:
            print(f"Warning: Missing price snapshot for {ts}")

    print(f"Loaded {found_count} / {len(required_ts)} snapshots.")

    # 5. Apply Prices
    def get_price_data(row):
        ts = row['hourly_ts']
        iid = row['item_id']
        data = price_cache.get(ts, {}).get(iid, {})
        
        # Default to High Price (Buy), fallback to Low (Sell)
        high = data.get('avgHighPrice', 0)
        low = data.get('avgLowPrice', 0)
        return high if high > 0 else low

    df['hist_price_unit'] = df.apply(get_price_data, axis=1)
    df['total_value'] = df['qty_delta'] * df['hist_price_unit']

    # 6. Save
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Success! Saved {len(df)} rows to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()