import customtkinter as ctk
import sqlite3
import datetime
import os
from dateutil import parser, relativedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Patch
import pandas as pd
import tkinter as tk
from tkinter import messagebox

# --- CONFIGURATION ---
DB_NAME = "time_tracker.db"
REPORT_DIR = "reports"
CSV_NAME = "time_tracking_history.csv"
GOAL_HOURS_PER_DAY = 1.0
THEME_COLOR = "green" 
APP_SIZE = "1200x800"

# Ensure report directory exists
if not os.path.exists(REPORT_DIR):
    os.makedirs(REPORT_DIR)

# --- DATABASE MANAGER ---
class DatabaseManager:
    def __init__(self, db_name):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS shifts
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      session_group_id TEXT, 
                      start_timestamp DATETIME,
                      end_timestamp DATETIME,
                      type TEXT)''')
        conn.commit()
        conn.close()

    def run_query(self, query, params=()):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute(query, params)
        data = c.fetchall()
        conn.commit()
        conn.close()
        return data

    def get_dataframe(self):
        conn = sqlite3.connect(self.db_name)
        df = pd.read_sql_query("SELECT * FROM shifts", conn)
        conn.close()
        return df

    def export_to_csv(self):
        """Mirrors the DB to a CSV file for external analysis."""
        try:
            df = self.get_dataframe()
            # Add some derived columns for easier analysis in Excel/R
            df['start_timestamp'] = pd.to_datetime(df['start_timestamp'])
            df['end_timestamp'] = pd.to_datetime(df['end_timestamp'])
            df['duration_hours'] = (df['end_timestamp'] - df['start_timestamp']).dt.total_seconds() / 3600
            
            path = os.path.join(REPORT_DIR, CSV_NAME)
            df.to_csv(path, index=False)
            print(f"Data auto-exported to {path}")
        except Exception as e:
            print(f"Export failed: {e}")

# --- UI COMPONENTS ---

class EditorFrame(ctk.CTkFrame):
    def __init__(self, master, db):
        super().__init__(master)
        self.db = db
        self.rows = []
        
        self.ctrl_frame = ctk.CTkFrame(self, height=40)
        self.ctrl_frame.pack(fill="x", padx=10, pady=5)
        
        self.btn_refresh = ctk.CTkButton(self.ctrl_frame, text="Refresh Data", command=self.load_data, width=100)
        self.btn_refresh.pack(side="left", padx=5)
        
        self.btn_save = ctk.CTkButton(self.ctrl_frame, text="Save Changes", command=self.save_changes, fg_color="green", width=100)
        self.btn_save.pack(side="left", padx=5)

        self.scroll = ctk.CTkScrollableFrame(self, label_text="Edit Recent Logs (Top 50)")
        self.scroll.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.load_data()

    def load_data(self):
        for widget in self.scroll.winfo_children():
            widget.destroy()
        self.rows = []

        headers = ["ID", "Start Time (YYYY-MM-DD HH:MM:SS)", "End Time", "Type (WORK/BREAK)"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.scroll, text=h, font=("Arial", 12, "bold")).grid(row=0, column=i, padx=5, pady=5, sticky="w")

        data = self.db.run_query("SELECT id, start_timestamp, end_timestamp, type FROM shifts ORDER BY start_timestamp DESC LIMIT 50")

        for idx, (row_id, start, end, type_) in enumerate(data):
            r = idx + 1
            lbl_id = ctk.CTkLabel(self.scroll, text=str(row_id), width=30)
            lbl_id.grid(row=r, column=0, padx=5)

            ent_start = ctk.CTkEntry(self.scroll, width=200)
            ent_start.insert(0, start)
            ent_start.grid(row=r, column=1, padx=5, pady=2)

            ent_end = ctk.CTkEntry(self.scroll, width=200)
            ent_end.insert(0, str(end) if end else "")
            ent_end.grid(row=r, column=2, padx=5, pady=2)

            ent_type = ctk.CTkEntry(self.scroll, width=100)
            ent_type.insert(0, type_)
            ent_type.grid(row=r, column=3, padx=5, pady=2)

            self.rows.append((row_id, ent_start, ent_end, ent_type))

    def save_changes(self):
        try:
            for row_id, e_start, e_end, e_type in self.rows:
                s_txt = e_start.get()
                e_txt = e_end.get()
                t_txt = e_type.get()

                if s_txt: parser.parse(s_txt)
                if e_txt and e_txt != "None": parser.parse(e_txt)
                else: e_txt = None

                self.db.run_query("UPDATE shifts SET start_timestamp=?, end_timestamp=?, type=? WHERE id=?", 
                                  (s_txt, e_txt, t_txt, row_id))
            
            print("Saved successfully.")
            self.db.export_to_csv() # Trigger Auto-Export
            self.load_data()
        except Exception as e:
            tk.messagebox.showerror("Save Error", f"Could not save changes.\nCheck date formats.\nError: {e}")


class AnalysisFrame(ctk.CTkFrame):
    def __init__(self, master, db):
        super().__init__(master)
        self.db = db
        self.current_date = datetime.date.today()
        self.view_mode = "Week" 

        # --- Top Controls ---
        self.ctrl_frame = ctk.CTkFrame(self)
        self.ctrl_frame.pack(fill="x", padx=10, pady=10)

        # Row 1: View Selection
        self.seg_view = ctk.CTkSegmentedButton(self.ctrl_frame, values=["Today", "3-Day", "Week", "Month", "Custom"], command=self.change_view_mode)
        self.seg_view.set("Week")
        self.seg_view.pack(pady=5)

        # Row 2: Navigation & Custom Inputs
        self.nav_frame = ctk.CTkFrame(self.ctrl_frame, fg_color="transparent")
        self.nav_frame.pack(fill="x", pady=5)

        self.btn_prev = ctk.CTkButton(self.nav_frame, text="< Prev", width=60, command=lambda: self.change_date(-1))
        self.btn_prev.pack(side="left", padx=5)

        self.lbl_date_range = ctk.CTkLabel(self.nav_frame, text="Date Range", font=("Arial", 16, "bold"), width=250)
        self.lbl_date_range.pack(side="left", padx=5)

        self.btn_next = ctk.CTkButton(self.nav_frame, text="Next >", width=60, command=lambda: self.change_date(1))
        self.btn_next.pack(side="left", padx=5)

        # Custom Date Inputs (Hidden by default)
        self.custom_frame = ctk.CTkFrame(self.ctrl_frame, fg_color="transparent")
        self.ent_custom_start = ctk.CTkEntry(self.custom_frame, placeholder_text="YYYY-MM-DD")
        self.ent_custom_start.pack(side="left", padx=5)
        ctk.CTkLabel(self.custom_frame, text="to").pack(side="left")
        self.ent_custom_end = ctk.CTkEntry(self.custom_frame, placeholder_text="YYYY-MM-DD")
        self.ent_custom_end.pack(side="left", padx=5)
        self.btn_custom_go = ctk.CTkButton(self.custom_frame, text="Go", width=50, command=self.update_chart)
        self.btn_custom_go.pack(side="left", padx=5)

        # Right Side Tools
        self.btn_export = ctk.CTkButton(self.nav_frame, text="Export PNG", command=self.export_chart, fg_color="#D4AF37", text_color="black", width=100)
        self.btn_export.pack(side="right", padx=5)
        
        self.btn_refresh = ctk.CTkButton(self.nav_frame, text="Refresh", command=self.update_chart, fg_color="#555555", width=80)
        self.btn_refresh.pack(side="right", padx=5)

        # --- Stats Bar ---
        self.stats_frame = ctk.CTkFrame(self, height=40, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=20, pady=5)
        self.lbl_stats = ctk.CTkLabel(self.stats_frame, text="Loading stats...", font=("Arial", 14))
        self.lbl_stats.pack(side="left")

        # --- Chart Area ---
        self.chart_frame = ctk.CTkFrame(self)
        self.chart_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.fig, self.ax = plt.subplots(figsize=(10, 5), dpi=100)
        self.fig.patch.set_facecolor('#2b2b2b') 
        self.ax.set_facecolor('#2b2b2b')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.update_chart()

    def change_view_mode(self, value):
        self.view_mode = value
        if value == "Custom":
            self.nav_frame.pack_forget()
            self.custom_frame.pack(pady=5)
        else:
            self.custom_frame.pack_forget()
            self.nav_frame.pack(fill="x", pady=5)
            self.update_chart()

    def change_date(self, direction):
        if self.view_mode == "Week":
            delta = datetime.timedelta(weeks=1)
        elif self.view_mode == "Month":
            # Rough month approximation for navigation
            delta = datetime.timedelta(days=30)
        elif self.view_mode == "3-Day":
            delta = datetime.timedelta(days=3)
        elif self.view_mode == "Today":
            delta = datetime.timedelta(days=1)
        else:
            return 
        
        if direction == 1: self.current_date += delta
        else: self.current_date -= delta
        self.update_chart()

    def get_date_range(self):
        if self.view_mode == "Custom":
            try:
                s = parser.parse(self.ent_custom_start.get()).date()
                e = parser.parse(self.ent_custom_end.get()).date()
                return s, e
            except:
                return datetime.date.today(), datetime.date.today()

        if self.view_mode == "Today":
            return self.current_date, self.current_date
        
        if self.view_mode == "3-Day":
            # Current date and previous 2 days
            start = self.current_date - datetime.timedelta(days=2)
            return start, self.current_date

        if self.view_mode == "Week":
            # Start Monday, End Sunday
            start = self.current_date - datetime.timedelta(days=self.current_date.weekday())
            end = start + datetime.timedelta(days=6)
            return start, end

        if self.view_mode == "Month":
            # 1st to Last
            start = self.current_date.replace(day=1)
            next_month = start + relativedelta.relativedelta(months=1)
            end = next_month - datetime.timedelta(days=1)
            return start, end
            
        return self.current_date, self.current_date

    def update_chart(self):
        start_date, end_date = self.get_date_range()
        self.lbl_date_range.configure(text=f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}")

        df = self.db.get_dataframe()
        if df.empty: return

        df['start_timestamp'] = pd.to_datetime(df['start_timestamp'])
        df['end_timestamp'] = pd.to_datetime(df['end_timestamp'])
        
        mask = (df['start_timestamp'].dt.date <= end_date) & \
               ((df['end_timestamp'].dt.date >= start_date) | (df['end_timestamp'].isna()))
        df_view = df.loc[mask].copy()

        now = datetime.datetime.now()
        df_view['end_timestamp'] = df_view['end_timestamp'].fillna(now)

        plot_data = {} 
        total_seconds = 0

        for _, row in df_view.iterrows():
            s = row['start_timestamp']
            e = row['end_timestamp']
            typ = row['type']

            current = s
            while current < e:
                next_midnight = (current + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                segment_end = min(e, next_midnight)
                
                if start_date <= current.date() <= end_date:
                    d_key = current.date()
                    if d_key not in plot_data: plot_data[d_key] = {'work': [], 'break': []}
                    
                    start_h = current.hour + current.minute/60 + current.second/3600
                    dur_h = (segment_end - current).total_seconds() / 3600
                    
                    if typ == 'WORK':
                        plot_data[d_key]['work'].append((start_h, dur_h))
                        total_seconds += (segment_end - current).total_seconds()
                    else:
                        plot_data[d_key]['break'].append((start_h, dur_h))

                current = next_midnight

        days_in_view = (end_date - start_date).days + 1
        total_hours = total_seconds / 3600
        goal = days_in_view * GOAL_HOURS_PER_DAY
        variance = total_hours - goal
        
        color = "green" if variance >= 0 else "red"
        self.lbl_stats.configure(text=f"Total: {total_hours:.2f} hrs  |  Goal: {goal:.1f} hrs  |  Variance: {variance:+.2f} hrs", text_color=color)

        self.ax.clear()
        
        dates_list = [start_date + datetime.timedelta(days=x) for x in range((end_date-start_date).days + 1)]
        y_ticks = range(len(dates_list))
        
        for i, d in enumerate(dates_list):
            if d in plot_data:
                if plot_data[d]['work']:
                    self.ax.broken_barh(plot_data[d]['work'], (i - 0.4, 0.8), facecolors='#4CAF50', edgecolor='white', linewidth=0.5)
                if plot_data[d]['break']:
                    self.ax.broken_barh(plot_data[d]['break'], (i - 0.4, 0.8), facecolors='#FFC107', edgecolor='white', linewidth=0.5)

        self.ax.set_yticks(y_ticks)
        self.ax.set_yticklabels([d.strftime("%a %d") for d in dates_list], color='white')
        self.ax.set_ylim(-0.5, len(dates_list) - 0.5)
        self.ax.set_xlim(0, 24)
        self.ax.set_xticks(range(0, 25, 2))
        self.ax.set_xticklabels(range(0, 25, 2), color='white')
        self.ax.set_xlabel("Hour of Day", color='white')
        self.ax.grid(True, axis='x', linestyle='--', alpha=0.2, color='white')
        
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['top'].set_color('white') 
        self.ax.spines['left'].set_color('white')
        self.ax.spines['right'].set_color('white')
        self.ax.tick_params(axis='x', colors='white')
        self.ax.tick_params(axis='y', colors='white')

        legend_elements = [Patch(facecolor='#4CAF50', label='Work'),
                           Patch(facecolor='#FFC107', label='Break')]
        self.ax.legend(handles=legend_elements, loc='upper right', facecolor='#2b2b2b', edgecolor='white', labelcolor='white')

        self.canvas.draw()

    def export_chart(self):
        filename = f"report_{self.current_date}.png"
        self.fig.savefig(filename, facecolor='#2b2b2b')
        tk.messagebox.showinfo("Export", f"Chart saved as {filename}")


class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, db, update_callback):
        super().__init__(master)
        self.db = db
        self.update_callback = update_callback 
        
        self.is_working = False
        self.on_break = False
        self.current_session_id = None
        self.start_time = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) 
        self.grid_rowconfigure(4, weight=1) 

        self.lbl_timer = ctk.CTkLabel(self, text="00:00:00", font=("Roboto Mono", 80, "bold"))
        self.lbl_timer.grid(row=1, column=0, pady=20)

        self.lbl_status = ctk.CTkLabel(self, text="Ready to Grind", font=("Arial", 20))
        self.lbl_status.grid(row=2, column=0, pady=(0, 30))

        self.btn_action = ctk.CTkButton(self, text="CLOCK IN", command=self.toggle_work, 
                                        height=80, width=300, font=("Arial", 24, "bold"), fg_color="green")
        self.btn_action.grid(row=3, column=0, pady=10)

        self.btn_break = ctk.CTkButton(self, text="TAKE BREAK", command=self.toggle_break, 
                                       state="disabled", height=50, width=300, fg_color="#D4AF37", text_color="black")
        self.btn_break.grid(row=4, column=0, pady=10)

        self.check_active_session()
        self.update_clock()

    def check_active_session(self):
        res = self.db.run_query("SELECT session_group_id, start_timestamp, type FROM shifts WHERE end_timestamp IS NULL ORDER BY start_timestamp DESC LIMIT 1")
        if res:
            self.current_session_id, start_str, type_ = res[0]
            self.start_time = parser.parse(start_str)
            self.is_working = True
            
            if type_ == 'BREAK':
                self.on_break = True
                self.set_ui_state("break")
            else:
                self.set_ui_state("working")

    def set_ui_state(self, state):
        if state == "working":
            self.btn_action.configure(text="END SHIFT", fg_color="red")
            self.btn_break.configure(state="normal", text="TAKE BREAK")
            self.lbl_status.configure(text="Session Active", text_color="#4CAF50")
        elif state == "break":
            self.btn_action.configure(text="END SHIFT", fg_color="red")
            self.btn_break.configure(state="normal", text="RESUME WORK")
            self.lbl_status.configure(text="On Break", text_color="#FFC107")
        elif state == "idle":
            self.btn_action.configure(text="CLOCK IN", fg_color="green")
            self.btn_break.configure(state="disabled", text="TAKE BREAK")
            self.lbl_status.configure(text="Shift Saved", text_color="white")
            self.lbl_timer.configure(text="00:00:00")

    def get_current_duration(self):
        if self.start_time:
            delta = datetime.datetime.now() - self.start_time
            return str(delta).split('.')[0] 
        return "00:00:00"

    def update_clock(self):
        if self.is_working:
            self.lbl_timer.configure(text=self.get_current_duration())
        self.after(1000, self.update_clock)

    def toggle_work(self):
        now = datetime.datetime.now()
        if not self.is_working:
            self.is_working = True
            self.start_time = now
            self.current_session_id = f"SESSION_{int(now.timestamp())}"
            self.db.run_query("INSERT INTO shifts (session_group_id, start_timestamp, type) VALUES (?, ?, ?)",
                              (self.current_session_id, now, 'WORK'))
            self.set_ui_state("working")
            self.db.export_to_csv() # Auto-Export
        else:
            self.db.run_query("UPDATE shifts SET end_timestamp = ? WHERE session_group_id = ? AND end_timestamp IS NULL",
                              (now, self.current_session_id))
            self.is_working = False
            self.on_break = False
            self.start_time = None
            self.set_ui_state("idle")
            self.db.export_to_csv() # Auto-Export
            self.update_callback() 

    def toggle_break(self):
        now = datetime.datetime.now()
        self.db.run_query("UPDATE shifts SET end_timestamp = ? WHERE session_group_id = ? AND end_timestamp IS NULL",
                          (now, self.current_session_id))
        
        if not self.on_break:
            self.db.run_query("INSERT INTO shifts (session_group_id, start_timestamp, type) VALUES (?, ?, ?)",
                              (self.current_session_id, now, 'BREAK'))
            self.on_break = True
            self.start_time = now
            self.set_ui_state("break")
        else:
            self.db.run_query("INSERT INTO shifts (session_group_id, start_timestamp, type) VALUES (?, ?, ?)",
                              (self.current_session_id, now, 'WORK'))
            self.on_break = False
            self.start_time = now 
            self.set_ui_state("working")
        
        self.db.export_to_csv() # Auto-Export


# --- MAIN APP ---

class TimeTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("4-Year Hour | Series Tracker")
        self.geometry(APP_SIZE)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme(THEME_COLOR)

        self.db = DatabaseManager(DB_NAME)

        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(fill="both", expand=True, padx=20, pady=20)

        self.tab_view.add("Tracker")
        self.tab_view.add("History & Analysis")
        self.tab_view.add("Editor")

        self.analysis_frame = AnalysisFrame(self.tab_view.tab("History & Analysis"), self.db)
        self.dashboard_frame = DashboardFrame(self.tab_view.tab("Tracker"), self.db, self.analysis_frame.update_chart)
        self.editor_frame = EditorFrame(self.tab_view.tab("Editor"), self.db)

        self.dashboard_frame.pack(fill="both", expand=True)
        self.analysis_frame.pack(fill="both", expand=True)
        self.editor_frame.pack(fill="both", expand=True)

if __name__ == "__main__":
    app = TimeTrackerApp()
    app.mainloop()