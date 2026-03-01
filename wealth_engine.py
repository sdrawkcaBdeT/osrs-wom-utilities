import json
import csv
import os
import pandas as pd
from datetime import datetime
import glob

# --- CONFIG ---
CURRENT_STATE_FILE = "current_state.json"
ENRICHED_CSV = "gpph_enriched.csv"             
JOURNAL_CSV = "adjustments_journal.csv"
EXCHANGE_LOGGER_DIR = r"C:\Users\Teddy\.runelite\exchange-logger"
PRICES_DIR = "price_snapshots"
ITEMS_CSV = "items.csv"

class WealthEngine:
    def __init__(self):
        self.item_map_id_to_name = {}
        self.item_map_name_to_id = {}
        self.load_item_maps()

    def load_item_maps(self):
        if not os.path.exists(ITEMS_CSV):
            print(f"Warning: {ITEMS_CSV} not found. Item translation may fail.")
            return

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
            if cat not in inventory: inventory[cat] = {}
            for item_name, qty in items.items():
                key = item_name.lower().strip()
                inventory[cat][key] = {"name": item_name, "qty": float(qty)}
                
        if "coins" not in inventory["GE"]: inventory["GE"]["coins"] = {"name": "Coins", "qty": 0.0}
        if "coins" not in inventory["Drops"]: inventory["Drops"]["coins"] = {"name": "Coins", "qty": 0.0}

        return pd.to_datetime(data['snapshot_time']), inventory

    def get_prices_for_date(self, target_date, lookback_hours=168):
        """
        Builds a composite price dictionary.
        Looks at the target snapshot, and if items are missing, looks back up to 7 days 
        (168 hours) to find the most recent trade price for low-volume items.
        """
        target_ts = int(target_date.timestamp())
        files = glob.glob(os.path.join(PRICES_DIR, "prices_*.csv"))
        
        # Parse and filter files that are on or before our target date
        valid_files =[]
        for f in files:
            try:
                ts = int(os.path.basename(f).replace("prices_", "").replace(".csv", ""))
                # +3600 buffer to catch the bucket your target date falls into
                if ts <= target_ts + 3600:
                    valid_files.append((ts, f))
            except: pass

        # Sort descending (newest valid file first, rewinding backward)
        valid_files.sort(key=lambda x: x[0], reverse=True)

        prices = {}
        # Iterate backwards through time to fill out the price book
        for ts, f in valid_files[:lookback_hours]:
            with open(f, 'r', encoding='utf-8') as file:
                for row in csv.DictReader(file):
                    item_id = int(row['item_id'])
                    
                    # If we don't have a price for this item yet, grab it!
                    if item_id not in prices:
                        # Fallback to HighPrice if LowPrice is 0 (for super weird volume)
                        price = int(row['avgLowPrice'] or row['avgHighPrice'] or 0)
                        if price > 0:
                            prices[item_id] = price

        return prices

    def load_ge_transactions(self):
        if not os.path.exists(EXCHANGE_LOGGER_DIR):
            return pd.DataFrame()

        rows =[]
        files = glob.glob(os.path.join(EXCHANGE_LOGGER_DIR, "*.log")) + glob.glob(os.path.join(EXCHANGE_LOGGER_DIR, "*.json"))
        
        for f in files:
            with open(f, 'r', encoding='utf-8') as file:
                for line in file:
                    if not line.strip(): continue
                    try:
                        data = json.loads(line)
                        if data.get("state") in["BOUGHT", "SOLD", "CANCELLED_BUY", "CANCELLED_SELL"] and data.get("qty", 0) > 0:
                            timestamp_str = f"{data['date']} {data['time']}"
                            data['timestamp'] = pd.to_datetime(timestamp_str)
                            rows.append(data)
                    except: pass
                    
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def calculate_wealth_on_date(self, target_date_str):
        target_date = pd.to_datetime(target_date_str)
        snapshot_date, inventory = self.load_current_state()

        if target_date > snapshot_date:
            print("Target date is in the future. Can only reverse time.")
            return

        if target_date != snapshot_date:
            print(f"\nReversing time from {snapshot_date.strftime('%Y/%m/%d %I:%M %p')} down to {target_date.strftime('%Y/%m/%d %I:%M %p')}...\n")

        # --- 1. REVERSE GRINDING LEDGER ---
        if os.path.exists(ENRICHED_CSV):
            df_enriched = pd.read_csv(ENRICHED_CSV)
            # FIX: Explicit format to remove the UserWarning
            df_enriched['local_start_time'] = pd.to_datetime(df_enriched['local_start_time'], format='%Y-%m-%d %I:%M:%S %p')
            
            mask = (df_enriched['local_start_time'] >= target_date) & (df_enriched['local_start_time'] <= snapshot_date)
            reversal_grinds = df_enriched.loc[mask]
            
            for _, row in reversal_grinds.iterrows():
                item_name = row['item_name'] if pd.notna(row['item_name']) else self.item_map_id_to_name.get(row['item_id'], f"Item {row['item_id']}")
                key = str(item_name).lower().strip()
                cat = "Drops" if row['qty_delta'] > 0 else "Supplies"
                
                if key not in inventory[cat]:
                    inventory[cat][key] = {"name": item_name, "qty": 0.0}
                
                inventory[cat][key]['qty'] -= float(row['qty_delta'])

        # --- 2. REVERSE GE LOGS ---
        ge_df = self.load_ge_transactions()
        if not ge_df.empty:
            mask = (ge_df['timestamp'] >= target_date) & (ge_df['timestamp'] <= snapshot_date)
            reversal_ge = ge_df.loc[mask]
            
            for _, row in reversal_ge.iterrows():
                item_name = self.item_map_id_to_name.get(row['item'], f"Item {row['item']}")
                key = item_name.lower().strip()
                
                if key not in inventory["GE"]:
                    inventory["GE"][key] = {"name": item_name, "qty": 0.0}
                
                if row['state'] in ["BOUGHT", "CANCELLED_BUY"]:
                    inventory["GE"][key]['qty'] -= row['qty']
                    inventory["GE"]["coins"]['qty'] += row['worth']
                elif row['state'] in ["SOLD", "CANCELLED_SELL"]:
                    inventory["GE"][key]['qty'] += row['qty']
                    inventory["GE"]["coins"]['qty'] -= row['worth']

        # --- 3. REVERSE MANUAL JOURNAL ---
        if os.path.exists(JOURNAL_CSV):
            df_journal = pd.read_csv(JOURNAL_CSV)
            df_journal['date'] = pd.to_datetime(df_journal['date'])
            
            mask = (df_journal['date'] >= target_date) & (df_journal['date'] <= snapshot_date)
            reversal_events = df_journal.loc[mask]

            for _, row in reversal_events.iterrows():
                key = str(row['item_name']).lower().strip()
                to_cat = row['to_cat']
                from_cat = row['from_cat']
                event_type = str(row['type']).upper()

                if to_cat in inventory and key not in inventory[to_cat]:
                    inventory[to_cat][key] = {"name": row['item_name'], "qty": 0.0}

                if event_type == "INJECTION":
                    inventory[to_cat][key]["qty"] -= row['qty']
                elif event_type == "EXTRACTION":
                    inventory[from_cat][key]["qty"] += row['qty']
                elif event_type == "BUY":
                    inventory[to_cat][key]["qty"] -= row['qty']
                    inventory[from_cat]['coins']['qty'] += row['gp_value']
                elif event_type == "SELL":
                    inventory[from_cat][key]["qty"] += row['qty']
                    inventory[to_cat]['coins']['qty'] -= row['gp_value']

        # --- 4. APPLY PRICES FOR TARGET DATE ---
        prices = self.get_prices_for_date(target_date)
        totals = {"Gear": 0, "Supplies": 0, "Drops": 0, "GE": 0}
        
        for cat, items in inventory.items():
            for key, data in items.items():
                qty = data["qty"]
                
                if qty == 0:
                    continue
                    
                if key == "coins":
                    totals[cat] += qty
                else:
                    item_id = self.item_map_name_to_id.get(key, 0)
                    price = prices.get(item_id, 0)
                    
                    if price == 0 and qty > 0:
                        print(f" [!] Warning: '{data['name']}' in {cat} evaluated at 0 GP. Check spelling!")
                        
                    totals[cat] += (qty * price)

        grand_total = sum(totals.values())
        tbow_price = prices.get(20997, 1600000000) 
        gap = tbow_price - grand_total
        progress = (grand_total / tbow_price) * 100

        # --- NOTEPAD OUTPUT ---
        date_display = target_date.strftime('%Y/%m/%d %I:%M %p')
        print(f"wealth tracker:")
        print(f"\n{date_display}: ")
        print(f"\t\t Gear: {int(totals.get('Gear', 0) / 1000000):>3} M")
        print(f"\t Supplies: {int(totals.get('Supplies', 0) / 1000000):>3} M")
        print(f"\t\tDrops: {int(totals.get('Drops', 0) / 1000000):>3} M")
        print(f"\t\t   GE: {int(totals.get('GE', 0) / 1000000):>3} M")
        print(f"\t\tTotal: {int(grand_total / 1000000):>3} M")
        print("\nTwisted Bow Cost: {:>4} M".format(int(tbow_price / 1000000)))
        print(f"\t\t\t Gap: {int(gap / 1000000):>4} M")
        print(f"\t\tProgress: {progress:.1f} %")
        print("***\n")

if __name__ == "__main__":
    engine = WealthEngine()
    engine.calculate_wealth_on_date("2026-02-28 16:00")