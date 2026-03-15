import os
import shutil
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
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
    print("--- Generating The Consistency Paradox Chart ---")
    
    if not os.path.exists(DATA_DIR):
        return print(f"Error: {DATA_DIR} not found.")

    plot_data =[]

    # 1. Parse JSONs for exact kill deltas and theoretical accuracy
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            
        theo = data.get("theoretical_stats", {})
        acc = theo.get("accuracy", 0)
        
        # We need the accuracy stat to map this session
        if acc <= 0: continue
            
        timeline = data.get('event_timeline', [])
        
        ttk_data =[]
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
                    
                    # Filter out massive anomalies to protect the standard deviation math
                    if 10 < ttk < 150:
                        ttk_data.append(ttk)
                        
                if in_killing_phase:
                    last_event_time = e_time

        # Only use sessions with enough kills to form a real standard deviation
        if len(ttk_data) >= 5:
            std_dev = np.std(ttk_data)
            mean_ttk = np.mean(ttk_data)
            
            plot_data.append({
                "session_id": data.get("session_id"),
                "accuracy": acc,
                "std_dev": std_dev,
                "mean_ttk": mean_ttk,
                "kill_count": len(ttk_data)
            })

    if not plot_data:
        return print("No valid sessions with accuracy and TTK data found.")

    df = pd.DataFrame(plot_data)

    # 2. Setup Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"
    C_DOTS = "#00FF00"      # Neon Green for sessions
    C_TREND = "#FF4444"     # Red for the trendline

    fig, ax = plt.subplots(figsize=(14, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # 3. Draw Scatter Plot with Trendline
    sns.regplot(
        data=df, 
        x="accuracy", 
        y="std_dev", 
        ax=ax,
        color=C_DOTS,
        scatter_kws={"s": df['kill_count'] * 2, "alpha": 0.7, "edgecolors": "#FFFFFF", "linewidths": 1.0, "zorder": 4},
        line_kws={"color": C_TREND, "linewidth": 4, "zorder": 5}
    )

    # 4. Calculate and Annotate the Slope
    slope, intercept = np.polyfit(df['accuracy'], df['std_dev'], 1)
    
    # If slope is negative, accuracy REDUCES variance (improves consistency)
    if slope < -0.1:
        verdict_text = "VERDICT: Accuracy Tightens The Bell Curve."
    elif slope > 0.1:
        verdict_text = "VERDICT: Higher Accuracy is more volatile?!"
    else:
        verdict_text = "VERDICT: Consistency is unaffected by Accuracy."
        
    sign = "+" if slope > 0 else ""
    math_text = f"{verdict_text}\n{sign}{slope:.2f} seconds of variance per +1% Accuracy"
    
    txt_slope = ax.text(df['accuracy'].max(), df['std_dev'].max() * 0.95, 
                        math_text, color=C_TREND, fontsize=15, fontweight='bold', ha='right',
                        bbox=dict(facecolor="#220000", edgecolor=C_TREND, boxstyle='round,pad=0.5', alpha=0.8))

    # 5. Formatting the Axes
    ax.set_xlabel("Theoretical Accuracy %", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    ax.set_ylabel("TTK Volatility (Standard Deviation in Seconds)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    ax.tick_params(axis='both', colors=TEXT_COLOR, labelsize=12)
    
    # Format X-Axis as percentage
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.1f}%"))
    # Format Y-Axis as seconds
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x:.1f}s"))

    # Add some padding so the dots don't ride the walls
    x_margin = (df['accuracy'].max() - df['accuracy'].min()) * 0.1
    if x_margin == 0: x_margin = 1.0
    ax.set_xlim(df['accuracy'].min() - x_margin, df['accuracy'].max() + x_margin)

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    
    ax.grid(axis='both', linestyle='--', alpha=0.15, color='white', zorder=1)

    # 6. Titles
    plt.suptitle("THE CONSISTENCY PARADOX", color=TEXT_COLOR, fontsize=26, fontweight='bold', y=0.96)
    plt.title("Does higher accuracy actually stop the dry streaks? (Dot size = Session Kills)", 
              color="#AAAAAA", fontsize=15, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    # Save with precise timestamp
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"consistency_paradox_chart_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_accuracy_consistency")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_accuracy_consistency.png")
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