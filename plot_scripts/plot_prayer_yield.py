import os
import shutil
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.patheffects as path_effects
from datetime import datetime

# --- CONFIG ---
NORMALIZED_CSV = "../normalized_sessions.csv"
DATA_DIR = "../bbd_data"
OUTPUT_DIR = "../analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Generating The Prayer Yield Curve ---")
    
    if not os.path.exists(NORMALIZED_CSV):
        return print(f"Error: {NORMALIZED_CSV} not found.")

    # 1. Load Normalized Data
    df_norm = pd.read_csv(NORMALIZED_CSV)
    
    # Calculate Supply Cost per Hour
    df_norm['cost_per_hr'] = df_norm['actual_supply_cost'] / df_norm['duration_hrs']
    
    # 2. Extract Prayer Bonus from JSONs
    json_data =[]
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            theo = data.get("theoretical_stats", {})
            
            json_data.append({
                "session_id": data.get("session_id"),
                "pray_bonus": theo.get("pray_bonus", None)
            })
            
    df_json = pd.DataFrame(json_data)
    
    # 3. Merge and Filter
    df = pd.merge(df_norm, df_json, on="session_id", how="inner")
    
    # Drop rows without a prayer bonus logged, or weird 0-cost sessions
    df = df.dropna(subset=['pray_bonus'])
    df = df[df['cost_per_hr'] > 0].copy()
    
    if df.empty:
        return print("No valid sessions with prayer bonus data found.")

    # 4. Setup Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"
    C_DOTS = "#00FFFF"      # Cyan for sessions
    C_TREND = "#FFD700"     # Gold for the Yield Curve

    fig, ax = plt.subplots(figsize=(14, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # 5. Draw Scatter Plot with a Non-Linear (Polynomial) Trendline
    # We use order=2 (quadratic) because prayer reduction yields diminishing returns!
    sns.regplot(
        data=df, 
        x="pray_bonus", 
        y="cost_per_hr", 
        ax=ax,
        order=2,
        color=C_DOTS,
        scatter_kws={"s": 120, "alpha": 0.7, "edgecolors": "#FFFFFF", "linewidths": 1.0, "zorder": 4},
        line_kws={"color": C_TREND, "linewidth": 4, "zorder": 5}
    )

    # 6. Formatting the Axes
    ax.set_xlabel("In-Game Prayer Bonus", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    ax.set_ylabel("Supply Cost per Hour", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    ax.tick_params(axis='both', colors=TEXT_COLOR, labelsize=12)
    
    # Format Y-Axis to K (Thousands)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x/1000:.0f}K"))

    # Add some breathing room on the X-axis
    ax.set_xlim(df['pray_bonus'].min() - 2, df['pray_bonus'].max() + 2)

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    
    ax.grid(axis='both', linestyle='--', alpha=0.15, color='white', zorder=1)

    # 7. Add Annotations to explain the curve
    txt_info = ax.text(df['pray_bonus'].max() * 0.98, df['cost_per_hr'].max() * 0.95, 
                       "Notice the curve flattening.\nAdding +5 Prayer at the low end\nsaves more GP than adding\n+5 Prayer at the high end.", 
                       color=C_TREND, fontsize=14, fontweight='bold', ha='right', va='top',
                       bbox=dict(facecolor="#222200", edgecolor=C_TREND, boxstyle='round,pad=0.5', alpha=0.8))

    # 8. Titles
    plt.suptitle("THE PRAYER YIELD CURVE", color=TEXT_COLOR, fontsize=26, fontweight='bold', y=0.96)
    plt.title("Diminishing Returns: Does stacking Prayer Bonus actually save you money?", 
              color="#AAAAAA", fontsize=15, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    # Save with the new naming convention
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"plot_prayer_yield_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_prayer_yield")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_prayer_yield.png")
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