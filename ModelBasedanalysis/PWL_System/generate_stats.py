import pandas as pd

def generate_statistics(file_path):
    df = pd.read_csv(file_path)
    
    total_days = len(df)
    breaches = df[df['target_1_breach'] == 1]
    total_breaches = len(breaches)
    
    # Target 2 & 3 stats (only among breaches where outcome is known)
    t2_valid = breaches.dropna(subset=['target_2_fall'])
    t2_success_rate = t2_valid['target_2_fall'].mean()
    
    t3_valid = breaches.dropna(subset=['target_3_ev'])
    t3_win_rate = t3_valid['target_3_ev'].mean()
    
    # Gap Analysis: Probability of breach based on Gap to PWL
    # Binning gaps into 0.5% increments
    df['gap_bin'] = (df['gap_to_pwl_pct'] * 200).round() / 200
    gap_stats = df.groupby('gap_bin')['target_1_breach'].agg(['count', 'mean']).rename(columns={'mean': 'breach_prob'})
    # Filter for bins with at least 20 occurrences for statistical significance
    significant_gaps = gap_stats[gap_stats['count'] >= 20].tail(10)

    stats_md = f"""# QQQ Historical PWL Analysis (2018 - 2026)

## 1. Overall Base Rates
- **Total Trading Days:** {total_days}
- **Total PWL Breaches:** {total_breaches}
- **Breach Probability:** {total_breaches/total_days:.2%}

## 2. Post-Breach Probabilities (The Edge)
*Once the Previous Week Low is touched:*
- **Prob of 2% further fall (within 5 days):** {t2_success_rate:.2%}
- **Prob of 2% fall BEFORE 2% gain (EV Win Rate):** {t3_win_rate:.2%}

## 3. Gap Analysis (Open Price vs. Probability)
| Open Gap to PWL (%) | Sample Size | Breach Probability |
| :--- | :--- | :--- |
"""
    for gap, row in significant_gaps.iterrows():
        stats_md += f"| {gap:.2%} | {int(row['count'])} | {row['breach_prob']:.2%} |\n"

    with open('historical_statistics.md', 'w') as f:
        f.write(stats_md)
    
    print(stats_md)

if __name__ == "__main__":
    generate_statistics('mvp_features_targets.csv')
