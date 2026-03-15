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
    print("--- Generating The Noodle Index ---")
    
    if not os.path.exists(DB_PATH):
        return print(f"Error: {DB_PATH} not found.")

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT damage FROM hitsplats", conn)
    conn.close()

    if df.empty or len(df) < 500:
        return print("Not enough telemetry data for streak analysis.")

    # 1. Count the zero streaks
    hits = df['damage'].values
    streaks =[]
    current_streak = 0
    
    for h in hits:
        if h == 0:
            current_streak += 1
        else:
            if current_streak > 0:
                streaks.append(current_streak)
                current_streak = 0
    if current_streak > 0:
        streaks.append(current_streak)

    if not streaks:
        return print("No misses recorded yet. You are a god.")

    streak_counts = pd.Series(streaks).value_counts().sort_index()
    
    # 2. Calculate Theoretical Geometric Distribution
    total_attacks = len(hits)
    miss_prob = len(df[df['damage'] == 0]) / total_attacks
    hit_prob = 1.0 - miss_prob
    
    # Expected number of streaks of exactly length k is roughly: N * (hit_prob) * (miss_prob^k)
    max_streak = streak_counts.index.max()
    x_vals = np.arange(1, max_streak + 2)
    expected_counts = total_attacks * hit_prob * (miss_prob ** x_vals)

    # 3. Setup Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"

    fig, ax = plt.subplots(figsize=(14, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # Plot empirical bars
    bars = ax.bar(streak_counts.index, streak_counts.values, color="#FF4444", edgecolor="#111111", linewidth=1.5, label="Actual Streaks of Zeroes")
    
    # Plot theoretical curve
    ax.plot(x_vals, expected_counts, color="#00FF00", linewidth=3, linestyle="--", marker="o", label="Expected Mathematical Frequency")

    # Annotations
    for bar in bars:
        height = bar.get_height()
        txt = ax.text(bar.get_x() + bar.get_width()/2, height + (max(streak_counts.values)*0.02), 
                      f"{int(height)}", ha='center', va='bottom', color=TEXT_COLOR, fontweight='bold')
        txt.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground='black')])

    # Formatting
    ax.set_xlabel("Length of 'Zero' Streak (Consecutive Misses)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    ax.set_ylabel("Frequency (Log Scale)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    ax.tick_params(axis='both', colors=TEXT_COLOR, labelsize=12)
    
    # Use Log Scale because streak probabilities drop off exponentially
    ax.set_yscale('log')
    
    # Force integer ticks on X
    ax.set_xticks(x_vals)

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    ax.grid(axis='y', linestyle='--', alpha=0.15, color='white', zorder=-1)
    
    ax.legend(facecolor='#111111', edgecolor='#333333', fontsize=12, loc='upper right', labelcolor=TEXT_COLOR)

    # Titles
    plt.suptitle("THE NOODLE INDEX: OSRS RNG INDEPENDENCE", color=TEXT_COLOR, fontsize=26, fontweight='bold', y=0.96)
    plt.title(f"If the Red Bars extend past the Green Line, the server is actively clumping your bad luck. | Empirical Miss Rate: {miss_prob*100:.1f}%", 
              color="#AAAAAA", fontsize=14, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"plot_noodle_index_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_noodle_index")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_noodle_index.png")
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