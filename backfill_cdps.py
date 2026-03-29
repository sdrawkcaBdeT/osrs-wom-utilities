import json
import glob
import os
from cdps_simulator import simulate_bbd_combat

def backfill_sessions():
    print("=== Scanning bbd_data/ for historical sessions ===")
    files = glob.glob("bbd_data/session_*.json")
    updated = 0
    skipped = 0
    
    for filepath in files:
        filename = os.path.basename(filepath)
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        stats = data.get("theoretical_stats", {})
        config = data.get("config", {})
        
        # STRICT REQUIREMENT: We do not assume stats. 
        rng_str = stats.get("rng_str")
        rng_acc = stats.get("rng_acc")
        weapon = config.get("weapon")
        ammo = config.get("ammo")
        prayer = config.get("prayer", "None") # Prayer can safely default to None if missing
        
        if None in (rng_str, rng_acc, weapon, ammo):
            print(f"[SKIPPED] {filename} -> Missing critical gear/stat data.")
            skipped += 1
            continue
            
        # Run the Monte Carlo Engine using the EXACT data from the JSON
        calibrated = simulate_bbd_combat(
            rng_str=rng_str, 
            rng_acc=rng_acc, 
            weapon=weapon, 
            ammo=ammo, 
            prayer=prayer
        )
        
        # Inject the new metrics
        stats.update(calibrated)
        data["theoretical_stats"] = stats
        
        # Save the file
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
            
        print(f"[UPDATED] {filename} | {weapon} + {ammo} | cDPS: {calibrated['cdps']} | cTTK: {calibrated['cttk']}s")
        updated += 1
        
    print(f"\n✅ Session Backfill Complete: {updated} updated, {skipped} skipped.")

def backfill_profiles():
    print("\n=== Scanning dps_profiles.json for saved loadouts ===")
    profile_path = "dps_profiles.json"
    
    if not os.path.exists(profile_path):
        print("No dps_profiles.json found. Skipping.")
        return
        
    with open(profile_path, 'r') as f:
        profiles = json.load(f)
        
    updated = 0
    for sig, stats in profiles.items():
        rng_str = stats.get("rng_str")
        rng_acc = stats.get("rng_acc")
        
        if rng_str is None or rng_acc is None:
            continue
            
        # Since dps_profiles.json doesn't save string names, we just safely assume 
        # the DHCB/Rigour baseline so the live UI doesn't crash. 
        # (These update dynamically anyway the second you change a dropdown in the GUI).
        calibrated = simulate_bbd_combat(
            rng_str=rng_str, 
            rng_acc=rng_acc, 
            weapon="Dragon hunter crossbow", 
            ammo="Diamond bolts (e)", 
            prayer="Rigour"
        )
        
        stats.update(calibrated)
        profiles[sig] = stats
        updated += 1
        print(f"[PROFILE UPDATED] Signature: {sig[:8]}... | cDPS: {calibrated['cdps']}")
        
    with open(profile_path, 'w') as f:
        json.dump(profiles, f, indent=4)
        
    print(f"✅ Profile Backfill Complete: {updated} loadouts updated.")

if __name__ == "__main__":
    backfill_sessions()
    backfill_profiles()
    print("\n=== All historical data successfully upgraded ===")