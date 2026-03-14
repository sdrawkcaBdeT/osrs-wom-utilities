import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from matplotlib.colors import ListedColormap, BoundaryNorm
from datetime import datetime

# --- CONFIG ---
NORMALIZED_CSV = "normalized_sessions.csv"
OUTPUT_DIR = "analytics_output"

# Set this to False if you want to use ACTUAL GP/hr (including your drop RNG)
USE_THEORETICAL_GP = True 

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Generating The AFK Matrix (Discrete Colors) ---")
    
    if not os.path.exists(NORMALIZED_CSV):
        return print(f"Error: {NORMALIZED_CSV} not found.")

    df = pd.read_csv(NORMALIZED_CSV)
    
    # 1. Filter out bad data
    df = df[(df['total_attacks'] > 0) & (df['trips'] > 0) & (df['active_hrs'] > 0)].copy()
    if df.empty:
        return print("Not enough complete session data to build the matrix.")

    # 2. Calculate Metrics
    df['astb'] = (df['bank_hrs'] * 3600) / df['trips']
    
    # Missed attacks (Rapid = 5 ticks = 3.0s)
    df['max_attacks'] = (df['active_hrs'] * 3600) / 3.0
    df['missed_attacks'] = np.maximum(0, df['max_attacks'] - df['total_attacks'])
    df['miss_per_hr'] = df['missed_attacks'] / df['active_hrs']

    # Filter massive anomalies
    df = df[(df['astb'] < 300) & (df['miss_per_hr'] < 1000)]

    # Calculate Actual Net GP/hr just in case you want to use it
    df['actual_ngp_hr'] = df['t_ngp_hr'] + (df['rng_variance_gp'] / df['duration_hrs'])

    # Select the target variable for the colors
    target_col = 't_ngp_hr' if USE_THEORETICAL_GP else 'actual_ngp_hr'
    metric_name = "Theoretical Net GP/hr" if USE_THEORETICAL_GP else "Actual Net GP/hr (Inc. RNG)"

    # 3. Create DISCRETE Bins (Quintiles: Bottom 20%, 20-40%, etc.)
    # This guarantees the colors are evenly distributed across your actual performance range
    bins = np.percentile(df[target_col], [0, 20, 40, 60, 80, 100])
    
    # Shift the absolute min/max slightly so no data points fall out of bounds
    bins[0] -= 1 
    bins[-1] += 1

    # 5 Distinct Colors: Red -> Orange -> Gold -> Light Green -> Neon Green
    discrete_colors =["#FF3333", "#FF8800", "#FFD700", "#88FF00", "#00FF00"]
    cmap = ListedColormap(discrete_colors)
    norm = BoundaryNorm(bins, cmap.N)

    # 4. Setup Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"

    fig, ax = plt.subplots(figsize=(14, 10), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # 5. Draw Scatter Plot
    scatter = ax.scatter(
        x=df['astb'], 
        y=df['miss_per_hr'], 
        c=df[target_col], 
        cmap=cmap, 
        norm=norm,
        s=180, # Made dots slightly larger
        alpha=0.9, 
        edgecolors="#222222", 
        linewidths=1.5,
        zorder=4
    )

    # 6. Draw Quadrants (using medians)
    med_astb = df['astb'].median()
    med_miss = df['miss_per_hr'].median()
    
    ax.axvline(med_astb, color="gray", linestyle="--", linewidth=1.5, zorder=2)
    ax.axhline(med_miss, color="gray", linestyle="--", linewidth=1.5, zorder=2)

    # 7. Annotate Quadrants
    def add_quadrant_label(x, y, text):
        ax.text(x, y, text, color="#555555", fontsize=28, fontweight='bold', 
                ha='center', va='center', zorder=1, alpha=0.4)
        
    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    
    add_quadrant_label(x_min + (med_astb - x_min)/2, y_min + (med_miss - y_min)/2, "THE SWEAT\nZONE")
    add_quadrant_label(med_astb + (x_max - med_astb)/2, med_miss + (y_max - med_miss)/2, "TRUE AFK\n(THE SLOTH)")
    add_quadrant_label(x_min + (med_astb - x_min)/2, med_miss + (y_max - med_miss)/2, "SLOW\nCOMBAT")
    add_quadrant_label(med_astb + (x_max - med_astb)/2, y_min + (med_miss - y_min)/2, "SLOW\nBANKING")

    # 8. Add the Discrete Colorbar
    cbar = plt.colorbar(scatter, ax=ax, pad=0.02, ticks=bins)
    cbar.ax.yaxis.set_tick_params(color=TEXT_COLOR)
    cbar.ax.tick_params(labelsize=11, colors=TEXT_COLOR)
    cbar.set_label(f"{metric_name} (Performance Tiers)", color=TEXT_COLOR, size=13, fontweight='bold', labelpad=15)
    
    def cb_formatter(x, pos):
        if x >= 1000000: return f"{x/1000000:.2f}M"
        elif x >= 1000: return f"{x/1000:.0f}K"
        return ""
    cbar.ax.yaxis.set_major_formatter(plt.FuncFormatter(cb_formatter))

    # 9. Formatting Axes
    ax.set_xlabel("Average Seconds to Bank (ASTB)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    ax.set_ylabel("Missed Attacks / Active Hour", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    ax.tick_params(axis='both', colors=TEXT_COLOR, labelsize=12)

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    
    ax.grid(axis='both', linestyle='--', alpha=0.15, color='white', zorder=1)

    # 10. Titles
    plt.suptitle('YOU SHOULD AFK WHEN YOU AFK', color=TEXT_COLOR, fontsize=26, fontweight='bold', y=0.96)
    
    # Calculate how many "Peak" sessions fell into the Sloth quadrant
    sloth_peak_mask = (df['astb'] > med_astb) & (df['miss_per_hr'] > med_miss) & (df[target_col] >= bins[-2])
    sloth_peak_count = sloth_peak_mask.sum()
    
    plt.title(f"The Tryhard Index | {sloth_peak_count} 'S-Tier' sessions occurred while playing lazily.", 
              color="#AAAAAA", fontsize=15, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"afk_matrix_discrete_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    print(f"Chart saved successfully: {output_path}")

if __name__ == "__main__":
    main()