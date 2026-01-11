# visualizer.py
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import os
import glob
import pytz
from datetime import datetime
import config

# ==========================================
# SETUP
# ==========================================

# Setup Fonts
try:
    if os.path.exists(config.FONT_PATH_PRIMARY):
        title_font = fm.FontProperties(fname=config.FONT_PATH_PRIMARY, size=18)
        label_font = fm.FontProperties(fname=config.FONT_PATH_PRIMARY, size=12)
        body_font = fm.FontProperties(fname=config.FONT_PATH_SECONDARY, size=10)
    else:
        raise FileNotFoundError
except:
    print(f"Warning: Custom fonts not found at {config.FONT_PATH_PRIMARY}. Using defaults.")
    title_font = fm.FontProperties(family='sans-serif', weight='bold', size=18)
    label_font = fm.FontProperties(family='sans-serif', weight='bold', size=12)
    body_font = fm.FontProperties(family='sans-serif', size=10)

# Setup Timezone
local_tz = pytz.timezone(config.TIMEZONE)

def get_latest_file(pattern):
    """Finds the most recent CSV matching the pattern."""
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getctime)

def add_footer(ax):
    """Adds the 'Data as-of' footer."""
    timestamp = datetime.now(local_tz).strftime("%Y/%m/%d %H:%M")
    plt.figtext(0.99, 0.01, f"Data as-of: {timestamp} {config.TIMEZONE}", 
                horizontalalignment='right', 
                fontproperties=body_font, 
                weight='bold',
                color='#555555')

# ==========================================
# CHART 1: 100% STACKED BAR (VARIETY)
# ==========================================

def draw_variety_chart():
    csv_file = get_latest_file("reports/detailed_xp_*.csv")
    if not csv_file:
        print("No Detailed XP CSV found. Run analyzer.py (Option 4) first.")
        return

    print(f"Drawing Variety Chart from {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # 1. Filter out users with 0 gains
    skills = [c for c in df.columns if c not in ['Username', 'Category']]
    df['Total_Gained'] = df[skills].sum(axis=1)
    df = df[df['Total_Gained'] > 0].copy()

    # 2. Normalize to 100%
    # We create a new dataframe for percentages
    df_pct = df.copy()
    df_pct[skills] = df_pct[skills].div(df_pct['Total_Gained'], axis=0) * 100

    # 3. Sort the Data
    # We sort by Category first, then Username
    df_pct = df_pct.sort_values(by=['Category', 'Username'])
    
    # 4. Set the Index to Username
    # This is the CRITICAL FIX. By setting the index, pandas aligns the math automatically.
    df_pct.set_index('Username', inplace=True)

    # Plotting
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Initialize bottoms using the DataFrame's index to ensure alignment
    bottoms = pd.Series(0.0, index=df_pct.index)
    
    # Iterate through skills and stack bars
    for skill in skills:
        values = df_pct[skill]
        color = config.SKILL_COLORS.get(skill, "#000000")
        
        # Only plot if there is data for this skill across the board
        if values.sum() > 0:
            ax.bar(
                df_pct.index,  # Use the index (Usernames) as X-axis
                values, 
                bottom=bottoms, 
                label=skill.capitalize(), 
                color=color, 
                edgecolor='black', 
                linewidth=1.2,
                width=0.6
            )
            # Add the current values to the bottom tracker
            bottoms = bottoms.add(values, fill_value=0)

    # Formatting
    ax.set_title("Skill Training Variety Distribution (Last 7 Days)", fontproperties=title_font, pad=20)
    ax.set_ylabel("Percentage of Total XP Gained (%)", fontproperties=label_font)
    ax.set_xlabel("Player Name", fontproperties=label_font)
    
    # Rotate x-labels
    plt.xticks(rotation=45, ha='right', fontproperties=body_font)
    plt.yticks(fontproperties=body_font)
    
    # Legend
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], bbox_to_anchor=(1.02, 1), loc='upper left', prop=body_font)

    plt.tight_layout()
    add_footer(ax)
    
    output_path = f"reports/chart_variety_{datetime.now().strftime('%Y%m%d_%H%M')}.png"
    plt.savefig(output_path, dpi=300)
    print(f"Saved: {output_path}")

# ==========================================
# CHART 2: GANTT CHART (ACTIVITY LOG)
# ==========================================

def draw_activity_gantt():
    csv_file = get_latest_file("reports/activity_log_*.csv")
    if not csv_file:
        print("No Activity Log CSV found. Run analyzer.py (Option 3) first.")
        return

    print(f"Drawing Gantt Chart from {csv_file}...")
    df = pd.read_csv(csv_file)

    # Convert Time Strings to Datetime Objects
    # The CSV format is YYYY-MM-DD HH:MM (which implies local time from analyzer output, 
    # but let's ensure we treat it consistently).
    df['Start'] = pd.to_datetime(df['Time_Window_Start'])
    df['End'] = pd.to_datetime(df['Time_Window_End'])
    
    # Calculate Duration for plotting
    df['Duration_Days'] = (df['End'] - df['Start']).dt.total_seconds() / (24 * 3600)

    # Sort by Username to group them on Y-Axis
    df = df.sort_values(by=['Category', 'Username'])
    
    # Assign colors based on Category (Bots = Red, Real = Blue)
    category_colors = {'suspected_bots': '#d61a1a', 'real_ones': '#6277be'}
    
    fig, ax = plt.subplots(figsize=(14, 8))

    # Get unique players for Y-axis mapping
    players = df['Username'].unique()
    y_pos = range(len(players))
    player_map = {name: i for i, name in enumerate(players)}

    # Plot bars
    for idx, row in df.iterrows():
        y = player_map[row['Username']]
        start_date = mdates.date2num(row['Start'])
        duration = row['Duration_Days']
        color = category_colors.get(row['Category'], 'gray')
        
        # Alpha (transparency) based on efficiency? 
        # High efficiency = darker, Low efficiency = lighter
        alpha = min(1.0, max(0.3, row['Implied_Efficiency'] / 100))

        ax.barh(
            y, 
            duration, 
            left=start_date, 
            height=0.6, 
            color=color, 
            edgecolor='black', 
            alpha=alpha
        )

    # Formatting X-Axis (Dates)
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%a %H:%M', tz=local_tz))
    ax.set_xlim(mdates.date2num(df['Start'].min()), mdates.date2num(df['End'].max()))
    
    # Formatting Y-Axis
    ax.set_yticks(y_pos)
    ax.set_yticklabels(players, fontproperties=body_font)

    # Labels
    ax.set_title("Player Activity Timeline (Inferred Windows)", fontproperties=title_font, pad=20)
    ax.set_xlabel(f"Time ({config.TIMEZONE})", fontproperties=label_font)
    ax.grid(True, axis='x', linestyle='--', alpha=0.5)

    # Custom Legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='#d61a1a', lw=4, label='Suspected Bots'),
        Line2D([0], [0], color='#6277be', lw=4, label='Real Players'),
        Line2D([0], [0], color='gray', lw=0, label='(Opacity = Efficiency)'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', prop=body_font)

    plt.tight_layout()
    add_footer(ax)

    output_path = f"reports/chart_gantt_{datetime.now().strftime('%Y%m%d_%H%M')}.png"
    plt.savefig(output_path, dpi=300)
    print(f"Saved: {output_path}")

# ==========================================
# CHART 3: CUMULATIVE XP LINE CHART
# ==========================================

def draw_cumulative_line_chart():
    csv_file = get_latest_file("reports/timeseries_*.csv")
    if not csv_file:
        print("No Time Series CSV found. Run analyzer.py (Option 5) first.")
        return

    print(f"Drawing Line Chart from {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Convert Timestamp
    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.tz_localize('UTC').dt.tz_convert(config.TIMEZONE)
    
    # Sort
    df = df.sort_values('Timestamp')

    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Get unique players and assign colors
    players = df['Username'].unique()
    # Use a colormap that supports many distinct colors (tab20)
    colors = plt.cm.tab20.colors 
    
    for i, player in enumerate(players):
        player_data = df[df['Username'] == player]
        
        # Determine line style based on category (optional visual distinction)
        category = player_data['Category'].iloc[0]
        linestyle = '--' if category == 'suspected_bots' else '-'
        linewidth = 2 if category == 'suspected_bots' else 1.5
        
        # Cycle through colors if we have more players than colors
        color = colors[i % len(colors)]
        
        ax.plot(
            player_data['Timestamp'], 
            player_data['Total_XP'], 
            label=player,
            color=color,
            marker='o',          # The circle marker
            markersize=5,        # Size of the dot
            linestyle=linestyle, 
            linewidth=linewidth,
            alpha=0.9
        )

    # Formatting Y-Axis (Millions/Thousands)
    def human_format(num, pos):
        magnitude = 0
        while abs(num) >= 1000:
            magnitude += 1
            num /= 1000.0
        return '%.1f%s' % (num, ['', 'K', 'M', 'B'][magnitude])

    from matplotlib.ticker import FuncFormatter
    ax.yaxis.set_major_formatter(FuncFormatter(human_format))

    # Formatting X-Axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%a %H:%M', tz=local_tz))
    plt.xticks(rotation=45, ha='right', fontproperties=body_font)
    
    # Labels
    ax.set_title("Cumulative XP Progression (Last 7 Days)", fontproperties=title_font, pad=20)
    ax.set_ylabel("Total Experience", fontproperties=label_font)
    ax.set_xlabel(f"Time ({config.TIMEZONE})", fontproperties=label_font)
    
    ax.grid(True, linestyle='--', alpha=0.3)
    
    # Legend
    ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', prop=body_font, title="Players")
    
    plt.tight_layout()
    add_footer(ax)
    
    output_path = f"reports/chart_line_{datetime.now().strftime('%Y%m%d_%H%M')}.png"
    plt.savefig(output_path, dpi=300)
    print(f"Saved: {output_path}")

def main():
    print("1. Generate Variety Chart (Stacked Bar)")
    print("2. Generate Activity Gantt Chart")
    print("3. Generate Cumulative XP Line Chart")
    print("4. Generate All")
    
    choice = input("Select: ")
    
    if choice == '1':
        draw_variety_chart()
    elif choice == '2':
        draw_activity_gantt()
    elif choice == '3':
        draw_cumulative_line_chart()
    elif choice == '4':
        draw_variety_chart()
        draw_activity_gantt()
        draw_cumulative_line_chart()

if __name__ == "__main__":
    main()