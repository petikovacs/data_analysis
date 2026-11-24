"""
Data loading and preparation for the Streamlit dashboard
========================================================
All pandas logic lives here so the page files only deal with layout.
Every loader reads the files produced by the pipeline and the forecast notebook;
nothing is recalculated, so the dashboard always shows the same numbers as the report.
"""

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]           # repository root
sys.path.insert(0, str(ROOT / "src"))                # makes `import water_maps` work

MASTER_CSV = ROOT / "data" / "processed" / "Master_Global_Water_Dataset_2001_2023.csv"
FORECAST_CSV = ROOT / "data" / "processed" / "Water_Stress_Forecast_2024_2035.csv"
RISK_CSV = ROOT / "reports" / "06_Countries_At_Risk_2035.csv"

FIRST_YEAR, LAST_YEAR = 2001, 2023
FORECAST_FIRST, FORECAST_LAST = 2024, 2035
CRITICAL = "5. Critical Stress (>100%)"

STATUS_LABELS = {"A": "Reported by country", "E": "Estimated", "I": "Imputed"}

try:  # cache in Streamlit, plain functions everywhere else (tests, notebooks)
    import streamlit as st
    cache = st.cache_data
except ImportError:  # pragma: no cover
    def cache(func=None, **_):
        return func if func else (lambda f: f)


# --------------------------------------------------------------------------- loaders
@cache
def load_master() -> pd.DataFrame:
    """Cleaned 2001–2023 panel (one row per country and year)."""
    return pd.read_csv(MASTER_CSV)


@cache
def load_forecast() -> pd.DataFrame:
    """Yearly 2024–2035 forecast for the 151 forecastable countries."""
    return pd.read_csv(FORECAST_CSV)


@cache
def load_risk() -> pd.DataFrame:
    """Countries that may cross the 75% (High) or 100% (Critical) threshold by 2035."""
    return pd.read_csv(RISK_CSV)


# --------------------------------------------------------------------------- helpers
def latest_per_country(master: pd.DataFrame) -> pd.DataFrame:
    """Each country's most recent year that has a stress value."""
    d = master.dropna(subset=["Water_Stress_Total_Pct"])
    return d.sort_values("Year").groupby("ISO3_Code").tail(1)


def forecast_as_master(forecast: pd.DataFrame, year: int) -> pd.DataFrame:
    """Rename forecast columns so the forecast can be drawn with `water_maps.stress_tier_map`."""
    d = forecast[forecast["Year"] == year].copy()
    return d.rename(columns={"Forecast_Stress_Pct": "Water_Stress_Total_Pct",
                             "Forecast_Category": "Water_Stress_Category"})


def tier_counts(d: pd.DataFrame, order: list) -> pd.DataFrame:
    """Number of countries in each UN stress tier (only tiers present in `order`)."""
    counts = d["Water_Stress_Category"].value_counts()
    rows = [(t, int(counts.get(t, 0))) for t in order if t != "Unknown"]
    return pd.DataFrame(rows, columns=["Stress tier", "Countries"])


def headline_numbers(master: pd.DataFrame, forecast: pd.DataFrame, risk: pd.DataFrame) -> dict:
    """The few numbers shown at the top of the overview page."""
    latest = latest_per_country(master)
    stressed = master.dropna(subset=["Water_Stress_Total_Pct"])
    agri_main = master.dropna(subset=["Agri_Share_Pct", "Ind_Share_Pct", "Mun_Share_Pct"])
    agri_main = agri_main.sort_values("Year").groupby("ISO3_Code").tail(1)
    agri_lead = (agri_main["Agri_Share_Pct"] >= agri_main[["Ind_Share_Pct", "Mun_Share_Pct"]].max(axis=1))
    return {
        "countries": int(master["ISO3_Code"].nunique()),
        "critical_now": int((latest["Water_Stress_Category"] == CRITICAL).sum()),
        "median_stress": float(latest["Water_Stress_Total_Pct"].median()),
        "reported_share": float((stressed["Stress_Obs_Status"] == "A").mean() * 100),
        "forecast_countries": int(forecast["ISO3_Code"].nunique()),
        "at_risk_critical": int((risk["Threshold"].str.startswith("Critical")).sum()),
        "agri_lead": int(agri_lead.sum()),
        "agri_total": int(len(agri_main)),
    }


def country_list(master: pd.DataFrame) -> list:
    """Countries that have at least one stress value, alphabetically."""
    return sorted(master.dropna(subset=["Water_Stress_Total_Pct"])["Country"].unique())


def country_history(master: pd.DataFrame, country: str) -> pd.DataFrame:
    """2001–2023 rows of one country, with a readable label for how each value was obtained."""
    d = master[master["Country"] == country].sort_values("Year").copy()
    d["Value_Type"] = "Carried forward (repeat of previous year)"
    genuine = ~d["Stress_Carried_Forward"].astype(bool)
    d.loc[genuine, "Value_Type"] = d.loc[genuine, "Stress_Obs_Status"].map(STATUS_LABELS).fillna("Unknown")
    return d


def country_forecast(forecast: pd.DataFrame, country: str) -> pd.DataFrame:
    return forecast[forecast["Country"] == country].sort_values("Year")


def country_summary(history: pd.DataFrame, fc: pd.DataFrame) -> dict:
    """Key facts for the country page cards."""
    h = history.dropna(subset=["Water_Stress_Total_Pct"])
    genuine = h[~h["Stress_Carried_Forward"].astype(bool)]
    sectors = history.dropna(subset=["Agri_Share_Pct"]).tail(1)
    out = {
        "latest_stress": float(h["Water_Stress_Total_Pct"].iloc[-1]) if len(h) else None,
        "latest_year": int(h["Year"].iloc[-1]) if len(h) else None,
        "category": h["Water_Stress_Category"].iloc[-1] if len(h) else "Unknown",
        "last_real_year": int(genuine["Year"].max()) if len(genuine) else None,
        "agri_share": float(sectors["Agri_Share_Pct"].iloc[0]) if len(sectors) else None,
        "forecastable": bool(len(fc)),
        "caveat": bool(history["Any_Definition_Caveat"].any()),
        "mismatch": bool(history["Flag_UNSD_FAO_Mismatch"].any()),
    }
    if len(fc):
        last = fc[fc["Year"] == FORECAST_LAST].iloc[0]
        out.update(fc_2035=float(last["Forecast_Stress_Pct"]), fc_low=float(last["Lower_80_Pct"]),
                   fc_high=float(last["Upper_80_Pct"]), fc_category=last["Forecast_Category"])
    return out


def risk_table(risk: pd.DataFrame, threshold: str) -> pd.DataFrame:
    """Countries at risk for one threshold, highest chance first, with readable column names."""
    d = risk[risk["Threshold"] == threshold].sort_values("Chance_Above_2035_Pct", ascending=False)
    d = d.assign(**{c: d[c].astype("Int64") for c in ["Base_Crossing_Year", "Crossing_If_Trend_Continues"]})
    return d.rename(columns={
        "Last_Real_Data_Year": "Last real data",
        "Latest_Stress_Pct": "Latest stress (%)",
        "Base_2035_Pct": "Forecast 2035 (%)",
        "Trend_Continues_2035_Pct": "If trend continues 2035 (%)",
        "Chance_Above_2035_Pct": "Chance above threshold by 2035 (%)",
        "Base_Crossing_Year": "Crossing year (forecast)",
        "Crossing_If_Trend_Continues": "Crossing year (trend continues)",
    }).drop(columns=["Threshold"])


# --------------------------------------------------------------------------- display helpers
def chart(fig):
    """Full-width Plotly chart on both new (width='stretch') and older Streamlit versions."""
    try:
        st.plotly_chart(fig, width="stretch")
    except Exception:
        st.plotly_chart(fig, use_container_width=True)


def table(df, **kwargs):
    """Full-width dataframe on both new and older Streamlit versions."""
    try:
        st.dataframe(df, width="stretch", **kwargs)
    except Exception:
        st.dataframe(df, use_container_width=True, **kwargs)
