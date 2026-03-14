import os
import json

DATA_DIR = "bbd_data"

def patch_armor_and_names():
    if not os.path.exists(DATA_DIR):
        return print(f"Error: {DATA_DIR} folder not found.")

    patched_count = 0

    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"):
            continue
            
        filepath = os.path.join(DATA_DIR, filename)
        
        with open(filepath, 'r') as f:
            try:
                data = json.load(f)
            except Exception as e:
                print(f"Error reading {filename}: {e}")
                continue
        
        config = data.get("config", {})
        needs_save = False
        
        # 1. Split "armor" into head/body/legs
        if "armor" in config:
            armor_val = config["armor"]
            
            if armor_val == "Masori (f)":
                config["head"] = "Masori mask (f)"
                config["body"] = "Masori body (f)"
                config["legs"] = "Masori chaps (f)"
            elif armor_val == "God d'hide" or armor_val == "Blessed d'hide":
                config["head"] = "Saradomin coif"
                config["body"] = "Saradomin d'hide body"
                config["legs"] = "Saradomin chaps"
            else:
                # Fallback for anything weird
                config["head"] = f"{armor_val} head"
                config["body"] = f"{armor_val} body"
                config["legs"] = f"{armor_val} legs"
                
            # Remove the old monolithic key
            del config["armor"]
            needs_save = True

        # 2. Rename God d'hide hands/feet to Saradomin
        if config.get("hands") == "God d'hide bracers":
            config["hands"] = "Saradomin bracers"
            needs_save = True
            
        if config.get("feet") == "God d'hide boots":
            config["feet"] = "Saradomin d'hide boots"
            needs_save = True

        # Save back to disk if we changed anything
        if needs_save:
            data["config"] = config
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
            patched_count += 1
            print(f"Patched: {filename}")

    print(f"--- Done! Successfully patched and split armor for {patched_count} sessions. ---")

if __name__ == "__main__":
    patch_armor_and_names()