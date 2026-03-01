import pandas as pd
import os
from datetime import datetime
import json

# --- CONFIG ---
TIME_TRACKING_FILE = "reports/time_tracking_history.csv"  # Save your raw data here
BBD_DATA_DIR = "bbd_data"
OUTPUT_FILE = "reports/time_tracking_history_enriched.csv"

def load_bbd_sessions():
    """Loads start/end times for all BBD sessions."""
    sessions = []
    if not os.path.exists(BBD_DATA_DIR):
        print("BBD Data directory not found.")
        return sessions

    for f in os.listdir(BBD_DATA_DIR):
        if f.endswith(".json"):
            try:
                with open(os.path.join(BBD_DATA_DIR, f), 'r') as file:
                    data = json.load(file)
                    # Parse ISO timestamps
                    start = datetime.fromisoformat(data['start_time'])
                    end = datetime.fromisoformat(data['end_time'])
                    sessions.append({
                        "id": data['session_id'],
                        "start": start,
                        "end": end,
                        "type": "Brutal Black Dragons"
                    })
            except Exception as e:
                print(f"Skipping broken BBD file {f}: {e}")
    return sessions

def main():
    print("--- Time Ledger Unification ---")
    
    # 1. Load Raw Time Data
    # Assuming your provided data is in 'time_tracking.csv'
    # We explicitly name columns based on your paste
    try:
        df = pd.read_csv(TIME_TRACKING_FILE)
        # Convert timestamps to datetime objects
        df['start_dt'] = pd.to_datetime(df['start_timestamp'])
        df['end_dt'] = pd.to_datetime(df['end_timestamp'])
    except Exception as e:
        print(f"Error loading time tracking CSV: {e}")
        return

    # 2. Load BBD Context
    bbd_sessions = load_bbd_sessions()
    print(f"Loaded {len(bbd_sessions)} BBD sessions for cross-referencing.")

    # 3. The Matching Algorithm
    def label_activity(row):
        # We only care about WORK blocks for labeling activities
        if row['type'] == 'BREAK':
            return "Break"
            
        # Check for overlap with any BBD session
        # Logic: (StartA <= EndB) and (EndA >= StartB)
        for bbd in bbd_sessions:
            # We use a 5-minute buffer because clocks might be slightly off
            # or you might clock in 1 minute before killing the first dragon.
            buffer = pd.Timedelta(minutes=5)
            
            if (row['start_dt'] <= (bbd['end'] + buffer)) and \
               (row['end_dt'] >= (bbd['start'] - buffer)):
                return "Brutal Black Dragons"
        
        return "Non-Combat / Other"

    print("Classifying sessions...")
    df['activity_label'] = df.apply(label_activity, axis=1)

    # 4. Save
    cols = ['start_timestamp', 'end_timestamp', 'duration_hours', 'type', 'activity_label']
    df[cols].to_csv(OUTPUT_FILE, index=False)
    
    # 5. Report
    summary = df['activity_label'].value_counts()
    print("\nClassification Results:")
    print(summary)
    print(f"\nSaved enriched ledger to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()