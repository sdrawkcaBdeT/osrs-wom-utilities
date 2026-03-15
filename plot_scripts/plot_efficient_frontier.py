import os
import shutil
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from matplotlib.colors import ListedColormap, BoundaryNorm
from datetime import datetime

# --- CONFIG ---
NORMALIZED_CSV = "../normalized_sessions.csv"
DATA_DIR = "../bbd_data"
OUTPUT_DIR = "../analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Generating The Efficient Frontier ---")
    
    if not os.path.exists(NORMALIZED_CSV):
        return print(f"Error: {NORMALIZED_CSV} not found.")

    # 1. Load Normalized Data (For T-NGP/hr and Costs)
    df_norm = pd.read_csv(NORMALIZED_CSV)
    
    # Calculate Supply Cost per Hour
    df_norm['cost_per_hr'] = df_norm['actual_supply_cost'] / df_norm['duration_hrs']
    
    # 2. Extract Theoretical DPS and Gear Configs directly from JSONs
    # (Since we didn't add DPS to the normalizer script, we just pull it fresh here!)
    json_data =[]
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            config = data.get("config", {})
            theo = data.get("theoretical_stats", {})
            
            json_data.append({
                "session_id": data.get("session_id"),
                "theo_dps": theo.get("dps", 0),
                "cape": config.get("back", ""),
                "boots": config.get("feet", ""),
                "ring": config.get("ring", "")
            })
            
    df_json = pd.DataFrame(json_data)
    
    # 3. Merge them together
    df = pd.merge(df_norm, df_json, on="session_id", how="inner")
    
    # Filter out sessions where you didn't enter the DPS yet
    df = df[df['theo_dps'] > 0].copy()
    
    if df.empty:
        return print("No sessions with Theoretical DPS found.")

    # 4. Setup Discrete Quantile Colors
    bins = np.percentile(df['t_ngp_hr'],[0, 20, 40, 60, 80, 100])
    bins[0] -= 1 
    bins[-1] += 1
    
    discrete_colors =["#FF3333", "#FF8800", "#FFD700", "#88FF00", "#00FF00"]
    cmap = ListedColormap(discrete_colors)
    norm = BoundaryNorm(bins, cmap.N)

    # 5. Setup Cinematic Plot
    BG_COLOR = "#0A0A0A"
    TEXT_COLOR = "#FFFFFF"

    fig, ax = plt.subplots(figsize=(14, 10), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # 6. Plot the Data Points
    scatter = ax.scatter(
        x=df['theo_dps'], 
        y=df['cost_per_hr'], 
        c=df['t_ngp_hr'], 
        cmap=cmap, 
        norm=norm,
        s=200, 
        alpha=0.85, 
        edgecolors="#222222", 
        linewidths=1.5,
        zorder=4
    )

    # 7. Draw The Trade-Off Trajectory Vectors
    # These are the specific A/B tests you requested
    trade_offs =[
        {"slot": "boots", "item_A": "Pegasian boots", "item_B": "Devout Boots", "label": "Boots Swap", "offset": (0, 60)},
        {"slot": "cape", "item_A": "Ranging cape (t)", "item_B": "Ava's assembler", "label": "Cape Swap", "offset": (0, -70)},
        {"slot": "ring", "item_A": "Archers ring (i)", "item_B": "Ring of the gods (i)", "label": "Ring Swap", "offset": (80, 20)}
    ]

    for trade in trade_offs:
        col = trade["slot"]
        item_a = trade["item_A"]
        item_b = trade["item_B"]
        offset = trade["offset"]
        
        # Isolate sessions for Item A and Item B
        df_a = df[df[col] == item_a]
        df_b = df[df[col] == item_b]
        
        # We only draw the vector if you have actually tested both items!
        if not df_a.empty and not df_b.empty:
            dps_a, cost_a = df_a['theo_dps'].mean(), df_a['cost_per_hr'].mean()
            dps_b, cost_b = df_b['theo_dps'].mean(), df_b['cost_per_hr'].mean()
            
            # Draw the dashed vector line showing the path of the swap
            ax.annotate("", xy=(dps_b, cost_b), xytext=(dps_a, cost_a),
                        arrowprops=dict(arrowstyle="->,head_length=0.8,head_width=0.4", 
                                        color="#FFFFFF", lw=2.5, ls="dashed"), zorder=5)
            
            # Calculate the literal math of the trade
            diff_dps = dps_b - dps_a
            diff_cost = cost_b - cost_a
            
            # Find the midpoint of the arrow to attach the text box line to
            mid_dps = (dps_a + dps_b) / 2
            mid_cost = (cost_a + cost_b) / 2
            
            # --- NEW: Draw the offset annotation with a connecting line ---
            ax.annotate(
                f"{item_b}\n$\Delta$DPS: {diff_dps:+.2f}\n$\Delta$Cost: {diff_cost/1000:+.0f}k/hr", 
                xy=(mid_dps, mid_cost),            # The point to point at (midpoint of arrow)
                xytext=offset,                     # The offset in pixels (from the trade_offs dict)
                textcoords='offset points',        # Tells matplotlib to use exact pixels for offset
                color="#0A0A0A", fontsize=10, fontweight='bold', ha='center', va='center', zorder=6,
                bbox=dict(facecolor="#FFD700", edgecolor='white', boxstyle='round,pad=0.4', alpha=0.9),
                arrowprops=dict(arrowstyle="-", color="#FFD700", lw=1.5, alpha=0.8) # The callout line!
            )

    # 8. Formatting the Axes
    ax.set_xlabel("Theoretical DPS (Higher is Better)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    ax.set_ylabel("Supply Cost per Hour (Lower is Better)", color=TEXT_COLOR, fontsize=14, fontweight='bold', labelpad=15)
    
    # INVERT THE Y-AXIS! So the "Best" outcome is the top right corner.
    ax.invert_yaxis()
    
    # Format Y-Axis to K/M
    def cost_formatter(x, pos):
        if x >= 1000000: return f"{x/1000000:.1f}M"
        elif x >= 1000: return f"{x/1000:.0f}K"
        return f"{x:.0f}"
    ax.yaxis.set_major_formatter(plt.FuncFormatter(cost_formatter))
    
    ax.tick_params(axis='both', colors=TEXT_COLOR, labelsize=12)

    # 9. Add the Discrete Colorbar
    cbar = plt.colorbar(scatter, ax=ax, pad=0.02, ticks=bins)
    cbar.ax.yaxis.set_tick_params(color=TEXT_COLOR)
    cbar.ax.tick_params(labelsize=11, colors=TEXT_COLOR)
    cbar.set_label("T-NGP/hr (Performance Quintiles)", color=TEXT_COLOR, size=13, fontweight='bold', labelpad=15)
    
    def cb_formatter(x, pos):
        if x >= 1000000: return f"{x/1000000:.2f}M"
        elif x >= 1000: return f"{x/1000:.0f}K"
        return ""
    cbar.ax.yaxis.set_major_formatter(plt.FuncFormatter(cb_formatter))

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    
    ax.grid(axis='both', linestyle='--', alpha=0.15, color='white', zorder=1)

    # 10. Titles
    plt.suptitle('THE EFFICIENT FRONTIER: DPS VS. SUSTAIN COST', color=TEXT_COLOR, fontsize=26, fontweight='bold', y=0.96)
    plt.title("Top Right = High DPS / Low Cost. Arrows show the empirical effect of A/B gear swaps.", 
              color="#AAAAAA", fontsize=15, pad=15)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)
    
    # Save with precise timestamp
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"efficient_frontier_{timestamp_str}.png")
    
    plt.savefig(output_path, dpi=200, facecolor=BG_COLOR, bbox_inches='tight')
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_efficient_frontier")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_efficient_frontier.png")
        # Use the filename that was generated for the specific dir
        filename = os.path.basename(output_path)
        specific_path = os.path.join(specific_dir, filename)
        
        shutil.copy(output_path, recent_path)
        shutil.move(output_path, specific_path)
        print(f"-> Saved recent to: {recent_path}")
        print(f"-> Saved archived to: {specific_path}")
    except Exception as e:
        print(f"Error routing file: {e}")
    print(f"Chart saved successfully: {output_path}")

if __name__ == "__main__":
    main()