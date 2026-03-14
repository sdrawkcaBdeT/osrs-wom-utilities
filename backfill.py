import pandas as pd
import os
from datetime import timedelta
from wealth_engine import WealthEngine, GENESIS

# Your exact Notepad entries (The Ground Truths)
MANUAL_ENTRIES =[
    {
        "timestamp": "2026-01-13T00:00:00.000000",
        "gear": 395000000.0, "supplies": 33000000.0, "drops": 2000000.0, "ge": 8000000.0, "total": 438000000.0,
        "gear_delta": 0.0, "supplies_delta": 0.0, "drops_delta": 0.0, "ge_delta": 0.0, "total_delta": 0.0,
        "hours_logged": 0.0, "days_elapsed": 1.0, "hours_per_day": 0.0,
        "net_gp_hr": 0.0, "no_gear_gp_hr": 0.0,
        "tbow_cost": 1600000000.0, "gap": 1162000000.0, "progress_pct": 27.4,
        "played_hours_rem": 1162.0, "real_days_rem": 1161.0, "eta_date": "2029/03/20"
    },
    {
        "timestamp": "2026-02-02T19:12:00.000000",
        "gear": 379000000.0, "supplies": 34000000.0, "drops": 22000000.0, "ge": 20000000.0, "total": 455000000.0,
        "gear_delta": -20000000.0, "supplies_delta": 1000000.0, "drops_delta": 20000000.0, "ge_delta": 12000000.0, "total_delta": 17000000.0,
        "hours_logged": 59.27, "days_elapsed": 20.0, "hours_per_day": 2.97,
        "net_gp_hr": 287000.0, "no_gear_gp_hr": 624000.0,
        "tbow_cost": 1588000000.0, "gap": 1133000000.0, "progress_pct": 28.7,
        "played_hours_rem": 3948.0, "real_days_rem": 1329.0, "eta_date": "2029/09/24"
    },
    {
        "timestamp": "2026-02-17T17:44:00.000000",
        "gear": 376000000.0, "supplies": 65000000.0, "drops": 40000000.0, "ge": 54000000.0, "total": 535000000.0,
        "gear_delta": -19000000.0, "supplies_delta": 32000000.0, "drops_delta": 38000000.0, "ge_delta": 46000000.0, "total_delta": 97000000.0,
        "hours_logged": 67.38, "days_elapsed": 35.0, "hours_per_day": 1.93,
        "net_gp_hr": 1440000.0, "no_gear_gp_hr": 1722000.0,
        "tbow_cost": 1602000000.0, "gap": 1067000000.0, "progress_pct": 33.4,
        "played_hours_rem": 740.0, "real_days_rem": 383.0, "eta_date": "2027/03/07"
    },
    {
        "timestamp": "2026-02-22T20:45:00.000000",
        "gear": 386000000.0, "supplies": 66000000.0, "drops": 47000000.0, "ge": 59000000.0, "total": 558000000.0,
        "gear_delta": -9000000.0, "supplies_delta": 33000000.0, "drops_delta": 45000000.0, "ge_delta": 51000000.0, "total_delta": 120000000.0,
        "hours_logged": 75.75, "days_elapsed": 40.0, "hours_per_day": 1.89,
        "net_gp_hr": 1584000.0, "no_gear_gp_hr": 1703000.0,
        "tbow_cost": 1635000000.0, "gap": 1077000000.0, "progress_pct": 34.1,
        "played_hours_rem": 680.0, "real_days_rem": 360.0, "eta_date": "2027/02/17"
    }
]

def get_row_dict(engine, target_now, genesis_dt):
    """Helper to calculate the wealth engine state at a specific time."""
    live_totals, tbow_cost, calc_now = engine.calculate_live_wealth(target_now=target_now)
    
    tgt_tot = sum(live_totals.values())
    days_elapsed = max((calc_now - genesis_dt).total_seconds() / 86400.0, 1.0)
    hours_logged = engine.get_hours_logged(genesis_dt, calc_now)
    hours_per_day = hours_logged / days_elapsed
    
    delta_wealth = tgt_tot - GENESIS['Total']
    net_gp_hr = delta_wealth / hours_logged if hours_logged > 0 else 0
    gear_delta = live_totals['Gear'] - GENESIS['Gear']
    no_gear_gp_hr = (delta_wealth - gear_delta) / hours_logged if hours_logged > 0 else 0
    
    gap = tbow_cost - tgt_tot
    progress_pct = (tgt_tot / tbow_cost) * 100 if tbow_cost else 0
    
    played_hours_rem = gap / net_gp_hr if net_gp_hr > 0 else 0
    real_days_rem = played_hours_rem / hours_per_day if hours_per_day > 0 else 0
    if real_days_rem > 10000: real_days_rem = 10000
    
    eta_date = calc_now + timedelta(days=real_days_rem)
    
    return {
        "timestamp": calc_now,
        "gear": live_totals['Gear'], "supplies": live_totals['Supplies'],
        "drops": live_totals['Drops'], "ge": live_totals['GE'], "total": tgt_tot,
        "gear_delta": live_totals['Gear'] - GENESIS['Gear'],
        "supplies_delta": live_totals['Supplies'] - GENESIS['Supplies'],
        "drops_delta": live_totals['Drops'] - GENESIS['Drops'],
        "ge_delta": live_totals['GE'] - GENESIS['GE'],
        "total_delta": delta_wealth,
        "hours_logged": hours_logged, "days_elapsed": days_elapsed, "hours_per_day": hours_per_day,
        "net_gp_hr": net_gp_hr, "no_gear_gp_hr": no_gear_gp_hr,
        "tbow_cost": tbow_cost, "gap": gap, "progress_pct": progress_pct,
        "played_hours_rem": played_hours_rem, "real_days_rem": real_days_rem,
        "eta_date": eta_date.strftime('%Y/%m/%d')
    }

def main():
    print("--- 🚀 Time Travel Engine: The Bridge ---")
    engine = WealthEngine()
    
    # 1. Identify the Transition Point (The Bank Snapshot)
    snapshot_date, _ = engine.load_current_state()
    genesis_dt = pd.to_datetime(GENESIS['date'])
    today = pd.Timestamp.now()
    
    print(f"Era 1: Interpolating from Genesis ({genesis_dt.date()}) to Snapshot ({snapshot_date.date()})")
    
    # Calculate the exact state AT the snapshot to act as the final interpolation anchor
    snapshot_row = get_row_dict(engine, snapshot_date, genesis_dt)
    
    # Combine Manual Entries with the Snapshot Anchor
    df_manual = pd.DataFrame(MANUAL_ENTRIES)
    df_manual['timestamp'] = pd.to_datetime(df_manual['timestamp'])
    
    anchor_df = pd.DataFrame([snapshot_row])
    df_bridge = pd.concat([df_manual, anchor_df], ignore_index=True)
    
    # Apply Pandas Magic: Resample to Hourly and Interpolate missing data linearly
    df_bridge.set_index('timestamp', inplace=True)
    numeric_cols = df_bridge.select_dtypes(include='number').columns
    
    # Ensure all hour buckets exist, interpolate numbers, forward-fill strings (like ETA dates)
    df_bridge = df_bridge.resample('h').asfreq()
    df_bridge[numeric_cols] = df_bridge[numeric_cols].interpolate(method='time')
    df_bridge = df_bridge.ffill().reset_index()
    
    # ---
    
    print(f"Era 2: Calculating Automated Live Wealth from Snapshot to Today...")
    # Calculate everything after the snapshot using the actual GPPH Engine
    date_range_live = pd.date_range(start=snapshot_date + pd.Timedelta(hours=1), end=today, freq='h')
    
    live_rows =[]
    total_steps = len(date_range_live)
    
    for i, target_now in enumerate(date_range_live):
        if i % 12 == 0:  # Print update every 12 calculated hours
            print(f"[{i}/{total_steps}] Processing: {target_now.strftime('%Y-%m-%d %H:%M')}")
        row = get_row_dict(engine, target_now, genesis_dt)
        live_rows.append(row)
        
    df_live = pd.DataFrame(live_rows)
    
    # Combine the Bridge (Past) with the Engine (Present)
    final_df = pd.concat([df_bridge, df_live], ignore_index=True)
    
    # Format timestamps cleanly for the CSV
    final_df['timestamp'] = final_df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
    
    final_df.to_csv("wealth_history.csv", index=False)
    print(f"\n✅ Rebuild complete! Generated {len(final_df)} hourly records connecting your notepad to the live engine.")

if __name__ == "__main__":
    main()