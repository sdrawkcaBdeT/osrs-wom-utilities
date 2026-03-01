# visualizer.py
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import math
import numpy as np
import os
import glob
import pytz
from datetime import datetime
import config

# ==========================================
# SETUP & CONFIGURATION
# ==========================================

# Define Sub-Directories
LATEST_DIR = os.path.join("reports", "latest")
ARCHIVE_DIR = os.path.join("reports", "archive")

for d in ["reports", LATEST_DIR, ARCHIVE_DIR]:
    if not os.path.exists(d): os.makedirs(d)

# Setup Timezone & Date Filter
local_tz = pytz.timezone(config.TIMEZONE)

# Parse Project Start Date
try:
    PROJECT_START = pd.to_datetime(config.PROJECT_START_DATE).tz_localize(None)
except:
    print("Warning: PROJECT_START_DATE not found in config. Using 2024-01-01.")
    PROJECT_START = pd.to_datetime("2024-01-01")

# Setup Fonts
try:
    if os.path.exists(config.FONT_PATH_PRIMARY):
        title_font = fm.FontProperties(fname=config.FONT_PATH_PRIMARY, size=18)
        label_font = fm.FontProperties(fname=config.FONT_PATH_PRIMARY, size=12)
        body_font = fm.FontProperties(fname=config.FONT_PATH_SECONDARY, size=10)
        anno_font = fm.FontProperties(fname=config.FONT_PATH_SECONDARY, size=14) 
    else:
        raise FileNotFoundError
except:
    print(f"Warning: Custom fonts not found. Using system defaults.")
    title_font = fm.FontProperties(family='sans-serif', weight='bold', size=18)
    label_font = fm.FontProperties(family='sans-serif', weight='bold', size=12)
    body_font = fm.FontProperties(family='sans-serif', size=10)
    anno_font = fm.FontProperties(family='sans-serif', weight='bold', size=12)

# ==========================================
# COLOR PALETTE
# ==========================================
# 6-Step Diverging + Black for Zero
HEATMAP_COLORS = [
    "#b2182b", # 0. Highest
    "#ef8a62", # 1.
    "#fddbc7", # 2.
    "#e0e0e0", # 3.
    "#999999", # 4.
    "#4d4d4d", # 5. Lowest
    "#000000"  # 6. Zero
]

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_latest_file(pattern):
    files = glob.glob(pattern)
    if not files: return None
    return max(files, key=os.path.getctime)

def add_footer(obj):
    timestamp = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M")
    fig = obj.figure if hasattr(obj, 'figure') else obj
    fig.text(0.99, 0.01, f"Data as-of: {timestamp} {config.TIMEZONE}", 
                horizontalalignment='right', fontproperties=body_font, weight='bold', color='#555555')

def save_chart(fig, filename_base):
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    archive_path = os.path.join(ARCHIVE_DIR, f"{filename_base}_{ts}.png")
    fig.savefig(archive_path, dpi=300, bbox_inches='tight')
    
    latest_path = os.path.join(LATEST_DIR, f"{filename_base}.png")
    fig.savefig(latest_path, dpi=300, bbox_inches='tight')
    print(f"Saved: {latest_path}")
    plt.close(fig)

def human_format(num, pos=None):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '%.1f%s' % (num, ['', 'K', 'M', 'B'][magnitude])

# ==========================================
# CHART 1 & 2: VARIETY (Stacked Bars)
# ==========================================

def draw_variety_charts():
    csv_file = get_latest_file("reports/detailed_xp_*.csv")
    if not csv_file: return

    print(f"Generating Variety Charts...")
    df = pd.read_csv(csv_file)
    
    skills = [c for c in df.columns if c not in ['Username', 'Category']]
    df['Total_Gained'] = df[skills].sum(axis=1)
    df = df[df['Total_Gained'] > 0].copy()
    
    df = df.sort_values(by=['Category', 'Username'])
    df.set_index('Username', inplace=True)

    # --- A: PERCENTAGE (Relative) ---
    df_pct = df.copy()
    df_pct[skills] = df_pct[skills].div(df_pct['Total_Gained'], axis=0) * 100
    
    fig, ax = plt.subplots(figsize=(12, 8))
    bottoms = pd.Series(0.0, index=df_pct.index)
    
    for skill in skills:
        values = df_pct[skill]
        color = config.SKILL_COLORS.get(skill, "#000000")
        if values.sum() > 0:
            ax.bar(df_pct.index, values, bottom=bottoms, label=skill.capitalize(), 
                   color=color, edgecolor='black', linewidth=1.2, width=0.6)
            bottoms = bottoms.add(values, fill_value=0)

    ax.set_title("Skill Training Variety (Distribution %)", fontproperties=title_font, pad=20)
    ax.set_ylabel("% of Total XP", fontproperties=label_font)
    plt.xticks(rotation=45, ha='right', fontproperties=body_font)
    
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], bbox_to_anchor=(1.02, 1), loc='upper left', prop=body_font)
    
    add_footer(ax)
    save_chart(fig, "chart_variety_percent")

    # --- B: ABSOLUTE (Total XP) ---
    fig2, ax2 = plt.subplots(figsize=(12, 8))
    bottoms_abs = pd.Series(0.0, index=df.index)

    for skill in skills:
        values = df[skill]
        color = config.SKILL_COLORS.get(skill, "#000000")
        if values.sum() > 0:
            ax2.bar(df.index, values, bottom=bottoms_abs, label=skill.capitalize(), 
                   color=color, edgecolor='black', linewidth=1.2, width=0.6)
            bottoms_abs = bottoms_abs.add(values, fill_value=0)

    ax2.set_title("Total XP Gained by Skill (Absolute)", fontproperties=title_font, pad=20)
    ax2.set_ylabel("Total XP Gained", fontproperties=label_font)
    
    from matplotlib.ticker import FuncFormatter
    ax2.yaxis.set_major_formatter(FuncFormatter(human_format))
    
    plt.xticks(rotation=45, ha='right', fontproperties=body_font)
    ax2.legend(handles[::-1], labels[::-1], bbox_to_anchor=(1.02, 1), loc='upper left', prop=body_font)
    
    add_footer(ax2)
    save_chart(fig2, "chart_variety_absolute")

# ==========================================
# CHART 3: HEATMAP GANTT (Rate-Based)
# ==========================================

def get_category_color(category, xp_rate):
    """
    Returns color based on XP/Hr rate and Category.
    Handles split logic for Bots (BBD Rates) vs Real (Skilling Rates).
    """
    colors = HEATMAP_COLORS 
    
    # Check for ZERO first
    if xp_rate <= 0:
        return colors[6] # Pure Black

    if category == "suspected_bots":
        # BBD Ranged XP Thresholds
        if xp_rate >= 99225: return colors[0] # 75 KPH
        if xp_rate >= 92610: return colors[1] # 70 KPH
        if xp_rate >= 85995: return colors[2] # 65 KPH
        if xp_rate >= 79380: return colors[3] # 60 KPH
        if xp_rate >= 72765: return colors[4] # 55 KPH
        return colors[5]                      # 50 KPH

    else:
        # Real Player Thresholds (Total XP)
        if xp_rate >= 900000: return colors[0] # Theoretical Max
        if xp_rate >= 300000: return colors[1] # Buyable Spike
        if xp_rate >= 140000: return colors[2] # Efficient
        if xp_rate >= 70000:  return colors[3] # Standard
        if xp_rate >= 25000:  return colors[4] # AFK
        return colors[5]                       # Bankstanding

def draw_heatmap_gantt():
    csv_file = get_latest_file("reports/timeseries_*.csv")
    if not csv_file: return

    print(f"Generating Heatmap Gantt...")
    df = pd.read_csv(csv_file)
    
    # 1. Parse & Filter
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], utc=True)
    proj_start_utc = PROJECT_START.tz_localize('UTC') if PROJECT_START.tz is None else PROJECT_START
    df = df[df['Timestamp'] >= proj_start_utc]
    df['Timestamp'] = df['Timestamp'].dt.tz_convert(config.TIMEZONE)
    
    if df.empty:
        print("No data after Project Start Date.")
        return

    # 2. Sort
    df = df.sort_values(by=['Category', 'Username', 'Timestamp'])
    
    # 3. Process Intervals
    plot_data = [] 
    
    users = df['Username'].unique()
    y_map = {u: i for i, u in enumerate(users)}
    
    for user in users:
        u_df = df[df['Username'] == user].copy()
        
        u_df['Time_Diff'] = u_df['Timestamp'].diff().dt.total_seconds() / 3600 # Hours
        u_df['XP_Diff'] = u_df['Total_XP'].diff()
        
        u_df = u_df.dropna()
        
        category = u_df['Category'].iloc[0]
        y_idx = y_map[user]

        for _, row in u_df.iterrows():
            duration = row['Time_Diff']
            xp_gained = row['XP_Diff']
            
            ts_pydt = row['Timestamp'].to_pydatetime()
            start_time = mdates.date2num(ts_pydt) - (duration / 24) 
            
            rate = 0
            if duration > 0:
                rate = xp_gained / duration
            
            color = get_category_color(category, rate)
            
            if duration < 48: 
                plot_data.append({
                    "y": y_idx,
                    "xranges": [(start_time, duration / 24)], 
                    "color": color
                })

    # 4. Plotting
    fig, ax = plt.subplots(figsize=(14, 8))
    
    for item in plot_data:
        # Added black stroke as requested
        ax.broken_barh(item['xranges'], (item['y'] - 0.4, 0.8), 
                       facecolors=item['color'], edgecolor='black', linewidth=0.5)

    ax.set_yticks(range(len(users)))
    ax.set_yticklabels(users, fontproperties=body_font)
    
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M', tz=local_tz))
    plt.xticks(rotation=45, ha='right', fontproperties=body_font)
    
    ax.set_title("XP Rate Heatmap (Intensity over Time)", fontproperties=title_font, pad=20)
    ax.set_xlabel(f"Time ({config.TIMEZONE})", fontproperties=label_font)
    ax.grid(True, axis='x', linestyle='--', alpha=0.3)

    # 5. Dual Legends (Full 6 Categories + Zero)
    
    # Legend 1: Bots (BBD Ranged XP)
    bot_labels = [
        ("> 75 KPH (99k+)", HEATMAP_COLORS[0]),
        ("70-75 KPH (92k+)", HEATMAP_COLORS[1]),
        ("65-70 KPH (86k+)", HEATMAP_COLORS[2]),
        ("60-65 KPH (79k+)", HEATMAP_COLORS[3]),
        ("55-60 KPH (72k+)", HEATMAP_COLORS[4]),
        ("< 55 KPH", HEATMAP_COLORS[5]),
        ("0 XP", HEATMAP_COLORS[6])
    ]
    bot_patches = [mpatches.Patch(color=c, label=l) for l, c in bot_labels]
    
    legend1 = ax.legend(handles=bot_patches, loc='upper left', 
                        bbox_to_anchor=(1.02, 1), prop=body_font, title="Bot Intensity (BBD)")
    ax.add_artist(legend1)

    # Legend 2: Real Players (Total XP)
    real_labels = [
        ("Theoretical Max (900k+)", HEATMAP_COLORS[0]),
        ("Buyable Spike (300k+)", HEATMAP_COLORS[1]),
        ("Efficient (140k+)", HEATMAP_COLORS[2]),
        ("Standard (70k+)", HEATMAP_COLORS[3]),
        ("AFK/Gathering (25k+)", HEATMAP_COLORS[4]),
        ("Bankstanding (<25k)", HEATMAP_COLORS[5]),
        ("0 XP", HEATMAP_COLORS[6])
    ]
    real_patches = [mpatches.Patch(color=c, label=l) for l, c in real_labels]
    
    ax.legend(handles=real_patches, loc='upper left', 
              bbox_to_anchor=(1.02, 0.65), prop=body_font, title="Real Intensity (Total)")

    plt.tight_layout(rect=[0, 0, 0.85, 1]) 
    add_footer(ax)
    save_chart(fig, "chart_gantt_heatmap")

# ==========================================
# CHART 4: ANNOTATED LINE CHARTS
# ==========================================

def draw_annotated_facet(df, category_name, filename_base):
    players = df['Username'].unique()
    if len(players) == 0: return

    cols = 2
    rows = math.ceil(len(players) / cols)
    
    fig, axes = plt.subplots(rows, cols, figsize=(14, 5 * rows), squeeze=False)
    fig.suptitle(f"Cumulative XP Progression: {category_name}", fontproperties=title_font, fontsize=24, y=0.98)

    axes_flat = axes.flatten()
    colors = plt.cm.tab20.colors

    for i, ax in enumerate(axes_flat):
        if i < len(players):
            player = players[i]
            player_data = df[df['Username'] == player]
            color = colors[i % len(colors)]

            # Plot Line
            ax.plot(player_data['Timestamp'], player_data['Total_XP'], color=color, 
                    marker='o', markersize=3, linewidth=2, label=player)

            # --- ANNOTATION LOGIC ---
            if len(player_data) >= 2:
                # 1. Total XP Gained
                start_xp = player_data['Total_XP'].iloc[0]
                end_xp = player_data['Total_XP'].iloc[-1]
                total_gained = end_xp - start_xp
                
                # 2. Real Hours (Wall Clock)
                start_time = player_data['Timestamp'].iloc[0]
                end_time = player_data['Timestamp'].iloc[-1]
                real_hours = (end_time - start_time).total_seconds() / 3600
                
                # 3. Rate
                rate = 0
                if real_hours > 0:
                    rate = total_gained / real_hours
                
                # Format Strings
                rate_str = f"{int(rate):,} EXP / REAL HOUR"
                total_str = f"{int(total_gained/1000):,}K TOTAL EXP"
                
                # Add Text to Bottom Right
                ax.text(0.95, 0.05, f"{rate_str}\n{total_str}", 
                        transform=ax.transAxes, 
                        horizontalalignment='right',
                        verticalalignment='bottom',
                        fontproperties=anno_font,
                        color='#333333',
                        bbox=dict(facecolor='white', alpha=0.9, edgecolor='#cccccc', boxstyle='round,pad=0.5'))

            # Standard Formatting
            ax.set_title(player, fontproperties=label_font, fontsize=14, color=color)
            
            from matplotlib.ticker import FuncFormatter
            ax.yaxis.set_major_formatter(FuncFormatter(human_format))
            
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%a %H:%M', tz=local_tz))
            plt.setp(ax.get_xticklabels(), rotation=30, ha='right', fontsize=9)
            ax.grid(True, linestyle='--', alpha=0.3)
        else:
            ax.axis('off')

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    add_footer(fig)
    save_chart(fig, f"chart_line_{filename_base}")

def draw_annotated_line_charts():
    csv_file = get_latest_file("reports/timeseries_*.csv")
    if not csv_file: return

    print(f"Generating Annotated Line Charts...")
    df = pd.read_csv(csv_file)
    
    # Parse & Filter
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], utc=True)
    
    proj_start_utc = PROJECT_START.tz_localize('UTC') if PROJECT_START.tz is None else PROJECT_START
    df = df[df['Timestamp'] >= proj_start_utc]
    
    # Convert to Local
    df['Timestamp'] = df['Timestamp'].dt.tz_convert(config.TIMEZONE)

    if df.empty:
        print("No data for line charts after Project Start Date.")
        return

    df = df.sort_values('Timestamp')

    draw_annotated_facet(df[df['Category'] == 'real_ones'], "Real Players", "real_ones")
    draw_annotated_facet(df[df['Category'] == 'suspected_bots'], "Suspected Bots", "bots")

# ==========================================
# MAIN EXECUTION
# ==========================================

def main():
    print("--- Starting Visualization Suite ---")
    print(f"Global Filter: Data after {config.PROJECT_START_DATE}")
    
    draw_variety_charts()
    draw_heatmap_gantt()
    draw_annotated_line_charts()
    
    print("--- Visualization Complete ---")
    print(f"Latest charts available in: {LATEST_DIR}")

if __name__ == "__main__":
    main()