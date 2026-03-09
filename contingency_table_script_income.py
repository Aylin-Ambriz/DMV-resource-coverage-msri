import pandas as pd

# ── 1. Load data ──────────────────────────────────────────────────────────────
# Income CSV has two header rows; row 0 = codes, row 1 = labels. Use row 1 as header.
income_raw = pd.read_csv("Cali_Income_Data.csv", header=1, dtype=str)
underserved_df = pd.read_csv("pre-processing/output/zip_underserved_mapping.csv", dtype=str)
# ── 2. Extract the 10 Household income bracket columns (Estimate only) ────────
# The readable labels in row 1 look like:
#   "Estimate!!Households!!Total!!Less than $10,000"
#   "Estimate!!Households!!Total!!$10,000 to $14,999"  … etc.
# We want every column whose name starts with "Estimate!!Households!!Total!!"
# EXCEPT the plain total (no bracket suffix).

bracket_cols = [
    c for c in income_raw.columns
    if c.startswith("Estimate!!Households!!Total!!")
]

# Friendly short names for the contingency table columns
friendly_names = {
    "Estimate!!Households!!Total!!Less than $10,000":   "< $10K",
    "Estimate!!Households!!Total!!$10,000 to $14,999":  "$10K–$15K",
    "Estimate!!Households!!Total!!$15,000 to $24,999":  "$15K–$25K",
    "Estimate!!Households!!Total!!$25,000 to $34,999":  "$25K–$35K",
    "Estimate!!Households!!Total!!$35,000 to $49,999":  "$35K–$50K",
    "Estimate!!Households!!Total!!$50,000 to $74,999":  "$50K–$75K",
    "Estimate!!Households!!Total!!$75,000 to $99,999":  "$75K–$100K",
    "Estimate!!Households!!Total!!$100,000 to $149,999":"$100K–$150K",
    "Estimate!!Households!!Total!!$150,000 to $199,999":"$150K–$200K",
    "Estimate!!Households!!Total!!$200,000 or more":    "$200K+",
}

# ── 3. Parse zip codes from the Geography / GEO_ID column ────────────────────
# The Geography column contains values like "8600000US90001"; last 5 chars = ZIP.
income_raw["ZIP_CODE"] = income_raw["Geography"].str[-5:]

# Keep only the bracket columns + ZIP
income = (
    income_raw[["ZIP_CODE"] + bracket_cols]
    .rename(columns=friendly_names)
    .copy()
)

# Convert bracket columns to numeric (non-numeric → NaN → 0)
for col in friendly_names.values():
    income[col] = pd.to_numeric(income[col], errors="coerce").fillna(0)

# ── 4. Merge with underserved status ─────────────────────────────────────────
underserved_df["ZIP_CODE"] = underserved_df["ZIP_CODE"].str.strip().str.zfill(5)
income["ZIP_CODE"] = income["ZIP_CODE"].str.strip().str.zfill(5)

merged = income.merge(underserved_df[["ZIP_CODE", "STATUS"]], on="ZIP_CODE", how="inner")

# Normalise status labels
merged["STATUS"] = merged["STATUS"].str.upper().str.strip()
merged["STATUS"] = merged["STATUS"].map(
    {"UNDERSERVED": "Underserved", "NOT UNDERSERVED": "Not Underserved"}
)
merged = merged.dropna(subset=["STATUS"])

# ── 5. Build contingency table ────────────────────────────────────────────────
income_cols = list(friendly_names.values())

contingency = (
    merged.groupby("STATUS")[income_cols]
    .sum()
    .astype(int)
)

# Ensure row order: Underserved first
contingency = contingency.reindex(["Underserved", "Not Underserved"])

# Add a row total column
contingency["TOTAL"] = contingency.sum(axis=1)

print("Contingency Table — Estimated Households by Income Bracket & Underserved Status")
print("=" * 90)
print(contingency.to_string())
print()
print(f"Zip codes matched: {len(merged)}")
print(f"  Underserved    : {(merged['STATUS'] == 'Underserved').sum()}")
print(f"  Not Underserved: {(merged['STATUS'] == 'Not Underserved').sum()}")

# ── 6. Save to CSV ────────────────────────────────────────────────────────────
out_path = "contingency_table_income.csv"
contingency.to_csv(out_path)
print(f"\nSaved → {out_path}")