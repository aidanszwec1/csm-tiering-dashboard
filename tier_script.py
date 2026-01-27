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

# --------- TIER LOGIC ---------
def assign_revenue_tier(mrr: float) -> str:
    """High / Mid / Low based on Total Usage MRR."""
    if pd.isna(mrr):
        return "Unknown"
    if mrr > 2000:
        return "High"
    elif mrr >= 1000:
        return "Mid"
    else:
        return "Low"


def assign_vum_tier(vum: float) -> str:
    """High / Mid / Low based on VUM Total."""
    if pd.isna(vum):
        return "Unknown"
    if vum > 100:
        return "High"
    elif vum >= 50:
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
    if count >= 4:
        return "Full Stack"
    elif count == 3:
        return "Strong"
    elif count == 2:
        return "Moderate"
    else:
        return "Single"


def main():
    # ---- 1. Load data ----
    df = pd.read_excel(INPUT_FILE)

    # ---- 2. Compute Total Usage MRR ----
    df["Total Usage MRR"] = df[PRODUCT_COLS].fillna(0).sum(axis=1)

    # ---- 3. Compute Product Count (how many products have MRR > 0) ----
    df["Product Count"] = (df[PRODUCT_COLS].fillna(0) > 0).sum(axis=1)

    # ---- 4. Apply tier logic ----
    df["Revenue Tier"] = df["Total Usage MRR"].apply(assign_revenue_tier)
    df["VUM Tier"] = df["VUM Total"].apply(assign_vum_tier)
    df["Product Mix Tier"] = df["Product Count"].apply(assign_mix_tier)

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
            full_stack_accounts=("Product Mix Tier", lambda s: (s == "Full Stack").sum()),
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
