# High-Value Overlay Expansions & Analytics

## 1. The "Deja Vu" Sighting Callout
Since the `census.db` already tracks sighting counts and last-seen timestamps, surfacing this data immediately upon a player spawning adds a tangible layer of neighborhood awareness to the grind.

**Implementation Logic:**
* **Trigger:** Hook into the `player_spawn` event within `bbd_tracker.py`. 
* **Database Query:** When `census.log_sighting()` is called, modify the return payload to include the historical sighting count and the `last_seen` timestamp.
* **UI Routing:** If `sightings > 1`, route a specialized alert to the Tkinter UI thread.
* **Display:** Inject a high-visibility log into the existing `log_box` (e.g., `[14:32:01] Familiar Face: BotName123 (Seen 14x, last on 10/24)`). This could also flash briefly on the transparent `bbd_gui.py` overlay to ensure it isn't missed while focused on the game client.

## 2. The "Ghost" Pacer (Turnarounds & Splits)
Gamifying the grind through live split-tracking transforms an idle activity into an active optimization challenge. This relies entirely on parsing the historical JSON files stored in the `bbd_data/` directory.

**Implementation Logic - Kill Splits:**
* **Baseline Parsing:** On startup, parse the `event_timeline` array within every `session_*.json` file in `bbd_data/`. Filter for events where `"type": "kill"`. 
* **The "First Kill" Rule:** To accurately measure the time taken to achieve *N* kills, the calculation must discard the very first kill in the sequence, as the time spent engaging the first dragon is unknown. A 5-kill split is calculated as the timestamp difference between Kill *i* and Kill *i+5*.
* **Live Tracking:** Maintain a rolling buffer of kill timestamps during the active session. Calculate the rolling difference for milestones: 5, 10, 25, 50, 75, 100, 200, and 300 kills.
* **The Display:** Create a small `Kill Splits` window in `bbd_gui.py`. 
    * **Columns:** `Kills` | `Best` (All-Time) | `Sess` (Current Session Best).
    * If the current session best beats the all-time best, highlight the row in green.

**Implementation Logic - Bank Splits (Turnarounds):**
* **Baseline Parsing:** Scan the `bbd_data/` JSON files for `"type": "phase"` events. A "Bank Split" is defined as the time difference between `"Phase Changed: AWAY"` and the immediately following `"Phase Changed: KILLING"`.
* **The Display (Table):** Create a small `Bank Split` overlay window displaying a ranked list of the 5 shortest bank intervals achieved during the current session.
* **The Display (Live Matrix Race):** Integrate the bank split directly into the visual tick-matrix. When the phase shifts to `AWAY`, trigger an animated overlay on the matrix consisting of yellow squares representing the session's *shortest* bank sequence. As the live matrix ticks forward, the user visually races the ghost overlay to return to the `KILLING` phase before the ghost squares run out.

## 3. Calibrated Expected DPS (cDPS)
Theoretical DPS assumes a monster has infinite health, meaning every attack roll can fully express its damage. Because Brutal Black Dragons have exactly 315 HP, the final hit of every kill is almost always truncated (overkill). This structurally guarantees that actual DPS will always underperform standard theoretical DPS calculators.

**Implementation Logic:**
* **The Math:** To find the true benchmark, calculate the expected number of hits to reduce exactly 315 HP to 0. When a new loadout is saved in `bbd_tracker.py`, run a Monte Carlo simulation or Markov chain calculation using the input `Max Hit` and `Accuracy` to determine the "Calibrated Expected TTK" (cTTK). Calculate `cDPS = 315 / cTTK`.
* **Back-Propagation Strategy:** This new metric must be retroactively applied to ensure historical accuracy.
    1.  **`dps_profiles.json`:** Update the schema to include `cdps` and `cttk` alongside the raw theoretical numbers.
    2.  **Historical JSONs:** Write a one-time utility script to iterate through all files in `bbd_data/`. For each file, extract the `theoretical_stats` block, calculate the new `cdps` and `cttk`, inject them into the JSON, and save the file.
    3.  **UI Updates:** Modify the `Combat Telemetry` overlay in `bbd_gui.py` to calculate the Delta against the `cDPS` rather than the standard theoretical DPS, providing a mathematically sound baseline for evaluating combat luck.

## 4. Post-Hoc Analytics (Histograms)
These are standalone visual tools generated outside of the live tracking environment to analyze macro-behavior over the lifetime of the tracking project.

* **Session Length Distribution:** A Python script utilizing `matplotlib` or `seaborn` to parse the `duration_sec` from all `bbd_data/` JSONs. It renders a histogram (binned by 30-minute intervals) to visually demonstrate the most common natural session lengths, highlighting player fatigue limits.
* **Session Kills Distribution:** A corresponding histogram parsing the `total_kills` metric from the JSONs (binned by 10-kill intervals). This illustrates standard grind thresholds (e.g., showing a massive spike at exactly 100 kills if the player naturally stops at round numbers).