import os
import json
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from datetime import datetime

# --- CONFIG ---
DATA_DIR = "bbd_data"
OUTPUT_DIR = "analytics_output"
TARGET_DURATION_MINS = 75.0  # The algorithm searches for sessions closest to this length
SESSIONS_PER_GROUP = 3       # How many lines to show per category

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def parse_iso_time(ts_str):
    try:
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except:
        return None

def main():
    print("--- Generating Curated Session Heartbeat ---")
    
    if not os.path.exists(DATA_DIR):
        return print(f"Error: {DATA_DIR} not found.")

    raw_sessions =[]

    # 1. Parse all JSON timelines
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            
        t_start = parse_iso_time(data.get('start_time'))
        t_end = parse_iso_time(data.get('end_time'))
        if not t_start or not t_end: continue
        
        dur_mins = (t_end - t_start).total_seconds() / 60.0
        if dur_mins < 10 or data.get('total_kills', 0) == 0:
            continue
            
        bones_method = data.get('config', {}).get('bones', 'Unknown')
        timeline = data.get('event_timeline', [])
        
        intervals = []
        kill_times =[]
        
        current_phase = "AWAY"
        phase_start = t_start
        
        for e in timeline:
            e_time = parse_iso_time(e['timestamp'])
            if not e_time: continue
                
            e_type = e['type']
            if e_type == 'phase':
                intervals.append((phase_start, e_time, current_phase))
                current_phase = "KILLING" if "KILLING" in e['value'] else "AWAY"
                phase_start = e_time
            elif e_type == 'kill':
                kill_times.append(e_time)
                
        intervals.append((phase_start, t_end, current_phase))
        
        min_intervals =[]
        for s, e, p in intervals:
            start_m = (s - t_start).total_seconds() / 60.0
            end_m = (e - t_start).total_seconds() / 60.0
            if end_m > start_m:
                min_intervals.append((start_m, end_m, p))
                
        min_kills =[(k - t_start).total_seconds() / 60.0 for k in kill_times]
        
        raw_sessions.append({
            "id": data.get("session_id"),
            "duration": dur_mins,
            "bones_method": bones_method,
            "intervals": min_intervals,
            "kills": min_kills,
            "date": t_start
        })

    if not raw_sessions:
        return print("No valid sessions to plot.")

    # 2. The Targeting Algorithm
    groups = {}
    for s in raw_sessions:
        grp = s['bones_method']
        if grp not in groups: groups[grp] = []
        groups[grp].append(s)
        
    curated_groups = {}
    for grp, session_list in groups.items():
        if len(session_list) < SESSIONS_PER_GROUP:
            continue
            
        session_list.sort(key=lambda x: abs(x['duration'] - TARGET_DURATION_MINS))
        top_n = session_list[:SESSIONS_PER_GROUP]
        top_n.sort(key=lambda x: x['duration'], reverse=False)
        curated_groups[grp] = top_n

    if not curated_groups:
        return print("Not enough sessions to build the A/B comparison.")

    # 3. Setup the Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"
    C_KILLING = "#006600"   # Deep Green Ribbon
    C_AWAY = "#880000"      # Brighter Red so the gaps POP
    C_KILL_TICK = "#FFFFFF" # Bright White
    
    fig, ax = plt.subplots(figsize=(16, 9), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    
    y_current = 0
    ribbon_height = 0.8  
    group_spacing = 2.5  
    
    max_x = 0
    sorted_group_keys = sorted(curated_groups.keys())

    # 4. Draw the Curated Ridgelines
    for grp_key in sorted_group_keys:
        session_list = curated_groups[grp_key]
        
        # Add Group Title
        txt = ax.text(0, y_current + (len(session_list)*1) + 0.2, f"METHOD: {grp_key.upper()}", 
                      color="#FFD700", fontsize=18, fontweight='bold')
        txt.set_path_effects([path_effects.withStroke(linewidth=3, foreground='black')])
        
        for s in session_list:
            if s['duration'] > max_x: max_x = s['duration']
            
            has_started_killing = False
            trip_count = 0
            
            # Draw Intervals (Phase Ribbons)
            for start_m, end_m, phase in s['intervals']:
                if phase == "KILLING":
                    has_started_killing = True
                    
                color = C_KILLING if phase == "KILLING" else C_AWAY
                ax.barh(y_current, end_m - start_m, left=start_m, height=ribbon_height, 
                        color=color, edgecolor="none", align='center')
                
                # --- NEW: TRIP ANNOTATIONS ---
                # Only count AWAY phases after we've actually reached the dragons, 
                # and ignore tiny <15 second glitches (0.25 mins)
                if phase == "AWAY" and has_started_killing and (end_m - start_m) > 0.25:
                    trip_count += 1
                    mid_x = (start_m + end_m) / 2
                    
                    trip_txt = ax.text(mid_x, y_current, str(trip_count), 
                                       color="#FFFFFF", fontsize=11, fontweight='bold', 
                                       ha='center', va='center')
                    trip_txt.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground='black')])
                        
            # Draw Kill Ticks
            for k_m in s['kills']:
                ax.vlines(x=k_m, ymin=y_current - (ribbon_height/2), 
                          ymax=y_current + (ribbon_height/2), 
                          color=C_KILL_TICK, linewidth=1.5, alpha=0.8)
                          
            y_current += 1.2 # Step up
            
        y_current += group_spacing # Extra gap between groups

    # 5. Formatting
    ax.set_xlabel("Minutes Elapsed in Session", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    ax.set_yticks([])
    ax.set_yticklabels([])
    ax.tick_params(axis='x', colors=TEXT_COLOR, labelsize=12)
    ax.set_xlim(0, max_x * 1.02)
    
    for spine in['top', 'right', 'left']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    
    ax.set_xticks([i for i in range(0, int(max_x) + 10, 10)])
    ax.grid(axis='x', linestyle='--', alpha=0.25, color='white', zorder=-1)

    # Titles
    plt.suptitle("SESSION HEARTBEAT: THE INVENTORY SQUEEZE", color=TEXT_COLOR, fontsize=26, fontweight='bold', y=0.96)
    plt.title(f"A/B Comparison of {SESSIONS_PER_GROUP} representative sessions (~{int(TARGET_DURATION_MINS)} mins) | Numbered Red Blocks = Bank Trips", 
              color="#AAAAAA", fontsize=14, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"session_heartbeat_curated_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    print(f"Chart saved successfully: {output_path}")

if __name__ == "__main__":
    main()