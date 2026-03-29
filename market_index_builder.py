import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime
import json

# ==========================================
# CONFIGURATION
# ==========================================
PRICES_DIR = "price_snapshots"
ITEMS_FILE = "items.csv"
OUTPUT_DIR = "market_data"

# Index Rules
LOOKBACK_DAYS = 60
MIN_PRICED_DAYS = 45
MIN_VOLUME_DAYS = 40
TARGET_CONSTITUENTS = 100
MAX_SINGLE_WEIGHT = 0.08
BASE_INDEX_VALUE = 1000.0

def _get_timestamp_from_filename(filename):
    basename = os.path.basename(filename)
    ts_str = basename.replace("prices_", "").replace(".csv", "")
    return int(ts_str)

def aggregate_daily_prices():
    """
    Reads all hourly prices_*.csv snapshots, aggregates volume,
    and computes a daily VWAP (Volume Weighted Average Price) per item.
    Caches the intermediate daily panel for speed on subsequent runs.
    """
    cache_file = os.path.join(OUTPUT_DIR, "osrs_100_daily_panel.csv")
    
    files = glob.glob(os.path.join(PRICES_DIR, "prices_*.csv"))
    if not files:
        print(f"CRITICAL WARNING: No snapshot files found in {PRICES_DIR}")
        return pd.DataFrame()
        
    # Check if cache needs invalidation
    newest_snapshot_time = max(os.path.getmtime(f) for f in files)
    
    if os.path.exists(cache_file):
        cache_time = os.path.getmtime(cache_file)
        if cache_time > newest_snapshot_time:
            print(f"Loading cached daily panel from {cache_file}...")
            df_daily = pd.read_csv(cache_file, parse_dates=["date"])
            # Ensure it's sorted
            df_daily = df_daily.sort_values(by=["date", "item_id"])
            return df_daily
        else:
            print("Newer price snapshots detected. Invalidating cache and rebuilding...")
    else:
        print("No daily panel cache found. Building daily panel from snapshots... (This may take a minute)")
        
    failed_files = 0
    all_rows = []
    
    for f in files:
        ts = _get_timestamp_from_filename(f)
        date_str = pd.to_datetime(ts, unit='s').date()
        
        try:
            df = pd.read_csv(f)
        except Exception as e:
            failed_files += 1
            print(f"Warning: Failed to read {f} ({e})")
            continue
            
        # Some rows might missing one side of the margin. Clean NaNs to 0s
        df = df.fillna(0)
        
        # We compute total traded value and volume for this snapshot
        df['high_val'] = df['avgHighPrice'] * df['highPriceVolume']
        df['low_val'] = df['avgLowPrice'] * df['lowPriceVolume']
        df['total_vol'] = df['highPriceVolume'] + df['lowPriceVolume']
        df['total_val'] = df['high_val'] + df['low_val']
        
        # Only keep items with volume for this hour
        df = df[df['total_vol'] > 0]
        
        # Build minimal dataframe to append
        df['date'] = date_str
        df = df[['date', 'item_id', 'total_vol', 'total_val']].copy()
        
        
        all_rows.append(df)
        
    if failed_files > 0:
        print(f"WARNING: {failed_files} snapshot files were skipped due to errors.")
        
    if not all_rows:
        print("CRITICAL WARNING: All snapshot files failed to load. Returns empty dataframe.")
        return pd.DataFrame()
        
    print(f"Concatenating {len(all_rows)} valid files...")    
    raw_df = pd.concat(all_rows, ignore_index=True)
    
    # Aggregate to daily
    print("Aggregating to daily grain...")
    df_daily = raw_df.groupby(['date', 'item_id']).sum().reset_index()
    
    # Compute the daily fair price (VWAP)
    df_daily['price'] = df_daily['total_val'] / df_daily['total_vol']
    
    # Clean up division by zero if any (shouldn't happen because we filtered total_vol > 0, but play it safe)
    df_daily['price'] = df_daily['price'].fillna(0)
    df_daily = df_daily[df_daily['price'] > 0]
    
    df_daily['date'] = pd.to_datetime(df_daily['date'])
    
    # Cache the result
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df_daily.to_csv(cache_file, index=False)
    print("Saved daily panel cache.")
    
    return df_daily

def _apply_weight_caps(weights_dict, cap=0.08):
    """
    Caps the maximum weight of any single item at `cap`, redistributing
    the excess proportionally among the remaining items.
    """
    weights = pd.Series(weights_dict)
    
    while True:
        capped_mask = weights > cap
        if not capped_mask.any():
            break
            
        excess_total = (weights[capped_mask] - cap).sum()
        weights[capped_mask] = cap
        
        uncapped_mask = ~capped_mask
        uncapped_sum = weights[uncapped_mask].sum()
        
        if uncapped_sum == 0:
            break
            
        # Distribute the excess proportionally based on current weight of uncapped
        weights[uncapped_mask] += excess_total * (weights[uncapped_mask] / uncapped_sum)
        
    return weights.to_dict()

def compute_monthly_rebalance(df_daily, rebalance_date):
    """
    Determines the top 100 constituent items and their weights for a given month.
    Based on the trailing 60 days of data. Returns (weights_dict, diagnostics_df).
    """
    # Filter trailing 60 days
    start_date = rebalance_date - pd.Timedelta(days=LOOKBACK_DAYS)
    df_lookback = df_daily[(df_daily['date'] >= start_date) & (df_daily['date'] < rebalance_date)].copy()
    
    if df_lookback.empty:
        return None, pd.DataFrame()
        
    # Calculate days of pricing history and volume history per item
    # We already filtered for total_vol > 0 in aggregate_daily_prices, 
    # but we will count distinct days.
    item_day_counts = df_lookback.groupby('item_id').size()
    item_total_vol = df_lookback.groupby('item_id')['total_vol'].sum()
    item_total_val = df_lookback.groupby('item_id')['total_val'].sum()
    
    # We approximate "meaningful volume days" as days where volume > 0, 
    # which is strictly all returned rows here due to upstream filtering.
    
    # Create diagnostics dataframe base
    diag_df = pd.DataFrame({
        'priced_days': item_day_counts,
        'volume_days': item_day_counts,  # Since we pre-filtered vol=0 upstream
        'trailing_60d_total_val': item_total_val,
        'trailing_60d_avg_daily_val': item_total_val / LOOKBACK_DAYS
    }).reset_index()
    
    # Determine Eligibility
    diag_df['eligible'] = True
    diag_df['exclusion_reason'] = ""
    
    mask_priced = diag_df['priced_days'] < MIN_PRICED_DAYS
    diag_df.loc[mask_priced, 'eligible'] = False
    diag_df.loc[mask_priced, 'exclusion_reason'] += f"Insufficient priced days (<{MIN_PRICED_DAYS}). "
    
    mask_vol = diag_df['volume_days'] < MIN_VOLUME_DAYS
    diag_df.loc[mask_vol, 'eligible'] = False
    diag_df.loc[mask_vol, 'exclusion_reason'] += f"Insufficient volume days (<{MIN_VOLUME_DAYS}). "
    
    # Initialize rank for all
    diag_df['rank'] = None
    
    # Filter and rank only eligibles
    eligible_df = diag_df[diag_df['eligible']].copy()
    
    if eligible_df.empty:
        print(f"WARNING: No eligible items found for rebalance date {rebalance_date}")
        return None, diag_df
        
    # Rank by 60d avg daily val
    eligible_df['rank'] = eligible_df['trailing_60d_avg_daily_val'].rank(ascending=False, method='min')
    
    # Push ranks back to main diag_df
    diag_df.set_index('item_id', inplace=True)
    eligible_df.set_index('item_id', inplace=True)
    diag_df.update(eligible_df[['rank']])
    diag_df.reset_index(inplace=True)
    eligible_df.reset_index(inplace=True)
    
    # Top TARGET_CONSTITUENTS
    top_items = eligible_df[eligible_df['rank'] <= TARGET_CONSTITUENTS].copy()
    diag_df['selected'] = diag_df['item_id'].isin(top_items['item_id'])
    
    if len(top_items) < TARGET_CONSTITUENTS:
        print(f"WARNING: Only {len(top_items)} eligible items found for index. Index will proceed heavily concentrated.")
    
    # Calculate Weights
    raw_weights = np.sqrt(top_items['trailing_60d_avg_daily_val'])
    
    # Add weighting basis to diagnostics
    diag_df['weighting_basis_sqrt_val'] = np.sqrt(diag_df['trailing_60d_avg_daily_val'])
    
    normalized_weights = raw_weights / raw_weights.sum()
    
    # Create dictionary to cap
    weight_dict_pre = dict(zip(top_items['item_id'], normalized_weights))
    capped_weights = _apply_weight_caps(weight_dict_pre, cap=MAX_SINGLE_WEIGHT)
    
    # Verify weights sum closely to 1.0
    weight_sum = sum(capped_weights.values())
    if not np.isclose(weight_sum, 1.0):
        print(f"CRITICAL WARNING: Capped weights sum to {weight_sum}, expected 1.0. Check cap logic.")
    
    return capped_weights, diag_df

def build_index():
    df_daily = aggregate_daily_prices()
    if df_daily.empty:
        print("Cannot build index. Daily panel is empty.")
        return
    
    # Identify unique dates
    all_dates = sorted(df_daily['date'].unique())
    if len(all_dates) < LOOKBACK_DAYS:
        print(f"Not enough data history ({len(all_dates)} days) to fulfill {LOOKBACK_DAYS}-day lookback.")
        return
        
    # We rebalance exclusively on the 1st of every month, but we need our "First Rebalance"
    # to just be the first date where we *have* 60 days of history.
    first_valid_date = all_dates[LOOKBACK_DAYS]
    
    rebalance_dates = []
    # Force the first available boundary
    rebalance_dates.append(first_valid_date)
    
    # After the initial start date, simply grab the first unique date of every month
    current_month_yr = (first_valid_date.year, first_valid_date.month)
    for d in all_dates:
        if d > first_valid_date and (d.year, d.month) != current_month_yr:
            rebalance_dates.append(d)
            current_month_yr = (d.year, d.month)
            
    # Also include the very end of history so the final month calculates bounds properly
    if all_dates[-1] not in rebalance_dates:
        # We won't rebalance here, just mark it for calculation boundaries
        pass
        
    print(f"Identified {len(rebalance_dates)} rebalance points.")

    # Pivot prices so we have dates as rows and items as columns
    print("Pivoting daily item prices for fast return calculation...")
    price_matrix = df_daily.pivot(index='date', columns='item_id', values='price')
    # Forward fill missing prices for a short period (up to 3 days)
    # Beyond that, it's stale
    price_matrix = price_matrix.ffill(limit=3)
    
    # We calculate daily returns of the underlying prices
    # rt = Pt / Pt-1 - 1
    daily_returns_matrix = price_matrix.pct_change(fill_method=None)
    # Fill NAs in returns with 0 (no return if no price change or no history)
    daily_returns_matrix = daily_returns_matrix.fillna(0)
    
    # We will build three tables: daily index values, monthly composition, and diagnostics
    index_series = []
    historical_composition = []
    historical_diagnostics = []
    adds_drops_log = []
    
    current_index_level = BASE_INDEX_VALUE
    
    # To track adds/drops, we need to know the previous month's constituents
    prev_constituents = set()
    prev_weights = {}
    prev_ranks = {}
    
    # Loop over the periods between rebalances
    for i in range(len(rebalance_dates)):
        rebal_date = rebalance_dates[i]
        next_rebal_date = rebalance_dates[i+1] if i + 1 < len(rebalance_dates) else all_dates[-1] + pd.Timedelta(days=1)
        
        # 1. Compute Weights
        weights, diag_df = compute_monthly_rebalance(df_daily, rebal_date)
        if weights is None:
            continue
            
        # Attach date to diagnostics and save
        diag_df['rebalance_date'] = rebal_date
        historical_diagnostics.append(diag_df)
            
        current_constituents = set(weights.keys())
        
        # Build current ranks dictionary
        # Retrieve rank from diag_df for the items selected
        current_ranks_df = diag_df[diag_df['item_id'].isin(current_constituents)][['item_id', 'rank']]
        current_ranks = dict(zip(current_ranks_df['item_id'], current_ranks_df['rank']))
        
        adds = current_constituents - prev_constituents if prev_constituents else current_constituents
        drops = prev_constituents - current_constituents if prev_constituents else set()
        
        # Save composition log AND Adds/Drops log
        for item_id, weight in weights.items():
            rank = current_ranks.get(item_id, None)
            prior_rank = prev_ranks.get(item_id, None)
            
            historical_composition.append({
                'rebalance_date': rebal_date,
                'item_id': item_id,
                'weight': weight,
                'rank': rank,
                'status': 'ADD' if item_id in adds else 'HOLD'
            })
            
            if item_id in adds and prev_constituents:
                adds_drops_log.append({
                    'rebalance_date': rebal_date,
                    'item_id': item_id,
                    'action': 'ADD',
                    'prior_weight': 0.0,
                    'new_weight': weight,
                    'prior_rank': prior_rank,
                    'new_rank': rank,
                    'reason': "Entered Top 100"
                })
            
        for item_id in drops:
            prior_rank = prev_ranks.get(item_id, None)
            
            # Fetch why it dropped if it's in diag_df
            drop_reason = "Fell below Top 100"
            if not diag_df[diag_df['item_id'] == item_id].empty:
                item_diag = diag_df[diag_df['item_id'] == item_id].iloc[0]
                if not item_diag['eligible']:
                    drop_reason = item_diag['exclusion_reason']
                    
            historical_composition.append({
                'rebalance_date': rebal_date,
                'item_id': item_id,
                'weight': 0.0,
                'rank': None,
                'status': 'DROP'
            })
            
            if prev_constituents:
                adds_drops_log.append({
                    'rebalance_date': rebal_date,
                    'item_id': item_id,
                    'action': 'DROP',
                    'prior_weight': prev_weights.get(item_id, 0.0),
                    'new_weight': 0.0,
                    'prior_rank': prior_rank,
                    'new_rank': None,
                    'reason': drop_reason
                })
            
        prev_constituents = current_constituents
        prev_weights = weights.copy()
        prev_ranks = current_ranks.copy()
        
        # 2. Iterate days between rebal_date and next_rebal_date
        period_dates = [d for d in all_dates if rebal_date <= d < next_rebal_date]
        
        for d in period_dates:
            # First day of the overall index, initialize
            if not index_series:
                index_series.append({
                    'date': d,
                    'index_level': current_index_level,
                    'daily_return': 0.0
                })
                continue
                
            # For this day, what is the weighted return?
            # It's simply the sum of (weight_i * item_return_i)
            day_returns = daily_returns_matrix.loc[d]
            weighted_return = 0.0
            
            for item_id, w in weights.items():
                if item_id in day_returns:
                    weighted_return += w * day_returns[item_id]
                    
            current_index_level = current_index_level * (1 + weighted_return)
            
            index_series.append({
                'date': d,
                'index_level': current_index_level,
                'daily_return': weighted_return
            })
            
    # Construct final DataFrames
    df_index = pd.DataFrame(index_series)
    df_comp = pd.DataFrame(historical_composition)
    df_ad = pd.DataFrame(adds_drops_log) if adds_drops_log else pd.DataFrame(columns=['rebalance_date', 'item_id', 'action', 'prior_weight', 'new_weight', 'prior_rank', 'new_rank', 'reason'])
    
    if historical_diagnostics:
        df_diag = pd.concat(historical_diagnostics, ignore_index=True)
    else:
        df_diag = pd.DataFrame()
    
    # --- Map Human Readable Item Names ---
    try:
        items_df = pd.read_csv(ITEMS_FILE)
        # Create a dictionary for mapping item IDs to names
        id_to_name = dict(zip(items_df['id'], items_df['name']))
        df_comp['item_name'] = df_comp['item_id'].map(id_to_name).fillna("Unknown Item")
        
        if not df_ad.empty:
            df_ad['item_name'] = df_ad['item_id'].map(id_to_name).fillna("Unknown Item")
            
        if not df_diag.empty:
            df_diag['item_name'] = df_diag['item_id'].map(id_to_name).fillna("Unknown Item")
            
    except Exception as e:
        print(f"Warning: Could not load items.csv to map names ({e})")
        df_comp['item_name'] = "Unknown Item"
        if not df_ad.empty: df_ad['item_name'] = "Unknown Item"
        if not df_diag.empty: df_diag['item_name'] = "Unknown Item"
        
    df_index.to_csv(os.path.join(OUTPUT_DIR, "osrs_100_index_daily.csv"), index=False)
    df_comp.to_csv(os.path.join(OUTPUT_DIR, "osrs_100_constituents.csv"), index=False)
    
    if not df_ad.empty:
        df_ad.to_csv(os.path.join(OUTPUT_DIR, "osrs_100_adds_drops.csv"), index=False)
    
    if not df_diag.empty:
        df_diag.to_csv(os.path.join(OUTPUT_DIR, "osrs_100_diagnostics.csv"), index=False)
    
    # Save a quick JSON snapshot for the dashboard to read efficiently
    latest_level = df_index['index_level'].iloc[-1]
    last_close = df_index['index_level'].iloc[-2] if len(df_index) > 1 else latest_level
    d1_return = (latest_level / last_close) - 1
    
    d7_close_idx = max(0, len(df_index) - 8)
    d7_return = (latest_level / df_index['index_level'].iloc[d7_close_idx]) - 1 if len(df_index) > 7 else 0
    
    d30_close_idx = max(0, len(df_index) - 31)
    d30_return = (latest_level / df_index['index_level'].iloc[d30_close_idx]) - 1 if len(df_index) > 30 else 0
    
    inception_return = (latest_level / BASE_INDEX_VALUE) - 1
    
    latest_rebal_date = df_comp['rebalance_date'].max()
    latest_comp = df_comp[df_comp['rebalance_date'] == latest_rebal_date]
    active_count = len(latest_comp[latest_comp['status'] != 'DROP'])
    
    snapshot = {
        'last_updated': datetime.utcnow().isoformat(),
        'index_level': float(latest_level),
        '1d_return': float(d1_return),
        '7d_return': float(d7_return),
        '30d_return': float(d30_return),
        'inception_return': float(inception_return),
        'active_constituents': int(active_count),
        'latest_rebalance_date': latest_rebal_date.isoformat()
    }
    
    with open(os.path.join(OUTPUT_DIR, "osrs_100_snapshot.json"), "w") as f:
        json.dump(snapshot, f, indent=4)
        
    print("Successfully built the OSRS 100 Index!")

if __name__ == "__main__":
    build_index()
