# Tiering Rules (Source of Truth: `tier_script.py`)

This document describes the rules used to classify accounts into tiers and to compute the tier proximity field.

## Inputs / Derived Fields Used

- **Total Usage MRR**

  Sum of these product MRR columns (missing treated as 0):

  - `CCD Usage MRR`
  - `FM Usage MRR`
  - `INSV Usage MRR`
  - `Scheduler Usage MRR`
  - `Booking Engine Usage MRR`
  - `Telematics Usage MRR`
  - `Toll Usage MRR`

- **Product Count**

  Count of product columns where MRR > 0.

---

## Supporting Classifiers (Built First)

### Revenue Tier (based on `Total Usage MRR`)

- **High**: `Total Usage MRR >= 2000`
- **Mid**: `1000 <= Total Usage MRR < 2000`
- **Low**: `Total Usage MRR < 1000`
- **Unknown**: `Total Usage MRR` is blank/NaN

### VUM Tier (based on `VUM Total`)

- **High**: `VUM Total >= 80`
- **Mid**: `40 <= VUM Total < 80`
- **Low**: `VUM Total < 40`
- **Unknown**: `VUM Total` is blank/NaN

### Product Mix Tier (based on `Product Count`)

- **Strong**: `Product Count >= 3`
- **Moderate**: `Product Count == 2`
- **Low**: `Product Count == 1`
- **None**: `Product Count == 0` (or blank/NaN)

---

# Final Output Tier: `Account Priority Tier`

## Weighted score inputs

A weighted score is computed using:

- **Revenue** (based on `Revenue Tier`) = 50%
- **VUM** (based on `VUM Tier`) = 25%
- **Usage** (based on `Product Count`) = 25%

### Revenue score

- `Revenue Tier == "High"` -> 1.0
- `Revenue Tier == "Mid"` -> 0.6
- `Revenue Tier == "Low"` -> 0.2
- `Revenue Tier == "Unknown"` -> 0.0

### VUM score

- `VUM Tier == "High"` -> 1.0
- `VUM Tier == "Mid"` -> 0.6
- `VUM Tier == "Low"` -> 0.2
- `VUM Tier == "Unknown"` -> 0.0

### Usage score (based on `Product Count`)

- `Product Count >= 3` -> 1.0
- `Product Count == 2` -> 0.6
- `Product Count == 1` -> 0.3
- `Product Count == 0` (or blank/NaN) -> 0.0

### Score formula

`score = 0.50 * revenue_score + 0.25 * vum_score + 0.25 * usage_score`

## 1) White Glove (weighted)

An account is **White Glove** if:

- `Total Usage MRR >= 1000`
- AND `score >= 0.80`

## 2) Growth (ANY of the following)

If the account is not White Glove, it is **Growth** if it matches **any** rule below:

### Growth Rule 1 (Weighted)

- `score >= 0.60` (and not already White Glove)

### Growth Rule 2 (Option A – Revenue-led Growth)

- `Revenue Tier == "Mid"`
- AND `VUM Tier in {"Mid", "High"}`
- AND `Product Count >= 2`

### Growth Rule 3 (Option B – Complexity-led Growth)

- `Revenue Tier in {"Low", "Mid"}`
- AND `VUM Tier == "High"`
- AND `Product Count >= 3`

### Growth Rule 4 (Option C – Expansion-ready)

- `Product Mix Tier == "Moderate"`
- AND `Total Usage MRR >= 750`

## 3) Tech Touch (default)

If the account is **not White Glove** and does **not** meet any Growth rule, it is **Tech Touch**.

---

# Extra Field: `Tier Trajectory` (Tier Proximity)

This does **not** change the tier. It flags accounts that are close to moving up.

## Values

- **Stable**
- **Near Upgrade**

## Tech Touch → Growth: `Near Upgrade`

A **Tech Touch** account is marked **Near Upgrade** if:

- It meets **at least 2** of the 4 Growth signals:

  - `Product Count >= 2`
  - `VUM Tier in {"Mid", "High"}`
  - `Product Mix Tier in {"Moderate", "Strong"}`
  - `Total Usage MRR >= 750`

- AND `Total Usage MRR >= 500` (noise filter)

## Growth → White Glove: `Near Upgrade`

A **Growth** account is marked **Near Upgrade** if:

- `Total Usage MRR >= 1300`
