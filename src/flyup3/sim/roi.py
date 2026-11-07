"""Panelin programEcon() ve renderE2E() hesaplarının Python karşılığı."""

from itertools import product

from .churn import simulate_churn_risk
from .common import CUSTOMERS, DATA, number, response
from .loyalty import TIERS, loyalty_rows

IMPACTS = (0, 0.25, 0.5, 0.75)
MARGINS = (0.15, 0.25, 0.35)
REBATE_MULTIPLIERS = (0.5, 1, 2)
OPPORTUNITY_COSTS = (0, 10000, 25000)


def program_econ(impact, margin, rebate_multiplier, opportunity_cost, stress=1):
    rows = loyalty_rows(TIERS, DATA["benefits"], DATA["growth"]["baz"], {})
    risks = {r["customer"]: r["score"] for r in simulate_churn_risk()["results"]["customers"]}
    fixed = sum(r["fixed"] for r in rows)
    reb = sum(r["rebate"] for r in rows) * rebate_multiplier
    prot = sum(
        c["rev"] * min(1, risks[cid] / 200 * stress) * impact
        for cid, c in CUSTOMERS.items()
        if TIERS[cid] != "Classic"
    )
    neu = sum(
        CUSTOMERS[r["customer"]]["rev"] * r["growth"] * impact
        for r in rows
        if r["tier"] != "Classic"
    )
    return {
        "fixed": fixed,
        "reb": reb,
        "cost": fixed + reb,
        "prot": prot,
        "neu": neu,
        "net": (prot + neu) * margin - fixed - reb - opportunity_cost,
    }


def cumulative(econ, margin, opportunity_cost, weeks):
    q4 = sum(c["rev"] * c["q4"] / 100 for c in CUSTOMERS.values())
    q4 /= sum(c["rev"] for c in CUSTOMERS.values())
    value, points = 0, []
    for week in range(1, weeks + 1):
        weight = q4 / 13 if week >= 40 else (1 - q4) / 39
        value += (
            (econ["prot"] + econ["neu"]) * margin * weight
            - (econ["fixed"] + opportunity_cost) / 52
            - (econ["reb"] if week == 52 else 0)
        )
        points.append(value)
    return points


def simulate_program_roi(
    impact: float = 0.5,
    margin: float = 0.25,
    rebate_multiplier: float = 1,
    opportunity_cost: float = 0,
    weeks: int = 52,
) -> dict:
    """Programın yıllık katkısını ve 108 koşullu duyarlılığını hesaplar; hafta 1–52."""
    number(impact, "Etki", maximum=1)
    number(margin, "Marj", maximum=1)
    number(rebate_multiplier, "Rebate çarpanı")
    number(opportunity_cost, "Fırsat maliyeti")
    number(weeks, "Hafta sayısı", minimum=1, maximum=52, integer=True)
    weeks = int(weeks)
    econ = program_econ(impact, margin, rebate_multiplier, opportunity_cost)
    grid = [
        {
            "impact": i,
            "margin": m,
            "rebate_multiplier": r,
            "opportunity_cost": o,
            "net": program_econ(i, m, r, o)["net"],
        }
        for i, m, r, o in product(IMPACTS, MARGINS, REBATE_MULTIPLIERS, OPPORTUNITY_COSTS)
    ]
    # Kaynak JS 0.01 adımlı tarama yapar; analitik eşik ayrıca raporlanır.
    be = next(
        (
            i / 100
            for i in range(101)
            if program_econ(i / 100, margin, rebate_multiplier, opportunity_cost)["net"] >= 0
        ),
        None,
    )
    unit = program_econ(1, margin, rebate_multiplier, opportunity_cost)
    denominator = (unit["prot"] + unit["neu"]) * margin
    exact = (econ["cost"] + opportunity_cost) / denominator if denominator else None
    series = [
        {
            "impact": i,
            "points": cumulative(
                program_econ(i, margin, rebate_multiplier, opportunity_cost),
                margin,
                opportunity_cost,
                52,
            ),
        }
        for i in IMPACTS
    ]
    points = cumulative(econ, margin, opportunity_cost, weeks)
    net52 = cumulative(econ, margin, opportunity_cost, 52)[-1]
    return response(
        {
            "impact": impact,
            "margin": margin,
            "rebate_multiplier": rebate_multiplier,
            "opportunity_cost": opportunity_cost,
            "weeks": weeks,
        },
        {
            "economy": econ,
            "stress_economy": program_econ(
                impact, margin, rebate_multiplier, opportunity_cost, 1.5
            ),
            "cumulative_net": points,
            "horizon_net": points[-1],
            "net_52_weeks": net52,
            "break_even_impact": be,
            "break_even_impact_exact": exact,
            "series_52_weeks": series,
            "sensitivity": {
                "runs": len(grid),
                "positive": sum(g["net"] > 0 for g in grid),
                "min_net": min(g["net"] for g in grid),
                "max_net": max(g["net"] for g in grid),
                "grid": grid,
            },
        },
        f"52 haftalık net katkı {net52:,.2f} USD. "
        + (
            f"Program yaklaşık {be:.2f} etki düzeyinde kendini öder."
            if be is not None
            else "Program %100 etkide bile kendini ödemez."
        ),
        [
            "Kaynak: dashboard/index.html loyalty, programEcon ve renderE2E; makale kademeleri.",
            (
                "Korunan gelir = yıllık gelir × min(1, risk/200 × stres) × etki; "
                "Classic müşterilerin korunan/yeni geliri program getirisine dahil değildir."
            ),
            (
                "Sabit ve fırsat maliyeti 52 haftaya yayılır; rebate 52. haftada ödenir. "
                "Hafta parametresi ilk yılın 1–52 haftalık ufkudur; duyarlılık ızgarası yıllıktır."
            ),
        ],
    )
