# Wise Old Man (WOM) Data Pipeline

This document outlines the architecture and data flow for the Wise Old Man integration within the tracker. The pipeline is responsible for automatically requesting stat updates from the WOM API, managing rate limits, and archiving the resulting historical snapshots into a local master database.

## 1. The Auto-Updater (`main.py`)

The auto-updater functions as a continuous background service. Upon initialization, it loads the configured player lists (categorized by groups such as `real_ones` and `suspected_bots`). 

The core loop performs the following actions:
* Iterates through every player in the tracked categories.
* Calls the `update_player` method via the `WiseOldManClient`, which sends a POST request to the API to refresh the player's stats.
* Sleeps for a configured `REQUEST_DELAY` between each individual player to ensure politeness.
* Once all players are processed, the script sleeps for the duration of the `CYCLE_INTERVAL` (typically an hour) before beginning the next update cycle.

## 2. Rate Limit & Error Handling (`wom_client.py`)

Interacting with the external WOM API requires strict adherence to rate limits. The `WiseOldManClient` class centrally manages HTTP requests and enforces safety parameters:
* **Headers:** It securely passes the user agent and API key (if provided) from the configuration to authenticate the application.
* **429 Handling:** If the application exceeds the API's rate limits and receives an HTTP 429 status code, the client's internal `_handle_response` method intercepts it and forces the script to pause for 60 seconds before continuing.
* **Pagination Delays:** When fetching large histories in `get_player_snapshots`, a hardcoded `0.3` second delay is inserted between page requests to prevent overwhelming the API during heavy pagination.

## 3. Data Archival (`archiver.py`)

While `main.py` requests the generation of new data, `archiver.py` is responsible for pulling those snapshots down and storing them permanently for local analysis.

The `MasterArchive` class handles this storage process:
* **The Master Database:** Data is persisted in a local SQLite database named `wom_master.db`. The schema includes the player's username, category, snapshot timestamp, total experience, Efficient Hours Played (EHP), and the complete raw JSON data payload.
* **Incremental Syncing:** To avoid downloading redundant data, `sync_player` queries the local database to find the most recent snapshot timestamp for a given user. It then instructs the WOM client to only fetch snapshots created after that date.
* **Start Date Constraint:** If no local history exists for a player, the archiver falls back to the `PROJECT_START_DATE` defined in the configuration to prevent downloading years of irrelevant historical data.
* **Export Capability:** The archiver includes a utility to export the entire `snapshots` table into a flattened CSV format (`master_dataset_YYYYMMDD.csv`) for external data science tools like Pandas.