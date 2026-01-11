# main.py
import time
import config
from wom_client import WiseOldManClient

def main():
    client = WiseOldManClient()
    
    print("--- Wise Old Man Auto-Updater Started ---")
    print(f"User Agent: {config.USER_AGENT}")
    print(f"Update Interval: Every {config.CYCLE_INTERVAL} seconds")
    print(f"Politeness Delay: {config.REQUEST_DELAY} seconds per player")
    print("-----------------------------------------")

    if "YourDiscordName" in config.USER_AGENT:
        print("WARNING: Please update the USER_AGENT in config.py before running!")
        return

    while True:
        cycle_start_time = time.time()
        total_players_processed = 0

        # Iterate through every category in the config
        for category, players in config.PLAYER_LISTS.items():
            client.log(f"--- Processing List: {category} ---")
            
            for username in players:
                # Execute the update
                client.update_player(username)
                total_players_processed += 1
                
                # Polite delay between requests to avoid 429s/Bans
                time.sleep(config.REQUEST_DELAY)

        # Calculate time taken
        elapsed = time.time() - cycle_start_time
        client.log(f"--- Cycle Complete. Updated {total_players_processed} players in {elapsed:.2f} seconds. ---")
        
        # Sleep until the next cycle
        client.log(f"Sleeping for {config.CYCLE_INTERVAL} seconds...")
        print("-" * 40)
        time.sleep(config.CYCLE_INTERVAL)

if __name__ == "__main__":
    main()