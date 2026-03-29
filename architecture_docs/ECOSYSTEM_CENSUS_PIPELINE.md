# Ecosystem Census and Bot Tracking Pipeline
*Pipeline C: External Integration & Deduction Engine*

This document maps the data flow, schemas, and logic of the Player Census and Bot Tracking Pipeline. This system operates independently from the live combat telemetry trackers and is primarily responsible for identifying, tracking, and analyzing long-term player behavior to deduce botting probabilities.

## 1. Data Ingestion & Census Management (The Watchlist)

The pipeline begins when the local RuneLite plugin broadcasts a `player_spawn` event containing the name, combat level, world, and visible gear of any player entering the local render distance.

### Data Ingestion Flow:
1. **Plugin to Tracker**: `bbd_tracker.py` (via Flask server) receives `player_spawn` events.
2. **Sighting Log**: It calls `CensusManager.log_sighting()`, which writes the event to `census.db`.
3. **The Inbox**: New players default to a `NEW` status and are displayed in the UI's "Detected (New)" column.
4. **Manual Triage**: The user manually flags players as `"BOT"` (`SUSPECT`), `"REAL"` (`REAL`), or `"DEL"` (`TRASH`). 

### SQLite Schema (`census.db`)
Stores the master roster and individual sighting events.

**Table: `roster`**
- `username` (TEXT, PRIMARY KEY)
- `status` (TEXT) - *Values: 'NEW', 'SUSPECT', 'REAL', 'TRASH', 'BANNED'*
- `combat_level` (INTEGER)
- `first_seen` (DATETIME)
- `latest_seen` (DATETIME)
- `total_sightings` (INTEGER)
- `notes` (TEXT)

**Table: `sightings`**
- `id` (INTEGER, PRIMARY KEY)
- `username` (TEXT, FOREIGN KEY to roster)
- `session_id` (TEXT) - *Ties the sighting to a specific combat tracking session*
- `world` (INTEGER)
- `timestamp` (DATETIME)
- `gear_json` (TEXT) - *Array of visible gear item IDs*

---

## 2. External API Integration (Wise Old Man)

Players flagged as `SUSPECT` (or explicitly listed as seeded bots/real players) are dynamically loaded into `config.PLAYER_LISTS`. The system then uses the Wise Old Man (WOM) API to track their long-term progression.

### Primary Integration Points (`wom_client.py` & `main.py`)
- **Auto-Updater (`main.py`)**: Runs purely to keep WOM data fresh. It loops through lists in `config.py` and hits the WOM API every `config.CYCLE_INTERVAL` (default: 1 hour) with a polite delay between requests.
- **WOM Client (`wom_client.py`)**: Handles the HTTP requests.

### Specific API Endpoints Hit:
1. **POST `/players/{username}`**
   - **Trigger**: Called by `main.py` on a schedule.
   - **Purpose**: Forces WOM to fetch the latest OSRS Hiscores and create a new data "Snapshot" for the player.
2. **GET `/players/{username}`**
   - **Purpose**: Fetches current player details (stats and boss kills).
3. **GET `/players/{username}/gained?period={period}`**
   - **Purpose**: Fetches exact XP and KC gained over a specific period (e.g., "week").
4. **GET `/players/{username}/snapshots`**
   - **Trigger**: Used when historical tracking is needed.
   - **Purpose**: Paginated fetching of historical player states over time to build local timelines.

---

## 3. The Deduction Engine & Bot Flagging Logic

While the *initial* flagging into the `SUSPECT` list is a manual triage via the UI, the *probability computation and verification* of a bot is handled programmatically by `analyzer.py` and `config.py`.

### The Logic (Activity Inference Algorithm)
The pipeline determines botting probability by calculating an **"Implied Efficiency"** metric over a moving time window. 

1. **The Reference Rate (`config.ACTIVITY_CONFIG`)**: 
   - The config defines an expected `xp_per_hour` for specific activities (e.g., `85,995` Ranged XP/hr for Brutal Black Dragons).
2. **Snapshot Deltas (`analyzer.py`)**:
   - `estimate_activity_log()` takes two snapshots from `wom_master.db` (seeded by the WOM API).
   - It calculates the absolute Time Window between the snapshots (e.g., 24 hours).
   - It calculates the XP gained in the `primary_metric` (e.g., Ranged) between those snapshots.
3. **Probability Calculation**:
   - `Est_Active_Hours = XP_Gained / xp_per_hour`
   - `Implied_Efficiency = Est_Active_Hours / Window_Duration_Hours`
   
**Flagging Outcome:**
If a `SUSPECT` shows an `Implied_Efficiency` that is inhumanly high (e.g., gaining 20 hours worth of expected XP in a 24-hour window, or 85%+ efficiency), the system flags the account as a highly probable bot with near certainty, rather than just a legitimate player grinding hard.
