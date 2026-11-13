"""Exact-decimal equity valuation models.

Inputs and returned values use Decimal so calculations do not silently pass
through binary floating point.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from typing import Iterable


class ValuationError(ValueError):
    """Raised when valuation assumptions are incomplete or invalid."""


def decimal_value(value: object, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValuationError(f"{field} must be a decimal number") from exc
    if not result.is_finite():
        raise ValuationError(f"{field} must be finite")
    return result


def decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def earnings_multiple(payload: dict[str, object]) -> dict[str, object]:
    eps = decimal_value(payload.get("normalized_eps"), "normalized_eps")
    fair_pe = decimal_value(payload.get("fair_pe"), "fair_pe")
    if eps <= 0:
        raise ValuationError("normalized_eps must be greater than zero")
    if fair_pe <= 0 or fair_pe > 100:
        raise ValuationError("fair_pe must be greater than zero and no more than 100")

    value = eps * fair_pe
    result: dict[str, object] = {
        "estimated_value_per_share": decimal_text(value),
        "formula": "normalized EPS × fair P/E",
    }
    market_raw = payload.get("market_price")
    if market_raw not in (None, ""):
        market = decimal_value(market_raw, "market_price")
        if market <= 0:
            raise ValuationError("market_price must be greater than zero")
        result["upside_percent"] = decimal_text((value - market) / market * 100)

    target_raw = payload.get("target_price")
    if target_raw not in (None, ""):
        target = decimal_value(target_raw, "target_price")
        if target <= 0:
            raise ValuationError("target_price must be greater than zero")
        result["required_eps"] = decimal_text(target / fair_pe)
        result["required_pe"] = decimal_text(target / eps)
    return result


def equity_dcf(payload: dict[str, object]) -> dict[str, object]:
    starting = decimal_value(payload.get("starting_fcfe"), "starting_fcfe")
    years_raw = payload.get("forecast_years")
    try:
        years = int(str(years_raw))
    except (TypeError, ValueError) as exc:
        raise ValuationError("forecast_years must be 5 or 10") from exc
    discount = decimal_value(payload.get("discount_rate"), "discount_rate")
    terminal_growth = decimal_value(
        payload.get("terminal_growth_rate"), "terminal_growth_rate"
    )
    cash = decimal_value(payload.get("non_operating_cash", "0"), "non_operating_cash")
    debt = decimal_value(payload.get("debt_adjustment", "0"), "debt_adjustment")
    shares = decimal_value(payload.get("diluted_shares"), "diluted_shares")
    margin = decimal_value(payload.get("margin_of_safety", "0"), "margin_of_safety")

    if starting <= 0:
        raise ValuationError("starting_fcfe must be greater than zero")
    if years not in (5, 10):
        raise ValuationError("forecast_years must be 5 or 10")
    if discount <= 0 or discount > Decimal("0.50"):
        raise ValuationError("discount_rate must be between 0 and 0.50")
    if terminal_growth < Decimal("-0.10") or terminal_growth >= discount:
        raise ValuationError("terminal_growth_rate must be at least -0.10 and below discount_rate")
    if shares <= 0:
        raise ValuationError("diluted_shares must be greater than zero")
    if margin < 0 or margin >= 1:
        raise ValuationError("margin_of_safety must be in [0, 1)")

    growth_raw = payload.get("growth_rates")
    if not isinstance(growth_raw, list):
        growth_raw = [payload.get("growth_rate")]
    growth_rates = [decimal_value(item, "growth_rates") for item in growth_raw]
    if len(growth_rates) not in (1, years):
        raise ValuationError(f"growth_rates must contain one rate or {years} annual rates")
    if any(rate < -1 or rate > 2 for rate in growth_rates):
        raise ValuationError("each growth rate must be between -1.0 and 2.0")

    with localcontext() as context:
        context.prec = 34
        cash_flow = starting
        forecast_value = Decimal("0")
        projections: list[dict[str, object]] = []
        for year in range(1, years + 1):
            growth = growth_rates[0] if len(growth_rates) == 1 else growth_rates[year - 1]
            cash_flow *= Decimal("1") + growth
            present_value = cash_flow / ((Decimal("1") + discount) ** year)
            forecast_value += present_value
            projections.append(
                {
                    "year": year,
                    "cash_flow": decimal_text(cash_flow),
                    "present_value": decimal_text(present_value),
                }
            )

        terminal_value = (
            cash_flow * (Decimal("1") + terminal_growth) / (discount - terminal_growth)
        )
        present_terminal = terminal_value / ((Decimal("1") + discount) ** years)
        equity_value = forecast_value + present_terminal + cash - debt
        value_per_share = equity_value / shares
        result: dict[str, object] = {
            "methodology": "equity DCF using levered free cash flow (FCFE proxy) discounted at cost of equity",
            "projections": projections,
            "pv_forecast": decimal_text(forecast_value),
            "terminal_value": decimal_text(terminal_value),
            "pv_terminal": decimal_text(present_terminal),
            "estimated_equity_value": decimal_text(equity_value),
            "value_per_share": decimal_text(value_per_share),
            "buy_below_price": decimal_text(value_per_share * (Decimal("1") - margin)),
        }
        market_raw = payload.get("market_price")
        if market_raw not in (None, ""):
            market = decimal_value(market_raw, "market_price")
            if market <= 0:
                raise ValuationError("market_price must be greater than zero")
            result["upside_percent"] = decimal_text(
                (value_per_share - market) / market * 100
            )
        return result
