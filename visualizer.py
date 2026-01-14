# visualizer.py
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
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

# Ensure directories exist
for d in ["reports", LATEST_DIR, ARCHIVE_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# Setup Timezone
local_tz = pytz.timezone(config.TIMEZONE)

# Setup Fonts
try:
    if os.path.exists(config.FONT_PATH_PRIMARY):
        title_font = fm.FontProperties(fname=config.FONT_PATH_PRIMARY, size=18)
        label_font = fm.FontProperties(fname=config.FONT_PATH_PRIMARY, size=12)
        body_font = fm.FontProperties(fname=config.FONT_PATH_SECONDARY, size=10)
    else:
        raise FileNotFoundError
except:
    print(f"Warning: Custom fonts not found. Using system defaults.")
    title_font = fm.FontProperties(family='sans-serif', weight='bold', size=18)
    label_font = fm.FontProperties(family='sans-serif', weight='bold', size=12)
    body_font = fm.FontProperties(family='sans-serif', size=10)

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_latest_file(pattern):
    """Finds the most recent CSV matching the pattern."""
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getctime)

def add_footer(obj):
    """Adds the 'Data as-of' footer to a Figure or Axes."""
    timestamp = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M")
    
    # Get the figure object regardless of input
    fig = obj.figure if hasattr(obj, 'figure') else obj

    fig.text(0.99, 0.01, f"Data as-of: {timestamp} {config.TIMEZONE}", 
                horizontalalignment='right', 
                fontproperties=body_font, 
                weight='bold',
                color='#555555')

def save_chart(fig, filename_base):
    """
    Saves the chart to BOTH 'latest' (overwrite) and 'archive' (timestamped).
    """
    # 1. Save to Archive (History)
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    archive_path = os.path.join(ARCHIVE_DIR, f"{filename_base}_{ts}.png")
    fig.savefig(archive_path, dpi=300, bbox_inches='tight')
    
    # 2. Save to Latest (For easy linking in Video Editors/OBS)
    latest_path = os.path.join(LATEST_DIR, f"{filename_base}.png")
    fig.savefig(latest_path, dpi=300, bbox_inches='tight')
    
    print(f"Saved: {latest_path}")
    
    # Close figure to free memory
    plt.close(fig)

# ==========================================
# CHART 1: 100% STACKED BAR (VARIETY)
# ==========================================

def draw_variety_chart():
    csv_file = get_latest_file("reports/detailed_xp_*.csv")
    if not csv_file:
        print("Skipping Variety Chart: No CSV found.")
        return

    print(f"Generating Variety Chart...")
    df = pd.read_csv(csv_file)
    
    skills = [c for c in df.columns if c not in ['Username', 'Category']]
    df['Total_Gained'] = df[skills].sum(axis=1)
    df = df[df['Total_Gained'] > 0].copy()

    df_pct = df.copy()
    df_pct[skills] = df_pct[skills].div(df_pct['Total_Gained'], axis=0) * 100
    df_pct = df_pct.sort_values(by=['Category', 'Username'])
    df_pct.set_index('Username', inplace=True)

    fig, ax = plt.subplots(figsize=(12, 8))
    bottoms = pd.Series(0.0, index=df_pct.index)
    
    for skill in skills:
        values = df_pct[skill]
        color = config.SKILL_COLORS.get(skill, "#000000")
        
        if values.sum() > 0:
            ax.bar(df_pct.index, values, bottom=bottoms, label=skill.capitalize(), 
                   color=color, edgecolor='black', linewidth=1.2, width=0.6)
            bottoms = bottoms.add(values, fill_value=0)

    ax.set_title("Skill Training Variety Distribution (Last 7 Days)", fontproperties=title_font, pad=20)
    ax.set_ylabel("Percentage of Total XP Gained (%)", fontproperties=label_font)
    ax.set_xlabel("Player Name", fontproperties=label_font)
    
    plt.xticks(rotation=45, ha='right', fontproperties=body_font)
    plt.yticks(fontproperties=body_font)
    
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], bbox_to_anchor=(1.02, 1), loc='upper left', prop=body_font)

    add_footer(ax)
    save_chart(fig, "chart_variety")

# ==========================================
# CHART 2: GANTT CHART (ACTIVITY LOG)
# ==========================================

def draw_activity_gantt():
    csv_file = get_latest_file("reports/activity_log_*.csv")
    if not csv_file:
        print("Skipping Gantt Chart: No CSV found.")
        return

    print(f"Generating Activity Gantt Chart...")
    df = pd.read_csv(csv_file)

    df['Start'] = pd.to_datetime(df['Time_Window_Start'])
    df['End'] = pd.to_datetime(df['Time_Window_End'])
    df['Duration_Days'] = (df['End'] - df['Start']).dt.total_seconds() / (24 * 3600)
    df = df.sort_values(by=['Category', 'Username'])
    
    category_colors = {'suspected_bots': '#d61a1a', 'real_ones': '#6277be'}
    
    fig, ax = plt.subplots(figsize=(14, 8))

    players = df['Username'].unique()
    y_pos = range(len(players))
    player_map = {name: i for i, name in enumerate(players)}

    for idx, row in df.iterrows():
        y = player_map[row['Username']]
        start_date = mdates.date2num(row['Start'])
        duration = row['Duration_Days']
        color = category_colors.get(row['Category'], 'gray')
        alpha = min(1.0, max(0.3, row['Implied_Efficiency'] / 100))

        ax.barh(y, duration, left=start_date, height=0.6, color=color, edgecolor='black', alpha=alpha)

    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%a %H:%M', tz=local_tz))
    ax.set_xlim(mdates.date2num(df['Start'].min()), mdates.date2num(df['End'].max()))
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(players, fontproperties=body_font)

    ax.set_title("Player Activity Timeline (Inferred Windows)", fontproperties=title_font, pad=20)
    ax.set_xlabel(f"Time ({config.TIMEZONE})", fontproperties=label_font)
    ax.grid(True, axis='x', linestyle='--', alpha=0.5)

    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='#d61a1a', lw=4, label='Suspected Bots'),
        Line2D([0], [0], color='#6277be', lw=4, label='Real Players'),
        Line2D([0], [0], color='gray', lw=0, label='(Opacity = Efficiency)'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', prop=body_font)

    add_footer(ax)
    save_chart(fig, "chart_gantt")

# ==========================================
# CHART 3: FACETED CUMULATIVE XP CHARTS
# ==========================================

def human_format(num, pos):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '%.1f%s' % (num, ['', 'K', 'M', 'B'][magnitude])

def draw_group_facet(df, category_name, filename_base):
    players = df['Username'].unique()
    if len(players) == 0:
        return

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

            ax.plot(player_data['Timestamp'], player_data['Total_XP'], color=color, 
                    marker='o', markersize=4, linewidth=2, label=player)

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

def draw_faceted_cumulative_charts():
    csv_file = get_latest_file("reports/timeseries_*.csv")
    if not csv_file:
        print("Skipping Line Charts: No CSV found.")
        return

    print(f"Generating Line Charts...")
    df = pd.read_csv(csv_file)
    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize('UTC').dt.tz_convert(config.TIMEZONE)
    df = df.sort_values('Timestamp')

    draw_group_facet(df[df['Category'] == 'real_ones'], "Real Players", "real_ones")
    draw_group_facet(df[df['Category'] == 'suspected_bots'], "Suspected Bots", "bots")

# ==========================================
# MAIN EXECUTION
# ==========================================

def main():
    print("--- Starting Visualization Suite ---")
    
    # Always run all charts
    draw_variety_chart()
    draw_activity_gantt()
    draw_faceted_cumulative_charts()
    
    print("--- Visualization Complete ---")
    print(f"Latest charts available in: {LATEST_DIR}")

if __name__ == "__main__":
    main()