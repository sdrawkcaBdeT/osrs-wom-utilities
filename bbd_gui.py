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
        self.win_iterator = OverlayWindow(self.root, 100, 55, SIDE_ORIGIN_X + 875+103, SIDE_ORIGIN_Y + 2, "Iterator")
        
        # --- WINDOW 2: HISTORY ---
        self.win_history = OverlayWindow(self.root, 375, 105, SIDE_ORIGIN_X + 2, SIDE_ORIGIN_Y + 2, "History")
        
        # --- WINDOW 3: STATISTICS DASHBOARD ---
        self.win_stats = OverlayWindow(self.root, 498, 105, SIDE_ORIGIN_X + 2, SIDE_ORIGIN_Y + 110, "Stats")
        
        # --- WINDOW 4: RNG TRACKER (Gross GP/D) ---
        self.win_rng = OverlayWindow(self.root, 250, 50, SIDE_ORIGIN_X + 2, SIDE_ORIGIN_Y + 218, "RNG Tracker")

        # --- WINDOW 5: OPPORTUNITY COST (Min Slot Value) ---
        self.win_opp = OverlayWindow(self.root, 135, 50, SIDE_ORIGIN_X + 380, SIDE_ORIGIN_Y + 2, "Opp Cost")

        # --- NEW WINDOWS (2x2 Grid) ---
        # Starts 5px to the right of Opportunity Cost (415 + 135 + 5 = 555)
        grid_x = SIDE_ORIGIN_X + 518  
        grid_y = SIDE_ORIGIN_Y + 2

        # Top-Left: Financial Statement (W: 240, H: 180)
        self.win_fin_stmt = OverlayWindow(self.root, 206, 167, grid_x, grid_y, "Fin Stmt")
        
        # Top-Right: Time Log (W: 200, H: 85) -> 5px gap from Top-Left
        self.win_time_log = OverlayWindow(self.root, 200, 74, grid_x + 210, grid_y, "Time Log")
        
        # Bottom-Left: Performance (W: 240, H: 75) -> 5px gap below Top-Left
        self.win_perf = OverlayWindow(self.root, 206, 62, grid_x, grid_y + 170, "Performance")
        
        # Bottom-Right: Projections (W: 200, H: 95) -> 5px gap below Top-Right
        self.win_proj = OverlayWindow(self.root, 200, 95, grid_x + 210, grid_y + 78, "Projections")
        
        # --- WINDOW 7: THE PROMPTER WAFFLE TRACKER ---
        PROMPTER_X = -1930
        PROMPTER_Y = -596
        
        # Sized exactly to the Elgato Prompter
        self.win_waffle = OverlayWindow(self.root, 1024, 600, PROMPTER_X, PROMPTER_Y, "Waffle")

        # --- NEW WINDOW 8: LIVE COMBAT TELEMETRY ---
        # Sits directly below the 2x2 grid. Width: 415px (spanning both columns), Height: 120px
        self.win_telemetry = OverlayWindow(self.root, 350, 95, grid_x + 210, grid_y + 176, "Combat Telemetry")

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

    def load_wealth_data(self):
        if os.path.exists("live_wealth.json"):
            try:
                with open("live_wealth.json", 'r') as f:
                    self.wealth_data = json.load(f)
            except Exception as e:
                pass

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
        
        # Header on the top line
        self.draw_text(c, 10, 5, "NEXT SESSION:", HEADER_COLOR, FONT_BOLD)
        
        # Number shifted down (y=22) and aligned to the left edge (x=10)
        c.create_text(10, 22, text=self.next_session_val, fill="#00FFFF", font=("Consolas", 18, "bold"), anchor="nw")

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

    def draw_fin_stmt(self):
        c = self.win_fin_stmt.canvas
        c.delete("all")
        if not self.wealth_data: return
        w = self.wealth_data
        y = 5
        def fmt_m(val): return f"{int(val/1000000):,}M"
        def fmt_delta(val): return f"{'+' if val > 0 else ''}{int(val/1000000):,}M"

        self.draw_text(c, 10, y, "FINANCIAL STATEMENT", HEADER_COLOR, FONT_BOLD)
        y += 15; c.create_line(10, y, 230, y, fill="gray"); y += 5
        
        self.draw_text(c, 10, y, f"{'Gear':<12} {fmt_m(w['gear']):>6} ({fmt_delta(w['gear_delta']):>5})")
        y += 15
        self.draw_text(c, 10, y, f"{'Supplies':<12} {fmt_m(w['supplies']):>6} ({fmt_delta(w['supplies_delta']):>5})")
        y += 15
        self.draw_text(c, 10, y, f"{'Drops':<12} {fmt_m(w['drops']):>6} ({fmt_delta(w['drops_delta']):>5})")
        y += 15
        self.draw_text(c, 10, y, f"{'GE / Cash':<12} {fmt_m(w['ge']):>6} ({fmt_delta(w['ge_delta']):>5})")
        
        y += 18; c.create_line(10, y, 230, y, fill="#333333"); y += 5
        self.draw_text(c, 10, y, f"{'Subtotal':<12} {fmt_m(w['total']):>6} ({fmt_delta(w['total_delta']):>5})", "#00FFFF", FONT_BOLD)
        
        y += 20
        self.draw_text(c, 10, y, f"{'Twisted Bow':<12} ({fmt_m(w['tbow_cost'])})", "#FF4444")
        y += 18; c.create_line(10, y, 230, y, fill="#333333"); y += 5
        self.draw_text(c, 10, y, f"{'Gap':<12} {fmt_m(w['gap']):>6}", "#FFD700", FONT_BOLD)
        y += 15
        self.draw_text(c, 10, y, f"{'Progress':<12} {w['progress_pct']:>6.1f} %", "#00FF00", FONT_BOLD)

    def draw_time_log(self):
        c = self.win_time_log.canvas
        c.delete("all")
        if not self.wealth_data: return
        w = self.wealth_data
        y = 5
        self.draw_text(c, 10, y, "TIME LOG", HEADER_COLOR, FONT_BOLD)
        y += 15; c.create_line(10, y, 190, y, fill="gray"); y += 5
        self.draw_text(c, 10, y, f"{'Hrs Logged':<13} {w['hours_logged']:>8.2f}")
        y += 15
        self.draw_text(c, 10, y, f"{'Days Elapsed':<13} {int(w['days_elapsed']):>8}")
        y += 15
        self.draw_text(c, 10, y, f"{'Hours/Day':<13} {w['hours_per_day']:>8.2f}")

    def draw_performance(self):
        c = self.win_perf.canvas
        c.delete("all")
        if not self.wealth_data: return
        w = self.wealth_data
        y = 5
        self.draw_text(c, 10, y, "PERFORMANCE", HEADER_COLOR, FONT_BOLD)
        y += 15; c.create_line(10, y, 230, y, fill="gray"); y += 5
        self.draw_text(c, 10, y, f"{'Net GP/hr':<14} {int(w['net_gp_hr']/1000):>7,} K")
        y += 15
        self.draw_text(c, 10, y, f"{'No-Gear GP/hr':<14} {int(w['no_gear_gp_hr']/1000):>7,} K")

    def draw_projections(self):
        c = self.win_proj.canvas
        c.delete("all")
        if not self.wealth_data: return
        w = self.wealth_data
        y = 5
        self.draw_text(c, 10, y, "PROJECTIONS", HEADER_COLOR, FONT_BOLD)
        y += 15; c.create_line(10, y, 190, y, fill="gray"); y += 5
        self.draw_text(c, 10, y, f"{'Played Hrs Rem':<15} {int(w['played_hours_rem']):>6}")
        y += 15
        self.draw_text(c, 10, y, f"{'Real Days Rem':<15} {int(w['real_days_rem']):>6}")
        y += 15
        self.draw_text(c, 10, y, f"{'Completion ETA':<15} {w['eta_date']:>6}", "#00FFFF", FONT_BOLD)

    def draw_waffle(self):
        c = self.win_waffle.canvas
        c.delete("all")
        if not self.wealth_data: return
        w = self.wealth_data

        # Math: 9px box + 1px gap = 10px footprint. 
        # 30 columns = 300px wide per waffle board.
        box_size = 9
        gap = 1
        step = box_size + gap
        cols = 30
        rows = 40  # 1,200 max capacity

        grave_fill, grave_out = "#111111", "#222222"

        def render_grid(start_x, start_y, value, title, fill_c, out_c):
            # 1. Draw Headers
            self.draw_text(c, start_x, start_y, title, HEADER_COLOR, ("Consolas", 14, "bold"))
            self.draw_text(c, start_x, start_y + 25, str(value), fill_c, ("Consolas", 14))

            # 2. Draw Grid
            grid_y_start = start_y + 60
            full_boxes = int(value)
            half_box = (value % 1) >= 0.5

            for i in range(cols * rows):
                r = i // cols
                col = i % cols
                x = start_x + (col * step)
                y = grid_y_start + (r * step)

                if i < full_boxes:
                    c.create_rectangle(x, y, x + box_size, y + box_size, fill=fill_c, outline=out_c)
                elif i == full_boxes and half_box:
                    # Draw Left Half
                    c.create_rectangle(x, y, x + (box_size//2), y + box_size, fill=fill_c, outline=out_c)
                    # Draw Right Half (Graveyard)
                    c.create_rectangle(x + (box_size//2), y, x + box_size, y + box_size, fill=grave_fill, outline=grave_out)
                else:
                    # Graveyard (Unlit LED)
                    c.create_rectangle(x, y, x + box_size, y + box_size, fill=grave_fill, outline=grave_out)

        # Draw the 3 distinct waffle boards, perfectly spaced for a 1024px screen
        grid_start_y = 20
        render_grid(20,  grid_start_y, round(w['hours_logged'],1), "HOURS LOGGED", "#00FF00", "#003300")
        render_grid(360, grid_start_y, round(w['played_hours_rem'],1), "HOURS REMAINING", "#FFD700", "#332B00")
        render_grid(700, grid_start_y, round(w['real_days_rem'],1), "DAYS REMAINING", "#00FFFF", "#003333")

    def draw_telemetry(self):
        import sqlite3
        c = self.win_telemetry.canvas
        c.delete("all")
        
        if not os.path.exists("combat_telemetry.db"):
            self.draw_text(c, 10, 10, "Awaiting Combat Telemetry...", "gray")
            return
            
        try:
            conn = sqlite3.connect("combat_telemetry.db")
            cur = conn.cursor()
            
            # Find the most recently logged session ID
            cur.execute("SELECT session_id FROM hitsplats ORDER BY id DESC LIMIT 1")
            res = cur.fetchone()
            if not res:
                self.draw_text(c, 10, 10, "No attacks logged yet.", "gray")
                conn.close()
                return
                
            latest_session = res[0]
            
            # Grab all damage values for this specific session
            cur.execute("SELECT damage FROM hitsplats WHERE session_id = ?", (latest_session,))
            hits = [row[0] for row in cur.fetchall()]
            conn.close()
            
        except Exception as e:
            self.draw_text(c, 10, 10, f"DB Error: {e}", "red")
            return

        if not hits:
            self.draw_text(c, 10, 10, "No attacks logged in current session.", "gray")
            return

        # --- Calculate Metrics ---
        bolts_fired = len(hits)
        total_dmg = sum(hits)
        
        # Active DPS: Total Damage / (Bolts Fired * 3.0 seconds per attack)
        actual_dps = total_dmg / (bolts_fired * 3.0) if bolts_fired > 0 else 0
        
        # --- Draw Text Headers ---
        self.draw_text(c, 10, 5, "LIVE COMBAT TELEMETRY", HEADER_COLOR, ("Consolas", 10, "bold"))
        c.create_line(10, 20, 340, 20, fill="gray")
        
        # Dropped "Miss%" and rebalanced the remaining text
        self.draw_text(c, 10, 25, f"Bolts Fired: {bolts_fired:,}", TEXT_COLOR, ("Consolas", 9))
        self.draw_text(c, 215, 25, f"Act DPS: {actual_dps:.2f}", "#00FFFF", ("Consolas", 9, "bold"))

        # --- Calculate Histogram Bins ---
        bins = [0] * 7
        for h in hits:
            if h == 0: bins[0] += 1
            elif h <= 10: bins[1] += 1
            elif h <= 20: bins[2] += 1
            elif h <= 30: bins[3] += 1
            elif h <= 40: bins[4] += 1
            elif h <= 50: bins[5] += 1
            else: bins[6] += 1
            
        max_bin = max(bins) if max(bins) > 0 else 1

        # --- Draw Native Bar Chart ---
        bar_w = 28   
        gap = 12     
        start_x = 45 
        base_y = 80  
        max_h = 35   
        
        labels =["0", "1-10", "11-20", "21-30", "31-40", "41-50", "51+"]
        
        # Colors: Pure White for 0, then a smooth grayscale gradient for the damage hits
        colors =["#FFFFFF", "#444444", "#555555", "#666666", "#777777", "#888888", "#999999"]
        
        # Draw physical X and Y axis lines
        c.create_line(start_x - 5, base_y, start_x + (bar_w + gap)*7, base_y, fill="#555555") 
        c.create_line(start_x - 5, base_y, start_x - 5, base_y - max_h - 5, fill="#555555")   
        
        # Y-axis scale markers
        c.create_text(start_x - 10, base_y - max_h, text=str(max_bin), fill="#888888", font=("Consolas", 7), anchor="e")
        c.create_text(start_x - 10, base_y, text="0", fill="#888888", font=("Consolas", 7), anchor="e")
        
        for i in range(7):
            h = (bins[i] / max_bin) * max_h
            x = start_x + i * (bar_w + gap)
            draw_h = h if h > 0 else 1 
            
            c.create_rectangle(x, base_y - draw_h, x + bar_w, base_y, fill=colors[i], outline="#222222")
            
            # --- PERCENTAGE ANNOTATIONS ---
            pct = (bins[i] / bolts_fired) * 100 if bolts_fired > 0 else 0
            
            if pct >= 1:
                pct_text = f"{pct:.0f}%"
            elif pct > 0:
                pct_text = "<1%"
            else:
                pct_text = ""
                
            if pct_text:
                # If the bar is tall enough, put text inside it
                if draw_h >= 10:
                    t_y = base_y - (draw_h / 2)
                    t_color = "black" if i == 0 else "white"
                # If the bar is too short, float the text just above the bar in white
                else:
                    t_y = base_y - draw_h - 5
                    t_color = "white"
                    
                c.create_text(x + (bar_w / 2), t_y, text=pct_text, fill=t_color, font=("Consolas", 7, "bold"), anchor="center")
            
            # X-Axis labels underneath the bars
            c.create_text(x + (bar_w / 2), base_y + 8, text=labels[i], fill="#AAAAAA", font=("Consolas", 7), anchor="center")

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
        self.load_wealth_data()

        self.draw_iterator()
        self.draw_history()
        self.draw_stats()
        self.draw_rng_tracker()
        self.draw_opportunity_cost()
        
        # --- NEW 2x2 GRID ---
        self.draw_fin_stmt()
        self.draw_time_log()
        self.draw_performance()
        self.draw_projections()
        
        self.draw_waffle()
        self.draw_telemetry()

    def start_auto_refresh(self):
        self.root.after(5000, self.run_auto_refresh)

    def run_auto_refresh(self):
        self.refresh_all()
        self.start_auto_refresh()

    def close_app(self):
        self.root.quit()

if __name__ == "__main__":
    BBDGUI()