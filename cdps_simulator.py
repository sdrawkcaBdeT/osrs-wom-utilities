import random
import math

def calculate_effective_stats(rng_str, rng_acc, prayer="Rigour", ranged_level=112, weapon="Dragon hunter crossbow"):
    # Prayer multipliers [Accuracy, Strength]
    prayers = {
        "Rigour": [1.20, 1.23],
        "Deadeye": [1.18, 1.18],
        "Eagle Eye": [1.15, 1.15],
        "Hawk Eye": [1.10, 1.10],
        "Sharp Eye": [1.05, 1.05],
        "None": [1.0, 1.0]
    }
    
    mults = prayers.get(prayer, [1.0, 1.0])
    pray_acc = mults[0]
    pray_str = mults[1]

    # Step 1 & 2: Effective Ranged Strength & Base Max Hit
    eff_str = math.floor(math.floor(ranged_level * pray_str) + 8)
    base_max_hit = math.floor(0.5 + eff_str * (rng_str + 64) / 640)

    # Step 4 & 5: Effective Ranged Attack & Attack Roll
    eff_acc = math.floor(math.floor(ranged_level * pray_acc) + 8)
    atk_roll = eff_acc * (rng_acc + 64)

    # --- THE DRAGON HUNTER MULTIPLIERS ---
    if weapon == "Dragon hunter crossbow":
        base_max_hit = math.floor(base_max_hit * 1.25)
        atk_roll = math.floor(atk_roll * 1.30)

    # Step 6 & 7: Hit Chance vs Brutal Black Dragon (Def Roll = 19758)
    def_roll = 19758
    if atk_roll > def_roll:
        hit_chance = 1 - ((def_roll + 2) / (2 * (atk_roll + 1)))
    else:
        hit_chance = atk_roll / (2 * (def_roll + 1))

    return base_max_hit, hit_chance

def simulate_bbd_combat(rng_str, rng_acc, weapon="Dragon hunter crossbow", ammo="Diamond bolts (e)", prayer="Rigour", weapon_ticks=5, regen_ticks=20, iterations=1_000_000):
    """
    Runs a Monte Carlo simulation against a 315 HP target to find Calibrated TTK and DPS.
    Accounts for diamond bolt armor piercing, weapon speed, and monster HP regeneration.
    """
    try:
        rng_str = float(rng_str)
        rng_acc = float(rng_acc)
    except (ValueError, TypeError):
        return {"cttk": 0, "cdps": 0, "accuracy": 0, "max_hit": 0, "exp_hit": 0, "cexp_hit": 0}

    base_max_hit, hit_chance = calculate_effective_stats(rng_str, rng_acc, prayer, 112, weapon)
    
    # --- 1. THEORETICAL EXPECTED HIT & ABSOLUTE MAX HIT MATH ---
    if "Diamond" in ammo and "bolts" in ammo:
        proc_chance = 0.10
        absolute_max_hit = math.floor(base_max_hit * 1.15)
        # Blended expected hit: (10% Proc Reality) + (90% Normal Reality)
        exp_hit = (proc_chance * (absolute_max_hit / 2)) + ((1 - proc_chance) * hit_chance * (base_max_hit / 2))
    else:
        absolute_max_hit = base_max_hit
        exp_hit = hit_chance * (base_max_hit / 2)
        proc_chance = 0.0

    total_attacks_across_sims = 0

    # --- 2. THE MONTE CARLO LOOP ---
    for _ in range(iterations):
        hp = 315
        kill_ticks = 0
        
        while hp > 0:
            total_attacks_across_sims += 1
            kill_ticks += weapon_ticks
            
            if regen_ticks > 0:
                regens = (kill_ticks // regen_ticks) - ((kill_ticks - weapon_ticks) // regen_ticks)
                if regens > 0 and hp < 315:
                    hp = min(315, hp + regens)
            
            if proc_chance > 0 and random.random() < proc_chance:
                damage = random.randint(0, absolute_max_hit)
                hp -= damage
                continue
            
            if random.random() < hit_chance:
                damage = random.randint(0, base_max_hit)
                hp -= damage

    # --- 3. CALIBRATED METRICS ---
    avg_attacks = total_attacks_across_sims / iterations
    cttk = avg_attacks * weapon_ticks * 0.6
    cdps = 315 / cttk
    cexp_hit = cdps * (weapon_ticks * 0.6) # The Realized Hit

    return {
        "cttk": round(cttk, 1),
        "cdps": round(cdps, 3),
        "accuracy": round(hit_chance * 100, 2),
        "max_hit": int(absolute_max_hit),
        "exp_hit": round(exp_hit, 1),
        "cexp_hit": round(cexp_hit, 1)
    }

# Quick test execution if run directly
if __name__ == "__main__":
    print("Testing Monte Carlo Engine (1,000,000 iterations)...")
    stats = simulate_bbd_combat(rng_str=132, rng_acc=244, weapon="Dragon hunter crossbow", ammo="Diamond bolts (e)", prayer="Rigour")
    print(f"Results: {stats}")