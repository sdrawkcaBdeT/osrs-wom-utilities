import json
import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import config  # Re-using your config for fonts/colors

# --- CONFIGURATION ---
DATA_DIR = "bbd_data"
OUTPUT_DIR = os.path.join("reports", "bbd_analysis")

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Setup Fonts (Re-using your existing setup)
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
    """Reads all JSON files and parses kill events."""
    files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    sessions = []

    for f in files:
        try:
            with open(f, 'r') as file:
                data = json.load(file)
                
                # We only care about sessions with kills
                if data.get('total_kills', 0) < 5:
                    continue

                # Extract Kill Timestamps
                kills = []
                start_time = pd.to_datetime(data['start_time'])
                
                # Check event timeline for kills
                events = data.get('event_timeline', []) or data.get('events', [])
                
                for e in events:
                    if e['type'] == 'kill':
                        # Calculate minutes from start
                        ts = pd.to_datetime(e['timestamp'])
                        delta_ min = (ts - start_time).total_seconds() / 60
                        kills.append(delta_min)
                
                if kills:
                    sessions.append({
                        "id": data.get('session_id'),
                        "weapon": data.get('config', {}).get('weapon', 'Unknown'),
                        "ammo": data.get('config', {}).get('ammo', 'Unknown'),
                        "kills": sorted(kills),
                        "total": data.get('total_kills')
                    })
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    return sessions

def calculate_velocity(kills_timestamps):
    """
    Calculates a rolling KPH (Kills Per Hour).
    """
    df = pd.DataFrame({'time': kills_timestamps})
    
    # Calculate gap between kills in minutes
    df['gap'] = df['time'].diff()
    
    # Instant KPH = 60 / gap_in_minutes
    # Example: 2 min gap = 30 KPH
    df['instant_kph'] = 60 / df['gap']
    
    # Rolling Average (Smooth out RNG/Banking)
    # Window of 5 kills provides a good balance of sensitivity vs smoothness
    df['rolling_kph'] = df['instant_kph'].rolling(window=5).mean()
    
    return df

def draw_velocity_comparison(sessions):
    """Draws the Kill Velocity Chart."""
    if not sessions:
        print("No valid sessions found.")
        return

    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Sort sessions by total kills (or date) to keep legend tidy
    sessions.sort(key=lambda x: x['total'], reverse=True)

    # Limit to top 5 sessions to avoid clutter? 
    # Or let user choose. For now, plot all found.
    
    for s in sessions:
        df = calculate_velocity(s['kills'])
        
        label = f"{s['weapon']} ({s['total']} kills)"
        
        # Plot
        ax.plot(df['time'], df['rolling_kph'], label=label, linewidth=2, alpha=0.8)

    # Formatting
    ax.set_title("Kill Velocity Analysis (Rolling 5-Kill Average)", fontproperties=title_font, pad=20)
    ax.set_xlabel("Time Elapsed (Minutes)", fontproperties=label_font)
    ax.set_ylabel("Kills Per Hour (Pace)", fontproperties=label_font)
    
    # Grid
    ax.grid(True, linestyle='--', alpha=0.3)
    
    # Legend
    ax.legend(prop=label_font, loc='upper right')

    # Footer
    plt.figtext(0.99, 0.01, "Smoothed over 5-kill window", 
                horizontalalignment='right', color='#555555')

    # Save
    ts = pd.Timestamp.now().strftime('%Y%m%d_%H%M')
    path = os.path.join(OUTPUT_DIR, f"velocity_chart_{ts}.png")
    plt.savefig(path, dpi=300, bbox_inches='tight')
    print(f"Chart saved: {path}")
    plt.close()

if __name__ == "__main__":
    print("--- BBD Micro-Analyzer ---")
    data = load_sessions()
    print(f"Found {len(data)} valid sessions.")
    draw_velocity_comparison(data)