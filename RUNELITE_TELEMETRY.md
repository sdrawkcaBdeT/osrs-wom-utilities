# Live Game Tracking Architecture

This document details the real-time telemetry pipeline connecting the RuneLite game client to the local Python tracking server.

## 1. Dual-Stream Networking (HTTP vs. UDP)

The Java-based RuneLite plugin (`BBDTrackerPlugin.java`) transmits in-game events to the Python server using two distinct network protocols to balance reliability with performance:

* **HTTP Pipe (Port 5000):** Used for critical, discrete game events that must not be lost over the network. The plugin sends asynchronous POST requests to `http://127.0.0.1:5000/event` for events like loot drops, player spawns, and zone changes.
* **UDP Pipe (Port 5005):** A fast, fire-and-forget socket connection used for high-frequency data. The plugin uses a `DatagramSocket` to continuously stream 600ms tick heartbeats and real-time GP (gold) deltas without blocking the game thread. Notably, the Java plugin also "shadows" all HTTP payloads to the UDP pipe to ensure data availability.

## 2. JSON Payload Structure

Events are formatted as JSON strings before transmission. There are two primary payload structures depending on the event source:

* **Standard Events (HTTP & UDP Shadow):** Handled via the `sendPayload` method, these encapsulate the event data within a `payload` wrapper.
    ```json
    {
      "event": "loot_event",
      "payload": {
        "npc": "Brutal Black Dragon",
        "items": [{"id": 536, "qty": 1}]
      }
    }
    ```
* **Direct Telemetry (UDP Only):** Sent via the `sendUdp` method, these are flat JSON objects used for rapid state updates.
    ```json
    {
      "event": "tick_heartbeat",
      "tick": 1245,
      "state": "attack"
    }
    ```

## 3. Event Processing in `bbd_tracker.py`

The Python server (`bbd_tracker.py`) captures and routes these streams using different mechanisms.

### Flask Server (HTTP Handler)
A Flask application listens on port 5000 and processes incoming POST requests. 
* **Direct Processing:** High-priority actions bypass the UI thread. For example, `combat_telemetry` events (hitsplats) are instantly written directly into the `combat_telemetry.db` SQLite database. Similarly, `notification` events trigger local audio playback via Pygame.
* **Delegation:** Standard game events (like `loot_event`, `player_spawn`, and `phase_change`) are routed back to the main Tkinter UI thread using `app_instance.after(0, ...)` to safely update GUI elements and local variables.

### Background Listener (UDP Handler)
A background thread runs `start_udp_listener()`, catching datagrams on port 5005 and placing them into a thread-safe `queue`. The main application loop checks this queue continuously via `process_udp_queue()`.
* **The Session Tape:** As `tick_heartbeat` and `net_profit_delta` events arrive, they are assembled into a RAM buffer called `session_tape` (a dictionary mapping tick numbers to state and gold values). This ensures that rapid economy changes are accurately tied to the exact server tick they occurred on.
* **Rolling Stream:** All UDP payloads are also appended to a 50-item rolling list (`udp_stream`) stored in the global `LIVE_HP_STATE` dictionary, which can be queried for live matrix rendering.