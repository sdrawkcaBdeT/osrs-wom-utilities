import tkinter as tk
import os
import json
import glob
import csv
from datetime import datetime, timedelta
import keyboard

# Safely import the drop table so we can calculate theoreticals
try:
    from bbd_tracker import DROP_TABLE
except ImportError:
    print("Warning: Could not import DROP_TABLE from bbd_tracker.py")
    DROP_TABLE = {}

# --- CONFIG ---
DATA_DIR = "bbd_data"
STATE_FILE = "session_state.json"
TEXT_COLOR = "#00FF00"      # Green text (Matrix style)
HEADER_COLOR = "#FFFFFF"    # White headers
BACKGROUND_COLOR = "black"
WINDOW_OPACITY = 0.85
FONT_MAIN = ("Consolas", 10)
FONT_BOLD = ("Consolas", 10, "bold")

class OverlayWindow(tk.Toplevel):
    def __init__(self, master, width, height, x, y, title):
        super().__init__(master)
        self.overrideredirect(True)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.attributes("-topmost", True)
        self.attributes("-alpha", WINDOW_OPACITY)
        self.configure(bg=BACKGROUND_COLOR)
        self.title(title)
        
        self.canvas = tk.Canvas(self, width=width, height=height, bg=BACKGROUND_COLOR, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

class BBDGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw() # Hide main window

        # State Variables
        self.sessions =[]
        self.next_session_val = "0001"
        self.item_map = {}
        self.prices = {}
        self.gpph_data =[]
        
        # Load Data Ecosystem
        self.load_items_and_prices()
        self.load_session_data()
        self.load_state()

        # --- MONITOR LAYOUT ---
        MAIN_W, MAIN_H = 2560, 1440
        SIDE_W, SIDE_H = 1080, 1920
        SIDE_ORIGIN_X = MAIN_W   
        SIDE_ORIGIN_Y = 0        

        # --- WINDOW 1: NEXT SESSION ITERATOR ---
        self.win_iterator = OverlayWindow(self.root, 200, 40, SIDE_ORIGIN_X + 875, SIDE_ORIGIN_Y + 5, "Iterator")
        
        # --- WINDOW 2: HISTORY ---
        self.win_history = OverlayWindow(self.root, 400, 110, SIDE_ORIGIN_X + 5, SIDE_ORIGIN_Y + 5, "History")
        
        # --- WINDOW 3: STATISTICS DASHBOARD ---
        self.win_stats = OverlayWindow(self.root, 525, 120, SIDE_ORIGIN_X + 5, SIDE_ORIGIN_Y + 125, "Stats")
        
        # --- WINDOW 4: RNG TRACKER (Gross GP/D) ---
        self.win_rng = OverlayWindow(self.root, 300, 50, SIDE_ORIGIN_X + 400 + 15, SIDE_ORIGIN_Y + 5, "RNG Tracker")

        # --- WINDOW 5: OPPORTUNITY COST (Min Slot Value) ---
        self.win_opp = OverlayWindow(self.root, 135, 50, SIDE_ORIGIN_X + 400 + 15, SIDE_ORIGIN_Y + 65, "Opp Cost")

        # Initial Draw
        self.refresh_all()

        # Hotkeys
        keyboard.add_hotkey("ctrl+up", self.increment_session)
        keyboard.add_hotkey("ctrl+down", self.decrement_session)
        keyboard.add_hotkey("ctrl+r", self.refresh_all)
        keyboard.add_hotkey("ctrl+q", self.close_app)

        self.start_auto_refresh()
        self.root.mainloop()

    # --- DATA PIPELINE ---
    def load_items_and_prices(self):
        self.item_map.clear()
        self.prices.clear()
        
        # 1. Load Dictionary (ID/Alch values)
        if os.path.exists("items.csv"):
            with open("items.csv", 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    self.item_map[row['name'].lower()] = {
                        'id': int(row['id']),
                        'highalch': int(row['highalch']) if row['highalch'] else 0
                    }
        
        # 2. Load latest Wiki Snapshot
        snapshot_dir = "price_snapshots"
        if os.path.exists(snapshot_dir):
            files = glob.glob(os.path.join(snapshot_dir, "prices_*.csv"))
            if files:
                newest_file = max(files, key=os.path.getctime)
                with open(newest_file, 'r', encoding='utf-8') as f:
                    for row in csv.DictReader(f):
                        avg_low = int(row['avgLowPrice']) if row['avgLowPrice'] else 0
                        self.prices[int(row['item_id'])] = avg_low

    def get_item_value(self, name):
        """Translates Name -> ID -> Wiki Price (Fallback to High Alch)"""
        name_lower = name.lower()
        if name_lower in self.item_map:
            item_id = self.item_map[name_lower]['id']
            val = self.prices.get(item_id, 0)
            if val == 0:
                val = self.item_map[name_lower]['highalch']
            return val
        return 0

    def load_session_data(self):
        self.sessions =[]
        
        # 1. Pre-load GPPH sessions into memory for fast matching
        self.gpph_data =[]
        if os.path.exists("gpph_sessions.csv"):
            with open("gpph_sessions.csv", 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    try:
                        # Convert human readable "2026-02-27 06:23:09 PM" to datetime
                        dt = datetime.strptime(row['local_start_time'], '%Y-%m-%d %I:%M:%S %p')
                        self.gpph_data.append({
                            'time': dt,
                            'profit': int(row['net_profit']),
                            'duration': int(row['duration_seconds'])
                        })
                    except Exception:
                        pass

        # 2. Process all JSON files
        files = glob.glob(os.path.join(DATA_DIR, "*.json"))
        for f in files:
            try:
                with open(f, 'r') as file:
                    data = json.load(file)
                    
                    sess_name = data.get('config', {}).get('experiment_name', '????')
                    start_str = data.get('start_time')
                    end_str = data.get('end_time')
                    kills = data.get('total_kills', 0)

                    start_dt = datetime.fromisoformat(start_str) if start_str else datetime.now()
                    end_dt = datetime.fromisoformat(end_str) if end_str else datetime.now()
                    duration_sec = (end_dt - start_dt).total_seconds()

                    total_attacks = data.get('total_attacks', None) 
                    active_seconds = data.get('active_seconds', 0)

                    # Extract ASTB Banking logic
                    bank_sec, trips = 0, 0
                    away_ts = None
                    for e in data.get('event_timeline',[]):
                        if e['type'] == 'phase':
                            ts = datetime.fromisoformat(e['timestamp'])
                            if "AWAY" in e['value']: away_ts = ts
                            elif "KILLING" in e['value'] and away_ts:
                                bank_sec += (ts - away_ts).total_seconds()
                                trips += 1
                                away_ts = None 

                    # Calculate Gross GP for this session based on exact drops
                    gross_gp = 0
                    for item, qty in data.get('loot_summary', {}).items():
                        gross_gp += self.get_item_value(item) * qty
                        
                    # Match this JSON session to a GPPH Net ledger session (5 minute tolerance)
                    net_profit, duration_gpph = None, None
                    for g in self.gpph_data:
                        if abs((start_dt - g['time']).total_seconds()) < 300:
                            net_profit = g['profit']
                            duration_gpph = g['duration']
                            break

                    self.sessions.append({
                        'name': sess_name,
                        'date': start_dt,
                        'duration_sec': duration_sec,
                        'active_sec': active_seconds,
                        'attacks': total_attacks,
                        'kills': kills,
                        'bank_sec': bank_sec,
                        'trips': trips,
                        'gross_gp': gross_gp,
                        'net_profit': net_profit,
                        'duration_gpph': duration_gpph
                    })
            except Exception as e:
                pass

        self.sessions.sort(key=lambda x: x['date'], reverse=True)

        if self.sessions and not os.path.exists(STATE_FILE):
            try:
                last_num = int(self.sessions[0]['name'])
                self.next_session_val = f"{last_num + 1:04d}"
                self.save_state()
            except: pass

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    self.next_session_val = data.get("next_session", "0001")
            except: self.next_session_val = "0001"

    def save_state(self):
        with open(STATE_FILE, 'w') as f:
            json.dump({"next_session": self.next_session_val}, f)
        self.draw_iterator()

    # --- MATH HELPER ---
    def calculate_efficiency(self, duration_sec, active_sec, attacks, bank_sec, trips):
        if duration_sec <= 0: return "-", "-", "-"
        
        astb = (bank_sec / trips) if trips > 0 else 0
        astb_str = f"{astb:.0f}s" if trips > 0 else "-"
        upt_pct = (active_sec / duration_sec) * 100
        
        if attacks is None or active_sec <= 0: return astb_str, "-", "-"
        
        active_ticks = active_sec / 0.6
        max_attacks = int(active_ticks // 5)
        
        # Bring back the MISS/HR calculation
        dropped = max(0, max_attacks - attacks)
        miss_per_hr = dropped * (3600.0 / active_sec)
        
        atk_pct = min((attacks / max_attacks * 100) if max_attacks > 0 else 0, 100.0) 
        eff_pct = (upt_pct / 100.0) * (atk_pct / 100.0) * 100

        # Return all 3 combat metrics
        return astb_str, f"{miss_per_hr:.0f}", f"{eff_pct:.0f}%"

    # --- DRAWING ---
    def draw_text(self, canvas, x, y, text, color=TEXT_COLOR, font=FONT_MAIN):
        canvas.create_text(x, y, text=text, fill=color, font=font, anchor="nw")

    def draw_iterator(self):
        c = self.win_iterator.canvas
        c.delete("all")
        self.draw_text(c, 10, 5, "NEXT SESSION:", HEADER_COLOR, FONT_BOLD)
        c.create_text(120, 5, text=self.next_session_val, fill="#00FFFF", font=("Consolas", 18, "bold"), anchor="nw")

    # --- DRAWING ---
    def draw_history(self):
        c = self.win_history.canvas
        c.delete("all")
        
        # Brought MISS back, carefully packed to fit 50 chars (360px)
        headers = f"{'SESS':<6} {'DATE':<11} {'KILLS':>5} {'GGP/s':>5} {'ASTB':>4} {'MISS':>4} {'EFF%':>4} {'GP/D':>5}"
        self.draw_text(c, 10, 5, headers, HEADER_COLOR, FONT_BOLD)
        c.create_line(10, 20, 350, 20, fill="gray")
        y = 25
        
        for s in self.sessions[:5]:
            date_str = s['date'].strftime("%m/%d %H:%M") 
            astb_s, miss_s, eff_s = self.calculate_efficiency(s['duration_sec'], s['active_sec'], s['attacks'], s['bank_sec'], s['trips'])
            
            # GGP/s Calculation
            gpd = s['gross_gp'] / s['kills'] if s['kills'] > 0 else 0
            ggps = s['gross_gp'] / s['duration_sec'] if s['duration_sec'] > 0 else 0
            
            row_txt = f"{s['name']:<6} {date_str:<11} {s['kills']:>5} {ggps:>5.1f} {astb_s:>4} {miss_s:>4} {eff_s:>4} {gpd:>5.0f}"
            self.draw_text(c, 10, y, row_txt)
            y += 15

    def draw_stats(self):
        c = self.win_stats.canvas
        c.delete("all")
        now = datetime.now()
        periods =[("24h", 24), ("3d", 72), ("7d", 168), ("30d", 720)]

        # Brought R-HR, MISS, and K/R-HR back. Packed to fit ~68 chars (525px max)
        headers = f"{'PERIOD':<6} {'SESS':<4} {'HRS':<4} {'R-HR':<4}| {'GP/D':>5} {'NGP/s':>5} {'ASTB':>4} {'MISS':>4} {'EFF%':>4} | {'KILLS':>5} {'K/HR':>4} {'K/R-HR':>6}"
        self.draw_text(c, 10, 5, headers, HEADER_COLOR, FONT_BOLD)
        c.create_line(10, 20, 515, 20, fill="gray")

        y = 25
        for name, r_hours in periods:
            cutoff = now - timedelta(hours=r_hours)
            subset =[s for s in self.sessions if s['date'] > cutoff]
            
            count = len(subset)
            total_dur_sec = sum(s['duration_sec'] for s in subset)
            total_act_sec = sum(s['active_sec'] for s in subset)
            kills = sum(s['kills'] for s in subset)
            total_bank_sec = sum(s['bank_sec'] for s in subset)
            total_trips = sum(s['trips'] for s in subset)
            total_gross = sum(s['gross_gp'] for s in subset)
            
            valid_atk =[s for s in subset if s['attacks'] is not None]
            total_atk_sec = sum(s['active_sec'] for s in valid_atk) if valid_atk else 0
            total_attacks = sum(s['attacks'] for s in valid_atk) if valid_atk else None
            
            # Match Net Ledger sessions
            matched_net =[s for s in subset if s['net_profit'] is not None]

            if count > 0:
                astb = (total_bank_sec / total_trips) if total_trips > 0 else 0
                astb_s = f"{astb:.0f}s" if total_trips > 0 else "-"
                upt_pct = (total_act_sec / total_dur_sec * 100) if total_dur_sec > 0 else 0
                
                # Gross GP/D
                gpd = total_gross / kills if kills > 0 else 0
                
                # Net GP/s (NGP/s)
                if matched_net:
                    total_net = sum(s['net_profit'] for s in matched_net)
                    total_dur = sum(s['duration_gpph'] for s in matched_net)
                    ngps = total_net / total_dur if total_dur > 0 else 0
                    ngps_str = f"{ngps:.1f}"
                else:
                    ngps_str = "-"

                if total_attacks is not None and total_atk_sec > 0:
                    max_attacks = int((total_atk_sec / 0.6) // 5)
                    # Brought MISS back
                    dropped = max(0, max_attacks - total_attacks)
                    miss_per_hr = dropped * (3600.0 / total_atk_sec)
                    atk_pct = min((total_attacks / max_attacks * 100) if max_attacks > 0 else 0, 100.0)
                    eff_pct = (upt_pct / 100.0) * (atk_pct / 100.0) * 100
                    
                    miss_s = f"{miss_per_hr:.0f}"
                    eff_s = f"{eff_pct:.0f}%"
                else: 
                    miss_s, eff_s = "-", "-"
            else: 
                astb_s, miss_s, eff_s, gpd, ngps_str = "-", "-", "-", 0, "-"

            hrs_logged = total_dur_sec / 3600
            k_hr = (kills / hrs_logged) if hrs_logged > 0 else 0
            # Brought K/R-HR back
            k_r_hr = (kills / r_hours) if r_hours > 0 else 0

            row_txt = f"{name:<6} {count:<4} {hrs_logged:<4.1f} {r_hours:<4}| {gpd:>5.0f} {ngps_str:>5} {astb_s:>4} {miss_s:>4} {eff_s:>4} | {kills:>5} {k_hr:>4.1f} {k_r_hr:>6.1f}"
            self.draw_text(c, 10, y, row_txt)
            y += 20

    # --- NEW WINDOWS ---
    def draw_rng_tracker(self):
        c = self.win_rng.canvas
        c.delete("all")

        # 1. Theoretical Calculation (Baseline Perfect RNG)
        theo_gpd = 0
        for item, info in DROP_TABLE.items():
            val = self.get_item_value(item)
            theo_gpd += val * info['rate'] * info['qty']

        # 2. All-Time Calculation
        total_gross = sum(s['gross_gp'] for s in self.sessions)
        total_kills = sum(s['kills'] for s in self.sessions)
        all_time_gpd = (total_gross / total_kills) if total_kills > 0 else 0

        # 3. Current Session Calculation
        curr_gpd = 0
        if self.sessions and self.sessions[0]['kills'] > 0:
            curr_gpd = self.sessions[0]['gross_gp'] / self.sessions[0]['kills']

        # Draw Table Headers
        self.draw_text(c, 10, 5, "THEORETICAL", HEADER_COLOR, FONT_BOLD)
        self.draw_text(c, 110, 5, "ALL-TIME", HEADER_COLOR, FONT_BOLD)
        self.draw_text(c, 200, 5, "CURRENT", HEADER_COLOR, FONT_BOLD)
        c.create_line(10, 20, 290, 20, fill="gray")
        
        # Draw Values
        self.draw_text(c, 10, 25, f"{theo_gpd:,.0f}")
        self.draw_text(c, 110, 25, f"{all_time_gpd:,.0f}")
        self.draw_text(c, 200, 25, f"{curr_gpd:,.0f}")

    def draw_opportunity_cost(self):
        c = self.win_opp.canvas
        c.delete("all")

        # 1. Calculate Average NGP/s over recent matched sessions
        matched_sessions = [s for s in self.sessions if s['net_profit'] is not None][:5]
        net_gps = 0
        if matched_sessions:
            sum_profit = sum(s['net_profit'] for s in matched_sessions)
            sum_dur = sum(s['duration_gpph'] for s in matched_sessions)
            if sum_dur > 0:
                net_gps = sum_profit / sum_dur

        # 2. Get Current ASTB
        astb = 0
        if self.sessions:
            s = self.sessions[0]
            if s['trips'] > 0:
                astb = s['bank_sec'] / s['trips']

        # 3. Calculate Threshold (Opportunity Cost of 1 inventory slot)
        min_slot_val = (net_gps * astb) / 24

        # Updated Header to explicitly say NGP/s
        self.draw_text(c, 10, 5, "NGP/s | MIN SLOT", HEADER_COLOR, FONT_BOLD)
        c.create_line(10, 20, 125, 20, fill="gray")
        
        val_txt = f"{net_gps:.1f} | {min_slot_val:,.0f}"
        c.create_text(10, 25, text=val_txt, fill="#FFD700", font=("Consolas", 12, "bold"), anchor="nw")

    # --- ACTIONS ---
    def increment_session(self):
        try:
            val = int(self.next_session_val)
            self.next_session_val = f"{val + 1:04d}"
            self.save_state()
        except: pass

    def decrement_session(self):
        try:
            val = int(self.next_session_val)
            if val > 0:
                self.next_session_val = f"{val - 1:04d}"
                self.save_state()
        except: pass

    def refresh_all(self):
        self.load_items_and_prices()
        self.load_session_data()
        self.draw_iterator()
        self.draw_history()
        self.draw_stats()
        self.draw_rng_tracker()
        self.draw_opportunity_cost()

    def start_auto_refresh(self):
        self.root.after(5000, self.run_auto_refresh)

    def run_auto_refresh(self):
        self.refresh_all()
        self.start_auto_refresh()

    def close_app(self):
        self.root.quit()

if __name__ == "__main__":
    BBDGUI()