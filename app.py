########################
# app.py  –  Streamlit #
########################
import streamlit as st
import pandas as pd
import altair as alt

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

    # --- keep 2-digit string FIPS codes to join with topojson ---------------
    state_id            = {s.abbr: s.fips for s in us.states.STATES}
    df["state_fips"]    = df["State"].map(state_id).astype(str)

    return df

df = load_data()
st.sidebar.caption(f"Rows after cleaning: {len(df):,}  |  Gift $ min–max: "
                   f"{df['Gift Amount'].min():,.0f} – {df['Gift Amount'].max():,.0f}")
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
            alt.Color("sum(Gift Amount):Q",
                      scale=alt.Scale(scheme="blues",domain=[0, None]),
                      title="Total Gifts ($)"),
            alt.value("lightgray")
        ),
        tooltip=[
            alt.Tooltip("sum(Gift Amount):Q", title="Total Gifts ($)", format=",.0f"),
            alt.Tooltip("count():Q",          title="# Gifts")
        ]
    )
    .transform_lookup(
        lookup="id",
        from_=alt.LookupData(
            df_filt,
            key="state_fips",
            fields=["Gift Amount"]
        )
    )
    .add_params(state_select)
    .project(type="albersUsa")
    .properties(width=380, height=250)
)
st.text("✅ map built")          # temporary breadcrumb

# ---------- LINE: GIFTS BY YEAR ----------------------------------------------
line_chart = (
    alt.Chart(df_filt)
    .transform_filter(state_select)
    .mark_line(point=True)
    .encode(
        x=alt.X("Year:O", sort="ascending"),
        y=alt.Y("sum(Gift Amount):Q", title="Total Gifts ($)"),
        tooltip=[
            alt.Tooltip("Year:O",             title="Year"),
            alt.Tooltip("sum(Gift Amount):Q", title="Total Gifts ($)", format=",.0f")
        ]
    )
    .add_params(brush)
    .properties(width=380, height=250)
)
st.text("✅ line chart built")          # temporary breadcrumb

# ---------- BAR: TOTAL BY COLLEGE --------------------------------------------
bar_college = (
    alt.Chart(df_filt)
    .transform_filter(state_select)
    .mark_bar()
    .encode(
        y=alt.Y("College:N",           sort="-x", title="College"),
        x=alt.X("sum(Gift Amount):Q",  title="Total Gifts ($)"),
        tooltip=[
            alt.Tooltip("College:N",           title="College"),
            alt.Tooltip("sum(Gift Amount):Q",  title="Total Gifts ($)", format=",.0f")
        ]
    )
    .properties(width=380, height=400)
)
st.text("✅ bar built")          # temporary breadcrumb

# ---------- BAR: TOTAL BY SUB-CATEGORY ---------------------------------------
bar_sub = (
    alt.Chart(df_filt)
    .transform_filter(state_select)
    .transform_filter(brush)
    .mark_bar()
    .encode(
        y=alt.Y("Allocation Subcategory:N", sort="-x",
                title="Allocation Sub-category"),
        x=alt.X("sum(Gift Amount):Q", title="Total Gifts ($)"),
        color=alt.condition(
            subcategory_select, alt.value("#1f77b4"), alt.value("lightgray")
        ),
        tooltip=[
            alt.Tooltip("Allocation Subcategory:N", title="Sub-category"),
            alt.Tooltip("sum(Gift Amount):Q",       title="Total Gifts ($)", format=",.0f")
        ]
    )
    .add_params(subcategory_select)
    .properties(width=380, height=400)
)
st.text("✅ bar sub built")          # temporary breadcrumb

# ---------- LAYOUT -----------------------------------------------------------
upper  = alt.hconcat(map_chart, line_chart).resolve_scale(color="independent")
lower  = alt.hconcat(bar_college, bar_sub)
layout = alt.vconcat(upper, lower)

# st.altair_chart(layout, use_container_width=True)

# ---- test one chart at a time ----
# st.altair_chart(map_chart,    use_container_width=True)   # map only
# st.altair_chart(line_chart,   use_container_width=True)   # line only
# st.altair_chart(bar_college,  use_container_width=True)   # college bars
st.altair_chart(bar_sub,      use_container_width=True)   # sub-category bars


