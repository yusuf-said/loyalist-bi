"""Sadakat sayfası ve panelin loyalty() hesaplaması; kaynak dosyaya erişmeden çalışır."""

from copy import deepcopy

from .common import CUSTOMERS, DATA, customer_keys, keys, number, response

TIERS = {
    "Medivia": "Elite Plus",
    "Nord": "Classic",
    "Bella": "Elite",
    "Veloce": "Elite",
    "Lago": "Classic",
    "Rossi": "Classic Plus",
}


def loyalty_rows(tiers, benefits, growth, visits):
    unit = DATA["unit"]
    rows = []
    for cid, c in CUSTOMERS.items():
        b = benefits[tiers[cid]]
        count = visits.get(cid, b["ziy"])
        digital = unit["dijital"] * b.get("dijital", 1) if c["dig"] < 50 else 0
        fixed = sum(b[k] * unit[k] for k in ("cip", "s247", "zirve", "karne"))
        fixed += digital + count * unit["ziyaret"]
        g = growth[cid]
        base = (
            c["rev"] * (1 + g)
            if b["base"] == "total"
            else (c["rev"] * g if b["base"] == "above" else 0)
        )
        rebate = min(b["cap"], b["rate"] * base)
        rows.append(
            {
                "customer": cid,
                "tier": tiers[cid],
                "fixed": fixed,
                "rebate": rebate,
                "total": fixed + rebate,
                "growth": g,
                "visits": count,
                "digital_training": digital,
            }
        )
    return rows


def simulate_loyalty_cost(
    tier_overrides: dict[str, str] | None = None,
    benefit_overrides: dict[str, dict] | None = None,
    growth_overrides: dict[str, float] | None = None,
    stress_growth_overrides: dict[str, float] | None = None,
    visit_overrides: dict[str, int] | None = None,
) -> dict:
    """Sadakat maliyetini hesaplar; avantajlar kademe, büyüme/ziyaret müşteri bazındadır."""
    for value in (tier_overrides, growth_overrides, stress_growth_overrides, visit_overrides):
        customer_keys(value)
    tiers = {**TIERS, **(tier_overrides or {})}
    for tier in tiers.values():
        if tier not in DATA["benefits"]:
            raise ValueError(f"Bilinmeyen kademe: {tier}")
    benefits = deepcopy(DATA["benefits"])
    for benefit in benefits.values():
        benefit["dijital"] = 1  # Düşük dijital kullanımda eğitim; tüm kademelerde varsayılan.
    keys(benefit_overrides, benefits, "Kademe")
    for tier, overrides in (benefit_overrides or {}).items():
        keys(overrides, benefits[tier], "Avantaj")
        for key, value in overrides.items():
            if key == "base":
                if value not in ("total", "above", "-"):
                    raise ValueError("Rebate bazı: total, above veya - olmalı.")
            else:
                number(
                    value,
                    f"{tier}.{key}",
                    maximum=1
                    if key in ("cip", "s247", "zirve", "karne", "dijital", "rate")
                    else None,
                    integer=key in ("cip", "s247", "zirve", "karne", "dijital", "ziy"),
                )
        benefits[tier].update(overrides)
    growth = {**DATA["growth"]["baz"], **(growth_overrides or {})}
    stress_growth = {**DATA["growth"]["stres"], **(stress_growth_overrides or {})}
    for cid in CUSTOMERS:
        number(growth[cid], f"{cid} büyüme", minimum=-1)
        number(stress_growth[cid], f"{cid} stres büyüme", minimum=-1)
    visits = visit_overrides or {}
    for cid, value in visits.items():
        number(value, f"{cid} ziyaret", integer=True)
    rows = loyalty_rows(tiers, benefits, growth, visits)
    stress_rows = loyalty_rows(tiers, benefits, stress_growth, visits)
    fixed = sum(r["fixed"] for r in rows)
    rebate = sum(r["rebate"] for r in rows)
    total = fixed + rebate
    stress = sum(r["total"] for r in stress_rows)
    return response(
        {
            "tiers": tiers,
            "benefits": benefits,
            "growth": growth,
            "stress_growth": stress_growth,
            "visits": {r["customer"]: r["visits"] for r in rows},
            "budget": 200000,
            "margin": 0.25,
        },
        {
            "customers": rows,
            "fixed": fixed,
            "rebate": rebate,
            "total": total,
            "budget_utilization": total / 200000,
            "budget_remaining": 200000 - total,
            "break_even_revenue": total / 0.25,
            "stress": {
                "customers": stress_rows,
                "total": stress,
                "budget_utilization": stress / 200000,
                "break_even_revenue": stress / 0.25,
            },
        },
        f"Yıllık sadakat maliyeti {total:,.2f} USD, bütçe kullanımı %{total / 2000:.2f}. "
        f"Stres maliyeti {stress:,.2f} USD; başabaş için {total / 0.25:,.2f} USD gelir gerekir.",
        [
            "Kaynak: FlyUp3_Cozum_Modeli.xlsx Sadakat; kademeler panelin makale yöntemiyle aynıdır.",
            "Kurtarma ziyaretleri sadakat bütçesine dahil değildir; dijital eğitim ilk yıl maliyetidir.",
            "Rebate tavanı uygulanır; above bazında negatif büyüme kaynak JS gibi negatif rebate üretir.",
        ],
    )
