"""
Rebuild of the demographic and walk-in analyses for the DMV coverage paper.

Fixes four things relative to the committed state of the repository:

  (1) walk-in filtration used a 166-entry weight vector (the full list minus
      Alturas) against a 167-office distance matrix;
  (2) the income table in the draft could not be regenerated from committed
      code (contingency_table_script_income.py reads a file not in the repo);
  (3) the race table in the draft has six Hispanic-exclusive categories that
      no committed file produces; the underlying data is race-alone with
      Hispanic as a separate overlapping column;
  (4) three different ZIP universes were in use across the outputs.

Run:  python3 rebuild_analysis.py
Writes: rebuilt/*.csv, rebuilt/summary.txt
"""

import ast
import os

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, mannwhitneyu

import gudhi

OUT = "rebuilt"
os.makedirs(OUT, exist_ok=True)

ZIP_LO, ZIP_HI = 90001, 96162

log_lines = []


def log(s=""):
    print(s)
    log_lines.append(str(s))


# ---------------------------------------------------------------------------
# (4) ONE ZIP UNIVERSE
# ---------------------------------------------------------------------------
# Canonical source for coverage status is the triangle-intersection mapping.
# The universe is every ZCTA in the California range that appears in BOTH the
# mapping and the demographic file being used, so income and race are computed
# on the same set of ZIPs.

mapping = pd.read_csv(
    "pre-processing/output/zip_underserved_mapping.csv", dtype={"ZIP_CODE": str}
)
mapping["ZIP_CODE"] = mapping["ZIP_CODE"].str.zfill(5)
mapping["zipnum"] = pd.to_numeric(mapping["ZIP_CODE"], errors="coerce")
mapping = mapping[mapping.zipnum.between(ZIP_LO, ZIP_HI)].copy()
mapping["underserved"] = mapping.STATUS.eq("UNDERSERVED")

log("=" * 72)
log("ZIP UNIVERSE")
log("=" * 72)
log(f"ZCTAs in mapping, range {ZIP_LO}-{ZIP_HI}: {len(mapping):,}")
log(f"  underserved:     {int(mapping.underserved.sum()):,}")
log(f"  not underserved: {int((~mapping.underserved).sum()):,}")

status = mapping.set_index("ZIP_CODE").underserved

# Strict intersection: the income and race tables must be computed on the same
# ZCTAs, or the two "% underserved" baselines are not comparable.
_inc_ids = set(
    pd.read_csv("HH_Cali_Income_Data_Updated.csv", low_memory=False, usecols=["NAME"])
    .NAME.str.extract(r"ZCTA5\s+(\d{5})")[0]
    .dropna()
)
_race_ids = set(
    pd.read_csv("california_race_with_other_and_hispanic.csv", dtype={"ZIP": str})
    .ZIP.str.zfill(5)
)
universe = sorted(set(status.index) & _inc_ids & _race_ids)
status = status.loc[universe]

log(f"common to mapping + income + race:            {len(status):,}")
log(f"  underserved:     {int(status.sum()):,}")
log(f"  not underserved: {int((~status).sum()):,}")


# ---------------------------------------------------------------------------
# (2) INCOME TABLE, regenerated from HH_Cali_Income_Data_Updated.csv
# ---------------------------------------------------------------------------
BRACKETS = [
    ("<$10K", "S1901_C01_002E"),
    ("$10K-$15K", "S1901_C01_003E"),
    ("$15K-$25K", "S1901_C01_004E"),
    ("$25K-$35K", "S1901_C01_005E"),
    ("$35K-$50K", "S1901_C01_006E"),
    ("$50K-$75K", "S1901_C01_007E"),
    ("$75K-$100K", "S1901_C01_008E"),
    ("$100K-$150K", "S1901_C01_009E"),
    ("$150K-$200K", "S1901_C01_010E"),
    ("$200K+", "S1901_C01_011E"),
]

inc = pd.read_csv("HH_Cali_Income_Data_Updated.csv", low_memory=False)
inc = inc.iloc[1:].copy()  # drop the human-readable header row
inc["ZIP_CODE"] = inc.NAME.str.extract(r"ZCTA5\s+(\d{5})")
inc["total_hh"] = pd.to_numeric(inc["S1901_C01_001E"], errors="coerce")

# S1901 publishes each bracket as a PERCENT of households; convert to counts,
# which is the method the draft describes.
for label, col in BRACKETS:
    pct = pd.to_numeric(inc[col], errors="coerce")
    inc[label] = pct / 100.0 * inc.total_hh

inc = inc.dropna(subset=["ZIP_CODE"])
inc["underserved"] = inc.ZIP_CODE.map(status)
inc_u = inc.dropna(subset=["underserved"]).copy()
inc_u["underserved"] = inc_u.underserved.astype(bool)

log()
log("=" * 72)
log("INCOME")
log("=" * 72)
log(f"ZCTAs matched to income data: {len(inc_u):,} "
    f"({int(inc_u.underserved.sum()):,} underserved)")

labels = [b[0] for b in BRACKETS]
tab = inc_u.groupby("underserved")[labels].sum().round(0).astype(np.int64)
tab.index = ["Not underserved", "Underserved"]
income_table = tab.T
income_table["% underserved"] = (
    100 * income_table["Underserved"]
    / (income_table["Underserved"] + income_table["Not underserved"])
).round(2)

obs = tab.values
chi2, p, dof, exp = chi2_contingency(obs)
N = obs.sum()
V = np.sqrt(chi2 / N / (min(obs.shape) - 1))
resid = (obs - exp) / np.sqrt(exp)
income_table["Pearson residual"] = resid[1].round(2)

log(income_table.to_string())
log()
log(f"chi2({dof}) = {chi2:,.2f}   p = {p:.3g}   N = {N:,}   Cramer's V = {V:.4f}")

baseline = 100 * obs[1].sum() / N
log(f"baseline share of households in an underserved ZIP: {baseline:.2f}%")

# ZIP-level robustness check (this is the test the draft does not report)
med = pd.to_numeric(inc_u["S1901_C01_012E"], errors="coerce")
inc_u = inc_u.assign(median_income=med).dropna(subset=["median_income"])
a = inc_u.loc[inc_u.underserved, "median_income"]
b = inc_u.loc[~inc_u.underserved, "median_income"]
u, pu = mannwhitneyu(a, b, alternative="two-sided")
log()
log("ZIP-level robustness check (Mann-Whitney U on ZCTA median income):")
log(f"  underserved median:     ${a.median():,.0f}  (n = {len(a):,})")
log(f"  not underserved median: ${b.median():,.0f}  (n = {len(b):,})")
log(f"  U = {u:,.0f}   p = {pu:.4g}")

income_table.to_csv(f"{OUT}/income_table.csv")


# ---------------------------------------------------------------------------
# (3) RACE TABLE, race-alone categories with Hispanic reported separately
# ---------------------------------------------------------------------------
RACE = [
    "White",
    "Black or African American",
    "Asian",
    "American Indian and Alaska Native",
    "Native Hawaiian and Other Pacific Islander",
    "Two or More Races",
    "Other Race",
]

race = pd.read_csv("california_race_with_other_and_hispanic.csv", dtype={"ZIP": str})
race["ZIP"] = race.ZIP.str.zfill(5)
race["underserved"] = race.ZIP.map(status)
race_u = race.dropna(subset=["underserved"]).copy()
race_u["underserved"] = race_u.underserved.astype(bool)

log()
log("=" * 72)
log("RACE (race alone; Hispanic origin reported separately, see note)")
log("=" * 72)
log(f"ZCTAs matched to race data: {len(race_u):,} "
    f"({int(race_u.underserved.sum()):,} underserved)")

# sanity: race-alone categories partition the Total, Hispanic overlaps them
chk = (race_u[RACE].sum(axis=1) - race_u["Total"]).abs().max()
log(f"max |sum(race alone) - Total| across ZCTAs: {chk:.0f}  "
    "(0 confirms race-alone partition; Hispanic is an overlapping column)")

g = race_u.groupby("underserved")[RACE].sum().astype(np.int64)
g.index = ["Not underserved", "Underserved"]
race_table = g.T
race_table["% underserved"] = (
    100 * race_table["Underserved"]
    / (race_table["Underserved"] + race_table["Not underserved"])
).round(2)

obs_r = g.values
chi2r, pr, dofr, expr = chi2_contingency(obs_r)
Nr = obs_r.sum()
Vr = np.sqrt(chi2r / Nr / (min(obs_r.shape) - 1))
race_table["Pearson residual"] = ((obs_r - expr) / np.sqrt(expr))[1].round(2)

log(race_table.to_string())
log()
log(f"chi2({dofr}) = {chi2r:,.2f}   p = {pr:.3g}   N = {Nr:,}   Cramer's V = {Vr:.4f}")
log(f"baseline share of residents in an underserved ZIP: "
    f"{100 * obs_r[1].sum() / Nr:.2f}%")

# Hispanic origin, as its own 2x2 against the balance of the population
h_u = int(race_u.loc[race_u.underserved, "Hispanic"].sum())
h_n = int(race_u.loc[~race_u.underserved, "Hispanic"].sum())
t_u = int(race_u.loc[race_u.underserved, "Total"].sum())
t_n = int(race_u.loc[~race_u.underserved, "Total"].sum())
hisp = np.array([[h_n, t_n - h_n], [h_u, t_u - h_u]])
chi2h, ph, dofh, exph = chi2_contingency(hisp)
Vh = np.sqrt(chi2h / hisp.sum() / (min(hisp.shape) - 1))
log()
log("Hispanic origin (any race), separate 2x2 against non-Hispanic:")
log(f"  Hispanic in underserved ZIPs:     {h_u:,} of {h_u + h_n:,} "
    f"({100 * h_u / (h_u + h_n):.2f}%)")
log(f"  non-Hispanic in underserved ZIPs: {t_u - h_u:,} of "
    f"{(t_u - h_u) + (t_n - h_n):,} "
    f"({100 * (t_u - h_u) / ((t_u - h_u) + (t_n - h_n)):.2f}%)")
log(f"  chi2({dofh}) = {chi2h:,.2f}   p = {ph:.3g}   Cramer's V = {Vh:.4f}")

race_table.to_csv(f"{OUT}/race_table.csv")


# ---------------------------------------------------------------------------
# (1) WALK-IN FILTRATION with the correct 167-entry weight vector
# ---------------------------------------------------------------------------
names = pd.read_csv("dmv_Symmetric_Distance_Matrix.csv", index_col=0).columns.tolist()
d = np.load("dmv_d_matrix.npy")
details = (
    pd.read_csv("pre-processing/output/dmv_offices_details.csv")
    .set_index("office_name")
    .reindex(names)
)

w_appt = np.loadtxt("dmv_waits.csv")
w_walk = details["walkin_wait_minutes"].to_numpy(dtype=float)
assert len(w_walk) == len(names) == d.shape[0] == 167
assert not np.isnan(w_walk).any()


def filtration(d, w):
    """Weighted VR: simplex enters at max over pairs of (d + w_i + w_j)/2."""
    n = len(w)
    D = d.copy()
    for i in range(n):
        for j in range(n):
            if i != j:
                D[i, j] = (d[i, j] + w[i] + w[j]) / 2
    st = gudhi.RipsComplex(distance_matrix=D.tolist()).create_simplex_tree(
        max_dimension=2
    )
    for i in range(n):
        st.assign_filtration([i], w[i])
    st.make_filtration_non_decreasing()
    st.persistence()
    feats = []
    for bs, ds in st.persistence_pairs():
        if len(bs) == 2 and len(ds) == 3:
            b, dd = st.filtration(bs), st.filtration(ds)
            feats.append((2 * b, 2 * dd, 2 * (dd - b), tuple(names[i] for i in ds)))
    feats.sort(key=lambda r: -r[2])
    return feats


log()
log("=" * 72)
log("WALK-IN FILTRATION (corrected weights)")
log("=" * 72)
log(f"walk-in weights: n = {len(w_walk)}, median = {np.median(w_walk):.1f}, "
    f"mean = {w_walk.mean():.1f}")
log(f"appointment weights: n = {len(w_appt)}, median = {np.median(w_appt):.1f}, "
    f"mean = {w_appt.mean():.1f}")
iu = np.triu_indices(167, 1)
log(f"median pairwise d: {np.median(d[iu]):.1f} minutes")

appt = filtration(d, w_appt)
walk = filtration(d, w_walk)
log()
log(f"finite 1-dimensional classes: appointment {len(appt)}, walk-in {len(walk)}")

shared = {f[3] for f in appt} & {f[3] for f in walk}
log(f"death simplices common to both filtrations: {len(shared)}")

rows = []
for k, (b, dd, pers, nm) in enumerate(walk, 1):
    rows.append(
        {
            "#": k,
            "Birth": round(b, 1),
            "Death": round(dd, 1),
            "Persistence": round(pers, 1),
            "Death simplex": ", ".join(nm),
            "Also in appointment": nm in {f[3] for f in appt},
        }
    )
walk_df = pd.DataFrame(rows)
log()
log(walk_df.to_string(index=False))
walk_df.to_csv(f"{OUT}/walkin_features.csv", index=False)

appt_df = pd.DataFrame(
    [
        {
            "#": k,
            "Birth": round(b, 1),
            "Death": round(dd, 1),
            "Persistence": round(pers, 1),
            "Death simplex": ", ".join(nm),
        }
        for k, (b, dd, pers, nm) in enumerate(appt, 1)
    ]
)
appt_df.to_csv(f"{OUT}/appointment_features.csv", index=False)

with open(f"{OUT}/summary.txt", "w") as f:
    f.write("\n".join(log_lines) + "\n")
print(f"\nwrote {OUT}/summary.txt and three CSVs")
