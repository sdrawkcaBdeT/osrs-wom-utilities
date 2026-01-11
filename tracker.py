import customtkinter as ctk
import sqlite3
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch

# --- CONFIGURATION ---
DB_NAME = "time_tracker.db"
GOAL_HOURS_PER_DAY = 1.0

class TimeTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Series Time Tracker")
        self.geometry("400x500")
        
        # State variables
        self.current_session_id = None
        self.is_working = False
        self.on_break = False
        self.start_time = None
        
        self.setup_db()
        self.setup_ui()
        self.check_active_session()
        self.update_clock()

    def setup_db(self):
        """Initialize SQLite Database"""
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        # Table for raw shift segments
        c.execute('''CREATE TABLE IF NOT EXISTS shifts
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      session_group_id TEXT, 
                      start_timestamp DATETIME,
                      end_timestamp DATETIME,
                      type TEXT)''') # type: 'WORK' or 'BREAK'
        conn.commit()
        conn.close()

    def setup_ui(self):
        """Build the GUI"""
        # 1. Header & Timer
        self.lbl_status = ctk.CTkLabel(self, text="Ready to Work", font=("Arial", 20))
        self.lbl_status.pack(pady=20)

        self.lbl_timer = ctk.CTkLabel(self, text="00:00:00", font=("Roboto Mono", 40, "bold"))
        self.lbl_timer.pack(pady=10)

        # 2. Controls
        self.btn_main = ctk.CTkButton(self, text="CLOCK IN", command=self.toggle_work, height=50, fg_color="green")
        self.btn_main.pack(pady=10, padx=20, fill="x")

        self.btn_break = ctk.CTkButton(self, text="TAKE BREAK", command=self.toggle_break, state="disabled", height=40, fg_color="#D4AF37")
        self.btn_break.pack(pady=5, padx=20, fill="x")

        # 3. Analytics Section
        ctk.CTkLabel(self, text="--- Analytics ---").pack(pady=20)
        
        # Simple date range selector (Mockup for now, defaults to last 7 days)
        self.seg_period = ctk.CTkSegmentedButton(self, values=["Last 7 Days", "This Month", "All Time"])
        self.seg_period.set("Last 7 Days")
        self.seg_period.pack(pady=5)

        self.btn_report = ctk.CTkButton(self, text="Generate Visual Report", command=self.generate_report)
        self.btn_report.pack(pady=10)

    def check_active_session(self):
        """Check if we closed the app while running (Basic recovery)"""
        # For V1, we simply reset. In V2, we can check DB for null end_timestamps.
        pass

    def get_current_duration(self):
        if self.start_time:
            delta = datetime.datetime.now() - self.start_time
            # remove microseconds for clean display
            return str(delta).split('.')[0] 
        return "00:00:00"

    def update_clock(self):
        if self.is_working and not self.on_break:
            self.lbl_timer.configure(text=self.get_current_duration())
        elif self.on_break:
             # Make timer blink or stay static to indicate pause
             pass
        self.after(1000, self.update_clock)

    # --- LOGIC HANDLERS ---
    def toggle_work(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.datetime.now()

        if not self.is_working:
            # STARTING WORK
            self.is_working = True
            self.start_time = now
            # Generate a unique group ID for this entire "shift" (work + breaks)
            self.current_session_id = f"SESSION_{int(now.timestamp())}"
            
            c.execute("INSERT INTO shifts (session_group_id, start_timestamp, type) VALUES (?, ?, ?)",
                      (self.current_session_id, now, 'WORK'))
            
            self.btn_main.configure(text="END SHIFT", fg_color="red")
            self.btn_break.configure(state="normal")
            self.lbl_status.configure(text="Working...", text_color="green")

        else:
            # ENDING WORK
            # Close the current open segment
            c.execute("UPDATE shifts SET end_timestamp = ? WHERE session_group_id = ? AND end_timestamp IS NULL",
                      (now, self.current_session_id))
            
            self.is_working = False
            self.on_break = False
            self.start_time = None
            
            self.btn_main.configure(text="CLOCK IN", fg_color="green")
            self.btn_break.configure(state="disabled", text="TAKE BREAK")
            self.lbl_status.configure(text="Shift Saved.", text_color="white")
            self.lbl_timer.configure(text="00:00:00")

        conn.commit()
        conn.close()

    def toggle_break(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.datetime.now()

        if not self.on_break:
            # START BREAK (End current work segment, start break segment)
            c.execute("UPDATE shifts SET end_timestamp = ? WHERE session_group_id = ? AND end_timestamp IS NULL",
                      (now, self.current_session_id))
            c.execute("INSERT INTO shifts (session_group_id, start_timestamp, type) VALUES (?, ?, ?)",
                      (self.current_session_id, now, 'BREAK'))
            
            self.on_break = True
            self.lbl_status.configure(text="On Break (Yellow)", text_color="yellow")
            self.btn_break.configure(text="RESUME WORK")
            
        else:
            # END BREAK (End break segment, start work segment)
            c.execute("UPDATE shifts SET end_timestamp = ? WHERE session_group_id = ? AND end_timestamp IS NULL",
                      (now, self.current_session_id))
            c.execute("INSERT INTO shifts (session_group_id, start_timestamp, type) VALUES (?, ?, ?)",
                      (self.current_session_id, now, 'WORK'))
            
            self.on_break = False
            # Reset visual timer base to now so it counts up from 0 for the new segment? 
            # Or keep total active time? (Keeping simple for now)
            self.lbl_status.configure(text="Working...", text_color="green")
            self.btn_break.configure(text="TAKE BREAK")

        conn.commit()
        conn.close()

    # --- VISUALIZATION & ANALYTICS ---
    def generate_report(self):
        """Queries DB and generates Matplotlib Gantt"""
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # Defaulting to "Last 7 days" for this demo
        seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        c.execute("SELECT start_timestamp, end_timestamp, type FROM shifts WHERE start_timestamp > ?", (seven_days_ago,))
        data = c.fetchall()
        conn.close()

        if not data:
            self.lbl_status.configure(text="No data to plot!")
            return

        # Process Data for Plotting
        # Matplotlib broken_barh needs: (start_time_as_float, duration)
        # We will organize data by DATE (y-axis)
        
        daily_data = {} # Key: Date string, Value: List of (start_hour, duration)
        total_seconds_worked = 0
        
        for start, end, type_ in data:
            if not end: continue # Skip active sessions
            
            s_dt = datetime.datetime.fromisoformat(start)
            e_dt = datetime.datetime.fromisoformat(end)
            date_key = s_dt.date()
            
            # Convert time to "Hours since midnight"
            start_h = s_dt.hour + s_dt.minute/60 + s_dt.second/3600
            end_h = e_dt.hour + e_dt.minute/60 + e_dt.second/3600
            duration = end_h - start_h
            
            if date_key not in daily_data:
                daily_data[date_key] = {'work': [], 'break': []}
            
            if type_ == 'WORK':
                daily_data[date_key]['work'].append((start_h, duration))
                total_seconds_worked += (e_dt - s_dt).total_seconds()
            else:
                daily_data[date_key]['break'].append((start_h, duration))

        # --- STATS CALCULATION ---
        days_tracked = len(daily_data) if daily_data else 1
        total_hours = total_seconds_worked / 3600
        goal_hours = days_tracked * GOAL_HOURS_PER_DAY
        variance = total_hours - goal_hours
        
        print(f"Total: {total_hours:.2f}h | Goal: {goal_hours}h | Var: {variance:.2f}h")

        # --- PLOTTING ---
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Sort dates for Y-axis
        sorted_dates = sorted(daily_data.keys())
        y_ticks = range(len(sorted_dates))
        
        for i, date in enumerate(sorted_dates):
            # Plot Work (Green)
            if daily_data[date]['work']:
                ax.broken_barh(daily_data[date]['work'], (i - 0.4, 0.8), facecolors='#4CAF50') # Green
            # Plot Breaks (Yellow)
            if daily_data[date]['break']:
                ax.broken_barh(daily_data[date]['break'], (i - 0.4, 0.8), facecolors='#FFC107') # Yellow

        # Formatting
        ax.set_ylim(-1, len(sorted_dates))
        ax.set_yticks(y_ticks)
        ax.set_yticklabels([d.strftime("%a %d") for d in sorted_dates])
        ax.set_xlim(0, 24)
        ax.set_xlabel("Time of Day (00:00 - 24:00)")
        ax.set_title(f"Shift History (Variance: {variance:+.2f} hrs)")
        
        # Add a vertical line for "Now" if you want? No, keeps it simple.
        # Grid lines for hours
        ax.set_xticks(range(0, 25, 2))
        ax.grid(True, axis='x', linestyle='--', alpha=0.5)

        # Legend
        legend_elements = [Patch(facecolor='#4CAF50', label='Work'),
                           Patch(facecolor='#FFC107', label='Break')]
        ax.legend(handles=legend_elements, loc='upper right')

        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    app = TimeTrackerApp()
    app.mainloop()