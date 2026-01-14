import sqlite3
import json
import os
import datetime
import config
from wom_client import WiseOldManClient

DB_FILE = "wom_master.db"

class MasterArchive:
    def __init__(self):
        self.client = WiseOldManClient()
        self.init_db()

    def init_db(self):
        """Create the master table if it doesn't exist."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # We store the raw JSON data so we can extract ANY skill later, 
        # even if we didn't think of it today.
        c.execute('''CREATE TABLE IF NOT EXISTS snapshots (
                        id INTEGER PRIMARY KEY,
                        username TEXT,
                        category TEXT,
                        timestamp DATETIME,
                        total_xp INTEGER,
                        ehp REAL,
                        data_json TEXT,
                        UNIQUE(username, timestamp)
                    )''')
        conn.commit()
        conn.close()

    def get_last_timestamp(self, username):
        """Finds the most recent snapshot we have locally."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT MAX(timestamp) FROM snapshots WHERE username = ?", (username,))
        result = c.fetchone()[0]
        conn.close()
        return result

    def sync_player(self, username, category):
        print(f"Syncing {username} ({category})...")
        
        last_sync = self.get_last_timestamp(username)
        snapshots = []

        if last_sync:
            print(f"   -> Found local data up to {last_sync}. Fetching newer...")
            # WOM API expects ISO dates. 
            # Note: We add 1 second to avoid grabbing the duplicate last entry
            snapshots = self.client.get_player_snapshots(username, start_date=last_sync)
        else:
            print(f"   -> No local data. Fetching FULL HISTORY (This may take time)...")
            # No start_date = Fetch everything
            snapshots = self.client.get_player_snapshots(username)

        if not snapshots:
            print("   -> Up to date.")
            return

        # Insert into DB
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        count = 0
        
        for snap in snapshots:
            try:
                ts = snap['createdAt']
                # Basic stats for easy SQL querying
                total_xp = snap['data']['skills']['overall']['experience']
                ehp = snap['data']['computed']['ehp']['value']
                
                c.execute('''INSERT OR IGNORE INTO snapshots 
                             (username, category, timestamp, total_xp, ehp, data_json) 
                             VALUES (?, ?, ?, ?, ?, ?)''',
                          (username, category, ts, total_xp, ehp, json.dumps(snap['data'])))
                if c.rowcount > 0:
                    count += 1
            except Exception as e:
                print(f"Error parsing snapshot: {e}")

        conn.commit()
        conn.close()
        print(f"   -> Added {count} new snapshots.")

    def run_sync(self):
        print("--- Starting Master Archive Sync ---")
        for category, players in config.PLAYER_LISTS.items():
            for username in players:
                self.sync_player(username, category)
        print("--- Sync Complete ---")

    def export_master_csv(self):
        """Exports the entire DB to a massive CSV for analysis."""
        import pandas as pd
        print("Exporting Master Dataset to CSV...")
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT username, category, timestamp, total_xp, ehp FROM snapshots ORDER BY timestamp", conn)
        conn.close()
        
        filename = f"reports/master_dataset_{datetime.datetime.now().strftime('%Y%m%d')}.csv"
        df.to_csv(filename, index=False)
        print(f"Saved to {filename}")

if __name__ == "__main__":
    archive = MasterArchive()
    archive.run_sync()
    archive.export_master_csv()