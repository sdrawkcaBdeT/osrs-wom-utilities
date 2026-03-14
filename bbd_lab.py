import streamlit as st
import pandas as pd
import statsmodels.api as sm
import numpy as np
import itertools

st.set_page_config(page_title="BBD Laboratory", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS FOR THE DARK/NEON THEME ---
st.markdown("""
    <style>
    .stApp { background-color: #0A0A0A; color: #FFFFFF; }
    .upgrade { color: #00FF00; font-weight: bold; }
    .trap { color: #FF4444; font-weight: bold; }
    .placebo { color: #888888; font-style: italic; }
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

@st.cache_data
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

# --- 5. RUN REGRESSION ---
X = df[cols_to_keep].astype(float) 
X = sm.add_constant(X) 
y = df['t_ngp_hr'].astype(float)

try:
    model = sm.OLS(y, X, missing=missing_handling).fit()
except Exception as e:
    st.error(f"Regression failed. This usually happens if you lack enough data after unchecking 'Impute'. Error: {e}")
    st.stop()

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
tab1, tab2, tab3 = st.tabs(["The Verdict (MLR)", "Optimizer", "Experiment Matrix"])

with tab1:
    st.header("Gear Analysis Verdicts")
    st.markdown(f"**Baseline Setup:** `{', '.join(baseline_items.values())}`")
    valid_sessions = len(y) if missing_handling == 'none' else len(y.dropna())
    st.markdown(f"**Baseline Net GP/hr:** `{model.params['const']:,.0f} GP/hr` *(Sample: {valid_sessions} sessions)*")
    
    st.markdown("---")
    st.subheader("The Cost of Sloth (Human Error Variables)")
    
    # Display Human Error Cards
    if human_error_results:
        cols_human = st.columns(2)
        for i, row in enumerate(human_error_results):
            with cols_human[i % 2]:
                st.markdown(f"""
                <div style='background-color: #330000; padding: 15px; border-radius: 5px; border: 1px solid #FF4444; margin-bottom: 20px;'>
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
                st.markdown(f"""
                <div style='background-color: #111111; padding: 15px; border-radius: 5px; border: 1px solid #333; margin-bottom: 10px;'>
                    <h4 style='margin:0; color: #FFF;'>{row['Item']}</h4>
                    <h2 style='margin:0; color: {"#00FF00" if row["Impact (GP/hr)"] > 0 else "#FF4444"};'>
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
                st.markdown(f"""
                <div style='background-color: #1a1a00; padding: 15px; border-radius: 5px; border: 1px solid #FFD700; margin-bottom: 10px;'>
                    <h4 style='margin:0; color: #FFF;'>{row['Item']}</h4>
                    <h2 style='margin:0; color: {"#FFD700" if row["Impact (GP/hr)"] > 0 else "#FF4444"};'>
                        {row['Impact (GP/hr)']:+,.0f} GP/hr
                    </h2>
                    <p style='margin:0; color: { "#888" if row["P-Value"] > 0.10 else "#FFF"};'>
                        {row['Verdict']} (p={row['P-Value']:.3f})
                    </p>
                </div>
                """, unsafe_allow_html=True)

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