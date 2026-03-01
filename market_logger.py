import time
import os
from datetime import datetime, timedelta
import get_prices

# --- CONFIG ---
SNAPSHOT_DIR = "price_snapshots"
INTERVAL_HOURS = 1
START_DATE = "2026-01-01 00:00"

if not os.path.exists(SNAPSHOT_DIR): os.makedirs(SNAPSHOT_DIR)

def get_latest_snapshot_time():
    """Finds the newest file in the folder."""
    timestamps = []
    for f in os.listdir(SNAPSHOT_DIR):
        if f.startswith("prices_") and f.endswith(".csv"):
            try:
                ts = int(f.replace("prices_", "").replace(".csv", ""))
                timestamps.append(ts)
            except ValueError: pass
    
    if not timestamps:
        dt = datetime.strptime(START_DATE, "%Y-%m-%d %H:%M")
        return int(dt.timestamp())
    
    return max(timestamps)

def main():
    print(f"--- Market Logger (Interval: {INTERVAL_HOURS}h) ---")
    print(f"Output: {os.path.abspath(SNAPSHOT_DIR)}")
    print("Press Ctrl+C to stop.\n")

    while True:
        # 1. Where are we now?
        now = int(time.time())
        current_bucket = now - (now % 3600) 
        
        # 2. Where did we leave off?
        last_snap = get_latest_snapshot_time()
        
        # 3. Calculate next needed time
        next_needed = last_snap + (INTERVAL_HOURS * 3600)
        
        # FIX: STRICTLY LESS THAN (<)
        # We cannot fetch the 1:00 PM stats until it is 2:00 PM.
        if next_needed < current_bucket:
            
            human_time = datetime.fromtimestamp(next_needed).strftime('%Y-%m-%d %H:%M')
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching missing snapshot: {human_time}")
            
            data, valid_ts = get_prices.fetch_prices(next_needed)
            
            if data:
                get_prices.save_prices_csv(data, valid_ts, folder=SNAPSHOT_DIR)
                time.sleep(1) # Success throttle
            else:
                # FAILURE SAFETY
                # If the API returns nothing (server error?), wait 60s before retrying
                # to prevent the infinite loop spam you just saw.
                print("  -> Warning: No data returned. Waiting 60s before retry...")
                time.sleep(60)
            
        else:
            # We are up to date. Sleep until the next interval.
            # We calculate time until the NEXT hour starts
            next_hour_start = current_bucket + 3600
            seconds_until_next = next_hour_start - now + 5 # +5s buffer to be safe
            
            next_run_str = (datetime.now() + timedelta(seconds=seconds_until_next)).strftime('%H:%M:%S')
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Up to date. Sleeping {int(seconds_until_next/60)} mins (Next run: {next_run_str})")
            time.sleep(seconds_until_next)

if __name__ == "__main__":
    main()