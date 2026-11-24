"""World map page: observed stress 2001–2023, forecast 2024–2035, or agricultural share."""

import plotly.express as px
import streamlit as st

import data
from water_maps import TIER_COLORS, TIER_ORDER, continuous_map, stress_tier_animation, stress_tier_map

st.set_page_config(page_title="World Map · Water Stress", page_icon="🌍", layout="wide")
master, forecast = data.load_master(), data.load_forecast()

st.title("🌍 World map")

with st.sidebar:
    st.header("Map settings")
    view = st.radio("What to show", ["Observed water stress (2001–2023)", "Forecast water stress (2024–2035)",
                                     "Agriculture's share of water use"])
    if view.startswith("Observed"):
        latest = st.checkbox("Latest available year per country", value=True)
        year = None if latest else st.slider("Year", data.FIRST_YEAR, data.LAST_YEAR, data.LAST_YEAR)
        animate = st.checkbox("Play animation 2001–2023", value=False)
    elif view.startswith("Forecast"):
        year = st.slider("Forecast year", data.FORECAST_FIRST, data.FORECAST_LAST, data.FORECAST_LAST)

if view.startswith("Observed"):
    if animate:
        fig = stress_tier_animation(master)
        shown = data.latest_per_country(master)
        st.caption("Press ▶ under the map to play the years.")
    else:
        fig = stress_tier_map(master, year=year)
        shown = data.latest_per_country(master) if year is None else master[master["Year"] == year].dropna(subset=["Water_Stress_Total_Pct"])
    data.chart(fig)
    st.caption("Many values repeat the previous year because the UN carries its last estimate forward between surveys. "
               "Open the Country View to see which years are real observations.")

elif view.startswith("Forecast"):
    shown = data.forecast_as_master(forecast, year)
    fig = stress_tier_map(shown, year=year, title=f"Forecast water stress, {year} (damped recent trend)")
    data.chart(fig)
    st.caption(f"Forecast for the {shown['ISO3_Code'].nunique()} countries with at least 5 real observations. "
               "Grey countries have too little real data to forecast.")

else:
    d = master.dropna(subset=["Agri_Share_Pct"]).sort_values("Year").groupby("ISO3_Code").tail(1)
    fig = continuous_map(d, "Agri_Share_Pct", "Share of water withdrawn for agriculture (latest year)",
                         "% agriculture", scale="YlGn", range_color=[0, 100], hover={"Year": True})
    data.chart(fig)
    st.caption(f"Agriculture is the largest water user in most countries; {int((d['Agri_Share_Pct'] >= 50).sum())} of "
               f"{len(d)} countries use at least half of their withdrawals for farming.")
    shown = None

if shown is not None:
    st.subheader("Countries per stress tier")
    counts = data.tier_counts(shown, TIER_ORDER)
    bar = px.bar(counts, x="Countries", y="Stress tier", orientation="h", color="Stress tier",
                 color_discrete_map=TIER_COLORS, text="Countries")
    bar.update_layout(showlegend=False, height=280, margin=dict(l=0, r=0, t=10, b=0), yaxis_title=None,
                      yaxis=dict(categoryorder="array", categoryarray=list(reversed(counts["Stress tier"]))))
    data.chart(bar)
