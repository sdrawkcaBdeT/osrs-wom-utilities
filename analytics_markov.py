import sqlite3
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import os

def generate_markov_matrix():
    if not os.path.exists('analytics_output'):
        os.makedirs('analytics_output')

    conn = sqlite3.connect('combat_telemetry.db')
    df = pd.read_sql_query("SELECT * FROM combat_ticks ORDER BY session_id, tick_number", conn)
    conn.close()

    if df.empty:
        print("No combat ticks found in database.")
        return

    # Create next state column grouped by session
    df['next_state'] = df.groupby('session_id')['state'].shift(-1)
    df = df.dropna(subset=['next_state'])

    # Filter out out-of-bounds states if they exist
    valid_states = ['attack', 'cooldown', 'idle']
    df = df[df['state'].isin(valid_states) & df['next_state'].isin(valid_states)]

    # Calculate transition probabilities
    transitions = pd.crosstab(df['state'], df['next_state'], normalize='index')
    
    # Reorder columns to standard format
    transitions = transitions.reindex(index=valid_states, columns=valid_states, fill_value=0)

    plt.figure(figsize=(8, 6))
    sns.heatmap(transitions, annot=True, cmap='Blues', fmt='.2%', cbar=False)
    plt.title('Combat State Transition Matrix (Markov Chain)')
    plt.xlabel('Next State')
    plt.ylabel('Current State')
    plt.tight_layout()
    plt.savefig('analytics_output/markov_matrix.png', dpi=300)
    plt.close()
    
    print("Generated analytics_output/markov_matrix.png")

if __name__ == "__main__":
    generate_markov_matrix()
