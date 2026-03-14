import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
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
    print("--- Generating The Fatigue Chart ---")
    
    if not os.path.exists(DATA_DIR):
        return print(f"Error: {DATA_DIR} not found.")

    trip_data =[]

    # 1. Parse all JSON timelines
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            
        t_start = parse_iso_time(data.get('start_time'))
        t_end = parse_iso_time(data.get('end_time'))
        if not t_start or not t_end: continue
        
        timeline = data.get('event_timeline',[])
        
        has_started_killing = False
        away_start = None
        
        for e in timeline:
            e_time = parse_iso_time(e['timestamp'])
            if not e_time: continue
                
            e_type = e['type']
            if e_type == 'phase':
                if "KILLING" in e['value']:
                    has_started_killing = True
                    # If we were away, the trip just ended!
                    if away_start is not None:
                        trip_duration = (e_time - away_start).total_seconds()
                        session_minute = (away_start - t_start).total_seconds() / 60.0
                        
                        # Filter out micro-disconnects (< 5 seconds) 
                        # and massive AFK logouts (> 10 minutes) to keep the trendline focused on "active" fatigue
                        if 5 <= trip_duration <= 600:
                            trip_data.append({
                                "session_minute": session_minute,
                                "trip_duration_sec": trip_duration
                            })
                        away_start = None
                
                elif "AWAY" in e['value']:
                    # Only count AWAY phases if we actually reached the dragons first
                    if has_started_killing:
                        away_start = e_time

    if not trip_data:
        return print("No valid bank trips found to plot.")

    df = pd.DataFrame(trip_data)

    # 2. Setup the Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"
    C_DOTS = "#00FFFF"      # Cyan for individual trips
    C_TREND = "#FF4444"     # Red for the brutal truth trendline
    
    fig, ax = plt.subplots(figsize=(14, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # 3. Draw Scatter Plot with Trendline using Seaborn
    sns.regplot(
        data=df, 
        x="session_minute", 
        y="trip_duration_sec", 
        ax=ax,
        color=C_DOTS,
        # CHANGED: "edgecolor" -> "edgecolors", "linewidth" -> "linewidths"
        scatter_kws={"s": 60, "alpha": 0.6, "edgecolors": "#FFFFFF", "linewidths": 0.5},
        line_kws={"color": C_TREND, "linewidth": 4, "zorder": 5}
    )

    # 4. Calculate the slope to annotate exactly how much fatigue costs you
    slope, intercept = np.polyfit(df['session_minute'], df['trip_duration_sec'], 1)
    
    # Text Annotation for the slope
    sign = "+" if slope > 0 else ""
    fatigue_text = f"Fatigue Rate: {sign}{slope*60:.1f} sec / hr"
    
    # Place it dynamically near the top left
    txt_slope = ax.text(df['session_minute'].max() * 0.05, df['trip_duration_sec'].max() * 0.9, 
                        fatigue_text, color=C_TREND, fontsize=16, fontweight='bold')
    txt_slope.set_path_effects([path_effects.withStroke(linewidth=3, foreground=BG_COLOR)])

    # 5. Formatting
    ax.set_xlabel("Minutes Elapsed in Session", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    ax.set_ylabel("Bank Trip Duration (Seconds)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    ax.tick_params(axis='x', colors=TEXT_COLOR, labelsize=12)
    ax.tick_params(axis='y', colors=TEXT_COLOR, labelsize=12)
    
    # Set limits to make it look clean
    ax.set_xlim(0, df['session_minute'].max() * 1.05)
    ax.set_ylim(0, df['trip_duration_sec'].max() * 1.1)

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    
    ax.grid(axis='both', linestyle='--', alpha=0.15, color='white', zorder=-1)

    # Titles
    plt.suptitle("THE FATIGUE CURVE: DISTRACTION OVER TIME", color=TEXT_COLOR, fontsize=24, fontweight='bold', y=0.96)
    plt.title(f"Bank Trip Duration vs. Session Length | Sample Size: {len(df)} Trips", 
              color="#AAAAAA", fontsize=14, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"fatigue_chart_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    print(f"Chart saved successfully: {output_path}")

if __name__ == "__main__":
    main()