"""
Water Stress Forecasting Utilities (UN SDG 6.4.2)
=================================================
Reusable functions for forecasting each country's water stress level
(freshwater withdrawal as % of available freshwater resources).

The notebook `notebooks/03_forecast_water_stress.ipynb` uses these functions to:
    1. select countries whose stress series has real year-to-year variation,
    2. back-test four forecasting models on held-out years,
    3. forecast 2024-2035 with uncertainty ranges,
    4. find the year each country is expected to cross the High (75%)
       and Critical (100%) stress thresholds.

Why carried-forward values are removed:
    The UN repeats the last estimate in years with no new survey. Treating those
    repeats as real observations would make trends look flatter than they are,
    so models are fitted on genuine observations only.
"""

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.holtwinters import ExponentialSmoothing

# Official UN SDG 6.4.2 stress tiers (lower bound of each tier, in %)
STRESS_TIERS = [
    (0, '1. No Stress (<25%)'),
    (25, '2. Low Stress (25-50%)'),
    (50, '3. Medium Stress (50-75%)'),
    (75, '4. High Stress (75-100%)'),
    (100, '5. Critical Stress (>100%)'),
]
HIGH_THRESHOLD = 75.0
CRITICAL_THRESHOLD = 100.0
MODELS = ['Naive (last value)', 'Linear trend', 'Damped Holt', 'Damped recent trend']

# Damped recent trend settings (chosen by back-testing in the notebook)
RECENT_WINDOW = 8     # number of latest genuine observations used for the slope
DEFAULT_PHI = 0.5     # damping factor: each year adds phi^h of the slope (tuned on the 2016 back-test)
TREND_PHI = 1.0       # "recent trend continues" stress-test scenario (no damping)


def stress_category(value):
    """Return the UN SDG 6.4.2 tier label for a stress percentage (NaN -> 'Unknown')."""
    if pd.isna(value):
        return 'Unknown'
    label = STRESS_TIERS[0][1]
    for lower_bound, tier in STRESS_TIERS:
        if value >= lower_bound:
            label = tier
    return label


def prepare_observations(master, min_obs=5):
    """Keep only genuine stress observations for countries worth forecasting.

    Args:
        master: the processed master dataset (one row per country-year).
        min_obs: minimum number of genuine observations a country needs.

    Returns:
        DataFrame with columns m49, ISO3_Code, Country, Year, Stress — one row per
        genuine (not carried-forward) observation of a forecastable country.
    """
    obs = master[
        master['Stress_Forecastable']
        & master['Water_Stress_Total_Pct'].notna()
        & ~master['Stress_Carried_Forward']
    ][['m49', 'ISO3_Code', 'Country', 'Year', 'Water_Stress_Total_Pct']]
    obs = obs.rename(columns={'Water_Stress_Total_Pct': 'Stress'})
    counts = obs.groupby('m49')['Year'].transform('size')
    return obs[counts >= min_obs].sort_values(['m49', 'Year']).reset_index(drop=True)


def forecast_naive(years, values, target_years):
    """Persistence baseline: every future year equals the last observed value."""
    return np.full(len(target_years), float(values[-1]))


def forecast_linear(years, values, target_years, interval=0.80):
    """Ordinary least-squares linear trend on year.

    Returns:
        (mean, lower, upper) arrays for `target_years`; the bounds are the
        prediction interval at the given coverage. Values are floored at 0%.
    """
    X = sm.add_constant(np.asarray(years, dtype=float))
    fit = sm.OLS(np.asarray(values, dtype=float), X).fit()
    X_new = sm.add_constant(np.asarray(target_years, dtype=float), has_constant='add')
    pred = fit.get_prediction(X_new).summary_frame(alpha=1 - interval)
    mean = pred['mean'].to_numpy()
    lower = pred['obs_ci_lower'].to_numpy()
    upper = pred['obs_ci_upper'].to_numpy()
    return np.clip(mean, 0, None), np.clip(lower, 0, None), np.clip(upper, 0, None)


def forecast_damped_holt(years, values, target_years):
    """Holt's linear trend with damping, fitted on a gap-filled annual series.

    Gaps left by removed carried-forward years are filled by linear interpolation
    so the model sees a regular yearly series. Damping makes the trend flatten
    over time, which avoids extreme long-range extrapolation.
    """
    years = np.asarray(years, dtype=int)
    series = pd.Series(np.asarray(values, dtype=float), index=years)
    full = series.reindex(range(years.min(), years.max() + 1)).interpolate()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        fit = ExponentialSmoothing(full.to_numpy(), trend='add', damped_trend=True,
                                   initialization_method='estimated').fit()
        steps = int(max(target_years) - years.max())
        path = fit.forecast(steps)
    lookup = dict(zip(range(years.max() + 1, years.max() + 1 + steps), path))
    return np.clip(np.array([lookup[y] for y in target_years]), 0, None)


def forecast_damped_recent(years, values, target_years, phi=DEFAULT_PHI, window=RECENT_WINDOW):
    """Damped recent trend: start at the last value and follow a fading recent slope.

    The slope is the least-squares slope of the last `window` genuine observations.
    The forecast h years after the last observation is

        last_value + slope * (phi + phi^2 + ... + phi^h)

    so with phi < 1 the trend flattens out; the total future change can never exceed
    slope * phi / (1 - phi) (4 years' worth of slope when phi = 0.8). phi = 1 is an
    undamped straight line; phi = 0 is the naive last-value forecast.
    """
    years = np.asarray(years, dtype=float)[-window:]
    values = np.asarray(values, dtype=float)[-window:]
    slope = np.polyfit(years, values, 1)[0] if len(years) >= 2 else 0.0
    horizons = np.asarray(target_years, dtype=float) - years[-1]
    damp_sum = np.array([phi * (1 - phi ** h) / (1 - phi) if phi < 1 else h for h in horizons])
    return np.clip(values[-1] + slope * damp_sum, 0, None)


def run_model(name, years, values, target_years, phi=DEFAULT_PHI):
    """Dispatch to one of the models in MODELS by name and return point forecasts."""
    if name == 'Naive (last value)':
        return forecast_naive(years, values, target_years)
    if name == 'Linear trend':
        return forecast_linear(years, values, target_years)[0]
    if name == 'Damped Holt':
        return forecast_damped_holt(years, values, target_years)
    if name == 'Damped recent trend':
        return forecast_damped_recent(years, values, target_years, phi=phi)
    raise ValueError(f'Unknown model: {name}')


def backtest(obs, train_end=2018, min_train_obs=4, models=MODELS, phi=DEFAULT_PHI):
    """Hold out the years after `train_end`, forecast them, and record the errors.

    Each model is trained on a country's observations up to `train_end` and asked
    to predict that country's real observations after `train_end`.

    Returns:
        DataFrame with one row per (country, test year, model): actual, predicted,
        error (percentage points), log error (log(1+pred) - log(1+actual)) and the
        horizon in years since the last training observation.
    """
    rows = []
    for m49, grp in obs.groupby('m49'):
        train = grp[grp['Year'] <= train_end]
        test = grp[grp['Year'] > train_end]
        if len(train) < min_train_obs or test.empty:
            continue
        last_train_year = train['Year'].iloc[-1]
        for model in models:
            pred = run_model(model, train['Year'].to_numpy(), train['Stress'].to_numpy(),
                             test['Year'].to_numpy(), phi=phi)
            for year, actual, p in zip(test['Year'], test['Stress'], pred):
                rows.append({'m49': m49, 'Country': grp['Country'].iloc[0], 'Year': year,
                             'Horizon': year - last_train_year, 'Model': model,
                             'Actual': actual, 'Predicted': p, 'Error': p - actual,
                             'LogError': np.log1p(p) - np.log1p(actual)})
    return pd.DataFrame(rows)


def interval_scale(bt, model='Damped recent trend'):
    """Estimate forecast uncertainty from back-test errors.

    Assumes the spread of log errors grows with the square root of the horizon:
    sd(h) = s * sqrt(h). Returns s, fitted by least squares on the per-horizon
    standard deviations of the given model's log errors.
    """
    d = bt[bt['Model'] == model]
    sd = d.groupby('Horizon')['LogError'].std().dropna()
    h = np.sqrt(sd.index.to_numpy(dtype=float))
    return float((h @ sd.to_numpy()) / (h @ h))


def summarise_backtest(bt):
    """Aggregate back-test errors per model.

    Metrics (all in percentage points of water stress):
        MAE        mean absolute error
        Median_AE  median absolute error (robust to a few extreme countries)
        Bias       mean signed error (positive = model over-predicts)
        Win_Rate   share of countries where this model has the lowest error
    """
    bt = bt.assign(AbsError=bt['Error'].abs())
    summary = bt.groupby('Model').agg(MAE=('AbsError', 'mean'),
                                      Median_AE=('AbsError', 'median'),
                                      Bias=('Error', 'mean'))
    per_country = bt.groupby(['m49', 'Model'])['AbsError'].mean().unstack()
    wins = per_country.idxmin(axis=1).value_counts(normalize=True)
    summary['Win_Rate_Pct'] = (wins.reindex(summary.index).fillna(0) * 100)
    summary['Countries'] = bt['m49'].nunique()
    return summary.round(2).sort_values('MAE')


def forecast_all(obs, master, log_sd_scale, first_year=2024, last_year=2035, phi=DEFAULT_PHI):
    """Forecast every forecastable country with the damped recent trend model.

    The 80% range is forecast * exp(+/- 1.2816 * s * sqrt(h)) in log(1 + stress)
    space, where s comes from `interval_scale` (i.e. from real back-test errors)
    and h is years since the country's last genuine observation.

    Returns:
        DataFrame with one row per country-year (first_year..last_year):
        Forecast, Lower/Upper 80% range and forecast category.
    """
    z80 = 1.2816
    target = np.arange(first_year, last_year + 1)
    names = master.drop_duplicates('m49').set_index('m49')[['ISO3_Code', 'Country']]
    rows = []
    for m49, grp in obs.groupby('m49'):
        years, values = grp['Year'].to_numpy(), grp['Stress'].to_numpy()
        mean = forecast_damped_recent(years, values, target, phi=phi)
        spread = z80 * log_sd_scale * np.sqrt(target - years[-1])
        lower = np.expm1(np.log1p(mean) - spread)
        upper = np.expm1(np.log1p(mean) + spread)
        rows.append(pd.DataFrame({
            'm49': m49, 'ISO3_Code': names.at[m49, 'ISO3_Code'], 'Country': names.at[m49, 'Country'],
            'Year': target, 'Last_Observed_Year': int(years[-1]),
            'Forecast_Stress_Pct': mean.round(2),
            'Lower_80_Pct': np.clip(lower, 0, None).round(2), 'Upper_80_Pct': upper.round(2),
        }))
    out = pd.concat(rows, ignore_index=True)
    out['Forecast_Category'] = out['Forecast_Stress_Pct'].apply(stress_category)
    return out


def threshold_crossings(forecast, latest, thresholds=(HIGH_THRESHOLD, CRITICAL_THRESHOLD)):
    """Find the first forecast year each country crosses each threshold.

    Only countries currently *below* a threshold can cross it.

    Args:
        forecast: output of `forecast_all`.
        latest: DataFrame with m49 and Latest_Stress_Pct (most recent known value).

    Returns:
        DataFrame with one row per (country, threshold) crossing.
    """
    merged = forecast.drop(columns='Latest_Stress_Pct', errors='ignore').merge(
        latest[['m49', 'Latest_Stress_Pct']], on='m49')
    columns = ['m49', 'ISO3_Code', 'Country', 'Threshold_Pct', 'Latest_Stress_Pct', 'Crossing_Year']
    rows = []
    for thr in thresholds:
        below_now = merged[merged['Latest_Stress_Pct'] < thr]
        hits = below_now[below_now['Forecast_Stress_Pct'] >= thr]
        first = hits.sort_values('Year').drop_duplicates('m49')
        for _, r in first.iterrows():
            rows.append({'m49': r['m49'], 'ISO3_Code': r['ISO3_Code'], 'Country': r['Country'],
                         'Threshold_Pct': thr, 'Latest_Stress_Pct': r['Latest_Stress_Pct'],
                         'Crossing_Year': int(r['Year'])})
    out = pd.DataFrame(rows, columns=columns)
    return out.sort_values(['Threshold_Pct', 'Crossing_Year'], ascending=[False, True]).reset_index(drop=True)


def chance_above(forecast_value, threshold, log_sd_scale, horizon):
    """Probability (0-100) that true stress exceeds `threshold`, given a forecast.

    Uses the same log-normal error model as the forecast ranges:
    log(1 + stress) ~ Normal(log(1 + forecast), (s * sqrt(horizon))^2).
    """
    from scipy.stats import norm
    sd = log_sd_scale * np.sqrt(horizon)
    z = (np.log1p(threshold) - np.log1p(forecast_value)) / sd
    return float(100 * (1 - norm.cdf(z)))
