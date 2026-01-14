"""
OSRS DATAHUB (The Orchestrator)
================================

This script acts as the central command center for the OSRS Bot Detective Suite.
It coordinates the Engine, Archiver, Analyzer, and Visualizer.

USAGE EXAMPLES:
-------------------------------------------------------------------------
1. Start the Tracker (Background Mode)
   > python datahub.py engine
   * Launches main.py in a separate window to track players 24/7.

2. Generate Full Report (The "Video Ready" Command)
   > python datahub.py report
   * Step 1: Syncs Master Archive (Downloads all new history).
   * Step 2: Analyzes data (Marginal gains, variety, activity logs).
   * Step 3: Visualizes data (Generates PNG charts in /reports).

3. Generate Quick Report (Skip Archiving)
   > python datahub.py report --quick
   * Skips the slow archive sync. Useful if you just ran a sync recently
     and want to regenerate charts with slightly different settings.

4. Manual Archive Sync
   > python datahub.py sync
   * Only updates the local SQLite database with the latest WOM data.
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

def log(msg):
    print(f"[\033[96mDATAHUB\033[0m] {msg}")

# --- COMMAND: START ENGINE ---
def start_engine():
    """
    Launches main.py in a separate process.
    On Windows, this opens a new window. On Mac/Linux, it runs in background.
    """
    log("Igniting the Engine (main.py)...")
    try:
        # Use Popen to run it without blocking DataHub
        if sys.platform == "win32":
            subprocess.Popen([sys.executable, "main.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([sys.executable, "main.py"])
        log("Engine started. It will run continuously in the background.")
    except Exception as e:
        print(f"Error starting engine: {e}")

# --- COMMAND: RUN PIPELINE ---
def run_pipeline(skip_archive=False):
    """
    The 'One-Click' Report Generator.
    1. Syncs Master Archive.
    2. Runs Analyzer Suite.
    3. Runs Visualizer Suite.
    """
    start_time = time.time()
    
    # 1. ARCHIVE SYNC
    if not skip_archive:
        log("Step 1/3: Syncing Master Archive...")
        try:
            archive = archiver.MasterArchive()
            archive.run_sync()
            # Optional: Export master CSV every time?
            # archive.export_master_csv() 
        except Exception as e:
            print(f"Archiver failed: {e}")
            return
    else:
        log("Step 1/3: Skipping Archive Sync.")

    # 2. ANALYZE
    log("Step 2/3: Running Analysis Suite...")
    try:
        client = WiseOldManClient()
        timestamp_suffix = datetime.now().strftime('%Y%m%d_%H%M')
        period = "week" # Default for reports
        
        # Fetch Data (In-Memory)
        # We use analyzer's logic to get the fresh snapshot cache
        data_cache = analyzer.fetch_all_data(client, period)
        
        if data_cache:
            # Run all analysis functions directly (bypassing the menu)
            analyzer.analyze_marginal_gains(data_cache, timestamp_suffix, period)
            analyzer.analyze_consistency_variety(data_cache, timestamp_suffix, period)
            analyzer.estimate_activity_log(data_cache, timestamp_suffix, period)
            analyzer.generate_timeseries_data(data_cache, timestamp_suffix, period)
            analyzer.analyze_detailed_xp_breakdown(data_cache, timestamp_suffix, period)
        else:
            print("Analysis Aborted: No data fetched.")
            return
    except Exception as e:
        print(f"Analyzer failed: {e}")
        return

    # 3. VISUALIZE
    log("Step 3/3: Generating Visuals...")
    try:
        # Run all visualization functions directly
        visualizer.draw_variety_chart()
        visualizer.draw_activity_gantt()
        visualizer.draw_faceted_cumulative_charts()
    except Exception as e:
        print(f"Visualizer failed: {e}")
        return

    elapsed = time.time() - start_time
    log(f"Pipeline Complete in {elapsed:.2f} seconds.")
    log(f"Check the /reports folder for your content.")

# --- CLI HANDLER ---
def main():
    parser = argparse.ArgumentParser(description="OSRS Data Orchestrator")
    
    # Define commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Command: engine
    subparsers.add_parser('engine', help='Start the continuous tracking engine (main.py)')
    
    # Command: report
    parser_report = subparsers.add_parser('report', help='Run the full analysis & visualization pipeline')
    parser_report.add_argument('--quick', action='store_true', help='Skip the Archive Sync step (Faster)')

    # Command: sync
    subparsers.add_parser('sync', help='Only run the Archiver')

    args = parser.parse_args()

    if args.command == 'engine':
        start_engine()
    elif args.command == 'report':
        run_pipeline(skip_archive=args.quick)
    elif args.command == 'sync':
        log("Running Manual Sync...")
        archiver.MasterArchive().run_sync()
    else:
        # If no args, print help
        parser.print_help()

if __name__ == "__main__":
    main()