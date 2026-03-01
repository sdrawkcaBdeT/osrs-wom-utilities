import sqlite3
import datetime
import json
import os
import threading

DB_FILE = "census.db"

class CensusManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(DB_FILE)

    def init_db(self):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("PRAGMA journal_mode=WAL;")
        
        c.execute('''CREATE TABLE IF NOT EXISTS roster (
                        username TEXT PRIMARY KEY,
                        status TEXT DEFAULT 'NEW',
                        combat_level INTEGER,
                        first_seen DATETIME,
                        latest_seen DATETIME,
                        total_sightings INTEGER DEFAULT 0,
                        notes TEXT
                    )''')

        c.execute('''CREATE TABLE IF NOT EXISTS sightings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT,
                        session_id TEXT,
                        world INTEGER,
                        timestamp DATETIME,
                        gear_json TEXT,
                        FOREIGN KEY(username) REFERENCES roster(username)
                    )''')
        
        conn.commit()
        conn.close()

    def log_sighting(self, session_id, name, combat_level, world, gear_ids):
        """
        Logs a sighting. Handles the logic for "Recurring Trash".
        """
        with self.lock: 
            conn = self.get_connection()
            c = conn.cursor()
            now = datetime.datetime.now()

            # 1. Check if we have already logged this player in THIS session
            c.execute('''SELECT id FROM sightings 
                         WHERE username = ? AND session_id = ? AND world = ?''', 
                      (name, session_id, world))
            
            is_duplicate = c.fetchone() is not None

            # 2. Get current Roster status
            c.execute("SELECT total_sightings, status FROM roster WHERE username = ?", (name,))
            row = c.fetchone()

            roster_status = 'NEW'
            total_sightings = 0

            if row:
                total_sightings = row[0]
                roster_status = row[1]
                
                # Resurrect trash if it's a new session (and not a duplicate causing the check)
                if roster_status == 'TRASH' and not is_duplicate:
                    c.execute("UPDATE roster SET status = 'NEW' WHERE username = ?", (name,))
                    roster_status = 'NEW'

                # OPTIONAL FIX: Only increment total_sightings if NOT a duplicate
                # Otherwise, render flickering inflates this number rapidly.
                if not is_duplicate:
                    c.execute('''UPDATE roster 
                                 SET latest_seen = ?, total_sightings = total_sightings + 1, combat_level = ?
                                 WHERE username = ?''', 
                              (now, combat_level, name))
                else:
                    # Just update the timestamp if it's a duplicate
                    c.execute("UPDATE roster SET latest_seen = ? WHERE username = ?", (now, name))
            else:
                # New Player
                c.execute('''INSERT INTO roster (username, status, combat_level, first_seen, latest_seen, total_sightings)
                             VALUES (?, 'NEW', ?, ?, ?, 1)''', 
                          (name, combat_level, now, now))
                total_sightings = 1

            # 3. Log Sighting (Only if not duplicate)
            if not is_duplicate:
                c.execute('''INSERT INTO sightings (username, session_id, world, timestamp, gear_json)
                             VALUES (?, ?, ?, ?, ?)''',
                          (name, session_id, world, now, json.dumps(gear_ids)))

            conn.commit()
            conn.close()
            
            return {
                "status": "logged",
                "roster_status": roster_status,
                "total_sightings": total_sightings
            }

    def update_status(self, username, new_status):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("UPDATE roster SET status = ? WHERE username = ?", (new_status, username))
        conn.commit()
        conn.close()

    def get_inbox(self, session_start_time=None):
        """
        Returns NEW players.
        If session_start_time is provided, filters out players NOT seen in this session.
        """
        conn = self.get_connection()
        c = conn.cursor()
        
        query = "SELECT username, combat_level, total_sightings, latest_seen, status, notes FROM roster WHERE status = 'NEW'"
        params = []

        if session_start_time:
            query += " AND latest_seen >= ?"
            params.append(session_start_time)

        query += " ORDER BY latest_seen DESC"

        c.execute(query, tuple(params))
        data = c.fetchall()
        conn.close()
        return data

    def get_category(self, status):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''SELECT username, combat_level, total_sightings, latest_seen, status, notes 
                     FROM roster 
                     WHERE status = ? 
                     ORDER BY latest_seen DESC''', (status,))
        data = c.fetchall()
        conn.close()
        return data

    def export_suspects_to_config(self):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT username FROM roster WHERE status = 'SUSPECT'")
        names = [row[0] for row in c.fetchall()]
        conn.close()
        return names