import os
import shutil
import json
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIG ---
NORMALIZED_CSV = "../normalized_sessions.csv"
DATA_DIR = "../bbd_data"
OUTPUT_DIR = "../analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Generating 3D Profit Topography (Interactive HTML) ---")
    
    if not os.path.exists(NORMALIZED_CSV):
        return print(f"Error: {NORMALIZED_CSV} not found.")

    # 1. Load Normalized Data
    df_norm = pd.read_csv(NORMALIZED_CSV)
    
    # 2. Extract Stats & Loadout Strings from JSONs
    json_data =[]
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        with open(os.path.join(DATA_DIR, filename), 'r') as f:
            data = json.load(f)
            config = data.get("config", {})
            theo = data.get("theoretical_stats", {})
            
            # Create a clean, readable loadout string for the hover tooltip
            loadout = f"Wep: {config.get('weapon', '')}<br>"
            loadout += f"Ammo: {config.get('ammo', '')}<br>"
            loadout += f"Boots: {config.get('feet', '')}<br>"
            loadout += f"Back: {config.get('back', '')}<br>"
            loadout += f"Ring: {config.get('ring', '')}<br>"
            loadout += f"Bones: {config.get('bones', '')}"
            
            json_data.append({
                "session_id": data.get("session_id"),
                "pray_bonus": theo.get("pray_bonus", 0),
                "theo_dps": theo.get("dps", 0),
                "loadout": loadout
            })
            
    df_json = pd.DataFrame(json_data)
    
    # 3. Merge and Filter
    df = pd.merge(df_norm, df_json, on="session_id", how="inner")
    
    # Filter out missing data
    df = df[(df['pray_bonus'] > 0) & (df['theo_dps'] > 0) & (df['t_ngp_hr'] > 0)].copy()
    
    if df.empty:
        return print("No valid sessions with full theoretical stats found.")

    # Convert T-NGP/hr to Millions for cleaner axis labeling
    df['t_ngp_hr_m'] = df['t_ngp_hr'] / 1000000.0

    # 4. Generate the 3D Interactive Plot
    # X: Prayer Bonus (Sustain/Cost)
    # Y: Theoretical DPS (Damage/Speed)
    # Z: T-NGP/hr (Ultimate Profit)
    
    fig = px.scatter_3d(
        df, 
        x='pray_bonus', 
        y='theo_dps', 
        z='t_ngp_hr_m',
        color='t_ngp_hr_m',
        color_continuous_scale=px.colors.sequential.Viridis, # Dark Purple to Neon Green
        hover_name='loadout',
        title="<b>THE HOLY TRINITY OF GEAR: PROFIT TOPOGRAPHY</b><br><sup>Rotate the cube. Hover over dots to see exact gear configurations.</sup>"
    )

    # 5. Cinematic Dark Mode Styling
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0A0A0A",
        scene=dict(
            xaxis=dict(title='Prayer Bonus (Sustain)', backgroundcolor="#111111", gridcolor="#333333"),
            yaxis=dict(title='Theoretical DPS (Damage)', backgroundcolor="#111111", gridcolor="#333333"),
            zaxis=dict(title='Net GP/hr (Millions)', backgroundcolor="#111111", gridcolor="#333333"),
        ),
        font=dict(family="Consolas", color="#FFFFFF", size=12)
    )

    # Tweak the marker size and add a slight border to make them pop
    fig.update_traces(marker=dict(size=8, line=dict(width=2, color='DarkSlateGrey')),
                      selector=dict(mode='markers'))

    # 6. Save as an Interactive HTML file
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"plot_profit_topography_{timestamp_str}.html")
    
    fig.write_html(output_path)
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_3d_profit_topography")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_3d_profit_topography.html")
        # Use the filename that was generated for the specific dir
        filename = os.path.basename(output_path)
        specific_path = os.path.join(specific_dir, filename)
        
        shutil.copy(output_path, recent_path)
        shutil.move(output_path, specific_path)
        print(f"-> Saved recent to: {recent_path}")
        print(f"-> Saved archived to: {specific_path}")
    except Exception as e:
        print(f"Error routing file: {e}")
    print(f"3D Interactive Chart saved successfully: {output_path}")
    print("Open this HTML file in your web browser to interact with it!")

if __name__ == "__main__":
    main()