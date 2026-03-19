import subprocess

scripts = [
    "plot_3d_profit_topography.py",
    "plot_accuracy_consistency.py",
    "plot_afk_matrix.py",
    "plot_banking.py",
    "plot_combat_luck.py",
    "plot_efficient_frontier.py",
    "plot_empirical_hit_distribution.py",
    "plot_fatigue.py",
    "plot_heartbeat.py",
    "plot_heatmap.py",
    "plot_hours_heatmap.py",
    "plot_income_waterfall.py",
    "plot_monte_carlo.py",
    "plot_moving_target.py",
    "plot_noodle_index.py",
    "plot_overkill_cliff.py",
    "plot_overkill_tax.py",
    "plot_prayer_yield.py",
    "plot_rng_waterfall.py",
    "plot_sloth_surface.py",
    # "plot_sloth_tax.py",
    "plot_tick_latency.py",
    "plot_ttk_kde.py",
    "plot_wealth_composition.py",
]

for script in scripts:
    print(f"\n=== Running {script} ===")
    result = subprocess.run(["python", script])

    if result.returncode != 0:
        print(f"❌ Error running {script}")
        break  # stop on failure (remove this line if you want to continue anyway)

print("\n✅ Done.")