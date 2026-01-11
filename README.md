# OSRS Wise Old Man Toolkit

A modular Python suite for automating OSRS player tracking, analyzing progression data, and generating visual reports using the Wise Old Man API.

## Setup

1. **Install Dependencies**
   ```bash
   pip install requests matplotlib pandas pytz

## Configuration `config.py`

- User Agent: Required. Update USER_AGENT with your app name or Discord handle.
- Player Lists: Define groups of players to track (e.g., "friends", "clan_mates", "suspects").
- Settings: Configure your timezone, update frequency, and chart styling preferences.

### Usage Instructions
```markdown
## Usage

### 1. Track (`main.py`)
*   **Purpose:** The engine. Runs a continuous loop to update player data on Wise Old Man.
*   **Command:** `python main.py`
*   **Note:** Keep this running in the background to build a history of data points (snapshots).

### 2. Analyze (`analyzer.py`)
*   **Purpose:** The processor. Fetches snapshot history to calculate marginal gains, skill variety, and estimated activity hours.
*   **Command:** `python analyzer.py`
*   **Output:** Generates CSV reports in the `reports/` folder.

### 3. Visualize (`visualizer.py`)
*   **Purpose:** The reporter. Converts the analyzed CSV data into high-resolution charts.
*   **Command:** `python visualizer.py`
*   **Output:** Generates PNG charts (Stacked Bars, Gantt Charts) in the `reports/` folder.

## File Structure

*   `config.py`: Central configuration for users, lists, and visuals.
*   `wom_client.py`: API wrapper handling requests and rate limits.
*   `main.py`: Script for continuous data collection.
*   `analyzer.py`: Script for data processing and logic.
*   `visualizer.py`: Script for chart generation.
*   `reports/`: Output directory for data and images.