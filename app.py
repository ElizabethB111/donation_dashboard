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
    
    # --- keep numeric FIPS codes so they match the topojson ----------------------

    state_id = {s.abbr: int(s.fips) for s in us.states.STATES}   # ints: 1, 2, 4, …
    df["state_fips"] = df["State"].map(state_id).astype("Int64")  # nullable int


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

# right after you build df_filt
state_totals = (
    df_filt.groupby("state_fips", as_index=False)["Gift Amount"].sum()
           .rename(columns={"Gift Amount": "total_gift"})
)

# ---------- SELECTION DEFINITIONS --------------------------------------------
state_select       = alt.selection_point(fields=["state_fips"], toggle=False, empty="all")
brush              = alt.selection_interval(encodings=["x"])
subcategory_select = alt.selection_point(fields=["Allocation Subcategory"],
                                         toggle="event", empty="all")

# ---------- CHOROPLETH MAP ---------------------------------------------------
states = alt.topo_feature(data.us_10m.url, "states")
st.write(state_totals.head())
map_chart = (
    alt.Chart(states)
    .mark_geoshape(stroke="white", strokeWidth=0.5)
    .encode(
        color=alt.condition(
            state_select,
            alt.Color(
                "total_gift:Q",                       # ← no sum(), just the field
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
        lookup="id",                      # int IDs from the topojson
        from_=alt.LookupData(
            state_totals,                 # 1 row per state
            key="state_fips",             # int keys too
            fields=["total_gift"]
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
    .add_params(state_select, brush)
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
    .add_params(state_select)
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
    .add_params(state_select, subcategory_select)
    .properties(width=380, height=400)
)
st.text("✅ bar sub built")          # temporary breadcrumb

upper  = alt.hconcat(map_chart, line_chart).resolve_scale(color="independent")
lower  = alt.hconcat(bar_college, bar_sub)
layout = alt.vconcat(upper, lower)

st.altair_chart(layout, use_container_width=True)



# ---- test one chart at a time ----
# st.altair_chart(map_chart,    use_container_width=True)   # map only
# st.altair_chart(line_chart,   use_container_width=True)   # line only
# st.altair_chart(bar_college,  use_container_width=True)   # college bars
# st.altair_chart(bar_sub,      use_container_width=True)   # sub-category bars


