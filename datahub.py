"""
OSRS DATAHUB (The Orchestrator)
================================

This script acts as the central command center for the OSRS Bot Detective Suite.

USAGE EXAMPLES:
-------------------------------------------------------------------------
1. ACTION MODE (When you sit down to play)
   > python datahub.py play
   * Launches BOTH the Time Tracker (tracker.py) and the BBD Lab (bbd_tracker.py).

2. BACKGROUND MODE (Always running)
   > python datahub.py engine
   * Launches the WOM Updater (main.py) in the background.

3. REVIEW MODE (Generate all visualizations)
   > python datahub.py charts
   * Runs the FULL pipeline:
     1. Syncs Master Archive (WOM History).
     2. Analyzes WOM Data (Gains, Consistency, Suspects).
     3. Generates WOM Charts (Gantt, Stacked Bar, Line).
     4. Generates BBD Experiment Charts (Velocity, Phase, DPS).

   > python datahub.py charts --quick
   * Generates all charts but skips the slow Archive Sync step.
-------------------------------------------------------------------------
"""

import argparse
import sys
import subprocess
import time
from datetime import datetime

# Import Suite Modules
import config
from wom_client import WiseOldManClient
import archiver
import analyzer
import visualizer
import bbd_visualizer

def log(msg):
    print(f"[\033[96mDATAHUB\033[0m] {msg}")

# --- HELPER: LAUNCH PROCESS ---
def launch_process(script_name):
    """Launches a python script in a detached process."""
    try:
        if sys.platform == "win32":
            subprocess.Popen([sys.executable, script_name], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([sys.executable, script_name])
        log(f"Launched: {script_name}")
    except Exception as e:
        print(f"Error launching {script_name}: {e}")

# --- COMMAND: PLAY (Action Mode) ---
def start_session_tools():
    log("Initializing Session Tools...")
    launch_process("tracker.py")      # The Clock
    launch_process("bbd_tracker.py")  # The Lab

# --- COMMAND: ENGINE (Background Mode) ---
def start_engine():
    log("Igniting the Engine...")
    launch_process("main.py")         # The Updater

# --- COMMAND: CHARTS (Review Mode) ---
def run_full_suite(skip_archive=False):
    """
    Runs every analysis tool available in the suite.
    """
    start_time = time.time()
    
    # --- PART 1: WISE OLD MAN PIPELINE ---
    log("=== STARTING WOM PIPELINE ===")
    
    # 1. Archive Sync
    if not skip_archive:
        log("Step 1/4: Syncing Master Archive...")
        try:
            archive = archiver.MasterArchive()
            archive.run_sync()
        except Exception as e:
            print(f"Archiver failed: {e}")
    else:
        log("Step 1/4: Skipping Archive Sync.")

    # 2. Analyze
    log("Step 2/4: Running Analyzer...")
    try:
        timestamp_suffix = datetime.now().strftime('%Y%m%d_%H%M')
        period = "week"
        
        # UPDATE: New function name, no client argument
        data_cache = analyzer.fetch_local_data(period)
        
        if data_cache:
            analyzer.analyze_marginal_gains(data_cache, timestamp_suffix, period)
            analyzer.analyze_consistency_variety(data_cache, timestamp_suffix, period)
            analyzer.estimate_activity_log(data_cache, timestamp_suffix, period)
            analyzer.generate_timeseries_data(data_cache, timestamp_suffix, period)
            analyzer.analyze_detailed_xp_breakdown(data_cache, timestamp_suffix, period)
        else:
            print("WOM Analysis Aborted: No data fetched.")
    except Exception as e:
        print(f"Analyzer failed: {e}")

    # 3. Visualize (WOM)
    log("Step 3/4: Generating WOM Visuals...")
    try:
        # UPDATE: New function names matching visualizer.py overhaul
        visualizer.draw_variety_charts()       # Plural
        visualizer.draw_heatmap_gantt()        # Renamed from activity_gantt
        visualizer.draw_annotated_line_charts() # Renamed from faceted_cumulative
    except Exception as e:
        print(f"WOM Visualizer failed: {e}")

    # --- PART 2: BBD EXPERIMENT PIPELINE ---
    log("=== STARTING BBD PIPELINE ===")
    
    # 4. Visualize (BBD)
    log("Step 4/4: Generating BBD Experiment Visuals...")
    try:
        sessions = bbd_visualizer.load_sessions()
        if sessions:
            log(f"Found {len(sessions)} sessions.")
            bbd_visualizer.draw_velocity_comparison(sessions)
            bbd_visualizer.draw_phase_gantt(sessions)
            bbd_visualizer.draw_kill_time_histogram(sessions)
        else:
            log("No BBD sessions found.")
    except Exception as e:
        print(f"BBD Visualizer failed: {e}")

    elapsed = time.time() - start_time
    log(f"FULL SUITE COMPLETE in {elapsed:.2f} seconds.")
    log(f"All charts available in /reports")

# --- CLI HANDLER ---
def main():
    parser = argparse.ArgumentParser(description="OSRS Data Orchestrator")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # 1. Play
    subparsers.add_parser('play', help='Launch Tracker + BBD Lab GUIs')

    # 2. Engine
    subparsers.add_parser('engine', help='Start the continuous tracking engine')
    
    # 3. Charts
    parser_charts = subparsers.add_parser('charts', help='Generate ALL reports and visualizations')
    parser_charts.add_argument('--quick', action='store_true', help='Skip Archive Sync')

    # 4. Sync (Utility)
    subparsers.add_parser('sync', help='Only run the WOM Archiver')

    args = parser.parse_args()

    if args.command == 'play':
        start_session_tools()
    elif args.command == 'engine':
        start_engine()
    elif args.command == 'charts':
        run_full_suite(skip_archive=args.quick)
    elif args.command == 'sync':
        log("Running Manual Sync...")
        archiver.MasterArchive().run_sync()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()