import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patheffects as path_effects
from datetime import datetime

# --- CONFIG ---
HISTORY_CSV = "wealth_history.csv"
OUTPUT_DIR = "analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Generating Moving Target Line Graph ---")
    
    if not os.path.exists(HISTORY_CSV):
        return print(f"Error: {HISTORY_CSV} not found. Let pipeline.py run first!")

    # 1. Load Data
    df = pd.read_csv(HISTORY_CSV)
    if df.empty:
        return print("No data in wealth_history.csv yet.")

    # Convert timestamps
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Sort by time to ensure lines draw left-to-right properly
    df = df.sort_values('timestamp')

    # 2. Setup the Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"
    C_WEALTH = "#00FF00"  # Neon Green
    C_TBOW = "#FF4444"    # Piercing Red
    
    fig, ax = plt.subplots(figsize=(14, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    dates = df['timestamp']
    wealth = df['total']
    tbow = df['tbow_cost']

    # 3. Draw Lines
    ax.plot(dates, tbow, color=C_TBOW, linewidth=3.5, label="Twisted Bow Cost", zorder=4)
    ax.plot(dates, wealth, color=C_WEALTH, linewidth=3.5, label="Total Wealth", zorder=4)

    # 4. Shade "The Gap"
    # Fills the space between your wealth and the T-bow in a translucent red
    ax.fill_between(dates, wealth, tbow, where=(tbow >= wealth), 
                    color=C_TBOW, alpha=0.15, interpolate=True, zorder=3)
    
    # Just in case you finish the grind and wealth > tbow! (Fills in Green)
    ax.fill_between(dates, wealth, tbow, where=(wealth > tbow), 
                    color=C_WEALTH, alpha=0.15, interpolate=True, zorder=3)

    # 5. Add Current Status Annotations at the very end of the lines
    last_date = dates.iloc[-1]
    last_wealth = wealth.iloc[-1]
    last_tbow = tbow.iloc[-1]
    current_gap = last_tbow - last_wealth
    
    def format_m(val):
        if val >= 1000000000: return f"{val/1000000000:,.2f}B"
        return f"{val/1000000:,.1f}M"

    # Annotate T-Bow Price
    txt_tbow = ax.text(last_date, last_tbow, f"  {format_m(last_tbow)}", color=C_TBOW, 
                       fontsize=14, fontweight='bold', va='center')
    txt_tbow.set_path_effects([path_effects.withStroke(linewidth=3, foreground=BG_COLOR)])
    
    # Annotate Your Wealth
    txt_wealth = ax.text(last_date, last_wealth, f"  {format_m(last_wealth)}", color=C_WEALTH, 
                         fontsize=14, fontweight='bold', va='center')
    txt_wealth.set_path_effects([path_effects.withStroke(linewidth=3, foreground=BG_COLOR)])

    # 6. Formatting
    ax.set_ylabel("Grand Exchange Value", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    # Format Y-Axis to Billions/Millions (e.g. 1.65B, 800M)
    def currency_formatter(x, pos):
        if x >= 1000000000: return f"{x/1000000000:.2f}B"
        elif x >= 1000000: return f"{x/1000000:.0f}M"
        return f"{x:,.0f}"
    ax.yaxis.set_major_formatter(plt.FuncFormatter(currency_formatter))
    ax.tick_params(axis='y', colors=TEXT_COLOR, labelsize=12)
    
    # Format X-Axis Dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M'))
    ax.tick_params(axis='x', colors=TEXT_COLOR, labelsize=11)
    
    # Expand X-limit slightly (~8% padding) so the text annotations on the right don't get cut off
    xlims = ax.get_xlim()
    ax.set_xlim(xlims[0], xlims[0] + (xlims[1] - xlims[0]) * 1.08)

    # Clean Borders and Grid
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    
    ax.grid(axis='y', linestyle='--', alpha=0.2, color='white', zorder=1)
    ax.grid(axis='x', linestyle='--', alpha=0.1, color='white', zorder=1)

    # Legend
    legend = ax.legend(facecolor='#111111', edgecolor='#333333', fontsize=12, loc='upper left')
    for text in legend.get_texts():
        text.set_color(TEXT_COLOR)

    # Titles
    plt.suptitle("THE MOVING TARGET: TOTAL WEALTH VS. T-BOW ECONOMY", color=TEXT_COLOR, fontsize=24, fontweight='bold', y=0.96)
    plt.title(f"Current Gap: {format_m(current_gap)} GP | Total Progress: {(last_wealth/last_tbow)*100:.1f}%", 
              color="#AAAAAA", fontsize=14, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"moving_target_chart_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    print(f"Chart saved successfully: {output_path}")

if __name__ == "__main__":
    main()