# Ecosystem Telemetry Pipeline Architecture (Track A)

SCOPE LIMITATION: This document ONLY covers the Track A (Telemetry) pipeline originating from the custom `BBDTrackerPlugin.java`. For economic and loot schemas based on the gp-per-hour plugin, refer to `ECOSYSTEM_ECONOMY_PIPELINE.md`.

This document maps out the high-frequency combat telemetry data flow, defining the exact payloads sent from the RuneLite client and how the Python backend (`bbd_tracker.py`) ingests and stores them. **Any modifications to these systems must maintain strict schema compatibility.**

---

## 1. Data Emitter Layer (Java Client)
**Source:** `BBDTrackerPlugin.java`
**Destination:** Local HTTP Server (`http://127.0.0.1:5000/event`)

The RuneLite plugin listens to internal game events and emits JSON payloads via HTTP POST. Every payload is wrapped in a standard envelope:
```json
{
  "event": "<event_type_string>",
  "payload": { ... } // Varies by event type
}
```

### Emitted Event Types & Payloads:

*   **`combat_telemetry`** (Hitsplats)
    *   *Trigger:* When the local player lands a successful hitsplat on a Brutal Black Dragon.
    *   *Payload:* `{ "damage": <int>, "hp_before": <int> }`
*   **`hp_update`** (Live Boss HP)
    *   *Trigger:* Continually sent while fighting a BBD to drive the live overlay.
    *   *Payload:* `{ "current": <int>, "max": 315, "active": <boolean> }`
*   **`phase_change`** (Zone Transitions)
    *   *Trigger:* When the player enters or leaves the designated bounding box (Min X: 1608, Max X: 1625, Min Y: 10085, Max Y: 10104).
    *   *Payload:* `{ "in_zone": <boolean> }`
*   **`player_attack`** (Attack Animation)
    *   *Trigger:* When the local player performs a recognized ranged attack animation (e.g., Crossbow: 4230, DHCB: 7617, TBow: 7615) inside the zone.
    *   *Payload:* `{}` (Empty JSON object)
*   **`loot_event`** (Drop Received)
    *   *Trigger:* When the game client parses a loot drop from a BBD.
    *   *Payload:* `{ "npc": "Brutal Black Dragon", "items": [{"id": <int>, "qty": <int>}, ...] }`
*   **`player_spawn`** (Census/Bot Detection)
    *   *Trigger:* When another player spawns inside the BBD cave.
    *   *Payload:* `{ "name": "<string>", "combat": <int>, "world": <int>, "gear": [<int>, <int>, ...] }`
*   **`shiny_spawn`** / **`notification`** (Visuals/Audio)
    *   *Triggers:* 1/2048 shiny spawn chance, or upon killing any dragon (or explicitly typing `::honk`).

---

## 2. Ingestion & Database Layer (Python Backend)
**Entry Script:** `bbd_tracker.py`
**Host:** `127.0.0.1:5000` (Flask)

The Python UI application runs a background Flask server to receive the Java payloads. Data is split into two primary storage mechanisms depending on the event type.

### A. High-Frequency Relational Data (SQLite)
**Database:** `combat_telemetry.db`
Only `combat_telemetry` (hitsplat) events are written here.

*   *Table Name:* `hitsplats`
*   *Schema:*
    *   `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
    *   `session_id` (TEXT) - e.g., "session_1700000000"
    *   `timestamp` (DATETIME) - ISO Format
    *   `damage` (INTEGER)
    *   `dragon_hp_before` (INTEGER)

*(Note: `player_spawn` events are routed to a separate `census_manager.py` which manages `census.db` for the bot-detection UI).*

### B. Session Aggregate Data (JSON Files)
**Storage Location:** `bbd_data/<session_id>.json`

State is held in memory while a session is active. When `phase_change` implies "AWAY" or when "STOP & SAVE" is clicked, the entire session state is dumped to a monolithic JSON file.

**JSON Schema:**
```json
{
    "session_id": "session_1700000000",
    "start_time": "2023-11-15T12:00:00.000000",
    "end_time": "2023-11-15T13:00:00.000000",
    "total_kills": 50,
    "total_attacks": 850,
    "active_seconds": 3600.5,
    "config": {
        "experiment_name": "Test Run",
        "mode": "Experimental",
        "weapon": "Dragon hunter crossbow",
        "head": "Masori mask (f)",
        "body": "Masori body (f)",
        "legs": "Masori chaps (f)",
        "hands": "Zaryte vambraces",
        "ammo": "Diamond dragon bolts (e)",
        "ring": "Venator Ring",
        "back": "Dizana's Quiver",
        "feet": "Pegasian boots",
        "prayer": "Rigour",
        "tele": "Xeric's Talisman",
        "bank": "Crafting cape",
        "bones": "Bonecrusher necklace",
        "pray_restore": "Prayer Potions"
    },
    "theoretical_stats": {
        "max_hit": 54.0,
        "exp_hit": 27.5,
        "dps": 8.1,
        "ttk": 40.2,
        "accuracy": 85.5,
        "rng_str": 150.0,
        "rng_acc": 200.0,
        "pray_bonus": 15.0
    },
    "loot_summary": {
        "Dragon bones": 50,
        "Black dragonhide": 100,
        "Rune platelegs": 2
    },
    "event_timeline": [
        {
            "timestamp": "2023-11-15T12:00:00.000000",
            "type": "session_start",
            "value": "Session Started (Experimental)"
        },
        {
            "timestamp": "2023-11-15T12:00:15.000000",
            "type": "phase",
            "value": "Phase Changed: KILLING"
        }
    ]
}
```

## Summary of Dependencies
If creating a new or alternative data ingestion client:
1.  It MUST emulate the HTTP POST envelope structure targeting `localhost:5000/event`.
2.  It MUST provide the `combat_telemetry` and `phase_change` (KILLING vs AWAY) payloads exactly as defined to ensure the `active_seconds` and MLR models generated by `normalize_sessions.py` remain accurate.
3.  Changes to the config dictionary must be mapped carefully, as `normalize_sessions.py` relies on one-hot encoding these specific string values (`config_weapon_Dragon hunter crossbow`, etc.).
