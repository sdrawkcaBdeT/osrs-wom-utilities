import tkinter as tk
import os
import json
import glob
import csv
from datetime import datetime, timedelta
import keyboard
import requests
import time
import threading
import queue

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
        self.last_snapshot_mtime = 0.0 # Cache for O(1) checking
        
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

        # --- WINDOW 9: LIVE TICK MATRIX ---
        # Starts 4px to the right of the RNG Tracker window (which is 250px wide) at x + 2 + 250 + 4
        self.win_ticks = OverlayWindow(self.root, 258, 62, SIDE_ORIGIN_X + 256, SIDE_ORIGIN_Y + 218, "Dual View Matrix")

        # --- WINDOW 10: THE MEGAVAULT CLUSTER ---
        # Option A Geometry: 4 Vaults, Single Row. Width: 139px, Height: 36px
        self.win_vaults = OverlayWindow(self.root, 139, 39, SIDE_ORIGIN_X + 379, SIDE_ORIGIN_Y + 53, "Vault Cluster")

        self.current_view = "Matrix"
        self.tick_history = []
        self.last_tick_processed = None
        self.cooldown_remaining = 0
        
        # --- PHASE 4 ECONOMY ---
        self.gp_backlog = 0
        self.vault_gp = 0
        self.last_total_profit = 0
        
        # --- PHASE 5 DRAIN SEQUENCE ---
        self.is_draining = False
        self.drain_index = 0
        self.was_session_running = False  # Tracks when to flush the vaults
        
        # Initial Draw
        self.refresh_all()

        # Start HTTP Polling Daemon
        self.http_queue = queue.Queue()
        threading.Thread(target=self.http_polling_daemon, daemon=True).start()

        # Hotkeys
        keyboard.add_hotkey("ctrl+l", self.toggle_view)
        keyboard.add_hotkey("ctrl+up", self.increment_session)
        keyboard.add_hotkey("ctrl+down", self.decrement_session)
        keyboard.add_hotkey("ctrl+r", self.refresh_all)
        keyboard.add_hotkey("ctrl+q", self.close_app)

        self.start_auto_refresh()
        self.start_tick_loop()
        self.root.mainloop()

    # --- TICK POLL LOOP ---
    def start_tick_loop(self):
        self.root.after(50, self.run_tick_loop)

    def toggle_view(self):
        if self.current_view == "Matrix":
            self.current_view = "Gold"
        else:
            self.current_view = "Matrix"
        self.refresh_all()

    def http_polling_daemon(self):
        while True:
            try:
                # Fast timeout so the thread doesn't hang if the server drops
                resp = requests.get("http://127.0.0.1:5000/hp", timeout=0.1)
                self.http_queue.put(resp.json())
            except Exception:
                pass
            time.sleep(0.05) # ~20Hz polling rate

    def run_tick_loop(self):
        data = None
        try:
            # Drain the queue to grab only the absolute freshest state
            while True:
                data = self.http_queue.get_nowait()
        except queue.Empty:
            pass

        if data:
            # --- PHASE 5/6: PIPELINE FLUSH LOGIC ---
            is_running = data.get("session_running", False)
            if is_running and not self.was_session_running:
                # A new session just started. 
                self.vault_gp = 0
                self.gp_backlog = 0 
                
                # CRITICAL FIX: Sync the high-water mark so new gold flows
                self.last_total_profit = data.get("total_profit", 0) 
                
                # Wipe the physical conveyor belt clean for the new run
                self.tick_history.clear() 
                
                self.draw_ticks()
                self.draw_vaults()
            self.was_session_running = is_running

            # 1. Check for the End Session Handshake
            if data.get("drain_triggered") and not self.is_draining:
                self.start_drain_sequence()
                
            # 2. If we are actively draining, halt all normal matrix progression
            # 2. If we are actively draining, halt all normal matrix progression
            if not self.is_draining:
                total_profit = data.get("total_profit", 0)
                # Changed from > to != to allow negative deltas (expenses)
                if total_profit != self.last_total_profit:
                    self.gp_backlog += (total_profit - self.last_total_profit)
                    self.last_total_profit = total_profit

                # --- PHASE 6 FIX: Read the Rolling Stream ---
                udp_stream = data.get("udp_stream", [])
                server_phase = data.get("phase", "IDLE")

                # Iterate through the entire buffer of recent ticks
                for udp_payload in udp_stream:
                    tick = udp_payload.get("tick")
                    state = udp_payload.get("state", "idle")

                    # --- The Matrix Bouncer ---
                    if tick is not None:
                        if self.last_tick_processed is None:
                            self.last_tick_processed = tick - 1

                        # ONLY process if this tick is newer than our matrix timeline
                        if tick > self.last_tick_processed:
                            # If we STILL have a gap here, it's a true network drop
                            missed = tick - self.last_tick_processed - 1
                            for _ in range(missed):
                                self.push_tick("#333333", False)

                            if state == "attack":
                                self.cooldown_remaining = 4
                                self.push_tick("#00FFFF", True)
                            else:
                                if self.cooldown_remaining > 0:
                                    self.cooldown_remaining -= 1
                                    self.push_tick("#00FF00", False)
                                else:
                                    if state == "away" or server_phase == "AWAY":
                                        self.push_tick("#FFFF00", False)
                                    else:
                                        self.push_tick("#FF0000", False)
                            
                            self.last_tick_processed = tick

        self.root.after(50, self.run_tick_loop)

    def start_drain_sequence(self):
        self.is_draining = True
        # Because we insert(0), index len-1 is the oldest tick closest to the vault
        self.drain_index = len(self.tick_history) - 1 
        self.run_drain_sweep()

    def run_drain_sweep(self):
        if self.drain_index >= 0:
            # Fast-forward extract GP from the tick
            tick = self.tick_history[self.drain_index]
            gp = tick.get("gp", 0)
            if gp > 0:
                self.vault_gp += gp
                tick["gp"] = 0 # Visually erase the gold from the belt
                self.draw_ticks()
                self.draw_vaults()
            
            # Move backwards towards the start of the conveyor
            self.drain_index -= 1
            self.root.after(20, self.run_drain_sweep) # 20ms rapid sweep
        else:
            # Array swept. Dump any remaining raw backlog directly into the vault.
            if self.gp_backlog > 0:
                self.vault_gp += self.gp_backlog
                
            final_gp = self.vault_gp
            
            # Fire the resolution callback to Flask to trigger the save
            try:
                payload = {"event": "drain_complete", "payload": {"final_vault_gp": final_gp}}
                requests.post("http://127.0.0.1:5000/event", json=payload, timeout=0.1)
            except Exception:
                pass
                
            # Safely reset the pipeline flags, but LEAVE self.vault_gp intact
            self.gp_backlog = 0
            self.last_total_profit = 0
            self.is_draining = False
            
            # (No draw_vaults() call here, so the gold lingers on the screen)

    def push_tick(self, color, is_attack):
        # --- PHASE 6: 1k CAP & ANTIMATTER ---
        # A 7x7 tick holds exactly 49,000 GP. Route positive or negative amounts.
        if self.gp_backlog > 0:
            gp_to_attach = min(self.gp_backlog, 49000)
        elif self.gp_backlog < 0:
            gp_to_attach = max(self.gp_backlog, -49000)
        else:
            gp_to_attach = 0
            
        self.gp_backlog -= gp_to_attach

        # INSERT at index 0 (Top-Left) to push older ticks to the right
        self.tick_history.insert(0, {"color": color, "is_attack": is_attack, "gp": gp_to_attach})
        
        # POP from the end (Bottom-Right) when it falls off the conveyor
        if len(self.tick_history) > 217:
            dropped_tick = self.tick_history.pop()
            self.vault_gp += dropped_tick.get("gp", 0)
            
            # Floor the vault at 0 to prevent negative rendering artifacts
            if self.vault_gp < 0: self.vault_gp = 0 
            
            self.draw_vaults() # Force redraw on physical drop
            
        self.draw_ticks()

    # --- DATA PIPELINE ---
    def load_items_and_prices(self):
        snapshot_dir = "price_snapshots"
        
        # O(1) Mtime check: If the directory hasn't changed, skip parsing.
        if os.path.exists(snapshot_dir):
            current_mtime = os.path.getmtime(snapshot_dir)
            if current_mtime == self.last_snapshot_mtime and self.prices:
                return # Fast exit: No new snapshots detected
            
            self.last_snapshot_mtime = current_mtime

        print("[I/O] Parsing items.csv and snapshot directory...") # Verification print
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
        if os.path.exists(snapshot_dir):
            files = glob.glob(os.path.join(snapshot_dir, "prices_*.csv"))
            if files:
                newest_file = max(files, key=os.path.getctime)
                with open(newest_file, 'r', encoding='utf-8') as f:
                    for row in csv.DictReader(f):
                        avg_low = int(row['avgLowPrice']) if row['avgLowPrice'] else 0
                        self.prices[int(row['item_id'])] = avg_low
        
        self.theo_base_kill_val = 0
        for item, info in DROP_TABLE.items():
            self.theo_base_kill_val += self.get_item_value(item) * info['rate'] * info['qty']
        if self.theo_base_kill_val < 5000: self.theo_base_kill_val = 26500

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

                    theo = data.get('theoretical_stats', {})

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
                        'id': data.get('session_id'),
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
                        'theo_ttk': theo.get('ttk', 0), 'theo_dps': theo.get('dps', 0), 'theo_acc': theo.get('accuracy', 0),
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
        
        # --- SWAPPED GGP/S FOR ΔTTK, AND GP/D FOR LtLCK% ---
        headers = f"{'SESS':<6} {'DATE':<11} {'KILLS':>5} {'ΔTTK':>5} {'ASTB':>4} {'MISS':>4} {'EFF%':>4} {'LtLCK':>6}"
        self.draw_text(c, 10, 5, headers, HEADER_COLOR, FONT_BOLD)
        c.create_line(10, 20, 350, 20, fill="gray")
        y = 25
        
        for s in self.sessions[:5]:
            date_str = s['date'].strftime("%m/%d %H:%M") 
            astb_s, miss_s, eff_s = self.calculate_efficiency(s['duration_sec'], s['active_sec'], s['attacks'], s['bank_sec'], s['trips'])
            
            # ΔTTK Math
            if s['kills'] > 0 and s['theo_ttk'] > 0:
                act_ttk = s['active_sec'] / s['kills']
                dt_str = f"{act_ttk - s['theo_ttk']:+.1f}s"
            else: dt_str = "-"
            
            # LtLCK% Math
            gpd = s['gross_gp'] / s['kills'] if s['kills'] > 0 else 0
            ltlck = (gpd / self.theo_base_kill_val) * 100 if getattr(self, 'theo_base_kill_val', 26500) > 0 else 0
            lt_str = f"{ltlck:.0f}%" if ltlck > 0 else "-"
            
            row_txt = f"{s['name']:<6} {date_str:<11} {s['kills']:>5} {dt_str:>5} {astb_s:>4} {miss_s:>4} {eff_s:>4} {lt_str:>6}"
            self.draw_text(c, 10, y, row_txt)
            y += 15

    def draw_stats(self):
        c = self.win_stats.canvas
        c.delete("all")
        now = datetime.now()
        periods =[("24h", 24), ("3d", 72), ("7d", 168), ("30d", 720)]

        # Headers updated for LtLCK and ΔTTK
        headers = f"{'PERIOD':<6} {'SESS':<4} {'HRS':<4} {'R-HR':<4}| {'LtLCK':>5} {'NGP/s':>5} {'ASTB':>4} {'MISS':>4} {'EFF%':>4} | {'KILLS':>5} {'K/HR':>4} {'ΔTTK':>5}"
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
            
            matched_net =[s for s in subset if s['net_profit'] is not None]

            if count > 0:
                astb = (total_bank_sec / total_trips) if total_trips > 0 else 0
                astb_s = f"{astb:.0f}s" if total_trips > 0 else "-"
                upt_pct = (total_act_sec / total_dur_sec * 100) if total_dur_sec > 0 else 0
                
                # LtLCK %
                gpd = total_gross / kills if kills > 0 else 0
                ltlck = (gpd / getattr(self, 'theo_base_kill_val', 26500)) * 100 if getattr(self, 'theo_base_kill_val', 26500) > 0 else 0
                lt_str = f"{ltlck:.0f}%" if ltlck > 0 else "-"
                
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
                    dropped = max(0, max_attacks - total_attacks)
                    miss_per_hr = dropped * (3600.0 / total_atk_sec)
                    atk_pct = min((total_attacks / max_attacks * 100) if max_attacks > 0 else 0, 100.0)
                    eff_pct = (upt_pct / 100.0) * (atk_pct / 100.0) * 100
                    
                    miss_s = f"{miss_per_hr:.0f}"
                    eff_s = f"{eff_pct:.0f}%"
                else: 
                    miss_s, eff_s = "-", "-"
                    
                # ΔTTK Math
                weighted_theo = sum(s.get('theo_ttk', 0) * s['kills'] for s in subset) / kills if kills > 0 else 0
                act_ttk = total_act_sec / kills if kills > 0 else 0
                dt_str = f"{act_ttk - weighted_theo:+.1f}s" if weighted_theo > 0 and kills > 0 else "-"
            else: 
                # If no data, fill everything with dashes to match format
                astb_s, miss_s, eff_s, lt_str, ngps_str, dt_str = "-", "-", "-", "-", "-", "-"

            hrs_logged = total_dur_sec / 3600
            k_hr = (kills / hrs_logged) if hrs_logged > 0 else 0

            # Swapped 'gpd' for 'lt_str' and swapped 'k_r_hr' for 'dt_str'
            row_txt = f"{name:<6} {count:<4} {hrs_logged:<4.1f} {r_hours:<4}| {lt_str:>5} {ngps_str:>5} {astb_s:>4} {miss_s:>4} {eff_s:>4} | {kills:>5} {k_hr:>4.1f} {dt_str:>5}"
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
            cur.execute("SELECT session_id FROM hitsplats ORDER BY id DESC LIMIT 1")
            res = cur.fetchone()
            if not res:
                self.draw_text(c, 10, 10, "No attacks logged yet.", "gray")
                conn.close()
                return
                
            latest_session = res[0]
            cur.execute("SELECT damage FROM hitsplats WHERE session_id = ?", (latest_session,))
            hits = [row[0] for row in cur.fetchall()]
            conn.close()
        except Exception as e:
            self.draw_text(c, 10, 10, f"DB Error: {e}", "red")
            return

        if not hits:
            self.draw_text(c, 10, 10, "No attacks logged in current session.", "gray")
            return

        # Fetch baseline stats from the active session config
        theo_dps, theo_acc, theo_ttk, act_ttk = 0, 0, 0, 0
        
        # Safely find the session in our history that exactly matches the SQLite latest_session ID
        active_session = next((s for s in self.sessions if s.get('id') == latest_session), None)
        
        if active_session: 
            theo_dps = active_session.get('theo_dps', 0)
            theo_acc = active_session.get('theo_acc', 0)
            theo_ttk = active_session.get('theo_ttk', 0)
            
            if active_session['kills'] > 0: 
                act_ttk = active_session['active_sec'] / active_session['kills']

        # --- Calculate Actuals ---
        bolts_fired = len(hits)
        zeroes = sum(1 for h in hits if h == 0)
        total_dmg = sum(hits)
        
        act_acc = ((bolts_fired - zeroes) / bolts_fired) * 100 if bolts_fired > 0 else 0
        act_dps = total_dmg / (bolts_fired * 3.0) if bolts_fired > 0 else 0
        
        d_dps = act_dps - theo_dps if theo_dps > 0 else 0
        d_acc = act_acc - theo_acc if theo_acc > 0 else 0
        d_ttk = act_ttk - theo_ttk if (theo_ttk > 0 and act_ttk > 0) else 0

        # --- Draw Text Headers ---
        self.draw_text(c, 10, 5, "LIVE COMBAT TELEMETRY", HEADER_COLOR, ("Consolas", 10, "bold"))
        c.create_line(10, 20, 340, 20, fill="gray")
        
        def draw_stat(x, label, actual, delta, is_ttk=False):
            self.draw_text(c, x, 25, f"{label}: {actual}", TEXT_COLOR, ("Consolas", 8, "bold"))
            if delta != 0:
                if is_ttk: color = "#00FF00" if delta < 0 else "#FF4444"
                else: color = "#00FF00" if delta > 0 else "#FF4444"
                offset = x + len(f"{label}: {actual}") * 6
                self.draw_text(c, offset, 25, f"({delta:+.1f})", color, ("Consolas", 8, "bold"))
        
        draw_stat(10, "DPS", f"{act_dps:.1f}", d_dps, is_ttk=False)
        draw_stat(120, "Acc", f"{act_acc:.0f}%", d_acc, is_ttk=False)
        draw_stat(230, "TTK", f"{act_ttk:.1f}s", d_ttk, is_ttk=True)

        # --- Histogram Bins ---
        bins =[0] * 7
        for h in hits:
            if h == 0: bins[0] += 1
            elif h <= 10: bins[1] += 1
            elif h <= 20: bins[2] += 1
            elif h <= 30: bins[3] += 1
            elif h <= 40: bins[4] += 1
            elif h <= 50: bins[5] += 1
            else: bins[6] += 1
            
        max_bin = max(bins) if max(bins) > 0 else 1

        bar_w = 28; gap = 12; start_x = 45; base_y = 80; max_h = 35   
        labels =["0", "1-10", "11-20", "21-30", "31-40", "41-50", "51+"]
        colors =["#FFFFFF", "#444444", "#555555", "#666666", "#777777", "#888888", "#999999"]
        
        c.create_line(start_x - 5, base_y, start_x + (bar_w + gap)*7, base_y, fill="#555555") 
        c.create_line(start_x - 5, base_y, start_x - 5, base_y - max_h - 5, fill="#555555")   
        c.create_text(start_x - 10, base_y - max_h, text=str(max_bin), fill="#888888", font=("Consolas", 7), anchor="e")
        c.create_text(start_x - 10, base_y, text="0", fill="#888888", font=("Consolas", 7), anchor="e")
        
        for i in range(7):
            h = (bins[i] / max_bin) * max_h
            x = start_x + i * (bar_w + gap)
            draw_h = h if h > 0 else 1 
            c.create_rectangle(x, base_y - draw_h, x + bar_w, base_y, fill=colors[i], outline="#222222")
            
            pct = (bins[i] / bolts_fired) * 100 if bolts_fired > 0 else 0
            if pct >= 1: pct_text = f"{pct:.0f}%"
            elif pct > 0: pct_text = "<1%"
            else: pct_text = ""
                
            if pct_text:
                if draw_h >= 10:
                    t_y, t_color = base_y - (draw_h / 2), "black" if i == 0 else "white"
                else:
                    t_y, t_color = base_y - draw_h - 5, "white"
                c.create_text(x + (bar_w / 2), t_y, text=pct_text, fill=t_color, font=("Consolas", 7, "bold"), anchor="center")
            
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
        self.draw_ticks()
        self.draw_vaults()

    def draw_ticks(self):
        c = self.win_ticks.canvas
        c.delete("all")
        
        start_x, start_y = 5, 3
        cols, rows = 31, 7
        cell_w, cell_h = 8, 8
        
        for i in range(217):
            r = i // cols
            col = i % cols
            x = start_x + (col * cell_w)
            y = start_y + (r * cell_h)
            
            if i < len(self.tick_history):
                tick = self.tick_history[i]
                
                if self.current_view == "Matrix":
                    # View A: Solid Combat States
                    c.create_rectangle(x, y, x+7, y+7, fill=tick['color'], outline="")
                    if tick['is_attack']:
                        c.create_line(x+6, y, x+6, y+7, fill="white")
                
                elif self.current_view == "Gold":
                    # View B: The Gold Conveyor
                    if tick['color'] == "#333333":
                        # Dropped tick: A literal gap in the conveyor belt
                        c.create_rectangle(x, y, x+7, y+7, fill="black", outline="")
                    else:
                        # Valid empty tick: The dark grey rubber belt
                        c.create_rectangle(x, y, x+7, y+7, fill="#1c1c1c", outline="")
                    
                    # --- PHASE 6: RED/YELLOW RENDERER (OPTIMIZED) ---
                    gp = tick.get("gp", 0)
                    if gp != 0:
                        # 1k = 1 Pixel scale. Cap at 49 pixels per tick.
                        px_count = min(int(abs(gp) // 1000), 49)
                        px_color = "#FFD700" if gp > 0 else "#FF4444"
                        
                        full_rows = px_count // 7
                        remainder = px_count % 7
                        
                        # 1. Draw all full horizontal rows as ONE single rectangle
                        if full_rows > 0:
                            # Bottom-up math
                            c.create_rectangle(x, y + 7 - full_rows, x + 7, y + 7, fill=px_color, outline="")
                            
                        # 2. Draw the partial remainder row on top
                        if remainder > 0:
                            rem_y = y + 7 - full_rows - 1
                            c.create_rectangle(x, rem_y, x + remainder, rem_y + 1, fill=px_color, outline="")
            else:
                c.create_rectangle(x, y, x+7, y+7, fill="#1c1c1c", outline="")

    def draw_vaults(self):
        c = self.win_vaults.canvas
        c.delete("all")
        
        # 1k per pixel rescale. 1 Megapixel = 1,024,000 GP
        total_pixels = int(self.vault_gp // 1000)
        
        # Option A: 4 vaults, single horizontal row
        vault_coords = [(2, 2), (36, 2), (70, 2), (104, 2)]
        
        for idx, (x, y) in enumerate(vault_coords):
            pixels = min(max(total_pixels - idx * 1024, 0), 1024)
            border_color = "#8B6508" if pixels == 1024 else "#222222"
            
            # Outer 34x34 structural border
            c.create_rectangle(x, y, x+34, y+34, fill=border_color, outline="")
            # Inner 32x32 black core
            c.create_rectangle(x+1, y+1, x+33, y+33, fill="black", outline="")
            
            if pixels > 0:
                full_rows = pixels // 32
                remainder = pixels % 32
                
                if full_rows > 0:
                    c.create_rectangle(x+1, y+33-full_rows, x+33, y+33, fill="#FFD700", outline="")
                
                if remainder > 0:
                    rem_y = y + 32 - full_rows
                    # Draw partial row left-to-right
                    c.create_rectangle(x+1, rem_y, x+1+remainder, rem_y+1, fill="#FFD700", outline="")

    def start_auto_refresh(self):
        self.root.after(30000, self.run_auto_refresh)

    def run_auto_refresh(self):
        self.refresh_all()
        self.start_auto_refresh()

    def close_app(self):
        self.root.quit()

if __name__ == "__main__":
    BBDGUI()