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

## 3. Monte Carlo cDPS Analytics Engine

a. Primary Objective
To build a standalone Python analytics tool that simulates 1,000,000 Brutal Black Dragon encounters per saved loadout and renders a cinematic, full-bleed probability curve. Secondary data (the visual equipment grid and mathematical ledger) will be injected as floating HUD overlays to maximize the plotting space.

b. Directory Architecture

    Input Data: dps_profiles.json and local JSON session files.

    Asset Library: icons/ directory (containing 32x32 PNGs).

    Output Destination: analytics_output/monte_carlo_cdps/.

c. Data Ingestion & Harmonization

    Constructs a "Full Base Loadout" by merging the user's static gear constants (Dragon hunter crossbow, Twisted buckler, Necklace of anguish) with dynamic profile variables.

    Explicitly filters out non-combat utility variables to keep the visual grid focused purely on DPS-impacting gear.

d. The Visual Canvas (The Full-Bleed HUD Layout)

    Dimensions: Root-two aspect ratio (1.414:1). For example, a high-resolution base figure size of 14.14 inches by 10 inches.

    The Main Plot (Full Canvas): * A smooth KDE curve and histogram stretching edge-to-edge across the entire figure.

        Dark cinematic theme (Background: #0A0A0A, Text: #FFFFFF, Primary Data: Glowing Cyan/Green).

        Vertical dashed line indicating the peak cTTK.

    HUD Element 1: The Visual Loadout Grid (Top-Left Anchor):

        A borderless, 10-slot cross-formation grid of 32x32 PNG icons.

        Anchored to the top-left coordinate space of the plot area, utilizing a subtle, semi-transparent background box to ensure the icons pop without entirely blocking the grid lines behind them.

    HUD Element 2: The Truth Ledger (Top-Right Anchor):

        A matching semi-transparent bounding box anchored to the top-right.

        Displays the direct side-by-side comparison of Theoretical vs. Calibrated metrics (DPS, Expected Hit, TTK).

    e. The Logging & Terminal Experience
The script will feature a clean, verbose, and professional terminal output so you can monitor exactly what the engine is processing, which is critical when iterating through millions of simulations.

    It will announce the current profile being processed.

    It will display a progress indicator (e.g., [1/4]).

    It will confirm when the Monte Carlo simulation finishes and when the rendering begins.

    It will output the exact file path of the successfully saved asset.

    f. Output Specifications & File Naming

    Format: .png at 300 DPI.

    Naming Convention: [base_plot_name]_[loadout_signature]_[yyyymmddhhmmss].png

        Example: rng_curve_8a2b4f1c_20260328223637.png

    g. Future-Proofing for Live Data
Because the main plot commands the entire canvas, overlaying the live session data later will be seamless. The actual kill times will plot naturally along the bottom X-axis beneath the curve, completely undisturbed by the HUD elements floating in the top corners.

## 4. Post-Hoc Analytics (Histograms)
These are standalone visual tools generated outside of the live tracking environment to analyze macro-behavior over the lifetime of the tracking project.

* **Session Length Distribution:** A Python script utilizing `matplotlib` or `seaborn` to parse the `duration_sec` from all `bbd_data/` JSONs. It renders a histogram (binned by 30-minute intervals) to visually demonstrate the most common natural session lengths, highlighting player fatigue limits.
* **Session Kills Distribution:** A corresponding histogram parsing the `total_kills` metric from the JSONs (binned by 10-kill intervals). This illustrates standard grind thresholds (e.g., showing a massive spike at exactly 100 kills if the player naturally stops at round numbers).

### 5. The TTK Probability Distribution (The "RNG Curve")

**Objective:** To visualize the frequency of Time-to-Kill (TTK) outcomes across the dataset, mapping the true RNG variance and consistency of a specific gear setup.

**Data Requirements:** A single-dimensional array containing the final kill times (in seconds) of all 1,000,000 simulated encounters.

**Axis Mapping:**
* **X-Axis:** Time to Kill (Seconds).
* **Y-Axis:** Probability Density / Frequency (Percentage of kills that landed on that specific time).

**Visual Characteristics:**
* **The Shape:** A prominently right-skewed distribution.
* **The Left Wall:** A sharp, hard boundary on the left side of the X-axis, representing the absolute mathematical minimum TTK (perfect RNG).
* **The Right Tail:** A long, tapering tail stretching to the right, representing extreme dry streaks and the infinite possibility of rolling zeroes. 
* **The Peak:** The highest point of the density curve, which perfectly aligns with the Calibrated TTK (`cTTK`).

### 6. The HP Drain "Spaghetti Plot"

**Objective:** To illustrate the pacing of individual fights, demonstrating how damage RNG fluctuates moment-to-moment before converging on the mathematical average.

**Data Requirements:** Step-by-step HP logs (Remaining HP vs. Time) for a random subsample of 100 kills, alongside the calculated step-by-step mean trajectory of the entire 1,000,000-kill dataset.

**Axis Mapping:**
* **X-Axis:** Time Elapsed (Seconds).
* **Y-Axis:** Target Remaining Health (Starting at Max HP, descending to 0).

**Visual Characteristics:**
* **The Chaos Web:** 100 faint, highly transparent background lines plotting the raw subsample. These lines will show jagged, vertical plummets (armor-piercing procs) and flat horizontal shelves (strings of missed attacks).
* **The Core Trajectory:** A single, thick, high-contrast line cutting directly through the center of the web. This represents the absolute mathematical average pacing of the fight. The point where this line intersects the X-axis (0 HP) is the exact `cTTK`.

### 7. The Realized Damage Distribution

**Objective:** To dissect the raw dice rolls of the simulation, visualizing weapon accuracy, special attack proc rates, and the mathematical suppression caused by the "Overkill Tax."

**Data Requirements:** A massive array containing every single individual damage hitsplat rolled across all simulated attacks (tens of millions of data points).

**Axis Mapping:**
* **X-Axis:** Damage Dealt per Attack (0 up to the Absolute Max Hit).
* **Y-Axis:** Total Count / Frequency.

**Visual Characteristics:**
* **The Zero Spike:** A massive, towering bar at `0`, representing all missed attacks and successful zero-damage rolls based on the weapon's accuracy profile.
* **The Standard Plateau:** A perfectly flat, uniform block of bars spanning from `1` to the weapon's standard Max Hit, representing the equal probability of rolling any number on a successful hit.
* **The Proc Shelf:** A distinct, sudden drop-off into a lower shelf of bars extending past the standard max hit. This maps the exact probability and damage range of special mechanics (e.g., the 10% chance to roll up to the Diamond Bolt maximum).
* **The Overkill Taper:** A subtle but critical downward slope affecting the highest damage bars on both the plateau and the shelf. This visually proves the Overkill Tax: the highest possible damage numbers are rolled slightly less frequently overall because they are mathematically impossible to achieve during the final moments of a fight when the monster's HP is lower than the weapon's max hit.