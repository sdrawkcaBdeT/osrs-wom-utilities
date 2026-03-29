import sqlite3
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os
import json
from datetime import datetime

def generate_distraction_heatmap():
    if not os.path.exists('analytics_output'):
        os.makedirs('analytics_output')

    # Load session start times
    session_starts = {}
    if os.path.exists('bbd_data'):
        for f in os.listdir('bbd_data'):
            if f.endswith('.json'):
                try:
                    with open(os.path.join('bbd_data', f), 'r') as jf:
                        d = json.load(jf)
                        # Handle singleton lists if they exist
                        if isinstance(d, list) and len(d) == 1:
                            d = d[0]
                        sid = d.get('session_id')
                        st = d.get('start_time')
                        if sid and st:
                            session_starts[sid] = pd.to_datetime(st)
                except: pass

    if not session_starts:
        print("No valid session JSONs found to map timestamps.")
        return

    # Load Census Sightings
    try:
        conn = sqlite3.connect('census.db')
        query = """
            SELECT s.session_id, s.timestamp, r.status as category
            FROM sightings s
            JOIN roster r ON s.username = r.username
            WHERE r.status IN ('REAL', 'SUSPECT')
        """
        sightings_df = pd.read_sql_query(query, conn)
        conn.close()
    except Exception as e:
        print(f"Failed to load census data: {e}")
        return

    if sightings_df.empty:
        print("No valid sightings found.")
        return

    sightings_df['timestamp'] = pd.to_datetime(sightings_df['timestamp'])

    # Prepare window metrics
    # Let's say window is [-100 ticks, +500 ticks] -> [-60s, +300s]
    window_ticks_pre = 100
    window_ticks_post = 500

    results = []

    try:
        conn_ticks = sqlite3.connect('combat_telemetry.db')
        
        for idx, row in sightings_df.iterrows():
            sid = row['session_id']
            cat = row['category']
            sts = row['timestamp']
            
            if sid not in session_starts: continue
            
            # Absolute to Tick Number Conversion
            start_ts = session_starts[sid]
            elapsed_sec = (sts - start_ts).total_seconds()
            if elapsed_sec < 0: continue
            
            sighting_tick = int(elapsed_sec / 0.6)
            
            # Fetch ticks for this session
            ticks_df = pd.read_sql_query(
                "SELECT tick_number, state FROM combat_ticks WHERE session_id = ?", 
                conn_ticks, params=(sid,)
            )
            if ticks_df.empty: continue
            
            # Split into inside-window and outside-window
            min_tick = sighting_tick - window_ticks_pre
            max_tick = sighting_tick + window_ticks_post
            
            in_window = ticks_df[(ticks_df['tick_number'] >= min_tick) & (ticks_df['tick_number'] <= max_tick)]
            out_window = ticks_df[(ticks_df['tick_number'] < min_tick) | (ticks_df['tick_number'] > max_tick)]
            
            if not in_window.empty and not out_window.empty:
                in_idle = len(in_window[in_window['state'] == 'idle']) / len(in_window)
                out_idle = len(out_window[out_window['state'] == 'idle']) / len(out_window)
                
                results.append({
                    'Category': cat,
                    'Context': 'Near Entity',
                    'Idle %': in_idle * 100
                })
                results.append({
                    'Category': cat,
                    'Context': 'Normal (Session Avg)',
                    'Idle %': out_idle * 100
                })
                
        conn_ticks.close()
    except Exception as e:
        print(f"Error querying ticks: {e}")
        return

    if not results:
        print("Not enough tick overlap data for heatmap.")
        return

    res_df = pd.DataFrame(results)

    plt.figure(figsize=(8, 6))
    sns.barplot(data=res_df, x='Category', y='Idle %', hue='Context', errorbar=None)
    plt.title('Distraction Heatmaps: Player/Bot Encounters vs. Tick Efficiency')
    plt.xlabel('Encounter Type')
    plt.ylabel('Idle Ticks (%)')
    plt.legend(title='Temporal Context')
    plt.tight_layout()
    plt.savefig('analytics_output/distraction_heatmap.png', dpi=300)
    plt.close()

    print("Generated analytics_output/distraction_heatmap.png")

if __name__ == "__main__":
    generate_distraction_heatmap()
