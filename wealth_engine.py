import json
import csv
import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import glob

# --- CONFIG ---
CURRENT_STATE_FILE = "current_state.json"
ENRICHED_CSV = "gpph_enriched.csv"             
JOURNAL_CSV = "adjustments_journal.csv"
EXCHANGE_LOGGER_DIR = r"C:\Users\Teddy\.runelite\exchange-logger"
PRICES_DIR = "price_snapshots"
ITEMS_CSV = "items.csv"
DB_PATH = "time_tracker.db"
OUTPUT_DASHBOARD = "live_wealth.json" # For your GUI to read

# THE SOURCE OF TRUTH (From your Notepad)
GENESIS = {
    "date": "2026-01-13 00:00:00",
    "Gear": 395000000,
    "Supplies": 33000000,
    "Drops": 2000000,
    "GE": 8000000,
    "Total": 438000000
}

class WealthEngine:
    def __init__(self):
        self.item_map_id_to_name = {}
        self.item_map_name_to_id = {}
        self.load_item_maps()

    def load_item_maps(self):
        if os.path.exists(ITEMS_CSV):
            with open(ITEMS_CSV, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    i_id = int(row['id'])
                    name = row['name'].strip()
                    self.item_map_id_to_name[i_id] = name
                    if name.lower() not in self.item_map_name_to_id or "note" not in name.lower():
                        self.item_map_name_to_id[name.lower()] = i_id

    def load_current_state(self):
        with open(CURRENT_STATE_FILE, 'r') as f:
            data = json.load(f)
        
        inventory = {"Gear": {}, "Supplies": {}, "Drops": {}, "GE": {}}
        for cat, items in data['categories'].items():
            for item_name, qty in items.items():
                key = item_name.lower().strip()
                inventory[cat][key] = {"name": item_name, "qty": float(qty)}
                
        if "coins" not in inventory["GE"]: inventory["GE"]["coins"] = {"name": "Coins", "qty": 0.0}
        if "coins" not in inventory["Drops"]: inventory["Drops"]["coins"] = {"name": "Coins", "qty": 0.0}

        return pd.to_datetime(data['snapshot_time']), inventory

    def get_prices_for_date(self, target_date, lookback_hours=168):
        target_ts = int(target_date.timestamp())
        files = glob.glob(os.path.join(PRICES_DIR, "prices_*.csv"))
        
        valid_files =[]
        for f in files:
            try:
                ts = int(os.path.basename(f).replace("prices_", "").replace(".csv", ""))
                if ts <= target_ts + 3600:
                    valid_files.append((ts, f))
            except: pass

        valid_files.sort(key=lambda x: x[0], reverse=True)
        prices = {}
        for ts, f in valid_files[:lookback_hours]:
            with open(f, 'r', encoding='utf-8') as file:
                for row in csv.DictReader(file):
                    item_id = int(row['item_id'])
                    if item_id not in prices:
                        price = int(row['avgLowPrice'] or row['avgHighPrice'] or 0)
                        if price > 0: prices[item_id] = price
        return prices

    def load_ge_transactions(self):
        if not os.path.exists(EXCHANGE_LOGGER_DIR): return pd.DataFrame()
        rows =[]
        files = glob.glob(os.path.join(EXCHANGE_LOGGER_DIR, "*.log")) + glob.glob(os.path.join(EXCHANGE_LOGGER_DIR, "*.json"))
        for f in files:
            with open(f, 'r', encoding='utf-8') as file:
                for line in file:
                    if not line.strip(): continue
                    try:
                        data = json.loads(line)
                        if data.get("state") in ["BOUGHT", "SOLD"] and data.get("qty", 0) > 0:
                            data['timestamp'] = pd.to_datetime(f"{data['date']} {data['time']}")
                            rows.append(data)
                    except: pass
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def get_hours_logged(self, start_date, end_date):
        if not os.path.exists(DB_PATH): return 0.0
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT start_timestamp, end_timestamp FROM shifts WHERE type = 'WORK'", conn)
        conn.close()
        if df.empty: return 0.0

        df['start_timestamp'] = pd.to_datetime(df['start_timestamp'])
        df['end_timestamp'] = pd.to_datetime(df['end_timestamp']).fillna(pd.Timestamp.now())
        mask = (df['start_timestamp'] >= start_date) & (df['start_timestamp'] <= end_date)
        valid_shifts = df.loc[mask]
        
        return (valid_shifts['end_timestamp'] - valid_shifts['start_timestamp']).dt.total_seconds().sum() / 3600.0

    def calculate_live_wealth(self, target_now=None):
        """Rolls the state FORWARD from the snapshot time to Right Now (or a historical target_now)."""
        now = target_now if target_now is not None else pd.Timestamp.now()
        snapshot_date, inventory = self.load_current_state()

        # 1. ADD NEW GRINDS (Forward Time)
        if os.path.exists(ENRICHED_CSV):
            df_enriched = pd.read_csv(ENRICHED_CSV)
            df_enriched['local_start_time'] = pd.to_datetime(df_enriched['local_start_time'], format='%Y-%m-%d %I:%M:%S %p', errors='coerce')
            
            # Find kills AFTER our snapshot, but BEFORE our target time
            mask = (df_enriched['local_start_time'] > snapshot_date) & (df_enriched['local_start_time'] <= now)
            for _, row in df_enriched.loc[mask].iterrows():
                item_name = row['item_name'] if pd.notna(row['item_name']) else self.item_map_id_to_name.get(row['item_id'], f"Item {row['item_id']}")
                key = str(item_name).lower().strip()
                cat = "Drops" if row['qty_delta'] > 0 else "Supplies"
                
                if key not in inventory[cat]: inventory[cat][key] = {"name": item_name, "qty": 0.0}
                inventory[cat][key]['qty'] += float(row['qty_delta'])

        # 2. ADD NEW GE TRADES (Forward Time)
        ge_df = self.load_ge_transactions()
        if not ge_df.empty:
            # Mask to only include trades before our target time
            mask = (ge_df['timestamp'] > snapshot_date) & (ge_df['timestamp'] <= now)
            for _, row in ge_df.loc[mask].iterrows():
                item_name = self.item_map_id_to_name.get(row['item'], f"Item {row['item']}")
                key = item_name.lower().strip()
                if key not in inventory["GE"]: inventory["GE"][key] = {"name": item_name, "qty": 0.0}
                
                if row['state'] == "BOUGHT":
                    inventory["GE"][key]['qty'] += row['qty']
                    inventory["GE"]["coins"]['qty'] -= row['worth']
                elif row['state'] == "SOLD":
                    inventory["GE"][key]['qty'] -= row['qty']
                    inventory["GE"]["coins"]['qty'] += row['worth']

        # 3. APPLY PRICES FOR THAT SPECIFIC DATE
        prices = self.get_prices_for_date(now)
        totals = {"Gear": 0, "Supplies": 0, "Drops": 0, "GE": 0}
        
        for cat, items in inventory.items():
            for key, data in items.items():
                qty = data["qty"]
                if qty == 0: continue
                if key == "coins": totals[cat] += qty
                else:
                    item_id = self.item_map_name_to_id.get(key, 0)
                    totals[cat] += (qty * prices.get(item_id, 0))

        return totals, prices.get(20997, 1600000000), now

    def print_notepad_and_export(self):
        live_totals, tbow_cost, now = self.calculate_live_wealth()
        genesis_dt = pd.to_datetime(GENESIS['date'])
        
        tgt_tot = sum(live_totals.values())
        
        # Time Metrics
        days_elapsed = max((now - genesis_dt).total_seconds() / 86400.0, 1.0)
        hours_logged = self.get_hours_logged(genesis_dt, now)
        hours_per_day = hours_logged / days_elapsed
        
        # Wealth Metrics
        delta_wealth = tgt_tot - GENESIS['Total']
        net_gp_hr = delta_wealth / hours_logged if hours_logged > 0 else 0
        
        gear_delta = live_totals['Gear'] - GENESIS['Gear']
        no_gear_gp_hr = (delta_wealth - gear_delta) / hours_logged if hours_logged > 0 else 0

        # Projections
        gap = tbow_cost - tgt_tot
        progress_pct = (tgt_tot / tbow_cost) * 100

        played_hours_rem = gap / net_gp_hr if net_gp_hr > 0 else 0
        real_days_rem = played_hours_rem / hours_per_day if hours_per_day > 0 else 0
        eta_date = now + timedelta(days=real_days_rem)
        years_rem, days_rem_remainder = int(real_days_rem // 365), int(real_days_rem % 365)

        # --- NOTEPAD OUTPUT (Unchanged) ---
        print("\nwealth tracker:\n")
        print(f"{now.strftime('%Y/%m/%d %I:%M %p')}: ")
        print(f"\t\t Gear: {int(live_totals['Gear']/1000000):>3} ({int((live_totals['Gear'] - GENESIS['Gear'])/1000000):+d})")
        print(f"\t Supplies: {int(live_totals['Supplies']/1000000):>3} ({int((live_totals['Supplies'] - GENESIS['Supplies'])/1000000):+d})")
        print(f"\t\tDrops: {int(live_totals['Drops']/1000000):>3} ({int((live_totals['Drops'] - GENESIS['Drops'])/1000000):+d})")
        print(f"\t\t   GE: {int(live_totals['GE']/1000000):>3} ({int((live_totals['GE'] - GENESIS['GE'])/1000000):+d})")
        print(f"\t\tTotal: {int(tgt_tot/1000000):>3} ({int(delta_wealth/1000000):+d})\n")
        
        print(f"\tHours Logged: {hours_logged:.2f}")
        print(f"\tDays Elapsed: {int(days_elapsed)}")
        print(f"\t Hours / Day: {hours_per_day:.2f}\n")
        
        print(f"\t   Net GP/hr: {int(net_gp_hr/1000):,} K")
        print(f"\tNo Gear Loss: {int(no_gear_gp_hr/1000):,} K\n")
        
        print(f"Twisted Bow Cost: {int(tbow_cost/1000000)} M")
        print(f"\t\t\t Gap: {int(gap/1000000)} M")
        print(f"\t\tProgress: {progress_pct:.1f} %\n")
        
        print(f"  Played Hours to Completion: {int(played_hours_rem)} Est. Hours Remaining")
        if years_rem > 0: print(f"\t Real Time to Completion: {years_rem} Years, {days_rem_remainder} Days")
        else: print(f"\t Real Time to Completion: {days_rem_remainder} Days")
        print(f"Estimated Date of Completion: {eta_date.strftime('%Y/%m/%d')}")
        print("***\n")

        # --- COMPREHENSIVE GUI EXPORT ---
        export_data = {
            "timestamp": now.isoformat(),
            "gear": live_totals['Gear'],
            "supplies": live_totals['Supplies'],
            "drops": live_totals['Drops'],
            "ge": live_totals['GE'],
            "total": tgt_tot,
            "gear_delta": live_totals['Gear'] - GENESIS['Gear'],
            "supplies_delta": live_totals['Supplies'] - GENESIS['Supplies'],
            "drops_delta": live_totals['Drops'] - GENESIS['Drops'],
            "ge_delta": live_totals['GE'] - GENESIS['GE'],
            "total_delta": delta_wealth,
            "hours_logged": hours_logged,
            "days_elapsed": days_elapsed,
            "hours_per_day": hours_per_day,
            "net_gp_hr": net_gp_hr,
            "no_gear_gp_hr": no_gear_gp_hr,
            "tbow_cost": tbow_cost,
            "gap": gap,
            "progress_pct": progress_pct,
            "played_hours_rem": played_hours_rem,
            "real_days_rem": real_days_rem,
            "eta_date": eta_date.strftime('%Y/%m/%d')
        }
        
        with open(OUTPUT_DASHBOARD, "w") as f:
            json.dump(export_data, f, indent=4)
            
        # --- HISTORICAL LOGGING ---
        history_file = "wealth_history.csv"
        file_exists = os.path.exists(history_file)
        with open(history_file, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=export_data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(export_data)

if __name__ == "__main__":
    engine = WealthEngine()
    engine.print_notepad_and_export()