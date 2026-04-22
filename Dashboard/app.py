"""
Cotton TDM Export Flow Dashboard
================================
Run:
    streamlit run app.py
"""

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Cotton TDM Export Flow Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
  [data-testid="stHeader"] { background: transparent !important; }
  .block-container { padding-top: 2.5rem !important; padding-bottom: 1.5rem; max-width: 1450px; }
  html, body, [class*="css"] { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; }
  h1, h2, h3 { font-weight: 550 !important; letter-spacing: 0 !important; }
  hr { border: none !important; border-top: 1px solid #e8e8ed !important; margin: 0.75rem 0 !important; }
  [data-testid="stMetric"] { border: 1px solid #ececf1; border-radius: 8px; padding: 10px 12px; }
  [data-testid="stExpander"] { border: 1px solid #e8e8ed !important; border-radius: 8px !important; }
</style>
""",
    unsafe_allow_html=True,
)

APP_DIR = Path(__file__).parent
DATA_PATH = APP_DIR.parent / "Database" / "tdm_cotton_exports.parquet"

HS4_LABELS = {
    "5201": "Cotton, not carded/combed",
    "5202": "Cotton waste",
    "5203": "Cotton, carded/combed",
    "5204": "Cotton sewing thread",
    "5205": "Cotton yarn >=85%",
    "5206": "Cotton yarn <85%",
    "5207": "Cotton yarn, retail sale",
    "5208": "Woven cotton >=85%, <=200g/m2",
    "5209": "Woven cotton >=85%, >200g/m2",
    "5210": "Woven cotton <85%, <=200g/m2",
    "5211": "Woven cotton <85%, >200g/m2",
    "5212": "Other woven cotton fabrics",
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PAL = ["#2f6f73", "#c75d2c", "#415a77", "#d6a23f", "#6f5aa8", "#5a8f5b", "#8d6e63", "#b54b63"]


@st.cache_data(ttl=600)
def load_data(path: str) -> pd.DataFrame:
    p = path.replace("\\", "/")
    df = duckdb.sql(f"SELECT * FROM '{p}'").df()
    if "MONTH" in df.columns and "MONTH_NUM" not in df.columns:
        df = df.rename(columns={"MONTH": "MONTH_NUM"})
    df["DATE"] = pd.to_datetime(df[["YEAR", "MONTH_NUM"]].rename(columns={"MONTH_NUM": "MONTH"}).assign(DAY=1))
    df["HS4"] = df["COMMODITY"].astype(str).str.extract(r"(\d+)")[0].str.zfill(6).str[:4]
    df["HS4_LABEL"] = df["HS4"].map(HS4_LABELS).fillna("Other cotton")
    df["HS4_NAME"] = df["HS4"] + " - " + df["HS4_LABEL"]
    df["MONTH_NAME"] = df["MONTH_NUM"].map({i + 1: m for i, m in enumerate(MONTHS)})
    return df


def apply_crop_year(df: pd.DataFrame, start_month: int) -> pd.DataFrame:
    out = df.copy()
    year_start = out["YEAR"] - (out["MONTH_NUM"] < start_month).astype(int)
    if start_month == 1:
        out["CROP_YEAR"] = year_start.astype(str)
    else:
        out["CROP_YEAR"] = (
            (year_start % 100).astype(str).str.zfill(2)
            + "/"
            + ((year_start + 1) % 100).astype(str).str.zfill(2)
        )
    out["CROP_MONTH_NUM"] = ((out["MONTH_NUM"] - start_month) % 12) + 1
    out["CROP_MONTH"] = out["CROP_MONTH_NUM"].map(
        {i + 1: MONTHS[(start_month - 1 + i) % 12] for i in range(12)}
    )
    return out


def chart_layout(height: int = 360) -> dict:
    return dict(
        height=height,
        template="plotly_white",
        margin=dict(t=20, b=40, l=10, r=10),
        legend=dict(orientation="h", y=-0.18, x=0),
        font=dict(family="-apple-system, Helvetica Neue, Arial, sans-serif", size=11, color="#1d1d1f"),
    )


def kmt(series: pd.Series) -> pd.Series:
    return series / 1000


if not DATA_PATH.exists():
    st.error(f"Missing parquet: {DATA_PATH}")
    st.stop()

df = load_data(str(DATA_PATH))

with st.sidebar:
    crop_basis = st.radio("Crop Year", ["Jan-Dec", "Apr-Mar", "Oct-Sep", "Custom"], index=0)
    if crop_basis == "Jan-Dec":
        crop_start = 1
    elif crop_basis == "Apr-Mar":
        crop_start = 4
    elif crop_basis == "Oct-Sep":
        crop_start = 10
    else:
        crop_start = MONTHS.index(st.selectbox("Start Month", MONTHS, index=0)) + 1

    unit = st.radio("Unit", ["k MT", "MT"], index=0)

df = apply_crop_year(df, crop_start)
df["VALUE"] = kmt(df["QTY1"]) if unit == "k MT" else df["QTY1"]

st.markdown("## Cotton TDM Export Flow")
st.caption("TDM reporter exports only: China, United States, Brazil. HS labels use Chapter 52 cotton headings.")
st.markdown("<hr>", unsafe_allow_html=True)

with st.expander("Filters", expanded=True):
    c1, c2, c3, c4, c5 = st.columns([1.1, 1.3, 1.2, 1.4, 1.2])

    exporters = sorted(df["REPORTER"].dropna().unique())
    hs_names = sorted(df["HS4_NAME"].dropna().unique())
    regions = sorted(df["REGION"].dropna().unique())
    years = sorted(df["CROP_YEAR"].dropna().unique())

    with c1:
        sel_exporters = st.multiselect("Exporter", exporters, default=exporters)
    with c2:
        sel_hs = st.multiselect("HS Heading", hs_names, default=hs_names)
    with c3:
        sel_region = st.selectbox("Destination Region", ["All"] + regions, index=0)

    region_mask = df["REGION"].eq(sel_region) if sel_region != "All" else pd.Series(True, index=df.index)
    partners = sorted(df.loc[region_mask, "PARTNER"].dropna().unique())
    with c4:
        sel_partners = st.multiselect("Destination", partners, default=partners)
    with c5:
        sel_year_range = st.select_slider("Crop Years", options=years, value=(years[0], years[-1]))

mask = (
    df["REPORTER"].isin(sel_exporters or exporters)
    & df["HS4_NAME"].isin(sel_hs or hs_names)
    & region_mask
    & df["PARTNER"].isin(sel_partners or partners)
    & df["CROP_YEAR"].between(sel_year_range[0], sel_year_range[1])
)
dff = df.loc[mask].copy()

if dff.empty:
    st.warning("No data for current filters.")
    st.stop()

latest_year = sorted(dff["CROP_YEAR"].unique())[-1]
prev_year = sorted(dff["CROP_YEAR"].unique())[-2] if dff["CROP_YEAR"].nunique() > 1 else None
latest_total = dff.loc[dff["CROP_YEAR"].eq(latest_year), "VALUE"].sum()
prev_total = dff.loc[dff["CROP_YEAR"].eq(prev_year), "VALUE"].sum() if prev_year else 0
yoy = ((latest_total / prev_total) - 1) * 100 if prev_total else None

m1, m2, m3, m4 = st.columns(4)
m1.metric("Latest CY", latest_year)
m2.metric(f"{latest_year} Total", f"{latest_total:,.1f} {unit}", f"{yoy:+.1f}%" if yoy is not None else None)
m3.metric("Destinations", f"{dff['PARTNER'].nunique():,}")
m4.metric("HS Headings", f"{dff['HS4'].nunique():,}")

tab_overview, tab_exporter, tab_destination, tab_hs, tab_data = st.tabs(
    ["Overview", "Exporter", "Destination", "HS Heading", "Data"]
)

with tab_overview:
    annual = dff.groupby(["CROP_YEAR", "REPORTER"], as_index=False)["VALUE"].sum()
    fig = px.bar(
        annual,
        x="CROP_YEAR",
        y="VALUE",
        color="REPORTER",
        color_discrete_sequence=PAL,
        barmode="stack",
        labels={"VALUE": unit, "CROP_YEAR": "Crop Year", "REPORTER": "Exporter"},
    )
    fig.update_layout(**chart_layout(390))
    st.plotly_chart(fig, width="stretch")

    monthly = dff.groupby(["CROP_YEAR", "CROP_MONTH_NUM", "CROP_MONTH"], as_index=False)["VALUE"].sum()
    fig2 = go.Figure()
    for i, cy in enumerate(sorted(monthly["CROP_YEAR"].unique())):
        d = monthly[monthly["CROP_YEAR"].eq(cy)].sort_values("CROP_MONTH_NUM")
        width = 3 if cy == latest_year else 1.4
        color = "#1d1d1f" if cy == latest_year else PAL[i % len(PAL)]
        fig2.add_trace(go.Scatter(x=d["CROP_MONTH"], y=d["VALUE"], mode="lines+markers", name=cy, line=dict(color=color, width=width)))
    fig2.update_layout(**chart_layout(430), xaxis=dict(categoryorder="array", categoryarray=d["CROP_MONTH"].tolist()))
    st.plotly_chart(fig2, width="stretch")

with tab_exporter:
    ex = dff.groupby(["REPORTER", "CROP_YEAR"], as_index=False)["VALUE"].sum()
    fig = px.line(ex, x="CROP_YEAR", y="VALUE", color="REPORTER", markers=True, color_discrete_sequence=PAL, labels={"VALUE": unit})
    fig.update_layout(**chart_layout(390))
    st.plotly_chart(fig, width="stretch")

    share = dff.groupby(["REPORTER"], as_index=False)["VALUE"].sum().sort_values("VALUE", ascending=False)
    fig2 = px.pie(share, names="REPORTER", values="VALUE", hole=0.45, color_discrete_sequence=PAL)
    fig2.update_layout(**chart_layout(360))
    st.plotly_chart(fig2, width="stretch")

with tab_destination:
    top_dest = dff.groupby("PARTNER", as_index=False)["VALUE"].sum().nlargest(25, "VALUE")
    fig = px.bar(top_dest, x="VALUE", y="PARTNER", orientation="h", labels={"VALUE": unit, "PARTNER": "Destination"}, color_discrete_sequence=["#2f6f73"])
    fig.update_layout(**chart_layout(620), yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, width="stretch")

    region = dff.groupby(["REGION", "CROP_YEAR"], as_index=False)["VALUE"].sum()
    fig2 = px.area(region, x="CROP_YEAR", y="VALUE", color="REGION", color_discrete_sequence=PAL, labels={"VALUE": unit})
    fig2.update_layout(**chart_layout(390))
    st.plotly_chart(fig2, width="stretch")

with tab_hs:
    hs = dff.groupby(["HS4_NAME"], as_index=False)["VALUE"].sum().sort_values("VALUE", ascending=False)
    fig = px.bar(hs, x="VALUE", y="HS4_NAME", orientation="h", labels={"VALUE": unit, "HS4_NAME": "HS Heading"}, color_discrete_sequence=["#415a77"])
    fig.update_layout(**chart_layout(520), yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, width="stretch")

    mix = dff.groupby(["CROP_YEAR", "HS4_NAME"], as_index=False)["VALUE"].sum()
    fig2 = px.area(mix, x="CROP_YEAR", y="VALUE", color="HS4_NAME", color_discrete_sequence=PAL, labels={"VALUE": unit, "HS4_NAME": "HS Heading"})
    fig2.update_layout(**chart_layout(430))
    st.plotly_chart(fig2, width="stretch")

with tab_data:
    out = (
        dff.groupby(["REPORTER", "PARTNER", "REGION", "HS4", "HS4_LABEL", "CROP_YEAR"], as_index=False)["VALUE"]
        .sum()
        .sort_values("VALUE", ascending=False)
    )
    st.dataframe(out, width="stretch", height=650)

st.caption(f"Source parquet: {DATA_PATH}")
