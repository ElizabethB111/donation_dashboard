########################
# app.py – Streamlit   #
########################
import streamlit as st
import pandas as pd
import altair as alt
from vega_datasets import data
import us

# -------------------------------------------------
# PAGE CONFIG + TITLE
# -------------------------------------------------
st.set_page_config(page_title="University Donor Dashboard", layout="wide")
st.title("University Donor Dashboard")
alt.data_transformers.enable("default", max_rows=None)

# -------------------------------------------------
# DATA
# -------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("university-donations.csv")
    df["Gift Date"] = pd.to_datetime(
        df["Gift Date"],
        format="%m/%d/%y",
        errors="coerce"
    )
    df["Year"]      = df["Gift Date"].dt.year.astype("Int64")
    df["YearMonth"] = df["Gift Date"].dt.to_period("M").astype(str)

    # 2-letter state → FIPS
    state_id = {s.abbr: int(s.fips) for s in us.states.STATES}
    df["state_fips"] = df["State"].map(state_id)
    return df

df = load_data()
st.write("Loaded rows:", len(df))   # quick sanity check

# -------------------------------------------------
# SIDEBAR FILTERS
# -------------------------------------------------
st.sidebar.header("Filters")
col_opts = ["All"] + sorted(df["College"].dropna().unique())
mot_opts = ["All"] + sorted(df["Gift Allocation"].dropna().unique())

col_pick = st.sidebar.selectbox("College", col_opts, index=0)
mot_pick = st.sidebar.selectbox("Motivation (Gift Allocation)", mot_opts, index=0)

mask = pd.Series(True, index=df.index)
if col_pick != "All":
    mask &= df["College"] == col_pick
if mot_pick != "All":
    mask &= df["Gift Allocation"] == mot_pick
df_filt = df[mask]


# -------------------------------------------------
# SELECTIONS
# -------------------------------------------------
state_select = alt.selection_point(fields=["state_fips"], toggle=False, empty=True)
brush         = alt.selection_interval(encodings=["x"])
subcategory_select = alt.selection_point(
    fields=["Allocation Subcategory"],
    toggle="event.shiftKey",
    empty=True
)

# -------------------------------------------------
# CHOROPLETH MAP  (now with true count + sum)
# -------------------------------------------------
state_totals = (
    df_filt.groupby("state_fips", as_index=False)
           .agg(Gift_Amount_sum=("Gift Amount", "sum"),
                Gift_Count=("Gift Amount", "count"))
)

states = alt.topo_feature(data.us_10m.url, "states")
map_chart = (
alt.Chart(states))
.mark_geoshape(stroke="white", strokeWidth=0.5)
    .encode(
        color=alt.condition(
            state_select,
            alt.Color("Gift_Amount_sum:Q",
                      scale=alt.Scale(scheme="blues"),
                      title="Total Gifts ($)"),
            alt.value("lightgray")
        ),
        tooltip=[
            alt.Tooltip("Gift_Amount_sum:Q", title="Total Gifts ($)", format=",.0f"),
            alt.Tooltip("Gift_Count:Q",       title="# Gifts")
        ]
    )
    #.transform_lookup(
        lookup="id",
        from_=alt.LookupData(state_totals,
                             key="state_fips",
                             fields=["Gift_Amount_sum", "Gift_Count"])
    
    .add_params(state_select)
    .project(type="albersUsa")
    .properties(width=380, height=250)


# -------------------------------------------------
# LINE – GIFTS BY YEAR
# -------------------------------------------------
line_chart = (
    alt.Chart(df_filt)
    # .transform_filter(state_select)   
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

# -------------------------------------------------
# BAR – TOTAL BY COLLEGE
# -------------------------------------------------
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
    .add_params(state_select)          # ← declare state_select
    .properties(width=380, height=400)
)

# -------------------------------------------------
# BAR – TOTAL BY SUB-CATEGORY
# -------------------------------------------------
bar_sub = (
    alt.Chart(df_filt)
    #.transform_filter(state_select)
    #.transform_filter(brush)
    .mark_bar()
    .encode(
        y=alt.Y("Allocation Subcategory:N", sort="-x",
                title="Allocation Sub-category"),
        x=alt.X("sum(Gift Amount):Q", title="Total Gifts ($)"),
        color=alt.condition(subcategory_select,
                            alt.value("#1f77b4"), alt.value("lightgray")),
        tooltip=[
            alt.Tooltip("Allocation Subcategory:N", title="Sub-category"),
            alt.Tooltip("sum(Gift Amount):Q", title="Total Gifts ($)", format=",.0f")
        ]
    )
    .add_params(state_select, brush, subcategory_select)  # ← declare all three
    .properties(width=380, height=400)
)

# -------------------------------------------------
# LAYOUT
# -------------------------------------------------
upper = alt.hconcat(map_chart, line_chart).resolve_scale(color="independent")
lower = alt.hconcat(bar_college, bar_sub)
st.altair_chart(alt.vconcat(upper, lower), use_container_width=True)
