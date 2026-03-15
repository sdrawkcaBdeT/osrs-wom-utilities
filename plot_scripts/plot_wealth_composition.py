import os
import shutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patheffects as path_effects
from datetime import datetime

# --- CONFIG ---
HISTORY_CSV = "wealth_history.csv"
OUTPUT_DIR = "../analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Generating Wealth Composition Stacked Chart ---")
    
    if not os.path.exists(HISTORY_CSV):
        return print(f"Error: {HISTORY_CSV} not found. Let pipeline.py run first!")

    # 1. Load and prep data
    df = pd.read_csv(HISTORY_CSV)
    if df.empty:
        return print("No data in wealth_history.csv yet.")

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')

    # We want absolute values for the stacked layers to match Total Wealth exactly
    dates = df['timestamp']
    gear = df['gear']
    supplies = df['supplies']  # <-- ADDED SUPPLIES BACK!
    ge_cash = df['ge']
    drops = df['drops']

    # 2. Setup the Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"

    # Deep, rich colors for the stack
    C_GEAR = "#4B0082"      # Deep Purple
    C_SUPPLIES = "#FF4500"  # Bright Orange/Red
    C_CASH = "#B8860B"      # Dark Gold
    C_DROPS = "#006400"     # Forest Green

    fig, ax = plt.subplots(figsize=(16, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # 3. Draw the Stacked Area Plot (This now perfectly equals Total Wealth)
    ax.stackplot(dates, gear, supplies, ge_cash, drops, 
                 labels=['Gear', 'Supplies', 'GE / Cash', 'Unsold Drops'], 
                 colors=[C_GEAR, C_SUPPLIES, C_CASH, C_DROPS],
                 alpha=0.85, edgecolor="#111111", linewidth=1.5, zorder=3)

    # 4. Add Current Value Annotations on the right edge
    last_date = dates.iloc[-1]
    
    def format_m(val):
        if abs(val) >= 1000000000: return f"{val/1000000000:,.2f}B"
        return f"{val/1000000:,.1f}M"

    def annotate_layer(y_val, text, color):
        txt = ax.text(last_date + pd.Timedelta(hours=2), y_val, text, 
                      color=color, fontsize=12, fontweight='bold', va='center')
        txt.set_path_effects([path_effects.withStroke(linewidth=3, foreground=BG_COLOR)])

    # Calculate the exact middle Y-positions for the labels at the far right
    y_gear = gear.iloc[-1] / 2
    y_supplies = gear.iloc[-1] + (supplies.iloc[-1] / 2)
    y_cash = gear.iloc[-1] + supplies.iloc[-1] + (ge_cash.iloc[-1] / 2)
    y_drops = gear.iloc[-1] + supplies.iloc[-1] + ge_cash.iloc[-1] + (drops.iloc[-1] / 2)

    # Only annotate if the slice is actually visible (greater than 1M or so)
    if gear.iloc[-1] > 1000000: annotate_layer(y_gear, f"Gear\n{format_m(gear.iloc[-1])}", "#DDA0DD")
    if supplies.iloc[-1] > 1000000: annotate_layer(y_supplies, f"Supplies\n{format_m(supplies.iloc[-1])}", "#FFA07A")
    if ge_cash.iloc[-1] > 1000000: annotate_layer(y_cash, f"Cash\n{format_m(ge_cash.iloc[-1])}", "#FFD700")
    if drops.iloc[-1] > 1000000: annotate_layer(y_drops, f"Drops\n{format_m(drops.iloc[-1])}", "#00FF00")

    # 5. Formatting
    ax.set_ylabel("Grand Exchange Value", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    # Format Y-Axis
    def currency_formatter(x, pos):
        if x >= 1000000000: return f"{x/1000000000:.2f}B"
        elif x >= 1000000: return f"{x/1000000:.0f}M"
        return f"{x:,.0f}"
    ax.yaxis.set_major_formatter(plt.FuncFormatter(currency_formatter))
    ax.tick_params(axis='y', colors=TEXT_COLOR, labelsize=12)
    
    # Format X-Axis Dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=10))
    ax.tick_params(axis='x', colors=TEXT_COLOR, labelsize=11)
    
    # Expand X-limit slightly so text annotations don't cut off
    xlims = ax.get_xlim()
    ax.set_xlim(xlims[0], xlims[0] + (xlims[1] - xlims[0]) * 1.06)

    # Set Y-limits intelligently
    max_wealth = df['total'].max()
    ax.set_ylim(0, max_wealth * 1.15)

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    
    ax.grid(axis='y', linestyle='--', alpha=0.15, color='white', zorder=1)
    ax.grid(axis='x', linestyle='--', alpha=0.1, color='white', zorder=1)

    # Legend
    legend = ax.legend(facecolor='#111111', edgecolor='#333333', fontsize=12, loc='upper left')
    for text in legend.get_texts():
        text.set_color(TEXT_COLOR)

    # Titles
    plt.suptitle("WEALTH COMPOSITION & LIQUIDITY CYCLE", color=TEXT_COLOR, fontsize=26, fontweight='bold', y=0.96)
    plt.title(f"Current Total Wealth: {format_m(df['total'].iloc[-1])}", color="#AAAAAA", fontsize=15, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"wealth_composition_stack_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_wealth_composition")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_wealth_composition.png")
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