# Ecosystem Mapping: Analytics & Presentation Layer

## Constraints for Live Data Feed Refactor (HTTP -> UDP)
When modifying the underlying data streams (moving the plugin emitter to ping UDP instead of HTTP), the following constraints apply to the frontend and analytics ecosystem:

1. **`bbd_gui.py` (The Overlay) WILL BREAK:**
   - **The Issue:** It actively relies on a `requests.get("http://127.0.0.1:5000/hp")` polling loop, running every 50ms to populate the "Live Tick Matrix" visualization and determine the application's synchronization state.
   - **Constraint:** The GUI script must be refactored to either listen to the new UDP socket stream directly, or intermediate telemetry middleware must be placed between the UDP socket and the GUI to maintain the `LIVE_HP_STATE` in a readable format.

2. **`bbd_gui.py` (Live Telemetry Widget) REMAINS INTACT (Conditional):**
   - **The Good News:** The "Combat Telemetry" widget (which renders the hitsplat histograms) does not use the `/hp` HTTP endpoint. Instead, it hits `sqlite3` and queries `combat_telemetry.db` directly.
   - **Constraint:** As long as the new UDP backend successfully intercepts hitsplats and routes them into the `hitsplats` table in `combat_telemetry.db`, this GUI widget will not break.

3. **`bbd_lab.py` (Streamlit) REMAINS INTACT:**
   - **The Good News:** The Streamlit laboratory is entirely decoupled from the live data feeds. It expects no live updates.
   - **Constraint:** None. It runs strictly on aggregated static datasets (`normalized_sessions.csv`, `wealth_history.csv`, and JSON files), which are updated by completely passive background scripts (`normalize_sessions.py`).

4. **Plotting Scripts (`plot_scripts/*.py`) REMAIN INTACT:**
   - **The Good News:** All 24 chart generators pull from static datasets (`csv`, `json`, `.db` queries).
   - **Constraint:** None. They do not intercept the live data pipe.

---

## 1. Presentation Layer `bbd_gui.py` (Live Overlay)
Provides the pilot's HUD atop the OSRS client and the Elgato Prompter. It spans multiple displays.

**Data Sources:**
- **Live / Active Data:**
  - `http://127.0.0.1:5000/hp`: HTTP endpoint for phase mapping (AWAY, KILLING, IDLE) and tick timing.
  - `combat_telemetry.db`: SQLite DB pinged to fetch the latest session's `damage` hitsplats.
- **Historical / Flat File References:**
  - `items.csv` & `prices_*.csv` (Wiki snapshots for opportunity cost math)
  - `bbd_data/*.json` (Recent session aggregations)
  - `gpph_sessions.csv` (Cross-referenced with JSONs to retrieve net profit / margins)
  - `live_wealth.json` (Used for the financial grid tracking)

**Specific UI Widgets Rendered:**
1. **Iterator**: Displays `<NEXT SESSION: ####>`
2. **History**: Top 5 most recent sessions with ΔTTK, Avg Secs to Bank (ASTB), Missed Ticks, and Efficiency %.
3. **Stats**: Segmented moving averages across 24h, 3d, 7d, and 30d periods.
4. **RNG Tracker**: Live Gross GP/D variance (Theoretical baseline vs. All-Time vs. Current Session).
5. **Opportunity Cost**: Actively updates the "Minimum Slot Value" required to drop an item, calculated from current Net GP/s and Average Bank Time metrics.
6. **2x2 Financial Grid**: `Fin Stmt`, `Time Log`, `Performance`, `Projections`. Driven entirely by `live_wealth.json`.
7. **Waffle Board**: A massive 1024x600 grid specifically sized for the Elgato Prompter, visualizing "Hours Logged", "Hours Remaining", and "Days Remaining".
8. **Combat Telemetry**: Plots a bar histogram of damage ranges (0, 1-10, 11-20, etc.) and actively tracks DPS/Accuracy divergence from the theoretical setups defined in the tracker.
9. **Tick Visualizer**: The neon scrolling tick tape powered by the `requests.get` loop. Color codes valid ticks, dropped ticks, and non-combat phases.

---

## 2. Analytics Layer `bbd_lab.py` (Streamlit)
Serves as the post-session "Laboratory" where ML modeling identifies gear traps. Does **not** poll 127.0.0.1.

**Data Ingestion:**
- `normalized_sessions.csv`: Main artery for the OLS, Lasso, and Bayesian Ridge models.
- `wealth_history.csv`: Feed for the Plotly time series graphs in the "Wealth Tracker" tab.
- `bbd_data/*.json`: Parsed in bulk to recreate visual images of the worn equipment loadouts.

---

## 3. Data Generators `plot_scripts/*.py`
Stand-alone scripts used for deep-dive reporting. 

**Data Ingestion Sources:**
No live consumption. They rely natively on `pandas.read_csv()`, `json.load()`, and `sqlite3.connect()`.
- **Databases**: `census.db` (bot paths), `combat_telemetry.db` (luck curves), `time_tracker.db` (session bounds).
- **Files**: `normalized_sessions.csv`, `gpph_enriched.csv`, `live_wealth.json`.

---

## 4. Fundamental Save Mechanism (The Source of Truth)
The final `bbd_data/session_*.json` files that form the foundation of our entire ML/Analytics structure are constructed in **`bbd_tracker.py`**.

- **Mechanism/Function**: `save_data(self, silent=False)` located inside the `BBDTrackerApp` class.
- **Trigger Condition**: Exclusively fired when the user presses the red `<⏹ STOP & SAVE>` button in the Tkinter tracker GUI. It is linked to `stop_session()`.
- **What it compiles**:
  - Halts the active session clock (`self.active_seconds_bank`) and calculates true execution time.
  - Bundles the dictionary `self.loot_tracker`.
  - Serializes the list of timestamped events (`self.event_log`).
  - Appends the UI states of every `<ctk.CTkOptionMenu>` dropdown item indicating the gear worn during that run.
  - Uses `json.dump()` to write this super-object out as `bbd_data/session_{UnixTimestamp}.json`.
