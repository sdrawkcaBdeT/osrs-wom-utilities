# wom_client.py
import requests
import time
from datetime import datetime
import config

class WiseOldManClient:
    def __init__(self):
        self.base_url = config.BASE_URL
        self.headers = {
            "User-Agent": config.USER_AGENT,
            "Content-Type": "application/json"
        }
        
        # Add API Key if it exists in config
        if config.API_KEY:
            self.headers["x-api-key"] = config.API_KEY

    def log(self, message):
        """Helper to print messages with a timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")

    def _handle_response(self, response, context):
        """Internal helper to handle status codes."""
        # UPDATE: Added 201 to success codes (for new players)
        if response.status_code in [200, 201]:
            return response.json()
        elif response.status_code == 404:
            self.log(f"FAILED: {context} not found.")
        elif response.status_code == 429:
            self.log(f"RATE LIMITED: Pausing for 60s.")
            time.sleep(60)
        elif response.status_code == 500:
            self.log(f"SERVER ERROR: WOM API issue.")
        else:
            self.log(f"ERROR: Status {response.status_code} - {response.text}")
        return None

    def update_player(self, username):
        """POST /players/:username - Update player data."""
        clean_username = username.strip()
        url = f"{self.base_url}/players/{clean_username}"
        try:
            self.log(f"Updating: {clean_username}...")
            response = requests.post(url, headers=self.headers)
            
            # Check response using the updated handler
            data = self._handle_response(response, clean_username)
            if data:
                # Try to get the latest snapshot date for logging
                latest = data.get('latestSnapshot', {}).get('createdAt', 'New Entry')
                self.log(f"SUCCESS: {clean_username} updated. (Snapshot: {latest})")
                return True
        except Exception as e:
            self.log(f"EXCEPTION: {e}")
        return False

    def get_player_details(self, username):
        """GET /players/:username - Get current stats/bosses."""
        clean_username = username.strip()
        url = f"{self.base_url}/players/{clean_username}"
        try:
            response = requests.get(url, headers=self.headers)
            return self._handle_response(response, clean_username)
        except Exception as e:
            self.log(f"EXCEPTION: {e}")
            return None

    def get_player_gains(self, username, period="week"):
        """GET /players/:username/gained?period=week - Get gains."""
        clean_username = username.strip()
        url = f"{self.base_url}/players/{clean_username}/gained"
        params = {"period": period}
        try:
            response = requests.get(url, headers=self.headers, params=params)
            return self._handle_response(response, clean_username)
        except Exception as e:
            self.log(f"EXCEPTION: {e}")
            return None

    # INDENTATION FIXED HERE
    def get_player_snapshots(self, username, period=None, start_date=None, end_date=None):
        """
        Fetches snapshots. 
        Supports 'period' (e.g., 'week') OR 'start_date'/'end_date' (ISO strings).
        Handles pagination automatically to get ALL results for the criteria.
        """
        clean_username = username.strip()
        url = f"{self.base_url}/players/{clean_username}/snapshots"
        
        all_snapshots = []
        offset = 0
        limit = 50 
        
        try:
            while True:
                params = {
                    "limit": limit,
                    "offset": offset
                }
                
                # Add conditional filters
                if period:
                    params["period"] = period
                if start_date:
                    params["startDate"] = start_date
                if end_date:
                    params["endDate"] = end_date
                
                response = requests.get(url, headers=self.headers, params=params)
                data = self._handle_response(response, clean_username)
                
                if not data:
                    break
                
                all_snapshots.extend(data)
                
                if len(data) < limit:
                    break
                
                offset += limit
                time.sleep(0.3) # Polite delay during heavy pagination

            return all_snapshots

        except Exception as e:
            self.log(f"EXCEPTION: {e}")
            return None