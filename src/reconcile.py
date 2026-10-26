"""Prove a migration to the cent before anyone looks at a screen.

When a tenant moves from a legacy system, the only acceptable result is that
cost, accumulated depreciation and net book value per ledger account match the
legacy closing exactly. "Close enough" hides real defects (a rounding rule, an
asset loaded twice, a coefficient applied twice) that later surface in an audit.

`reconcile()` compares per-account totals and, for every account that does not
match, points at the assets most likely responsible.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping

METRICS = ("cost", "accumulated", "net")


@dataclass(frozen=True)
class Row:
    asset_id: str
    account: str
    cost: Decimal
    accumulated: Decimal

    @property
    def net(self) -> Decimal:
        return self.cost - self.accumulated


@dataclass
class Mismatch:
    account: str
    metric: str
    ours: Decimal
    legacy: Decimal
    suspects: list[str]

    @property
    def delta(self) -> Decimal:
        return self.ours - self.legacy


def totals(rows: Iterable[Row]) -> dict[str, dict[str, Decimal]]:
    out: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {m: Decimal("0") for m in METRICS})
    for r in rows:
        for m in METRICS:
            out[r.account][m] += getattr(r, m)
    return dict(out)


def reconcile(ours: list[Row], legacy_totals: Mapping[str, Mapping[str, Decimal]],
              legacy_rows: Mapping[str, Row] | None = None) -> list[Mismatch]:
    """Return every (account, metric) that differs. Empty list = reconciled.

    Accounts present on only one side are mismatches too: a missing account is
    the most common symptom of a mapping table that lost a row.
    """
    mine = totals(ours)
    legacy_rows = legacy_rows or {}
    by_account: dict[str, list[Row]] = defaultdict(list)
    for r in ours:
        by_account[r.account].append(r)

    zero = {m: Decimal("0") for m in METRICS}
    issues = []
    for account in sorted(set(mine) | set(legacy_totals)):
        a, b = mine.get(account, zero), legacy_totals.get(account, zero)
        for m in METRICS:
            if a[m] != b[m]:
                issues.append(Mismatch(account, m, a[m], b[m],
                                       _suspects(by_account[account], legacy_rows, m)))
    return issues


def _suspects(rows: list[Row], legacy_rows: Mapping[str, Row], metric: str,
              limit: int = 5) -> list[str]:
    """Assets whose own value differs from legacy, largest gap first. Without
    legacy rows, assets the legacy side does not know about are listed."""
    scored = []
    for r in rows:
        old = legacy_rows.get(r.asset_id)
        gap = getattr(r, metric) - (getattr(old, metric) if old else Decimal("0"))
        if gap:
            scored.append((abs(gap), r.asset_id))
    return [asset for _, asset in sorted(scored, reverse=True)[:limit]]
