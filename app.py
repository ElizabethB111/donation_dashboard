########################
# app.py  –  Streamlit #
########################
import streamlit as st
import pandas as pd
import altair as alt
import json
import urllib.request

# --- FIX #2: lift Altair’s 5 000-row cap (do this once) ----------------------
alt.data_transformers.disable_max_rows()

from vega_datasets import data
import us

states = alt.topo_feature(data.us_10m.url, "states")

st.set_page_config(
    page_title="University Donor Dashboard",
    layout="wide"
)

@st.cache_data
def load_data():
    df = pd.read_csv("university-donations.csv")

    # --- clean dates ---------------------------------------------------------
    df["Gift Date"] = pd.to_datetime(df["Gift Date"], errors="coerce")
    df = df.dropna(subset=["Gift Date"])

    # 🔹 strip $ and commas, coerce to float
    df["Gift Amount"] = (
        pd.to_numeric(
            df["Gift Amount"].astype(str).str.replace(r"[^\d\-.]", "", regex=True),
            errors="coerce")
        )
    df = df.dropna(subset=["Gift Amount"])   # drop any non-numeric rows

    # --- add calendar helpers -----------------------------------------------
    df["Year"]      = df["Gift Date"].dt.year
    df["YearMonth"] = df["Gift Date"].dt.to_period("M").astype(str)

    # --- FIPS codes as zero-padded 2-digit strings to match topojson -----------
    state_id = {s.abbr: s.fips for s in us.states.STATES}  # e.g. 'CA' → '06'
    df["state_fips"] = df["State"].map(state_id)
    df = df.dropna(subset=["state_fips"])  # drop rows with missing states
    df["state_fips"] = df["state_fips"].astype(str).str.zfill(2)  # ensure zero-padding

    return df

df = load_data()
st.sidebar.caption(
    f"Rows after cleaning: {len(df):,}  |  Gift $ min–max: "
    f"{df['Gift Amount'].min():,.0f} – {df['Gift Amount'].max():,.0f}"
)

st.write("Data type of df['state_fips']:", df["state_fips"].dtype)
st.write("Sample values from df['state_fips']:", df["state_fips"].unique()[:10])

# ---------- SIDEBAR FILTERS --------------------------------------------------
st.sidebar.header("Filters")
st.sidebar.caption(f"Altair version: {alt.__version__}")
col_opts = ["All"] + sorted(df["College"].unique())
mot_opts = ["All"] + sorted(df["Gift Allocation"].unique())

col_pick = st.sidebar.selectbox("College", col_opts, index=0)
mot_pick = st.sidebar.selectbox("Motivation (Gift Allocation)", mot_opts, index=0)

mask = pd.Series(True, index=df.index)
if col_pick != "All":
    mask &= df["College"] == col_pick
if mot_pick != "All":
    mask &= df["Gift Allocation"] == mot_pick
df_filt = df[mask]

# Aggregate gifts by state_fips
state_totals = (
    df_filt.groupby("state_fips", as_index=False)["Gift Amount"].sum()
           .rename(columns={"Gift Amount": "total_gift"})
)

# Load topojson IDs for comparison
url = data.us_10m.url
with urllib.request.urlopen(url) as response:
    topojson_data = json.load(response)

topo_ids = {str(feature["id"]) for feature in topojson_data["objects"]["states"]["geometries"]}
df_state_fips = set(state_totals["state_fips"])

missing_in_topo = df_state_fips - topo_ids
missing_in_df = topo_ids - df_state_fips

st.write("State FIPS codes in data not in topojson:", missing_in_topo)
st.write("State IDs in topojson not in data:", missing_in_df)

# ---------- SELECTION DEFINITIONS --------------------------------------------
state_select       = alt.selection_point(fields=["state_fips"], toggle=False, empty="all")
brush              = alt.selection_interval(encodings=["x"])
subcategory_select = alt.selection_point(fields=["Allocation Subcategory"], toggle="event", empty="all")

# ---------- CHOROPLETH MAP ---------------------------------------------------
map_chart = (
    alt.Chart(states)
    .mark_geoshape(stroke="white", strokeWidth=0.5)
    .encode(
        color=alt.condition(
            state_select,
            alt.Color(
                "total_gift:Q",
                scale=alt.Scale(scheme="blues", domain=[0, None]),
                title="Total Gifts ($)"
            ),
            alt.value("lightgray")
        ),
        tooltip=[
            alt.Tooltip("total_gift:Q", title="Total Gifts ($)", format=",.0f")
        ]
    )
    .transform_lookup(
        lookup="id",
        from_=alt.LookupData(state_totals, key="state_fips", fields=["total_gift"])
    )
    .add_params(state_select)
    .project(type="albersUsa")
    .properties(width=380, height=250)
)

st.text("✅ map built")

# ---------- LINE: GIFTS BY YEAR ----------------------------------------------
line_chart = (
    alt.Chart(df_filt)
    .transform_filter(state_select)
    .mark_line(point=True)
    .encode(
        x=alt.X("Year:O", sort="ascending"),
        y=alt.Y("sum(Gift Amount):Q", title="Total Gifts ($)"),
        tooltip=[
            alt.Tooltip("Year:O", title="Year"),
            alt.Tooltip("sum(Gift Amount):Q", title="Total Gifts ($)", format=",.0f")
        ]
    )
    .add_params(state_select, brush)



