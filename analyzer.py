# analyzer.py
import csv
import os
import time
from datetime import datetime
import config
from wom_client import WiseOldManClient

# Ensure reports directory exists
if not os.path.exists('reports'):
    os.makedirs('reports')

def parse_iso_date(date_str):
    """Parses WOM ISO dates (e.g., 2023-10-27T10:00:00.000Z)"""
    return datetime.strptime(date_str.replace('Z', '+0000'), "%Y-%m-%dT%H:%M:%S.%f%z")

def fetch_all_data(client, period="week"):
    """
    The Data Loader.
    Fetches snapshots ONCE for every player and stores them in memory.
    Returns: dict { 'Username': {'category': 'real_ones', 'snapshots': [...]} }
    """
    print("--- 1. Fetching Data from Wise Old Man (This may take a moment) ---")
    data_cache = {}
    
    for category, players in config.PLAYER_LISTS.items():
        for username in players:
            snapshots = client.get_player_snapshots(username, period)
            
            if snapshots and len(snapshots) >= 2:
                # Sort once here, so we don't have to do it in every report
                snapshots.sort(key=lambda x: x['createdAt'])
                data_cache[username] = {
                    'category': category,
                    'snapshots': snapshots
                }
                print(f"Loaded {len(snapshots)} snapshots for {username}")
            else:
                print(f"Insufficient data for {username}")
            
            # Polite delay between players
            time.sleep(0.5)
            
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
    """
    REQUIRED for the Stacked Bar Chart in visualizer.py
    """
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
    client = WiseOldManClient()
    period = "week"
    
    # 1. Generate a single timestamp for all files in this batch
    timestamp_suffix = datetime.now().strftime('%Y%m%d_%H%M')
    
    # 2. Fetch Data ONCE
    data_cache = fetch_all_data(client, period)
    
    if not data_cache:
        print("No data fetched. Exiting.")
        return

    # 3. Run Analysis Suite (Memory based, instant)
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