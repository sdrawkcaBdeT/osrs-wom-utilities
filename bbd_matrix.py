import tkinter as tk
import requests
import time
import threading
import queue
import keyboard

# --- CONFIG ---
BACKGROUND_COLOR = "black"
WINDOW_OPACITY = 0.85
MAIN_W, MAIN_H = 2560, 1440
SIDE_W, SIDE_H = 1080, 1920
SIDE_ORIGIN_X = MAIN_W   
SIDE_ORIGIN_Y = 0

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

class BBDMatrix:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw() 

        # --- MATRIX WINDOWS ---
        self.win_ticks = OverlayWindow(self.root, 258, 62, SIDE_ORIGIN_X + 256, SIDE_ORIGIN_Y + 218, "Dual View Matrix")
        self.win_vaults = OverlayWindow(self.root, 139, 39, SIDE_ORIGIN_X + 379, SIDE_ORIGIN_Y + 53, "Vault Cluster")

        self.current_view = "Matrix"
        self.tick_history = []
        self.last_tick_processed = None
        self.cooldown_remaining = 0
        
        # --- PHASE 4/5/6 PIPELINE ---
        self.gp_backlog = 0
        self.vault_gp = 0
        self.last_total_profit = 0
        self.is_draining = False
        self.drain_index = 0
        self.was_session_running = False  
        
        self.draw_ticks()
        self.draw_vaults()

        # Start HTTP Polling Daemon
        self.http_queue = queue.Queue()
        threading.Thread(target=self.http_polling_daemon, daemon=True).start()

        keyboard.add_hotkey("ctrl+l", self.toggle_view)
        keyboard.add_hotkey("ctrl+q", self.close_app)

        self.start_tick_loop()
        self.root.mainloop()

    def start_tick_loop(self):
        self.root.after(50, self.run_tick_loop)

    def toggle_view(self):
        if self.current_view == "Matrix":
            self.current_view = "Gold"
        else:
            self.current_view = "Matrix"
        self.draw_ticks()

    def http_polling_daemon(self):
        while True:
            try:
                resp = requests.get("http://127.0.0.1:5000/hp", timeout=0.1)
                self.http_queue.put(resp.json())
            except Exception:
                pass
            time.sleep(0.05) 

    def run_tick_loop(self):
        data = None
        try:
            while True:
                data = self.http_queue.get_nowait()
        except queue.Empty:
            pass

        if data:
            is_running = data.get("session_running", False)
            if is_running and not self.was_session_running:
                self.vault_gp = 0
                self.gp_backlog = 0 
                self.last_total_profit = data.get("total_profit", 0) 
                self.tick_history.clear() 
                self.draw_ticks()
                self.draw_vaults()
            self.was_session_running = is_running

            if data.get("drain_triggered") and not self.is_draining:
                self.start_drain_sequence()
                
            if not self.is_draining:
                total_profit = data.get("total_profit", 0)
                if total_profit != self.last_total_profit:
                    self.gp_backlog += (total_profit - self.last_total_profit)
                    self.last_total_profit = total_profit

                udp_stream = data.get("udp_stream", [])
                server_phase = data.get("phase", "IDLE")

                for udp_payload in udp_stream:
                    tick = udp_payload.get("tick")
                    state = udp_payload.get("state", "idle")

                    if tick is not None:
                        if self.last_tick_processed is None:
                            self.last_tick_processed = tick - 1

                        if tick > self.last_tick_processed:
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
        self.drain_index = len(self.tick_history) - 1 
        self.run_drain_sweep()

    def run_drain_sweep(self):
        if self.drain_index >= 0:
            tick = self.tick_history[self.drain_index]
            gp = tick.get("gp", 0)
            if gp > 0:
                self.vault_gp += gp
                tick["gp"] = 0 
                self.draw_ticks()
                self.draw_vaults()
            
            self.drain_index -= 1
            self.root.after(20, self.run_drain_sweep) 
        else:
            if self.gp_backlog > 0:
                self.vault_gp += self.gp_backlog
                
            final_gp = self.vault_gp
            
            try:
                payload = {"event": "drain_complete", "payload": {"final_vault_gp": final_gp}}
                requests.post("http://127.0.0.1:5000/event", json=payload, timeout=0.1)
            except Exception:
                pass
                
            self.gp_backlog = 0
            self.last_total_profit = 0
            self.is_draining = False

    def push_tick(self, color, is_attack):
        if self.gp_backlog > 0:
            gp_to_attach = min(self.gp_backlog, 49000)
        elif self.gp_backlog < 0:
            gp_to_attach = max(self.gp_backlog, -49000)
        else:
            gp_to_attach = 0
            
        self.gp_backlog -= gp_to_attach
        self.tick_history.insert(0, {"color": color, "is_attack": is_attack, "gp": gp_to_attach})
        
        if len(self.tick_history) > 217:
            dropped_tick = self.tick_history.pop()
            self.vault_gp += dropped_tick.get("gp", 0)
            
            if self.vault_gp < 0: self.vault_gp = 0 
            self.draw_vaults() 
            
        self.draw_ticks()

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
                    c.create_rectangle(x, y, x+7, y+7, fill=tick['color'], outline="")
                    if tick['is_attack']:
                        c.create_line(x+6, y, x+6, y+7, fill="white")
                
                elif self.current_view == "Gold":
                    if tick['color'] == "#333333":
                        c.create_rectangle(x, y, x+7, y+7, fill="black", outline="")
                    else:
                        c.create_rectangle(x, y, x+7, y+7, fill="#1c1c1c", outline="")
                    
                    gp = tick.get("gp", 0)
                    if gp != 0:
                        px_count = min(int(abs(gp) // 1000), 49)
                        px_color = "#FFD700" if gp > 0 else "#FF4444"
                        
                        full_rows = px_count // 7
                        remainder = px_count % 7
                        
                        if full_rows > 0:
                            c.create_rectangle(x, y + 7 - full_rows, x + 7, y + 7, fill=px_color, outline="")
                            
                        if remainder > 0:
                            rem_y = y + 7 - full_rows - 1
                            c.create_rectangle(x, rem_y, x + remainder, rem_y + 1, fill=px_color, outline="")
            else:
                c.create_rectangle(x, y, x+7, y+7, fill="#1c1c1c", outline="")

    def draw_vaults(self):
        c = self.win_vaults.canvas
        c.delete("all")
        
        total_pixels = int(self.vault_gp // 1000)
        vault_coords = [(2, 2), (36, 2), (70, 2), (104, 2)]
        
        for idx, (x, y) in enumerate(vault_coords):
            pixels = min(max(total_pixels - idx * 1024, 0), 1024)
            border_color = "#8B6508" if pixels == 1024 else "#222222"
            
            c.create_rectangle(x, y, x+34, y+34, fill=border_color, outline="")
            c.create_rectangle(x+1, y+1, x+33, y+33, fill="black", outline="")
            
            if pixels > 0:
                full_rows = pixels // 32
                remainder = pixels % 32
                
                if full_rows > 0:
                    c.create_rectangle(x+1, y+33-full_rows, x+33, y+33, fill="#FFD700", outline="")
                
                if remainder > 0:
                    rem_y = y + 32 - full_rows
                    c.create_rectangle(x+1, rem_y, x+1+remainder, rem_y+1, fill="#FFD700", outline="")

    def close_app(self):
        self.root.quit()

if __name__ == "__main__":
    BBDMatrix()