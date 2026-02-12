# CSM Tiering Buckets Summary

## Data source

`newexport.xlsx` (bucket counts are based on unique `Account ID Case Safe`).

## 1) Customers in each bucket (current rules)

| Account Priority Tier | Unique customers (accounts) |
| --- | ---: |
| Strategic | 1748 |
| Low Touch | 1164 |
| Growth | 357 |
| White Glove | 121 |

Total unique accounts: **3390**

## 2) “Same data” with lowest bucket = 1x 30-minute call per quarter

### Bucket assignment

Changing the lowest-bucket engagement level does **not** change which bucket customers fall into. Bucket counts remain:

| Account Priority Tier | Unique customers (accounts) |
| --- | ---: |
| Strategic | 1748 |
| Low Touch | 1164 |
| Growth | 357 |
| White Glove | 121 |

### Workload / call-time assumptions

The dashboard maps tiers to **CSM Call Hours / Month**.

- Current **Low Touch** mapping: **`1.0/3.0` hours/month** (≈ 1x 1-hour call per quarter)
- Requested **Low Touch** mapping: **`0.5/3.0` hours/month** (≈ 1x 30-minute call per quarter)

Workload totals (using `HOURS_PER_CSM_PER_MONTH = 6.5 * 21 = 136.5`):

| Scenario | Total call hours / month | Total FTE required |
| --- | ---: | ---: |
| Current mapping | 2735.00 | 20.037 |
| Low Touch = 30-min/qtr | 2541.00 | 18.615 |
| Delta | -194.00 | -1.420 |

## 3) Rules for each bucket (what makes White Glove, etc.)

Rules are implemented in `tier_dashboard.py`:

### Inputs used

- **Total Usage MRR** = sum of product MRR columns present
- **Product Count** = number of product columns with MRR > 0

### Revenue Tier rules (`assign_revenue_tier`)

- **High**: `Total Usage MRR >= 2000`
- **Mid**: `Total Usage MRR >= 1000` and `< 2000`
- **Low**: `Total Usage MRR < 1000`

### VUM Tier rules (`assign_vum_tier`)

- **High**: `VUM Total >= 80`
- **Mid**: `VUM Total >= 40` and `< 80`
- **Low**: `VUM Total < 40`

### Account Priority Tier rules (`assign_priority_tier`)

- **White Glove**
  - `Revenue Tier == High`
  - AND `VUM Tier == High`
  - AND `Product Count >= 3`

- **Growth**
  - (`Revenue Tier == Mid` AND (`VUM Tier == High` OR `Product Count >= 3`))
  - OR (`Revenue Tier == Low` AND `VUM Tier == High` AND `Product Count >= 3`)

- **Low Touch**
  - `Revenue Tier == Low`
  - AND `VUM Tier == Low`
  - AND `Product Count <= 1`

- **Strategic**
  - Default bucket for any account not matching the above rules

### Engagement mapping (calls) currently in the dashboard

| Account Priority Tier | CSM Call Hours / Month |
| --- | ---: |
| White Glove | 2.0 |
| Growth | 1.0 |
| Strategic | 1.0 |
| Low Touch | 0.3333 (1.0/3.0) |
