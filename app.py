import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os
import json
import glob
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="OSRS Strategic Dashboard", layout="wide", page_icon="🐉")
GEAR_FILE = "gear.json"
WEALTH_LOG_FILE = "manual_wealth_log.csv"
ITEMS_FILE = "items.csv"
SNAPSHOT_DIR = "price_snapshots"
TBOW_ID = 20997 

# --- DATA LOADING ---

@st.cache_data
def load_reference_data():
    if os.path.exists(ITEMS_FILE):
        df = pd.read_csv(ITEMS_FILE)
        return pd.Series(df.id.values, index=df.name).to_dict()
    return {}

@st.cache_data
def load_main_data():
    # 1. Financials
    if os.path.exists("gpph_enriched.csv"):
        df_fin = pd.read_csv("gpph_enriched.csv")
        df_fin['item_name'] = df_fin['item_name'].fillna('Coins')
        df_fin['local_start_time'] = pd.to_datetime(df_fin['local_start_time'])
        
        # --- FIX: Ensure Coins have value ---
        # If Item ID is 995 (Coins), force total_value = qty_delta * 1
        # Assuming ID column exists as 'item_id'. If not, we use name.
        mask_coins = df_fin['item_name'] == 'Coins'
        df_fin.loc[mask_coins, 'total_value'] = df_fin.loc[mask_coins, 'qty_delta']
        df_fin.loc[mask_coins, 'hist_price_unit'] = 1
    else:
        df_fin = pd.DataFrame()

    # 2. Time Ledger
    if os.path.exists("time_ledger_enriched.csv"):
        df_time = pd.read_csv("time_ledger_enriched.csv")
        rename_map = {'start_time': 'start_timestamp', 'Start': 'start_timestamp'}
        df_time.rename(columns=rename_map, inplace=True)
        if 'start_timestamp' in df_time.columns:
            df_time['start_timestamp'] = pd.to_datetime(df_time['start_timestamp'])
        else:
            df_time['start_timestamp'] = pd.to_datetime(datetime.now())
    else:
        df_time = pd.DataFrame(columns=['start_timestamp', 'duration_hours'])

    # 3. BBD Logs
    bbd_records = []
    for f in glob.glob(os.path.join("bbd_data", "*.json")):
        try:
            with open(f, 'r') as file:
                data = json.load(file)
                sess_id = data.get('session_id')
                exp_name = data.get('config', {}).get('experiment_name', '0')
                try: mapped_id = int(exp_name)
                except: mapped_id = -1
                
                # Metrics
                start_ts = datetime.fromisoformat(data['start_time'])
                end_ts = datetime.fromisoformat(data['end_time'])
                duration_sec = (end_ts - start_ts).total_seconds()
                duration_hours = duration_sec / 3600
                
                active = 0
                last = None
                killing = False
                for e in data.get('event_timeline', []):
                    ts = datetime.fromisoformat(e['timestamp'])
                    if last and killing: active += (ts - last).total_seconds()
                    if e['type'] == 'phase': killing = ("KILLING" in e['value'])
                    last = ts
                
                # Uptime Efficiency (Time in cave vs Time logged in)
                eff = (active / duration_sec) if duration_sec > 0 else 0
                
                # --- Attack Efficiency ---
                total_attacks = data.get('total_attacks', 0)
                # Theoretical max assumes 3.0 seconds per attack (5 ticks)
                theoretical_attacks = active / 3.0 
                attack_eff = (total_attacks / theoretical_attacks) if theoretical_attacks > 0 else 0
                
                bbd_records.append({
                    'session_mapped_id': mapped_id,
                    'efficiency_pct': eff,
                    'attack_eff_pct': attack_eff,  # <--- NEW
                    'duration_hours': duration_hours,
                    'total_kills': data.get('total_kills', 0),
                    'total_attacks': total_attacks, # <--- NEW
                    'drops': data.get('loot_summary', {}),
                    'config': data.get('config', {})
                })
        except: pass
    
    df_bbd = pd.DataFrame(bbd_records)
    
    if not df_fin.empty and not df_bbd.empty:
        merged = pd.merge(df_fin, df_bbd, left_on='session_name', right_on='session_mapped_id', how='left')
    else:
        merged = df_fin
        
    return merged, df_time, df_bbd

def get_daily_prices(item_ids, start_date, end_date):
    dates = pd.date_range(start_date, end_date)
    price_history = pd.DataFrame(index=dates, columns=item_ids)
    
    if not os.path.exists(SNAPSHOT_DIR): return price_history.fillna(0)
    available_files = sorted([f for f in os.listdir(SNAPSHOT_DIR) if f.startswith("prices_")])
    
    for d in dates:
        target_ts = int(datetime(d.year, d.month, d.day, 12, 0).timestamp())
        best_file = None
        min_diff = float('inf')
        for f in available_files:
            try:
                ts = int(f.split('_')[1].split('.')[0])
                diff = abs(ts - target_ts)
                if diff < min_diff: min_diff, best_file = diff, f
            except: pass
            
        if best_file and min_diff < 86400: 
            try:
                df_snap = pd.read_csv(os.path.join(SNAPSHOT_DIR, best_file))
                snap_map = pd.Series(df_snap.avgHighPrice.values, index=df_snap.item_id).to_dict()
                for iid in item_ids:
                    val = snap_map.get(iid, 0)
                    if val == 0:
                        row = df_snap[df_snap['item_id'] == iid]
                        if not row.empty: val = row.iloc[0]['avgLowPrice']
                    price_history.at[d, iid] = val
            except: pass
    return price_history.ffill().bfill().fillna(0)

def calculate_gear_value_history(start_date, end_date):
    if not os.path.exists(GEAR_FILE): return pd.Series(0, index=pd.date_range(start_date, end_date))
    with open(GEAR_FILE) as f: gear_dict = json.load(f).get('gear', {})
    item_map = load_reference_data()
    gear_ids = [item_map[name] for name in gear_dict.values() if name in item_map]
    if not gear_ids: return pd.Series(0, index=pd.date_range(start_date, end_date))
    return get_daily_prices(gear_ids, start_date, end_date).sum(axis=1)

def get_tbow_history(start_date, end_date):
    return get_daily_prices([TBOW_ID], start_date, end_date)[TBOW_ID]

def load_wealth_log():
    if os.path.exists(WEALTH_LOG_FILE):
        df = pd.read_csv(WEALTH_LOG_FILE)
        df['date'] = pd.to_datetime(df['date'])
        if 'gear_m' in df.columns: df = df.drop(columns=['gear_m'])
        return df
    return pd.DataFrame(columns=['date', 'supply_m', 'drops_m', 'ge_m'])

def save_wealth_log(date, supply, drops, ge):
    df = load_wealth_log()
    new_row = pd.DataFrame({'date': [pd.to_datetime(date)], 'supply_m': [supply], 'drops_m': [drops], 'ge_m': [ge]})
    df = pd.concat([df, new_row]).sort_values('date').drop_duplicates(subset=['date'], keep='last')
    df.to_csv(WEALTH_LOG_FILE, index=False)

# --- LOAD STATE ---
df_main, df_time, df_bbd = load_main_data()
df_wealth = load_wealth_log()

# --- SIDEBAR ---
st.sidebar.header("Wealth Logger")
with st.sidebar.form("wealth_form"):
    st.write("Log Value (Millions)")
    w_date = st.date_input("Date")
    def_sup, def_drop, def_ge = 33.0, 2.0, 8.0
    if not df_wealth.empty:
        last = df_wealth.iloc[-1]
        def_sup, def_drop, def_ge = last.get('supply_m', 33.0), last.get('drops_m', 2.0), last.get('ge_m', 8.0)
    in_sup = st.number_input("Supplies", value=float(def_sup))
    in_drop = st.number_input("Drops", value=float(def_drop))
    in_ge = st.number_input("GE", value=float(def_ge))
    if st.form_submit_button("Save Check-in"):
        save_wealth_log(w_date, in_sup, in_drop, in_ge)
        st.rerun()

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["Session Audit", "Wealth & Forecast", "The Lab"])

# ==============================================================================
# TAB 1: SESSION AUDIT
# ==============================================================================
with tab1:
    if not df_main.empty:
        sessions = sorted(df_main['session_name'].unique().tolist(), 
                          key=lambda x: int(x) if str(x).isdigit() else 0, reverse=True)
        sel_id = st.selectbox("Select Session", sessions)
        
        sess_data = df_main[df_main['session_name'] == sel_id].copy()
        meta = df_bbd[df_bbd['session_mapped_id'] == sel_id]
        
        drops_exp = meta.iloc[0]['drops'] if not meta.empty else {}
        eff_pct = meta.iloc[0]['efficiency_pct'] if not meta.empty else 0
        dur_hrs = meta.iloc[0]['duration_hours'] if not meta.empty else 0
        kills_total = meta.iloc[0]['total_kills'] if not meta.empty else 0
        
        gross = sess_data[sess_data['category'] == 'LOOT']['total_value'].sum()
        supply = sess_data[sess_data['category'] == 'SUPPLY']['total_value'].sum()
        net = gross + supply
        
        # Calculate Scavenged for Metrics
        scavenged_total = 0
        for _, row in sess_data[sess_data['category'] == 'LOOT'].iterrows():
            item, qty, price = row['item_name'], row['qty_delta'], row['hist_price_unit']
            exp_qty = drops_exp.get(item, 0)
            if qty > exp_qty: scavenged_total += (qty - exp_qty) * price

        kills_per_hr = kills_total / dur_hrs if dur_hrs > 0 else 0
        gp_per_hr = net / dur_hrs if dur_hrs > 0 else 0
        
        # Metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Net Profit", f"{net:,.0f} gp")
        c2.metric("Supply Burn", f"{supply:,.0f} gp")
        c3.metric("Bot Subsidy", f"{scavenged_total:,.0f} gp")
        c4.metric("GP / Hour", f"{gp_per_hr:,.0f}") 
        
        # Expanded columns to fit the new metric
        c5, c6, c7, c8, c9 = st.columns(5)
        c5.metric("Total Kills", f"{kills_total}")
        c6.metric("Kills / Hr", f"{kills_per_hr:.1f}") 
        c7.metric("Uptime Eff.", f"{eff_pct*100:.1f}%")
        
        # --- NEW: Display Attack Efficiency ---
        attk_eff = meta.iloc[0]['attack_eff_pct'] if 'attack_eff_pct' in meta.columns else 0
        c8.metric("Attack Eff.", f"{attk_eff*100:.1f}%") 
        
        c9.metric("Duration", f"{dur_hrs:.2f} hrs")
        
        st.divider()

        # --- WATERFALL CHART PREP ---
        # 1. Income Items (Split Bot Drops)
        wf_names = []
        wf_values = []
        wf_types = []
        wf_text = []
        
        loot_df = sess_data[sess_data['category'] == 'LOOT'].sort_values('total_value', ascending=False)
        
        for _, row in loot_df.iterrows():
            item = row['item_name']
            qty = row['qty_delta']
            price = row['hist_price_unit']
            val = row['total_value']
            
            exp_qty = drops_exp.get(item, 0)
            
            if qty > exp_qty and exp_qty >= 0:
                # Split It
                org_val = exp_qty * price
                bot_val = (qty - exp_qty) * price
                
                if org_val > 0:
                    wf_names.append(item)
                    wf_values.append(org_val)
                    wf_types.append("relative")
                    wf_text.append(f"+{org_val/1000:.0f}k")
                
                if bot_val > 0:
                    wf_names.append(f"Bot Drop - {item}")
                    wf_values.append(bot_val)
                    wf_types.append("relative")
                    wf_text.append(f"+{bot_val/1000:.0f}k")
            else:
                # Normal
                wf_names.append(item)
                wf_values.append(val)
                wf_types.append("relative")
                wf_text.append(f"+{val/1000:.0f}k")

        # 2. Net Revenue Subtotal
        wf_names.append("Gross Revenue")
        wf_values.append(0) # Plotly calculates the sum automatically for 'total'
        wf_types.append("total")
        wf_text.append(f"{gross/1000:.0f}k")

        # 3. Expenses (Sorted smallest negative to largest negative to create stairs down)
        supply_df = sess_data[sess_data['category'] == 'SUPPLY'].sort_values('total_value', ascending=True)
        
        for _, row in supply_df.iterrows():
            wf_names.append(row['item_name'])
            wf_values.append(row['total_value']) # Negative
            wf_types.append("relative")
            wf_text.append(f"{row['total_value']/1000:.0f}k")

        # 4. Final Profit
        wf_names.append("Net Profit")
        wf_values.append(0)
        wf_types.append("total")
        wf_text.append(f"{net/1000:.0f}k")

        fig_wf = go.Figure(go.Waterfall(
            orientation = "v",
            measure = wf_types,
            x = wf_names,
            textposition = "outside",
            text = wf_text,
            y = wf_values,
            connector = {"line":{"color":"rgb(63, 63, 63)"}},
            decreasing = {"marker":{"color":"#EF553B"}},
            increasing = {"marker":{"color":"#00CC96"}},
            totals = {"marker":{"color":"#636EFA"}}
        ))
        
        fig_wf.update_layout(title="Session Profit & Loss", showlegend=False, height=550)
        st.plotly_chart(fig_wf, use_container_width=True)
        
        # Detailed Ledger
        st.markdown("### 📋 Detailed Ledger")
        st.dataframe(sess_data[['item_name', 'qty_delta', 'hist_price_unit', 'total_value']].sort_values('total_value', ascending=False), height=400)

# ==============================================================================
# TAB 2: WEALTH & FORECAST
# ==============================================================================
with tab2:
    if df_wealth.empty:
        st.info("Log your Wealth (Sidebar) to initialize the Forecast.")
    else:
        st.header("The Road to the Twisted Bow")
        start_date, end_date = df_wealth['date'].min(), datetime.now()
        date_range = pd.date_range(start_date, end_date)
        ts_df = pd.merge(pd.DataFrame({'date': date_range}), df_wealth, on='date', how='left')
        cols = ['supply_m', 'drops_m', 'ge_m']
        ts_df[cols] = ts_df[cols].interpolate(method='linear').ffill().bfill()
        
        gear_vals = calculate_gear_value_history(start_date, end_date).values
        tbow_vals = get_tbow_history(start_date, end_date).values
        
        ts_df['gear_m'] = gear_vals / 1e6
        ts_df['tbow_price'] = tbow_vals
        ts_df['total_m'] = ts_df['gear_m'] + ts_df['supply_m'] + ts_df['drops_m'] + ts_df['ge_m']
        
        start_row, curr_row = ts_df.iloc[0], ts_df.iloc[-1]
        
        valid_time = df_time[df_time['start_timestamp'] <= end_date] if 'start_timestamp' in df_time.columns else pd.DataFrame()
        hours_logged = valid_time['duration_hours'].sum() if not valid_time.empty else 1.0
        days_elapsed = max((end_date - start_date).days, 1)
        hours_per_day = hours_logged / days_elapsed
        
        total_chg = curr_row['total_m'] - start_row['total_m']
        liq_chg = (curr_row['drops_m'] + curr_row['ge_m'] + curr_row['supply_m']) - (start_row['drops_m'] + start_row['ge_m'] + start_row['supply_m'])
        
        net_gp_hr = (total_chg * 1e6) / hours_logged if hours_logged > 0 else 0
        no_gear_gp_hr = (liq_chg * 1e6) / hours_logged if hours_logged > 0 else 0
        
        curr_tbow = curr_row['tbow_price'] if curr_row['tbow_price'] > 0 else 1.6e9
        curr_nw = curr_row['total_m'] * 1e6
        gap = curr_tbow - curr_nw
        pct = curr_nw / curr_tbow
        
        est_hours = gap / net_gp_hr if net_gp_hr > 0 else 0
        est_days = est_hours / hours_per_day if hours_per_day > 0 else 0
        comp_date = datetime.now() + timedelta(days=est_days)
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("### 📊 Status Report")
            w_data = {
                "Asset": ["Gear", "Supplies", "Drops", "GE", "TOTAL"],
                "Value (M)": [curr_row['gear_m'], curr_row['supply_m'], curr_row['drops_m'], curr_row['ge_m'], curr_row['total_m']],
                "Change (M)": [curr_row['gear_m'] - start_row['gear_m'], curr_row['supply_m'] - start_row['supply_m'], curr_row['drops_m'] - start_row['drops_m'], curr_row['ge_m'] - start_row['ge_m'], total_chg]
            }
            st.dataframe(pd.DataFrame(w_data).style.format(subset=["Value (M)", "Change (M)"], formatter="{:,.1f}"), hide_index=True)
            
            st.write(f"**Hours Logged:** {hours_logged:.1f}")
            st.write(f"**Net GP/Hr:** {net_gp_hr:,.0f} gp")
            st.write(f"**No Gear Loss:** {no_gear_gp_hr:,.0f} gp")
            st.divider()
            st.write(f"**Gap:** {gap/1e6:,.1f} M")
            st.write(f"**Est. Remaining Hours:** {est_hours:.0f}")
            st.progress(min(pct, 1.0))
            st.caption(f"Est. Completion: {comp_date.strftime('%Y-%m-%d')}")

        with c2:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=ts_df['date'], y=ts_df['ge_m'], stackgroup='one', name='GE'))
            fig.add_trace(go.Scatter(x=ts_df['date'], y=ts_df['drops_m'], stackgroup='one', name='Drops'))
            fig.add_trace(go.Scatter(x=ts_df['date'], y=ts_df['supply_m'], stackgroup='one', name='Supplies'))
            fig.add_trace(go.Scatter(x=ts_df['date'], y=ts_df['gear_m'], stackgroup='one', name='Gear'))
            fig.add_trace(go.Scatter(x=ts_df['date'], y=ts_df['tbow_price']/1e6, mode='lines', name='T-Bow Price', line=dict(color='white', width=2, dash='dash')))
            fig.update_layout(title="Net Worth vs Market", yaxis_title="Millions (GP)", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# TAB 3: THE LAB
# ==============================================================================
with tab3:
    st.header("Experimental Analysis")
    if not df_bbd.empty:
        configs = pd.json_normalize(df_bbd['config'])
        lab_df = pd.concat([df_bbd.drop('config', axis=1), configs], axis=1)
        
        c1, c2 = st.columns(2)
        with c1:
            weps = st.multiselect("Weapon", lab_df['weapon'].unique(), default=lab_df['weapon'].unique())
            ammos = st.multiselect("Ammo", lab_df['ammo'].unique(), default=lab_df['ammo'].unique())
        filtered = lab_df[lab_df['weapon'].isin(weps) & lab_df['ammo'].isin(ammos)]
        
        with c2:
            var = st.selectbox("Compare By", ['prayer', 'ring', 'feet'])
        res = filtered.groupby(var).agg({'total_kills': 'mean', 'efficiency_pct': 'mean', 'session_mapped_id': 'count'}).reset_index()
        st.table(res)