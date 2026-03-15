import os
import json
import urllib.request
import urllib.parse
from pathlib import Path
import pandas as pd
import time

# Create icons directory if it doesn't exist
ICON_DIR = Path("bbd_data/icons")
ICON_DIR.mkdir(parents=True, exist_ok=True)

# URL format: https://oldschool.runescape.wiki/images/{filename}.png
WIKI_FILE_BASE = "https://oldschool.runescape.wiki/w/Special:FilePath/"

def get_filename_from_item(item_name):
    if not item_name or item_name.lower() in ['nan', 'none', 'unknown', '']:
        return None, None
        
    name = item_name.strip("[]'\"")
    if name == 'none': return None, None
    
    local_filename = name.replace(' ', '_') + ".png"
    
    # Fix wiki URL naming issues
    wiki_overrides = {
        'Devout Boots': 'Devout_boots.png',
        'Runite Bolts': 'Runite_bolts.png',
        'Ranging cape (t)': 'Ranging_cape(t).png',
        "Xeric's Talisman": "Xeric's_talisman.png"
    }
    
    if name in wiki_overrides:
        wiki_filename = wiki_overrides[name]
    else:
        if len(name) > 0:
            wiki_name = name[0].upper() + name[1:]
        else:
            wiki_name = name
        wiki_filename = wiki_name.replace(' ', '_') + ".png"
        
    return local_filename, wiki_filename

def download_icon(item_name):
    local_file, wiki_file = get_filename_from_item(item_name)
    if not local_file:
        return None
        
    local_path = ICON_DIR / local_file
    if local_path.exists():
        return str(local_path)
        
    # URL encode the filename
    url = WIKI_FILE_BASE + urllib.parse.quote(wiki_file)
    
    print(f"Downloading: {local_file} from {url}")
    
    # Try the standard download
    try:
        req = urllib.request.Request(
            url, 
            data=None, 
            headers={
                'User-Agent': 'BBD_Data_Analyzer_Script (local)'
            }
        )
        
        with urllib.request.urlopen(req) as response:
            with open(local_path, 'wb') as f:
                f.write(response.read())
        time.sleep(0.2) # Polite delay
        return str(local_path)
    except urllib.error.HTTPError as e:
        print(f"  -> Failed (HTTP {e.code}) for {item_name}. You may need to download manually.")
        return None
    except Exception as e:
        print(f"  -> Failed (Error: {e}) for {item_name}")
        return None

def main():
    print("Starting Icon Download Sweep...")
    
    try:
        df = pd.read_csv('normalized_sessions.csv')
    except Exception as e:
        print(f"Could not load normalized_sessions.csv: {e}")
        return
        
    config_cols = [c for c in df.columns if c.startswith('config_') and c not in ['config_experiment_name', 'config_mode']]
    
    unique_items = set()
    for col in config_cols:
        # Columns look like: 'config_weapon_Dragon hunter crossbow'
        # Remove 'config_' string
        clean_col = col.replace('config_', '')
        # Split by first underscore to remove the slot name (e.g., 'weapon_')
        parts = clean_col.split('_', 1)
        if len(parts) > 1:
            item_name = parts[1]
            if item_name.lower() not in ['nan', 'none', 'unknown', '']:
                unique_items.add(item_name)
                
    # Extract baseline items safely
    CONFIG_KEYS = [
        "weapon", "head", "body", "legs", "hands", "ammo", "ring", "back", "feet", 
        "prayer", "tele", "bank", "bones", "pray_restore"
    ]
    categories = []
    for k in CONFIG_KEYS:
        if any(c.startswith(f"config_{k}_") for c in config_cols):
            categories.append(f"config_{k}")
            
    for cat in categories:
        cat_cols = [c for c in config_cols if c.startswith(f"{cat}_")]
        if not cat_cols: continue
        
        usage_counts = {c: df[c].sum() for c in cat_cols}
        if usage_counts:
            try:
                baseline_col = max(usage_counts, key=usage_counts.get)
                baseline_item = baseline_col.replace(f"{cat}_", "")
                if baseline_item.lower() not in ['nan', 'none', 'unknown', '']:
                    unique_items.add(baseline_item)
            except Exception:
                pass
                
    # Add a fallback 'Null' placeholder if needed
    
    print(f"Found {len(unique_items)} unique gear pieces.")
    
    downloaded = 0
    failed = []
    
    for item in sorted(list(unique_items)):
        path = download_icon(item)
        if path:
            downloaded += 1
        else:
            failed.append(item)
            
    print(f"\nSweep complete. {downloaded}/{len(unique_items)} icons available locally.")
    if failed:
        print("Failed to auto-download icons for:")
        for item in failed:
            print(f" - {item}")

if __name__ == "__main__":
    main()
