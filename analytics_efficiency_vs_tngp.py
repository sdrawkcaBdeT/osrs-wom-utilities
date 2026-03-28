import sqlite3
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

def generate_efficiency_scatter():
    if not os.path.exists('analytics_output'):
        os.makedirs('analytics_output')

    if not os.path.exists('normalized_sessions.csv'):
        print("Missing normalized_sessions.csv. Please run pipeline.py / normalize_sessions.py first.")
        return

    norm_df = pd.read_csv('normalized_sessions.csv')
    if 'session_id' not in norm_df.columns or 't_ngp_hr' not in norm_df.columns:
        print("Invalid normalized_sessions schema.")
        return

    try:
        conn = sqlite3.connect('combat_telemetry.db')
        ticks_df = pd.read_sql_query(
            "SELECT session_id, state, COUNT(*) as qty FROM combat_ticks GROUP BY session_id, state", 
            conn
        )
        conn.close()
    except Exception as e:
        print(f"Failed to load combat ticks: {e}")
        return

    if ticks_df.empty:
        print("No combat ticks found to calculate efficiency.")
        return

    # Pivot the ticks dataframe to get counts of each state per session
    pivot_df = ticks_df.pivot(index='session_id', columns='state', values='qty').fillna(0)
    
    # Needs attack, cooldown, idle to compute efficiency
    for col in ['attack', 'cooldown', 'idle']:
        if col not in pivot_df.columns:
            pivot_df[col] = 0

    pivot_df['total_ticks'] = pivot_df['attack'] + pivot_df['cooldown'] + pivot_df['idle']
    pivot_df = pivot_df[pivot_df['total_ticks'] > 0]
    
    # Efficiency Quotient = (Attack + Cooldown) / Total Ticks
    pivot_df['efficiency'] = (pivot_df['attack'] + pivot_df['cooldown']) / pivot_df['total_ticks']
    
    pivot_df = pivot_df.reset_index()

    # Join with normalized sessions
    merged_df = pd.merge(norm_df, pivot_df, on='session_id', how='inner')

    if merged_df.empty:
        print("No matching sessions found between database and normalized_sessions.csv.")
        return

    # Scatter Plot
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=merged_df, x='efficiency', y='t_ngp_hr', alpha=0.7, color='purple', s=100)
    
    # Add a trendline
    sns.regplot(data=merged_df, x='efficiency', y='t_ngp_hr', scatter=False, color='red', line_kws={"linestyle": "--"})

    plt.title('The "Perfect Tick" vs. T-NGP Yield')
    plt.xlabel('Micro-Efficiency Quotient (Action Ticks / Total Ticks)')
    plt.ylabel('Luck-Adjusted Theoretical Net GP/hr (T-NGP/hr)')
    plt.grid(alpha=0.3)
    
    # Format axes
    import matplotlib.ticker as ticker
    plt.gca().xaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0))
    plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: format(int(x), ',')))
    
    plt.tight_layout()
    plt.savefig('analytics_output/efficiency_vs_tngp.png', dpi=300)
    plt.close()

    print("Generated analytics_output/efficiency_vs_tngp.png")

if __name__ == "__main__":
    generate_efficiency_scatter()
