import json
import os
import matplotlib.pyplot as plt
import numpy as np

# --- CONFIGURATION ---
PROFILES_FILE = "dps_profiles.json"
OUTPUT_DIR = "analytics_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# OSRS Theme Colors
BG_COLOR = "#1e1e1e"
TEXT_COLOR = "#00FF00"
THEO_COLOR = "#FFD700"  # Gold for theoretical potential
REAL_COLOR = "#00FFFF"  # Cyan for realized output
TAX_COLOR = "#FF4444"   # Red for the wasted damage

def generate_overkill_report():
    if not os.path.exists(PROFILES_FILE):
        print(f"Error: {PROFILES_FILE} not found.")
        return

    with open(PROFILES_FILE, 'r') as f:
        profiles = json.load(f)

    if not profiles:
        print("No profiles found to analyze.")
        return

    labels = []
    theo_hits = []
    real_hits = []
    taxes = []

    # Parse the profiles
    for i, (sig, stats) in enumerate(profiles.items()):
        # We need the theoretical expected hit and the calibrated (realized) expected hit
        exp_hit = stats.get("exp_hit")
        cexp_hit = stats.get("cexp_hit")
        
        if exp_hit is None or cexp_hit is None:
            continue
            
        labels.append(f"Loadout {i+1}\n(Str: {stats.get('rng_str')})")
        theo_hits.append(exp_hit)
        real_hits.append(cexp_hit)
        taxes.append(exp_hit - cexp_hit)

    if not labels:
        print("No fully calibrated profiles found. Run backfill_cdps.py first.")
        return

    # --- PLOTTING ---
    fig, ax = plt.subplots(figsize=(10, 6), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    x = np.arange(len(labels))
    width = 0.6

    # Plot the Realized Hit (Cyan)
    bars_real = ax.bar(x, real_hits, width, label='Realized Hit (cHit)', color=REAL_COLOR, edgecolor='black')
    
    # Plot the Overkill Tax stacked on top (Red)
    bars_tax = ax.bar(x, taxes, width, bottom=real_hits, label='Overkill Tax (Wasted)', color=TAX_COLOR, edgecolor='black', hatch='//')

    # Formatting
    ax.set_ylabel('Damage per Attack', color=TEXT_COLOR, fontsize=12, fontweight='bold')
    ax.set_title('The Overkill Tax: Theoretical vs Realized Output (315 HP)', color=TEXT_COLOR, fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, color=TEXT_COLOR, fontsize=10)
    ax.tick_params(axis='y', colors=TEXT_COLOR)
    
    # Add the value text on top of the bars
    for i in range(len(x)):
        # Realized text
        ax.text(x[i], real_hits[i] / 2, f"{real_hits[i]:.1f}", ha='center', va='center', color='black', fontweight='bold', fontsize=11)
        # Tax text
        ax.text(x[i], real_hits[i] + (taxes[i] / 2), f"-{taxes[i]:.1f}", ha='center', va='center', color='white', fontweight='bold', fontsize=10)
        # Total Theoretical text
        ax.text(x[i], theo_hits[i] + 0.5, f"Theo: {theo_hits[i]:.1f}", ha='center', va='bottom', color=THEO_COLOR, fontweight='bold')

    # Grid and Legend
    ax.yaxis.grid(True, linestyle='--', alpha=0.3, color='gray')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('gray')
    ax.spines['bottom'].set_color('gray')
    
    legend = ax.legend(facecolor='#2a2a2a', edgecolor='gray', labelcolor='white', loc='lower right')

    # Save and Show
    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, "plot_overkill_tax.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Success! Report saved to: {output_path}")
    
    # Optional: Open the window to view it immediately
    plt.show()

if __name__ == "__main__":
    generate_overkill_report()