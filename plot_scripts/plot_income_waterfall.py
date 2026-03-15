import os
import shutil
import json
import csv
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from datetime import datetime, timedelta

# --- CONFIG ---
ENRICHED_CSV = "../gpph_enriched.csv"
PRICES_DIR = "../price_snapshots"
ITEMS_CSV = "../items.csv"
DATA_DIR = "../bbd_data"
OUTPUT_DIR = "../analytics_output"
SESSION_DIR = os.path.join(OUTPUT_DIR, "session_waterfalls")
ECONOMY_ANCHOR_TS = 1772377200

for d in [OUTPUT_DIR, SESSION_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

def build_static_prices():
    """Builds the frozen economy dictionary."""
    name_to_id = {}
    fallback_alch = {}
    if os.path.exists(ITEMS_CSV):
        with open(ITEMS_CSV, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                i_id = int(row['id'])
                name = row['name'].strip().lower()
                if name not in name_to_id or "note" not in name:
                    name_to_id[name] = i_id
                fallback_alch[name] = int(row['highalch']) if row.get('highalch') else 0

    prices_by_id = {}
    files = glob.glob(os.path.join(PRICES_DIR, "prices_*.csv"))
    valid_files =[f for f in files if int(os.path.basename(f).replace("prices_", "").replace(".csv", "")) >= ECONOMY_ANCHOR_TS]
    valid_files.sort(key=lambda x: int(os.path.basename(x).replace("prices_", "").replace(".csv", "")))
    
    for f in valid_files:
        with open(f, 'r', encoding='utf-8') as file:
            for row in csv.DictReader(file):
                item_id = int(row['item_id'])
                if item_id not in prices_by_id:
                    p_low = int(row.get('avgLowPrice') or 0)
                    p_high = int(row.get('avgHighPrice') or 0)
                    price = p_low if p_low > 0 else p_high
                    if price > 0: prices_by_id[item_id] = price

    def get_price(name):
        name_lower = str(name).lower().strip()
        if name_lower == 'coins': return 1
        i_id = name_to_id.get(name_lower)
        if i_id and i_id in prices_by_id: return prices_by_id[i_id]
        return fallback_alch.get(name_lower, 0)
        
    return get_price

def group_tail(data_list, keep_top, other_label):
    if len(data_list) <= keep_top + 1: return data_list
    top = data_list[:keep_top]
    tail_sum = sum(x['value'] for x in data_list[keep_top:])
    top.append({"name": other_label, "value": tail_sum})
    return top

def draw_waterfall(revenues, expenses, total_coins, title, subtitle, output_path, rev_limit=6, exp_limit=4):
    """Reusable drawing function for both the master chart and individual sessions."""
    
    rev_chart = group_tail(revenues, rev_limit, "Other Drops")
    exp_chart = group_tail(expenses, exp_limit, "Other Supplies")

    gross_revenue = sum(x['value'] for x in rev_chart)
    operating_profit = gross_revenue - sum(x['value'] for x in exp_chart)
    
    taxable_revenue = max(0, gross_revenue - total_coins)
    ge_tax = taxable_revenue * 0.02
    net_profit = operating_profit - ge_tax

    # Build sequence
    waterfall_data =[]
    for r in rev_chart: waterfall_data.append((r['name'], r['value'], 'rev'))
    waterfall_data.append(("GROSS REVENUE", gross_revenue, 'sub_gross'))
    for e in exp_chart: waterfall_data.append((e['name'], e['value'], 'exp'))
    waterfall_data.append(("OPERATING PROFIT", operating_profit, 'sub_op'))
    waterfall_data.append(("GE Tax (2%)", ge_tax, 'tax'))
    waterfall_data.append(("NET PROFIT", net_profit, 'net'))

    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"

    fig, ax = plt.subplots(figsize=(16, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    x_labels = [x[0] for x in waterfall_data]
    x_pos = np.arange(len(x_labels))
    current_y = 0
    
    # Calculate visual headroom for margin text
    max_y = gross_revenue * 1.15
    ax.set_ylim(0, max_y if max_y > 0 else 1000)
    
    for i, (name, val, type_) in enumerate(waterfall_data):
        # Determine bar positioning and colors
        if type_ == 'rev':
            bottom, height = current_y, val
            current_y += val
            fill_c, edge_c = "#004400", "#00FF00"
        elif type_ == 'sub_gross':
            bottom, height = 0, current_y
            fill_c, edge_c = "#004466", "#00FFFF"
        elif type_ in ['exp', 'tax']:
            current_y -= val
            bottom, height = current_y, val
            fill_c, edge_c = "#550000", "#FF4444"
        elif type_ == 'sub_op':
            bottom, height = 0, current_y
            fill_c, edge_c = "#554400", "#FFD700"
        elif type_ == 'net':
            bottom, height = 0, current_y
            fill_c, edge_c = "#006600", "#00FF00"
            
        # Draw bar
        ax.bar(x_pos[i], height, bottom=bottom, color=fill_c, edgecolor=edge_c, linewidth=2, width=0.7)
        
        # Draw connectors
        if i > 0:
            prev_y = bottom if type_ in ['exp', 'tax'] else bottom + height
            if type_ in['sub_gross', 'sub_op', 'net']: prev_y = height
            line_y = bottom + height if type_ == 'rev' else (current_y + val if type_ in ['exp', 'tax'] else current_y)
            ax.plot([x_pos[i-1]+0.35, x_pos[i]-0.35], [line_y, line_y], color='gray', linestyle='--', linewidth=1.5)

        # Value Text inside the bar
        sign = "+" if type_ == 'rev' else ("-" if type_ in ['exp', 'tax'] else "")
        if val >= 1000000: txt = f"{sign}{val/1000000:.1f}M"
        elif val >= 1000: txt = f"{sign}{val/1000:.0f}K"
        else: txt = f"{sign}{val:.0f}"

        txt_obj = ax.text(x_pos[i], bottom + (height/2), txt, ha='center', va='center', 
                          color=TEXT_COLOR, fontweight='bold', fontsize=10)
        txt_obj.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground='black')])

        # --- NEW: THE MARGIN ANNOTATIONS ---
        if type_ == 'sub_op':
            margin = (val / gross_revenue * 100) if gross_revenue > 0 else 0
            m_txt = ax.text(x_pos[i], val + (gross_revenue * 0.03), f"{margin:.1f}%\nMargin", 
                            ha='center', va='bottom', color="#FFD700", fontweight='bold', fontsize=12)
            m_txt.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground='black')])
            
        if type_ == 'net':
            margin = (val / gross_revenue * 100) if gross_revenue > 0 else 0
            m_txt = ax.text(x_pos[i], val + (gross_revenue * 0.03), f"{margin:.1f}%\nNet Margin", 
                            ha='center', va='bottom', color="#00FF00", fontweight='bold', fontsize=12)
            m_txt.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground='black')])

    # Formatting axes
    font_s = 11 if len(x_labels) <= 15 else 9
    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels, rotation=45, ha='right', color=TEXT_COLOR, fontsize=font_s, fontweight='bold')
    
    def currency_formatter(x, pos):
        if x >= 1000000: return f"{x/1000000:.1f}M"
        return f"{x/1000:.0f}K"
    ax.yaxis.set_major_formatter(plt.FuncFormatter(currency_formatter))
    ax.tick_params(axis='y', colors=TEXT_COLOR, labelsize=11)

    for spine in ['top', 'right', 'left']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.grid(axis='y', linestyle='--', alpha=0.2, color='white', zorder=-1)

    plt.suptitle(title, color=TEXT_COLOR, fontsize=24, fontweight='bold', y=1.02)
    plt.title(subtitle, color="gray", fontsize=14, pad=15)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_income_waterfall")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_income_waterfall.png")
        # Use the filename that was generated for the specific dir
        filename = os.path.basename(output_path)
        specific_path = os.path.join(specific_dir, filename)
        
        shutil.copy(output_path, recent_path)
        shutil.move(output_path, specific_path)
        print(f"-> Saved recent to: {recent_path}")
        print(f"-> Saved archived to: {specific_path}")
    except Exception as e:
        print(f"Error routing file: {e}")
    plt.close()

def main():
    print("--- Generating Income Statement Waterfalls ---")
    if not os.path.exists(ENRICHED_CSV):
        return print(f"Error: {ENRICHED_CSV} not found.")

    get_price = build_static_prices()
    
    # Pre-load GPPH CSV
    df = pd.read_csv(ENRICHED_CSV)
    df['local_start_time'] = pd.to_datetime(df['local_start_time'], format='%Y-%m-%d %I:%M:%S %p', errors='coerce')
    
    # ----------------------------------------------------
    # 1. GENERATE THE MASTER ACCOUNT WATERFALL
    # ----------------------------------------------------
    item_sums = df.groupby('item_name')['qty_delta'].sum().reset_index()
    revs, exps = [],[]
    t_coins = 0

    for _, row in item_sums.iterrows():
        name, qty = str(row['item_name']), row['qty_delta']
        val = qty * get_price(name)
        if val > 0:
            if name.lower() == 'coins':
                t_coins += val
                revs.append({"name": "Coins (Drops+Alchs)", "value": val})
            else: revs.append({"name": name.title(), "value": val})
        elif val < 0: exps.append({"name": name.title(), "value": abs(val)})

    revs = sorted(revs, key=lambda x: x['value'], reverse=True)
    exps = sorted(exps, key=lambda x: x['value'], reverse=True)

    today = pd.Timestamp.now()
    timestamp_str = today.strftime("%Y%m%d%H%M")
        
    draw_waterfall(
        revs, exps, t_coins,
        title="BBD LABORATORY: TOTAL INCOME STATEMENT",
        subtitle=f"Economy Anchored | Assuming 2% GE Tax on Liquidation",
        output_path = os.path.join(OUTPUT_DIR, f"income_waterfall_chart_{timestamp_str}.png"),
        rev_limit=6, exp_limit=4
    )
    print("Master chart generated.")

    # ----------------------------------------------------
    # 2. GENERATE INDIVIDUAL SESSION WATERFALLS
    # ----------------------------------------------------
    session_count = 0
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            
        s_id = data.get("session_id", filename.replace(".json", ""))
        start_t = pd.to_datetime(data.get("start_time"))
        end_t = pd.to_datetime(data.get("end_time", pd.Timestamp.now().isoformat()))
        
        # Filter GPPH data exactly to this session (2 min buffer)
        mask = (df['local_start_time'] >= start_t - timedelta(minutes=2)) & \
               (df['local_start_time'] <= end_t + timedelta(minutes=2))
        s_df = df.loc[mask]
        
        if s_df.empty: continue
        
        s_sums = s_df.groupby('item_name')['qty_delta'].sum().reset_index()
        s_revs, s_exps = [],[]
        s_coins = 0
        
        for _, row in s_sums.iterrows():
            name, qty = str(row['item_name']), row['qty_delta']
            val = qty * get_price(name)
            if val > 0:
                if name.lower() == 'coins':
                    s_coins += val
                    s_revs.append({"name": "Coins (Drops+Alchs)", "value": val})
                else: s_revs.append({"name": name.title(), "value": val})
            elif val < 0: s_exps.append({"name": name.title(), "value": abs(val)})
            
        if not s_revs and not s_exps: continue
        
        s_revs = sorted(s_revs, key=lambda x: x['value'], reverse=True)
        s_exps = sorted(s_exps, key=lambda x: x['value'], reverse=True)

        dur_hrs = (end_t - start_t).total_seconds() / 3600.0

        
        
        # Draw with limits set to 999 to EXPAND ALL ITEMS
        draw_waterfall(
            s_revs, s_exps, s_coins,
            title=f"INCOME STATEMENT: {s_id.upper()}",
            subtitle=f"Date: {start_t.strftime('%Y-%m-%d')} | Duration: {dur_hrs:.1f}h",
            output_path=os.path.join(SESSION_DIR, f"{s_id}_waterfall.png"),
            rev_limit=999, exp_limit=999
        )
        session_count += 1

    print(f"Generated {session_count} individual session waterfall charts in '{SESSION_DIR}/'.")

if __name__ == "__main__":
    main()