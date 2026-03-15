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
        except: return {}
    return {}

def save_dps_profiles(profiles):
    with open(DPS_PROFILES_FILE, 'w') as f:
        json.dump(profiles, f, indent=4)

def main():
    print("--- In-Game Stats Backfiller Wizard ---")
    
    if not os.path.exists(DATA_DIR):
        return print(f"Error: {DATA_DIR} not found.")

    profiles = load_dps_profiles()
    sessions_updated = 0
    profiles_patched = 0

    # 1. Ask for missing stats in the existing profiles
    for sig, stats in profiles.items():
        if "rng_str" not in stats:
            print(f"\n⚠️ PROFILE MISSING IN-GAME STATS:")
            # The signature is formatted with underscores, let's print it cleanly
            clean_sig = sig.replace("_", " | ")
            print(f"   Loadout: {clean_sig}")
            print("-" * 40)
            
            try:
                rng_str_input = input("Ranged Strength Bonus: ")
                if not rng_str_input.strip():
                    print("Skipping...")
                    continue
                    
                rng_str = float(rng_str_input)
                rng_acc = float(input("Ranged Attack Bonus: "))
                pray_bonus = float(input("Prayer Bonus: "))
                
                stats["rng_str"] = rng_str
                stats["rng_acc"] = rng_acc
                stats["pray_bonus"] = pray_bonus
                
                profiles_patched += 1
                print("✅ Stats Saved!")
                
            except ValueError:
                print("❌ Invalid number. Skipping.")
                continue

    # Save the updated master profile dictionary
    save_dps_profiles(profiles)

    # 2. Inject the updated profiles back into the session JSONs
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        
        filepath = os.path.join(DATA_DIR, filename)
        
        with open(filepath, 'r') as f:
            try:
                data = json.load(f)
            except Exception as e:
                continue
                
        config = data.get("config", {})
        
        # Build the exact signature
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

        # If the profile is fully updated, ensure the JSON matches it
        if sig in profiles and "rng_str" in profiles[sig]:
            current_stats = data.get("theoretical_stats", {})
            
            if "rng_str" not in current_stats:
                data["theoretical_stats"] = profiles[sig]
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=4)
                sessions_updated += 1

    print("\n" + "=" * 40)
    print(f"Done! Updated {profiles_patched} unique profiles.")
    print(f"Backfilled {sessions_updated} historical sessions.")
    print("=" * 40)

if __name__ == "__main__":
    main()