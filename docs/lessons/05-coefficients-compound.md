# Revaluation coefficients compound, and the missing term

Each year, replacement cost is updated with an official coefficient per asset class. Two separate
problems showed up.

## 1. Calibration: ~60 % matched, then 100 %

**Symptom.** Rolling one tenant's valuation forward a year and comparing it with the legacy system,
asset by asset, only ~60 % matched. The differences were small, and none of them were rounding.

**Cause.** The engine multiplied the replacement cost by the coefficient and added the year's
depreciation charge, but left the **accumulated depreciation** at its old nominal value. The
legacy system revalues it with the same coefficient first.

**Fix.**

```python
cost = money(cost * coef)
annual = money(cost / life_years)
accumulated = min(money(accumulated * coef) + annual, cost)
```

With that term, **100 % of ~2,300 assets matched with a delta of 0.00**. It was calibrated against
two consecutive legacy year-end snapshots, not against expectations.

## 2. Running it twice

**Symptom.** A rerun of the yearly update during testing raised a tenant's total replacement cost
by about 2 %, with no error.

**Cause.** Multiplying by a coefficient is not idempotent: `x × 1.02 × 1.02 ≠ x × 1.02`.

**Fix.** The state records the last year applied, and the operation only applies later years. A
second run is a no-op. The API answers *409 Conflict* unless an explicit "reapply" flag is
given, and every run writes a per-asset log that can reverse it. The operation is a dry run by
default.

**How it stays fixed.** In the [demo](../../src/depreciation.py) `revalue()` carries
`revalued_through`. Tests cover the double run, the missing year (which raises instead of
skipping) and the revalued accumulated term.
