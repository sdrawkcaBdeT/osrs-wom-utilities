import json
import csv
import os
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for older Python versions, though 3.9+ is recommended
    from backports.zoneinfo import ZoneInfo

# --- CONFIGURATION ---
INPUT_FILE = r"C:\Users\Teddy\.runelite\profiles2\$rsprofile--1.properties"
OUTPUT_SESSION_CSV = "gpph_sessions.csv"
OUTPUT_LEDGER_CSV = "gpph_ledger_raw.csv"

# The key prefix to identify relevant lines
TARGET_KEY_PREFIX = "gpperhour.rsprofile.t-qiiBcR.session_stats"

# Your Local Timezone for reporting
LOCAL_TZ = ZoneInfo("America/Chicago")

def load_processed_sessions():
    """Reads the existing CSV to avoid duplicate processing."""
    processed_ids = set()
    if os.path.exists(OUTPUT_SESSION_CSV):
        with open(OUTPUT_SESSION_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "session_uuid" in row:
                    processed_ids.add(row["session_uuid"])
    return processed_ids

def parse_line(line):
    """Parses a single line from the properties file."""
    try:
        if "=" not in line: return None
        key, raw_value = line.split("=", 1)

        # Ignore lines that aren't for our specific character/plugin
        if not key.strip().startswith(TARGET_KEY_PREFIX):
            return None

        # Clean RuneLite's escaped colons
        clean_json = raw_value.replace(r'\:', ':').strip()
        return json.loads(clean_json)
    except Exception:
        return None

def get_time_data(save_time_ms, duration_ms):
    """
    Calculates timestamps for both the Wiki API (UTC) and User Reports (Local).
    """
    if not save_time_ms:
        return 0, "Unknown"

    # 1. Calculate Start Time in UTC (Save Time - Duration)
    # The plugin logs when you *stopped*, but we usually care when you *started*
    start_timestamp_utc = (save_time_ms - duration_ms) / 1000
    
    # 2. Create Timezone-Aware Object (UTC)
    dt_utc = datetime.fromtimestamp(start_timestamp_utc, tz=timezone.utc)
    
    # 3. Convert to Local Time (Central) for the CSV report
    dt_local = dt_utc.astimezone(LOCAL_TZ)
    local_time_str = dt_local.strftime('%Y-%m-%d %I:%M:%S %p')

    # 4. Calculate Wiki Pricing Timestamp (UTC, 5-minute bucket)
    # We use the END time (SaveTime) for pricing, as that's when you banked the loot.
    save_timestamp_seconds = int(save_time_ms / 1000)
    wiki_pricing_timestamp = save_timestamp_seconds - (save_timestamp_seconds % 300)

    return wiki_pricing_timestamp, local_time_str

def process_session_data(data):
    if not data: return None, None

    session_id = data.get("sessionID")
    save_time = data.get("sessionSaveTime", 0)
    duration = data.get("sessionRuntime", 0)

    # Get the calculated times
    wiki_ts, local_time_str = get_time_data(save_time, duration)

    # --- Session Row ---
    session_row = {
        "session_uuid": session_id,
        "name": data.get("sessionName"),
        "local_start_time": local_time_str, # Human readable Central Time
        "wiki_pricing_timestamp": wiki_ts,  # UTC timestamp for API calls
        "duration_seconds": int(duration / 1000),
        "trip_count": data.get("tripCount"),
        "net_profit": data.get("netTotal"),
        "total_gain": data.get("totalGain"),
        "total_loss": data.get("totalLoss")
    }

    # --- Ledger Rows ---
    initial = data.get("initialQtys", {})
    ending = data.get("qtys", {})
    all_items = set(initial.keys()) | set(ending.keys())
    
    ledger_rows = []
    for item_id in all_items:
        start_qty = initial.get(item_id, 0.0)
        end_qty = ending.get(item_id, 0.0)
        delta = end_qty - start_qty
        
        if delta == 0: continue
        
        ledger_rows.append({
            "session_uuid": session_id,
            "item_id": int(item_id),
            "qty_delta": delta,
            "category": "LOOT" if delta > 0 else "SUPPLY"
        })

    return session_row, ledger_rows

def main():
    print(f"Scanning: {INPUT_FILE}")
    if not os.path.exists(INPUT_FILE):
        print("Error: Input file not found.")
        return

    processed_ids = load_processed_sessions()
    print(f"Found {len(processed_ids)} sessions already in database.")

    new_sessions = []
    new_ledger = []

    # RuneLite .properties files are usually Latin-1
    with open(INPUT_FILE, 'r', encoding='latin-1') as f:
        for line in f:
            data = parse_line(line)
            if data:
                sid = data.get("sessionID")
                
                # Deduplication check
                if sid in processed_ids: continue
                if any(s['session_uuid'] == sid for s in new_sessions): continue

                s_row, l_rows = process_session_data(data)
                if s_row:
                    new_sessions.append(s_row)
                    new_ledger.extend(l_rows)
                    print(f"  [NEW] {s_row['local_start_time']} | Session: {s_row['name']}")

    if not new_sessions:
        print("\nNo new sessions found.")
        return

    print(f"\nSaving {len(new_sessions)} new sessions...")

    # Write Sessions CSV
    file_exists = os.path.exists(OUTPUT_SESSION_CSV)
    with open(OUTPUT_SESSION_CSV, 'a', newline='', encoding='utf-8') as f:
        # Define order of columns
        headers = ["session_uuid", "name", "local_start_time", "wiki_pricing_timestamp", 
                   "duration_seconds", "trip_count", "net_profit", "total_gain", "total_loss"]
        writer = csv.DictWriter(f, fieldnames=headers)
        if not file_exists: writer.writeheader()
        writer.writerows(new_sessions)

    # Write Ledger CSV
    file_exists = os.path.exists(OUTPUT_LEDGER_CSV)
    if new_ledger:
        with open(OUTPUT_LEDGER_CSV, 'a', newline='', encoding='utf-8') as f:
            headers = ["session_uuid", "item_id", "qty_delta", "category"]
            writer = csv.DictWriter(f, fieldnames=headers)
            if not file_exists: writer.writeheader()
            writer.writerows(new_ledger)

    print("Import Complete.")

if __name__ == "__main__":
    main()