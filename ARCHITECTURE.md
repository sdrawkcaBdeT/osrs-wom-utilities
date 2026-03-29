# System Architecture and Flow

## Flow Breakdown

* **The Source (RuneLite Client):** The user's in-game actions (attacking, receiving loot, changing areas) trigger events caught by `BBDTrackerPlugin.java`. The plugin formats these as JSON and transmits them via HTTP and UDP.
* **The Aggregator (Tracker Server):** `bbd_tracker.py` receives the payloads while concurrently accepting direct UI inputs from the user (such as configuring gear or starting a session). It unifies these streams into an active session state.
* **The Storage Layer:** Upon session completion or specific heartbeat intervals, `bbd_tracker.py` writes high-fidelity combat data (ticks, hitsplats, profit deltas) into the `combat_telemetry.db` SQLite database, and saves holistic session breakdowns into the `bbd_data` folder as JSON.
* **The Observers (GUI & Pipelines):** `bbd_gui.py` constantly polls these storage files to render transparent overlays over the game window. Meanwhile, the orchestrator (`datahub.py`) manages independent scripts that pull external data (Wise Old Man API, Grand Exchange prices) into secondary local databases to enrich the HUD.

---

## Responsibility Roster

Core services, managers, and controllers in the repository:

* **`datahub.py` (The Orchestrator)**
    * **Description:** Central command-line interface to orchestrate and launch various tracking, updating, and data visualization pipelines.
    * **Communicates with:** `config.py`, `wom_client.py`, `archiver.py`, `analyzer.py`, `visualizer.py`, and `bbd_visualizer.py`.

* **`bbd_tracker.py` (Tracker Server & App Controller)**
    * **Description:** Primary combat tracking interface and local server, ingesting live game telemetry via HTTP and UDP to manage session states, drop logs, and local SQLite persistence.
    * **Communicates with:** `census_manager.py` and external Java client via HTTP/UDP.

* **`bbd_gui.py` (Overlay Renderer)**
    * **Description:** Provides a transparent, always-on-top overlay interface to display real-time statistics, session history, and financial projections by polling local storage files.
    * **Communicates with:** `bbd_tracker.py` (specifically imports `DROP_TABLE`).

* **`pipeline.py` (Background Data Pipeline)**
    * **Description:** Continuously runs a sequential batch of independent data enrichment, wealth tracking, and market index building sub-scripts at regular five-minute intervals.
    * **Communicates with:** Executes `get_gpph.py`, `get_gpph_prices.py`, `enrich_gpph.py`, `wealth_engine.py`, `normalize_sessions.py`, `daily_report.py`, and `market_index_builder.py`.

* **`archiver.py` (Master Archive Manager)**
    * **Description:** Fetches player snapshot data from the Wise Old Man API and archives it into a local master SQLite database for historical analysis.
    * **Communicates with:** `config.py` and `wom_client.py`.

* **`main.py` (Wise Old Man Auto-Updater)**
    * **Description:** Background service periodically iterates through a configured list of players and politely requests updates for their statistics via the Wise Old Man API.
    * **Communicates with:** `config.py` and `wom_client.py`.

* **`BBDTrackerPlugin.java` (RuneLite Event Controller)**
    * **Description:** Java-based client plugin listens to in-game events like hitsplats, NPC spawns, and inventory changes, formatting and transmitting them as JSON payloads to the Python tracking server.
    * **Communicates with:** `bbd_tracker.py` (via local port 5000 for HTTP and 5005 for UDP).

* **`wom_client.py` (Wise Old Man Client Service)**
    * **Description:** Wrapper for interacting with the external Wise Old Man platform to fetch snapshots or request player updates.
    * **Communicates with:** Used by `main.py`, `archiver.py`, and `datahub.py`.

* **`census_manager.py` (Player Census Manager)**
    * **Description:** Tracks, logs, and categorizes sighted players within specific game zones to maintain a roster of potential bot accounts.
    * **Communicates with:** Used by `bbd_tracker.py`.

---

## Configuration Audit

Comprehensive list of configuration points, environment variables, and hardcoded constants:

### 1. Environment Variables (`.env`)
Loaded via dotenv in `config.py`.
* **`WOM_API_KEY`:** API key used to authenticate with the Wise Old Man (WOM) API. (Default: `None`)

### 2. Python Configuration (`config.py`)
Primary configuration hub for the Wise Old Man orchestration pipeline.
* **`USER_AGENT`:** Required string to identify the application to the WOM API. (Default: `"MyOSRSUpdater/1.0 (Discord: sdrawkcabdet)"`)
* **`BASE_URL`:** Base URL endpoint for the WOM API. (Default: `"https://api.wiseoldman.net/v2"`)
* **`CYCLE_INTERVAL`:** How often the full WOM auto-update cycle runs in seconds. (Default: `3600`)
* **`REQUEST_DELAY`:** Delay in seconds between individual API calls to respect rate limits. (Default: `5`)
* **`PROJECT_START_DATE`:** ISO 8601 string threshold; the archiver ignores data before this date. (Default: `"2026-01-04T00:00:00"`)
* **`SEED_LISTS`:** A dictionary containing base lists of players to track, categorized by `real_ones` and `suspected_bots`.
* **`CENSUS_DB`:** Path to the local SQLite database used to dynamically merge in-game sighted players into the tracking lists. (Default: `"census.db"`)
* **`ACTIVITY_CONFIG`:** Configuration dictionary used by the deduction engine to estimate "Hours Played" based on XP gains per category.
    * `suspected_bots`: Tracks "ranged" at 85,995 XP/hr with a secondary "hitpoints" metric.
    * `real_ones`: Tracks "overall" at 75,000 XP/hr.
* **`TIMEZONE`:** Timezone used for generating analytics visualizations. (Default: `'America/Chicago'`)
* **`FONT_PATH_PRIMARY` / `FONT_PATH_SECONDARY`:** File paths for the fonts used in generated charts. (Defaults: `"fonts/industryultra.OTF"`, `"fonts/EXPRESSWAY RG-BOLD.OTF"`)
* **`SKILL_COLORS`:** A dictionary mapping OSRS skill names to specific Hex color codes for chart rendering.

### 3. Streamlit Theme Configuration (`.streamlit/config.toml`)
Controls the UI aesthetics for any Streamlit-based dashboards in the repository.
* **`base`:** Base theme mode. (Default: `"dark"`)
* **`primaryColor`:** Primary UI accent color. (Default: `"#00FF00"`)
* **`backgroundColor`:** Main background color. (Default: `"#1E1E1E"`)
* **`secondaryBackgroundColor`:** Sidebar or secondary element background. (Default: `"#252526"`)
* **`textColor`:** Base text color. (Default: `"#CCCCCC"`)
* **`font`:** Base font family. (Default: `"sans serif"`)

### 4. Hardcoded Networking & Server Constants
* **HTTP Server (`bbd_tracker.py` / `BBDTrackerPlugin.java`):** Flask server runs on `HOST = '127.0.0.1'` and `PORT = 5000`. The Java plugin POSTs payloads to `"http://127.0.0.1:5000/event"`.
* **UDP Listener (`bbd_tracker.py` / `BBDTrackerPlugin.java`):** The secondary fast-tick UDP pipe runs on `UDP_HOST = '127.0.0.1'` and `UDP_PORT = 5005`.

### 5. Hardcoded Storage & Database Paths
* **`combat_telemetry.db`:** Hardcoded SQLite database name in `bbd_tracker.py` and `bbd_gui.py` for storing tick-by-tick combat and hitsplat data.
* **`wom_master.db`:** Hardcoded SQLite database name in `archiver.py` for storing historical WOM snapshots.
* **`DATA_DIR`:** Folder for saving individual session JSONs. (Default: `"bbd_data"`)
* **`IMG_DIR`:** Folder for caching downloaded item UI images. (Default: `"item_images"`)
* **`STATE_FILE`:** File saving the iterator for the next session. (Default: `"session_state.json"`)
* **`DPS_PROFILES_FILE`:** File saving saved theoretical combat profiles. (Default: `"dps_profiles.json"`)

### 6. Hardcoded In-Game Logic Constants
* **BBD Location Bounds (`BBDTrackerPlugin.java`):** The specific coordinate rectangle defining the Catacombs Brutal Black Dragon area. (`MIN_X = 1608`, `MAX_X = 1625`, `MIN_Y = 10085`, `MAX_Y = 10104`).
* **BBD Health (`bbd_tracker.py` / `BBDTrackerPlugin.java`):** Max HP for the target NPC is hardcoded to `315`.
* **Shiny Spawn Rate (`BBDTrackerPlugin.java`):** The probability of the custom "shiny" texture triggering on an NPC spawn is hardcoded to `0.00048828125` (1/2048).
* **`DROP_TABLE` & `ITEM_MAP` (`bbd_tracker.py`):** Massive static dictionaries containing the exact drop rates, item names, and IDs for the Brutal Black Dragon drop table.
* **`SOUND_PATH` (`bbd_tracker.py`):** Local file path for the kill notification sound. (Default: `r"D:\AFK Adventures Part 4\assets_licensed audio\Sound Effects\kill_notification_lq.wav"`)

### 7. Hardcoded Pipeline & Overlay Constants
* **`PIPELINE_SCRIPTS` (`pipeline.py`):** A static array of python scripts executed sequentially every 300 seconds (5 minutes).
* **Overlay Grid Coordinates (`bbd_gui.py`):** Extensive hardcoded integer grids (e.g., `MAIN_W = 2560`, `MAIN_H = 1440`, `SIDE_ORIGIN_X = MAIN_W`) used to absolutely position the Tkinter overlay windows relative to specific monitor resolutions.