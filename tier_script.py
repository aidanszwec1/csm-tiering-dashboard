import pandas as pd

# --------- CONFIG ---------
INPUT_FILE = "TIER_DATA.xlsx"          # your input file
OUTPUT_FILE = "TIER_OUTPUT.xlsx"       # output file name

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

# --------- TIER LOGIC ---------
def assign_revenue_tier(mrr: float) -> str:
    """High / Mid / Low based on Total Usage MRR."""
    if pd.isna(mrr):
        return "Unknown"
    if mrr >= 2000:
        return "High"
    elif mrr >= 1000:
        return "Mid"
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


def assign_vum_tier(vum: float) -> str:
    """High / Mid / Low based on VUM Total."""
    if pd.isna(vum):
        return "Unknown"
    if vum >= 80:
        return "High"
    elif vum >= 40:
        return "Mid"
    else:
        return "Low"


def assign_mix_tier(count: int) -> str:
    """
    Tier based on how many products have MRR > 0:
    0  -> None
    1  -> Single
    2  -> Moderate
    3  -> Strong
    4+ -> Full Stack
    """
    if pd.isna(count) or count == 0:
        return "None"
    if count >= 3:
        return "Strong"
    elif count == 2:
        return "Moderate"
    else:
        return "Low"


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


def main():
    # ---- 1. Load data ----
    df = pd.read_excel(INPUT_FILE)

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

    # ---- 2. Compute Total Usage MRR ----
    df["Total Usage MRR"] = df[PRODUCT_COLS].fillna(0).sum(axis=1)

    # ---- 3. Compute Product Count (how many products have MRR > 0) ----
    df["Product Count"] = (df[PRODUCT_COLS].fillna(0) > 0).sum(axis=1)

    # ---- 4. Apply tier logic ----
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

    # ---- 5. Build CSM-level summary ----
    # If Account ID is duplicated across rows, nunique prevents double-counting
    csm_summary = (
        df.groupby("Account Manager")
        .agg(
            accounts=("Account ID Case Safe", "nunique"),
            total_mrr=("Total Usage MRR", "sum"),
            avg_mrr=("Total Usage MRR", "mean"),
            total_vum=("VUM Total", "sum"),
            avg_vum=("VUM Total", "mean"),
            avg_product_count=("Product Count", "mean"),
            full_stack_accounts=("Product Mix Tier", lambda s: (s == "Strong").sum()),
            csm_call_hours_per_month=("CSM Call Hours / Month", "sum"),
        )
        .reset_index()
    )

    # ---- 6. Write output to Excel ----
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Account Tiers", index=False)
        csm_summary.to_excel(writer, sheet_name="CSM Summary", index=False)

    print(f"Done. Wrote tiers + summary to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
