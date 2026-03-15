import pandas as pd
import json

df = pd.read_csv('normalized_sessions.csv')
config_cols = [c for c in df.columns if c.startswith('config_') and c not in ['config_experiment_name', 'config_mode']]

def get_loadout(row):
    loadout = []
    for col in sorted(config_cols):
        val = str(row[col])
        if val and val.lower() not in ['nan', 'none', 'unknown', '']:
            item = val.strip('[]').replace("'", "")
            col_name = col.replace('config_', '').capitalize()
            loadout.append(f'{col_name}: {item}')
    return ' | '.join(loadout)

df['Loadout'] = df.apply(get_loadout, axis=1)

summary = df.groupby('Loadout').agg(
    Sessions=('session_id', 'count'),
    Total_Hrs=('duration_hrs', 'sum')
).sort_values('Sessions', ascending=False)

with open('gear_audit.md', 'w', encoding='utf-8') as f:
    f.write('## Gear Setup Audit\n\n')
    f.write(summary.to_markdown())
