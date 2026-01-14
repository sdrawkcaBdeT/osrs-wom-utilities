import json
import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import numpy as np
import config

# --- CONFIGURATION ---
DATA_DIR = "bbd_data"
OUTPUT_DIR = os.path.join("reports", "bbd_analysis")

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Setup Fonts
try:
    if os.path.exists(config.FONT_PATH_PRIMARY):
        title_font = fm.FontProperties(fname=config.FONT_PATH_PRIMARY, size=18)
        label_font = fm.FontProperties(fname=config.FONT_PATH_PRIMARY, size=12)
    else:
        raise FileNotFoundError
except:
    title_font = fm.FontProperties(family='sans-serif', weight='bold', size=18)
    label_font = fm.FontProperties(family='sans-serif', weight='bold', size=12)

def load_sessions():
    files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    sessions = []

    for f in files:
        try:
            with open(f, 'r') as file:
                data = json.load(file)
                if data.get('total_kills', 0) < 5: continue

                # Parse Timestamps
                start_time = pd.to_datetime(data['start_time'])
                end_time = pd.to_datetime(data['end_time'])
                
                # Parse Events
                raw_events = data.get('event_timeline', []) or data.get('events', [])
                parsed_events = []
                kill_timestamps = []

                for e in raw_events:
                    ts = pd.to_datetime(e['timestamp'])
                    delta_min = (ts - start_time).total_seconds() / 60
                    
                    parsed_events.append({
                        'type': e['type'],
                        'val': e.get('value', ''),
                        'min': delta_min,
                        'ts': ts
                    })
                    
                    if e['type'] == 'kill':
                        kill_timestamps.append(delta_min)

                sessions.append({
                    "id": data.get('session_id'),
                    "name": data.get('config', {}).get('experiment_name', 'Unnamed'),
                    "weapon": data.get('config', {}).get('weapon', 'Unknown'),
                    "kills": sorted(kill_timestamps),
                    "events": parsed_events,
                    "total": data.get('total_kills'),
                    "duration": (end_time - start_time).total_seconds() / 60
                })
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    return sessions

# --- CHART 1: VELOCITY (Existing) ---
def calculate_velocity(kills_timestamps):
    df = pd.DataFrame({'time': kills_timestamps})
    df['gap'] = df['time'].diff()
    df['instant_kph'] = 60 / df['gap']
    df['rolling_kph'] = df['instant_kph'].rolling(window=5).mean()
    return df

def draw_velocity_comparison(sessions):
    if not sessions: return
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Sort by weapon for grouping
    sessions.sort(key=lambda x: x['weapon'])

    for s in sessions:
        df = calculate_velocity(s['kills'])
        label = f"{s['weapon']} - {s['name']}"
        ax.plot(df['time'], df['rolling_kph'], label=label, linewidth=2, alpha=0.8)

    ax.set_title("Kill Velocity Analysis (Rolling 5-Kill Average)", fontproperties=title_font, pad=20)
    ax.set_xlabel("Time Elapsed (Minutes)", fontproperties=label_font)
    ax.set_ylabel("Kills Per Hour (Pace)", fontproperties=label_font)
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.legend(prop=label_font, loc='upper right')
    
    path = os.path.join(OUTPUT_DIR, f"velocity_chart.png")
    plt.savefig(path, dpi=300, bbox_inches='tight')
    print(f"Saved: {path}")
    plt.close()

# --- CHART 2: PHASE GANTT (New) ---
def draw_phase_gantt(sessions):
    """
    Visualizes Time Spent 'Killing' vs 'Away' for each session.
    """
    if not sessions: return
    
    fig, ax = plt.subplots(figsize=(14, len(sessions) * 1.5 + 2))
    
    # Y-Axis positions
    y_ticks = []
    y_labels = []

    for i, s in enumerate(sessions):
        y = i * 10
        y_ticks.append(y)
        y_labels.append(f"{s['weapon']}\n{s['name']}")
        
        # Process Phases
        # We look for "phase" events. 
        # If we find "KILLING", we start a red bar. 
        # If we find "AWAY" (or session end), we close the bar.
        
        current_start = 0
        current_state = "IDLE" # Assumes we start Away/Idle
        
        # Add a synthetic "End" event to close the last bar
        events = s['events'] + [{'type': 'end', 'min': s['duration']}]
        
        ranges_killing = []
        ranges_away = []

        for e in events:
            # Check for phase change or end
            if e['type'] == 'phase' or e['type'] == 'end':
                # Close previous segment
                duration = e['min'] - current_start
                if duration > 0:
                    if "KILLING" in current_state:
                        ranges_killing.append((current_start, duration))
                    else:
                        ranges_away.append((current_start, duration))
                
                # Start new segment
                if e['type'] == 'phase':
                    val = e['val'].upper()
                    current_state = "KILLING" if "KILLING" in val else "AWAY"
                    current_start = e['min']

        # Draw Broken Bars
        # Killing = Red, Away = Gray
        if ranges_away:
            ax.broken_barh(ranges_away, (y - 3, 6), facecolors='#555555', edgecolor='none', alpha=0.6)
        if ranges_killing:
            ax.broken_barh(ranges_killing, (y - 3, 6), facecolors='#d32f2f', edgecolor='black')

    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels, fontproperties=label_font)
    ax.set_xlabel("Time Elapsed (Minutes)", fontproperties=label_font)
    ax.set_title("Session Phase Analysis: Uptime vs. Banking", fontproperties=title_font, pad=20)
    ax.grid(True, axis='x', linestyle='--', alpha=0.3)
    
    # Custom Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#d32f2f', edgecolor='black', label='Killing (In Zone)'),
        Patch(facecolor='#555555', alpha=0.6, label='Away / Banking'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', prop=label_font)

    path = os.path.join(OUTPUT_DIR, f"phase_gantt.png")
    plt.savefig(path, dpi=300, bbox_inches='tight')
    print(f"Saved: {path}")
    plt.close()

# --- CHART 3: KILL DURATION HISTOGRAM (New) ---
def draw_kill_time_histogram(sessions):
    """
    Analyzes the raw time between kills to determine DPS efficiency.
    Excludes gaps > 3 minutes (assumed banking).
    """
    if not sessions: return
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    bins = np.arange(0, 180, 5) # 0s to 180s in 5s buckets
    
    for s in sessions:
        # Calculate gaps between kills (in seconds)
        kills_min = pd.Series(s['kills'])
        gaps_sec = kills_min.diff() * 60
        
        # Filter: Remove first kill (NaN) and Banking gaps (> 3 mins / 180s)
        valid_gaps = gaps_sec[(gaps_sec > 0) & (gaps_sec < 180)]
        
        # Plot Density Curve (KDE) or Histogram
        # Using Histogram 'step' style for comparison
        label = f"{s['weapon']} (Avg: {valid_gaps.mean():.1f}s)"
        ax.hist(valid_gaps, bins=bins, histtype='step', linewidth=2, label=label, density=True)

    ax.set_title("Kill Duration Distribution (Raw DPS Check)", fontproperties=title_font, pad=20)
    ax.set_xlabel("Seconds per Kill", fontproperties=label_font)
    ax.set_ylabel("Frequency (Density)", fontproperties=label_font)
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.legend(prop=label_font)
    
    path = os.path.join(OUTPUT_DIR, f"kill_histogram.png")
    plt.savefig(path, dpi=300, bbox_inches='tight')
    print(f"Saved: {path}")
    plt.close()

if __name__ == "__main__":
    print("--- BBD Micro-Analyzer ---")
    data = load_sessions()
    print(f"Found {len(data)} valid sessions.")
    
    draw_velocity_comparison(data)
    draw_phase_gantt(data)
    draw_kill_time_histogram(data)
    
    print("Micro-Analysis Complete.")