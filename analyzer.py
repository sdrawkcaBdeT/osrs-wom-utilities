# analyzer.py
import csv
import os
import time
from datetime import datetime, timedelta
import config
from wom_client import WiseOldManClient

# Ensure reports directory exists
if not os.path.exists('reports'):
    os.makedirs('reports')

def parse_iso_date(date_str):
    """Parses WOM ISO dates (e.g., 2023-10-27T10:00:00.000Z)"""
    return datetime.strptime(date_str.replace('Z', '+0000'), "%Y-%m-%dT%H:%M:%S.%f%z")

def analyze_marginal_gains(client, period="week"):
    """
    Report 1: Marginal Gains
    Shows exactly how much XP and Boss KC increased in the period.
    """
    filename = f"reports/marginal_gains_{period}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    headers = ["Username", "Category", "Ranged_XP_Gained", "HP_XP_Gained", "Total_XP_Gained", "Vorkath_Delta", "Zulrah_Delta"]
    
    print(f"--- Generating Marginal Gains Report ---")
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for category, players in config.PLAYER_LISTS.items():
            for username in players:
                # Get snapshots
                snapshots = client.get_player_snapshots(username, period)
                
                if snapshots and len(snapshots) >= 2:
                    # Sort by date (oldest to newest)
                    snapshots.sort(key=lambda x: x['createdAt'])
                    
                    start_snap = snapshots[0]['data']
                    end_snap = snapshots[-1]['data']

                    # Helper to get delta
                    def get_delta(metric_type, metric_name, subkey):
                        start = start_snap.get(metric_type, {}).get(metric_name, {}).get(subkey, -1)
                        end = end_snap.get(metric_type, {}).get(metric_name, {}).get(subkey, -1)
                        if start == -1 or end == -1: return 0
                        return max(0, end - start)

                    row = [
                        username,
                        category,
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
                    ]
                    writer.writerow(row)
                    print(f"Processed gains for {username}")
                else:
                    print(f"Not enough data for {username}")
                
                time.sleep(1)

def analyze_consistency_variety(client, period="week"):
    """
    Report 2: Variety & Consistency
    Checks how many UNIQUE skills had XP gains (Real players > Bots).
    """
    filename = f"reports/variety_consistency_{period}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    headers = ["Username", "Category", "Unique_Skills_Trained", "Top_Skill_Trained", "Top_Skill_XP"]
    
    print(f"--- Generating Variety Report ---")
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for category, players in config.PLAYER_LISTS.items():
            for username in players:
                snapshots = client.get_player_snapshots(username, period)
                
                if snapshots and len(snapshots) >= 2:
                    snapshots.sort(key=lambda x: x['createdAt'])
                    start_snap = snapshots[0]['data']['skills']
                    end_snap = snapshots[-1]['data']['skills']

                    skills_trained = 0
                    top_skill = "None"
                    top_xp = 0

                    # Iterate over all skills in the snapshot
                    for skill_name, start_data in start_snap.items():
                        start_xp = start_data.get('experience', 0)
                        end_xp = end_snap.get(skill_name, {}).get('experience', 0)
                        
                        gained = end_xp - start_xp
                        
                        if gained > 500: # Threshold to ignore accidental XP
                            skills_trained += 1
                            if gained > top_xp:
                                top_xp = gained
                                top_skill = skill_name

                    writer.writerow([username, category, skills_trained, top_skill, top_xp])
                    print(f"Processed variety for {username}")
                time.sleep(1)

def estimate_activity_log(client, period="week"):
    """
    Report 3: The Activity Inference Engine
    Uses user-defined XP rates to guess how long they played between snapshots.
    """
    filename = f"reports/activity_log_{period}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    headers = ["Username", "Category", "Time_Window_Start", "Time_Window_End", "Window_Duration_Hours", "Est_Active_Hours", "Implied_Efficiency", "Metric_Used"]
    
    print(f"--- Generating Activity Inference Log ---")
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for category, players in config.PLAYER_LISTS.items():
            # Get the config for this category (e.g., suspected_bots)
            cat_config = config.ACTIVITY_CONFIG.get(category)
            if not cat_config:
                print(f"Skipping {category} - No Activity Config defined.")
                continue

            target_metric = cat_config['primary_metric']
            ref_rate = cat_config['xp_per_hour']

            for username in players:
                snapshots = client.get_player_snapshots(username, period)
                
                if snapshots and len(snapshots) >= 2:
                    snapshots.sort(key=lambda x: x['createdAt'])

                    # Compare every snapshot to the previous one
                    for i in range(1, len(snapshots)):
                        prev = snapshots[i-1]
                        curr = snapshots[i]

                        # Calculate Time Difference
                        t1 = parse_iso_date(prev['createdAt'])
                        t2 = parse_iso_date(curr['createdAt'])
                        window_hours = (t2 - t1).total_seconds() / 3600

                        if window_hours < 0.1: continue # Skip duplicate/instant updates

                        # Calculate XP Difference
                        xp_prev = prev['data']['skills'].get(target_metric, {}).get('experience', 0)
                        xp_curr = curr['data']['skills'].get(target_metric, {}).get('experience', 0)
                        xp_gained = max(0, xp_curr - xp_prev)

                        # THE DEDUCTION MATH
                        # Est Hours = Gained / Rate
                        est_active_hours = xp_gained / ref_rate
                        
                        # Efficiency = Active / Window
                        # If efficiency > 1.0 (100%), they are gaining XP faster than our config rate
                        efficiency = 0
                        if window_hours > 0:
                            efficiency = est_active_hours / window_hours

                        if xp_gained > 0:
                            writer.writerow([
                                username,
                                category,
                                t1.strftime("%Y/%m/%d %H:%M"),
                                t2.strftime("%Y/%m/%d %H:%M"),
                                round(window_hours, 2),
                                round(est_active_hours, 2),
                                round(efficiency * 100, 1), # Percentage
                                target_metric
                            ])
                    
                    print(f"Processed activity log for {username}")
                time.sleep(1)

def generate_timeseries_data(client, period="week"):
    """
    Report 5: Time Series Data
    Dumps every snapshot timestamp and Total XP for the Line Chart.
    """
    filename = f"reports/timeseries_{period}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    headers = ["Username", "Category", "Timestamp", "Total_XP"]
    
    print(f"--- Generating Time Series Data ---")
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for category, players in config.PLAYER_LISTS.items():
            for username in players:
                snapshots = client.get_player_snapshots(username, period)
                
                if snapshots:
                    # Sort by date
                    snapshots.sort(key=lambda x: x['createdAt'])
                    
                    for snap in snapshots:
                        ts = parse_iso_date(snap['createdAt'])
                        total_xp = snap['data']['skills']['overall']['experience']
                        
                        writer.writerow([
                            username, 
                            category, 
                            ts.strftime("%Y-%m-%d %H:%M:%S"), 
                            total_xp
                        ])
                    print(f"Processed time series for {username}")
                time.sleep(1)

def main():
    client = WiseOldManClient()
    print("1. Marginal Gains Report")
    print("2. Consistency/Variety Report")
    print("3. Activity Inference Log")
    print("4. Run All")
    
    choice = input("Select: ")
    
    if choice == '1': analyze_marginal_gains(client)
    elif choice == '2': analyze_consistency_variety(client)
    elif choice == '3': estimate_activity_log(client)
    elif choice == '4': generate_timeseries_data(client)
    elif choice == '5':
        analyze_marginal_gains(client)
        analyze_consistency_variety(client)
        estimate_activity_log(client)
        generate_timeseries_data(client)

if __name__ == "__main__":
    main()