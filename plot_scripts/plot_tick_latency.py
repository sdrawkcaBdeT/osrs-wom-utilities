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
NORMALIZED_CSV = "../normalized_sessions.csv"
OUTPUT_DIR = "../analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Generating Tick Latency & Sloth Comparison ---")
    
    if not os.path.exists(DB_PATH) or not os.path.exists(NORMALIZED_CSV):
        return print("Missing required data (combat_telemetry.db or normalized_sessions.csv).")

    # 1. Fetch Telemetry Data
    conn = sqlite3.connect(DB_PATH)
    # Order strictly by session and time to calculate accurate time deltas
    df_hits = pd.read_sql_query("SELECT session_id, timestamp, dragon_hp_before FROM hitsplats ORDER BY session_id, timestamp", conn)
    conn.close()

    if df_hits.empty or len(df_hits) < 100:
        return print("Not enough telemetry data for tick analysis.")

    # 2. Calculate the exact time between shots (Delta T)
    df_hits['timestamp'] = pd.to_datetime(df_hits['timestamp'])
    df_hits['delta_s'] = df_hits.groupby('session_id')['timestamp'].diff().dt.total_seconds()

    # FILTERING: We only want to look at back-to-back attacks ON THE SAME DRAGON.
    # If the dragon_hp_before is near 315, it's a new dragon, meaning the time gap includes running/looting.
    # We also filter delta_s between 2.0s and 5.0s to catch the 5, 6, 7, and 8 tick gaps.
    # Anything > 5.0s means you completely missed an entire attack cycle.
    valid_attacks = df_hits[
        (df_hits['dragon_hp_before'] < 300) & 
        (df_hits['delta_s'] >= 2.0) & 
        (df_hits['delta_s'] <= 5.5)
    ].copy()

    # Calculate exact "Lost Ticks" per shot. 
    # Perfect DHCB Rapid = 3.0s. 1 tick = 0.6s. We use rounding to smooth out HTTP/Network jitter.
    valid_attacks['lost_ticks'] = np.round((valid_attacks['delta_s'] - 3.0) / 0.6)
    
    # 3. Aggregate Micro Sloth per Session
    micro_sloth = valid_attacks.groupby('session_id').agg(
        avg_lost_ticks=('lost_ticks', 'mean'),
        attacks_analyzed=('lost_ticks', 'count')
    ).reset_index()

    # 4. Merge with Macro Sloth
    df_norm = pd.read_csv(NORMALIZED_CSV)
    df_merged = pd.merge(micro_sloth, df_norm, on='session_id', how='inner')

    # 5. Setup Cinematic Plot (2 Panels)
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8), facecolor=BG_COLOR)
    fig.patch.set_facecolor(BG_COLOR)

    # ==========================================
    # PANEL 1: The OSRS Server Heartbeat (Histogram)
    # ==========================================
    ax1.set_facecolor(BG_COLOR)
    
    # Plot histogram with 0.05s bins to show network jitter clustering
    bins = np.arange(2.5, 5.5, 0.05)
    ax1.hist(valid_attacks['delta_s'], bins=bins, color="#00FFFF", edgecolor="#111111", alpha=0.8)

    # Draw vertical lines for the exact mathematical OSRS ticks
    ticks_to_plot =[
        (3.0, "Perfect (5-Tick)"),
        (3.6, "1 Tick Lost"),
        (4.2, "2 Ticks Lost"),
        (4.8, "3 Ticks Lost")
    ]
    
    for val, label in ticks_to_plot:
        ax1.axvline(val, color="#FFD700", linestyle="--", linewidth=2, zorder=3)
        txt = ax1.text(val + 0.05, ax1.get_ylim()[1] * 0.9, label, color="#FFD700", 
                       fontsize=11, fontweight='bold', rotation=90, va='top')
        txt.set_path_effects([path_effects.withStroke(linewidth=2, foreground='black')])

    ax1.set_xlabel("Seconds Between Consecutive Attacks", color=TEXT_COLOR, fontsize=12, fontweight='bold', labelpad=10)
    ax1.set_ylabel("Frequency", color=TEXT_COLOR, fontsize=12, fontweight='bold', labelpad=10)
    ax1.set_title("THE OSRS HEARTBEAT (HTTP JITTER VS. SERVER TICKS)", color=TEXT_COLOR, fontsize=16, fontweight='bold', pad=15)
    ax1.tick_params(axis='both', colors=TEXT_COLOR)

    # ==========================================
    # PANEL 2: Micro vs. Macro Sloth (Scatter)
    # ==========================================
    ax2.set_facecolor(BG_COLOR)

    # Bubble size = number of attacks analyzed
    scatter = ax2.scatter(
        x=df_merged['miss_per_hr'], 
        y=df_merged['avg_lost_ticks'], 
        c=df_merged['t_ngp_hr'], 
        cmap="RdYlGn", 
        s=df_merged['attacks_analyzed'] * 2, 
        alpha=0.8, 
        edgecolors="#FFFFFF", 
        linewidths=1.0,
        zorder=4
    )

    # Add trendline
    if len(df_merged) > 1:
        sns.regplot(data=df_merged, x='miss_per_hr', y='avg_lost_ticks', scatter=False, 
                    ax=ax2, color="#FF4444", line_kws={"linewidth": 3, "linestyle": "--", "zorder": 2})

    ax2.set_xlabel("Macro Sloth: Missed Attacks / Hr (JSON)", color=TEXT_COLOR, fontsize=12, fontweight='bold', labelpad=10)
    ax2.set_ylabel("Micro Sloth: Avg Lost Ticks per Shot (SQLite)", color=TEXT_COLOR, fontsize=12, fontweight='bold', labelpad=10)
    ax2.set_title("MACRO VS. MICRO INEFFICIENCY", color=TEXT_COLOR, fontsize=16, fontweight='bold', pad=15)
    ax2.tick_params(axis='both', colors=TEXT_COLOR)

    cbar = plt.colorbar(scatter, ax=ax2, pad=0.02)
    cbar.set_label("Theoretical Net GP/hr", color=TEXT_COLOR, size=11, fontweight='bold')
    cbar.ax.yaxis.set_tick_params(color=TEXT_COLOR)
    cbar.ax.tick_params(labelsize=10, colors=TEXT_COLOR)

    # Format Axes and Grid for both
    for ax in [ax1, ax2]:
        for spine in ['top', 'right']:
            ax.spines[spine].set_visible(False)
        ax.spines['bottom'].set_color('gray')
        ax.spines['left'].set_color('gray')
        ax.grid(axis='both', linestyle='--', alpha=0.15, color='white', zorder=-1)

    plt.tight_layout()
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"plot_tick_latency_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_tick_latency")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_tick_latency.png")
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