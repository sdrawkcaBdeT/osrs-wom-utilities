import time
import subprocess
import os

# The scripts we want to run automatically in sequence
PIPELINE_SCRIPTS =[
    "get_gpph.py",
    "get_gpph_prices.py",
    "enrich_gpph.py",
    "wealth_engine.py",
    "normalize_sessions.py",
    "daily_report.py",  # <--- NEW ADDITION
    "market_index_builder.py"
]

def run_pipeline():
    print(f"\n--- Running Data Pipeline at {time.strftime('%I:%M %p')} ---")
    for script in PIPELINE_SCRIPTS:
        if os.path.exists(script):
            print(f"Executing {script}...")
            # Run the script and wait for it to finish
            subprocess.run(["python", script], check=True)
        else:
            print(f"Warning: {script} not found!")
    print("--- Pipeline Cycle Complete ---")

if __name__ == "__main__":
    print("Starting Background Data Pipeline...")
    while True:
        run_pipeline()
        # Sleep for 5 minutes
        time.sleep(300)