import os
import shutil
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from datetime import datetime

# --- CONFIG ---
DATA_DIR = "../bbd_data"
OUTPUT_DIR = "../analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def parse_iso_time(ts_str):
    try:
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except:
        return None

def main():
    print("--- Generating Bank Trip (Away Time) Histogram ---")
    
    if not os.path.exists(DATA_DIR):
        return print(f"Error: {DATA_DIR} not found.")

    bank_times =[]

    # 1. Parse JSONs for Away -> Killing deltas
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            
        timeline = data.get('event_timeline',[])
        
        has_started_killing = False
        away_start = None
        
        for e in timeline:
            e_time = parse_iso_time(e['timestamp'])
            if not e_time: continue
                
            if e['type'] == 'phase':
                if "KILLING" in e['value']:
                    has_started_killing = True
                    if away_start is not None:
                        trip_time = (e_time - away_start).total_seconds()
                        
                        # Disqualify anything under 15 seconds
                        if 15 <= trip_time <= 900:
                            bank_times.append(trip_time)
                            
                        away_start = None
                elif "AWAY" in e['value']:
                    if has_started_killing:
                        away_start = e_time

    if len(bank_times) < 5:
        return print("Not enough bank trip data to build a histogram.")

    # 2. CALCULATE DYNAMIC BASELINE
    baseline = np.percentile(bank_times, 2)
    print(f"Calculated Dynamic Baseline (2nd Percentile): {baseline:.1f} seconds")

    zones =[
        {"label": "Tick-Perfect?", "max": baseline + 5,   "color": "#00FFFF"},  # Cyan
        {"label": "Fast",          "max": baseline + 20,  "color": "#00FF00"},  # Neon Green
        {"label": "Normal",        "max": baseline + 45,  "color": "#FFD700"},  # Gold
        {"label": "Slow",          "max": baseline + 90,  "color": "#FF8800"},  # Orange
        {"label": "Sidetracked",   "max": float('inf'),   "color": "#880000"}   # Deep Red
    ]

    total_trips = len(bank_times)
    zone_counts = [0] * len(zones)
    
    for val in bank_times:
        for i, z in enumerate(zones):
            if val <= z['max']:
                zone_counts[i] += 1
                break

    # 3. Setup Histogram Bins (2-second buckets)
    x_min = min(bank_times)
    x_max = max(240, np.percentile(bank_times, 95) * 1.1)
    
    # Create the buckets
    bin_width = 2
    bins = np.arange(int(x_min), int(x_max) + bin_width, bin_width)
    counts, edges = np.histogram(bank_times, bins=bins)
    max_count = max(counts)

    # 4. Setup Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"

    fig, ax = plt.subplots(figsize=(16, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # 5. Draw the colored bars
    for i in range(len(counts)):
        if counts[i] == 0: continue
        
        # Determine the color of this specific bar based on its center
        bar_center = (edges[i] + edges[i+1]) / 2
        bar_color = "#880000" # Default to sidetracked
        for z in zones:
            if bar_center <= z['max']:
                bar_color = z['color']
                break
                
        # Draw the bar with a crisp dark outline
        ax.bar(edges[i], counts[i], width=bin_width, align='edge', 
               color=bar_color, edgecolor="#111111", linewidth=1.0, alpha=0.9, zorder=3)

    # 6. Draw Annotations and Dividing Lines
    prev_max = 0
    for i, z in enumerate(zones):
        z_max = z['max'] if z['max'] != float('inf') else x_max
        
        # Draw the dividing line
        if prev_max > 0 and prev_max < x_max:
            ax.axvline(prev_max, color="#FFFFFF", linestyle="--", linewidth=1.5, alpha=0.4, zorder=2)
            
        # Find the highest bar in THIS specific zone to float the text properly
        zone_bars =[c for j, c in enumerate(counts) if prev_max < edges[j] <= z_max]
        peak_in_zone = max(zone_bars) if zone_bars else 0
        
        x_center = (prev_max + min(z_max, x_max)) / 2
        y_pos = peak_in_zone + (max_count * 0.05) # Float 5% above the highest bar in the zone
        
        # If the zone is completely flat/empty, push the text up slightly so it doesn't sit on the floor
        if peak_in_zone == 0:
            y_pos = max_count * 0.1
            
        pct = (zone_counts[i] / total_trips) * 100
        label_txt = f"{z['label']}\n{pct:.1f}%"
        
        txt_obj = ax.text(x_center, y_pos, label_txt, color=z['color'], 
                          fontsize=12, fontweight='bold', ha='center', va='bottom', zorder=6)
        txt_obj.set_path_effects([path_effects.withStroke(linewidth=3, foreground='black')])

        prev_max = z['max']

    # 7. Formatting
    ax.set_xlabel("Seconds Away From Boss (Banking, Running, Slacking)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    ax.set_ylabel("Number of Trips", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)

    ax.tick_params(axis='x', colors=TEXT_COLOR, labelsize=12)
    ax.tick_params(axis='y', colors=TEXT_COLOR, labelsize=12)
    ax.set_xlim(x_min - 10, x_max) # Add a small buffer to the left so the wall doesn't touch the Y-axis
    ax.set_ylim(0, max_count * 1.2) # 20% headroom for text

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')

    # --- Variable Resolution X-Axis Ticks ---
    # High detail where the sweaty banking happens, low detail in the AFK wasteland
    custom_ticks =[15, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90]
    
    # Fill in the rest of the chart by 30s
    tick_val = 120
    while tick_val <= x_max + 30:
        custom_ticks.append(tick_val)
        tick_val += 30
        
    ax.set_xticks(custom_ticks)
    ax.grid(axis='y', linestyle='--', alpha=0.15, color='white', zorder=-1)

    # Overall Median annotation
    median_away = np.median(bank_times)
    med_txt = ax.text(x_max * 0.95, max_count * 1.1, f"Median Trip:\n{median_away:.1f} Sec\n\nSweaty Baseline:\n{baseline:.1f} Sec", 
                      color=TEXT_COLOR, fontsize=14, fontweight='bold', ha='right')
    med_txt.set_path_effects([path_effects.withStroke(linewidth=3, foreground='#333333')])

    # Titles
    plt.suptitle("FOCUS DISTRIBUTION: TIME SPENT BANKING", color=TEXT_COLOR, fontsize=24, fontweight='bold', y=0.96)
    plt.title(f"Sample Size: {total_trips:,} Bank Trips | Binned in 2-second intervals", 
              color="#AAAAAA", fontsize=14, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"banking_distribution_hist_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_banking")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_banking.png")
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