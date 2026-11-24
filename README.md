# 🌍 Global Freshwater Resources & Water Stress Analysis (2001–2023)

## 📌 Project Overview
This project maps global renewable freshwater resources against sectoral water withdrawals (Agricultural, Industrial, and Municipal) from **2001 to 2023**. By integrating multi-source environmental datasets into a unified, reproducible Python pipeline, this repository provides clean, analysis-ready data and time-series forecasting to identify regions heading toward **Critical Water Stress** (UN SDG Indicator 6.4.2).

---

## 📂 Repository Structure
```text
data_analysis/
├── dashboard/                # Streamlit dashboard: app.py (overview) + pages/ (map, country, risk)
├── data/
│   ├── raw/                  # Unmodified raw datasets from UNSD, FAOSTAT & OWID
│   └── processed/            # Cleaned & merged datasets (CSV & Multi-sheet Excel)
├── notebooks/
│   ├── 02_eda_and_maps.ipynb           # Exploratory data analysis & geospatial mapping
│   └── 03_forecast_water_stress.ipynb  # Back-tested time-series forecast to 2035 & driver regression
├── reports/                  # Audit outputs, forecast tables, figures/ (PNG) & maps/ (interactive HTML + PNG)
├── src/
│   ├── 01_audit_and_profile.py   # Initial schema inspection & data quality profiling
│   ├── 02_clean_and_merge.py     # Reproducible ETL, entity matching & cleaning pipeline
│   ├── water_forecast.py         # Forecasting models, back-testing & risk functions
│   └── water_maps.py             # Reusable Plotly world-map builders (notebooks & dashboard)
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

---

## 📊 Data Sources & Integration
All data ingestion, entity matching, and transformations were scripted programmatically in Python (`pandas`, `numpy`, `pycountry`) with **zero manual Excel manipulation**:

1. **UNSD Environmental Indicators (Water):**
   - *Metrics:* Renewable Freshwater Resources & Total Freshwater Abstracted ($10^9\text{ m}^3/\text{year}$).
2. **FAOSTAT / AQUASTAT Water Use Database:**
   - *Metrics:* Total Water Withdrawal and Sectoral Breakdown (Agriculture, Industry, Municipal) alongside data reliability flags (`A`, `E`, `I`, `X`).
3. **Our World in Data (OWID):**
   - *Metrics:* Harmonized agricultural water withdrawal records (re-published FAO AQUASTAT data).
4. **UN SDG Global Database, Indicator 6.4.2:**
   - *Metrics:* Official level of water stress (%), with its sector contributions and observation status.

📄 Full source notes (portals, release dates, units, coverage, definitions, unused/duplicate files): [`data/raw/SOURCES.md`](data/raw/SOURCES.md)

### Key Data Engineering & Cleaning Steps:
* **Entity Resolution:** Resolved cross-source country naming discrepancies by standardizing entities using **UN M49 numeric codes** (`m49`) as the primary join key and **ISO 3166-1 alpha-3** (`ISO3_Code`) for geospatial mapping.
* **Temporal Alignment:** Harmonized all sources across a unified calendar timeframe (**2001–2023**).
* **Feature Engineering:**
  * Calculated sectoral withdrawal shares (`Agri_Share_Pct`, `Ind_Share_Pct`, `Mun_Share_Pct`).
  * Merged the official **UN SDG 6.4.2** water stress (`Water_Stress_Total_Pct` = withdrawal ÷ (renewable resources − environmental flow requirements)) and categorized countries into its 5 levels (*No Stress <25%* to *Critical Stress >100%*).
  * Calculated the work-plan pressure indicator `Abstraction_to_Renewable_Pct` (UNSD abstraction ÷ UNSD renewable resources × 100). It is **validated against UNSD's published ratio (36 of 36 countries match)** and treated as a preliminary indicator, not as SDG 6.4.2.
* **Quality Assurance & Caveat Tracking:**
  * Added accounting consistency checks (`Calculated_Sector_Sum_10e9_m3` vs. `Total_Withdrawal_FAO_10e9_m3`) and cleaned floating-point precision artifacts.
  * Implemented boolean quality flags (`Flag_Sector_Sum_Exceeds_Total`, `Flag_Negative_Renewable`, `Flag_UNSD_FAO_Mismatch`) and preserved methodological footnote codes (`Footnotes_Reference`) to ensure analytical transparency.
  * Cross-checked the two independent volume sources: rows where UNSD abstraction and FAO withdrawal differ by more than 10× (partial coverage or reporting errors, e.g. El Salvador ~200×) are flagged and ranked separately.

---

## 📖 Data Dictionary (Processed Dataset)
Full metadata and methodological footnotes are documented inside the `Data_Dictionary` and `Footnotes_Reference` tabs of the processed Excel workbook. Key variables include:

| Column Name | Unit / Values | Description |
| :--- | :--- | :--- |
| `m49` / `ISO3_Code` | Numeric / 3-Letter | Standardized UN M49 and ISO3 country identifiers |
| `Year` | `2001 - 2023` | Calendar year |
| `Renewable_Freshwater_10e9_m3` | $10^9\text{ m}^3/\text{year}$ | Total renewable freshwater resources (UNSD) |
| `Total_Withdrawal_FAO_10e9_m3` | $10^9\text{ m}^3/\text{year}$ | Total water withdrawal across all sectors (FAO) |
| `Agri / Ind / Mun_Withdrawal` | $10^9\text{ m}^3/\text{year}$ | Sector-specific water withdrawals |
| `Water_Stress_Total_Pct` | Percentage (`%`) | Official SDG 6.4.2: withdrawal ÷ (renewable resources − environmental flow requirements) |
| `Abstraction_to_Renewable_Pct` | Percentage (`%`) | Work-plan indicator: UNSD abstraction ÷ UNSD renewable resources (preliminary, not SDG 6.4.2) |
| `Flag_UNSD_FAO_Mismatch` | `True` / `False` | UNSD abstraction and FAO withdrawal differ by more than 10×; the ratio above is unreliable for that row |
| `Water_Stress_Category` | Category `1` to `5` | UN SDG 6.4.2 Stress Classification |
| `Stress_Obs_Status` | `A` / `E` / `I` / `O` | UN status of the stress value: Reported, Estimated, Imputed, Missing |
| `Stress_Carried_Forward` | `True` / `False` | Stress value is identical to the previous year (last estimate carried forward) |
| `Stress_Distinct_Values` | Count | Number of distinct stress values the country has over 2001–2023 |
| `Stress_Forecastable` | `True` / `False` | Country has ≥ 5 distinct stress values, enough real variation to fit a trend |
| `Any_Definition_Caveat` | `True` / `False` | Indicates if country data has specific methodological footnotes |

---

## 🚀 How to Run the Pipeline
1. **Clone the repository:**
   ```bash
   git clone https://github.com/petikovacs/data_analysis.git
   cd data_analysis
   ```
2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Run the audit and data cleaning scripts:**
   ```bash
   python src/01_audit_and_profile.py
   python src/02_clean_and_merge.py
   ```
4. **Run the notebooks** (open them in VS Code / Jupyter, or execute headless). Run 03 before 02, because the 2035 risk map in 02 reads the forecast output:
   ```bash
   python -m nbconvert --to notebook --execute --inplace notebooks/03_forecast_water_stress.ipynb
   python -m nbconvert --to notebook --execute --inplace notebooks/02_eda_and_maps.ipynb
   ```

---

## 🗺️ Exploratory Analysis & Geospatial Mapping
Notebook: `notebooks/02_eda_and_maps.ipynb` · Map functions: `src/water_maps.py`

**Maps** (`reports/maps/`: open the `.html` files in a browser for hover, zoom and the year slider)
| Map | Shows |
| :--- | :--- |
| `map_01_stress_latest` | UN water stress tier of every country (latest year) |
| `map_02_stress_animation.html` | Animated 2001–2023 stress map with year slider |
| `map_03_agri_share` | Share of water withdrawn for agriculture |
| `map_04_data_freshness` | Year of each country's latest genuine (non-repeated) observation |
| `map_05_critical_risk_2035` | Chance of Critical stress (>100%) by 2035, from the forecast |

**Key findings**
* Only ~30% of stress values are reported directly by countries; ~34% repeat the previous year, and for 46 countries the latest real observation is from 2010 or earlier.
* Stress is extremely unequal: the median country withdraws ~10% of its water, while 16 countries exceed 100%. They form one belt across **North Africa, the Arabian Peninsula and Central Asia**.
* Tier composition barely changed between 2001 and 2023 (15 Critical countries in both years, same-country panel).
* **Agriculture** is the largest water user in 107 of 179 countries and causes most of the stress in 17 of the 20 most stressed; the exceptions are Gulf states where municipal use dominates.
* Global withdrawals grew ~6% from 2001 to 2023; agriculture's share rose from 67% to 71%.
* The work-plan ratio (abstraction ÷ renewable) is available for 58 countries. Once 5 implausible ones are set aside it ranks countries almost exactly like the official indicator (Spearman ρ ≈ 0.94); the top 10 are led by the UAE, Jordan, Tunisia, Qatar and Egypt.
* Renewable freshwater swings about twice as much from year to year as abstraction (median variability 23% vs 11%), so dry years push pressure up even when use is flat (e.g. Morocco 2021).

---

## 📈 Forecasting Water Stress (2024–2035)
Notebook: `notebooks/03_forecast_water_stress.ipynb` · Functions: `src/water_forecast.py`

**Method**
* Fitted only on **genuine** UN observations (carried-forward repeats removed); 151 countries.
* **Back-tested** four models at three cut-offs (trained to 2015, 2016, 2018; predicting unseen later years).
  A full-history linear trend was the *worst* model; a **damped recent trend** (latest value + fading slope of the last 8 observations) had the lowest error (both **MAE and RMSE**) at every cut-off and beats the naive "no change" baseline.
* Damping factor φ = 0.5 **tuned on the 2016 cut-off** and confirmed on 2018.
* **80% uncertainty ranges calibrated from back-test errors** (87% coverage on unseen data, i.e. slightly conservative).
* A **"recent trend continues"** scenario (no damping) is reported alongside as a stress test, not a prediction.

**Key findings**
* 16 countries are already in **Critical** stress (>100%), led by Kuwait, UAE, Saudi Arabia and Libya.
* **Tunisia and Pakistan** (just under 100%, data to 2023) have close to a 50% chance of reaching Critical stress by 2035.
* If recent trends continue, **Iraq, North Macedonia, Lebanon, Cabo Verde and Mali** would pass 100% by 2033–2035.
* Agriculture-heavy water use is linked to higher stress (Spearman ρ ≈ 0.29, p < 0.001), but the effect is weak (R² ≈ 0.08): a country's available water matters more than its sector mix.

**Outputs**
| File | Contents |
| :--- | :--- |
| `data/processed/Water_Stress_Forecast_2024_2035.csv` | Yearly forecast per country: base forecast, 80% range, trend-continues scenario, category |
| `reports/06_Countries_At_Risk_2035.csv` | Countries at risk of crossing 75% / 100%, with probability and crossing years |
| `reports/07_Forecast_Backtest_Metrics.csv` | Back-test error of each model at each cut-off |
| `reports/figures/fc_*.png` | Charts used in the notebook |

---

## 🖥️ Interactive Dashboard (Streamlit)
Folder: `dashboard/` · Data helpers: `dashboard/data.py` · Maps reuse `src/water_maps.py`

**Run it** (from the repository root, after `pip install -r requirements.txt`):
```bash
streamlit run dashboard/app.py
```
The dashboard opens in your browser (usually http://localhost:8501).

| Page | What you can do |
| :--- | :--- |
| **Overview** (`app.py`) | Headline numbers, latest UN stress map, key findings and how to read the tiers |
| **World Map** | Observed stress for any year 2001–2023 (or animated), forecast stress for any year 2024–2035, or agriculture's share of water use; tier counts below the map |
| **Country View** | Pick a country: stress history with each value marked as reported / estimated / imputed / carried forward, the 2035 forecast with its 80% range and the "trend continues" scenario, the sector mix of withdrawals, data-quality notes and a CSV download |
| **Countries at Risk** | Countries that may cross 75% or 100% by 2035: risk map, chance ranking, crossing years and a CSV download |

The dashboard only reads files produced by the pipeline and notebooks (`data/processed/` and `reports/06_Countries_At_Risk_2035.csv`); it recalculates nothing, so its numbers always match the report.

---

## ⚠️ Analytical Caveats
* Users conducting downstream modeling should inspect the `Any_Definition_Caveat` and `Abstracted_Footnote_Codes` columns, as certain countries report partial city coverage or include desalinated water.
* Rows flagged with `Flag_Sector_Sum_Exceeds_Total = True` reflect minor discrepancies due to staggered source updates between FAO and national agencies.
* **Water stress is not observed every year.** The UN carries the last estimate forward between survey years, so about 32% of stress values simply repeat the previous year (`Stress_Carried_Forward = True`), and 32 of 183 countries have fewer than 5 distinct values over 2001–2023. Time-series forecasts should use only countries with `Stress_Forecastable = True`, and should treat carried-forward values as gaps rather than as evidence of a flat trend.

---

## 👥 Team Members
* **Eman Jmaous** – Data Engineering & ETL Pipeline
* **Mohamed Ghassen Boughalmi** – Exploratory Data Analysis & Geospatial Mapping
* **[Member 3 Name]** – Time-Series Forecasting & Reporting
