import streamlit as st
import pandas as pd
import statsmodels.api as sm
import numpy as np
import itertools
import plotly.graph_objects as go
import streamlit_antd_components as sac

st.set_page_config(page_title="BBD Laboratory", layout="wide", initial_sidebar_state="expanded")

from sklearn.linear_model import LassoCV, BayesianRidge

# --- CUSTOM CSS FOR THE DARK/NEON THEME ---
st.markdown("""
    <style>
    /* Force Charcoal Backgrounds */
    [data-testid="stAppViewContainer"] { background-color: #1E1E1E; }
    [data-testid="stSidebar"] { background-color: #252526; }
    [data-testid="stHeader"] { background-color: #1E1E1E; }
    
    /* Force Global Text Color for readability against dark background */
    p, h1, h2, h3, h4, h5, h6, li, span, label, div { color: #CCCCCC; }
    </style>
""", unsafe_allow_html=True)

st.title("Brutal Black Dragon Laboratory")
st.markdown("### Multiple Linear Regression & Experiment Tracking")

# --- SIDEBAR TOGGLES ---
st.sidebar.header("🧪 Lab Settings")
impute_missing = st.sidebar.checkbox(
    "Impute Missing Attack Data", 
    value=True, 
    help="If checked, fills missing 'Missed Attacks' with the median so you don't lose old sessions. If unchecked, drops old sessions entirely."
)

def load_data():
    try:
        df = pd.read_csv("normalized_sessions.csv")
        return df
    except:
        return pd.DataFrame()

df = load_data().copy()

if df.empty:
    st.error("Could not find normalized_sessions.csv. Run normalize_sessions.py first.")
    st.stop()

# --- 1. EXPLICIT CONFIG CATEGORIES (SPLIT ARMOR) ---
CONFIG_KEYS =[
    "weapon", "head", "body", "legs", "hands", "ammo", "ring", "back", "feet", 
    "prayer", "tele", "bank", "bones", "pray_restore"
]

feature_cols =[c for c in df.columns if c.startswith('config_')]

# Check which categories actually exist in the current dataset
categories =[]
for k in CONFIG_KEYS:
    if any(c.startswith(f"config_{k}_") for c in feature_cols):
        categories.append(f"config_{k}")

# --- 2. FIND BASELINE & PREP MLR ---
baseline_items = {}
cols_to_keep =[]

for cat in categories:
    cat_cols = [c for c in feature_cols if c.startswith(f"{cat}_")]
    if not cat_cols: continue
    
    usage_counts = {c: df[c].sum() for c in cat_cols}
    baseline_col = max(usage_counts, key=usage_counts.get)
    baseline_items[cat] = baseline_col.replace(f"{cat}_", "")
    
    for c in cat_cols:
        if c != baseline_col:
            cols_to_keep.append(c)

# --- 3. HUMAN ERROR & MISSING DATA LOGIC ---
if 'astb' in df.columns and 'miss_per_hr' in df.columns:
    cols_to_keep.extend(['astb', 'miss_per_hr'])
    
    if impute_missing:
        median_miss = df['miss_per_hr'].median()
        df['miss_per_hr'] = df['miss_per_hr'].fillna(median_miss)
        missing_handling = 'none' # We fixed the NaNs, tell statsmodels to run normally
    else:
        missing_handling = 'drop' # Tell statsmodels to drop rows with NaNs
else:
    missing_handling = 'none'

# Add the RNG Delta variable if it exists in the dataset!
if 'delta_kph' in df.columns:
    cols_to_keep.append('delta_kph')
    if impute_missing:
        df['delta_kph'] = df['delta_kph'].fillna(0) # 0 means "average luck" relative to theoretical

# --- 4. THE SYNERGY GENERATOR (Max Hit Breakpoints) ---
# We only care about synergies between Weapon, Ammo, and Back slot. 
ammo_cols =[c for c in cols_to_keep if c.startswith('config_ammo_')]
back_cols =[c for c in cols_to_keep if c.startswith('config_back_')]
weapon_cols =[c for c in cols_to_keep if c.startswith('config_weapon_')]

interaction_groups =[ammo_cols, back_cols, weapon_cols]
synergy_cols =[]

for i in range(len(interaction_groups)):
    for j in range(i+1, len(interaction_groups)):
        for col1 in interaction_groups[i]:
            for col2 in interaction_groups[j]:
                item1 = col1.split('_')[-1]
                item2 = col2.split('_')[-1]
                syn_name = f"SYN_{item1} + {item2}"
                
                # Mathematically multiply them (1 * 1 = 1, otherwise 0)
                df[syn_name] = df[col1] * df[col2]
                
                # Only add if synergy actually happened, AND it isn't a perfect copy of a parent
                if df[syn_name].sum() > 0 and not df[syn_name].equals(df[col1]) and not df[syn_name].equals(df[col2]):
                    synergy_cols.append(syn_name)

cols_to_keep.extend(synergy_cols)

# --- 5. RUN REGRESSION & ML MODELS ---
# Universal sanitizer: handles True/False strings, bracket-wrapped numbers, nans
def _clean_col(series, fill_nan=0.0):
    # 1. Convert to string and handle boolean words
    s = series.astype(str).str.strip()
    s = s.str.replace('True', '1', regex=False).str.replace('False', '0', regex=False)
    
    # 2. Aggressively strip EVERYTHING except digits, decimals, negatives, and scientific 'e/E'
    s = s.str.replace(r'[^0-9\.\-eE]', '', regex=True)
    
    # 3. Safely coerce to numeric (errors='coerce' forces any surviving garbage to NaN)
    return pd.to_numeric(s, errors='coerce').fillna(fill_nan)

try:
    for col in cols_to_keep:
        df[col] = _clean_col(df[col])
    
    df['t_ngp_hr'] = _clean_col(df['t_ngp_hr'], fill_nan=float('nan'))
    
    X = df[cols_to_keep].astype(float)
    X = sm.add_constant(X)
    y = df['t_ngp_hr'].astype(float)

    X_clean = X.dropna() if missing_handling == 'drop' else X.copy()
    y_clean = y[X_clean.index]
    
    if len(X_clean) < 5:
        raise ValueError(f"Only {len(X_clean)} valid sessions remain after dropping NaNs. Not enough to build ML models.")
    
    # 1. OLS (Baseline)
    model = sm.OLS(y_clean, X_clean).fit(cov_type='HC3')
    
    # 2. Lasso
    lasso_model = LassoCV(cv=5).fit(X_clean.drop(columns=['const']), y_clean)
    
    # 3. Bayesian Ridge
    bayes_model = BayesianRidge().fit(X_clean.drop(columns=['const']), y_clean)
    
except Exception as e:
    import traceback
    st.error(f"Modeling failed: {e}\n\nTraceback:\n{traceback.format_exc()}")
    print("FATAL MODELING ERROR:")
    traceback.print_exc()
    st.info("💡 **Tip:** Try checking 'Impute Missing Attack Data' in the sidebar to prevent older sessions from being dropped. You can still view the Wealth Tracker tab!")
    
    class DummyModel:
        def __init__(self):
            self.params = pd.Series({'const': 0})
            self.pvalues = pd.Series({'const': 1})
            self.coef_ = np.zeros(len(cols_to_keep))
            
    model = DummyModel()
    lasso_model = DummyModel()
    bayes_model = DummyModel()
    y_clean = pd.Series()
    X_clean = pd.DataFrame(columns=['const'] + cols_to_keep)

# --- 6. PARSE RESULTS ROBUSTLY ---
results =[]
human_error_results = []
synergy_results =[]

for var in model.params.index:
    if var == 'const': continue
    
    coef = model.params[var]
    p_val = model.pvalues[var]

    # Handle Human Error Controls uniquely
    if var in['astb', 'miss_per_hr']:
        name = "Avg Seconds to Bank" if var == 'astb' else "Missed Attacks / Hr"
        human_error_results.append({
            "Item": name,
            "Impact (GP/hr)": coef,
            "P-Value": p_val,
            "Verdict": "⚠️ COST OF SLOTH"
        })
        continue

    # Handle the Combat RNG Metric
    if var == 'delta_kph':
        human_error_results.append({
            "Item": "Lucky Combat (Δ KPH)",
            "Impact (GP/hr)": coef,
            "P-Value": p_val,
            "Verdict": "🎲 COMBAT RNG"
        })
        continue

    # Handle Synergies
    if var.startswith("SYN_"):
        synergy_results.append({
            "Item": var.replace("SYN_", "Combo: "),
            "Impact (GP/hr)": coef,
            "P-Value": p_val,
            "Verdict": "🔥 SYNERGY" if p_val < 0.10 else "⚖️ NO EXTRA SYNERGY"
        })
        continue
    
    # Safely extract the exact category and item name for GEAR
    cat_prefix = ""
    for cat in categories:
        if var.startswith(f"{cat}_"):
            cat_prefix = cat
            break
            
    item_name = var.replace(f"{cat_prefix}_", "")
    
    if p_val < 0.05 and coef > 0:
        verdict = "✅ CONFIRMED UPGRADE"
    elif p_val < 0.05 and coef < 0:
        verdict = "❌ CONFIRMED TRAP"
    else:
        verdict = "⚖️ PLACEBO / NEEDS DATA"
        
    results.append({
        "Category": cat_prefix,
        "Item": item_name,
        "Impact (GP/hr)": coef,
        "P-Value": p_val,
        "Verdict": verdict
    })

# Create DataFrame if results exist, otherwise empty
if results:
    df_res = pd.DataFrame(results).sort_values(by="Impact (GP/hr)", ascending=False)
else:
    df_res = pd.DataFrame(columns=["Category", "Item", "Impact (GP/hr)", "P-Value", "Verdict"])

# --- BUILD THE TABS ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["The Verdict (MLR)", "Optimizer", "Experiment Matrix", "Wealth Tracker", "Visual Loadouts", "OSRS 100 Index"])

import base64
from pathlib import Path

def get_image_base64(item_name):
    if not item_name or item_name.lower() in ['none', 'nan', 'unknown', '']: 
        item_name = "placeholder"
    clean_name = item_name.replace(' ', '_') + ".png"
    filepath = Path("bbd_data/icons") / clean_name
    if not filepath.exists():
        filepath = Path("bbd_data/icons/placeholder.png")
    try:
        with open(filepath, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{encoded}"
    except Exception:
        return ""
        
def build_osrs_grid(equipment):
    def get_slot_html(item_name, img_b64):
        title = item_name if item_name and item_name not in ['Empty', 'placeholder'] else 'Empty'
        return f"""<div style="height: 40px; width: 40px; position: relative;">
<div style="display: flex; justify-content: center; align-items: center; height: 40px; width: 40px; background-color: #1a1a1a; border: 1px solid #333; border-radius: 4px;" title="{title}">
<img src="{img_b64}" alt="{title}" style="max-width: 36px; max-height: 36px;">
</div>
</div>"""
        
    grid_html = f"""<div style="background-color: #252526; padding: 15px; border-radius: 8px; border: 1px solid #333; display: inline-block; width: max-content; margin-bottom: 20px;">
<!-- Row 1: Head -->
<div style="display: flex; justify-content: center;">
{get_slot_html(equipment.get('head', ''), get_image_base64(equipment.get('head', '')))}
</div>

<!-- Row 2: Cape, Neck, Ammo -->
<div style="display: flex; justify-content: center; gap: 8px; margin-top: 4px;">
{get_slot_html(equipment.get('back', ''), get_image_base64(equipment.get('back', '')))}
<div style="height: 40px; width: 40px;"></div>
{get_slot_html(equipment.get('ammo', ''), get_image_base64(equipment.get('ammo', '')))}
</div>

<!-- Row 3: Weapon, Body, Shield -->
<div style="display: flex; justify-content: center; gap: 24px; margin-top: 4px;">
<div style="height: 40px; width: 40px;"></div>
{get_slot_html(equipment.get('body', ''), get_image_base64(equipment.get('body', '')))}
{get_slot_html(equipment.get('shield', ''), get_image_base64(equipment.get('shield', '')))}
</div>

<!-- Row 4: Legs -->
<div style="display: flex; justify-content: center; margin-top: 4px;">
{get_slot_html(equipment.get('legs', ''), get_image_base64(equipment.get('legs', '')))}
</div>

<!-- Row 5: Hands, Feet, Ring -->
<div style="display: flex; justify-content: center; gap: 24px; margin-top: 4px;">
{get_slot_html(equipment.get('hands', ''), get_image_base64(equipment.get('hands', '')))}
{get_slot_html(equipment.get('feet', ''), get_image_base64(equipment.get('feet', '')))}
{get_slot_html(equipment.get('ring', ''), get_image_base64(equipment.get('ring', '')))}
</div>
</div>"""
    return grid_html

with tab1:
    st.header("Gear Analysis Verdicts")
    st.markdown(f"**Baseline Setup:** `{', '.join(baseline_items.values())}`")
    valid_sessions = len(y_clean)
    st.markdown(f"**Baseline Net GP/hr:** `{model.params['const']:,.0f} GP/hr` *(Sample: {valid_sessions} sessions)*")
    
    selected_model = sac.segmented(
        items=[
            sac.SegmentedItem(label='OLS (Baseline)', icon='calculator'),
            sac.SegmentedItem(label='Bayesian Ridge', icon='box'),
            sac.SegmentedItem(label='Lasso (Regularized)', icon='filter')
        ], align='center', size='sm', color='green'
    )
    
    st.markdown("---")
    
    if selected_model == 'OLS (Baseline)':
        st.subheader("The Cost of Sloth (Human Error Variables)")
        
        # Display Human Error Cards
        if human_error_results:
            cols_human = st.columns(2)
            for i, row in enumerate(human_error_results):
                with cols_human[i % 2]:
                    st.markdown(f"""
                    <div style='background-color: #252526; padding: 15px; border-radius: 5px; border: 1px solid #FF4444; margin-bottom: 20px; box-shadow: 0 0 15px rgba(255, 68, 68, 0.2);'>
                        <h4 style='margin:0; color: #FFF;'>{row['Item']}</h4>
                        <h2 style='margin:0; color: #FF4444;'>
                            {row['Impact (GP/hr)']:+,.0f} GP/hr
                        </h2>
                        <p style='margin:0; color: #AAA;'>
                            Every unit costs you this much. (p={row['P-Value']:.3f})
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    
        st.markdown("---")
        st.subheader("Gear Swaps")
        
        # Display visually
        if not df_res.empty:
            cols = st.columns(3)
            for i, row in df_res.iterrows():
                with cols[i % 3]:
                    glow_color = "#00FF00" if row["Impact (GP/hr)"] > 0 else "#FF4444"
                    st.markdown(f"""
                    <div style='background-color: #252526; padding: 15px; border-radius: 5px; border: 1px solid {glow_color}; margin-bottom: 10px; box-shadow: 0 0 15px {glow_color}33;'>
                        <h4 style='margin:0; color: #FFF;'>{row['Item']}</h4>
                        <h2 style='margin:0; color: {glow_color};'>
                            {row['Impact (GP/hr)']:+,.0f} GP/hr
                        </h2>
                        <p style='margin:0; color: { "#888" if row["P-Value"] > 0.05 else "#FFF"};'>
                            {row['Verdict']} (p={row['P-Value']:.3f})
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No alternative gear tested yet! You are only running the baseline.")

        # Display Synergies
        if synergy_results:
            st.markdown("---")
            st.subheader("Weapon/Ammo Synergies (Max Hit Breakpoints)")
            cols_syn = st.columns(2)
            for i, row in enumerate(synergy_results):
                with cols_syn[i % 2]:
                    glow_color = "#FFD700" if row["Impact (GP/hr)"] > 0 else "#FF4444"
                    st.markdown(f"""
                    <div style='background-color: #252526; padding: 15px; border-radius: 5px; border: 1px solid {glow_color}; margin-bottom: 10px; box-shadow: 0 0 15px {glow_color}33;'>
                        <h4 style='margin:0; color: #FFF;'>{row['Item']}</h4>
                        <h2 style='margin:0; color: {glow_color};'>
                            {row['Impact (GP/hr)']:+,.0f} GP/hr
                        </h2>
                        <p style='margin:0; color: { "#888" if row["P-Value"] > 0.10 else "#FFF"};'>
                            {row['Verdict']} (p={row['P-Value']:.3f})
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

    elif selected_model == 'Lasso (Regularized)':
        st.subheader("Lasso Regression: Aggressive Signal Filtering")
        st.write("Lasso applies an L1 penalty, forcing useless placebo gear to exactly 0 GP/hr. If it survives on this screen, it strongly matters.")
        
        lasso_features = X_clean.drop(columns=['const']).columns
        lasso_cards = []
        for idx, var in enumerate(lasso_features):
            coef = lasso_model.coef_[idx]
            if abs(coef) > 0.01:
                item_name = var.split('_')[-1] if 'config_' in var else var
                if var.startswith('SYN_'): item_name = var.replace("SYN_", "Combo: ")
                if var in ['astb', 'miss_per_hr', 'delta_kph']: item_name = var.upper()
                lasso_cards.append({"Item": item_name, "Impact": coef})
                
        if lasso_cards:
            lasso_cards = sorted(lasso_cards, key=lambda x: x["Impact"], reverse=True)
            cols = st.columns(3)
            for i, card in enumerate(lasso_cards):
                with cols[i % 3]:
                    glow_color = "#00FF00" if card["Impact"] > 0 else "#FF4444"
                    st.markdown(f"""
                    <div style='background-color: #252526; padding: 15px; border-radius: 5px; border: 1px solid {glow_color}; margin-bottom: 10px; box-shadow: 0 0 15px {glow_color}33;'>
                        <h4 style='margin:0; color: #FFF;'>{card['Item']}</h4>
                        <h2 style='margin:0; color: {glow_color};'>
                            {card['Impact']:+,.0f} GP/hr
                        </h2>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("Lasso zeroed everything out! The variance is too high or impacts are too small.")

    elif selected_model == 'Bayesian Ridge':
        st.subheader("Bayesian Ridge: Probabilistic Limits")
        st.write("Calculates coefficients using a probabilistic Bayesian approach rather than absolute least-squares.")
        
        bayes_features = X_clean.drop(columns=['const']).columns
        bayes_cards = []
        for idx, var in enumerate(bayes_features):
            coef = bayes_model.coef_[idx]
            # Filter negligible impacts
            if abs(coef) > 5000:
                item_name = var.split('_')[-1] if 'config_' in var else var
                if var.startswith('SYN_'): item_name = var.replace("SYN_", "Combo: ")
                if var in ['astb', 'miss_per_hr', 'delta_kph']: item_name = var.upper()
                bayes_cards.append({"Item": item_name, "Impact": coef})
                
        if bayes_cards:
            bayes_cards = sorted(bayes_cards, key=lambda x: x["Impact"], reverse=True)
            cols = st.columns(3)
            for i, card in enumerate(bayes_cards):
                with cols[i % 3]:
                    glow_color = "#00FF00" if card["Impact"] > 0 else "#FF4444"
                    st.markdown(f"""
                    <div style='background-color: #252526; padding: 15px; border-radius: 5px; border: 1px solid {glow_color}; margin-bottom: 10px; box-shadow: 0 0 15px {glow_color}33;'>
                        <h4 style='margin:0; color: #FFF;'>{card['Item']}</h4>
                        <h2 style='margin:0; color: {glow_color};'>
                            {card['Impact']:+,.0f} GP/hr
                        </h2>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("Bayesian Ridge found no meaningful impacts given the extreme variance.")



with tab2:
    st.header("Theoretical Maximum Setup")
    st.write("Starts with your baseline, and mathematically swaps out pieces for Confirmed Upgrades.")
    
    best_gp = model.params['const']
    best_setup = baseline_items.copy()  # Dictionary to enforce mutual exclusivity!
    
    if not df_res.empty:
        # Loop through categories to find the BEST upgrade per slot
        for cat in categories:
            cat_upgrades = df_res[(df_res['Category'] == cat) & (df_res['Verdict'] == "✅ CONFIRMED UPGRADE")]
            if not cat_upgrades.empty:
                # Find the single item in this category with the maximum positive impact
                best_upgrade = cat_upgrades.loc[cat_upgrades['Impact (GP/hr)'].idxmax()]
                
                # Replace the baseline item for this specific slot
                best_setup[cat] = best_upgrade['Item']
                best_gp += best_upgrade['Impact (GP/hr)']
            
    st.metric(label="Theoretical Ceiling (T-NGP/hr)", value=f"{best_gp:,.0f} GP/hr")
    
    st.markdown("### The Ideal Loadout:")
    # Format cleanly for display
    for cat, item in best_setup.items():
        clean_cat = cat.replace("config_", "").replace("_", " ").title()
        st.markdown(f"- **{clean_cat}:** {item}")

with tab3:
    st.header("Data Collection Hitlist")
    st.write("Instead of looking at massive loadout combinations, this list tells you exactly which **individual items** need more testing to prove if they are upgrades or traps.")
    
    # 1. Calculate Item-Level Stats
    item_stats =[]
    for var in model.params.index:
        if var == 'const' or var in['astb', 'miss_per_hr'] or var.startswith('SYN_'): continue
        
        # Calculate how many sessions and total hours this specific item was used
        sessions_count = int(df[var].sum())
        hours_sum = df.loc[df[var] == 1, 'duration_hrs'].sum()
        p_val = model.pvalues[var]
        
        # Parse the name cleanly
        cat_prefix = ""
        for cat in categories:
            if var.startswith(f"{cat}_"):
                cat_prefix = cat
                break
        item_name = var.replace(f"{cat_prefix}_", "")
        clean_cat = cat_prefix.replace("config_", "").replace("_", " ").title()
        
        # Determine the Action Item based on P-Value and Hours Tested
        if p_val < 0.05:
            action = "✅ Sufficient Data (Confirmed)"
        elif hours_sum < 5.0:
            action = "⚠️ Needs More Data"
        else:
            action = "🛑 Likely Placebo (High Hours, High P-value)"
            
        item_stats.append({
            "Slot": clean_cat,
            "Item": item_name,
            "Sessions": sessions_count,
            "Hours Tested": hours_sum,
            "P-Value": p_val,
            "Action": action
        })
        
    if item_stats:
        df_item_cov = pd.DataFrame(item_stats)
        
        # Sort so "Needs More Data" is at the top, sorted by lowest hours first
        df_item_cov['Sort_Priority'] = df_item_cov['Action'].apply(lambda x: 0 if "⚠️" in x else (1 if "🛑" in x else 2))
        df_item_cov = df_item_cov.sort_values(by=["Sort_Priority", "Hours Tested"], ascending=[True, True])
        
        # Format for clean display
        df_display = df_item_cov.drop(columns=['Sort_Priority'])
        df_display['Hours Tested'] = df_display['Hours Tested'].apply(lambda x: f"{x:.1f}h")
        df_display['P-Value'] = df_display['P-Value'].apply(lambda x: f"{x:.3f}")
        
        st.dataframe(df_display, use_container_width=True)
        
        st.info("💡 **How to use this:** Pick 1 or 2 items from the top of the list (⚠️ Needs More Data) and equip them with your standard baseline gear for today's session.")
    else:
        st.write("No alternative items tested yet.")

    st.markdown("---")
    st.subheader("🔗 Confounded Pairs (Break these up!)")
    st.write("When you frequently use two non-baseline items *together*, the algorithm can't tell which one is actually providing the benefit. Break these pairs up in your next session to feed the algorithm clean data!")
    
    # Find highly correlated pairs
    pairs = []
    gear_only_cols =[c for c in cols_to_keep if c.startswith('config_')]
    
    for col1, col2 in itertools.combinations(gear_only_cols, 2):
        # How many times were they used together?
        n_both = ((df[col1] == 1) & (df[col2] == 1)).sum()
        
        # Only care if they've been used together at least twice
        if n_both >= 2:
            # How many times was EITHER used?
            n_any = ((df[col1] == 1) | (df[col2] == 1)).sum()
            # Jaccard overlap percentage
            overlap_pct = n_both / n_any
            
            if overlap_pct >= 0.70: # If they overlap 70%+ of the time
                item1 = col1.split('_')[-1]
                item2 = col2.split('_')[-1]
                
                # Format category names
                cat1 =[c for c in categories if col1.startswith(f"{c}_")][0].replace("config_", "").replace("_", " ").title()
                cat2 =[c for c in categories if col2.startswith(f"{c}_")][0].replace("config_", "").replace("_", " ").title()
                
                pairs.append({
                    "Confounded Pair": f"{item1} ({cat1})  ➕  {item2} ({cat2})",
                    "Times Paired": n_both,
                    "Overlap": f"{overlap_pct*100:.0f}%",
                    "Action Needed": f"Use {item1} WITHOUT {item2} (or vice versa)"
                })
                
    if pairs:
        st.dataframe(pd.DataFrame(pairs).sort_values(by="Overlap", ascending=False), use_container_width=True)
    else:
        st.success("No highly confounded pairs found! Your testing variance is healthy.")
        
    # 2. Hide the raw matrix in an expander for debugging purposes
    with st.expander("View Raw Loadout Matrix (Advanced)"):
        clean_cat_names =[]
        for cat in categories:
            clean_name = cat.replace("config_", "").replace("_", " ").title()
            clean_cat_names.append(clean_name)
            cat_cols =[c for c in feature_cols if c.startswith(f"{cat}_")]
            
            # --- BULLETPROOF PARSING ---
            # 1. Isolate the category columns
            temp_df = df[cat_cols].copy()
            
            # 2. Force all values to text, look for truthy words, and convert to 1 or 0 integers
            for col in cat_cols:
                temp_df[col] = temp_df[col].astype(str).str.strip().str.lower().isin(['1', '1.0', 'true']).astype(int)
            
            # 3. Find the column that contains the '1'
            def reverse_dummy(row, category=cat):
                if row.sum() > 0:
                    # idxmax() returns the exact column name that holds the highest value (1)
                    return row.idxmax().replace(f"{category}_", "")
                return "Missing in JSON"
                
            df[clean_name] = temp_df.apply(reverse_dummy, axis=1)
            
        # Group and display the final Matrix
        coverage = df.groupby(clean_cat_names).agg(
            Sessions=('session_id', 'count'),
            Avg_T_NGP_hr=('t_ngp_hr', 'mean'),
            Total_Hours=('duration_hrs', 'sum'),
            # --- NEW: Concatenate all Session IDs for debugging ---
            Included_Sessions=('session_id', lambda x: ', '.join(map(str, x)))
        ).reset_index().sort_values(by='Sessions', ascending=False)
        
        coverage['Avg_T_NGP_hr'] = coverage['Avg_T_NGP_hr'].apply(lambda x: f"{x:,.0f}")
        coverage['Total_Hours'] = coverage['Total_Hours'].apply(lambda x: f"{x:.1f}h")
        
        st.dataframe(coverage, use_container_width=True)

with tab4:
    st.header("Wealth Progress & Goals")
    st.write("A high-level overview of our journey towards the Twisted Bow.")
    
    try:
        df_wealth = pd.read_csv("wealth_history.csv")
        df_wealth['timestamp'] = pd.to_datetime(df_wealth['timestamp'])
        
        # Resample to Daily (take the last record of each day)
        df_wealth['date'] = df_wealth['timestamp'].dt.date
        df_daily = df_wealth.groupby('date').last().reset_index()
        
        friendly_names = {
            'total': 'Total Net Worth',
            'gap': 'GP Needed for T-Bow',
            'progress_pct': 'Twisted Bow Progress (%)',
            'net_gp_hr': 'Overall Net GP/hr',
            'no_gear_gp_hr': 'GP/hr (Ignoring Gear Price Fluctuations)',
            'tbow_cost': 'Twisted Bow Price',
            'played_hours_rem': 'Estimated Play Hours to Goal',
            'real_days_rem': 'Estimated Real Days to Goal',
            'gear': 'Active Gear Value',
            'supplies': 'Banked Supplies Value',
            'drops': 'Loot Tab Value',
            'ge': 'Active GE Offers Value'
        }
        
        sac_items = [sac.ChipItem(label=v) for v in friendly_names.values()]
        
        selected_metric_name = sac.chip(
            items=sac_items,
            index=0,
            format_func='title',
            radius='sm',
            size='sm',
            align='center',
            variant='outline',
            color='green',
            multiple=False
        )
        
        # Reverse lookup the column
        selected_col = next(key for key, value in friendly_names.items() if value == selected_metric_name)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_daily['date'], 
            y=df_daily[selected_col],
            mode='lines+markers',
            line=dict(color='#00FF00', width=3),
            marker=dict(size=6, color='#1E1E1E', line=dict(width=2, color='#00FF00')),
            name=selected_metric_name
        ))
        
        # Annotate logic: Label every 7th day (weekly), plus the very last point
        annotations = []
        
        def format_val(val, col):
            if 'pct' in col:
                return f"{val:.1f}%"
            elif 'rem' in col or 'hours' in col:
                return f"{val:,.0f}"
            else:
                if val >= 1000000:
                    return f"{val/1000000:.1f}M"
                elif val >= 1000:
                    return f"{val/1000:.1f}k"
                else:
                    return f"{val:,.0f}"
        
        for i in range(0, len(df_daily), 7):
            val = df_daily[selected_col].iloc[i]
            date_str = df_daily['date'].iloc[i]
            text_val = format_val(val, selected_col)
                    
            annotations.append(
                dict(
                    x=date_str,
                    y=val,
                    text=text_val,
                    showarrow=False,
                    yshift=15,
                    font=dict(color="#AAAAAA", size=10)
                )
            )
            
        # Always ensure the strict LAST point is heavily annotated
        last_val = df_daily[selected_col].iloc[-1]
        last_date = df_daily['date'].iloc[-1]
        last_text = format_val(last_val, selected_col)
                
        annotations.append(
            dict(
                x=last_date,
                y=last_val,
                text=f"<b>CURRENT:<br>{last_text}</b>",
                showarrow=True,
                arrowcolor="#00FF00",
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                ax=0,
                ay=-40,
                font=dict(color="#00FF00", size=14)
            )
        )
        
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#1E1E1E",
            plot_bgcolor="#1E1E1E",
            annotations=annotations,
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(showgrid=True, gridcolor="#222222", title=""),
            yaxis=dict(showgrid=True, gridcolor="#222222", title="")
        )
        
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading wealth history: {e}")

with tab5:
    st.header("Tested Gear Setups (Worn Equipment)")
    st.write("Visual breakdown of all unique loadouts deployed in your dataset.")
    
    import glob
    import json
    
    @st.cache_data
    def load_raw_json_loadouts():
        loadouts = {}
        json_files = glob.glob("bbd_data/session_*.json")
        for f in json_files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                
                config = data.get('config', {})
                duration_ms = data.get('session_time_ms', 0)
                duration_hrs = duration_ms / 3600000.0 if duration_ms > 0 else 0.0
                
                eq = {}
                params = []
                
                for key, val in config.items():
                    if key in ['experiment_name', 'mode']: continue
                    if not val or str(val).lower() in ['nan', 'none', 'unknown', '']: continue
                    
                    if key in ['head', 'cape', 'neck', 'ammo', 'weapon', 'body', 'shield', 'legs', 'hands', 'feet', 'ring', 'back']:
                        actual_slot = 'back' if key == 'cape' else key
                        eq[actual_slot] = val
                    elif key == 'bones' and val == 'Bonecrusher necklace':
                        eq['neck'] = val
                    else:
                        opt_name = key.replace('_', ' ').capitalize()
                        params.append(f"{opt_name}: {val}")
                        
                sig = str(eq) + str(sorted(params))
                if sig not in loadouts:
                    loadouts[sig] = {
                        'equipment': eq,
                        'params': params,
                        'sessions': 1,
                        'hours': duration_hrs
                    }
                else:
                    loadouts[sig]['sessions'] += 1
                    loadouts[sig]['hours'] += duration_hrs
            except Exception as e:
                pass
        return sorted(list(loadouts.values()), key=lambda x: x['sessions'], reverse=True)
        
    sorted_loadouts = load_raw_json_loadouts()
    
    for l in sorted_loadouts:
        st.markdown("---")
        colA, colB = st.columns([1, 2])
        
        with colA:
            st.markdown(build_osrs_grid(l['equipment']), unsafe_allow_html=True)
            
        with colB:
            st.subheader(f"Tested {l['sessions']} times ({l['hours']:.1f} hours)")
            if l['params']:
                st.markdown("**Non-Gear Configurations:**")
                for p in l['params']:
                    st.markdown(f"- {p}")
            else:
                st.markdown("*No additional configuration parameters logged for this setup.*")

with tab6:
    st.header("OSRS 100 Market Index")
    st.write("A 60-day rolling, monthly-reconstituted benchmark tracking the broader Old School RuneScape economy.")
    
    try:
        import json
        with open("market_data/osrs_100_snapshot.json", "r") as f:
            snapshot = json.load(f)
            
        cols = st.columns(5)
        cols[0].metric("Index Level", f"{snapshot['index_level']:,.2f}", f"{snapshot['1d_return']*100:+.2f}% (1D)")
        cols[1].metric("7-Day Return", f"{snapshot['7d_return']*100:+.2f}%")
        cols[2].metric("30-Day Return", f"{snapshot['30d_return']*100:+.2f}%")
        cols[3].metric("Since Inception", f"{snapshot['inception_return']*100:+.2f}%")
        cols[4].metric("Constituents", snapshot['active_constituents'])
        
        st.markdown(f"*(Latest Rebalance: {snapshot['latest_rebalance_date'][:10]} | History starts early 2026)*")
        st.markdown("---")
        
        # Load necessary data
        df_index = pd.read_csv("market_data/osrs_100_index_daily.csv")
        df_index['date'] = pd.to_datetime(df_index['date'])
        
        df_comp = pd.read_csv("market_data/osrs_100_constituents.csv")
        df_comp['rebalance_date'] = pd.to_datetime(df_comp['rebalance_date'])
        
        try:
            df_ad = pd.read_csv("market_data/osrs_100_adds_drops.csv")
            df_ad['rebalance_date'] = pd.to_datetime(df_ad['rebalance_date'])
        except:
            df_ad = pd.DataFrame()
            
        latest_rebal = df_comp['rebalance_date'].max()
        df_latest = df_comp[df_comp['rebalance_date'] == latest_rebal].copy()
        
        # Determine current month's return for formatting
        df_index['year_month'] = df_index['date'].dt.to_period('M')
        monthly_returns = df_index.groupby('year_month').apply(
            lambda x: (x.iloc[-1]['index_level'] / x.iloc[0]['index_level']) - 1
        ).reset_index(name='return')
        monthly_returns['year_month'] = monthly_returns['year_month'].astype(str)
        
        # CHART 1 & 2: Daily Index and Monthly Returns (side-by-side)
        chart_col1, chart_col2 = st.columns([3, 1])
        
        with chart_col1:
            fig_index = go.Figure()
            fig_index.add_trace(go.Scatter(
                x=df_index['date'], 
                y=df_index['index_level'],
                mode='lines',
                line=dict(color='#FFD700', width=3),
                name="OSRS 100",
                fill='tozeroy',
                fillcolor='rgba(255, 215, 0, 0.1)'
            ))
            
            # Cumulative Baseline
            fig_index.add_trace(go.Scatter(
                x=[df_index['date'].min(), df_index['date'].max()],
                y=[1000, 1000],
                mode='lines',
                line=dict(color='white', width=1, dash='dash'),
                name="Base (1000)",
                hoverinfo='skip'
            ))
            
            fig_index.update_layout(
                title="OSRS 100 Daily Index Level",
                template="plotly_dark",
                paper_bgcolor="#1E1E1E",
                plot_bgcolor="#1E1E1E",
                margin=dict(l=20, r=20, t=40, b=20),
                xaxis=dict(showgrid=True, gridcolor="#222222", title=""),
                yaxis=dict(showgrid=True, gridcolor="#222222", title="Index Level", zeroline=False),
                showlegend=False
            )
            st.plotly_chart(fig_index, use_container_width=True)
            
        with chart_col2:
            fig_monthly = go.Figure()
            colors = ['#FF4136' if val < 0 else '#2ECC40' for val in monthly_returns['return']]
            
            fig_monthly.add_trace(go.Bar(
                x=monthly_returns['year_month'],
                y=monthly_returns['return'] * 100,
                marker_color=colors,
                text=[f"{val*100:+.1f}%" for val in monthly_returns['return']],
                textposition='auto',
                name="Monthly Return"
            ))
            
            fig_monthly.update_layout(
                title="Monthly MTM Returns",
                template="plotly_dark",
                paper_bgcolor="#1E1E1E",
                plot_bgcolor="#1E1E1E",
                margin=dict(l=20, r=20, t=40, b=20),
                xaxis=dict(showgrid=False, title="", type='category'),
                yaxis=dict(showgrid=True, gridcolor="#222222", title="Return (%)", zeroline=True, zerolinecolor="white"),
                showlegend=False
            )
            st.plotly_chart(fig_monthly, use_container_width=True)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_index['date'], 
            y=df_index['index_level'],
            mode='lines',
            line=dict(color='#FFD700', width=3),
            name="OSRS 100"
        ))
        
        fig.update_layout(
            title="OSRS 100 Daily Index Level",
            template="plotly_dark",
            paper_bgcolor="#1E1E1E",
            plot_bgcolor="#1E1E1E",
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(showgrid=True, gridcolor="#222222", title=""),
            yaxis=dict(showgrid=True, gridcolor="#222222", title="")
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader(f"Current Constituents (Rebalanced: {latest_rebal.strftime('%Y-%m-%d')})")
        
        active_latest = df_latest[df_latest['status'] != 'DROP'].sort_values(by='weight', ascending=False).copy()
        top_20 = active_latest.head(20)
        
        # Concentration metrics
        top_5_weight = active_latest.head(5)['weight'].sum()
        top_10_weight = active_latest.head(10)['weight'].sum()
        
        col_bar, col_metrics = st.columns([3, 1])
        
        with col_bar:
            fig_bar = go.Figure(data=[go.Bar(
                x=top_20['item_name'],
                y=top_20['weight'] * 100,
                marker_color='#00FF00',
                text=[f"{w*100:.1f}%" for w in top_20['weight']],
                textposition='auto'
            )])
            
            fig_bar.update_layout(
                title="Top 20 Constituents by Weight",
                template="plotly_dark",
                paper_bgcolor="#1E1E1E",
                plot_bgcolor="#1E1E1E",
                yaxis_title="Weight (%)",
                xaxis_tickangle=-45,
                margin=dict(t=40, b=100)
            )
            
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with col_metrics:
            st.markdown("### Concentration")
            st.metric("Top 5 Items", f"{top_5_weight*100:.1f}%")
            st.metric("Top 10 Items", f"{top_10_weight*100:.1f}%")
            st.markdown(f"**Single-Name Cap:** 8.0%")
            
            if not df_ad.empty:
                latest_ads = df_ad[df_ad['rebalance_date'] == latest_rebal]
                add_count = len(latest_ads[latest_ads['action'] == 'ADD'])
                drop_count = len(latest_ads[latest_ads['action'] == 'DROP'])
                st.markdown("### Turnover")
                st.markdown(f"**Adds:** {add_count}")
                st.markdown(f"**Drops:** {drop_count}")
                
        # FULL CONSTITUENTS TABLE
        with st.expander("🔍 View Full OSRS 100 Constituent List"):
            display_df = active_latest[['rank', 'item_name', 'item_id', 'weight']].copy()
            display_df['weight'] = (display_df['weight'] * 100).map('{:.2f}%'.format)
            display_df = display_df.rename(columns={
                'rank': 'Rank (by Traded Value)',
                'item_name': 'Item Name',
                'item_id': 'Item ID',
                'weight': 'Index Weight'
            })
            st.dataframe(display_df.set_index('Rank (by Traded Value)'), use_container_width=True)
        
        if not df_ad.empty:
            st.markdown("---")
            st.subheader("Latest Rebalance Adds & Drops")
            
            col_add, col_drop = st.columns(2)
            
            latest_ads = df_ad[df_ad['rebalance_date'] == latest_rebal]
            ad_adds = latest_ads[latest_ads['action'] == 'ADD'][['item_name', 'new_weight', 'reason']].copy()
            ad_drops = latest_ads[latest_ads['action'] == 'DROP'][['item_name', 'prior_weight', 'reason']].copy()
            
            with col_add:
                st.markdown("### 🟢 Adds")
                if ad_adds.empty:
                    st.write("No adds this month.")
                else:
                    ad_adds['new_weight'] = (ad_adds['new_weight'] * 100).map('{:.2f}%'.format)
                    ad_adds = ad_adds.rename(columns={'item_name': 'Item', 'new_weight': 'New Weight', 'reason': 'Reason'})
                    st.dataframe(ad_adds, use_container_width=True, hide_index=True)
                    
            with col_drop:
                st.markdown("### 🔴 Drops")
                if ad_drops.empty:
                    st.write("No drops this month.")
                else:
                    ad_drops['prior_weight'] = (ad_drops['prior_weight'] * 100).map('{:.2f}%'.format)
                    ad_drops = ad_drops.rename(columns={'item_name': 'Item', 'prior_weight': 'Prior Weight', 'reason': 'Reason'})
                    st.dataframe(ad_drops, use_container_width=True, hide_index=True)
                    
        # DIAGNOSTICS & EXCLUSIONS
        try:
            df_diag = pd.read_csv("market_data/osrs_100_diagnostics.csv")
            df_diag['rebalance_date'] = pd.to_datetime(df_diag['rebalance_date'])
            latest_diag = df_diag[df_diag['rebalance_date'] == latest_rebal]
            
            if not latest_diag.empty:
                st.markdown("---")
                with st.expander("🩺 Eligibility Diagnostics (Latest Rebalance Universe)"):
                    diag_cols = st.columns(3)
                    diag_cols[0].metric("Candidate Universe", len(latest_diag))
                    diag_cols[1].metric("Eligible Items", len(latest_diag[latest_diag['eligible']==True]))
                    diag_cols[2].metric("Ineligible Items", len(latest_diag[latest_diag['eligible']==False]))
                    
                    st.markdown("##### Ineligible Universe & Reasons")
                    ineligibles = latest_diag[latest_diag['eligible'] == False].copy()
                    if ineligibles.empty:
                        st.write("No ineligible items flagged in the candidate universe.")
                    else:
                        ineligibles = ineligibles[['item_name', 'priced_days', 'volume_days', 'exclusion_reason']].sort_values(by='priced_days', ascending=False)
                        st.dataframe(ineligibles, use_container_width=True, hide_index=True)
        except:
            pass
        
        st.markdown("---")
        with st.expander("📖 Methodology & Interpretation"):
            st.markdown("""
            ### The OSRS 100 Benchmark
            The OSRS 100 is an economic barometer designed to conceptually mimic real-world indices like the S&P 500, but applied to the Grand Exchange. It provides a daily snapshot of the broader Old School RuneScape economy.
            
            *History spans back to early 2026, anchoring daily prices against a base level of 1000.*

            ### Methodology
            - **Universe & Eligibility:** Items are eligible if they traded for at least 45 out of the last 60 days with meaningful consistent volume.
            - **Selection:** The top 100 eligible items are selected based on their **Average Daily Traded GP Value** (Fair Price × Volume) over the trailing 60 days.
            - **Weighting Basis (Not Market Cap!):** Because there is no concept of "shares outstanding" or "circulating supply" in OSRS, we cannot use true Market Cap. Instead, we use Trailing Traded Value as our proxy for economic importance.
            - **Normalization:** Constituents are weighted by the **square root** of their traded value. This dampens hyper-volume items (like Fire Runes or Zulrah Scales) from absorbing 99% of the index.
            - **Capping:** No single item can ever exceed an **8.0%** weight. Any excess weight is redistributed proportionally.
            - **Rebalancing:** The index resets its weights, identifies drops, and promotes adds strictly on the 1st of every month holding index continuity constant across the barrier.

            ### Known Limitations
            - **No Sector Caps:** The `items.csv` catalog lacks structured item typologies (e.g., "Armor", "Runes", "Supplies"). Therefore, we cannot enforce standard sector maximums (e.g. 25% max category caps).
            - **Pricing Anchors:** Daily prices are computed using an aggregated VWAP (Volume Weighted Average Price) of hourly snapshots. Gaps in pricing are carried forward for up to 3 days before an item is considered completely stale.
            """)
            
    except Exception as e:
        st.error(f"Waiting for index data to generate... ({e})")