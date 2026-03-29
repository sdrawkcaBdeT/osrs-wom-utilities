# Project: OSRS Discrete-Time Telemetry & Economy Visualizer
**Status: As-Built Architecture (Phase 5 Complete)**

**Project Goal:** A dual-renderer, discrete-time visualizer for Old School RuneScape (OSRS). Tracking 0.6-second server ticks to display combat efficiency and loot accumulation. Features a live, gamified overlay (Tkinter) for immediate feedback, background image loggers (Pillow/PIL) for barcodes, and an underlying data-science pipeline leveraging raw SQLite telemetry for advanced analytics.

---

## Part 1: System Architecture & Inter-Process Communication (IPC)

The system is fully decoupled to prevent stuttering and UI logic from interfering with data collection.

* **Broadcaster (Java - `BBDTrackerPlugin.java`):** Acts as the absolute source of truth. It tracks game state via the RuneLite client and sends lightweight payloads.
* **Listener/Backend (Python - `bbd_tracker.py`):** Dedicated background thread running a UDP server on `127.0.0.1:5005`.
* **Frontend A (Python - `bbd_gui.py`):** A 50ms (20 FPS) Tkinter main loop that reads state instantly from `mmap` shared memory blocks (`BBD_UDP_STATE` and `BBD_UDP_PROFIT`) to render smooth-scrolling live graphics.
* **Frontend B (Python - `bbd_pillow_loggers.py`):** Background Pillow threads that paint the history onto massive image canvases and save them as PNGs upon session completion.
* **Master Datastore (SQLite - `combat_telemetry.db`):** Highly granular event-storage housing thousands of timestamped combat ticks and profit deltas, committed in batches when sessions close to avoid disk thrashing.
* **The IPC Protocol:** Java and Python communicate via UDP Sockets. This is non-blocking ("fire and forget"), ensuring the Python tracker never locks up on network latency. The Python Tracker and the Python GUI communicate via Windows named memory-maps (`mmap`), delivering 0-latency variable reads.

## Part 2: The Java Broadcaster (RuneLite)

The Python app has *zero* internal combat timers. RuneLite dictates all logic to prevent double-counting.

* **The Tick Anchor:** The plugin broadcasts a UDP packet every time the server's `onGameTick` event fires (e.g., `{"event": "tick_sync", "tick": 1045, "state": "idle"}`).
* **Animation-Based Attack Tracking:** The plugin hooks into `onAnimationChanged`. When the player's attack animation ID starts, it flags the next `onGameTick` payload as an attack initiation.
* **Economy Tracking (Net Profit):** Tracks true Net Profit (Inventory Delta) based on the GP-Per-Hour reference plugin logic. Whenever Net GP changes, it fires a UDP packet: `{"event": "net_profit_delta", "value": [integer]}`.

## Part 3: Python Backend State Machine Logic (`bbd_tracker.py`)

When the UDP listener receives data, it manages the state machine and shares it with the UI via `BBD_UDP_STATE`.

* **The Combat Lockout (`update_state_machine`):** Upon receiving an attack initiation, the script forces the subsequent ticks into a "cooldown" state (dependent on the weapon speed, usually 5-ticks), ignoring extra attacks until the cycle completes.

## Part 4: The Live UI (`bbd_gui.py`) - Combat Tape

The Live UI features a rolling, 2-minute horizontal timeline built in Tkinter that shifts natively.

* **The 50ms Math:** The Tkinter `after(50, loop)` function runs tightly at 20 FPS. A server tick is 600ms. Therefore, 12 UI frames precisely equal 1 game tick.
* **The Grid Size:** Each tick block width is 12 pixels across. 
* **The Movement:** Every 50ms, the canvas translates exactly 1 pixel left. Blocks crossing the left bounds are deleted to prevent memory leaks.
* **Combat Color Mapping:**
    * **Cyan:** Tick 1 - Attack animation initiated.
    * **Green:** Ticks 2 through X - Active combat cooldown cycle.
    * **Red:** Dropped tick / Idle - An attack was mechanically possible but missed.
    * **Yellow:** Out of bounds.

## Part 5: The Economy & Reservoirs (`bbd_gui.py`)

* **The Loot Ticker (`ctrl+l`):** 
    * Loot volume is visualized via pixel density.
    * **Standard Scale:** 1 solid gold pixel = 1,000 GP. (Max: 144,000 GP per 12x12 tick block).
    * **Mega Rare Scale:** 1 magenta pixel = 30,000 GP. Automatically scales during >1M drops.
* **Multi-Window Reservoirs (`ctrl+v`):**
    * **Session Reservoir:** Nested beneath the Opportunity Cost window. When gold drops exit the left side of the Combat Tape, their value cascades into this vertical bar.
    * **Cumulative Vault:** Embedded inside the Waffle window directly above the prompter view (toggled with `ctrl+v`). 
    * **End of Session Pour:** Simulates a wealth transfer upon stopping the session, visually subtracting pixels from the Session Reservoir and adding to the Vault until empty.

## Part 6: Background Pillow Loggers (`bbd_pillow_loggers.py`)

Synchronous background threads that clone the live UI directly to ultra-high-resolution PNG datasets.

* **Dynamics:** Scales out dynamically in 10-row increments so RAM consumption remains linear to session length.
* **Outputs:** `combat_log_[date].png` and `loot_log_[date].png` safely crop to the exact session end point and write to the `bbd_data` folder on command.

## Part 7: Data Science Pipeline (`analytics_*.py`)

With raw telemetry cleanly preserved inside `combat_telemetry.db`, a suite of Data Science scripts enables granular review.

*   `analytics_markov.py`: Computes the Probability Matrix of migrating between Attack/Cooldown/Idle states.
*   `analytics_downtime.py`: Generates the frequency distribution of elapsed Idle intervals to determine micro-downtime causes.
*   `analytics_profit_density.py`: Plots historical GP drops on a chronological axis directly addressing RNG density volatility.
*   `analytics_distraction.py`: Formidably joins tick efficiency logs with `census.db` entity tracking, empirically testing how much DPS is lost to chatting with REAL players or dodging SUSPECT bots inside a 6-minute window.
*   `analytics_efficiency_vs_tngp.py`: The capstone scatter plot tracking how the raw biological `Efficiency Quotient` precisely impacts the Normalized, Luck-Adjusted `T-NGP/hr` metric outputted by the pipeline block.