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
# Rate = Probability of drop per kill.
# Qty = Average quantity per drop.
DROP_TABLE = {
    "Dragon Bones":       {"rate": 1.0, "qty": 1, "cat": "Guaranteed"},
    "Black D-hide":       {"rate": 1.0, "qty": 2, "cat": "Guaranteed"},
    
    # Uniques (1/512)
    "Dragon Platelegs":   {"rate": 1/512, "qty": 1, "cat": "Unique"},
    "Dragon Plateskirt":  {"rate": 1/512, "qty": 1, "cat": "Unique"},
    "Dragon Spear":       {"rate": 1/512, "qty": 1, "cat": "Unique"}, 
    "Uncut Dragonstone":  {"rate": 1/512, "qty": 1, "cat": "Unique"},
    
    # Weapons/Armor
    "Rune Hasta":         {"rate": 1/12.8, "qty": 1, "cat": "Gear"},
    "Rune Spear":         {"rate": 1/12.8, "qty": 1, "cat": "Gear"},
    "Rune Platelegs":     {"rate": 1/18.29, "qty": 1, "cat": "Gear"},
    "Rune Full Helm":     {"rate": 1/21.33, "qty": 2, "cat": "Gear"}, # Note: Drops 2
    "Rune Dart":          {"rate": 1/25.6, "qty": 20, "cat": "Gear"},
    "Rune Longsword":     {"rate": 1/25.6, "qty": 1, "cat": "Gear"},
    "Black D-hide Body":  {"rate": 1/64, "qty": 1, "cat": "Gear"},
    "Rune Knife":         {"rate": 1/64, "qty": 25, "cat": "Gear"},
    "Rune Thrownaxe":     {"rate": 1/64, "qty": 30, "cat": "Gear"},
    "Black D-hide Vamb":  {"rate": 1/128, "qty": 1, "cat": "Gear"},
    "Rune Platebody":     {"rate": 1/128, "qty": 1, "cat": "Gear"},
    "Dragon Med Helm":    {"rate": 1/128, "qty": 1, "cat": "Gear"},
    "Dragon Longsword":   {"rate": 1/128, "qty": 1, "cat": "Gear"},
    "Dragon Dagger":      {"rate": 1/128, "qty": 1, "cat": "Gear"},

    # Runes/Ammo
    "Rune Javelin":       {"rate": 1/16, "qty": 50, "cat": "Ammo"},
    "Blood Rune":         {"rate": 1/16, "qty": 50, "cat": "Ammo"},
    "Soul Rune":          {"rate": 1/16, "qty": 50, "cat": "Ammo"},
    "Death Rune":         {"rate": 1/18.29, "qty": 75, "cat": "Ammo"},
    "Law Rune":           {"rate": 1/18.29, "qty": 75, "cat": "Ammo"},
    "Rune Arrow":         {"rate": 1/18.29, "qty": 75, "cat": "Ammo"},

    # Materials
    "Lava Scale":         {"rate": 1/32, "qty": 5, "cat": "Mats"},
    "Dragon Dart Tip":    {"rate": 1/42.67, "qty": 40, "cat": "Mats"},
    "Runite Ore":         {"rate": 1/64, "qty": 3, "cat": "Mats"},
    "Dragon Arrowtips":   {"rate": 1/64, "qty": 40, "cat": "Mats"},
    "Dragon Javelin Heads":{"rate": 1/64, "qty": 40, "cat": "Mats"},

    # RDT / Rare
    "Loop Half of Key":    {"rate": 1/378, "qty": 1, "cat": "RDT"},
    "Tooth Half of Key":   {"rate": 1/378, "qty": 1, "cat": "RDT"},
    "Shield Left Half":    {"rate": 1/15738, "qty": 1, "cat": "RDT"},
    "Uncut Sapphire":      {"rate": 1/154, "qty": 1, "cat": "RDT"},
    "Uncut Emerald":       {"rate": 1/309, "qty": 1, "cat": "RDT"},
    "Uncut Ruby":          {"rate": 1/618, "qty": 1, "cat": "RDT"},
    "Uncut Diamond":       {"rate": 1/2473, "qty": 1, "cat": "RDT"},
    
    # Tertiary
    "Ensouled Dragon Head":{"rate": 1/20, "qty": 1, "cat": "Tertiary"},
    "Clue Scroll (hard)":  {"rate": 1/128, "qty": 1, "cat": "Tertiary"},
    "Clue Scroll (elite)": {"rate": 1/250, "qty": 1, "cat": "Tertiary"},
    "Draconic Visage":     {"rate": 1/10000, "qty": 1, "cat": "Tertiary"},
    "Ancient Shard":       {"rate": 1/123, "qty": 1, "cat": "Catacombs"},
    "Dark Totem Base":     {"rate": 1/185, "qty": 1, "cat": "Catacombs"},
    "Dark Totem Middle":   {"rate": 1/185, "qty": 1, "cat": "Catacombs"},
    "Dark Totem Top":      {"rate": 1/185, "qty": 1, "cat": "Catacombs"}
}

# ID to Name Map
ITEM_MAP = {
    536: "Dragon Bones", 1747: "Black D-hide",
    4087: "Dragon Platelegs", 4585: "Dragon Plateskirt", 1249: "Dragon Spear", 1615: "Uncut Dragonstone",
    11388: "Rune Hasta", 1247: "Rune Spear", 1079: "Rune Platelegs", 1163: "Rune Full Helm",
    811: "Rune Dart", 1201: "Rune Kite", 1303: "Rune Longsword", 2503: "Black D-hide Body",
    868: "Rune Knife", 805: "Rune Thrownaxe", 2491: "Black D-hide Vamb", 1127: "Rune Platebody",
    1149: "Dragon Med Helm", 1305: "Dragon Longsword", 1215: "Dragon Dagger",
    830: "Rune Javelin", 565: "Blood Rune", 566: "Soul Rune", 560: "Death Rune", 563: "Law Rune", 892: "Rune Arrow",
    11992: "Lava Scale", 11232: "Dragon Dart Tip", 451: "Runite Ore", 11237: "Dragon Arrowtips", 19582: "Dragon Javelin Heads",
    11286: "Draconic Visage", 2722: "Clue Scroll (hard)", 12073: "Clue Scroll (elite)", 13421: "Ensouled Dragon Head",
    19677: "Ancient Shard", 19679: "Dark Totem Base", 19681: "Dark Totem Middle", 19683: "Dark Totem Top",
    995: "Coins",
    987: "Loop Half of Key", 985: "Tooth Half of Key", 2366: "Shield Left Half",
    1623: "Uncut Sapphire", 1621: "Uncut Emerald", 1619: "Uncut Ruby", 1617: "Uncut Diamond"
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
        self.title("BBD Laboratory v9 (Granular Data)")
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

        # Full Config Fields
        self.cfg_ammo = self.create_dropdown("Ammo Slot", ["Diamond bolts (e)", "Ruby bolts (e)", "Dragon arrows", "Rune arrows", "Amethyst Broad Bolts"])
        self.cfg_weapon = self.create_dropdown("Weapon", ["Dragon Hunter Crossbow", "Twisted Bow", "Rune Crossbow", "Bow of Faerdhinen"])
        self.cfg_ring = self.create_dropdown("Ring Slot", ["Ring of the gods (i)", "Archers ring (i)", "Venator Ring"])
        self.cfg_back = self.create_dropdown("Back Slot", ["Ranging cape (t)", "Ava's assembler", "Dizana's Quiver"])
        self.cfg_feet = self.create_dropdown("Feet Slot", ["Pegasian boots", "God D'hide Boots", "Shayzien Boots"])
        self.cfg_pray = self.create_dropdown("Prayer Method", ["Rigour", "Eagle Eye", "Deadeye"])
        self.cfg_tele = self.create_dropdown("Teleport Method", ["Xeric's Talisman", "Book of Darkness", "House Tab"])
        self.cfg_bank = self.create_dropdown("Bank Method", ["Ring of dueling", "Crafting cape", "Farming Cape"])

        # Stats Box (Moved below config)
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

        # === RIGHT PANEL ===
        self.panel_right_container = ctk.CTkFrame(self)
        self.panel_right_container.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)
        
        header = ctk.CTkFrame(self.panel_right_container, height=30, fg_color="transparent")
        header.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(header, text="LOOT ANALYSIS", font=("Arial", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="🔄 Refresh", width=80, command=self.refresh_loot_table).pack(side="right")

        self.loot_scroll = ctk.CTkScrollableFrame(self.panel_right_container)
        self.loot_scroll.pack(fill="both", expand=True)

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
        self.refresh_loot_table()

    def stop_session(self):
        if not self.is_active: return
        self.is_active = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_manual_kill.configure(state="disabled", fg_color="#333")
        
        self.log_event("session_end", "Session Ended")
        self.save_data()

    def on_close(self):
        if self.is_active: self.stop_session()
        self.destroy()

    def get_iso_time(self):
        return datetime.datetime.now().isoformat()

    def log_event(self, type_, val):
        ts_iso = self.get_iso_time()
        ts_display = datetime.datetime.now().strftime("%H:%M:%S")
        
        # UI Log
        self.log_box.insert("end", f"[{ts_display}] {val}\n")
        self.log_box.see("end")
        
        # Data Log
        self.event_log.append({
            "timestamp": ts_iso,
            "type": type_,
            "value": val
        })

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

    def refresh_loot_table(self):
        for widget in self.loot_scroll.winfo_children(): widget.destroy()
        
        headers = ["", "Item", "Actual", "Expected", "Luck"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.loot_scroll, text=h, font=("Arial", 12, "bold")).grid(row=0, column=i, padx=5, pady=5, sticky="w")

        all_items = set(DROP_TABLE.keys()) | set(self.loot_tracker.keys())
        sorted_items = sorted(list(all_items), key=lambda x: (DROP_TABLE.get(x, {}).get("cat", "Z") != "Unique", x))

        row_idx = 1
        for name in sorted_items:
            actual = self.loot_tracker.get(name, 0)
            drop_info = DROP_TABLE.get(name, {})
            rate = drop_info.get("rate", 0)
            avg_qty = drop_info.get("qty", 1) # UPDATED MATH
            
            if actual == 0 and drop_info.get("cat") not in ["Unique", "Guaranteed"]: continue

            expected = self.kill_count * rate * avg_qty # UPDATED MATH
            
            luck_text = "-"
            luck_color = "gray"
            if self.kill_count > 0 and rate > 0 and rate < 1.0:
                # For Luck, we care about "Events" (Drops), not "Quantity" (Items)
                # If avg drop is 20 darts, getting 20 darts is 1 event.
                # Approx events = Actual / Avg_Qty
                events_actual = actual / avg_qty
                cdf = binom.cdf(int(events_actual), self.kill_count, rate)
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

            img = self.load_image(name)
            if img: ctk.CTkLabel(self.loot_scroll, text="", image=img).grid(row=row_idx, column=0, padx=2, pady=2)
            else: ctk.CTkLabel(self.loot_scroll, text="?").grid(row=row_idx, column=0, padx=2, pady=2)

            ctk.CTkLabel(self.loot_scroll, text=name, anchor="w").grid(row=row_idx, column=1, sticky="w", padx=5)
            ctk.CTkLabel(self.loot_scroll, text=str(actual)).grid(row=row_idx, column=2, padx=5)
            ctk.CTkLabel(self.loot_scroll, text=f"{expected:.1f}").grid(row=row_idx, column=3, padx=5)
            ctk.CTkLabel(self.loot_scroll, text=luck_text, text_color=luck_color).grid(row=row_idx, column=4, padx=5)
            row_idx += 1

    def manual_kill(self):
        self.process_kill(manual=True)

    def process_kill(self, loot_items=None, manual=False):
        self.kill_count += 1
        self.lbl_kills.configure(text=str(self.kill_count))
        source = "Manual" if manual else "Auto"
        
        # Log Kill Event (Granular)
        self.log_event("kill", f"Kill Confirmed ({source})")
        
        # Guaranteed
        self.add_loot("Dragon Bones", 1)
        self.add_loot("Black D-hide", 2)
        
        # Variable
        if loot_items:
            for item in loot_items:
                i_id = item.get('id')
                qty = item.get('qty')
                name = ITEM_MAP.get(i_id, f"Item {i_id}")
                
                if name not in ["Dragon Bones", "Black D-hide"]:
                    self.add_loot(name, qty)
                    self.log_event("loot", f"-> {qty}x {name}")
        
        self.refresh_loot_table()

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