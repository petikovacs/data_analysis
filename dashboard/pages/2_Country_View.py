"""Country view: stress history, forecast with uncertainty, sector mix and data-quality notes."""

import plotly.graph_objects as go
import streamlit as st

import data

st.set_page_config(page_title="Country View · Water Stress", page_icon="🔎", layout="wide")
master, forecast = data.load_master(), data.load_forecast()

countries = data.country_list(master)
with st.sidebar:
    st.header("Choose a country")
    country = st.selectbox("Country", countries, index=countries.index("Tunisia") if "Tunisia" in countries else 0)

hist = data.country_history(master, country)
fc = data.country_forecast(forecast, country)
s = data.country_summary(hist, fc)

st.title(f"🔎 {country}")

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"Water stress ({s['latest_year']})", f"{s['latest_stress']:.1f}%" if s["latest_stress"] is not None else "n/a")
c2.metric("UN stress tier", s["category"].split(" (")[0].split(". ")[-1] if s["category"] else "n/a")
c3.metric("Last real observation", s["last_real_year"] or "n/a",
          help="Latest year whose value is not just a repeat of the previous year.")
c4.metric("Agriculture's share of withdrawals", f"{s['agri_share']:.0f}%" if s["agri_share"] is not None else "n/a")

# ----------------------------------------------------------------- stress over time + forecast
fig = go.Figure()
h = hist.dropna(subset=["Water_Stress_Total_Pct"])
fig.add_trace(go.Scatter(x=h["Year"], y=h["Water_Stress_Total_Pct"], mode="lines", name="Water stress (UN)",
                         line=dict(color="#2b5f8a", width=2)))
markers = {"Reported by country": "#1a9850", "Estimated": "#fdae61", "Imputed": "#9e9ac8",
           "Carried forward (repeat of previous year)": "#cccccc"}
for label, color in markers.items():
    p = h[h["Value_Type"] == label]
    if len(p):
        fig.add_trace(go.Scatter(x=p["Year"], y=p["Water_Stress_Total_Pct"], mode="markers", name=label,
                                 marker=dict(color=color, size=8)))
if len(fc):
    fig.add_trace(go.Scatter(x=list(fc["Year"]) + list(fc["Year"])[::-1],
                             y=list(fc["Upper_80_Pct"]) + list(fc["Lower_80_Pct"])[::-1],
                             fill="toself", fillcolor="rgba(215,25,28,0.12)", line=dict(width=0),
                             name="80% uncertainty range", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=fc["Year"], y=fc["Forecast_Stress_Pct"], mode="lines", name="Forecast (damped trend)",
                             line=dict(color="#d7191c", width=2.5)))
    fig.add_trace(go.Scatter(x=fc["Year"], y=fc["Trend_Continues_Pct"], mode="lines", name="If recent trend continues",
                             line=dict(color="#d7191c", width=1.5, dash="dash")))
for level, label in [(25, "Low"), (50, "Medium"), (75, "High"), (100, "Critical")]:
    fig.add_hline(y=level, line=dict(color="#bbbbbb", width=1, dash="dot"),
                  annotation_text=label, annotation_position="top left", annotation_font_size=10)
if h["Water_Stress_Total_Pct"].max() > 300:  # e.g. Kuwait ≈ 3,850%: a log axis keeps the thresholds readable
    fig.update_yaxes(type="log")
fig.update_layout(title="Water stress over time (%)", height=460, hovermode="x unified",
                  margin=dict(l=0, r=0, t=50, b=0), legend=dict(orientation="h", y=-0.15),
                  yaxis_title="% of available freshwater withdrawn", xaxis_title=None)
data.chart(fig)

if len(fc):
    st.markdown(f"**Forecast for 2035:** {s['fc_2035']:.1f}% (80% range {s['fc_low']:.1f}–{s['fc_high']:.1f}%), "
                f"tier *{s['fc_category'].split('. ')[-1]}*.")
else:
    st.warning("No forecast for this country: it has fewer than 5 real (non-repeated) observations, "
               "so a trend cannot be estimated reliably.")

# ----------------------------------------------------------------- sector mix
sect = hist.dropna(subset=["Agri_Withdrawal_10e9_m3"])
if len(sect):
    st.subheader("Who uses the water?")
    area = go.Figure()
    for col, name, color in [("Agri_Withdrawal_10e9_m3", "Agriculture", "#4daf4a"),
                             ("Ind_Withdrawal_10e9_m3", "Industry", "#377eb8"),
                             ("Mun_Withdrawal_10e9_m3", "Municipal (households & services)", "#ff7f00")]:
        area.add_trace(go.Scatter(x=sect["Year"], y=sect[col], name=name, stackgroup="one",
                                  line=dict(width=0.5, color=color)))
    area.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified",
                       yaxis_title="Withdrawal (billion m³ per year)", legend=dict(orientation="h", y=-0.2))
    data.chart(area)

# ----------------------------------------------------------------- data quality
with st.expander("Data quality notes and raw values"):
    notes = []
    if s["last_real_year"] and s["last_real_year"] <= 2010:
        notes.append(f"The latest real stress observation is from {s['last_real_year']}; later values repeat or estimate it.")
    if s["caveat"]:
        notes.append("This country has methodological footnotes (e.g. partial coverage or desalinated water included).")
    if s["mismatch"]:
        notes.append("UNSD abstraction and FAO withdrawal differ by more than 10× in some years, so the abstraction ratio is unreliable.")
    st.markdown("\n".join(f"- {x}" for x in notes) or "No special caveats for this country.")
    cols = ["Year", "Water_Stress_Total_Pct", "Water_Stress_Category", "Value_Type", "Total_Withdrawal_FAO_10e9_m3",
            "Agri_Share_Pct", "Ind_Share_Pct", "Mun_Share_Pct"]
    data.table(hist[cols], hide_index=True)
    st.download_button("Download this country's data (CSV)", hist.to_csv(index=False).encode("utf-8"),
                       file_name=f"water_stress_{country.replace(' ', '_')}.csv", mime="text/csv")
