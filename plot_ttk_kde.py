import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde
import matplotlib.patheffects as path_effects
from datetime import datetime

# --- CONFIG ---
DATA_DIR = "bbd_data"
OUTPUT_DIR = "analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def parse_iso_time(ts_str):
    try:
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except:
        return None

def main():
    print("--- Generating Advanced TTK KDE Chart ---")
    
    if not os.path.exists(DATA_DIR):
        return print(f"Error: {DATA_DIR} not found.")

    ttk_data =[]

    # 1. Parse JSONs for exact kill deltas
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            
        timeline = data.get('event_timeline',[])
        
        in_killing_phase = False
        last_event_time = None
        
        for e in timeline:
            e_time = parse_iso_time(e['timestamp'])
            if not e_time: continue
                
            if e['type'] == 'phase':
                if "KILLING" in e['value']:
                    in_killing_phase = True
                    last_event_time = e_time
                else:
                    in_killing_phase = False
                    last_event_time = None
                    
            elif e['type'] == 'kill':
                if in_killing_phase and last_event_time is not None:
                    ttk = (e_time - last_event_time).total_seconds()
                    
                    # Filter out massive anomalies
                    if 2 < ttk < 150:
                        ttk_data.append(ttk)
                        
                if in_killing_phase:
                    last_event_time = e_time

    if len(ttk_data) < 10:
        return print("Not enough TTK data to build a smooth KDE curve.")

    # 2. Setup the Zones (Thresholds, Labels, and Colors)
    zones =[
        {"label": "Vulture / Bot", "max": 15, "color": "#00FFFF"},   # Cyan
        {"label": "God RNG",       "max": 30, "color": "#00FF00"},   # Bright Green
        {"label": "Standard",      "max": 45, "color": "#008800"},   # Deep Green
        {"label": "Noodling",      "max": 65, "color": "#FFD700"},   # Gold
        {"label": "Fresh Trip",    "max": 90, "color": "#FF4444"},   # Bright Red
        {"label": "???",    "max": float('inf'), "color": "#880000"} # Deep Red
    ]

    # Calculate raw percentages directly from the data points
    total_kills = len(ttk_data)
    zone_counts =[0] * len(zones)
    
    for val in ttk_data:
        for i, z in enumerate(zones):
            if val <= z['max']:
                zone_counts[i] += 1
                break

    # 3. Calculate the KDE (Smooth Bell Curve)
    kde = gaussian_kde(ttk_data)
    x_max = np.percentile(ttk_data, 99) * 1.15 # Add 15% padding to the right
    x_vals = np.linspace(0, x_max, 1000)
    y_vals = kde(x_vals)
    max_y = max(y_vals)

    # 4. Setup Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"

    fig, ax = plt.subplots(figsize=(16, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # Plot the overarching white line of the bell curve
    ax.plot(x_vals, y_vals, color="#FFFFFF", linewidth=2.5, zorder=5)

    # 5. Fill the Regions and Draw Annotations
    prev_max = 0
    for i, z in enumerate(zones):
        z_max = z['max'] if z['max'] != float('inf') else x_max
        
        # Mask for the fill
        mask = (x_vals > prev_max) & (x_vals <= z_max)
        if not any(mask): 
            prev_max = z['max']
            continue
            
        # Fill the zone
        ax.fill_between(x_vals, y_vals, where=mask, color=z['color'], alpha=0.6, zorder=3)
        
        # Draw the dividing line
        if prev_max > 0:
            ax.axvline(prev_max, color="#FFFFFF", linestyle="--", linewidth=1.5, alpha=0.4, zorder=4)
            
        # Text positioning: Center X, float Y slightly above the curve
        x_center = (prev_max + min(z_max, x_max)) / 2
        y_peak_in_zone = max(y_vals[mask])
        y_pos = y_peak_in_zone + (max_y * 0.08) # Hover 8% above the peak of this section
        
        # Percentage formatting
        pct = (zone_counts[i] / total_kills) * 100
        
        # Assemble text
        label_txt = f"{z['label']}\n{pct:.1f}%"
        
        txt_obj = ax.text(x_center, y_pos, label_txt, color=z['color'], 
                          fontsize=12, fontweight='bold', ha='center', va='bottom', zorder=6)
        txt_obj.set_path_effects([path_effects.withStroke(linewidth=3, foreground='black')])

        prev_max = z['max']

    # 6. Formatting
    ax.set_xlabel("Seconds per Kill", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    ax.set_yticks([])
    ax.set_ylabel("Probability Density", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)

    ax.tick_params(axis='x', colors=TEXT_COLOR, labelsize=12)
    ax.set_xlim(0, x_max)
    ax.set_ylim(0, max_y * 1.25) # Give 25% headroom so the floating text fits

    for spine in ['top', 'right', 'left']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')

    # Add subtle X-axis grid lines
    ax.set_xticks([i for i in range(0, int(x_max) + 15, 15)])
    ax.grid(axis='x', linestyle='--', alpha=0.2, color='white', zorder=-1)

    # Overall Median annotation
    median_ttk = np.median(ttk_data)
    med_txt = ax.text(x_max * 0.95, max_y * 1.1, f"Median TTK:\n{median_ttk:.1f} Sec", 
                      color=TEXT_COLOR, fontsize=16, fontweight='bold', ha='right')
    med_txt.set_path_effects([path_effects.withStroke(linewidth=3, foreground='#333333')])

    # Titles
    plt.suptitle("TIME-TO-KILL (TTK) PROBABILITY DISTRIBUTION", color=TEXT_COLOR, fontsize=24, fontweight='bold', y=0.96)
    plt.title(f"Sample Size: {total_kills:,} Kills | Highlighted areas represent true proportion of kills", 
              color="#AAAAAA", fontsize=14, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"ttk_distribution_kde_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    print(f"Chart saved successfully: {output_path}")

if __name__ == "__main__":
    main()