import os
import shutil
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.patheffects as path_effects
from datetime import datetime

# --- CONFIG ---
DB_PATH = "../combat_telemetry.db"
OUTPUT_DIR = "../analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Generating The Overkill Cliff ---")
    
    if not os.path.exists(DB_PATH):
        return print(f"Error: {DB_PATH} not found.")

    # 1. Fetch Telemetry Data
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT damage, dragon_hp_before FROM hitsplats WHERE dragon_hp_before > 0", conn)
    conn.close()

    if df.empty or len(df) < 200:
        return print("Not enough HP telemetry data to build the cliff.")

    # 2. Bin the Dragon's HP into 10-HP chunks (e.g., 0-10, 10-20, ... 310-320)
    # We calculate the AVERAGE damage you deal inside each of those brackets
    bins = np.arange(0, 330, 10)
    df['hp_bracket'] = pd.cut(df['dragon_hp_before'], bins=bins, labels=bins[:-1] + 5)
    
    # Calculate Mean Damage per Bracket
    cliff_data = df.groupby('hp_bracket')['damage'].mean().reset_index()
    cliff_data = cliff_data.dropna()

    # 3. Setup Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"

    fig, ax = plt.subplots(figsize=(14, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # 4. Draw the Cliff (Line Plot)
    # We plot the X-axis in reverse! (From 315 down to 0) to simulate the actual timeline of killing the dragon
    ax.plot(cliff_data['hp_bracket'], cliff_data['damage'], color="#00FF00", linewidth=4, marker='o', markersize=8, markerfacecolor="#FFFFFF", zorder=4)

    # 5. Fill the Overkill Tax Zone
    # Draw a flat baseline of your "Expected Hit" when the dragon is healthy (e.g., above 100 HP)
    healthy_hits = df[df['dragon_hp_before'] > 100]
    expected_hit = healthy_hits['damage'].mean()
    
    ax.axhline(expected_hit, color="#FFD700", linestyle="--", linewidth=2, zorder=3, label="Theoretical Expected Hit")
    
    # Shade the area where the green line drops below the yellow dashed line in red
    ax.fill_between(cliff_data['hp_bracket'], cliff_data['damage'], expected_hit, 
                    where=(cliff_data['damage'] < expected_hit), color="#FF4444", alpha=0.3, zorder=2)

    # 6. Formatting
    ax.set_xlabel("Dragon's Remaining Health", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    ax.set_ylabel("Average Damage Dealt per Shot", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    ax.tick_params(axis='both', colors=TEXT_COLOR, labelsize=12)
    
    # REVERSE THE X-AXIS! So it reads left-to-right from 315 down to 0 HP
    ax.set_xlim(320, -5)
    ax.set_ylim(0, expected_hit * 1.5)

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    ax.grid(axis='both', linestyle='--', alpha=0.15, color='white', zorder=-1)

    # 7. Annotations
    txt_tax = ax.text(30, expected_hit / 2, "THE OVERKILL\nTAX", color="#FF4444", 
                      fontsize=20, fontweight='bold', ha='center', va='center')
    txt_tax.set_path_effects([path_effects.withStroke(linewidth=3, foreground=BG_COLOR)])

    # Titles
    plt.suptitle("THE OVERKILL CLIFF", color=TEXT_COLOR, fontsize=26, fontweight='bold', y=0.96)
    plt.title(f"Visualizing the exact moment high-damage Ranged gear loses its efficiency | Based on {len(df):,} attacks", 
              color="#AAAAAA", fontsize=15, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"plot_overkill_cliff_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_overkill_cliff")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_overkill_cliff.png")
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