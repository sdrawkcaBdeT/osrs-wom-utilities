import os
import shutil
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patheffects as path_effects
from datetime import datetime

# --- CONFIG ---
DB_PATH = "../time_tracker.db"
OUTPUT_DIR = "../analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Generating Hours Logged Heatmap ---")
    
    if not os.path.exists(DB_PATH):
        return print(f"Error: {DB_PATH} not found.")

    # 1. Load the literal shift data
    conn = sqlite3.connect(DB_PATH)
    df_shifts = pd.read_sql_query("SELECT start_timestamp, end_timestamp FROM shifts WHERE type = 'WORK'", conn)
    conn.close()

    if df_shifts.empty:
        return print("No work shifts found in database.")

    df_shifts['start_timestamp'] = pd.to_datetime(df_shifts['start_timestamp'])
    # If a shift is currently running, use right now as the end time
    df_shifts['end_timestamp'] = pd.to_datetime(df_shifts['end_timestamp']).fillna(pd.Timestamp.now())

    # 2. Initialize a 7 (Days) x 24 (Hours) matrix of pure zeros
    matrix = np.zeros((7, 24))

    # 3. Slice every shift into the exact hour buckets it occupies
    for _, row in df_shifts.iterrows():
        start = row['start_timestamp']
        end = row['end_timestamp']
        
        # Floor to the start of the current hour
        current_block = start.floor('H')
        
        while current_block < end:
            next_block = current_block + pd.Timedelta(hours=1)
            
            # Find the overlap time within this specific hour block
            overlap_start = max(current_block, start)
            overlap_end = min(next_block, end)
            
            duration_hrs = (overlap_end - overlap_start).total_seconds() / 3600.0
            
            if duration_hrs > 0:
                day_idx = current_block.dayofweek
                hour_idx = current_block.hour
                matrix[day_idx, hour_idx] += duration_hrs
                
            current_block = next_block

    # Convert to DataFrame for Seaborn
    pivot = pd.DataFrame(matrix)

    # 4. Formatter: Show '0' explicitly, show 1 decimal for hours
    def format_hrs(val):
        if val == 0: return "0"
        return f"{val:.1f}h"
        
    annot_matrix = pivot.applymap(format_hrs)

    # 5. Render the Chart
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"
    
    # Colormap: 0 is Dark Red. Highest value is Neon Green.
    colors =["#2a0000", "#FF4444", "#FFD700", "#00FF00"]
    matrix_cmap = LinearSegmentedColormap.from_list("ryg_hours", colors, N=100)

    fig, ax = plt.subplots(figsize=(16, 7), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    
    # Draw heatmap
    sns.heatmap(pivot, cmap=matrix_cmap, ax=ax, linewidths=1.5, linecolor=BG_COLOR, 
                annot=annot_matrix, fmt="", annot_kws={"size": 10, "weight": "bold", "color": "white"},
                cbar_kws={'label': 'Total Hours Logged'})
    
    # Apply Black Stroke for readability
    for text in ax.texts:
        # If it's "0", maybe make it slightly dimmer so the actual playtime pops more
        if text.get_text() == "0":
            text.set_color("#888888")
            text.set_path_effects([path_effects.withStroke(linewidth=1.5, foreground='black')])
        else:
            text.set_color("white")
            text.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground='black')])
    
    # Format Colorbar
    cbar = ax.collections[0].colorbar
    cbar.ax.yaxis.set_tick_params(color=TEXT_COLOR)
    cbar.ax.tick_params(labelsize=10, colors=TEXT_COLOR)
    cbar.set_label("Total Historical Hours", color=TEXT_COLOR, size=12, fontweight='bold', labelpad=15)
    
    # Format X & Y Labels
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    hours = [f"{h:02d}:00" for h in range(24)]
    
    ax.set_yticklabels(days, rotation=0, color=TEXT_COLOR, fontsize=12)
    ax.set_xticklabels(hours, rotation=45, ha='right', color=TEXT_COLOR, fontsize=10)
    
    ax.set_ylabel("")
    ax.set_xlabel("Hour of Day (Local Time)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=10)
    
    # Titles
    plt.suptitle("GRIND HABITS: TOTAL HOURS PLAYED BY TIME OF DAY", color=TEXT_COLOR, fontsize=24, fontweight='bold', y=1.02)
    plt.title("Dark Red = Never Played | Neon Green = Heaviest Grind Windows", color="#AAAAAA", fontsize=14, pad=15)
    
    plt.tight_layout()
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"hours_logged_heatmap_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_hours_heatmap")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_hours_heatmap.png")
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