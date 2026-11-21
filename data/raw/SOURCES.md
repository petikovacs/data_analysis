# Raw Data Sources

All files in `data/raw/` are kept **exactly as downloaded**; no manual edits were made in Excel.
Every transformation happens in `src/02_clean_and_merge.py`.

Files were added to the repository on **15 Nov 2026** (commit `0d61dd2`). Release and extraction dates
below are taken from the files' own description sheets where available.

> ⚠️ **To confirm by the member who downloaded each file:** the exact download URL/filters and download date.
> The URLs below are the official portals for each dataset.

---

## Files used by the pipeline

### 1. UNSD: Freshwater abstracted
| | |
| :--- | :--- |
| **File** | `Freshwater abstracted.xlsx` |
| **Publisher** | United Nations Statistics Division (UNSD), Environment Statistics, Environmental Indicators: Water |
| **Portal** | https://unstats.un.org/unsd/envstats/qindicators.cshtml (section *Inland Water Resources*) |
| **Release date** | 9 Jan 2026 (from the file's *Description* sheet) |
| **Coverage** | 119 countries/areas, 2001–2024 (pipeline keeps 2001–2023) |
| **Unit** | Million m³/year → converted to 10⁹ m³/year (÷ 1,000) |
| **Definition** | Water removed from any surface or groundwater source, permanently or temporarily, incl. abstraction by the water supply industry |
| **Sources inside the file** | `U` = UNSD/UNEP Questionnaire, `E` = Eurostat (extracted 1 Dec 2025), `O` = OECD (extracted 1 Dec 2025) |
| **Notes** | Country footnotes (partial coverage, hydro excluded, desalination included, etc.) are kept in the `Abstracted_Footnote_Codes` column and the `Footnotes_Reference` sheet |

### 2. UNSD: Renewable freshwater resources
| | |
| :--- | :--- |
| **File** | `Renewable freshwater resources.xlsx` |
| **Publisher / Portal** | UNSD, same page as above |
| **Release date** | 16 Dec 2025 |
| **Coverage** | 82 countries/areas, 2001–2024, **sparse** (≈ 29% of country-years filled after merging) |
| **Unit** | Million m³/year → converted to 10⁹ m³/year |
| **Definition** | Internal flow + inflow of surface and groundwater from neighbouring countries |
| **Sources inside the file** | `U` / `E` (extracted 12 Dec 2025) / `O` (extracted 12 Dec 2025) |

### 3. FAO AQUASTAT: Water withdrawal by sector
| | |
| :--- | :--- |
| **File** | `aquastat_sector_withdrawal.csv` |
| **Publisher** | Food and Agriculture Organization (FAO), AQUASTAT |
| **Portal** | https://data.apps.fao.org/aquastat/ |
| **Variables** | Total, Industrial and Municipal water withdrawal |
| **Coverage** | 204 areas (incl. aggregates, removed via `IsAggregate`), 2001–2023 |
| **Unit** | 10⁹ m³/year (no conversion needed) |
| **Reliability flag** | `Symbol`: A = official national figure, E = estimate, I = imputed, X = external source (kept as `FAO_Total_Symbol`) |

### 4. Our World in Data: Agricultural water withdrawal
| | |
| :--- | :--- |
| **File** | `agricultural-water-withdrawals.csv` |
| **Publisher** | Our World in Data (OWID), re-publishing FAO AQUASTAT data |
| **Portal** | https://ourworldindata.org/grapher/agricultural-water-withdrawals |
| **Coverage** | 208 entities, 1965–2023 (pipeline keeps 2001–2023; `OWID_*` aggregate codes removed) |
| **Unit** | m³/year → converted to 10⁹ m³/year (÷ 10⁹) |
| **Why OWID** | Provides the agricultural series in one clean file with ISO3 codes; the original values come from FAO AQUASTAT |

### 5. UN SDG Global Database: Indicator 6.4.2 (Level of water stress)
| | |
| :--- | :--- |
| **File** | `sdg_water_stress.csv.xlsx` (an Excel file despite the `.csv` in its name) |
| **Publisher** | UN Statistics Division SDG Global Database; custodian agency FAO |
| **Portal** | https://unstats.un.org/sdgs/dataportal (series `ER_H2O_STRESS`) |
| **Coverage** | 211 countries, 2000–2023 (pipeline keeps 2001–2023) |
| **Unit** | % (`PT`) |
| **Definition** | Total freshwater withdrawal ÷ (total renewable freshwater resources − **environmental flow requirements**) × 100 |
| **Status flag** | `OBS_STATUS`: A = reported, E = estimated, I = imputed (kept as `Stress_Obs_Status`) |
| **Important** | Values are repeated between survey years; repeats are flagged as `Stress_Carried_Forward` |

---

## Reference / validation files (not merged)

| File | Contents | Use |
| :--- | :--- | :--- |
| `unsd_stress_ratio_latest_year.xlsx` | UNSD's published *freshwater abstracted as % of renewable freshwater resources*, latest year per country (released 16 Jan 2026, 131 countries) | Used in `notebooks/02_eda_and_maps.ipynb` to **validate** our own `Abstraction_to_Renewable_Pct` |
| `SDG_6.4.2_Metadata.xlsx` | FAO metadata for indicator 6.4.2 (concepts, method) | Documentation only |
| `unsd_precipitation.xlsx` | UNSD precipitation (million m³) | Not used |
| `unsd_resources_per_capita.xlsx` | UNSD renewable freshwater per capita | Not used |
| `unsd_freshwater_abstracted.xlsx`, `unsd_renewable_resources.xlsx` | **Byte-identical copies** of files 1 and 2 above | Not used (duplicates) |
| `aquastat_pressure_agri.csv.csv` | AQUASTAT pressure / efficiency indicators | **Not used.** The file has exactly 50,000 rows, the export limit, and its last variable (*agricultural withdrawal per capita*) is cut off, so it is incomplete |

---

## Why the project uses two water-pressure indicators

| Indicator | Column | Role |
| :--- | :--- | :--- |
| **Official UN SDG 6.4.2 water stress** | `Water_Stress_Total_Pct` | Main indicator: complete coverage, internationally comparable, accounts for environmental flow requirements |
| **Abstraction ÷ renewable freshwater** (work-plan indicator) | `Abstraction_to_Renewable_Pct` | Preliminary pressure indicator computed by us from UNSD data; validated against UNSD's published ratio. **Not** the official SDG 6.4.2 indicator, as it ignores environmental flow requirements |
