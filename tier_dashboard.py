import streamlit as st
import pandas as pd
import plotly.express as px
import os
import numpy as np

# --------- CONFIG ---------
APP_VERSION = "62cfb9b"
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

GROWTH_TO_WHITE_GLOVE_NEAR_UPGRADE_MRR_THRESHOLD = 1300

REVENUE_WEIGHT = 0.50
VUM_WEIGHT = 0.25
USAGE_WEIGHT = 0.25

WHITE_GLOVE_SCORE_THRESHOLD = 0.80
GROWTH_SCORE_THRESHOLD = 0.60

WHITE_GLOVE_MIN_MRR = 1000

HOURS_PER_CSM_PER_MONTH = 6.5 * 21

PARENT_ACCOUNT_OVERRIDES = {
    "autonation": "Rikki",
    "holman": "Brian",
    "sonic": "Danielle",
    "new country": "Emily",
    "sewell": "Brian",
    "asbury": "Emily",
    "jay wolfe": "Danielle",
    "kaplan": "Danielle",
}

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
    if count >= 3:
        return "Strong"
    elif count == 2:
        return "Moderate"
    else:
        return "Low"


def revenue_score(rev_tier: str) -> float:
    if rev_tier == "High":
        return 1.0
    if rev_tier == "Mid":
        return 0.6
    if rev_tier == "Low":
        return 0.2
    return 0.0


def vum_score(vum_tier: str) -> float:
    if vum_tier == "High":
        return 1.0
    if vum_tier == "Mid":
        return 0.6
    if vum_tier == "Low":
        return 0.2
    return 0.0


def usage_score(product_count: int) -> float:
    if pd.isna(product_count):
        return 0.0
    if product_count >= 3:
        return 1.0
    if product_count == 2:
        return 0.6
    if product_count == 1:
        return 0.3
    return 0.0

def assign_priority_tier(row) -> str:
    rev = row["Revenue Tier"]
    vum = row["VUM Tier"]
    product_count = row["Product Count"]

    product_mix = row["Product Mix Tier"]
    total_usage_mrr = row["Total Usage MRR"]

    score = (
        REVENUE_WEIGHT * revenue_score(rev)
        + VUM_WEIGHT * vum_score(vum)
        + USAGE_WEIGHT * usage_score(product_count)
    )

    # 1) White Glove (weighted)
    if (
        not pd.isna(total_usage_mrr)
        and total_usage_mrr >= WHITE_GLOVE_MIN_MRR
        and score >= WHITE_GLOVE_SCORE_THRESHOLD
    ):
        return "White Glove"

    # 2) Growth (weighted)
    if score >= GROWTH_SCORE_THRESHOLD:
        return "Growth"

    # Option A – Revenue-led Growth
    if rev == "Mid" and vum in {"Mid", "High"} and product_count >= 2:
        return "Growth"

    # Option B – Complexity-led Growth
    if rev in {"Low", "Mid"} and vum == "High" and product_count >= 3:
        return "Growth"

    # Option C – Expansion-ready
    if (
        product_mix == "Moderate"
        and (not pd.isna(total_usage_mrr) and total_usage_mrr >= 750)
    ):
        return "Growth"

    # 3) Tech Touch (default)
    return "Tech Touch"


def assign_tier_trajectory(row) -> str:
    tier = row["Account Priority Tier"]
    rev = row["Revenue Tier"]
    vum = row["VUM Tier"]
    product_count = row["Product Count"]
    product_mix = row["Product Mix Tier"]
    total_usage_mrr = row["Total Usage MRR"]

    # Tech Touch -> Growth proximity
    if tier == "Tech Touch":
        growth_signals_met = sum(
            [
                product_count >= 2,
                vum in {"Mid", "High"},
                product_mix in {"Moderate", "Strong"},
                (not pd.isna(total_usage_mrr) and total_usage_mrr >= 750),
            ]
        )
        if (not pd.isna(total_usage_mrr) and total_usage_mrr >= 500) and growth_signals_met >= 2:
            return "Near Upgrade"

    # Growth -> White Glove proximity
    if tier == "Growth":
        if (
            not pd.isna(total_usage_mrr)
            and total_usage_mrr >= GROWTH_TO_WHITE_GLOVE_NEAR_UPGRADE_MRR_THRESHOLD
        ):
            return "Near Upgrade"

    return "Stable"

def load_and_process_data(input_file):
    df = pd.read_excel(input_file)

    # Normalize column names to avoid KeyErrors due to trailing/leading whitespace.
    df.columns = df.columns.map(lambda c: c.strip() if isinstance(c, str) else c)

    if "Account Manager" not in df.columns and "Customer Success Manager" in df.columns:
        df = df.rename(columns={"Customer Success Manager": "Account Manager"})

    if "Parent Account" in df.columns and "Account Manager" in df.columns:
        parent_norm = (
            df["Parent Account"]
            .astype("string")
            .fillna("")
            .str.strip()
            .str.lower()
        )
        for parent_key, override_am in PARENT_ACCOUNT_OVERRIDES.items():
            override_mask = parent_norm.str.contains(parent_key, na=False)
            if override_mask.any():
                df.loc[override_mask, "Account Manager"] = override_am

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
    df["Tier Trajectory"] = df.apply(assign_tier_trajectory, axis=1)

    tier_to_monthly_call_hours = {
        "White Glove": 1.0,
        "Growth": 0.5,
        "Tech Touch": 0.0,
    }
    df["CSM Call Hours / Month"] = df["Account Priority Tier"].map(tier_to_monthly_call_hours).fillna(0.0)
    df["CSM FTE Required"] = df["CSM Call Hours / Month"] / HOURS_PER_CSM_PER_MONTH

    if "Account Manager" in df.columns:
        df["CSM Total Call Hours / Month (by Account Manager)"] = df.groupby("Account Manager")["CSM Call Hours / Month"].transform("sum")
        df["CSM Total FTE Required (by Account Manager)"] = df.groupby("Account Manager")["CSM FTE Required"].transform("sum")
    else:
        df["CSM Total Call Hours / Month (by Account Manager)"] = pd.NA
        df["CSM Total FTE Required (by Account Manager)"] = pd.NA
    return df


def allocate_csms_by_oem(oem_hours: pd.Series, total_csms: int) -> pd.Series:
    oem_hours = oem_hours.fillna(0.0)
    oem_hours = oem_hours[oem_hours > 0]
    if oem_hours.empty:
        return pd.Series(dtype=int)
    if total_csms <= 0:
        return pd.Series(0, index=oem_hours.index, dtype=int)

    total_hours = float(oem_hours.sum())
    raw = (oem_hours / total_hours) * float(total_csms)
    base = np.floor(raw).astype(int)

    remaining = int(total_csms - int(base.sum()))
    if remaining > 0:
        remainders = (raw - base).sort_values(ascending=False)
        for oem in remainders.index[:remaining]:
            base.loc[oem] += 1

    base[base < 0] = 0
    return base


def simulate_within_oem_assignment(df: pd.DataFrame, oem_col: str, allocation: pd.Series, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(int(seed))
    rows = []
    for oem, csm_count in allocation.items():
        if int(csm_count) <= 0:
            continue
        oem_df = df[df[oem_col] == oem]
        if oem_df.empty:
            continue
        csm_ids = [f"{oem} | CSM {i+1}" for i in range(int(csm_count))]
        assigned = rng.integers(low=0, high=len(csm_ids), size=len(oem_df))
        hours = (
            oem_df[["CSM Call Hours / Month"]]
            .assign(sim_csm=[csm_ids[i] for i in assigned])
            .groupby("sim_csm")["CSM Call Hours / Month"]
            .sum()
        )
        for sim_csm, h in hours.items():
            rows.append({"Simulated CSM": sim_csm, "OEM": oem, "Call Hours / Month": float(h)})
    if not rows:
        return pd.DataFrame(columns=["Simulated CSM", "OEM", "Call Hours / Month"])
    return pd.DataFrame(rows)

def main():
    st.set_page_config(layout="wide")
    st.title("CSM Tiering Dashboard")
    st.caption(f"App version: {APP_VERSION}")
    st.write("Upload a new Excel file or use the default.")
    uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx"])
    if uploaded_file:
        st.caption(f"Data source: uploaded file ({uploaded_file.name})")
        df = load_and_process_data(uploaded_file)
    else:
        if not os.path.exists(INPUT_FILE):
            st.warning("Default Excel file not found. Please upload an Excel file to continue.")
            st.stop()
        try:
            mtime = os.path.getmtime(INPUT_FILE)
            st.caption(f"Data source: default file ({INPUT_FILE}) | Last modified: {pd.to_datetime(mtime, unit='s')}")
        except OSError:
            st.caption(f"Data source: default file ({INPUT_FILE})")
        df = load_and_process_data(INPUT_FILE)

    tab1, tab2, tab3 = st.tabs(["Dashboard", "Tier Distribution by Selection", "OEM Split Experiment"])

    with tab1:
        st.markdown("## Account Overview and Tiers")
        with st.expander("Show/Hide Full Account Table", expanded=False):
            st.dataframe(df, use_container_width=True)

        st.markdown("---")
        st.markdown("### CSM Workload Summary")

        total_hours = float(df["CSM Call Hours / Month"].sum())
        total_fte = float(df["CSM FTE Required"].sum())
        m_col1, m_col2 = st.columns(2, gap="large")
        with m_col1:
            st.metric("Total CSM Call Hours / Month", f"{total_hours:,.1f}")
        with m_col2:
            st.metric("Total CSM FTE Required", f"{total_fte:,.2f}")

        if "Account Manager" in df.columns:
            workload_by_am = (
                df.groupby("Account Manager", dropna=False)
                .agg(
                    **{
                        "Accounts": ("Account ID Case Safe", "nunique"),
                        "CSM Call Hours / Month": ("CSM Call Hours / Month", "sum"),
                        "CSM FTE Required": ("CSM FTE Required", "sum"),
                    }
                )
                .reset_index()
                .sort_values("CSM Call Hours / Month", ascending=False)
            )
            st.dataframe(workload_by_am, use_container_width=True)
        else:
            st.info("Column 'Account Manager' not found, so workload cannot be summarized by CSM.")

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
            fig4 = px.histogram(df, x="Product Mix Tier", color="Product Mix Tier", category_orders={"Product Mix Tier": ["Strong","Moderate","Low","None"]}, title=None, text_auto=True)
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
            st.info("No accounts currently meet the White Glove criteria.")
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

    with tab3:
        st.header("OEM Split Experiment")

        oem_col = "Primary Manufacturer" if "Primary Manufacturer" in df.columns else None
        if oem_col is None:
            st.info("Column 'Primary Manufacturer' not found, so OEM split experiment cannot run.")
        else:
            oem_df = df.dropna(subset=[oem_col]).copy()
            if oem_df.empty:
                st.info("No OEM values found to analyze.")
            else:
                total_call_hours = float(oem_df["CSM Call Hours / Month"].sum())
                st.metric("Total Call Hours / Month (all OEMs)", f"{total_call_hours:,.1f}")

                oem_hours = (
                    oem_df.groupby(oem_col, dropna=False)["CSM Call Hours / Month"]
                    .sum()
                    .sort_values(ascending=False)
                )

                total_csms = st.number_input("Total CSMs to allocate across OEMs", min_value=1, max_value=500, value=10, step=1)
                allocation = allocate_csms_by_oem(oem_hours, int(total_csms))

                result = (
                    pd.DataFrame({
                        "OEM": oem_hours.index,
                        "Call Hours / Month": oem_hours.values,
                    })
                    .set_index("OEM")
                    .assign(
                        **{
                            "Allocated CSMs": allocation,
                        }
                    )
                )
                result["Allocated CSMs"] = result["Allocated CSMs"].fillna(0).astype(int)
                result["Call Hours / CSM / Month"] = result.apply(
                    lambda r: (float(r["Call Hours / Month"]) / float(r["Allocated CSMs"])) if int(r["Allocated CSMs"]) > 0 else float("nan"),
                    axis=1,
                )

                st.subheader("Recommended OEM → CSM allocation (fair by call hours)")
                st.dataframe(result.reset_index(), use_container_width=True)

                hours_per_csm = result["Call Hours / CSM / Month"].dropna()
                if not hours_per_csm.empty:
                    c1, c2, c3 = st.columns(3, gap="large")
                    with c1:
                        st.metric("Avg Call Hours / CSM / Month", f"{hours_per_csm.mean():,.2f}")
                    with c2:
                        st.metric("Min Call Hours / CSM / Month", f"{hours_per_csm.min():,.2f}")
                    with c3:
                        st.metric("Max Call Hours / CSM / Month", f"{hours_per_csm.max():,.2f}")

                    fig = px.bar(
                        result.reset_index(),
                        x="OEM",
                        y="Call Hours / CSM / Month",
                        title=None,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                st.markdown("---")
                st.subheader("Random within-OEM assignment simulation")
                simulate = st.checkbox("Simulate splitting each OEM's accounts across its allocated CSMs", value=True)
                seed = st.number_input("Random seed", min_value=0, max_value=1_000_000, value=42, step=1)
                if simulate:
                    sim_df = simulate_within_oem_assignment(oem_df, oem_col, allocation, int(seed))
                    if sim_df.empty:
                        st.info("Simulation produced no results (check allocation / OEM values).")
                    else:
                        st.dataframe(sim_df.sort_values("Call Hours / Month", ascending=False), use_container_width=True)
                        s1, s2, s3 = st.columns(3, gap="large")
                        with s1:
                            st.metric("Sim Avg Call Hours / CSM / Month", f"{sim_df['Call Hours / Month'].mean():,.2f}")
                        with s2:
                            st.metric("Sim Min Call Hours / CSM / Month", f"{sim_df['Call Hours / Month'].min():,.2f}")
                        with s3:
                            st.metric("Sim Max Call Hours / CSM / Month", f"{sim_df['Call Hours / Month'].max():,.2f}")

if __name__ == "__main__":
    main()
