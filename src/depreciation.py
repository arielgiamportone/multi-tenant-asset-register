"""Explainable straight-line depreciation for a public-sector fixed-asset register.

Three ideas, each from a real failure mode:

1. Money is `Decimal` rounded HALF_UP to the cent, never float and never
   Python's `round()` (banker's rounding) - the legacy system being replaced
   rounded half up, and a one-cent drift across thousands of assets is a failed
   reconciliation.
2. Every result carries a *calculation memo*: where each input came from
   (asset field, per-tenant table, default) and which rule applied. An auditor
   can ask "why this number?" and get an answer without reading code.
3. Annual revaluation by coefficient is guarded by state, not by discipline:
   coefficients compound, so running the job twice silently inflates values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Mapping

CENT = Decimal("0.01")
ZERO = Decimal("0")

# Indicative useful lives (years) when neither the asset nor the tenant says otherwise.
DEFAULT_LIFE = {"building": 50, "green_area": 25, "vehicle": 10, "furniture": 10,
                "equipment": 8}


def money(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Asset:
    id: str
    category: str                    # building | vehicle | furniture | heritage | land ...
    cost: Decimal                    # historical cost (acquisition price)
    start: date | None               # date put into service
    land_value: Decimal = ZERO       # land share of a building's cost
    residual: Decimal = ZERO         # residual value for assets without land
    useful_life: int | None = None   # years, if the asset record sets it
    owned: bool = True               # assets on loan/assigned are not depreciated here
    loaded_accumulated: Decimal | None = None  # balance from an approved closing


@dataclass
class Result:
    asset_id: str
    depreciable: bool
    accumulated: Decimal = ZERO
    charge_for_year: Decimal = ZERO
    net_book_value: Decimal = ZERO
    memo: dict = field(default_factory=dict)


def months_in_service(start: date, as_of: date) -> int:
    """Months counted inclusively: an asset put into service on the 31st still
    accrues that whole month. This matches the legacy convention; it is a
    policy choice, so it lives in one function with its own tests."""
    if as_of < start:
        return 0
    return (as_of.year - start.year) * 12 + (as_of.month - start.month) + 1


def _not_depreciable_reason(a: Asset) -> str | None:
    # Accounting rules first, data problems second: a heritage item with no
    # date is "heritage", not "missing date".
    if a.category == "heritage":
        return "historical/artistic heritage is not depreciated"
    if a.category == "land":
        return "land has an indefinite useful life"
    if not a.owned:
        return "asset is not owned by this entity"
    if a.cost <= 0:
        return "no cost recorded"
    if a.start is None:
        return "no in-service date"
    return None


def _useful_life(a: Asset, tenant_lives: Mapping[str, int]) -> tuple[int, str]:
    if a.useful_life:
        return a.useful_life, "asset record"
    if a.category in tenant_lives:
        return tenant_lives[a.category], "tenant table"
    return DEFAULT_LIFE.get(a.category, 10), "default by category"


def _base(a: Asset) -> tuple[Decimal, str]:
    if a.land_value > 0:
        # Land is excluded from the base *and is* the residual: subtracting
        # `residual` as well would count the land twice.
        return a.cost - a.land_value, "cost minus land (land acts as residual)"
    if a.residual > 0:
        return a.cost - a.residual, "cost minus residual value"
    return a.cost, "full cost, no residual"


def accumulated_at(a: Asset, as_of: date, life_years: int) -> Decimal:
    base, _ = _base(a)
    months = min(months_in_service(a.start, as_of), life_years * 12)
    return min(money(base * months / (life_years * 12)), base)


def depreciate(a: Asset, as_of: date,
               tenant_lives: Mapping[str, int] | None = None) -> Result:
    reason = _not_depreciable_reason(a)
    if reason:
        return Result(a.id, False, net_book_value=money(a.cost),
                      memo={"rule": reason})

    life, life_source = _useful_life(a, tenant_lives or {})
    base, base_rule = _base(a)
    memo = {"base": str(money(base)), "base_rule": base_rule,
            "useful_life_years": life, "useful_life_source": life_source,
            "method": "straight-line, monthly, inclusive start month"}

    if a.loaded_accumulated is not None:
        # Balances from an approved closing are respected, not recomputed:
        # the register must agree with accounts that were already signed off.
        acc = money(a.loaded_accumulated)
        memo["balance_source"] = "loaded from approved closing"
        return Result(a.id, True, acc, ZERO, money(a.cost - acc), memo)

    acc = accumulated_at(a, as_of, life)
    prev = accumulated_at(a, date(as_of.year - 1, 12, 31), life)
    memo["balance_source"] = "computed"
    return Result(a.id, True, acc, acc - prev, money(a.cost - acc), memo)


# ---------------------------------------------------------------- revaluation

@dataclass(frozen=True)
class Valuation:
    replacement_cost: Decimal
    accumulated: Decimal
    life_years: int
    revalued_through: int  # last year whose coefficient is already applied

    @property
    def net(self) -> Decimal:
        return self.replacement_cost - self.accumulated


def revalue(v: Valuation, coefficients: Mapping[int, Decimal], up_to: int) -> Valuation:
    """Roll a replacement-cost valuation forward one year per coefficient.

    Each year: cost *= coef; the accumulated depreciation is revalued with the
    *same* coefficient before adding the year's charge (leaving that term out
    is the classic calibration miss: totals drift a little every year).

    Idempotent by construction: the valuation records the last year applied,
    so a second run with the same `up_to` is a no-op instead of compounding.
    A missing year raises rather than silently skipping it.
    """
    cost, acc, year = v.replacement_cost, v.accumulated, v.revalued_through
    for y in range(year + 1, up_to + 1):
        if y not in coefficients:
            raise KeyError(f"no coefficient for {y}")
        c = coefficients[y]
        cost = money(cost * c)
        annual = money(cost / v.life_years) if v.life_years else ZERO
        acc = min(money(acc * c) + annual, cost)
    return Valuation(cost, acc, v.life_years, max(year, up_to))
