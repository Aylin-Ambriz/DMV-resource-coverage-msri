"""
Does the appointment/walk-in choice drive the income and race results?

The advisor's hypothesis is that underserved ZIPs skew higher-income because
the analysis is built on appointment wait times. This tests it directly: it
rebuilds the underserved ZIP set from the WALK-IN filtration's death simplices
(same geometry, same intersection rule, different vertex weights) and re-runs
both demographic tables.

Requires /tmp/zips/zip_poly.shp (unzip the ArcGIS layer in pre-processing/data).
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
from scipy.stats import chi2_contingency

import gudhi

ZIP_LO, ZIP_HI = 90001, 96162

names = pd.read_csv("dmv_Symmetric_Distance_Matrix.csv", index_col=0).columns.tolist()
d = np.load("dmv_d_matrix.npy")
det = (
    pd.read_csv("pre-processing/output/dmv_offices_details.csv")
    .set_index("office_name")
    .reindex(names)
)
w_appt = np.loadtxt("dmv_waits.csv")
w_walk = det["walkin_wait_minutes"].to_numpy(dtype=float)
lat = det["latitude"].to_numpy(dtype=float)
lon = det["longitude"].to_numpy(dtype=float)


def death_simplices(d, w):
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
    return [ds for bs, ds in st.persistence_pairs() if len(bs) == 2 and len(ds) == 3]


zips = gpd.read_file("/tmp/zips/zip_poly.shp").to_crs("EPSG:4326")
zips["ZIP_CODE"] = zips.ZIP_CODE.astype(str).str.zfill(5)
zips["zipnum"] = pd.to_numeric(zips.ZIP_CODE, errors="coerce")
zips = zips[zips.zipnum.between(ZIP_LO, ZIP_HI)].copy()


def underserved_set(simplices):
    tris = gpd.GeoDataFrame(
        geometry=[Polygon([(lon[i], lat[i]) for i in s]) for s in simplices],
        crs="EPSG:4326",
    )
    hit = gpd.sjoin(zips, tris, how="inner", predicate="intersects")
    return set(hit.ZIP_CODE.unique())


appt_set = underserved_set(death_simplices(d, w_appt))
walk_set = underserved_set(death_simplices(d, w_walk))

print(f"ZCTAs in range: {len(zips):,}")
print(f"underserved under appointment filtration: {len(appt_set):,}")
print(f"underserved under walk-in filtration:     {len(walk_set):,}")
print(f"in both: {len(appt_set & walk_set):,}   "
      f"appointment only: {len(appt_set - walk_set):,}   "
      f"walk-in only: {len(walk_set - appt_set):,}")

# ---- demographics under each labelling ------------------------------------
BR = [
    ("<$10K", "S1901_C01_002E"), ("$10K-$15K", "S1901_C01_003E"),
    ("$15K-$25K", "S1901_C01_004E"), ("$25K-$35K", "S1901_C01_005E"),
    ("$35K-$50K", "S1901_C01_006E"), ("$50K-$75K", "S1901_C01_007E"),
    ("$75K-$100K", "S1901_C01_008E"), ("$100K-$150K", "S1901_C01_009E"),
    ("$150K-$200K", "S1901_C01_010E"), ("$200K+", "S1901_C01_011E"),
]
inc = pd.read_csv("HH_Cali_Income_Data_Updated.csv", low_memory=False).iloc[1:].copy()
inc["ZIP_CODE"] = inc.NAME.str.extract(r"ZCTA5\s+(\d{5})")
tot = pd.to_numeric(inc["S1901_C01_001E"], errors="coerce")
for lab, col in BR:
    inc[lab] = pd.to_numeric(inc[col], errors="coerce") / 100.0 * tot
inc = inc.dropna(subset=["ZIP_CODE"])
inc = inc[inc.ZIP_CODE.isin(zips.ZIP_CODE)]

race = pd.read_csv("california_race_with_other_and_hispanic.csv", dtype={"ZIP": str})
race["ZIP"] = race.ZIP.str.zfill(5)
race = race[race.ZIP.isin(zips.ZIP_CODE)]
RACE = ["White", "Black or African American", "Asian",
        "American Indian and Alaska Native",
        "Native Hawaiian and Other Pacific Islander",
        "Two or More Races", "Other Race"]

for label, S in [("APPOINTMENT", appt_set), ("WALK-IN", walk_set)]:
    print("\n" + "=" * 68)
    print(label)
    print("=" * 68)

    u = inc.ZIP_CODE.isin(S)
    labs = [b[0] for b in BR]
    obs = np.vstack([inc.loc[~u, labs].sum().values, inc.loc[u, labs].sum().values])
    c, p, dof, _ = chi2_contingency(obs)
    N = obs.sum()
    pct = 100 * obs[1] / obs.sum(0)
    print(f"income:  chi2({dof}) = {c:,.1f}  V = {np.sqrt(c/N/(min(obs.shape)-1)):.4f}"
          f"  baseline {100*obs[1].sum()/N:.2f}%")
    print("  % of households underserved, lowest to highest bracket:")
    print("   " + "  ".join(f"{lab}:{v:.1f}" for lab, v in zip(labs, pct)))
    print(f"  spread bottom->top bracket: {pct[-1]-pct[0]:+.2f} pp")

    ur = race.ZIP.isin(S)
    obr = np.vstack([race.loc[~ur, RACE].sum().values, race.loc[ur, RACE].sum().values])
    cr, pr, dofr, _ = chi2_contingency(obr)
    Nr = obr.sum()
    pctr = 100 * obr[1] / obr.sum(0)
    print(f"race:    chi2({dofr}) = {cr:,.1f}  V = {np.sqrt(cr/Nr/(min(obr.shape)-1)):.4f}"
          f"  baseline {100*obr[1].sum()/Nr:.2f}%   p = {pr:.3g}")
    for lab, v in zip(RACE, pctr):
        print(f"    {lab:<46s} {v:6.2f}%")
    h_u = race.loc[ur, "Hispanic"].sum()
    h_a = race["Hispanic"].sum()
    print(f"    {'Hispanic (any race)':<46s} {100*h_u/h_a:6.2f}%")
