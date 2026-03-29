import sqlite3
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

def generate_profit_density():
    if not os.path.exists('analytics_output'):
        os.makedirs('analytics_output')

    conn = sqlite3.connect('combat_telemetry.db')
    df = pd.read_sql_query("SELECT * FROM profit_deltas ORDER BY session_id, tick_number", conn)
    conn.close()

    if df.empty:
        print("No profit deltas found in database.")
        return

    # Convert tick_number to minutes within the session
    df['minute'] = (df['tick_number'] * 0.6) / 60.0

    plt.figure(figsize=(12, 6))
    
    # We can plot each session's profit events over time
    for session_id, group in df.groupby('session_id'):
        plt.scatter(group['minute'], group['delta_gp'], alpha=0.5, label=session_id[:8] if len(df.groupby('session_id')) < 10 else '_nolegend_')

    if len(df.groupby('session_id')) < 10:
        plt.legend(title='Session ID', bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.title('Granular Profit Density Mapping (GP Drops Over Time)')
    plt.xlabel('Session Time (Minutes)')
    plt.ylabel('Profit Delta (GP)')
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('analytics_output/profit_density.png', dpi=300)
    plt.close()
    
    print("Generated analytics_output/profit_density.png")

if __name__ == "__main__":
    generate_profit_density()
