# analyzer.py
import csv
import os
import time
import sqlite3
import json
from datetime import datetime, timedelta, timezone
import config

# Ensure reports directory exists
if not os.path.exists('reports'):
    os.makedirs('reports')

DB_FILE = "wom_master.db"

def parse_iso_date(date_str):
    """Parses WOM ISO dates (e.g., 2023-10-27T10:00:00.000Z)"""
    # Handle Z for UTC
    if date_str.endswith('Z'):
        date_str = date_str.replace('Z', '+0000')
    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")

def fetch_local_data(period="week"):
    """
    The New Data Loader.
    Queries the local SQLite database for snapshots in the given period.
    Respects config.PROJECT_START_DATE to ensure no legacy data is included.
    Returns: dict { 'Username': {'category': 'real_ones', 'snapshots': [...]} }
    """
    print(f"--- 1. Fetching Data from Local Archive ({period}) ---")
    
    if not os.path.exists(DB_FILE):
        print("Error: wom_master.db not found. Run 'datahub.py sync' first.")
        return {}

    # 1. Determine Period Start Date
    now = datetime.now(timezone.utc)
    if period == "week":
        period_start = now - timedelta(weeks=1)
    elif period == "month":
        period_start = now - timedelta(days=30)
    else:
        period_start = now - timedelta(days=365*10) # Effectively forever

    # 2. Determine Project Start Date (Global Filter)
    try:
        # Parse config date (e.g. "2026-01-04T00:00:00")
        project_start = datetime.fromisoformat(config.PROJECT_START_DATE)
        # Ensure it is timezone-aware (UTC) for comparison
        if project_start.tzinfo is None:
            project_start = project_start.replace(tzinfo=timezone.utc)
    except Exception as e:
        print(f"Warning: Could not parse PROJECT_START_DATE ({e}). Ignoring filter.")
        project_start = period_start # Fallback

    # 3. Use the LATER of the two dates (Stricter Filter)
    effective_start_date = max(period_start, project_start)
    print(f"Filter Date: {effective_start_date.strftime('%Y-%m-%d %H:%M')}")

    data_cache = {}
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Get all players from config
    for category, players in config.PLAYER_LISTS.items():
        for username in players:
            # Query DB for snapshots newer than effective_start_date
            query = """
                SELECT data_json, timestamp 
                FROM snapshots 
                WHERE username = ? 
                AND timestamp >= ? 
                ORDER BY timestamp ASC
            """
            c.execute(query, (username, effective_start_date.isoformat()))
            rows = c.fetchall()
            
            snapshots = []
            for row in rows:
                try:
                    # Reconstruct the snapshot object structure the analyzer expects
                    snap_data = json.loads(row[0])
                    snapshots.append({
                        "createdAt": row[1],
                        "data": snap_data
                    })
                except:
                    continue

            if len(snapshots) >= 2:
                data_cache[username] = {
                    'category': category,
                    'snapshots': snapshots
                }
            else:
                # print(f"Insufficient local data for {username}")
                pass
    
    conn.close()
    print(f"Loaded data for {len(data_cache)} players from database.")
    return data_cache

def analyze_marginal_gains(data_cache, timestamp_suffix, period):
    filename = f"reports/marginal_gains_{period}_{timestamp_suffix}.csv"
    headers = ["Username", "Category", "Ranged_XP", "HP_XP", "Magic_XP", "Prayer_XP", "Strength_XP", "Farming_XP", "Hunter_XP", "Total_XP", "Vardorvis_KC", "Hespori_KC"]
    
    print(f"--- Generating Report: Marginal Gains ---")
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for username, data in data_cache.items():
            category = data['category']
            snapshots = data['snapshots']
            
            start_snap = snapshots[0]['data']
            end_snap = snapshots[-1]['data']

            def get_delta(metric_type, metric_name, subkey):
                start = start_snap.get(metric_type, {}).get(metric_name, {}).get(subkey, -1)
                end = end_snap.get(metric_type, {}).get(metric_name, {}).get(subkey, -1)
                if start == -1 or end == -1: return 0
                return max(0, end - start)

            writer.writerow([
                username, category,
                get_delta('skills', 'ranged', 'experience'),
                get_delta('skills', 'hitpoints', 'experience'),
                get_delta('skills', 'magic', 'experience'),
                get_delta('skills', 'prayer', 'experience'),
                get_delta('skills', 'strength', 'experience'),
                get_delta('skills', 'farming', 'experience'),
                get_delta('skills', 'hunter', 'experience'),
                get_delta('skills', 'overall', 'experience'),
                get_delta('bosses', 'vardorvis', 'kills'),
                get_delta('bosses', 'hespori', 'kills'),
            ])

def analyze_consistency_variety(data_cache, timestamp_suffix, period):
    filename = f"reports/variety_consistency_{period}_{timestamp_suffix}.csv"
    headers = ["Username", "Category", "Unique_Skills_Trained", "Top_Skill_Trained", "Top_Skill_XP"]
    
    print(f"--- Generating Report: Consistency & Variety ---")
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for username, data in data_cache.items():
            category = data['category']
            snapshots = data['snapshots']
            
            start_snap = snapshots[0]['data']['skills']
            end_snap = snapshots[-1]['data']['skills']

            skills_trained = 0
            top_skill = "None"
            top_xp = 0

            for skill_name, start_data in start_snap.items():
                start_xp = start_data.get('experience', 0)
                end_xp = end_snap.get(skill_name, {}).get('experience', 0)
                gained = max(0, end_xp - start_xp)
                
                if gained > 500: # Threshold
                    skills_trained += 1
                    if gained > top_xp:
                        top_xp = gained
                        top_skill = skill_name

            writer.writerow([username, category, skills_trained, top_skill, top_xp])

def estimate_activity_log(data_cache, timestamp_suffix, period):
    filename = f"reports/activity_log_{period}_{timestamp_suffix}.csv"
    headers = ["Username", "Category", "Time_Window_Start", "Time_Window_End", "Window_Duration_Hours", "Est_Active_Hours", "Implied_Efficiency", "Metric_Used"]
    
    print(f"--- Generating Report: Activity Inference Log ---")
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for username, data in data_cache.items():
            category = data['category']
            snapshots = data['snapshots']
            
            # Get Config
            cat_config = config.ACTIVITY_CONFIG.get(category)
            if not cat_config: continue

            target_metric = cat_config['primary_metric']
            ref_rate = cat_config['xp_per_hour']

            for i in range(1, len(snapshots)):
                prev = snapshots[i-1]
                curr = snapshots[i]

                t1 = parse_iso_date(prev['createdAt'])
                t2 = parse_iso_date(curr['createdAt'])
                window_hours = (t2 - t1).total_seconds() / 3600

                if window_hours < 0.1: continue

                xp_prev = prev['data']['skills'].get(target_metric, {}).get('experience', 0)
                xp_curr = curr['data']['skills'].get(target_metric, {}).get('experience', 0)
                xp_gained = max(0, xp_curr - xp_prev)

                if xp_gained > 0:
                    est_active_hours = xp_gained / ref_rate
                    efficiency = 0
                    if window_hours > 0:
                        efficiency = est_active_hours / window_hours

                    writer.writerow([
                        username, category,
                        t1.strftime("%Y/%m/%d %H:%M"),
                        t2.strftime("%Y/%m/%d %H:%M"),
                        round(window_hours, 2),
                        round(est_active_hours, 2),
                        round(efficiency * 100, 1),
                        target_metric
                    ])

def generate_timeseries_data(data_cache, timestamp_suffix, period):
    filename = f"reports/timeseries_{period}_{timestamp_suffix}.csv"
    headers = ["Username", "Category", "Timestamp", "Total_XP"]
    
    print(f"--- Generating Report: Time Series Data ---")
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for username, data in data_cache.items():
            category = data['category']
            snapshots = data['snapshots']
            
            for snap in snapshots:
                ts = parse_iso_date(snap['createdAt'])
                total_xp = snap['data']['skills']['overall']['experience']
                
                writer.writerow([
                    username, category,
                    ts.strftime("%Y-%m-%d %H:%M:%S"),
                    total_xp
                ])

def analyze_detailed_xp_breakdown(data_cache, timestamp_suffix, period):
    filename = f"reports/detailed_xp_{period}_{timestamp_suffix}.csv"
    
    # Get skills from config colors to ensure order
    all_skills = [s for s in config.SKILL_COLORS.keys() if s != 'overall']
    headers = ["Username", "Category"] + all_skills
    
    print(f"--- Generating Report: Detailed XP Breakdown ---")
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for username, data in data_cache.items():
            category = data['category']
            snapshots = data['snapshots']
            
            start_snap = snapshots[0]['data']['skills']
            end_snap = snapshots[-1]['data']['skills']

            row = [username, category]
            
            for skill in all_skills:
                s_xp = start_snap.get(skill, {}).get('experience', 0)
                e_xp = end_snap.get(skill, {}).get('experience', 0)
                gained = max(0, e_xp - s_xp)
                row.append(gained)
                
            writer.writerow(row)

def main():
    period = "week"
    timestamp_suffix = datetime.now().strftime('%Y%m%d_%H%M')
    
    # 1. Fetch Data from LOCAL DB (Instant)
    data_cache = fetch_local_data(period)
    
    if not data_cache:
        print("No local data found. Please run 'datahub.py sync' first.")
        return

    # 2. Run Analysis Suite
    print("\n--- Processing Reports ---")
    analyze_marginal_gains(data_cache, timestamp_suffix, period)
    analyze_consistency_variety(data_cache, timestamp_suffix, period)
    estimate_activity_log(data_cache, timestamp_suffix, period)
    generate_timeseries_data(data_cache, timestamp_suffix, period)
    analyze_detailed_xp_breakdown(data_cache, timestamp_suffix, period)
    
    print("\n=== Analysis Complete ===")
    print(f"Reports saved to /reports with suffix: {timestamp_suffix}")

if __name__ == "__main__":
    main()