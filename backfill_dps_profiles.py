import os
import json

# --- CONFIG ---
DATA_DIR = "bbd_data"
DPS_PROFILES_FILE = "dps_profiles.json"

def load_dps_profiles():
    if os.path.exists(DPS_PROFILES_FILE):
        try:
            with open(DPS_PROFILES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_dps_profiles(profiles):
    with open(DPS_PROFILES_FILE, 'w') as f:
        json.dump(profiles, f, indent=4)

def main():
    print("--- DPS Profile Backfiller Wizard ---")
    
    if not os.path.exists(DATA_DIR):
        return print(f"Error: {DATA_DIR} not found.")

    profiles = load_dps_profiles()
    sessions_updated = 0
    new_profiles_added = 0

    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        
        filepath = os.path.join(DATA_DIR, filename)
        
        with open(filepath, 'r') as f:
            try:
                data = json.load(f)
            except Exception as e:
                print(f"Error reading {filename}: {e}")
                continue
                
        config = data.get("config", {})
        
        # Build the exact signature the GUI uses
        weapon = config.get("weapon", "")
        ammo = config.get("ammo", "")
        head = config.get("head", "")
        body = config.get("body", "")
        legs = config.get("legs", "")
        hands = config.get("hands", "Zaryte vambraces")
        back = config.get("back", "")
        feet = config.get("feet", "")
        ring = config.get("ring", "")
        prayer = config.get("prayer", "")

        sig = f"{weapon}_{ammo}_{head}_{body}_{legs}_{hands}_{back}_{feet}_{ring}_{prayer}"

        # 1. Prompt for missing profiles
        if sig not in profiles:
            print(f"\n⚠️ NEW UNIQUE LOADOUT DETECTED:")
            print(f"   Weapon : {weapon}")
            print(f"   Ammo   : {ammo}")
            print(f"   Head   : {head}")
            print(f"   Body   : {body}")
            print(f"   Legs   : {legs}")
            print(f"   Hands  : {hands}")
            print(f"   Back   : {back}")
            print(f"   Feet   : {feet}")
            print(f"   Ring   : {ring}")
            print(f"   Prayer : {prayer}")
            print("-" * 40)
            print("Please open your DPS Calculator and enter the stats.")
            print("(Or press ENTER on Max Hit to skip this loadout for now)")
            
            try:
                max_hit_str = input("Max Hit: ")
                if not max_hit_str.strip():
                    print("Skipping...")
                    continue
                    
                max_hit = float(max_hit_str)
                exp_hit = float(input("Exp Hit: "))
                dps = float(input("DPS: "))
                ttk = float(input("Avg TTK: "))
                acc = float(input("Accuracy %: "))
                
                profiles[sig] = {
                    "max_hit": max_hit,
                    "exp_hit": exp_hit,
                    "dps": dps,
                    "ttk": ttk,
                    "accuracy": acc
                }
                
                save_dps_profiles(profiles)
                new_profiles_added += 1
                print("✅ Profile Saved!")
                
            except ValueError:
                print("❌ Invalid number entered. Skipping this loadout for now.")
                continue

        # 2. Inject the known profile back into the session JSON
        current_stats = data.get("theoretical_stats", {})
        
        # If the JSON doesn't have the stats yet, or they are all 0s, update it!
        if not current_stats or current_stats.get("dps", 0) == 0:
            data["theoretical_stats"] = profiles[sig]
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
                
            sessions_updated += 1

    print("\n" + "=" * 40)
    print(f"Done! Added {new_profiles_added} new unique profiles.")
    print(f"Backfilled {sessions_updated} historical sessions with theoretical stats.")
    print("=" * 40)

if __name__ == "__main__":
    main()