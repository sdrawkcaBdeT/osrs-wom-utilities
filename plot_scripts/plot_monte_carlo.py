import os
import shutil
import json
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import matplotlib.dates as mdates

# --- CONFIG ---
WEALTH_FILE = "../live_wealth.json"
DB_PATH = "../time_tracker.db"
NORMALIZED_CSV = "../normalized_sessions.csv"
OUTPUT_DIR = "../analytics_output"
SIMULATIONS = 10000

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def load_historical_data():
    """Extracts historical play habits and GP/hr to bootstrap the simulation."""
    # 1. Get GP/hr distribution from normalized sessions
    if not os.path.exists(NORMALIZED_CSV):
        print(f"Error: {NORMALIZED_CSV} not found. Run normalize_sessions.py first.")
        return None, None, None
        
    df_sessions = pd.read_csv(NORMALIZED_CSV)
    gp_hr_pool = df_sessions['t_ngp_hr'].dropna().values
    
    # 2. Get Daily Play Hours from SQLite
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found.")
        return None, None, None
        
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT date(start_timestamp) as play_date, 
               SUM((julianday(IFNULL(end_timestamp, CURRENT_TIMESTAMP)) - julianday(start_timestamp)) * 24) as hours_played
        FROM shifts 
        WHERE type = 'WORK'
        GROUP BY play_date
    """
    df_shifts = pd.read_sql_query(query, conn)
    conn.close()

    # Calculate Probability of Playing on any given day
    # Assuming "Genesis" was the earliest date in the database
    first_day = pd.to_datetime(df_shifts['play_date'].min())
    today = pd.Timestamp.now()
    total_days_since_start = max((today - first_day).days, 1)
    
    days_played = len(df_shifts)
    play_probability = days_played / total_days_since_start
    
    # Cap probability at 1.0 just in case
    play_probability = min(play_probability, 1.0)
    
    # The pool of hours played on active days
    hours_pool = df_shifts['hours_played'].values

    return gp_hr_pool, hours_pool, play_probability

def main():
    print(f"--- Running {SIMULATIONS:,} Monte Carlo Simulations ---")
    
    # 1. Load the remaining Gap
    if not os.path.exists(WEALTH_FILE):
        return print(f"Error: {WEALTH_FILE} not found.")
        
    with open(WEALTH_FILE, 'r') as f:
        wealth_data = json.load(f)
        
    gap = wealth_data.get('gap', 0)
    if gap <= 0:
        return print("Gap is 0 or negative. You already have enough for the T-Bow!")

    # 2. Load the Bootstrap Pools
    gp_hr_pool, hours_pool, play_prob = load_historical_data()
    if gp_hr_pool is None or len(gp_hr_pool) == 0:
        return print("Not enough normalized session data to simulate.")
    if len(hours_pool) == 0:
        return print("Not enough time tracker data to simulate.")

    print(f"Historical Play Probability: {play_prob*100:.1f}% per day")
    print(f"Average Shift: {np.mean(hours_pool):.2f} hours")
    print(f"Average Normalized GP/hr: {np.mean(gp_hr_pool):,.0f} GP")

    # 3. The Simulation Engine
    results_days =[]
    
    for i in range(SIMULATIONS):
        current_gap = gap
        days_passed = 0
        
        while current_gap > 0:
            days_passed += 1
            # Do we play today?
            if np.random.rand() <= play_prob:
                # How long do we play? (Bootstrap from history)
                hours_played = np.random.choice(hours_pool)
                # What is our GP/hr today? (Bootstrap from history)
                daily_gp_hr = np.random.choice(gp_hr_pool)
                
                # Deduct from the gap
                current_gap -= (hours_played * daily_gp_hr)
                
        results_days.append(days_passed)

    # 4. Calculate Percentiles and Dates
    results_days = np.array(results_days)
    p05 = np.percentile(results_days, 5)   # Top 5% (Lucky/Grindy - Fast)
    p50 = np.percentile(results_days, 50)  # Median (Expected)
    p95 = np.percentile(results_days, 95)  # Bottom 5% (Unlucky/Lazy - Slow)

    today = datetime.now()
    date_p05 = today + timedelta(days=int(p05))
    date_p50 = today + timedelta(days=int(p50))
    date_p95 = today + timedelta(days=int(p95))

    # 5. Render the Cinematic Bell Curve
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"
    BAR_COLOR = "#008800"
    LINE_P50 = "#00FFFF"  # Cyan for Median
    LINE_EXTREMES = "#FFD700"  # Gold for 5th/95th

    fig, ax = plt.subplots(figsize=(14, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # Convert day counts to actual Matplotlib dates for the X-axis
    result_dates =[today + timedelta(days=int(d)) for d in results_days]
    
    # Plot the Histogram
    n, bins, patches = ax.hist(result_dates, bins=50, color=BAR_COLOR, edgecolor="#222222", alpha=0.85)

    # Draw vertical lines for the percentiles
    ax.axvline(date_p50, color=LINE_P50, linestyle='-', linewidth=3, zorder=5)
    ax.axvline(date_p05, color=LINE_EXTREMES, linestyle='--', linewidth=2, zorder=5)
    ax.axvline(date_p95, color=LINE_EXTREMES, linestyle='--', linewidth=2, zorder=5)

    # Annotations
    y_max = max(n)
    
    # Function to add text with a dark background/outline for readability
    import matplotlib.patheffects as path_effects
    def annotate_line(date_val, label, x_offset, color):
        txt = ax.text(date_val + timedelta(days=x_offset), y_max * 0.9, 
                      f"{label}\n{date_val.strftime('%b %d, %Y')}", 
                      color=color, fontweight='bold', fontsize=12, ha='left' if x_offset > 0 else 'right')
        txt.set_path_effects([path_effects.withStroke(linewidth=3, foreground=BG_COLOR)])

    # Adjust x_offsets based on the spread of the data
    spread_days = (date_p95 - date_p05).days
    offset = max(spread_days * 0.02, 1)

    annotate_line(date_p50, "MEDIAN ETA", offset, LINE_P50)
    annotate_line(date_p05, "5th Percentile\n(Optimistic)", -offset, LINE_EXTREMES)
    annotate_line(date_p95, "95th Percentile\n(Pessimistic)", offset, LINE_EXTREMES)

    # Formatting axes
    ax.set_xlabel("Projected Completion Date", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    ax.set_ylabel("Simulation Frequency", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    ax.tick_params(axis='x', colors=TEXT_COLOR, labelsize=12)
    ax.tick_params(axis='y', colors=TEXT_COLOR, labelsize=12)
    
    # Format the X-axis to show nice Month/Year labels
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=45)

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['left'].set_color('gray')
    ax.spines['bottom'].set_color('gray')

    # Titles
    plt.suptitle("MONTE CARLO COMPLETION PROJECTION", color=TEXT_COLOR, fontsize=24, fontweight='bold', y=0.95)
    plt.title(f"Based on 10,000 simulations of historical GP/hr & play habits | Remaining Gap: {gap/1000000:,.1f}M", 
              color="gray", fontsize=14, pad=8)

    ax.grid(axis='y', linestyle='--', alpha=0.2, color='white', zorder=-1)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    # Auto-appending the YYYYMMDDHHMM timestamp!
    timestamp_str = today.strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"monte_carlo_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_monte_carlo")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_monte_carlo.png")
        # Use the filename that was generated for the specific dir
        filename = os.path.basename(output_path)
        specific_path = os.path.join(specific_dir, filename)
        
        shutil.copy(output_path, recent_path)
        shutil.move(output_path, specific_path)
        print(f"-> Saved recent to: {recent_path}")
        print(f"-> Saved archived to: {specific_path}")
    except Exception as e:
        print(f"Error routing file: {e}")
    print(f"Chart saved successfully: {output_path}")

if __name__ == "__main__":
    main()