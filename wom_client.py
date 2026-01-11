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

    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")

    def _handle_response(self, response, context):
        if response.status_code == 200:
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
        clean_username = username.strip()
        url = f"{self.base_url}/players/{clean_username}"
        try:
            self.log(f"Updating: {clean_username}...")
            response = requests.post(url, headers=self.headers)
            if self._handle_response(response, clean_username):
                self.log(f"SUCCESS: {clean_username} updated.")
                return True
        except Exception as e:
            self.log(f"EXCEPTION: {e}")
        return False

    def get_player_snapshots(self, username, period="week"):
        """
        Fetches the history of snapshots for a player.
        Useful for calculating marginal gains between points in time.
        """
        clean_username = username.strip()
        # Endpoint: /players/:username/snapshots?period={period}
        url = f"{self.base_url}/players/{clean_username}/snapshots"
        params = {"period": period}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            return self._handle_response(response, clean_username)
        except Exception as e:
            self.log(f"EXCEPTION: {e}")
            return None