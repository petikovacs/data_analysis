# 🌍 Global Freshwater Resources & Water Stress Analysis (2001–2023)

## 📌 Project Overview
This project maps global renewable freshwater resources against sectoral water withdrawals (Agricultural, Industrial, and Municipal) from **2001 to 2023**. By integrating multi-source environmental datasets into a unified, reproducible Python pipeline, this repository provides clean, analysis-ready data and time-series forecasting to identify regions heading toward **Critical Water Stress** (UN SDG Indicator 6.4.2).

---

## 📂 Repository Structure
```text
data_analysis/
├── dashboard/                # Interactive dashboards & visual analytics (Upcoming)
├── data/
│   ├── raw/                  # Unmodified raw datasets from UNSD, FAOSTAT & OWID
│   └── processed/            # Cleaned & merged datasets (CSV & Multi-sheet Excel)
├── notebooks/                # Exploratory Data Analysis (EDA) & Time-Series Forecasting
├── reports/                  # Data audit/profiling outputs, final report & presentation
├── src/
│   ├── 01_audit_and_profile.py   # Initial schema inspection & data quality profiling
│   └── 02_clean_and_merge.py     # Reproducible ETL, entity matching & cleaning pipeline
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
| `Any_Definition_Caveat` | `True` / `False` | Indicates if country data has specific methodological footnotes |

---

## 🚀 How to Run the Pipeline
1. **Clone the repository:**
   ```bash
   git clone https://github.com
   cd data_analysis
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the audit and data cleaning scripts:**
   ```bash
   python src/01_audit_and_profile.py
   python src/02_clean_and_merge.py
   ```

---

## ⚠️ Analytical Caveats
* Users conducting downstream modeling should inspect the `Any_Definition_Caveat` and `Abstracted_Footnote_Codes` columns, as certain countries report partial city coverage or include desalinated water.
* Rows flagged with `Flag_Sector_Sum_Exceeds_Total = True` reflect minor discrepancies due to staggered source updates between FAO and national agencies.

---

## 👥 Team Members
* **Eman Jmaous** – Data Engineering & ETL Pipeline
* **[Member 2 Name]** – Exploratory Data Analysis & Geospatial Mapping
* **[Member 3 Name]** – Time-Series Forecasting & Reporting
