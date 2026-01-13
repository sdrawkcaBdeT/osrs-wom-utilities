import customtkinter as ctk
import threading
from flask import Flask, request, jsonify
import datetime
import json
import time
import os
from PIL import Image
from scipy.stats import binom

# --- CONFIG ---
HOST = '127.0.0.1'
PORT = 5000
DATA_DIR = "bbd_data"
IMG_DIR = "item_images"

if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
if not os.path.exists(IMG_DIR): os.makedirs(IMG_DIR)

# --- MASTER DROP TABLE ---
DROP_TABLE = {
    "Dragon bones":       {"rate": 1.0, "qty": 1, "cat": "Guaranteed"},
    "Black dragonhide":       {"rate": 1.0, "qty": 2, "cat": "Guaranteed"},
    
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
    "Black d'hide vambraces":  {"rate": 1/128, "qty": 1, "cat": "Gear"},
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
    "Dragon javelin heads":{"rate": 1/64, "qty": 40, "cat": "Mats"},

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
    
    # Tertiary
    "Ensouled dragon head":{"rate": 1/20, "qty": 1, "cat": "Tertiary"},
    "Clue scroll (hard)":  {"rate": 1/128, "qty": 1, "cat": "Tertiary"},
    "Clue scroll (elite)": {"rate": 1/250, "qty": 1, "cat": "Tertiary"},
    "Draconic visage":     {"rate": 1/10000, "qty": 1, "cat": "Tertiary"},
    "Ancient shard":       {"rate": 1/123, "qty": 1, "cat": "Catacombs"},
    "Dark totem base":     {"rate": 1/185, "qty": 1, "cat": "Catacombs"},
    "Dark Totem Middle":   {"rate": 1/185, "qty": 1, "cat": "Catacombs"},
    "Dark Totem Top":      {"rate": 1/185, "qty": 1, "cat": "Catacombs"}
}

# ID to Name Map (Updated based on your JSON data)
ITEM_MAP = {
    536: "Dragon bones", 1747: "Black dragonhide", 13441: "Anglerfish",
    4087: "Dragon platelegs", 4585: "Dragon plateskirt", 1249: "Dragon spear", 1631: "Uncut dragonstone", 1615: "Uncut dragonstone",
    11388: "Rune hasta", 1247: "Rune spear", 1079: "Rune platelegs", 1163: "Rune full helm",
    811: "Rune dart", 1201: "Rune kite", 1303: "Rune longsword", 2503: "Black d'hide body",
    868: "Rune knife", 805: "Rune thrownaxe", 2491: "Black d'hide vambraces", 1127: "Rune platebody",
    1149: "Dragon med helm", 1305: "Dragon longsword", 1215: "Dragon dagger",
    830: "Rune javelin", 565: "Blood rune", 566: "Soul rune", 560: "Death rune", 563: "Law rune", 892: "Rune arrow",
    11993: "Lava scale", 11992: "Lava scale", 11232: "Dragon dart tip", 452: "Runite ore", 451: "Runite ore",
    11237: "Dragon arrowtips", 19582: "Dragon javelin heads",
    11286: "Draconic visage", 2722: "Clue scroll (hard)", 12073: "Clue scroll (elite)", 13510: "Ensouled dragon head", 13511: "Ensouled dragon head",
    19677: "Ancient shard", 19679: "Dark totem base", 19681: "Dark totem middle", 19683: "Dark totem top",
    995: "Coins",
    987: "Loop half of key", 985: "Tooth half of key", 2366: "Shield left half",
    1623: "Uncut sapphire", 1621: "Uncut emerald", 1619: "Uncut ruby", 1617: "Uncut diamond"
}

# --- FLASK SERVER ---
server = Flask(__name__)
app_instance = None 

@server.route('/event', methods=['POST'])
def handle_event():
    data = request.json
    if app_instance:
        app_instance.process_event(data.get('event'), data.get('payload'))
    return jsonify({"status": "ok"})

def run_server():
    server.run(host=HOST, port=PORT, debug=False, use_reloader=False)

# --- GUI APP ---
class BBDTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BBD Laboratory v10 (All-Time Stats)")
        self.geometry("1400x900")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("green")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # State
        self.is_active = False
        self.start_time = None
        self.kill_count = 0
        self.current_phase = "IDLE"
        self.event_log = []
        self.loot_tracker = {}
        self.session_id = None
        self.img_cache = {}

        self.setup_ui()
        self.update_timer()
        
        threading.Thread(target=run_server, daemon=True).start()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1) 
        self.grid_columnconfigure(1, weight=2) 
        self.grid_columnconfigure(2, weight=3) 
        self.grid_rowconfigure(0, weight=1)

        # === LEFT PANEL (Setup) ===
        self.panel_left = ctk.CTkScrollableFrame(self, label_text="EXPERIMENT SETUP")
        self.panel_left.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        self.entry_exp_name = ctk.CTkEntry(self.panel_left, placeholder_text="Session Name")
        self.entry_exp_name.pack(fill="x", padx=5, pady=5)

        self.cfg_ammo = self.create_dropdown("Ammo Slot", ["Diamond bolts (e)", "Diamond dragon bolts (e)", "Dragonstone bolts (e)", "Pearl dragon bolts (e)", "Emerald dragon bolts (e)", "Opal dragon bolts (e)"])
        self.cfg_weapon = self.create_dropdown("Weapon", ["Dragon hunter crossbow", "Twisted bow", "Dragon crossbow","Rune crossbow"])
        self.cfg_ring = self.create_dropdown("Ring Slot", ["Ring of the gods (i)", "Archers ring (i)", "Venator Ring"])
        self.cfg_back = self.create_dropdown("Back Slot", ["Ranging cape (t)", "Ava's accumulator","Ava's assembler", "Dizana's Quiver"])
        self.cfg_feet = self.create_dropdown("Feet Slot", ["Pegasian boots", "God d'hide boots", "Avernic treads (max)"])
        self.cfg_pray = self.create_dropdown("Prayer Method", ["Rigour", "Eagle Eye", "Deadeye"])
        self.cfg_tele = self.create_dropdown("Teleport Method", ["Xeric's Talisman", "Book of Darkness"])
        self.cfg_bank = self.create_dropdown("Bank Method", ["Ring of dueling", "Crafting cape"])

        ctk.CTkLabel(self.panel_left, text="--- LIVE STATS ---", font=("Arial", 12, "bold"), text_color="gray").pack(pady=(20,5))
        self.lbl_timer = ctk.CTkLabel(self.panel_left, text="00:00:00", font=("Courier New", 24, "bold"))
        self.lbl_timer.pack(pady=5)
        
        self.create_stat_box(self.panel_left, "Current Phase", "IDLE", "lbl_phase")
        self.create_stat_box(self.panel_left, "Dragons Killed", "0", "lbl_kills")
        self.create_stat_box(self.panel_left, "Est. Kills/Hr", "0.0", "lbl_kph")

        # === CENTER PANEL ===
        self.panel_center = ctk.CTkFrame(self)
        self.panel_center.grid(row=0, column=1, sticky="nsew", padx=0, pady=10)

        self.btn_start = ctk.CTkButton(self.panel_center, text="▶ START SESSION", fg_color="green", height=40, command=self.start_session)
        self.btn_start.pack(pady=10, padx=20, fill="x")
        
        self.btn_stop = ctk.CTkButton(self.panel_center, text="⏹ STOP & SAVE", fg_color="red", height=40, state="disabled", command=self.stop_session)
        self.btn_stop.pack(pady=5, padx=20, fill="x")

        self.btn_manual_kill = ctk.CTkButton(self.panel_center, text="MANUAL KILL (+1 Bone/Hide)", 
                                             height=60, font=("Arial", 16, "bold"), 
                                             fg_color="#333", state="disabled", command=self.manual_kill)
        self.btn_manual_kill.pack(pady=20, padx=20, fill="x")

        ctk.CTkLabel(self.panel_center, text="EVENT LOG", font=("Arial", 12, "bold")).pack(anchor="w", padx=20)
        self.log_box = ctk.CTkTextbox(self.panel_center, font=("Consolas", 12))
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # === RIGHT PANEL (Tabs) ===
        self.panel_right_container = ctk.CTkFrame(self)
        self.panel_right_container.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)
        
        # Header with Refresh
        header = ctk.CTkFrame(self.panel_right_container, height=30, fg_color="transparent")
        header.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(header, text="LOOT ANALYSIS", font=("Arial", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="🔄 Refresh Stats", width=120, command=self.refresh_all_tables).pack(side="right")

        # Tabs
        self.tabs = ctk.CTkTabview(self.panel_right_container)
        self.tabs.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.tab_current = self.tabs.add("Current Session")
        self.tab_all_time = self.tabs.add("All-Time")

        # Scrollable Frames inside Tabs
        self.scroll_current = ctk.CTkScrollableFrame(self.tab_current)
        self.scroll_current.pack(fill="both", expand=True)
        
        self.scroll_all_time = ctk.CTkScrollableFrame(self.tab_all_time)
        self.scroll_all_time.pack(fill="both", expand=True)

    # --- UI HELPERS ---
    def create_stat_box(self, parent, label, value, ref_name):
        frame = ctk.CTkFrame(parent, fg_color="#252525")
        frame.pack(fill="x", pady=5, padx=5)
        ctk.CTkLabel(frame, text=label, font=("Arial", 10)).pack(anchor="w", padx=5, pady=(5,0))
        lbl = ctk.CTkLabel(frame, text=value, font=("Arial", 18, "bold"), text_color="#4caf50")
        lbl.pack(anchor="w", padx=5, pady=(0,5))
        setattr(self, ref_name, lbl)

    def create_dropdown(self, label, values):
        frame = ctk.CTkFrame(self.panel_left, fg_color="transparent")
        frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(frame, text=label, font=("Arial", 10)).pack(anchor="w")
        opt = ctk.CTkOptionMenu(frame, values=values)
        opt.pack(fill="x")
        return opt

    def load_image(self, item_name):
        if item_name in self.img_cache: return self.img_cache[item_name]
        filename = item_name.lower().replace(" ", "_").replace("'", "").replace("-", "_") + ".png"
        path = os.path.join(IMG_DIR, filename)
        if os.path.exists(path):
            try:
                img = Image.open(path)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(32, 32))
                self.img_cache[item_name] = ctk_img
                return ctk_img
            except: pass
        return None

    # --- LOGIC ---
    def start_session(self):
        self.is_active = True
        self.start_time = time.time()
        self.kill_count = 0
        self.loot_tracker = {}
        self.event_log = []
        self.session_id = f"session_{int(self.start_time)}"
        
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_manual_kill.configure(state="normal", fg_color="#d32f2f")
        self.log_box.delete("1.0", "end")
        
        self.log_event("session_start", "Session Started")
        self.refresh_all_tables()

    def stop_session(self):
        if not self.is_active: return
        self.is_active = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_manual_kill.configure(state="disabled", fg_color="#333")
        
        self.log_event("session_end", "Session Ended")
        self.save_data()
        self.refresh_all_tables()

    def on_close(self):
        if self.is_active: self.stop_session()
        self.destroy()

    def get_iso_time(self):
        return datetime.datetime.now().isoformat()

    def log_event(self, type_, val):
        ts_iso = self.get_iso_time()
        ts_display = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{ts_display}] {val}\n")
        self.log_box.see("end")
        self.event_log.append({"timestamp": ts_iso, "type": type_, "value": val})

    def save_data(self):
        if not self.session_id: return
        
        config_data = {
            "experiment_name": self.entry_exp_name.get(),
            "weapon": self.cfg_weapon.get(),
            "ammo": self.cfg_ammo.get(),
            "ring": self.cfg_ring.get(),
            "back": self.cfg_back.get(),
            "feet": self.cfg_feet.get(),
            "prayer": self.cfg_pray.get(),
            "tele": self.cfg_tele.get(),
            "bank": self.cfg_bank.get()
        }

        data = {
            "session_id": self.session_id,
            "start_time": datetime.datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": self.get_iso_time(),
            "total_kills": self.kill_count,
            "config": config_data,
            "loot_summary": self.loot_tracker,
            "event_timeline": self.event_log
        }
        
        with open(f"{DATA_DIR}/{self.session_id}.json", 'w') as f:
            json.dump(data, f, indent=4)
        self.log_event("system", "Data Saved Successfully.")

    def update_timer(self):
        if self.is_active and self.start_time:
            elapsed = time.time() - self.start_time
            m, s = divmod(elapsed, 60)
            h, m = divmod(m, 60)
            self.lbl_timer.configure(text=f"{int(h):02d}:{int(m):02d}:{int(s):02d}")
            if elapsed > 0:
                self.lbl_kph.configure(text=f"{(self.kill_count / (elapsed/3600)):.2f}")
        self.after(1000, self.update_timer)

    def add_loot(self, item_name, qty):
        self.loot_tracker[item_name] = self.loot_tracker.get(item_name, 0) + qty

    # --- AGGREGATION & RENDERING ---
    
    def refresh_all_tables(self):
        # 1. Render Current Session
        self.render_table(self.scroll_current, self.loot_tracker, self.kill_count, show_all=False)
        
        # 2. Calculate All-Time Stats
        all_time_kills, all_time_loot = self.calculate_all_time_stats()
        
        # 3. Render All-Time
        self.render_table(self.scroll_all_time, all_time_loot, all_time_kills, show_all=True)

    def calculate_all_time_stats(self):
        total_kills = 0
        total_loot = {}

        # 1. Load from Disk
        for filename in os.listdir(DATA_DIR):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(DATA_DIR, filename), 'r') as f:
                        data = json.load(f)
                        total_kills += data.get("total_kills", 0)
                        
                        # Merge loot
                        session_loot = data.get("loot_summary", {})
                        for item, qty in session_loot.items():
                            total_loot[item] = total_loot.get(item, 0) + qty
                except:
                    pass
        
        # 2. Add Current Session (Live Data)
        if self.is_active:
            # We don't double count if session is saved, but session ID check is complex.
            # Simpler: If active, exclude current session ID from disk load? 
            # Actually, `save_data` overwrites the file. 
            # So if we load from disk, we might load the current session if it was saved.
            # BUT, we only save on STOP. So disk data is usually old.
            # Let's assume disk = old, memory = new.
            # NOTE: If you click "Stop & Save", it writes to disk. 
            # If we then calculate, we might double count if we aren't careful.
            # Fix: Only add self variables if session is NOT in the file list yet.
            if f"{self.session_id}.json" not in os.listdir(DATA_DIR):
                total_kills += self.kill_count
                for item, qty in self.loot_tracker.items():
                    total_loot[item] = total_loot.get(item, 0) + qty

        return total_kills, total_loot

    def render_table(self, parent_frame, loot_data, kills, show_all=False):
        for widget in parent_frame.winfo_children(): widget.destroy()
        
        headers = ["", "Item", "Actual", "Expected", "Luck"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(parent_frame, text=h, font=("Arial", 12, "bold")).grid(row=0, column=i, padx=5, pady=5, sticky="w")

        # Determine items to show
        if show_all:
            # Show everything in DROP_TABLE
            items_to_show = list(DROP_TABLE.keys())
        else:
            # Only show what we have found (plus Uniques/Guaranteed for context)
            items_to_show = list(set(loot_data.keys()) | {k for k,v in DROP_TABLE.items() if v['cat'] in ['Guaranteed', 'Unique']})

        # Sort
        sorted_items = sorted(items_to_show, key=lambda x: (DROP_TABLE.get(x, {}).get("cat", "Z") != "Unique", x))

        row_idx = 1
        for name in sorted_items:
            actual = loot_data.get(name, 0)
            drop_info = DROP_TABLE.get(name, {})
            rate = drop_info.get("rate", 0)
            avg_qty = drop_info.get("qty", 1)
            
            # Skip if count is 0 and we are in "Current Session" mode (unless unique/guaranteed)
            if not show_all and actual == 0 and drop_info.get("cat") not in ["Unique", "Guaranteed"]: 
                continue

            expected = kills * rate * avg_qty
            
            luck_text = "-"
            luck_color = "gray"
            
            if kills > 0 and rate > 0 and rate < 1.0:
                events_actual = actual / avg_qty
                cdf = binom.cdf(int(events_actual), kills, rate)
                percentile = cdf * 100
                
                if actual > expected:
                    luck_text = f"Top {100-percentile:.1f}%"
                    luck_color = "#4caf50"
                else:
                    luck_text = f"Bottom {percentile:.1f}%"
                    luck_color = "#d32f2f"
            elif rate == 1.0:
                luck_text = "100%"
                luck_color = "#4caf50"

            # Dim text if 0 found in All-Time view
            text_color = "white" if actual > 0 else "gray"

            img = self.load_image(name)
            if img: ctk.CTkLabel(parent_frame, text="", image=img).grid(row=row_idx, column=0, padx=2, pady=2)
            else: ctk.CTkLabel(parent_frame, text="?").grid(row=row_idx, column=0, padx=2, pady=2)

            ctk.CTkLabel(parent_frame, text=name, anchor="w", text_color=text_color).grid(row=row_idx, column=1, sticky="w", padx=5)
            ctk.CTkLabel(parent_frame, text=str(actual), text_color=text_color).grid(row=row_idx, column=2, padx=5)
            ctk.CTkLabel(parent_frame, text=f"{expected:.1f}", text_color=text_color).grid(row=row_idx, column=3, padx=5)
            ctk.CTkLabel(parent_frame, text=luck_text, text_color=luck_color).grid(row=row_idx, column=4, padx=5)
            row_idx += 1

    def manual_kill(self):
        self.process_kill(manual=True)

    def process_kill(self, loot_items=None, manual=False):
        self.kill_count += 1
        self.lbl_kills.configure(text=str(self.kill_count))
        source = "Manual" if manual else "Auto"
        
        self.log_event("kill", f"Kill Confirmed ({source})")
        
        # Guaranteed
        self.add_loot("Dragon bones", 1)
        self.add_loot("Black dragonhide", 2)
        
        # Variable
        if loot_items:
            for item in loot_items:
                i_id = item.get('id')
                qty = item.get('qty')
                name = ITEM_MAP.get(i_id, f"Item {i_id}")
                
                if name not in ["Dragon bones", "Black dragonhide"]:
                    self.add_loot(name, qty)
                    self.log_event("loot", f"-> {qty}x {name}")
        
        self.refresh_all_tables()

    def process_event(self, event_type, payload):
        if not self.is_active: return

        if event_type == "phase_change":
            in_zone = payload.get("in_zone")
            phase = "KILLING" if in_zone else "AWAY"
            if phase != self.current_phase:
                self.current_phase = phase
                self.lbl_phase.configure(text=phase, text_color="#d32f2f" if in_zone else "gray")
                self.log_event("phase", f"Phase Changed: {phase}")

        elif event_type == "loot_event":
            self.process_kill(loot_items=payload.get("items", []))

if __name__ == "__main__":
    app = BBDTrackerApp()
    app_instance = app
    app.mainloop()