import sqlite3
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

def generate_downtime_histogram():
    if not os.path.exists('analytics_output'):
        os.makedirs('analytics_output')

    conn = sqlite3.connect('combat_telemetry.db')
    df = pd.read_sql_query("SELECT * FROM combat_ticks ORDER BY session_id, tick_number", conn)
    conn.close()

    if df.empty:
        print("No combat ticks found in database.")
        return

    # To calculate downtime gaps, we find all 'idle' streaks
    gap_lengths = []
    
    for session_id, group in df.groupby('session_id'):
        current_streak = 0
        for state in group['state']:
            if state == 'idle':
                current_streak += 1
            else:
                if current_streak > 0:
                    gap_lengths.append(current_streak)
                    current_streak = 0
        if current_streak > 0:
            gap_lengths.append(current_streak)

    if not gap_lengths:
        print("No idle downtime found.")
        return

    # Cap at e.g. 50 ticks for readability
    capped_gaps = [min(x, 50) for x in gap_lengths]

    plt.figure(figsize=(10, 6))
    sns.histplot(capped_gaps, bins=range(1, 52), discrete=True, color='red')
    plt.title('Micro-Downtime Frequency Distribution (Consecutive Idle Ticks)')
    plt.xlabel('Downtime Length (Ticks) [Capped at 50]')
    plt.ylabel('Frequency')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig('analytics_output/downtime_histogram.png', dpi=300)
    plt.close()
    
    print("Generated analytics_output/downtime_histogram.png")

if __name__ == "__main__":
    generate_downtime_histogram()
