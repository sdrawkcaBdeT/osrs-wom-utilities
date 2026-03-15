import os
import shutil
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from datetime import datetime

# --- CONFIG ---
DB_PATH = "../combat_telemetry.db"
OUTPUT_DIR = "../analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Generating Empirical Hit Distribution ---")
    
    if not os.path.exists(DB_PATH):
        return print(f"Error: {DB_PATH} not found.")

    # 1. Fetch Telemetry Data
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT damage FROM hitsplats", conn)
    conn.close()

    if df.empty or len(df) < 100:
        return print("Not enough telemetry data. Shoot more dragons!")

    total_hits = len(df)
    zeroes = len(df[df['damage'] == 0])
    max_hit = df['damage'].max()

    # 2. Count the frequencies of every damage value
    hit_counts = df['damage'].value_counts().reindex(range(0, max_hit + 1), fill_value=0)
    
    # Calculate percentages for the annotations
    zero_pct = (zeroes / total_hits) * 100
    avg_dmg = df['damage'].mean()

    # 3. Setup Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"

    fig, ax = plt.subplots(figsize=(16, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    x_vals = hit_counts.index
    y_vals = hit_counts.values

    # Color the 0 bar bright red, and the rest a uniform cyan
    colors =["#FF4444" if x == 0 else "#00FFFF" for x in x_vals]

    # 4. Draw the Bar Chart
    bars = ax.bar(x_vals, y_vals, color=colors, edgecolor="#111111", linewidth=0.5, width=1.0, alpha=0.9)

    # 5. Draw the "Theoretical Flatline"
    # If OSRS RNG is truly uniform, every number from 1 to Max Hit should appear exactly this many times:
    non_zero_hits = total_hits - zeroes
    theoretical_uniform_count = non_zero_hits / max_hit if max_hit > 0 else 0
    
    ax.plot([1, max_hit], [theoretical_uniform_count, theoretical_uniform_count], 
            color="#FFD700", linestyle="--", linewidth=3, zorder=5, label="Theoretical Uniform Distribution")

    txt_theory = ax.text(max_hit * 0.5, theoretical_uniform_count * 1.05, 
                         "Perfect RNG Flatline", color="#FFD700", fontsize=12, fontweight='bold', ha='center', va='bottom')
    txt_theory.set_path_effects([path_effects.withStroke(linewidth=3, foreground=BG_COLOR)])

    # 6. Formatting
    ax.set_xlabel("Damage Dealt", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    ax.set_ylabel("Frequency (Number of Hits)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    ax.tick_params(axis='both', colors=TEXT_COLOR, labelsize=12)
    ax.set_xlim(-1, max_hit + 2)
    
    # Scale Y to fit the massive 0 bar, but add some headroom
    ax.set_ylim(0, zeroes * 1.15)

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    ax.grid(axis='y', linestyle='--', alpha=0.15, color='white', zorder=-1)

    # 7. Add Data Summary Card
    stats_txt = f"Total Bolts Fired: {total_hits:,}\n"
    stats_txt += f"Misses / 0s: {zero_pct:.1f}%\n"
    stats_txt += f"Average Damage: {avg_dmg:.2f}\n"
    stats_txt += f"Max Hit Recorded: {max_hit}"
    
    txt_box = ax.text(max_hit * 0.85, zeroes * 0.85, stats_txt, 
                      color="#0A0A0A", fontsize=14, fontweight='bold', ha='left', va='top',
                      bbox=dict(facecolor="#00FF00", edgecolor='white', boxstyle='round,pad=0.5', alpha=0.9))

    # Titles
    plt.suptitle("THE OSRS RNG FLATLINE: EMPIRICAL HIT DISTRIBUTION", color=TEXT_COLOR, fontsize=26, fontweight='bold', y=0.96)
    plt.title("Proving that in OSRS, you are mathematically just as likely to hit a 1 as you are your Max Hit.", 
              color="#AAAAAA", fontsize=15, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"plot_hit_distribution_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_empirical_hit_distribution")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_empirical_hit_distribution.png")
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