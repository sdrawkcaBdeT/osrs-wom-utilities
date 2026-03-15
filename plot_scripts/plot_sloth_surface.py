import os
import shutil
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIG ---
NORMALIZED_CSV = "../normalized_sessions.csv"
OUTPUT_DIR = "../analytics_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def main():
    print("--- Generating 3D Surface Plot (Sloth Mountain) ---")
    
    if not os.path.exists(NORMALIZED_CSV):
        return print(f"Error: {NORMALIZED_CSV} not found.")

    # 1. Load Data
    df = pd.read_csv(NORMALIZED_CSV)
    
    # 2. Filter for valid human error data
    df = df[(df['total_attacks'] > 0) & (df['trips'] > 0) & (df['active_hrs'] > 0)].copy()
    
    if len(df) < 5:
        return print("Not enough continuous data to build a surface plot.")

    # Calculate metrics
    df['astb'] = (df['bank_hrs'] * 3600) / df['trips']
    df['max_attacks'] = (df['active_hrs'] * 3600) / 3.0
    df['miss_per_hr'] = np.maximum(0, df['max_attacks'] - df['total_attacks']) / df['active_hrs']
    df['t_ngp_hr_m'] = df['t_ngp_hr'] / 1000000.0  # Convert to Millions for cleaner axis

    # Filter massive outliers so the terrain doesn't get stretched
    df = df[(df['astb'] < 200) & (df['miss_per_hr'] < 500)]

    # 3. Fit a Multiple Linear Regression Plane (Z = aX + bY + c)
    # X = ASTB, Y = Misses/Hr, Z = GP/hr
    # We use numpy's least squares solver to mathematically generate the "Surface of Expected Penalty"
    A = np.c_[df['astb'], df['miss_per_hr'], np.ones(df.shape[0])]
    C, _, _, _ = np.linalg.lstsq(A, df['t_ngp_hr_m'], rcond=None)
    
    # C[0] is the ASTB coefficient, C[1] is the Missed Attack coefficient, C[2] is the intercept.

    # 4. Generate the Meshgrid (The fabric of the 3D surface)
    # We create a 50x50 grid spanning your best and worst performances
    x_range = np.linspace(df['astb'].min() * 0.9, df['astb'].max() * 1.1, 50)
    y_range = np.linspace(0, df['miss_per_hr'].max() * 1.1, 50)
    X, Y = np.meshgrid(x_range, y_range)
    
    # Calculate the Z (GP/hr) height for every single point on that grid
    Z = C[0]*X + C[1]*Y + C[2]

    # 5. Build the Plotly Figure
    fig = go.Figure()

    # Add the 3D Surface Terrain
    fig.add_trace(go.Surface(
        x=X, y=Y, z=Z,
        colorscale='RdYlGn',     # Red (Low GP) to Green (High GP)
        opacity=0.7,             # Slightly translucent so we can see dots below it
        name='Expected Baseline',
        showscale=False,
        hoverinfo='skip'         # Turn off hover for the mesh so it doesn't distract from the dots
    ))

    # Add the actual session dots
    # We add hover text to show exactly what loadout caused a dot to float above/below the expected surface
    hover_text = []
    for _, row in df.iterrows():
        txt = f"Session: {row['session_id']}<br>"
        txt += f"ASTB: {row['astb']:.1f}s<br>"
        txt += f"Miss/Hr: {row['miss_per_hr']:.0f}<br>"
        txt += f"GP/hr: {row['t_ngp_hr_m']:.2f}M"
        hover_text.append(txt)

    fig.add_trace(go.Scatter3d(
        x=df['astb'], 
        y=df['miss_per_hr'], 
        z=df['t_ngp_hr_m'],
        mode='markers',
        marker=dict(
            size=6,
            color='#00FFFF', # Neon Cyan dots to contrast with the Red/Green terrain
            line=dict(width=1, color='black'),
            opacity=1.0
        ),
        name='Actual Sessions',
        text=hover_text,
        hoverinfo='text'
    ))

    # 6. Cinematic Formatting
    fig.update_layout(
        title="<b>THE SLOTH MOUNTAIN: HUMAN ERROR DECAY SURFACE</b><br><sup>The translucent plane is the mathematical penalty of laziness. Dots above the plane represent god-tier RNG or Gear.</sup>",
        template="plotly_dark",
        paper_bgcolor="#0A0A0A",
        scene=dict(
            xaxis=dict(title='Seconds to Bank (ASTB)', backgroundcolor="#111111", gridcolor="#333333"),
            yaxis=dict(title='Missed Attacks / Hr', backgroundcolor="#111111", gridcolor="#333333"),
            zaxis=dict(title='Theoretical Net GP/hr (Millions)', backgroundcolor="#111111", gridcolor="#333333"),
            # Set the camera angle to look slightly up at the mountain peak
            camera=dict(eye=dict(x=1.5, y=-1.5, z=0.5)) 
        ),
        font=dict(family="Consolas", color="#FFFFFF", size=12),
        margin=dict(l=0, r=0, b=0, t=80)
    )

    # 7. Save and Export
    timestamp_str = datetime.now().strftime("%Y%m%d%H%M")
    output_path = os.path.join(OUTPUT_DIR, f"plot_sloth_surface_{timestamp_str}.html")
    
    fig.write_html(output_path)
    # --- Route to specific folders ---
    try:
        recent_dir = os.path.join(OUTPUT_DIR, "0_recent")
        specific_dir = os.path.join(OUTPUT_DIR, "plot_sloth_surface")
        os.makedirs(recent_dir, exist_ok=True)
        os.makedirs(specific_dir, exist_ok=True)
        
        # The plot was just saved to `path_var`. Let's copy it.
        recent_path = os.path.join(recent_dir, f"plot_sloth_surface.html")
        # Use the filename that was generated for the specific dir
        filename = os.path.basename(output_path)
        specific_path = os.path.join(specific_dir, filename)
        
        shutil.copy(output_path, recent_path)
        shutil.move(output_path, specific_path)
        print(f"-> Saved recent to: {recent_path}")
        print(f"-> Saved archived to: {specific_path}")
    except Exception as e:
        print(f"Error routing file: {e}")
    print(f"3D Surface Chart saved successfully: {output_path}")

if __name__ == "__main__":
    main()