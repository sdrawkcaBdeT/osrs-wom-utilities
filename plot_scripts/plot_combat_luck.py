import os
import shutil
import json
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from datetime import datetime

# --- CONFIG ---
DATA_DIR = "../bbd_data"
DB_PATH = "../combat_telemetry.db"
OUTPUT_DIR = "../analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Generating Combat Luck (Delta DPS) Chart ---")
    
    if not os.path.exists(DATA_DIR) or not os.path.exists(DB_PATH):
        return print("Missing required data folders/databases.")

    # 1. Get theoretical DPS from JSONs
    session_theos = {}
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            s_id = data.get("session_id")
            theo = data.get("theoretical_stats", {})
            if theo.get("dps", 0) > 0:
                session_theos[s_id] = {
                    "name": data.get("config", {}).get("experiment_name", s_id),
                    "theo_dps": theo["dps"]
                }

    # 2. Get actual DPS from SQLite
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT session_id, SUM(damage) as total_dmg, COUNT(*) as bolts_fired FROM hitsplats GROUP BY session_id", conn)
    conn.close()

    if df.empty:
        return print("No combat telemetry found.")

    plot_data =[]
    total_delta = 0

    for _, row in df.iterrows():
        s_id = row['session_id']
        if s_id in session_theos:
            act_dps = row['total_dmg'] / (row['bolts_fired'] * 3.0)  # Assume 3.0s per DHCB hit
            theo_dps = session_theos[s_id]['theo_dps']
            delta = act_dps - theo_dps
            
            total_delta += delta
            plot_data.append({
                "name": session_theos[s_id]['name'],
                "delta": delta,
                "bolts": row['bolts_fired']
            })

    if not plot_data:
        return print("No sessions matched between JSON and SQLite.")

    # Sort by how lucky/unlucky you were
    df_plot = pd.DataFrame(plot_data).sort_values(by="delta", ascending=True)

    # 3. Setup Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"
    SPOONED_FILL = "#008800"
    DRY_FILL = "#AA2222"
    SPOONED_TEXT = "#00FF00"
    DRY_TEXT = "#FF4444"

    fig, ax = plt.subplots(figsize=(14, 10), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    bars = ax.barh(df_plot['name'], df_plot['delta'], 
                   color=[SPOONED_FILL if x > 0 else DRY_FILL for x in df_plot['delta']], 
                   edgecolor="#222222", height=0.7)

    ax.axvline(0, color=TEXT_COLOR, linewidth=1.5, zorder=0)

    # Formatting axes
    ax.set_xlabel("DPS Variance ($\Delta$DPS)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    ax.tick_params(axis='x', colors=TEXT_COLOR, labelsize=12)
    ax.tick_params(axis='y', colors=TEXT_COLOR, labelsize=11)

    for spine in ['top', 'right', 'left']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.grid(axis='x', linestyle='--', alpha=0.2, color='white', zorder=-1)

    # Annotate Top 3 and Bottom 3
    chart_span = df_plot['delta'].max() - df_plot['delta'].min()
    offset = chart_span * 0.015 if chart_span > 0 else 0.1

    for i, bar in enumerate(bars):
        if i < 3 or i >= len(bars) - 3:
            val = bar.get_width() 
            txt = f"{val:+.2f}"
            
            if val > 0:
                x_pos, align, txt_color = val + offset, 'left', SPOONED_TEXT
            else:
                x_pos, align, txt_color = val - offset, 'right', DRY_TEXT
                
            text_obj = ax.text(x_pos, bar.get_y() + bar.get_height()/2, txt, 
                               color=txt_color, ha=align, va='center', fontweight='bold', fontsize=12)
            text_obj.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground='white')])

    # Titles
    plt.suptitle("COMBAT RNG: ACTUAL VS. THEORETICAL DPS", color=TEXT_COLOR, fontsize=24, fontweight='bold', y=0.95)
    luck_str = f"Net Account Combat Luck: {'+' if total_delta > 0 else ''}{total_delta:,.2f} DPS"
    luck_color = SPOONED_TEXT if total_delta > 0 else DRY_TEXT
    plt.title(luck_str, color=luck_color, fontsize=16, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"plot_combat_luck_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_combat_luck")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_combat_luck.png")
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