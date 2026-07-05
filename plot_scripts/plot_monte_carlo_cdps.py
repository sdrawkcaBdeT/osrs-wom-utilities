import os
import shutil
import json
import math
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde
import matplotlib.image as mpimg
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.patheffects as path_effects
from datetime import datetime

# --- CONFIG ---
PROFILES_FILE = "../dps_profiles.json"
OUTPUT_DIR = "../analytics_output"
ICONS_DIR = "../icons"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Root-Two Aspect Ratio for Cinematic Balance (16 width / 1.414 = 11.3 height)
FIG_WIDTH = 16.0
FIG_HEIGHT = 11.3

MILESTONES = [100, 1000, 5000, 10000, 50000, 100000, 200000, 500000, 1000000]

# --- COLORS ---
BG_COLOR = "#0A0A0A"
TEXT_COLOR = "#FFFFFF"
THEO_COLOR = "#FFD700"
CALI_COLOR = "#00FFFF"
HUD_BG = "#111111"

def calculate_effective_stats(rng_str, rng_acc, prayer="Rigour", ranged_level=112, weapon="Dragon hunter crossbow"):
    prayers = {"Rigour": [1.20, 1.23], "None": [1.0, 1.0]}
    mults = prayers.get(prayer, [1.0, 1.0])
    
    eff_str = math.floor(math.floor(ranged_level * mults[1]) + 8)
    base_max_hit = math.floor(0.5 + eff_str * (rng_str + 64) / 640)
    
    eff_acc = math.floor(math.floor(ranged_level * mults[0]) + 8)
    atk_roll = eff_acc * (rng_acc + 64)

    if weapon == "Dragon hunter crossbow":
        base_max_hit = math.floor(base_max_hit * 1.25)
        atk_roll = math.floor(atk_roll * 1.30)

    def_roll = 19758
    hit_chance = 1 - ((def_roll + 2) / (2 * (atk_roll + 1))) if atk_roll > def_roll else atk_roll / (2 * (def_roll + 1))
    
    return base_max_hit, hit_chance

def run_simulation_engine(rng_str, rng_acc, weapon, ammo, prayer, iterations=1000000):
    print(f"Crunching {iterations:,} Monte Carlo combat iterations...")
    base_max_hit, hit_chance = calculate_effective_stats(rng_str, rng_acc, prayer, 112, weapon)
    
    has_diamond = "Diamond" in ammo and "bolts" in ammo
    absolute_max_hit = math.floor(base_max_hit * 1.15) if has_diamond else base_max_hit
    proc_chance = 0.10 if has_diamond else 0.0
    
    weapon_ticks = 5
    regen_ticks = 20
    ttks = np.zeros(iterations, dtype=np.float32)

    for i in range(iterations):
        hp = 315
        kill_ticks = 0
        attacks = 0
        
        while hp > 0:
            kill_ticks += weapon_ticks
            attacks += 1
            
            regens = (kill_ticks // regen_ticks) - ((kill_ticks - weapon_ticks) // regen_ticks)
            if regens > 0 and hp < 315:
                hp = min(315, hp + regens)
            
            if proc_chance > 0 and random.random() < proc_chance:
                hp -= random.randint(0, absolute_max_hit)
                continue
            
            if random.random() < hit_chance:
                hp -= random.randint(0, base_max_hit)
                
        ttks[i] = attacks * weapon_ticks * 0.6

    return ttks

def fetch_icon(item_name):
    if not item_name or str(item_name).lower() in ['nan', 'none', 'unknown', '']:
        return None
    safe_name = item_name.lower().replace(" ", "_") + ".png"
    filepath = os.path.join(ICONS_DIR, safe_name)
    if os.path.exists(filepath):
        return mpimg.imread(filepath)
    return None

def draw_gear_grid(fig, config):
    # Anchor top-left, floating style
    ax = fig.add_axes([0.05, 0.60, 0.15, 0.30])
    ax.set_facecolor(HUD_BG)
    ax.axis('off')

    # Draw a subtle border around the HUD
    rect = plt.Rectangle((0, 0), 1, 1, fill=False, edgecolor='#333333', lw=2, transform=ax.transAxes)
    ax.add_patch(rect)
    ax.text(0.5, 0.95, "WORN EQUIPMENT", color=TEXT_COLOR, fontsize=12, fontweight='bold', ha='center', va='top', transform=ax.transAxes)

    eq = {
        'head': config.get('head', 'Unknown'),
        'cape': config.get('back', 'Unknown'),
        'neck': 'Necklace of anguish',
        'ammo': config.get('ammo', 'Diamond bolts (e)'),
        'weapon': 'Dragon hunter crossbow',
        'body': config.get('body', 'Unknown'),
        'shield': 'Twisted buckler',
        'legs': config.get('legs', 'Unknown'),
        'hands': config.get('hands', 'Zaryte vambraces'),
        'feet': config.get('feet', 'Devout boots'),
        'ring': config.get('ring', 'Ring of the gods (i)')
    }

    grid_map = {
        "head": (1, 4), "cape": (0, 3), "neck": (1, 3), "ammo": (2, 3),
        "weapon": (0, 2), "body": (1, 2), "shield": (2, 2), "legs": (1, 1),
        "hands": (0, 0), "feet": (1, 0), "ring": (2, 0)
    }

    # Internal coordinates for plotting
    ax.set_xlim(-0.5, 2.5)
    ax.set_ylim(-0.5, 4.5)
    
    # Scale coordinates to fit under the title
    y_offset = -0.3

    for slot, (x, y) in grid_map.items():
        draw_y = y + y_offset
        # Draw dark slot square
        slot_bg = plt.Rectangle((x - 0.45, draw_y - 0.45), 0.9, 0.9, fill=True, facecolor='#1A1A1A', edgecolor='#333333', lw=1.5)
        ax.add_patch(slot_bg)
        
        icon = fetch_icon(eq.get(slot))
        if icon is not None:
            imagebox = OffsetImage(icon, zoom=1.1)
            ab = AnnotationBbox(imagebox, (x, draw_y), frameon=False)
            ax.add_artist(ab)

def draw_truth_ledger(fig, stats):
    # Anchor top-right, floating style
    ax = fig.add_axes([0.75, 0.70, 0.20, 0.20])
    ax.set_facecolor(HUD_BG)
    ax.axis('off')

    rect = plt.Rectangle((0, 0), 1, 1, fill=False, edgecolor='#333333', lw=2, transform=ax.transAxes)
    ax.add_patch(rect)
    
    ax.text(0.5, 0.85, "THE TRUTH LEDGER", color=TEXT_COLOR, fontsize=14, fontweight='bold', ha='center', va='center', transform=ax.transAxes)
    ax.plot([0.1, 0.9], [0.75, 0.75], color="gray", lw=1, transform=ax.transAxes)

    metrics = [
        ("DPS", stats.get('dps', 0), stats.get('cdps', 0), 0.60),
        ("Expected Hit", stats.get('exp_hit', 0), stats.get('cexp_hit', 0), 0.40),
        ("TTK (Seconds)", stats.get('ttk', 0), stats.get('cttk', 0), 0.20)
    ]

    ax.text(0.60, 0.60, "Theo", color="gray", fontsize=10, fontweight='bold', ha='center', va='bottom', transform=ax.transAxes)
    ax.text(0.85, 0.60, "Cali", color=CALI_COLOR, fontsize=10, fontweight='bold', ha='center', va='bottom', transform=ax.transAxes)

    for label, theo, cali, y_pos in metrics:
        ax.text(0.1, y_pos, label, color=TEXT_COLOR, fontsize=12, fontweight='bold', ha='left', va='center', transform=ax.transAxes)
        ax.text(0.60, y_pos, f"{theo:.2f}", color="gray", fontsize=12, ha='center', va='center', transform=ax.transAxes)
        ax.text(0.85, y_pos, f"{cali:.2f}", color=CALI_COLOR, fontsize=12, fontweight='bold', ha='center', va='center', transform=ax.transAxes)

def main():
    print("--- Generating Cinematic Monte Carlo Analysis ---")
    
    if not os.path.exists(PROFILES_FILE):
        return print(f"Error: {PROFILES_FILE} not found.")

    with open(PROFILES_FILE, 'r') as f:
        profiles = json.load(f)

    for sig, stats in profiles.items():
        print(f"\n[PROCESSING] Signature: {sig[:8]}...")
        
        rng_str, rng_acc = stats.get("rng_str"), stats.get("rng_acc")
        if rng_str is None or rng_acc is None:
            print("Missing core stats. Skipping.")
            continue
            
        weapon = stats.get("weapon", "Dragon hunter crossbow")
        ammo = stats.get("ammo", "Diamond bolts (e)")
        prayer = stats.get("prayer", "Rigour")
        
        ttks = run_simulation_engine(rng_str, rng_acc, weapon, ammo, prayer, iterations=1000000)
        
        # Pre-calculate axes limits for global lock
        x_min = np.percentile(ttks, 0.05) - 3.0
        x_max = np.percentile(ttks, 99.5) + 6.0
        
        # Determine the KDE max height for global Y-lock
        kde_global = gaussian_kde(ttks)
        global_x_vals = np.linspace(x_min, x_max, 500)
        y_max = max(kde_global(global_x_vals)) * 1.3 # 30% Headroom for curves

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        specific_dir_name = f"plot_monte_carlo_cdps_{sig[:8]}"
        specific_dir = os.path.join(OUTPUT_DIR, specific_dir_name)
        os.makedirs(specific_dir, exist_ok=True)
        
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        os.makedirs(recent_dir, exist_ok=True)

        for n in MILESTONES:
            print(f"-> Rendering frame N={n:,}")
            ttks_slice = ttks[:n]
            
            fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT), facecolor=BG_COLOR)
            ax.set_facecolor(BG_COLOR)

            # HISTOGRAM (Binned strictly to 3.0s weapon cycles to prevent gaps)
            bin_edges = np.arange(x_min - 1.5, x_max + 4.5, 3.0)
            ax.hist(ttks_slice, bins=bin_edges, color=CALI_COLOR, edgecolor="#111111", alpha=0.4, density=True, zorder=2)
            
            # KDE CURVE
            if n > 100:
                kde = gaussian_kde(ttks_slice)
                y_vals = kde(global_x_vals)
                ax.plot(global_x_vals, y_vals, color="#FFFFFF", linewidth=3, zorder=5)

            # CALIBRATED PEAK
            mean_ttk = np.mean(ttks_slice)
            ax.axvline(mean_ttk, color=THEO_COLOR, linestyle="--", linewidth=3, zorder=4)
            peak_txt = ax.text(mean_ttk + 1.0, y_max * 0.4, f"Calibrated Peak\n{mean_ttk:.1f}s", color=THEO_COLOR, fontsize=16, fontweight='bold')
            peak_txt.set_path_effects([path_effects.withStroke(linewidth=3, foreground='black')])

            # FORMATTING
            ax.set_xlim(x_min, x_max)
            ax.set_ylim(0, y_max)
            ax.set_yticks([]) # Hide y-axis numbers as they represent abstract density
            ax.set_xlabel("Time-to-Kill (Seconds)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
            ax.tick_params(axis='x', colors=TEXT_COLOR, labelsize=12)
            
            for spine in ['top', 'right', 'left']:
                ax.spines[spine].set_visible(False)
            ax.spines['bottom'].set_color('gray')
            ax.grid(axis='x', linestyle='--', alpha=0.15, color='white', zorder=1)

            # TITLES
            plt.suptitle(f"MONTE CARLO cDPS ENGINE", color=TEXT_COLOR, fontsize=26, fontweight='bold', y=0.96)
            plt.title(f"Convergence of {n:,} simulated kills vs. {weapon} mechanics", color="gray", fontsize=15, pad=15)

            # HUDS
            draw_gear_grid(fig, stats.get("config", {}))
            draw_truth_ledger(fig, stats)

            plt.tight_layout()
            plt.subplots_adjust(top=0.88, left=0.05, right=0.95, bottom=0.1)

            # SAVE & ROUTE
            filename = f"monte_carlo_{n:07d}.png"
            output_path = os.path.join(specific_dir, filename)
            plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
            
            # Keep 0_recent updated with the final 1M iteration chart
            if n == MILESTONES[-1]:
                recent_path = os.path.join(recent_dir, "plot_monte_carlo_cdps.png")
                shutil.copy(output_path, recent_path)
                print(f"-> Master chart copied to 0_recent")

            plt.close(fig)

if __name__ == "__main__":
    main()