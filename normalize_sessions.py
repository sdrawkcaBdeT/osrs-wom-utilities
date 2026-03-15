import os
import json
import csv
import glob
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIG ---
DATA_DIR = "bbd_data"
PRICES_DIR = "price_snapshots"
ITEMS_CSV = "items.csv"
ENRICHED_CSV = "gpph_enriched.csv"
OUTPUT_CSV = "normalized_sessions.csv"

# The anchor date for the economy.
ECONOMY_ANCHOR_TS = 1772377200

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
    """Builds a comprehensive dictionary of all items (Drops + Supplies) at the Anchor Date."""
    name_to_id = {}
    fallback_alch = {}
    
    # 1. Map Names to IDs
    if os.path.exists(ITEMS_CSV):
        with open(ITEMS_CSV, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                i_id = int(row['id'])
                name = row['name'].strip().lower()
                if name not in name_to_id or "note" not in name:
                    name_to_id[name] = i_id
                fallback_alch[name] = int(row['highalch']) if row.get('highalch') else 0

    # 2. Gather Price Snapshots from Anchor Date Forward
    prices_by_id = {}
    files = glob.glob(os.path.join(PRICES_DIR, "prices_*.csv"))
    valid_files =[]
    
    for f in files:
        try:
            ts = int(os.path.basename(f).replace("prices_", "").replace(".csv", ""))
            if ts >= ECONOMY_ANCHOR_TS:
                valid_files.append((ts, f))
        except: pass
        
    valid_files.sort(key=lambda x: x[0])
    
    for ts, f in valid_files:
        with open(f, 'r', encoding='utf-8') as file:
            for row in csv.DictReader(file):
                item_id = int(row['item_id'])
                if item_id not in prices_by_id:
                    p_low = int(row.get('avgLowPrice') or 0)
                    p_high = int(row.get('avgHighPrice') or 0)
                    price = p_low if p_low > 0 else p_high
                    if price > 0:
                        prices_by_id[item_id] = price

    # 3. Create final Name -> Price mapping for EVERY item we might encounter
    final_prices = {'coins': 1}
    for name, i_id in name_to_id.items():
        if i_id in prices_by_id:
            final_prices[name] = prices_by_id[i_id]
        else:
            final_prices[name] = fallback_alch.get(name, 0)
            
    return final_prices

def unpack_singletons(obj):
    if isinstance(obj, list):
        if len(obj) == 1:
            return unpack_singletons(obj[0])
        return [unpack_singletons(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: unpack_singletons(v) for k, v in obj.items()}
    return obj

def main():
    print("--- Normalizing BBD Sessions Data ---")
    
    # 1. Initialize Economy
    static_prices = build_static_prices()
    
    base_kill_value = 0
    for item, info in DROP_TABLE.items():
        price = static_prices.get(item.lower(), 0)
        base_kill_value += (price * info['rate'] * info['qty'])
        
    print(f"Economy Anchored. Theoretical Base Kill Value: {base_kill_value:,.0f} GP")

    # 2. Load Supply Logs
    if not os.path.exists(ENRICHED_CSV):
        return print(f"Error: {ENRICHED_CSV} not found.")
        
    df_enriched = pd.read_csv(ENRICHED_CSV)
    df_enriched['local_start_time'] = pd.to_datetime(df_enriched['local_start_time'], format='%Y-%m-%d %I:%M:%S %p', errors='coerce')
    
    dataset =[]

    # 3. Process all JSON Sessions
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            data = unpack_singletons(data)
            
        start_time = pd.to_datetime(data.get('start_time'))
        end_time = pd.to_datetime(data.get('end_time', pd.Timestamp.now().isoformat()))
        kills = data.get('total_kills', 0)
        active_sec = data.get('active_seconds', 0)
        
        duration_hrs = (end_time - start_time).total_seconds() / 3600.0
        if duration_hrs <= 0 or kills == 0: continue
        
        # Calculate Bank/Away Time
        bank_sec = 0
        trips = 0
        away_ts = None
        for e in data.get('event_timeline', []):
            if e['type'] == 'phase':
                ts = pd.to_datetime(e['timestamp'])
                if "AWAY" in e['value']: away_ts = ts
                elif "KILLING" in e['value'] and away_ts:
                    bank_sec += (ts - away_ts).total_seconds()
                    trips += 1
                    away_ts = None
                    
        # Extract Actual Supply Cost from GPPH plugin
        actual_supply_cost = 0
        # Add a 2-minute buffer window to ensure we catch end-of-trip supply logs
        mask = (df_enriched['local_start_time'] >= start_time - timedelta(minutes=2)) & \
               (df_enriched['local_start_time'] <= end_time + timedelta(minutes=2))
        
        session_logs = df_enriched.loc[mask]
        
        for _, row in session_logs.iterrows():
            if row['qty_delta'] < 0:  # Consumed supply!
                item_name = str(row['item_name']).lower()
                price = static_prices.get(item_name, 0)
                actual_supply_cost += abs(row['qty_delta']) * price

        # THE MAGIC MATH: Luck-Adjusted T-NGP/hr
        session_kill_value = base_kill_value
        
        # Option A: The Phantom Wealth Fix
        # If Bonecrusher is equipped, we never loot the bones, so we subtract their market value from the expected drop.
        if data.get("config", {}).get("bones") == "Bonecrusher necklace":
            session_kill_value -= static_prices.get("dragon bones", 0)

        expected_revenue = kills * session_kill_value
        t_ngp_hr = (expected_revenue - actual_supply_cost) / duration_hrs
        
        # Determine raw actual revenue just for variance calculation
        actual_revenue = sum(qty * static_prices.get(item.lower(), 0) for item, qty in data.get('loot_summary', {}).items())
        rng_variance_gp = actual_revenue - expected_revenue

        astb = (bank_sec / trips) if trips > 0 else 0
        
        total_attacks = data.get("total_attacks")
        
        # Use dynamic weapon tick speed to perfectly calculate missed attacks and Active TTK
        weapon = data.get("config", {}).get("weapon", "Unknown")
        
        # Crossbows and T-Bow attack every 6 ticks standard, 5 ticks (3.0s) on Rapid.
        # Assuming Rapid is always used.
        if weapon in ["Dragon hunter crossbow", "Twisted bow", "Dragon crossbow", "Rune crossbow"]:
            weapon_ticks = 5
        # Fallback assumption
        else:
            weapon_ticks = 5

        delta_kph = None

        if total_attacks is not None and active_sec > 0:
            active_ticks = active_sec / 0.6
            max_attacks = int(active_ticks // weapon_ticks)
            
            dropped = max(0, max_attacks - total_attacks)
            miss_per_hr = dropped * (3600.0 / active_sec)
            
            # THE NEW METRIC: Calculate Actual KPH vs Theoretical KPH
            if kills > 0:
                actual_active_ttk = (total_attacks / kills) * (weapon_ticks * 0.6)
                if actual_active_ttk > 0:
                    actual_kph = 3600.0 / actual_active_ttk
                    
                    theoretical_ttk = data.get("theoretical_stats", {}).get("ttk", 0)
                    if theoretical_ttk > 0:
                        theoretical_kph = 3600.0 / theoretical_ttk
                        delta_kph = actual_kph - theoretical_kph
        else:
            # If we don't have attack data, set to None so we don't poison the regression
            miss_per_hr = None 

        row_data = {
            "session_id": data.get("session_id"),
            "date": start_time.strftime("%Y-%m-%d"),
            "duration_hrs": duration_hrs,
            "active_hrs": active_sec / 3600.0,
            "bank_hrs": bank_sec / 3600.0,
            "trips": trips,
            "total_kills": kills,
            "total_attacks": total_attacks if total_attacks is not None else 0,
            "actual_supply_cost": actual_supply_cost,
            "rng_variance_gp": rng_variance_gp,
            "t_ngp_hr": t_ngp_hr,
            "astb": astb,
            "miss_per_hr": miss_per_hr,
            "delta_kph": delta_kph
        }
        
        # Flatten Gear Config for MLR
        config = data.get("config", {})
        for key, val in config.items():
            if key not in["experiment_name", "mode"]: 
                row_data[f"config_{key}"] = val
                
        dataset.append(row_data)

    if not dataset:
        return print("No valid sessions processed.")

    df = pd.DataFrame(dataset)
    
    # 4. ONE-HOT ENCODING
    # We turn categorical strings ("Devout Boots") into binary True/False columns
    config_cols =[c for c in df.columns if c.startswith('config_')]
    df_encoded = pd.get_dummies(df, columns=config_cols)
    
    # Save Output
    df_encoded.to_csv(OUTPUT_CSV, index=False)
    print(f"Successfully normalized {len(df)} sessions.")
    print(f"Dataset ready for MLR and Monte Carlo -> {OUTPUT_CSV}")

if __name__ == "__main__":
    main()