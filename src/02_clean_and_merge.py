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
    - global_water_stress_cleaned_2001_2023.csv
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
df_fao_piv.rename(columns={
    'Area': 'Country_FAO',
    'Industrial water withdrawal': 'Ind_Withdrawal_10e9_m3',
    'Municipal water withdrawal': 'Mun_Withdrawal_10e9_m3',
    'Total water withdrawal': 'Total_Withdrawal_FAO_10e9_m3'
}, inplace=True)

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
df_stress_piv.rename(columns={
    'AREA': 'Country_SDG',
    '_T': 'Water_Stress_Total_Pct',
    'ISIC4_A01_A0210_A0322': 'Water_Stress_Agri_Pct',
    'ISIC4_BTFXE': 'Water_Stress_Ind_Pct',
    'ISIC4_GTT': 'Water_Stress_Services_Pct'
}, inplace=True)


# 4. Clean UNSD Excel Files (Deduplicated & Strictly Filtered to Valid Countries)
def clean_unsd_excel(filepath, value_col, prefix):
    """Parse UNSD Excel matrices, extract footnote caveats, convert units, and deduplicate."""
    xl = pd.ExcelFile(filepath)
    df_raw = xl.parse('Data')
    df_raw['m49'] = pd.to_numeric(df_raw['CountryID'], errors='coerce')
    
    # Strict filtering to valid country codes (prevents ingesting footnote rows 1..37)
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
    return df_melted


df_abs_clean = clean_unsd_excel(RAW_DIR / "Freshwater abstracted.xlsx", "Freshwater_Abstracted_UNSD_10e9_m3", "Abstracted")
df_ren_clean = clean_unsd_excel(RAW_DIR / "Renewable freshwater resources.xlsx", "Renewable_Freshwater_10e9_m3", "Renewable")


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
).round(4)

# Compute accounting difference and eliminate floating-point artifacts (-0.0 and 1e-06)
diff_val = (master['Calculated_Sector_Sum_10e9_m3'] - master['Total_Withdrawal_FAO_10e9_m3']).round(4)
master['Diff_Sum_vs_Total_10e9_m3'] = np.where(diff_val.abs() < 1e-4, 0.0, diff_val)

# Standardize decimal precision across all volumetric columns
volume_cols = [
    'Renewable_Freshwater_10e9_m3', 'Freshwater_Abstracted_UNSD_10e9_m3',
    'Total_Withdrawal_FAO_10e9_m3', 'Agri_Withdrawal_10e9_m3', 
    'Ind_Withdrawal_10e9_m3', 'Mun_Withdrawal_10e9_m3'
]
master[volume_cols] = master[volume_cols].round(4)

# Quality Flags
master['Flag_Sector_Sum_Exceeds_Total'] = master['Diff_Sum_vs_Total_10e9_m3'] > 0.05
master['Flag_Negative_Renewable'] = master['Renewable_Freshwater_10e9_m3'] < 0
master['Any_Definition_Caveat'] = master['Abstracted_Has_Caveat'].fillna(False) | master['Renewable_Has_Caveat'].fillna(False)

# Sectoral Shares (%)
master['Agri_Share_Pct'] = ((master['Agri_Withdrawal_10e9_m3'] / master['Total_Withdrawal_FAO_10e9_m3']) * 100).round(2)
master['Ind_Share_Pct'] = ((master['Ind_Withdrawal_10e9_m3'] / master['Total_Withdrawal_FAO_10e9_m3']) * 100).round(2)
master['Mun_Share_Pct'] = ((master['Mun_Withdrawal_10e9_m3'] / master['Total_Withdrawal_FAO_10e9_m3']) * 100).round(2)

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


# 7. Final Column Selection & Export
final_cols = [
    'm49', 'ISO3_Code', 'Country', 'Year',
    'Renewable_Freshwater_10e9_m3', 'Freshwater_Abstracted_UNSD_10e9_m3',
]