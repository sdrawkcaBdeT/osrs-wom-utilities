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
    print("--- Generating The Overkill Tax Chart ---")
    
    if not os.path.exists(NORMALIZED_CSV):
        return print(f"Error: {NORMALIZED_CSV} not found.")

    # 1. Load Normalized Data
    df_norm = pd.read_csv(NORMALIZED_CSV)
    
    # 2. Extract Theoretical Stats from JSONs
    json_data =[]
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            theo = data.get("theoretical_stats", {})
            
            json_data.append({
                "session_id": data.get("session_id"),
                "max_hit": theo.get("max_hit", 0),
                "theo_ttk": theo.get("ttk", 0)
            })
            
    df_json = pd.DataFrame(json_data)
    
    # 3. Merge and Filter
    df = pd.merge(df_norm, df_json, on="session_id", how="inner")
    
    # Only keep valid sessions with kills and theoretical stats
    df = df[(df['total_kills'] > 0) & (df['max_hit'] > 0) & (df['theo_ttk'] > 0)].copy()
    
    if df.empty:
        return print("No valid sessions with theoretical stats found.")

    # 4. Calculate Actual TTK and Delta TTK
    # Active Hours -> Seconds, divided by Total Kills
    df['act_ttk'] = (df['active_hrs'] * 3600) / df['total_kills']
    
    # Delta TTK: Positive means the kill took LONGER than the calculator predicted
    df['delta_ttk'] = df['act_ttk'] - df['theo_ttk']

    # Filter out extreme anomalies (e.g., leaving it logged in while AFK) to protect the trendline
    df = df[(df['delta_ttk'] > -10) & (df['delta_ttk'] < 20)]

    # 5. Setup Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"
    C_DOTS = "#00FFFF"      # Cyan for sessions
    C_TREND = "#FF4444"     # Red for the Overkill Tax trendline
    C_ZERO = "#00FF00"      # Green for the "Perfect Theory" baseline

    fig, ax = plt.subplots(figsize=(14, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # 6. Draw Scatter Plot with Trendline
    sns.regplot(
        data=df, 
        x="max_hit", 
        y="delta_ttk", 
        ax=ax,
        color=C_DOTS,
        scatter_kws={"s": 100, "alpha": 0.7, "edgecolors": "#FFFFFF", "linewidths": 1.0, "zorder": 4},
        line_kws={"color": C_TREND, "linewidth": 4, "zorder": 5}
    )

    # 7. Draw the "Perfect Calculator" Baseline
    # If the calculator was perfectly accurate, all dots would sit on the 0.0 line
    ax.axhline(0, color=C_ZERO, linestyle="--", linewidth=2.5, zorder=3)
    
    txt_base = ax.text(df['max_hit'].min(), 0.2, "Calculator Prediction (0.0s Penalty)", 
                       color=C_ZERO, fontsize=12, fontweight='bold', va='bottom', ha='left')
    txt_base.set_path_effects([path_effects.withStroke(linewidth=3, foreground=BG_COLOR)])

    # 8. Annotate the Trend (The Overkill Tax)
    slope, intercept = np.polyfit(df['max_hit'], df['delta_ttk'], 1)
    sign = "+" if slope > 0 else ""
    
    tax_text = f"Overkill Tax Rate:\n{sign}{slope:.2f} seconds lost per +1 Max Hit"
    
    # Position text dynamically near the top-left or top-right based on the data
    txt_slope = ax.text(df['max_hit'].min() + 0.5, df['delta_ttk'].max() * 0.85, 
                        tax_text, color=C_TREND, fontsize=16, fontweight='bold',
                        bbox=dict(facecolor="#220000", edgecolor=C_TREND, boxstyle='round,pad=0.5', alpha=0.8))

    # 9. Formatting the Axes
    ax.set_xlabel("Theoretical Max Hit", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    ax.set_ylabel("Seconds Slower Than Calculator ($\Delta$TTK)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    ax.tick_params(axis='both', colors=TEXT_COLOR, labelsize=12)
    
    # Format Y-Axis to explicitly show the "+" or "-" seconds
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:+.1f}s"))

    # Force X-Axis to use integer ticks since Max Hit is always a whole number
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))

    for spine in['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    
    ax.grid(axis='both', linestyle='--', alpha=0.15, color='white', zorder=1)

    # 10. Titles
    plt.suptitle("THE OVERKILL TAX", color=TEXT_COLOR, fontsize=26, fontweight='bold', y=0.96)
    plt.title("Why the DPS Calculator lies to you about high-end Ranged gear.", 
              color="#AAAAAA", fontsize=15, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    # Save with precise timestamp
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"overkill_tax_chart_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_overkill_tax")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_overkill_tax.png")
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