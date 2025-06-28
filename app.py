########################
# app.py  –  Streamlit #
########################
import streamlit as st
import pandas as pd
import altair as alt
import us  # make sure "us" is in requirements.txt

# ------------- PAGE CONFIG & ALTAIR OPTIONS ------------------------
st.set_page_config(
    page_title="University Donor Dashboard",
    layout="wide",
)
alt.data_transformers.disable_max_rows()  # so Altair won’t truncate large dfs

# ------------- LOAD DATA -------------------------------------------
@st.cache_data(show_spinner=False)
def load_data(csv_path: str) -> pd.DataFrame:
    df0 = pd.read_csv(csv_path)

    # --- State FIPS lookups (only once, so fine to do here) ----------
    state_id_map   = {state.abbr: int(state.fips)  for state in us.states.STATES}
    state_name_map = {int(state.fips): state.name  for state in us.states.STATES}

    df0["state_fips"] = (
        df0["State"]
           .map(state_id_map)
           .dropna()
           .astype(int)
    )

    # Add Gift Year if missing
    if "Gift Year" not in df0.columns:
        df0["Gift Year"] = pd.to_datetime(df0["Gift Date"]).dt.year.astype(str)

    return df0, state_name_map

# Path can be relative in Streamlit Cloud repo
df, state_name_map = load_data("donations.csv")

# ------------- AGGREGATED DATA (for a possible map later) ----------
state_agg = (
    df.groupby("state_fips")
      .agg(
          **{
              "Total Donations": ("Gift Amount", "sum"),
              "Unique Donors" : ("Prospect ID", "nunique"),
          }
      )
      .reset_index()
)
state_agg["State Name"] = state_agg["state_fips"].map(state_name_map)

# ------------- SELECTIONS ------------------------------------------
selection_alloc = alt.selection_point(fields=["Gift Allocation"], name="SelectAlloc")
brush_year      = alt.selection_interval(encodings=["x"], name="BrushYear")

# --- If you want to reset by clicking blank space: ---------------
reset_click = alt.selection_point(on="click", clear="mouseup", name="ResetClick")

# ------------- MAIN CHARTS ----------------------------------------
bar_alloc = (
    alt.Chart(df)
        .mark_bar()
        .encode(
            y=alt.Y("Gift Allocation:N", sort="-x"),
            x=alt.X("sum(Gift Amount):Q", title="Total Gift Amount ($)"),
            color=alt.condition(selection_alloc, "Gift Allocation:N", alt.value("lightgray")),
            tooltip=[
                "Gift Allocation:N",
                alt.Tooltip("sum(Gift Amount):Q", format="$,.0f"),
            ],
        )
        .add_selection(selection_alloc)
        .properties(width=350, height=220, title="Total Gift Amount by Allocation")
)

line_year = (
    alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X("Gift Year:O", sort="ascending", title="Year"),
            y=alt.Y("sum(Gift Amount):Q", title="Total Gift Amount ($)"),
            color="Gift Allocation:N",
            tooltip=[
                alt.Tooltip("Gift Year:O", title="Year"),
                "Gift Allocation:N",
                alt.Tooltip("sum(Gift Amount):Q", format="$,.0f", title="Total Gift Amount"),
            ],
        )
        .add_selection(brush_year, selection_alloc)
        .transform_filter(selection_alloc)
        .properties(width=500, height=220, title="Donations Over Time by Allocation")
)

bar_subcat = (
    alt.Chart(df)
        .mark_bar()
        .encode(
            y=alt.Y("Allocation Subcategory:N", sort="-x"),
            x=alt.X("sum(Gift Amount):Q", title="Total Gift Amount ($)"),
            color="Gift Allocation:N",
            tooltip=[
                "Allocation Subcategory:N",
                alt.Tooltip("sum(Gift Amount):Q", format="$,.0f"),
            ],
        )
        .add_selection(selection_alloc, brush_year)
        .transform_filter(selection_alloc)
        .transform_filter(brush_year)
        .properties(width=850, height=300, title="Breakdown by Allocation Subcategory")
)

# ------------- LAYOUT (single Altair spec so linking works) --------
dashboard = alt.vconcat(
    alt.hconcat(bar_alloc, line_year).resolve_scale(color="independent"),
    bar_subcat,
    spacing=15,
)

st.altair_chart(dashboard, use_container_width=True)

# ------------- OPTIONAL: SIDEBAR INFO / RAW DATA TOGGLE -----------
with st.sidebar:
    st.header("About")
    st.markdown(
        """
        **Brushing & Linking Demo**

        * Click a bar to filter by **Gift Allocation**  
        * Drag across the year axis to focus on a time window  
        * All charts update together.
        """
    )
    if st.checkbox("Show raw data"):
        st.dataframe(df)




