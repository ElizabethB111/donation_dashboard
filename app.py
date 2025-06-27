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

    # --- map State abbreviations to zero-padded FIPS strings ----------------
    state_id = {s.abbr: s.fips for s in us.states.STATES}  # e.g. "CA" -> "06"
    df["state_fips"] = df["State"].map(state_id)
    df = df.dropna(subset=["state_fips"])   # drop if state_fips is NaN (unknown state)
    # Keep as string, zero-padded 2-digit
    df["state_fips"] = df["state_fips"].astype(str).str.zfill(2)

    return df

df = load_data()

# Load topojson IDs for states
url = data.us_10m.url
with urllib.request.urlopen(url) as response:
    topojson_data = json.load(response)

topo_ids = {str(feature["id"]).zfill(2) for feature in topojson_data["objects"]["states"]["geometries"]}

# Filters
st.sidebar.header("Filters")
st.sidebar.caption(f"Altair version: {alt.__version__}")

col_opts = ["All"] + sorted(df["College"].unique())
mot_opts = ["All"] + sorted(df["Gift Allocation"].unique())

col_pick = st.sidebar.selectbox("College", col_opts, index=0)
mot_pick = st.sidebar.selectbox("Motivation (Gift Allocation)", mot_opts, index=0)

mask = pd.Series(True, index=df.index)

if col_pick != "All" and col_pick in df["College"].unique():
    mask &= df["College"] == col_pick

if mot_pick != "All" and mot_pick in df["Gift Allocation"].unique():
    mask &= df["Gift Allocation"] == mot_pick

df_filt = df[mask]
st.write("Filtered rows:", len(df_filt))
st.write("Filtered df_filt sample:", df_filt.head())
st.write("Gift Amount summary:", df_filt["Gift Amount"].describe())

# Aggregate gift sums by state
state_totals = (
    df_filt.groupby("state_fips", as_index=False)["Gift Amount"].sum()
           .rename(columns={"Gift Amount": "total_gift"})
)

# Ensure all topojson states are present in state_totals, fill missing with 0
all_states = pd.DataFrame({"state_fips": list(topo_ids)})
state_totals = all_states.merge(state_totals, on="state_fips", how="left")
state_totals["total_gift"] = state_totals["total_gift"].fillna(0)

# Debug info
st.sidebar.caption(f"Rows after cleaning: {len(df):,}  |  Gift $ min–max: "
                   f"{df['Gift Amount'].min():,.0f} – {df['Gift Amount'].max():,.0f}")
st.write("State FIPS codes in data:", sorted(state_totals["state_fips"].unique()))
st.write("Sample state totals:", state_totals.head())

# ---------- SELECTION DEFINITIONS --------------------------------------------
state_select       = alt.selection_point(fields=["state_fips"], toggle=False, empty="all")
brush              = alt.selection_interval(encodings=["x"])
subcategory_select = alt.selection_point(fields=["Allocation Subcategory"],
                                         toggle="event", empty="all")

# ---------- CHOROPLETH MAP ---------------------------------------------------
states = alt.topo_feature(data.us_10m.url, "states")

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
        from_=alt.LookupData(
            state_totals,
            key="state_fips",
            fields=["total_gift"]
        )
    )
    .add_params(state_select)
    .project(type="albersUsa")
    .properties(width=380, height=250)
)

# ---------- LINE: GIFTS BY YEAR ----------------------------------------------
line_chart = (
    alt.Chart(df_filt)
    #.transform_filter(state_select)
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
    .properties(width=380, height=250)
)

# ---------- BAR: TOTAL BY COLLEGE --------------------------------------------
bar_college = (
    alt.Chart(df_filt)
    #.transform_filter(state_select)
    .mark_bar()
    .encode(
        y=alt.Y("College:N", sort="-x", title="College"),
        x=alt.X("sum(Gift Amount):Q", title="Total Gifts ($)"),
        tooltip=[
            alt.Tooltip("College:N", title="College"),
            alt.Tooltip("sum(Gift Amount):Q", title="Total Gifts ($)", format=",.0f")
        ]
    )
    .add_params(state_select)
    .properties(width=380, height=400)
)

# ---------- BAR: TOTAL BY SUB-CATEGORY ---------------------------------------
bar_sub = (
    alt.Chart(df_filt)
    #.transform_filter(state_select)
    .transform_filter(brush)
    .mark_bar()
    .encode(
        y=alt.Y("Allocation Subcategory:N", sort="-x", title="Allocation Sub-category"),
        x=alt.X("sum(Gift Amount):Q", title="Total Gifts ($)"),
        color=alt.condition(
            subcategory_select, alt.value("#1f77b4"), alt.value("lightgray")
        ),
        tooltip=[
            alt.Tooltip("Allocation Subcategory:N", title="Sub-category"),
            alt.Tooltip("sum(Gift Amount):Q", title="Total Gifts ($)", format=",.0f")
        ]
    )
    .add_params(state_select, subcategory_select)
    .properties(width=380, height=400)
)

upper = alt.hconcat(map_chart, line_chart).resolve_scale(color="independent")
lower = alt.hconcat(bar_college, bar_sub)
layout = alt.vconcat(upper, lower)

st.altair_chart(layout, use_container_width=True)



