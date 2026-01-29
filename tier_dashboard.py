import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --------- CONFIG ---------
INPUT_FILE = "TIER_DATA.xlsx"  # your input file
PRODUCT_COLS = [
    "CCD Usage MRR",
    "FM Usage MRR",
    "INSV Usage MRR",
    "Scheduler Usage MRR",
    "Booking Engine Usage MRR",
    "Telematics Usage MRR",
    "Toll Usage MRR",
]

HOURS_PER_CSM_PER_MONTH = 6.5 * 21

def assign_revenue_tier(mrr: float) -> str:
    if pd.isna(mrr):
        return "Unknown"
    if mrr >= 2000:
        return "High"
    elif mrr >= 1000:
        return "Mid"
    else:
        return "Low"

def assign_vum_tier(vum: float) -> str:
    if pd.isna(vum):
        return "Unknown"
    if vum >= 80:
        return "High"
    elif vum >= 40:
        return "Mid"
    else:
        return "Low"

def assign_mix_tier(count: int) -> str:
    if pd.isna(count) or count == 0:
        return "None"
    if count >= 5:
        return "Full Stack"
    elif count == 4:
        return "Strong"
    elif count == 3:
        return "Moderate"
    elif count == 2:
        return "Low"
    else:
        return "Single"

def assign_priority_tier(row) -> str:
    rev = row["Revenue Tier"]
    vum = row["VUM Tier"]
    product_count = row["Product Count"]

    high_rev = (rev == "High")
    high_vum = (vum == "High")
    high_mix = (product_count >= 3)

    if high_rev and high_vum and high_mix:
        return "White Glove"
    if (
        (rev == "Mid" and (high_vum or high_mix)) or
        (rev == "Low" and high_vum and high_mix)
    ):
        return "Growth"
    if (rev == "Low" and vum == "Low" and product_count <= 1):
        return "Low Touch"
    return "Strategic"

def load_and_process_data(input_file):
    df = pd.read_excel(input_file)

    # Normalize column names to avoid KeyErrors due to trailing/leading whitespace.
    df.columns = df.columns.map(lambda c: c.strip() if isinstance(c, str) else c)

    product_cols_present = [c for c in PRODUCT_COLS if c in df.columns]
    product_cols_missing = [c for c in PRODUCT_COLS if c not in df.columns]

    if len(product_cols_present) == 0:
        st.error(
            "Upload failed: none of the expected product MRR columns were found in this file. "
            "Please confirm your export includes these columns, or update PRODUCT_COLS in the app.\n\n"
            f"Missing columns: {product_cols_missing}\n\n"
            f"Columns found in file: {list(df.columns)}"
        )
        st.stop()

    if "VUM Total" not in df.columns:
        st.error(
            "Upload failed: required column 'VUM Total' was not found in this file.\n\n"
            f"Columns found in file: {list(df.columns)}"
        )
        st.stop()

    df["Total Usage MRR"] = df[product_cols_present].fillna(0).sum(axis=1)
    df["Product Count"] = (df[product_cols_present].fillna(0) > 0).sum(axis=1)
    df["Revenue Tier"] = df["Total Usage MRR"].apply(assign_revenue_tier)
    df["VUM Tier"] = df["VUM Total"].apply(assign_vum_tier)
    df["Product Mix Tier"] = df["Product Count"].apply(assign_mix_tier)
    df["Account Priority Tier"] = df.apply(assign_priority_tier, axis=1)

    tier_to_monthly_call_hours = {
        "White Glove": 2.0,
        "Growth": 1.0,
        "Strategic": 1.0,
        "Low Touch": 1.0 / 3.0,
    }
    df["CSM Call Hours / Month"] = df["Account Priority Tier"].map(tier_to_monthly_call_hours).fillna(0.0)
    df["CSM FTE Required"] = df["CSM Call Hours / Month"] / HOURS_PER_CSM_PER_MONTH
    return df

def main():
    st.set_page_config(layout="wide")
    st.title("CSM Tiering Dashboard")
    st.write("Upload a new Excel file or use the default.")
    uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx"])
    if uploaded_file:
        df = load_and_process_data(uploaded_file)
    else:
        if not os.path.exists(INPUT_FILE):
            st.warning("Default Excel file not found. Please upload an Excel file to continue.")
            st.stop()
        df = load_and_process_data(INPUT_FILE)

    tab1, tab2 = st.tabs(["Dashboard", "Tier Distribution by Selection"])

    with tab1:
        st.markdown("## Account Overview and Tiers")
        with st.expander("Show/Hide Full Account Table", expanded=False):
            st.dataframe(df, use_container_width=True)

        st.markdown("---")
        st.markdown("### Distributions and Summary Stats")

        # Product Count
        pc_col1, pc_col2 = st.columns([2,1], gap="large")
        with pc_col1:
            st.markdown("**Product Count Distribution**")
            fig1 = px.histogram(df, x="Product Count", color="Product Count", title=None, text_auto=True)
            st.plotly_chart(fig1, use_container_width=True, key="product_count")
        with pc_col2:
            st.markdown("**Product Count Table**")
            st.dataframe(df["Product Count"].value_counts().reset_index().rename(columns={"index":"Product Count","Product Count":"Accounts"}), use_container_width=True)

        # Revenue Tier
        rt_col1, rt_col2 = st.columns([2,1], gap="large")
        with rt_col1:
            st.markdown("**Revenue Tier Distribution**")
            fig2 = px.histogram(df, x="Revenue Tier", color="Revenue Tier", category_orders={"Revenue Tier": ["High","Mid","Low","Unknown"]}, title=None, text_auto=True)
            st.plotly_chart(fig2, use_container_width=True, key="revenue_tier")
        with rt_col2:
            st.markdown("**Revenue Tier Table**")
            st.dataframe(df.groupby("Revenue Tier")["Account ID Case Safe"].nunique().rename("Accounts").reset_index(), use_container_width=True)

        # VUM Tier
        vt_col1, vt_col2 = st.columns([2,1], gap="large")
        with vt_col1:
            st.markdown("**VUM Tier Distribution**")
            fig3 = px.histogram(df, x="VUM Tier", color="VUM Tier", category_orders={"VUM Tier": ["High","Mid","Low","Unknown"]}, title=None, text_auto=True)
            st.plotly_chart(fig3, use_container_width=True, key="vum_tier")
        with vt_col2:
            st.markdown("**VUM Tier Table**")
            st.dataframe(df.groupby("VUM Tier")["Account ID Case Safe"].nunique().rename("Accounts").reset_index(), use_container_width=True)

        # Product Mix Tier
        pm_col1, pm_col2 = st.columns([2,1], gap="large")
        with pm_col1:
            st.markdown("**Product Mix Tier Distribution**")
            fig4 = px.histogram(df, x="Product Mix Tier", color="Product Mix Tier", category_orders={"Product Mix Tier": ["Full Stack","Strong","Moderate","Single","None"]}, title=None, text_auto=True)
            st.plotly_chart(fig4, use_container_width=True, key="product_mix_tier")
        with pm_col2:
            st.markdown("**Product Mix Tier Table**")
            st.dataframe(df.groupby("Product Mix Tier")["Account ID Case Safe"].nunique().rename("Accounts").reset_index(), use_container_width=True)

        st.markdown("---")
        st.markdown("### White Glove Top 250 Accounts")

        white_glove = (
            df[df["Account Priority Tier"] == "White Glove"]
            .sort_values("Total Usage MRR", ascending=False)
            .head(250)
        )

        if white_glove.empty:
            st.info("No accounts currently meet the White Glove criteria (High MRR ≥ $2k, High VUM ≥ 80, 3+ products).")
        else:
            display_cols = [
                "Account Name",
                "Account Manager",
                "Primary Manufacturer",
                "Total Usage MRR",
                "VUM Total",
                "Product Count",
                "Revenue Tier",
                "VUM Tier",
                "Product Mix Tier",
                "Account Priority Tier",
                "Account ID Case Safe",
            ]
            display_cols = [c for c in display_cols if c in white_glove.columns]

            st.dataframe(white_glove[display_cols], use_container_width=True)

            csv_data = white_glove.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download White Glove Top 250 as CSV",
                data=csv_data,
                file_name="white_glove_top_250.csv",
                mime="text/csv",
            )

    with tab2:
        st.header("Filter Account Table by Tier")
        tier_type = st.selectbox(
            "Select Tier Type for Table",
            ["Account Priority Tier", "Revenue Tier", "VUM Tier", "Product Mix Tier"],
            key="tier_table_type"
        )
        tier_values = df[tier_type].dropna().unique().tolist()
        tier_value = st.selectbox(f"Select {tier_type}", sorted(tier_values), key="tier_table_value")
        filtered_accounts = df[df[tier_type] == tier_value]
        st.dataframe(filtered_accounts)

if __name__ == "__main__":
    main()
