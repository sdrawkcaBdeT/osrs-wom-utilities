import pandas as pd
df = pd.read_csv('normalized_sessions.csv')
config_cols = [c for c in df.columns if c.startswith('config_') and c not in ['config_experiment_name', 'config_mode']]

def extract_loadout_data(row):
    equipment = {}
    other_params = []
    for col in sorted(config_cols):
        val = str(row[col])
        if val.lower() in ['nan', 'none', 'unknown', '', 'false']:
            continue
            
        clean_col = col.replace('config_', '')
        parts = clean_col.split('_', 1)
        
        if val.lower() == 'true' or val in ['1.0', '1']:
            item_name = parts[1] if len(parts) > 1 else clean_col
            slot_indicator = parts[0].lower() if len(parts) > 1 else ""
        else:
            item_name = val.strip('[]').replace("'", "")
            slot_indicator = parts[0].lower() if len(parts) > 1 else clean_col
            
        if slot_indicator in ['head', 'cape', 'neck', 'ammo', 'weapon', 'body', 'shield', 'legs', 'hands', 'feet', 'ring', 'back']:
            actual_slot = 'back' if slot_indicator == 'cape' else slot_indicator
            equipment[actual_slot] = item_name
        else:
            opt_name = clean_col.replace('_', ' ').capitalize()
            other_params.append(f'{opt_name}: True')
            
    return equipment, other_params

print('Testing index 0:')
eq, param = extract_loadout_data(df.iloc[0])
print('Equipment:', eq)
print('Params:', param)
