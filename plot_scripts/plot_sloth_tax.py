import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import os
import shutil
from datetime import datetime
import numpy as np

# --- STRICT STYLE GUIDE ---
BG_COLOR = "#0A0A0A"
TEXT_COLOR = "#FFFFFF"
HIGHLIGHT_CYAN = "#00FFFF"
SUCCESS_GREEN = "#00FF00"
COST_RED = "#FF4444"
GOLD = "#FFD700"
Q_COLORS = [SUCCESS_GREEN, HIGHLIGHT_CYAN, GOLD, "#FFA500", COST_RED] # 5 Discrete Bins

os.makedirs("../analytics_output", exist_ok=True)

def generate_sloth_tax_chart():
    print("Executing Sloth Tax Visual Analytics...")
    try:
        df = pd.read_csv("../normalized_sessions.csv")
        # Filter out extreme outliers (AFK emergencies)
        df = df[(df['miss_per_hr'] < 1000) & (df['astb'] < 300)].copy()
    except FileNotFoundError:
        print("Error: normalized_sessions.csv not found.")
        return

    # Discrete Quantile Binning for ASTB (Avg Seconds to Bank)
    df['astb_bin'], bins = pd.qcut(df['astb'], q=5, retbins=True, labels=False)

    fig, ax = plt.subplots(figsize=(12, 7), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # Spine/Grid configuration
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    ax.grid(color='white', linestyle='--', alpha=0.15)
    ax.tick_params(colors=TEXT_COLOR)

    # Plot discretely colored scatter
    for i in range(5):
        subset = df[df['astb_bin'] == i]
        ax.scatter(subset['miss_per_hr'], subset['t_ngp_hr'], 
                   color=Q_COLORS[i], s=80, alpha=0.8, edgecolors=BG_COLOR,
                   label=f"ASTB: {bins[i]:.0f}s - {bins[i+1]:.0f}s")

    # Add trendline to quantify the "Sloth Slope"
    z = np.polyfit(df['miss_per_hr'], df['t_ngp_hr'], 1)
    p = np.poly1d(z)
    ax.plot(df['miss_per_hr'], p(df['miss_per_hr']), color=COST_RED, linestyle='--', linewidth=2)

    # Path Effect Text Overlays
    outline = [pe.withStroke(linewidth=3, foreground=BG_COLOR)]
    
    slope_text = f"Cost of Sloth: {z[0]:.0f} GP/hr per Missed Attack"
    ax.text(0.05, 0.95, slope_text, transform=ax.transAxes, fontsize=16, 
            color=COST_RED, fontweight='bold', path_effects=outline, va='top')

    ax.set_xlabel("Missed Attacks per Hour (In-Combat Sloth)", color=TEXT_COLOR, fontsize=12, fontweight='bold')
    ax.set_ylabel("Theoretical Net GP/Hr (T-NGP/hr)", color=TEXT_COLOR, fontsize=12, fontweight='bold')
    ax.set_title("The Sloth Tax: Biological Inefficiency vs. Wealth Generation", color=TEXT_COLOR, fontsize=16, fontweight='bold', pad=20)

    # Legend Styling
    legend = ax.legend(facecolor=BG_COLOR, edgecolor='gray', title="Bank Speed Quantiles", title_fontsize=12, labelcolor=TEXT_COLOR)
    legend.get_title().set_color(TEXT_COLOR)

    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    out_path = f"analytics_output/plot_sloth_tax_{timestamp}.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_sloth_tax")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_sloth_tax.png")
        # Use the filename that was generated for the specific dir
        filename = os.path.basename(out_path)
        specific_path = os.path.join(specific_dir, filename)
        
        shutil.copy(out_path, recent_path)
        shutil.move(out_path, specific_path)
        print(f"-> Saved recent to: {recent_path}")
        print(f"-> Saved archived to: {specific_path}")
    except Exception as e:
        print(f"Error routing file: {e}")
    plt.close()
    print(f"Rendered: {out_path}")

if __name__ == "__main__":
    generate_sloth_tax_chart()