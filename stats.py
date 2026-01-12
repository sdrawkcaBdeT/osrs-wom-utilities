from scipy.stats import binom

def calculate_luck(drop_rate, total_kills, actual_drops):
    # Calculate cumulative probability
    percentile = binom.cdf(actual_drops, total_kills, drop_rate)
    return percentile * 100