# 🌍 Global Freshwater Resources & Water Stress Analysis (2001–2023)

## 📌 Project Overview
This project maps global renewable freshwater resources against sectoral water withdrawals (Agricultural, Industrial, and Municipal) from **2001 to 2023**. By integrating multi-source environmental datasets into a unified, reproducible Python pipeline, this repository provides clean, analysis-ready data and time-series forecasting to identify regions heading toward **Critical Water Stress** (UN SDG Indicator 6.4.2).

---

## 📂 Repository Structure
```text
data_analysis/
├── dashboard/                # Interactive dashboard (upcoming)
├── data/
│   ├── raw/                  # Unmodified raw datasets from UNSD, FAOSTAT & OWID
│   └── processed/            # Cleaned & merged datasets (CSV & Multi-sheet Excel)
├── notebooks/
│   └── 03_forecast_water_stress.ipynb  # Back-tested time-series forecast to 2035 & driver regression
├── reports/                  # Data audit/profiling outputs, forecast tables & figures/
├── src/
│   ├── 01_audit_and_profile.py   # Initial schema inspection & data quality profiling
│   ├── 02_clean_and_merge.py     # Reproducible ETL, entity matching & cleaning pipeline
│   └── water_forecast.py         # Forecasting models, back-testing & risk functions
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
   - *Metrics:* Harmonized agricultural water withdrawal records.

### Key Data Engineering & Cleaning Steps:
* **Entity Resolution:** Resolved cross-source country naming discrepancies by standardizing entities using **UN M49 numeric codes** (`m49`) as the primary join key and **ISO 3166-1 alpha-3** (`ISO3_Code`) for geospatial mapping.
* **Temporal Alignment:** Harmonized all sources across a unified calendar timeframe (**2001–2023**).
* **Feature Engineering:**
  * Calculated sectoral withdrawal shares (`Agri_Share_Pct`, `Ind_Share_Pct`, `Mun_Share_Pct`).
  * Computed `Water_Stress_Total_Pct` and categorized countries into the 5 official **UN SDG 6.4.2 Water Stress Levels** (*No Stress <25%* to *Critical Stress >100%*).
* **Quality Assurance & Caveat Tracking:**
  * Added accounting consistency checks (`Calculated_Sector_Sum_10e9_m3` vs. `Total_Withdrawal_FAO_10e9_m3`) and cleaned floating-point precision artifacts.
  * Implemented boolean quality flags (`Flag_Sector_Sum_Exceeds_Total`, `Flag_Negative_Renewable`) and preserved methodological footnote codes (`Footnotes_Reference`) to ensure analytical transparency.

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
| `Water_Stress_Total_Pct` | Percentage (`%`) | Freshwater withdrawal as a proportion of available resources |
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
4. **Run the forecast notebook** (open it in VS Code / Jupyter, or execute it headless):
   ```bash
   python -m nbconvert --to notebook --execute --inplace notebooks/03_forecast_water_stress.ipynb
   ```

---

## 📈 Forecasting Water Stress (2024–2035)
Notebook: `notebooks/03_forecast_water_stress.ipynb` · Functions: `src/water_forecast.py`

**Method**
* Fitted only on **genuine** UN observations (carried-forward repeats removed); 151 countries.
* **Back-tested** four models at three cut-offs (trained to 2015, 2016, 2018; predicting unseen later years).
  A full-history linear trend was the *worst* model; a **damped recent trend** (latest value + fading slope of the last 8 observations) had the lowest error at every cut-off and beats the naive "no change" baseline.
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

## ⚠️ Analytical Caveats
* Users conducting downstream modeling should inspect the `Any_Definition_Caveat` and `Abstracted_Footnote_Codes` columns, as certain countries report partial city coverage or include desalinated water.
* Rows flagged with `Flag_Sector_Sum_Exceeds_Total = True` reflect minor discrepancies due to staggered source updates between FAO and national agencies.
* **Water stress is not observed every year.** The UN carries the last estimate forward between survey years, so about 32% of stress values simply repeat the previous year (`Stress_Carried_Forward = True`), and 32 of 183 countries have fewer than 5 distinct values over 2001–2023. Time-series forecasts should use only countries with `Stress_Forecastable = True`, and should treat carried-forward values as gaps rather than as evidence of a flat trend.

---

## 👥 Team Members
* **Eman Jmaous** – Data Engineering & ETL Pipeline
* **[Member 2 Name]** – Exploratory Data Analysis & Geospatial Mapping
* **[Member 3 Name]** – Time-Series Forecasting & Reporting
