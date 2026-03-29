# REFACTOR PLAN (Component-Driven Development)

This implementation manual defines the safe, vertically sliced refactoring path from HTTP polling to discrete-time UDP telemetry.

## Phase 1 (The Pipe)
*Objective: Base UDP broadcast in Java (hitsplats) and headless UDP listener in Python (console print only).*

### [Worker 1 - Java Tasks]
**Target Files:** `BBDTrackerPlugin.java`
*   **Target Method (`onGameTick`):** Establish a `DatagramSocket` pointing to `127.0.0.1:5005`. Broadcast a lightweight packet `{"tick": <tick_count>, "state": "idle"}` unconditionally on every server tick.
*   **Target Method (`onAnimationChanged`):** Do not track mouse clicks. Intercept valid attack animation IDs (4230, 7617, 7615). When triggered, flag the upcoming `onGameTick` payload as an attack initiation (`{"state": "attack"}`).
*   **Target Method (`postEvent` / HTTP logic):** Refactor the existing hitsplat `combat_telemetry` and `phase_change` HTTP POST routines to serialize as JSON strings and transmit over the newly established UDP socket.

### [Worker 2 - Python Tasks]
**Target Files:** `bbd_tracker.py`
*   **Target Method (`start_udp_listener` - *New*):** Instantiate a dedicated daemon thread running a background UDP server bound to `127.0.0.1:5005`.
*   **Target Method (`process_packet` - *New*):** Parse incoming JSON UDP payloads. At this phase, bypass any database or UI queues. Print the raw tick and state data directly to the console to validate the anchor pipe is active.

## Phase 2 (The Database)
*Objective: Connecting the Python UDP listener to combat_telemetry.db without breaking Streamlit.*

### [Worker 1 - Java Tasks]
*No tasks in this phase. The Java client must remain untouched to verify backend data parsing.*

### [Worker 2 - Python Tasks]
**Target Files:** `bbd_tracker.py`
*   **Target Method (`process_packet`):** Expand the UDP parser to intercept `combat_telemetry` and `phase_change` events.
*   **Target Method (`save_hitsplat` / Database Ingestion):** Route the intercepted UDP data into the existing SQLite ingestion logic for `combat_telemetry.db`.
*   **Constraint Checklist:** Ensure Streamlit (`bbd_lab.py`) continuity. The transition must not alter the 9 columns of `hitsplats` SQLite table or the monolithic `bbd_data/*.json` outputs (specifically `active_seconds` and `total_attacks`). Verify the `save_data` mechanism is unbroken.

## Phase 3 (The UI)
*Objective: Stripping HTTP polling from bbd_gui.py and wiring the Tkinter grid to the UDP shared memory.*

### [Worker 1 - Java Tasks]
*No tasks in this phase.*

### [Worker 2 - Python Tasks]
**Target Files:** `bbd_gui.py`, `bbd_tracker.py`
*   **Target Method (`bbd_tracker.py` - `update_state_machine`):** Implement the 5-Tick Combat Lockout. When an attack initiation packet is received, forcefully flag the following 4 ticks as active/cooldown (Green). Expose this canonical state via a thread-safe Queue or shared memory struct.
*   **Target Method (`bbd_gui.py` - `after(50, loop)`):** Delete the legacy `requests.get("http://127.0.0.1:5000/hp")` polling loop entirely.
*   **Target Method (`bbd_gui.py` - `render_tick_tape`):** Read from the UDP shared memory. Render a rolling 2-minute 12x12 grid. Shift the canvas exactly 1 pixel left every 50ms (or 12 pixels per 600ms game tick).
*   **Target Method (`bbd_gui.py` - `color_mapper`):** Apply state colors mapping to Tkinter blocks: Cyan (Tick 1 Attack), Green (Tick 2-5 Cooldown), Red (Dropped/Idle), Yellow (Out of Bounds). Delete blocks programmatically as they hit the left boundary to prevent memory leaks.

## Phase 4 (The Economy)
*Objective: Integrating the gp-per-hour inventory delta logic (Java) and the multi-window Reservoirs (Python Tkinter).*

### [Worker 1 - Java Tasks]
**Target Files:** Third-party GP-Per-Hour / Loot Tracker Reference Plugin
*   **Target Method (`Inventory Delta Calculation`):** Do not hook `onNpcLootReceived`. Piggyback on the existing `netTotal` tracker which measures true item gain minus supply loss.
*   **Target Method (`Broadcast Delta`):** Whenever the internal Net Profit variable shifts, fire a UDP packet unconditionally: `{"event": "net_profit_delta", "value": <integer>}`. Keep unchanged the CSV format outputted by the local plugin.

### [Worker 2 - Python Tasks]
**Target Files:** `bbd_gui.py`
*   **Target Method (`render_loot_ticker`):** Implement the UI toggle hotkey. When active, populate the 12x12 Tkinter blocks using a pixel-density calculation (1 pixel = 1,000 GP, Magenta/Blue shift for >1M GP drops at 30k/pixel).
*   **Target Method (`init_reservoirs`):** Spawn the "Session Reservoir" as an `overrideredirect(True)` borderless window pinned to the main monitor right edge, filled bottom-up from exiting scroll blocks. Spawn the "Cumulative Vault" window on the secondary 860x600 display.
*   **Target Method (`end_session_pour`):** Implement a rapid iterative GUI loop triggered upon session stop, which subtracts pixels from the Session Reservoir and deposits them visibly into the Cumulative Vault.

## Phase 5 (The Loggers)
*Objective: Building the background Pillow PNG generators.*

### [Worker 1 - Java Tasks]
*No tasks in this phase.*

### [Worker 2 - Python Tasks]
**Target Files:** New Logger Module (e.g., `bbd_pillow_loggers.py`) or integrated within `bbd_tracker.py`
*   **Target Method (`init_canvases`):** Spawn two background threads orchestrating massive `Pillow/PIL` image objects. Set the width rigidly to 1,200 pixels (100 blocks = 1 minute per row). Height dynamically scales as rows fill.
*   **Target Method (`draw_combat_history`):** Bind to the UDP queue. Paint the exact colored blocks (Cyan, Green, Red, Yellow) matching the UI history onto the `combat_log` canvas indefinitely.
*   **Target Method (`draw_loot_history`):** Paint the corresponding gold pixel density blocks onto the `loot_log` canvas.
*   **Target Method (`save_to_disk`):** Triggered strictly by the "End Session" stop signal. Halt rendering and cleanly write `combat_log_[date].png` and `loot_log_[date].png` to stable storage.
