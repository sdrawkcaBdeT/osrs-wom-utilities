import os
import shutil
import json
import csv
import glob
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patheffects as path_effects
from datetime import datetime

# --- CONFIG ---
DATA_DIR = "../bbd_data"
OUTPUT_DIR = "../analytics_output"
PRICES_DIR = "../price_snapshots"
ITEMS_CSV = "../items.csv"

# The anchor date for the economy. 
# Script will start here and roll forward to fill in any missing prices.
ECONOMY_ANCHOR_TS = 1772377200

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# --- MASTER DROP TABLE ---
DROP_TABLE = {
    "Dragon bones":       {"rate": 1.0, "qty": 1, "cat": "Guaranteed"},
    "Black dragonhide":   {"rate": 1.0, "qty": 2, "cat": "Guaranteed"},
    
    # Uniques (1/512)
    "Dragon platelegs":   {"rate": 1/512, "qty": 1, "cat": "Unique"},
    "Dragon plateskirt":  {"rate": 1/512, "qty": 1, "cat": "Unique"},
    "Dragon spear":       {"rate": 1/512, "qty": 1, "cat": "Unique"}, 
    "Uncut dragonstone":  {"rate": 1/512, "qty": 1, "cat": "Unique"},
    
    # Weapons/Armor
    "Rune spear":         {"rate": 1/12.8, "qty": 1, "cat": "Gear"},
    "Rune platelegs":     {"rate": 1/18.29, "qty": 1, "cat": "Gear"},
    "Rune full helm":     {"rate": 1/21.33, "qty": 2, "cat": "Gear"},
    "Rune dart":          {"rate": 1/25.6, "qty": 20, "cat": "Gear"},
    "Rune longsword":     {"rate": 1/25.6, "qty": 1, "cat": "Gear"},
    "Black d'hide body":  {"rate": 1/64, "qty": 1, "cat": "Gear"},
    "Rune knife":         {"rate": 1/64, "qty": 25, "cat": "Gear"},
    "Rune thrownaxe":     {"rate": 1/64, "qty": 30, "cat": "Gear"},
    "Black d'hide vambraces": {"rate": 1/128, "qty": 1, "cat": "Gear"},
    "Rune platebody":     {"rate": 1/128, "qty": 1, "cat": "Gear"},
    "Dragon med helm":    {"rate": 1/128, "qty": 1, "cat": "Gear"},
    "Dragon longsword":   {"rate": 1/128, "qty": 1, "cat": "Gear"},
    "Dragon dagger":      {"rate": 1/128, "qty": 1, "cat": "Gear"},

    # Runes/Ammo
    "Rune javelin":       {"rate": 1/16, "qty": 50, "cat": "Ammo"},
    "Blood rune":         {"rate": 1/16, "qty": 50, "cat": "Ammo"},
    "Soul rune":          {"rate": 1/16, "qty": 50, "cat": "Ammo"},
    "Death rune":         {"rate": 1/18.29, "qty": 75, "cat": "Ammo"},
    "Law rune":           {"rate": 1/18.29, "qty": 75, "cat": "Ammo"},
    "Rune arrow":         {"rate": 1/18.29, "qty": 75, "cat": "Ammo"},

    # Materials
    "Lava scale":         {"rate": 1/32, "qty": 5, "cat": "Mats"},
    "Dragon dart tip":    {"rate": 1/42.67, "qty": 40, "cat": "Mats"},
    "Runite ore":         {"rate": 1/64, "qty": 3, "cat": "Mats"},
    "Dragon arrowtips":   {"rate": 1/64, "qty": 40, "cat": "Mats"},
    "Dragon javelin tips":{"rate": 1/64, "qty": 40, "cat": "Mats"},

    # Coins
    "Coins":              {"rate": 1/10.66, "qty": 400, "cat": "Coins"},

    # Other
    "Anglerfish":         {"rate": 1/16, "qty": 2, "cat": "Other"},

    # RDT / Rare
    "Loop half of key":    {"rate": 1/378, "qty": 1, "cat": "RDT"},
    "Tooth half of key":   {"rate": 1/378, "qty": 1, "cat": "RDT"},
    "Shield left half":    {"rate": 1/15738, "qty": 1, "cat": "RDT"},
    "Uncut sapphire":      {"rate": 1/154, "qty": 1, "cat": "RDT"},
    "Uncut emerald":       {"rate": 1/309, "qty": 1, "cat": "RDT"},
    "Uncut ruby":          {"rate": 1/618, "qty": 1, "cat": "RDT"},
    "Uncut diamond":       {"rate": 1/2473, "qty": 1, "cat": "RDT"},
    "Nature talisman":     {"rate": 1/1638, "qty": 1, "cat": "RDT"},
    "Rune battleaxe":      {"rate": 1/2731, "qty": 1, "cat": "RDT"},
    "Rune 2h sword":       {"rate": 1/2731, "qty": 1, "cat": "RDT"},
    "Rune sq shield":      {"rate": 1/4096, "qty": 1, "cat": "RDT"},
    "Steel arrow":         {"rate": 1/4096, "qty": 150, "cat": "RDT"},
    "Adamant javelin":     {"rate": 1/4096, "qty": 20, "cat": "RDT"},
    "Dragonstone":         {"rate": 1/4096, "qty": 1, "cat": "RDT"},
    
    # Tertiary
    "Ensouled dragon head":{"rate": 1/20, "qty": 1, "cat": "Tertiary"},
    "Clue scroll (hard)":  {"rate": 1/128, "qty": 1, "cat": "Tertiary"},
    "Clue scroll (elite)": {"rate": 1/250, "qty": 1, "cat": "Tertiary"},
    "Draconic visage":     {"rate": 1/10000, "qty": 1, "cat": "Tertiary"},
    "Ancient shard":       {"rate": 1/123, "qty": 1, "cat": "Catacombs"},
    "Dark totem base":     {"rate": 1/185, "qty": 1, "cat": "Catacombs"},
    "Dark totem middle":   {"rate": 1/185, "qty": 1, "cat": "Catacombs"},
    "Dark totem top":      {"rate": 1/185, "qty": 1, "cat": "Catacombs"}
}

def build_static_prices():
    """Reads items.csv, then rolls forward through snapshot files to find missing GE prices."""
    name_to_id = {}
    fallback_alch = {}
    
    # 1. Load Dictionary
    if os.path.exists(ITEMS_CSV):
        with open(ITEMS_CSV, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                i_id = int(row['id'])
                name = row['name'].strip().lower()
                # Ignore noted versions to ensure we grab the base item ID
                if name not in name_to_id or "note" not in name:
                    name_to_id[name] = i_id
                fallback_alch[name] = int(row['highalch']) if row.get('highalch') else 0
                
    # 2. Get target files at or after Anchor Date
    prices_by_id = {}
    files = glob.glob(os.path.join(PRICES_DIR, "prices_*.csv"))
    valid_files =[]
    
    for f in files:
        try:
            ts = int(os.path.basename(f).replace("prices_", "").replace(".csv", ""))
            if ts >= ECONOMY_ANCHOR_TS:
                valid_files.append((ts, f))
        except: pass
        
    valid_files.sort(key=lambda x: x[0]) # Oldest (Anchor) to Newest
    
    # 3. Roll Forward to extract prices
    for ts, f in valid_files:
        with open(f, 'r', encoding='utf-8') as file:
            for row in csv.DictReader(file):
                item_id = int(row['item_id'])
                if item_id not in prices_by_id:
                    # Prefer low price, fallback to high price
                    p_low = int(row.get('avgLowPrice') or 0)
                    p_high = int(row.get('avgHighPrice') or 0)
                    price = p_low if p_low > 0 else p_high
                    if price > 0:
                        prices_by_id[item_id] = price

    # 4. Map back to item names in our DROP_TABLE
    final_prices = {'coins': 1}
    for item in DROP_TABLE.keys():
        name_lower = item.lower()
        if name_lower == 'coins': continue
        
        i_id = name_to_id.get(name_lower)
        if i_id and i_id in prices_by_id:
            final_prices[name_lower] = prices_by_id[i_id]
        else:
            # Fallback for untradeables (Ancient shard, Totem pieces) or missing items
            final_prices[name_lower] = fallback_alch.get(name_lower, 0)
            
    return final_prices

def main():
    print("--- Generating True RNG Variance Chart ---")
    static_prices = build_static_prices()
    
    total_kills = 0
    actual_loot = {}

    # 1. Aggregate All Data
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            total_kills += data.get("total_kills", 0)
            
            for item, qty in data.get("loot_summary", {}).items():
                actual_loot[item] = actual_loot.get(item, 0) + qty

    if total_kills == 0:
        return print("No kills found in dataset. Aborting.")

    # 2. Calculate GP Variance Per Item
    variance_data =[]
    total_account_luck = 0
    
    for item, info in DROP_TABLE.items():
        price = static_prices.get(item.lower(), 0)
        # Skip if price is 0 (Untradeables with no Alch value like Dark totem pieces)
        if price == 0: continue
            
        expected_qty = total_kills * info['rate'] * info['qty']
        expected_gp = expected_qty * price
        
        actual_qty = actual_loot.get(item, 0)
        actual_gp = actual_qty * price
        
        gp_delta = actual_gp - expected_gp
        total_account_luck += gp_delta
        
        # Only chart it if the variance is meaningful (e.g., more than 1,000 GP diff)
        if abs(gp_delta) > 1000:
            variance_data.append({
                "item": item,
                "gp_delta": gp_delta
            })

    # Sort by how "Spooned" (Positive) to how "Dry" (Negative) you are
    df = pd.DataFrame(variance_data).sort_values(by="gp_delta", ascending=True)

    if df.empty:
        return print("No meaningful variance to chart yet.")

    # 3. Render the Cinematic Chart
    # Colors matching our BBD lab aesthetic
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"
    SPOONED_COLOR = "#00FF00"
    DRY_COLOR = "#FF4444"

    fig, ax = plt.subplots(figsize=(14, 10), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # Create horizontal bars. Color them based on value.
    bars = ax.barh(df['item'], df['gp_delta'], 
                   color=[SPOONED_COLOR if x > 0 else DRY_COLOR for x in df['gp_delta']], 
                   edgecolor="#222222", height=0.7)

    # Center line at 0
    ax.axvline(0, color=TEXT_COLOR, linewidth=1.5, zorder=0)

    # --- NEW: Darker text colors specifically for the white-stroked annotations ---
    DARK_SPOONED_TEXT = "#008800"  # A deeper, richer green
    DARK_DRY_TEXT = "#CC0000"      # A deep, bold crimson
    
    # Calculate a slight offset based on chart width
    chart_span = df['gp_delta'].max() - df['gp_delta'].min()
    offset = chart_span * 0.015  

    for i, bar in enumerate(bars):
        # Annotate bottom 5 (most dry) and top 5 (most spooned)
        if i < 5 or i >= len(bars) - 5:
            val = bar.get_width() 
            
            # Format the text nicely
            if abs(val) >= 1000000: txt = f"{val/1000000:+.1f}M"
            elif abs(val) >= 1000: txt = f"{val/1000:+.0f}K"
            else: txt = f"{val:+.0f}"
            
            # Use the DARKER text colors here
            if val > 0:
                x_pos = val + offset
                align = 'left'
                txt_color = DARK_SPOONED_TEXT
            else:
                x_pos = val - offset
                align = 'right'
                txt_color = DARK_DRY_TEXT
                
            # Draw the text
            text_obj = ax.text(x_pos, bar.get_y() + bar.get_height()/2, txt, 
                               color=txt_color, ha=align, va='center', fontweight='bold', fontsize=11)
            
            # Apply the white stroke effect (Now it will pop beautifully!)
            text_obj.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground='white')])

    # Formatting axes
    ax.set_xlabel("GP Variance (Actual - Expected)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    # Format X-axis as Millions/Thousands (e.g., +1.5M, -500K)
    def currency_formatter(x, pos):
        if abs(x) >= 1000000: return f"{x/1000000:+.1f}M"
        elif abs(x) >= 1000: return f"{x/1000:+.0f}K"
        else: return f"{x:+.0f}"
        
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(currency_formatter))
    ax.tick_params(axis='x', colors=TEXT_COLOR, labelsize=12)
    ax.tick_params(axis='y', colors=TEXT_COLOR, labelsize=11)
    
    # Remove borders (spines) for a clean, floating look
    for spine in['top', 'right', 'left']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')

    # Add a title and the "Total Luck" subtitle
    plt.suptitle("TRUE RNG VARIANCE (ITEM-LEVEL)", color=TEXT_COLOR, fontsize=24, fontweight='bold', y=0.95)
    luck_str = f"Total Account Luck: {'+' if total_account_luck > 0 else ''}{total_account_luck:,.0f} GP"
    luck_color = SPOONED_COLOR if total_account_luck > 0 else DRY_COLOR
    plt.title(f"{luck_str} | Sample Size: {total_kills:,} Kills", color=luck_color, fontsize=16, pad=8)

    # Add a subtle grid behind the bars
    ax.grid(axis='x', linestyle='--', alpha=0.2, color='white', zorder=-1)

    # Save it perfectly for a 1080p video timeline
    plt.tight_layout()
    plt.subplots_adjust(top=0.88)

    # Auto-appending the YYYYMMDDHHMM timestamp!
    today = datetime.now()
    timestamp_str = today.strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"rng_variance_chart_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_rng_waterfall")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_rng_waterfall.png")
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