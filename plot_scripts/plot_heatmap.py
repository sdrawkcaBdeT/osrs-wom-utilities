import os
import shutil
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patheffects as path_effects
from datetime import datetime

# --- CONFIG ---
DATA_DIR = "../bbd_data"
NORMALIZED_CSV = "../normalized_sessions.csv"
OUTPUT_DIR = "../analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Generating Grind Heatmap (Red-Yellow-Green) ---")
    
    if not os.path.exists(NORMALIZED_CSV):
        return print("Error: normalized_sessions.csv not found.")
        
    df_norm = pd.read_csv(NORMALIZED_CSV)
    
    # 1. Extract exact timestamps from JSONs
    time_data =[]
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            time_data.append({
                "session_id": data.get("session_id"),
                "start_time": pd.to_datetime(data.get("start_time"))
            })
            
    df_times = pd.DataFrame(time_data)
    
    # 2. Merge timestamps with normalized GP/hr
    df = pd.merge(df_norm, df_times, on="session_id", how="inner")
    
    if df.empty:
        return print("No overlapping data found.")

    # 3. Extract Day of Week and Hour
    df['DayOfWeek'] = df['start_time'].dt.dayofweek
    df['Hour'] = df['start_time'].dt.hour
    
    # 4. Create the Pivot Table
    pivot = df.pivot_table(values='t_ngp_hr', index='DayOfWeek', columns='Hour', aggfunc='mean')
    pivot = pivot.reindex(index=range(7), columns=range(24))
    
    # Create formatted text annotations for the squares
    def format_gp(val):
        if pd.isna(val): return ""
        if val >= 1000000: return f"{val/1000000:.1f}M"
        elif val >= 1000: return f"{val/1000:.0f}K"
        return f"{val:.0f}"
        
    annot_matrix = pivot.applymap(format_gp)

    # 5. Render the Cinematic Heatmap
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"
    
    # --- NEW: Red -> Yellow -> Green Colormap ---
    # Deep Red -> Bright Red -> Gold/Yellow -> Bright Green
    colors =["#660000", "#FF4444", "#FFD700", "#00FF00"]
    matrix_cmap = LinearSegmentedColormap.from_list("ryg_matrix", colors, N=100)

    fig, ax = plt.subplots(figsize=(16, 7), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)  # This ensures empty squares (NaNs) are dark background
    
    # Draw heatmap
    sns.heatmap(pivot, cmap=matrix_cmap, ax=ax, linewidths=1.5, linecolor=BG_COLOR, 
                annot=annot_matrix, fmt="", annot_kws={"size": 10, "weight": "bold", "color": "white"},
                cbar_kws={'label': 'Theoretical Net GP/hr'})
    
    # --- NEW: Apply Black Stroke to Text Annotations ---
    # This prevents white text from washing out on the yellow squares
    for text in ax.texts:
        text.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground='black')])
    
    # Format the Colorbar
    cbar = ax.collections[0].colorbar
    cbar.ax.yaxis.set_tick_params(color=TEXT_COLOR)
    cbar.ax.tick_params(labelsize=10, colors=TEXT_COLOR)
    cbar.set_label("Theoretical Net GP/hr", color=TEXT_COLOR, size=12, fontweight='bold', labelpad=15)
    
    # Format X & Y Labels
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    hours = [f"{h:02d}:00" for h in range(24)]
    
    ax.set_yticklabels(days, rotation=0, color=TEXT_COLOR, fontsize=12)
    ax.set_xticklabels(hours, rotation=45, ha='right', color=TEXT_COLOR, fontsize=10)
    
    ax.set_ylabel("")
    ax.set_xlabel("Hour of Day (Local Time)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=10)
    
    # Titles
    plt.suptitle("EFFICIENCY HEATMAP: NET GP/HR BY TIME OF DAY", color=TEXT_COLOR, fontsize=24, fontweight='bold', y=1.02)
    plt.title("Red = Slow Kills / High AFK | Green = Peak Efficiency", color="#AAAAAA", fontsize=14, pad=15)
    
    plt.tight_layout()
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"grind_heatmap_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_heatmap")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_heatmap.png")
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