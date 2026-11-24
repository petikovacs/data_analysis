"""Countries at risk of crossing the High (75%) or Critical (100%) threshold by 2035."""

import plotly.express as px
import streamlit as st

import data
from water_maps import continuous_map

st.set_page_config(page_title="Countries at Risk · Water Stress", page_icon="⚠️", layout="wide")
risk = data.load_risk()

st.title("⚠️ Countries at risk by 2035")
st.markdown(
    "Countries that are **below a threshold today** but could cross it by 2035. "
    "*Chance* comes from the forecast's back-tested uncertainty; the **forecast** assumes the recent trend slows down, "
    "while **'if trend continues'** is a stress-test scenario, not a prediction."
)

with st.sidebar:
    st.header("Threshold")
    threshold = st.radio("Crossing which level?", sorted(risk["Threshold"].unique()),
                         index=0 if risk["Threshold"].str.startswith("Critical").any() else None)
    min_chance = st.slider("Show countries with a chance of at least (%)", 0, 50, 0, step=5)

table = data.risk_table(risk, threshold)
table = table[table["Chance above threshold by 2035 (%)"] >= min_chance]

c1, c2, c3 = st.columns(3)
c1.metric("Countries at risk", len(table))
c2.metric("Highest chance", f"{table['Chance above threshold by 2035 (%)'].max():.0f}%" if len(table) else "n/a",
          help=table.iloc[0]["Country"] if len(table) else None)
c3.metric("Cross even in the forecast", int(table["Crossing year (forecast)"].notna().sum()),
          help="Countries whose base forecast itself passes the threshold before 2035.")

left, right = st.columns([3, 2])
with left:
    mp = continuous_map(table.rename(columns={"Chance above threshold by 2035 (%)": "Chance_Pct"}), "Chance_Pct",
                        f"Chance of crossing the {threshold} threshold by 2035", "Chance (%)",
                        scale="OrRd", range_color=[0, 60])
    data.chart(mp)
with right:
    bar = px.bar(table.sort_values("Chance above threshold by 2035 (%)"), x="Chance above threshold by 2035 (%)",
                 y="Country", orientation="h", color="Chance above threshold by 2035 (%)",
                 color_continuous_scale="OrRd", range_color=[0, 60])
    bar.update_layout(height=max(300, 26 * len(table)), coloraxis_showscale=False, margin=dict(l=0, r=0, t=30, b=0),
                      title="Chance by 2035 (%)", xaxis_title=None, yaxis_title=None)
    data.chart(bar)

st.subheader("Details")
data.table(
    table, hide_index=True,
    column_config={
        "ISO3_Code": None,
        "Chance above threshold by 2035 (%)": st.column_config.ProgressColumn(
            "Chance above threshold by 2035 (%)", min_value=0, max_value=100, format="%d%%"),
        "Last real data": st.column_config.NumberColumn(format="%d"),
    },
)
old = table[table["Last real data"] < 2015]["Country"].tolist()
if old:
    st.caption("Less certain because the latest real data is older than 2015: " + ", ".join(old) + ".")
st.download_button("Download this table (CSV)", table.to_csv(index=False).encode("utf-8"),
                   file_name=f"countries_at_risk_{threshold.split()[0].lower()}_2035.csv", mime="text/csv")
