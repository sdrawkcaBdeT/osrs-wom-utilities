# OSRS Brutal Black Dragon Telemetry & Bot Census Tracker

## Overview
This project is a comprehensive telemetry, orchestration, and analytics system designed to track in-game combat data for Old School RuneScape (OSRS), specifically focused on Brutal Black Dragons. It unifies real-time event tracking via RuneLite, dynamic session state management, and external player data fetched from the Wise Old Man (WOM) API to maintain a roster of sighted players and potential bot accounts.

## System Architecture

The ecosystem relies on a multi-layered architecture that separates data ingestion, state management, storage, and visualization:

* **The Source (RuneLite Client):** A Java-based plugin (`BBDTrackerPlugin.java`) listens to in-game actions such as hitsplats, loot drops, and NPC spawns. These events are formatted as JSON payloads and transmitted to a local server via HTTP and high-speed UDP connections.
* **The Aggregator (Tracker Server):** The primary Python tracking server (`bbd_tracker.py`) ingests live game telemetry streams and unifies them with user UI inputs to manage the active session state.
* **The Storage Layer:** High-fidelity combat data (e.g., individual ticks and damage) is persisted into an SQLite database (`combat_telemetry.db`), while holistic session summaries are saved as JSON files in the local data directory.
* **The Observers (Pipelines & GUI):** A transparent Tkinter-based overlay (`bbd_gui.py`) constantly polls the local storage files to render live statistics over the game window. In the background, independent pipelines execute at regular intervals to pull live Grand Exchange prices and Wise Old Man data for market and demographic enrichment.

## Core Components

* **`datahub.py`**: The central command-line orchestrator that launches various tracking, archiving, and visualization tasks.
* **`bbd_tracker.py`**: The local HTTP/UDP server and application controller that manages the primary combat tracking interface.
* **`pipeline.py`**: A background service that runs a sequential batch of data enrichment scripts every five minutes.
* **`census_manager.py`**: Tracks and categorizes sighted players to build a dynamic local database (`census.db`) of suspected bots and real players.
* **`main.py` & `archiver.py`**: The Wise Old Man auto-updater loop and archiving service. `main.py` iterates through a tracked list of users, querying the WOM API while respecting rate limits, and `archiver.py` stores the historical snapshots.

## Configuration & Environment Variables

System-wide settings and secret keys are managed through a combination of environment variables and the `config.py` file.

### 1. Environment Variables
You must create a `.env` file in the root directory to store your sensitive credentials. 
* **`WOM_API_KEY`**: Your authentication key for the Wise Old Man V2 API.

### 2. General Configuration (`config.py`)
Several crucial parameters must be reviewed in `config.py` before running the pipeline:
* **`USER_AGENT`**: You must supply a valid application identifier (e.g., your Discord username) to comply with the WOM API terms of service.
* **`CYCLE_INTERVAL`**: Defines the update frequency for the WOM polling loop in seconds. The default is `3600` (1 hour).
* **`REQUEST_DELAY`**: The hardcoded pause between WOM API calls (defaulting to 5 seconds) to ensure the client avoids rate limit blocks (HTTP 429 errors).
* **Player Lists**: The `SEED_LISTS` dictionary contains the hardcoded baseline of `real_ones` and `suspected_bots`, which the system automatically merges with dynamic sightings from the SQLite census database upon startup.