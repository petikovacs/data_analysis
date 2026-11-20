import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    "1_agri_owid": RAW_DIR / "agricultural-water-withdrawals.csv",
    "2_fao_sectors": RAW_DIR / "aquastat_sector_withdrawal.csv",
    "3_sdg_stress": RAW_DIR / "sdg_water_stress.csv.xlsx", 
    "4_un_abstracted": RAW_DIR / "Freshwater abstracted.xlsx",
    "5_un_renewable": RAW_DIR / "Renewable freshwater resources.xlsx"
}

report_lines = []
anomalies_records = []

def log(text=""):
    print(text)
    report_lines.append(str(text))

log("=" * 80)
log("SCIENTIFIC DATA QUALITY AUDIT & PROFILING REPORT")
log("=" * 80)

def audit_tabular_file(dataset_name, filepath, entity_col, code_col, year_col, val_col, unit_info, symbol_col=None, group_col=None):
    log(f"\n{'#'*75}\nAUDITING DATASET: {dataset_name} | FILE: {filepath.name}\n{'#'*75}")
    if not filepath.exists():
        log(f"[ERROR] File not found at: {filepath}")
        return
    
    df = pd.read_excel(filepath) if filepath.suffix == '.xlsx' else pd.read_csv(filepath)
    
    log(f"1. Dimensions: {len(df)} rows x {len(df.columns)} columns")
    log(f"2. Columns: {list(df.columns)}")
    if unit_info in df.columns:
        log(f"3. Measurement Units: {df[unit_info].unique().tolist()}")
    else:
        log(f"3. Measurement Unit: {unit_info}")
        
    nulls = df.isnull().sum()
    log(f"4. Missing Values:\n   {nulls[nulls > 0].to_dict() if nulls.sum() > 0 else 'None (0 missing)'}")
    
    subset_cols = [c for c in [code_col, entity_col, year_col, group_col] if c and c in df.columns]
    dups = df.duplicated(subset=subset_cols).sum()
    log(f"5. Duplicate Rows based on keys {subset_cols}: {dups}")
    
    years = sorted(df[year_col].dropna().unique())
    expected_years = set(range(int(min(years)), int(max(years)) + 1))
    missing_years = sorted(list(expected_years - set(years)))
    log(f"6. Time Range: {min(years)} to {max(years)} ({len(years)} unique years) | Global Missing Years: {missing_years if missing_years else 'None'}")
    
    if code_col in df.columns:
        if df[code_col].dtype == object:
            aggs = df[df[code_col].isna() | df[code_col].astype(str).str.startswith('OWID_')][entity_col].unique()
            log(f"7. Regional/Non-Country Aggregates detected ({len(aggs)}): {list(aggs[:8])} ...")
        else:
            log(f"7. Unique Area Codes in '{code_col}': {df[code_col].nunique()}")

    if symbol_col and symbol_col in df.columns:
        log(f"8. Symbols/Flags ('{symbol_col}'): {df[symbol_col].value_counts(dropna=False).to_dict()}")
        
    if group_col and group_col in df.columns:
        log(f"9. Categories ('{group_col}'): {df[group_col].unique().tolist()}")

    df['num_val'] = pd.to_numeric(df[val_col], errors='coerce')
    vals = df['num_val'].dropna()
    neg_df = df[df['num_val'] < 0]
    zero_df = df[df['num_val'] == 0]
    
    Q1, Q3 = vals.quantile(0.25), vals.quantile(0.75)
    IQR = Q3 - Q1
    outliers_df = df[(df['num_val'] < (Q1 - 1.5 * IQR)) | (df['num_val'] > (Q3 + 1.5 * IQR))]
    
    log(f"10. Numerical Summary for '{val_col}':")
    log(f"    - Min: {vals.min():.4f} | Median: {vals.median():.4f} | Max: {vals.max():.4f}")
    log(f"    - Negative values (less than 0): {len(neg_df)} rows | Countries: {neg_df[entity_col].unique().tolist()}")
    log(f"    - Zero values (equal to 0): {len(zero_df)} rows | Countries count: {zero_df[entity_col].nunique()}")
    log(f"    - Statistical Outliers (IQR): {len(outliers_df)} rows")

    for _, row in neg_df.iterrows():
        anomalies_records.append({
            "Dataset": dataset_name, "Country": row[entity_col], "Year": row[year_col],
            "Issue_Type": "Negative Value", "Value": row['num_val'], "Details": row.get(group_col, "")
        })

def audit_unsd_excel(dataset_name, filepath):
    log(f"\n{'#'*75}\nAUDITING UNSD EXCEL DATASET: {dataset_name} | FILE: {filepath.name}\n{'#'*75}")
    if not filepath.exists():
        log(f"[ERROR] File not found at: {filepath}")
        return
        
    xl = pd.ExcelFile(filepath)
    target_sheet = None
    header_idx = None
    
    for sheet in xl.sheet_names:
        df_temp = xl.parse(sheet, header=None)
        mask = df_temp.apply(lambda col: col.astype(str).str.strip() == 'CountryID').any(axis=1)
        if mask.any():
            target_sheet = sheet
            header_idx = int(mask.idxmax())
            break
            
    if target_sheet is None:
        log(f"[WARNING] 'CountryID' not found in sheets {xl.sheet_names}. Skipping.")
        return

    df_temp = xl.parse(target_sheet, header=None)
    unit_info = "Million cubic metres (Million m3)"
    for r in range(header_idx):
        row_str = " ".join(df_temp.iloc[r].dropna().astype(str).tolist())
        if "Unit:" in row_str:
            unit_info = row_str.strip()
            break

    log(f"1. Sheet Used: '{target_sheet}' | Measurement Unit: {unit_info}")
    log(f"2. Metadata Header Rows Skipped: {header_idx} rows")
    
    df_raw = xl.parse(target_sheet, skiprows=header_idx)
    
    is_country = pd.to_numeric(df_raw['CountryID'], errors='coerce').notna() | df_raw['Country'].astype(str).str.contains('Kosovo', na=False)
    df_data = df_raw[is_country].copy()
    df_notes = df_raw[~is_country].dropna(how='all').copy()
    
    notes_clean = df_notes.iloc[:, :2].dropna(how='all')
    notes_clean.columns = ['Footnote_Code', 'Description']
    notes_clean = notes_clean[notes_clean['Footnote_Code'] != 'Footnote number']
    notes_path = REPORTS_DIR / f"{dataset_name}_footnotes_dictionary.csv"
    notes_clean.to_csv(notes_path, index=False, encoding='utf-8-sig')
    log(f"3. Footnotes Extracted: {len(notes_clean)} definitions saved to -> {notes_path.name}")
    
    log(f"4. Data Sources (U=UNSD, E=Eurostat, O=OECD): {df_data['Source'].value_counts(dropna=False).to_dict()}")
    log(f"5. Total Countries/Areas: {len(df_data)} | Duplicate Countries: {df_data['Country'].duplicated().sum()}")
    
    year_cols = [c for c in df_data.columns if str(c).strip().isdigit() and 2000 <= int(str(c).strip()) <= 2025]
    df_years = df_data[year_cols].replace('...', np.nan).apply(pd.to_numeric, errors='coerce')
    
    total_cells = df_years.size
    missing_cells = df_years.isna().sum().sum()
    log(f"6. Missing Values ('...'): {missing_cells} out of {total_cells} cells ({missing_cells/total_cells*100:.1f}%)")
    
    all_missing_countries = df_data.loc[df_years.isna().all(axis=1), 'Country'].tolist()
    log(f"7. Countries with 100% Missing Data ({len(all_missing_countries)}): {all_missing_countries}")
    
    neg_mask = (df_years < 0).any(axis=1)
    zero_mask = (df_years == 0).any(axis=1)
    log(f"8. Countries with Negative Values (less than 0): {df_data.loc[neg_mask, 'Country'].tolist()}")
    log(f"9. Countries with Zero Values (equal to 0): {df_data.loc[zero_mask, 'Country'].tolist()}")
    
    for country in all_missing_countries:
        anomalies_records.append({
            "Dataset": dataset_name, "Country": country, "Year": "All (2001-2024)",
            "Issue_Type": "100% Missing Data", "Value": np.nan, "Details": "No reported values across entire period"
        })
        
    for idx in df_data[neg_mask].index:
        country = df_data.loc[idx, 'Country']
        for y in year_cols:
            val = df_years.loc[idx, y]
            if pd.notna(val) and val < 0:
                anomalies_records.append({
                    "Dataset": dataset_name, "Country": country, "Year": y,
                    "Issue_Type": "Negative Value", "Value": val, "Details": "Negative water balance"
                })

    fn_cols = [c for c in df_data.columns if 'Footnote' in str(c)]
    df_data['All_Footnotes'] = df_data[fn_cols].apply(
        lambda r: ', '.join(sorted(set(str(x).strip() for x in r if pd.notna(x) and str(x).strip() != ''))), axis=1
    )
    country_fn_summary = df_data[df_data['All_Footnotes'] != ''][['CountryID', 'Country', 'Source', 'All_Footnotes']]
    log(f"10. Countries with Methodological Footnotes: {len(country_fn_summary)} out of {len(df_data)}")
    country_fn_summary.to_csv(REPORTS_DIR / f"{dataset_name}_countries_footnotes.csv", index=False, encoding='utf-8-sig')

    country_fn_summary = df_data[df_data['All_Footnotes'] != ''][['CountryID', 'Country', 'Source', 'All_Footnotes']]
    log(f"10. Countries with Methodological Footnotes: {len(country_fn_summary)} out of {len(df_data)}")
    country_fn_summary.to_csv(REPORTS_DIR / f"{dataset_name}_countries_footnotes.csv", index=False, encoding='utf-8-sig')

audit_tabular_file("1_Agriculture_OWID", FILES["1_agri_owid"], "Entity", "Code", "Year", "Agricultural water withdrawal", "Cubic metres per year (m3/year)")
audit_tabular_file("2_FAO_Sectors", FILES["2_fao_sectors"], "Area", "m49", "Year", "Value", "Unit", symbol_col="Symbol", group_col="Variable")
audit_tabular_file("3_SDG_Water_Stress", FILES["3_sdg_stress"], "AREA", "REF_AREA", "TIME_PERIOD", "OBS_VALUE", "UNIT_MEASURE", symbol_col="OBS_STATUS", group_col="ACTIVITY")

audit_unsd_excel("4_UN_Freshwater_Abstracted", FILES["4_un_abstracted"])
audit_unsd_excel("5_UN_Renewable_Resources", FILES["5_un_renewable"])

if anomalies_records:
    pd.DataFrame(anomalies_records).to_csv(REPORTS_DIR / "02_Anomalies_and_Missing_Records.csv", index=False, encoding='utf-8-sig')

with open(REPORTS_DIR / "01_Full_Data_Audit_Report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

log(f"\n[SUCCESS] Audit completed! Check the 'reports' folder.")
