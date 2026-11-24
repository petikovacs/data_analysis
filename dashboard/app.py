"""
Team 3 · Water Security & Industrial Stress — Streamlit dashboard (overview page)
Run from the repository root:   streamlit run dashboard/app.py
The three analysis pages live in dashboard/pages/ and appear in the sidebar automatically.
"""

import streamlit as st

import data
from water_maps import stress_tier_map

st.set_page_config(page_title="Global Water Stress Dashboard", page_icon="💧", layout="wide")

master, forecast, risk = data.load_master(), data.load_forecast(), data.load_risk()
n = data.headline_numbers(master, forecast, risk)

st.title("💧 Global Water Stress Dashboard (2001–2035)")
st.markdown(
    "How much of its renewable freshwater does each country withdraw for agriculture, industry and households, "
    "and which countries are heading toward **Critical water stress** (UN SDG indicator 6.4.2)? "
    "Use the pages in the sidebar to explore the **world map**, a **single country**, and the **countries at risk by 2035**."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Countries covered", n["countries"])
c2.metric("Already in Critical stress (>100%)", n["critical_now"])
c3.metric("Median country's water stress", f"{n['median_stress']:.0f}%")
c4.metric("May reach Critical by 2035", n["at_risk_critical"], help="Countries below 100% today with a real chance of crossing it (see 'Countries at Risk').")

data.chart(stress_tier_map(master))

left, right = st.columns([3, 2])
with left:
    st.subheader("Key findings")
    st.markdown(
        f"""
- **{n['critical_now']} countries already withdraw more water than is renewably available.** They form one belt across North Africa, the Arabian Peninsula and Central Asia (Kuwait, UAE, Saudi Arabia, Libya…).
- **Agriculture is the largest water user in {n['agri_lead']} of {n['agri_total']} countries** and drives most of the stress in the worst-affected ones; the exceptions are Gulf states, where municipal use dominates.
- **Tunisia and Pakistan** are just below 100% and have close to a 50% chance of reaching Critical stress by 2035.
- The forecast covers **{n['forecast_countries']} countries** with enough real observations; it was back-tested on years the model never saw.
"""
    )
with right:
    st.subheader("How to read water stress")
    st.markdown(
        """
**Water stress** = freshwater withdrawn ÷ (renewable freshwater − water nature needs) × 100

| Tier | Meaning |
|---|---|
| 🟦 < 25% | No stress |
| 🩵 25–50% | Low |
| 🟨 50–75% | Medium |
| 🟧 75–100% | High |
| 🟥 > 100% | **Critical** — more is withdrawn than renews |
"""
    )

st.info(
    f"**Data caveat:** only about {n['reported_share']:.0f}% of stress values are reported directly by countries; "
    "the rest are estimates, imputations or repeats of the previous year. The country page shows which values are real observations.",
    icon="ℹ️",
)
st.caption("Sources: UNSD Environmental Indicators, FAO AQUASTAT, Our World in Data, UN SDG Global Database (6.4.2). "
           "Pipeline, notebooks and source notes: github.com/petikovacs/data_analysis")
