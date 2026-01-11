import customtkinter as ctk
import sqlite3
import datetime
from dateutil import parser
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# --- CONFIGURATION ---
DB_NAME = "time_tracker.db"
GOAL_HOURS_PER_DAY = 1.0

class EditorWindow(ctk.CTkToplevel):
    """
    A spreadsheet-style popup window to edit database records directly.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Edit Shift Logs")
        self.geometry("650x500")
        self.parent = parent
        
        # UI Container
        self.scroll = ctk.CTkScrollableFrame(self, label_text="Recent Shifts (YYYY-MM-DD HH:MM:SS)")
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Save Button
        self.btn_save = ctk.CTkButton(self, text="Save Changes", command=self.save_changes, fg_color="green")
        self.btn_save.pack(pady=10)

        self.rows = [] # Will hold references to the entry widgets
        self.load_data()

    def load_data(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        # Fetch last 50 entries
        c.execute("SELECT id, start_timestamp, end_timestamp, type FROM shifts ORDER BY start_timestamp DESC LIMIT 50")
        data = c.fetchall()
        conn.close()

        # Headers
        headers = ["Start Time", "End Time", "Type"]
        for i, h in enumerate(headers):
            l = ctk.CTkLabel(self.scroll, text=h, font=("Arial", 12, "bold"))
            l.grid(row=0, column=i+1, padx=5, pady=5)

        # Build Grid
        for idx, (row_id, start, end, type_) in enumerate(data):
            r = idx + 1
            
            # Hidden ID
            lbl_id = ctk.CTkLabel(self.scroll, text=str(row_id), width=30)
            lbl_id.grid(row=r, column=0)

            # Start Entry
            ent_start = ctk.CTkEntry(self.scroll, width=180)
            ent_start.insert(0, start)
            ent_start.grid(row=r, column=1, padx=2, pady=2)

            # End Entry
            ent_end = ctk.CTkEntry(self.scroll, width=180)
            ent_end.insert(0, str(end) if end else "") # Handle active shifts
            ent_end.grid(row=r, column=2, padx=2, pady=2)

            # Type Entry
            ent_type = ctk.CTkEntry(self.scroll, width=80)
            ent_type.insert(0, type_)
            ent_type.grid(row=r, column=3, padx=2, pady=2)

            self.rows.append((row_id, ent_start, ent_end, ent_type))

    def save_changes(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            for row_id, e_start, e_end, e_type in self.rows:
                s_txt = e_start.get()
                e_txt = e_end.get()
                t_txt = e_type.get()

                # Basic validation: ensure it parses as date if not empty
                # We use dateutil.parser for flexibility, then format back to ISO
                if s_txt:
                    s_dt = parser.parse(s_txt)
                    s_txt = str(s_dt)
                
                if e_txt and e_txt != "None":
                    e_dt = parser.parse(e_txt)
                    e_txt = str(e_dt)
                else:
                    e_txt = None # Keep as None in DB

                c.execute("UPDATE shifts SET start_timestamp=?, end_timestamp=?, type=? WHERE id=?",
                          (s_txt, e_txt, t_txt, row_id))
            
            conn.commit()
            print("Database updated.")
            self.destroy() # Close window
        except Exception as e:
            print(f"Error saving: {e}")
            # In a real app, you'd show a popup error here
        finally:
            conn.close()


class TimeTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Series Time Tracker")
        self.geometry("400x550")
        
        self.current_session_id = None
        self.is_working = False
        self.on_break = False
        self.start_time = None
        
        self.setup_db()
        self.setup_ui()
        self.update_clock()

    def setup_db(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS shifts
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      session_group_id TEXT, 
                      start_timestamp DATETIME,
                      end_timestamp DATETIME,
                      type TEXT)''')
        conn.commit()
        conn.close()

    def setup_ui(self):
        # 1. Header & Timer
        self.lbl_status = ctk.CTkLabel(self, text="Ready", font=("Arial", 16))
        self.lbl_status.pack(pady=(20, 5))

        self.lbl_timer = ctk.CTkLabel(self, text="00:00:00", font=("Roboto Mono", 40, "bold"))
        self.lbl_timer.pack(pady=10)

        # 2. Controls
        self.btn_main = ctk.CTkButton(self, text="CLOCK IN", command=self.toggle_work, height=50, fg_color="green")
        self.btn_main.pack(pady=10, padx=20, fill="x")

        self.btn_break = ctk.CTkButton(self, text="TAKE BREAK", command=self.toggle_break, state="disabled", height=40, fg_color="#D4AF37")
        self.btn_break.pack(pady=5, padx=20, fill="x")

        # 3. Tools
        ctk.CTkLabel(self, text="--- Tools ---").pack(pady=15)
        
        self.btn_report = ctk.CTkButton(self, text="Generate Visual Report", command=self.generate_report)
        self.btn_report.pack(pady=5)

        self.btn_edit = ctk.CTkButton(self, text="Edit Logs (Spreadsheet)", command=self.open_editor, fg_color="#555555")
        self.btn_edit.pack(pady=5)

    def open_editor(self):
        EditorWindow(self)

    def get_current_duration(self):
        if self.start_time:
            delta = datetime.datetime.now() - self.start_time
            return str(delta).split('.')[0] 
        return "00:00:00"

    def update_clock(self):
        if self.is_working and not self.on_break:
            self.lbl_timer.configure(text=self.get_current_duration())
        self.after(1000, self.update_clock)

    def toggle_work(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.datetime.now()

        if not self.is_working:
            # START
            self.is_working = True
            self.start_time = now
            self.current_session_id = f"SESSION_{int(now.timestamp())}"
            c.execute("INSERT INTO shifts (session_group_id, start_timestamp, type) VALUES (?, ?, ?)",
                      (self.current_session_id, now, 'WORK'))
            self.btn_main.configure(text="END SHIFT", fg_color="red")
            self.btn_break.configure(state="normal")
            self.lbl_status.configure(text="Working...", text_color="green")
        else:
            # STOP
            c.execute("UPDATE shifts SET end_timestamp = ? WHERE session_group_id = ? AND end_timestamp IS NULL",
                      (now, self.current_session_id))
            self.is_working = False
            self.on_break = False
            self.start_time = None
            self.btn_main.configure(text="CLOCK IN", fg_color="green")
            self.btn_break.configure(state="disabled", text="TAKE BREAK")
            self.lbl_status.configure(text="Saved.", text_color="white")
            self.lbl_timer.configure(text="00:00:00")

        conn.commit()
        conn.close()

    def toggle_break(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.datetime.now()

        if not self.on_break:
            # START BREAK
            c.execute("UPDATE shifts SET end_timestamp = ? WHERE session_group_id = ? AND end_timestamp IS NULL",
                      (now, self.current_session_id))
            c.execute("INSERT INTO shifts (session_group_id, start_timestamp, type) VALUES (?, ?, ?)",
                      (self.current_session_id, now, 'BREAK'))
            self.on_break = True
            self.lbl_status.configure(text="On Break", text_color="yellow")
            self.btn_break.configure(text="RESUME WORK")
        else:
            # END BREAK
            c.execute("UPDATE shifts SET end_timestamp = ? WHERE session_group_id = ? AND end_timestamp IS NULL",
                      (now, self.current_session_id))
            c.execute("INSERT INTO shifts (session_group_id, start_timestamp, type) VALUES (?, ?, ?)",
                      (self.current_session_id, now, 'WORK'))
            self.on_break = False
            self.lbl_status.configure(text="Working...", text_color="green")
            self.btn_break.configure(text="TAKE BREAK")

        conn.commit()
        conn.close()

    def generate_report(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        # Grab last 14 days for example
        cutoff = datetime.datetime.now() - datetime.timedelta(days=14)
        c.execute("SELECT start_timestamp, end_timestamp, type FROM shifts WHERE start_timestamp > ?", (cutoff,))
        data = c.fetchall()
        conn.close()

        if not data: return

        daily_data = {}
        total_seconds_worked = 0
        
        for start_str, end_str, type_ in data:
            if not end_str: continue
            
            s_dt = parser.parse(start_str)
            e_dt = parser.parse(end_str)
            
            # --- MIDNIGHT CROSSOVER LOGIC ---
            segments = []
            
            # If same day, just one segment
            if s_dt.date() == e_dt.date():
                segments.append((s_dt.date(), s_dt, e_dt))
            else:
                # Splits across midnight
                # Segment 1: Start -> Midnight of that day
                midnight = (s_dt + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                segments.append((s_dt.date(), s_dt, midnight))
                
                # Segment 2: Midnight -> End
                segments.append((e_dt.date(), midnight, e_dt))

            for date_key, seg_start, seg_end in segments:
                # Convert to "Hours" for plotting (0.0 to 24.0)
                start_h = seg_start.hour + seg_start.minute/60 + seg_start.second/3600
                
                # Calculate duration in hours
                dur_h = (seg_end - seg_start).total_seconds() / 3600
                
                if date_key not in daily_data:
                    daily_data[date_key] = {'work': [], 'break': []}
                
                if type_ == 'WORK':
                    daily_data[date_key]['work'].append((start_h, dur_h))
                    total_seconds_worked += (seg_end - seg_start).total_seconds()
                else:
                    daily_data[date_key]['break'].append((start_h, dur_h))

        # --- STATS ---
        days_tracked = len(daily_data) if daily_data else 1
        total_hours = total_seconds_worked / 3600
        goal_hours = days_tracked * GOAL_HOURS_PER_DAY
        variance = total_hours - goal_hours

        # --- PLOT ---
        fig, ax = plt.subplots(figsize=(12, 6))
        sorted_dates = sorted(daily_data.keys())
        y_ticks = range(len(sorted_dates))
        
        for i, date in enumerate(sorted_dates):
            if daily_data[date]['work']:
                ax.broken_barh(daily_data[date]['work'], (i - 0.4, 0.8), facecolors='#4CAF50', edgecolor='black', linewidth=0.5)
            if daily_data[date]['break']:
                ax.broken_barh(daily_data[date]['break'], (i - 0.4, 0.8), facecolors='#FFC107', edgecolor='black', linewidth=0.5)

        ax.set_ylim(-1, len(sorted_dates))
        ax.set_yticks(y_ticks)
        ax.set_yticklabels([d.strftime("%a %d") for d in sorted_dates])
        ax.set_xlim(0, 24)
        ax.set_xlabel("Time of Day (00:00 - 24:00)")
        ax.set_title(f"Shift History | Variance from Goal: {variance:+.2f} hrs")
        ax.set_xticks(range(0, 25, 2))
        ax.grid(True, axis='x', linestyle='--', alpha=0.3)
        
        legend_elements = [Patch(facecolor='#4CAF50', label='Work'),
                           Patch(facecolor='#FFC107', label='Break')]
        ax.legend(handles=legend_elements, loc='upper right')

        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    app = TimeTrackerApp()
    app.mainloop()