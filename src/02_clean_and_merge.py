"""
Global Freshwater Resources & Water Stress ETL Pipeline (2001–2023)
==================================================================
Description:
    This script ingests raw water withdrawal, renewable freshwater resources, 
    and SDG 6.4.2 water stress datasets from UNSD, FAO AQUASTAT, and OWID.
    It performs programmatic entity resolution (via UN M49 and ISO3 codes), 
    standardizes units to billion cubic meters (10^9 m3/year), calculates sectoral 
    shares, applies floating-point precision cleanup, and flags methodological caveats.

Inputs (from data/raw/):
    - agricultural-water-withdrawals.csv (OWID / FAO)
    - aquastat_sector_withdrawal.csv (FAO AQUASTAT)
    - sdg_water_stress.csv.xlsx (UN SDG 6.4.2)
    - Freshwater abstracted.xlsx (UNSD)
    - Renewable freshwater resources.xlsx (UNSD)

Outputs (to data/processed/):
    - Master_Global_Water_Dataset_2001_2023.csv
    - Master_Global_Water_Dataset_2001_2023.xlsx
      (sheets: Master_Data, Data_Dictionary, Footnotes_Reference)

Usage:
    python src/02_clean_and_merge.py
"""

import pandas as pd
import numpy as np
import pycountry
from pathlib import Path

# Directory Configuration
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
REPORTS_DIR = BASE_DIR / "reports"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
YEAR_MIN, YEAR_MAX = 2001, 2023
OUTPUT_STEM = f"Master_Global_Water_Dataset_{YEAR_MIN}_{YEAR_MAX}"

# A country's stress series is only worth forecasting if it actually moves.
# UN SDG 6.4.2 carries the last estimate forward between survey years, so some
# countries report one identical value for all 23 years.
MIN_DISTINCT_STRESS_VALUES = 5
VOLUME_DECIMALS = 6  # 10^9 m3 to 6 decimals = precision of 1,000 m3
MISMATCH_FACTOR = 10  # flag UNSD abstraction more than 10x above/below FAO total withdrawal


def iso3_to_m49(iso_code):
    """Convert ISO 3166-1 alpha-3 code to UN M49 numeric country code."""
    if pd.isna(iso_code):
        return None
    c = pycountry.countries.get(alpha_3=str(iso_code).strip())
    return int(c.numeric) if c and hasattr(c, 'numeric') else None


def m49_to_iso3(m49_code):
    """Convert UN M49 numeric country code to ISO 3166-1 alpha-3 code."""
    c = pycountry.countries.get(numeric=f"{int(m49_code):03d}")
    return c.alpha_3 if c else None


# 1. Clean OWID Agriculture Dataset
df_agri = pd.read_csv(RAW_DIR / "agricultural-water-withdrawals.csv")
df_agri = df_agri[df_agri['Code'].notna() & (~df_agri['Code'].astype(str).str.startswith('OWID_'))].copy()
df_agri['m49'] = df_agri['Code'].apply(iso3_to_m49)
df_agri = df_agri.dropna(subset=['m49']).copy()
df_agri['m49'] = df_agri['m49'].astype(int)
df_agri['Year'] = pd.to_numeric(df_agri['Year'], errors='coerce').astype(int)
df_agri = df_agri[(df_agri['Year'] >= YEAR_MIN) & (df_agri['Year'] <= YEAR_MAX)].copy()
df_agri['Agri_Withdrawal_10e9_m3'] = pd.to_numeric(df_agri['Agricultural water withdrawal'], errors='coerce') / 1e9

df_agri_clean = df_agri[['m49', 'Code', 'Entity', 'Year', 'Agri_Withdrawal_10e9_m3']].drop_duplicates(
    subset=['m49', 'Year']
).rename(columns={'Code': 'ISO3_Code', 'Entity': 'Country_OWID'})


# 2. Clean FAO AQUASTAT Sectoral Withdrawals
df_fao = pd.read_csv(RAW_DIR / "aquastat_sector_withdrawal.csv")
df_fao = df_fao[df_fao['IsAggregate'] == False].copy()
df_fao['m49'] = pd.to_numeric(df_fao['m49'], errors='coerce').astype(int)
df_fao['Year'] = pd.to_numeric(df_fao['Year'], errors='coerce').astype(int)
df_fao = df_fao[(df_fao['Year'] >= YEAR_MIN) & (df_fao['Year'] <= YEAR_MAX)].copy()

df_fao_piv = df_fao.pivot_table(
    index=['m49', 'Area', 'Year'], columns='Variable', values='Value', aggfunc='first'
).reset_index()
df_fao_piv.columns.name = None

tot_symbols = df_fao[df_fao['Variable'] == 'Total water withdrawal'][['m49', 'Year', 'Symbol']].drop_duplicates(
    subset=['m49', 'Year']
).rename(columns={'Symbol': 'FAO_Total_Symbol'})

df_fao_piv = pd.merge(df_fao_piv, tot_symbols, on=['m49', 'Year'], how='left')
df_fao_piv = df_fao_piv.rename(columns={
    'Area': 'Country_FAO',
    'Industrial water withdrawal': 'Ind_Withdrawal_10e9_m3',
    'Municipal water withdrawal': 'Mun_Withdrawal_10e9_m3',
    'Total water withdrawal': 'Total_Withdrawal_FAO_10e9_m3'
})

# Master whitelist of valid UN M49 country codes (excludes Excel footnote rows)
valid_countries_m49 = set(df_fao_piv['m49'].unique()).union(set(df_agri_clean['m49'].unique()))


# 3. Clean SDG 6.4.2 Water Stress Dataset
df_stress = pd.read_excel(RAW_DIR / "sdg_water_stress.csv.xlsx")
df_stress = df_stress.dropna(subset=['OBS_VALUE']).copy()
df_stress['m49'] = pd.to_numeric(df_stress['REF_AREA'], errors='coerce')
df_stress = df_stress[df_stress['m49'].isin(valid_countries_m49)].copy()
df_stress['m49'] = df_stress['m49'].astype(int)
df_stress['Year'] = pd.to_numeric(df_stress['TIME_PERIOD'], errors='coerce').astype(int)
df_stress = df_stress[(df_stress['Year'] >= YEAR_MIN) & (df_stress['Year'] <= YEAR_MAX)].copy()

df_stress_piv = df_stress.pivot_table(
    index=['m49', 'AREA', 'Year'], columns='ACTIVITY', values='OBS_VALUE', aggfunc='first'
).reset_index()
df_stress_piv.columns.name = None

# Keep the UN observation status of the total stress value
# (A = reported by country, E = estimated, I = imputed, O = missing/other)
stress_status = df_stress[df_stress['ACTIVITY'] == '_T'][['m49', 'Year', 'OBS_STATUS']].drop_duplicates(
    subset=['m49', 'Year']
).rename(columns={'OBS_STATUS': 'Stress_Obs_Status'})
df_stress_piv = pd.merge(df_stress_piv, stress_status, on=['m49', 'Year'], how='left')

df_stress_piv = df_stress_piv.rename(columns={
    'AREA': 'Country_SDG',
    '_T': 'Water_Stress_Total_Pct',
    'ISIC4_A01_A0210_A0322': 'Water_Stress_Agri_Pct',
    'ISIC4_BTFXE': 'Water_Stress_Ind_Pct',
    'ISIC4_GTT': 'Water_Stress_Services_Pct'
})


# 4. Clean UNSD Excel Files (Deduplicated & Strictly Filtered to Valid Countries)
def split_unsd_sheet(filepath):
    """Split a UNSD 'Data' sheet into its country-data block and its footnote block.

    UNSD sheets list countries first, then a 'Footnote number' header row followed
    by the footnote definitions. Footnote numbers (1, 2, 3, ...) overlap with real
    M49 codes (4 = Afghanistan, 8 = Albania, ...), so filtering by valid country
    codes alone is not enough: the footnote block must be cut off by position.

    Returns:
        (data_rows, footnotes) where footnotes has columns Footnote_Code, Explanation.
    """
    df_raw = pd.read_excel(filepath, sheet_name='Data')
    marker = df_raw.index[df_raw['CountryID'].astype(str).str.strip() == 'Footnote number']
    if len(marker) == 0:
        return df_raw, pd.DataFrame(columns=['Footnote_Code', 'Explanation'])
    cut = marker[0]
    footnotes = df_raw.loc[cut + 1:, ['CountryID', 'Country']].dropna(subset=['CountryID'])
    footnotes.columns = ['Footnote_Code', 'Explanation']
    footnotes['Footnote_Code'] = footnotes['Footnote_Code'].astype(str).str.strip()
    return df_raw.loc[:cut - 1].copy(), footnotes.reset_index(drop=True)


def clean_unsd_excel(filepath, value_col, prefix):
    """Parse UNSD Excel matrices, extract footnote caveats, convert units, and deduplicate.

    Returns:
        (long_df, footnotes): one row per (m49, Year) with the value in 10^9 m3,
        plus the footnote definitions found at the bottom of the sheet.
    """
    df_raw, footnotes = split_unsd_sheet(filepath)
    df_raw['m49'] = pd.to_numeric(df_raw['CountryID'], errors='coerce')

    # Keep valid country codes only (footnote block was already removed above)
    df_data = df_raw[df_raw['m49'].isin(valid_countries_m49)].copy()
    df_data['m49'] = df_data['m49'].astype(int)
    
    fn_cols = [c for c in df_data.columns if 'Footnote' in str(c)]
    df_data[f'{prefix}_Footnote_Codes'] = df_data[fn_cols].apply(
        lambda r: ', '.join(sorted(set(str(x).strip() for x in r if pd.notna(x) and str(x).strip() != ''))), axis=1
    )
    df_data[f'{prefix}_Has_Caveat'] = df_data[f'{prefix}_Footnote_Codes'] != ''
    df_data[f'{prefix}_Footnote_Codes'] = df_data[f'{prefix}_Footnote_Codes'].replace('', np.nan)
    
    year_cols = [c for c in df_data.columns if str(c).strip().isdigit() and YEAR_MIN <= int(str(c).strip()) <= YEAR_MAX]
    df_data[year_cols] = df_data[year_cols].replace('...', np.nan)
    
    df_melted = df_data.melt(
        id_vars=['m49', f'{prefix}_Has_Caveat', f'{prefix}_Footnote_Codes'],
        value_vars=year_cols,
        var_name='Year',
        value_name=value_col
    )
    df_melted['Year'] = df_melted['Year'].astype(int)
    df_melted[value_col] = pd.to_numeric(df_melted[value_col], errors='coerce') / 1000.0
    
    # Deduplicate multi-source entries by prioritizing non-null observations
    df_melted = df_melted.sort_values(by=['m49', 'Year', value_col], na_position='last')
    df_melted = df_melted.drop_duplicates(subset=['m49', 'Year'], keep='first')
    return df_melted, footnotes


df_abs_clean, fn_abs = clean_unsd_excel(RAW_DIR / "Freshwater abstracted.xlsx", "Freshwater_Abstracted_UNSD_10e9_m3", "Abstracted")
df_ren_clean, fn_ren = clean_unsd_excel(RAW_DIR / "Renewable freshwater resources.xlsx", "Renewable_Freshwater_10e9_m3", "Renewable")


# 5. Merge All Datasets (1 Row per Country per Year)
master = pd.merge(df_fao_piv, df_agri_clean, on=['m49', 'Year'], how='outer')
master = pd.merge(master, df_stress_piv, on=['m49', 'Year'], how='outer')
master = pd.merge(master, df_abs_clean, on=['m49', 'Year'], how='outer')
master = pd.merge(master, df_ren_clean, on=['m49', 'Year'], how='outer')

master['Country'] = master['Country_FAO'].fillna(master['Country_OWID']).fillna(master['Country_SDG'])
master['Country'] = master.groupby('m49')['Country'].transform(lambda x: x.ffill().bfill())
master['ISO3_Code'] = master['m49'].apply(m49_to_iso3)


# 6. Consistency Check, Precision Cleanup & Feature Engineering
sector_sum = (
    master['Agri_Withdrawal_10e9_m3'].fillna(0) + 
    master['Ind_Withdrawal_10e9_m3'].fillna(0) + 
    master['Mun_Withdrawal_10e9_m3'].fillna(0)
)
master['Calculated_Sector_Sum_10e9_m3'] = np.where(
    master[['Agri_Withdrawal_10e9_m3', 'Ind_Withdrawal_10e9_m3', 'Mun_Withdrawal_10e9_m3']].notna().any(axis=1),
    sector_sum, np.nan
).round(VOLUME_DECIMALS)

# Compute accounting difference and eliminate floating-point artifacts (-0.0 and 1e-06)
diff_val = (master['Calculated_Sector_Sum_10e9_m3'] - master['Total_Withdrawal_FAO_10e9_m3']).round(VOLUME_DECIMALS)
master['Diff_Sum_vs_Total_10e9_m3'] = np.where(diff_val.abs() < 10 ** -VOLUME_DECIMALS, 0.0, diff_val)

# Standardize decimal precision across all volumetric columns
volume_cols = [
    'Renewable_Freshwater_10e9_m3', 'Freshwater_Abstracted_UNSD_10e9_m3',
    'Total_Withdrawal_FAO_10e9_m3', 'Agri_Withdrawal_10e9_m3', 
    'Ind_Withdrawal_10e9_m3', 'Mun_Withdrawal_10e9_m3'
]
master[volume_cols] = master[volume_cols].round(VOLUME_DECIMALS)

# Quality Flags
master['Flag_Sector_Sum_Exceeds_Total'] = master['Diff_Sum_vs_Total_10e9_m3'] > 0.05
master['Flag_Negative_Renewable'] = master['Renewable_Freshwater_10e9_m3'] < 0
master['Any_Definition_Caveat'] = master['Abstracted_Has_Caveat'].fillna(False) | master['Renewable_Has_Caveat'].fillna(False)

# Sectoral Shares (%)
master['Agri_Share_Pct'] = ((master['Agri_Withdrawal_10e9_m3'] / master['Total_Withdrawal_FAO_10e9_m3']) * 100).round(2)
master['Ind_Share_Pct'] = ((master['Ind_Withdrawal_10e9_m3'] / master['Total_Withdrawal_FAO_10e9_m3']) * 100).round(2)
master['Mun_Share_Pct'] = ((master['Mun_Withdrawal_10e9_m3'] / master['Total_Withdrawal_FAO_10e9_m3']) * 100).round(2)

# Work-plan pressure indicator: freshwater abstracted / renewable freshwater resources (%).
# Both inputs come from UNSD for the same country and year, matching UNSD's own published ratio.
# NOT the official SDG 6.4.2 indicator: it ignores environmental flow requirements.
renewable_positive = master['Renewable_Freshwater_10e9_m3'].where(master['Renewable_Freshwater_10e9_m3'] > 0)
master['Abstraction_to_Renewable_Pct'] = (
    master['Freshwater_Abstracted_UNSD_10e9_m3'] / renewable_positive * 100
).round(2)

# Plausibility check between the two independent volume sources: UNSD abstraction should be of the same
# order as FAO total withdrawal. A 10x gap points to partial coverage (e.g. city-only data, see footnotes)
# or a reporting/unit error (e.g. El Salvador ~200x), so the work-plan ratio is unreliable for that row.
unsd_vs_fao = master['Freshwater_Abstracted_UNSD_10e9_m3'] / master['Total_Withdrawal_FAO_10e9_m3'].where(
    master['Total_Withdrawal_FAO_10e9_m3'] > 0)
master['Flag_UNSD_FAO_Mismatch'] = (unsd_vs_fao > MISMATCH_FACTOR) | (unsd_vs_fao < 1 / MISMATCH_FACTOR)

# UN SDG 6.4.2 Water Stress Categorization
def categorize_stress(val):
    """Classify total water stress percentage into official UN SDG 6.4.2 tiers."""
    if pd.isna(val): return 'Unknown'
    elif val < 25: return '1. No Stress (<25%)'
    elif val < 50: return '2. Low Stress (25-50%)'
    elif val < 75: return '3. Medium Stress (50-75%)'
    elif val < 100: return '4. High Stress (75-100%)'
    else: return '5. Critical Stress (>100%)'

master['Water_Stress_Category'] = master['Water_Stress_Total_Pct'].apply(categorize_stress)


# 7. Water Stress Data-Quality Features (for forecasting)
master = master.sort_values(['m49', 'Year']).reset_index(drop=True)

# True when the stress value is identical to the same country's previous year,
# i.e. the UN carried the last estimate forward rather than observing a new one.
prev_stress = master.groupby('m49')['Water_Stress_Total_Pct'].shift(1)
master['Stress_Carried_Forward'] = (
    master['Water_Stress_Total_Pct'].notna() & (master['Water_Stress_Total_Pct'] == prev_stress)
)

# Per-country summary: how many distinct stress values exist across the period
master['Stress_Distinct_Values'] = master.groupby('m49')['Water_Stress_Total_Pct'].transform('nunique')
master['Stress_Forecastable'] = master['Stress_Distinct_Values'] >= MIN_DISTINCT_STRESS_VALUES


# 8. Final Column Selection & Export
final_cols = [
    'm49', 'ISO3_Code', 'Country', 'Year',
    'Renewable_Freshwater_10e9_m3', 'Freshwater_Abstracted_UNSD_10e9_m3',
    'Total_Withdrawal_FAO_10e9_m3', 'Calculated_Sector_Sum_10e9_m3', 'Diff_Sum_vs_Total_10e9_m3',
    'Agri_Withdrawal_10e9_m3', 'Ind_Withdrawal_10e9_m3', 'Mun_Withdrawal_10e9_m3',
    'Agri_Share_Pct', 'Ind_Share_Pct', 'Mun_Share_Pct', 'Abstraction_to_Renewable_Pct',
    'Water_Stress_Total_Pct', 'Water_Stress_Category',
    'Water_Stress_Agri_Pct', 'Water_Stress_Ind_Pct', 'Water_Stress_Services_Pct',
    'Stress_Obs_Status', 'Stress_Carried_Forward', 'Stress_Distinct_Values', 'Stress_Forecastable',
    'FAO_Total_Symbol', 'Any_Definition_Caveat',
    'Abstracted_Footnote_Codes', 'Renewable_Footnote_Codes',
    'Flag_Sector_Sum_Exceeds_Total', 'Flag_Negative_Renewable', 'Flag_UNSD_FAO_Mismatch',
]
master = master[master['Year'].between(YEAR_MIN, YEAR_MAX)]
master = master.dropna(subset=['Country'])[final_cols]

DATA_DICTIONARY = [
    ('m49', 'UN Numeric Code', 'UN M49 standard numeric country code (Primary Join Key).'),
    ('ISO3_Code', '3-Letter Code', 'ISO 3166-1 alpha-3 country code (e.g., EGY, SAU, USA) for geospatial mapping.'),
    ('Country', 'Text', 'Standardized official country or territory name.'),
    ('Year', f'{YEAR_MIN} - {YEAR_MAX}', 'Calendar year (Unified common time period across all 5 sources).'),
    ('Renewable_Freshwater_10e9_m3', '10^9 m3/year', 'Total renewable freshwater resources in billion cubic meters per year (Source: UNSD).'),
    ('Freshwater_Abstracted_UNSD_10e9_m3', '10^9 m3/year', 'Total freshwater abstracted as officially reported by countries in billion m3/year (Source: UNSD).'),
    ('Total_Withdrawal_FAO_10e9_m3', '10^9 m3/year', 'Total water withdrawal across all sectors in billion m3/year (Source: FAO AQUASTAT).'),
    ('Calculated_Sector_Sum_10e9_m3', '10^9 m3/year', 'Sum of Agricultural + Industrial + Municipal water withdrawals in billion m3/year.'),
    ('Diff_Sum_vs_Total_10e9_m3', '10^9 m3/year', 'Difference between Calculated_Sector_Sum and Total_Withdrawal_FAO for accounting consistency.'),
    ('Agri_Withdrawal_10e9_m3', '10^9 m3/year', 'Water withdrawal for the Agricultural sector in billion m3/year (Source: FAO / OWID).'),
    ('Ind_Withdrawal_10e9_m3', '10^9 m3/year', 'Water withdrawal for the Industrial sector in billion m3/year (Source: FAO AQUASTAT).'),
    ('Mun_Withdrawal_10e9_m3', '10^9 m3/year', 'Water withdrawal for the Municipal/Domestic sector in billion m3/year (Source: FAO AQUASTAT).'),
    ('Agri_Share_Pct / Ind_Share_Pct / Mun_Share_Pct', 'Percentage (%)', 'Sectoral percentage share of Total_Withdrawal_FAO.'),
    ('Abstraction_to_Renewable_Pct', 'Percentage (%)', 'Work-plan pressure indicator: UNSD freshwater abstracted / UNSD renewable freshwater resources x 100 (same year). Preliminary indicator, NOT the official SDG 6.4.2 (ignores environmental flow requirements).'),
    ('Water_Stress_Total_Pct', 'Percentage (%)', 'Official UN SDG 6.4.2 water stress: total freshwater withdrawal / (total renewable freshwater resources - environmental flow requirements) x 100.'),
    ('Water_Stress_Category', 'Category (1 to 5)', 'UN SDG 6.4.2 Stress Classification: No Stress (<25%), Low (25-50%), Medium (50-75%), High (75-100%), Critical (>100%).'),
    ('Water_Stress_Agri / Ind / Services_Pct', 'Percentage (%)', 'Contribution of Agriculture, Industry, and Services sectors to the total water stress percentage.'),
    ('Stress_Obs_Status', 'A, E, I, O', 'UN observation status of Water_Stress_Total_Pct: A = Reported by country, E = Estimated, I = Imputed, O = Missing/other.'),
    ('Stress_Carried_Forward', 'True / False', 'True when the stress value equals the previous year for the same country (last estimate carried forward, not a new observation).'),
    ('Stress_Distinct_Values', 'Count', f'Number of distinct stress values the country has across {YEAR_MIN}-{YEAR_MAX}.'),
    ('Stress_Forecastable', 'True / False', f'True when the country has at least {MIN_DISTINCT_STRESS_VALUES} distinct stress values, i.e. enough real variation to fit a time-series trend.'),
    ('FAO_Total_Symbol', 'A, E, I, X', 'FAO data reliability flag: A = Official national figure, E = Estimated, I = Imputed, X = External agency source.'),
    ('Any_Definition_Caveat', 'True / False', 'True indicates the country has specific methodological footnotes (e.g., partial city coverage, sector exclusion, or desalination included).'),
    ('Abstracted_Footnote_Codes / Renewable_Footnote_Codes', 'Codes / Numbers', "Specific footnote codes/numbers applicable to the country (refer to the 'Footnotes_Reference' sheet)."),
    ('Flag_Sector_Sum_Exceeds_Total', 'True / False', 'True indicates (Agri + Ind + Mun) exceeds Total_Withdrawal_FAO by > 0.05 billion m3 due to staggered source updates.'),
    ('Flag_Negative_Renewable', 'True / False', 'True indicates negative renewable freshwater balance (< 0) where evapotranspiration exceeds precipitation.'),
    ('Flag_UNSD_FAO_Mismatch', 'True / False', 'True when UNSD freshwater abstracted is more than 10x above or below FAO total withdrawal for the same year (partial coverage or reporting/unit error); Abstraction_to_Renewable_Pct is unreliable for these rows.'),
]
df_dictionary = pd.DataFrame(DATA_DICTIONARY, columns=['Column_Name', 'Unit_or_Values', 'Description'])

df_footnotes = pd.concat([
    fn_abs.assign(Source_Dataset='Freshwater Abstracted'),
    fn_ren.assign(Source_Dataset='Renewable Resources'),
], ignore_index=True)[['Source_Dataset', 'Footnote_Code', 'Explanation']]

csv_path = PROCESSED_DIR / f"{OUTPUT_STEM}.csv"
xlsx_path = PROCESSED_DIR / f"{OUTPUT_STEM}.xlsx"
master.to_csv(csv_path, index=False, encoding='utf-8-sig')
with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
    master.to_excel(writer, sheet_name='Master_Data', index=False)
    df_dictionary.to_excel(writer, sheet_name='Data_Dictionary', index=False)
    df_footnotes.to_excel(writer, sheet_name='Footnotes_Reference', index=False)

n_countries = master['m49'].nunique()
n_forecastable = master.loc[master['Stress_Forecastable'], 'm49'].nunique()
print(f"Saved {len(master):,} rows ({n_countries} countries, {YEAR_MIN}-{YEAR_MAX})")
print(f"  -> {csv_path.relative_to(BASE_DIR)}")
print(f"  -> {xlsx_path.relative_to(BASE_DIR)}")
print(f"Stress values carried forward from previous year: {master['Stress_Carried_Forward'].mean():.1%}")
print(f"Countries with enough variation to forecast: {n_forecastable} of {n_countries}")