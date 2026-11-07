"""Superset'ten bağımsız FlyUp3 simülasyonları."""

from .capacity import CAP, CHARTER, CUSTOMERS, solve
from .churn import simulate_churn_risk
from .common import customer_keys, keys, number, response
from .loyalty import simulate_loyalty_cost
from .roi import simulate_program_roi

__all__ = [
    "simulate_capacity_w48",
    "simulate_churn_risk",
    "simulate_loyalty_cost",
    "simulate_program_roi",
]


def simulate_capacity_w48(
    passive_consent: bool = True,
    allow_charter: bool = False,
    rule: str = "product_priority",
    p: dict[str, float] | None = None,
    delay_usd: float = 50,
    capacities: dict[str, float] | None = None,
) -> dict:
    """48. hafta MIP tahsisi; rule: product_priority, pure_contribution, relationship_cost.

    Kapasiteler ton: krg (kargo), bel (belly), akt (aktif), rfs, pzt (pazartesi).
    p, müşteri bazında offload sonrası kayıp olasılığıdır (0–1).
    """
    if not isinstance(passive_consent, bool) or not isinstance(allow_charter, bool):
        raise TypeError("passive_consent ve allow_charter boolean olmalı.")
    rules = {
        "product_priority": {"relationship": False, "delay": True, "priority": True},
        "pure_contribution": {"relationship": False},
        "relationship_cost": {"relationship": True},
    }
    if rule not in rules:
        raise ValueError("Bilinmeyen rule. İzin verilenler: " + ", ".join(rules))
    customer_keys(p)
    probabilities = {c: v[2] for c, v in CUSTOMERS.items()}
    probabilities.update(p or {})
    for cid, value in probabilities.items():
        number(value, f"{cid} kayıp olasılığı", maximum=1)
    keys(capacities, CAP, "Kapasite")
    caps = {**CAP, **(capacities or {})}
    for key, value in caps.items():
        number(value, key)
    number(delay_usd, "Gecikme maliyeti")
    kw = dict(
        p_override=probabilities,
        delay_usd=delay_usd,
        passive_consent=passive_consent,
        caps=caps,
        **rules[rule],
    )
    try:
        result = solve(allow_charter=allow_charter, **kw)
    except RuntimeError as error:
        if str(error) != "Infeasible":
            raise
        raise ValueError(
            "Bu kapasitelerle talep/ürün ve zorunlu allotment kısıtları birlikte sağlanamıyor."
        ) from error
    # Sabit kiralama maliyetini geri eklemek, bu iki optimal plan arasında
    # ödenebilecek en yüksek charter bedelini verir (öncelik cezası hariç).
    base = result
    if allow_charter:
        try:
            base = solve(allow_charter=False, **kw)
        except RuntimeError as error:
            if str(error) != "Infeasible":
                raise
            base = None
    charter = solve(allow_charter=True, force_charter=True, **kw)
    threshold = charter["objective"] + CHARTER["cost"] - base["objective"] if base else None
    result["unserved_tons"] = sum(r["yok"] for r in result["rows"])
    result["charter_break_even"] = {
        "max_justified_cost": threshold,
        "quoted_cost": CHARTER["cost"],
        "contribution_gain_before_charter_cost": (
            charter["contrib"] + CHARTER["cost"] - base["contrib"] if base else None
        ),
        "without_charter_feasible": base is not None,
        "basis": "İki haftalık katkı + seçili kuralın ilişki/gecikme etkisi; "
        "sözlüksel ürün önceliği cezası hariç.",
    }
    return response(
        {
            "passive_consent": passive_consent,
            "allow_charter": allow_charter,
            "rule": rule,
            "p": probabilities,
            "delay_usd": delay_usd,
            "capacities": caps,
        },
        result,
        f"48. hafta net gelir {result['net48']:,.0f} USD, iki haftalık katkı "
        f"{result['contrib']:,.0f} USD. Taşınamayan {result['unserved_tons']} ton; "
        f"charter {'seçildi' if result['charter'] else 'seçilmedi'}.",
        [
            "Kaynak: mip/mip_kapasite.py modelinin paket içi kopyası; tahsis tam tonludur.",
            "Marj %25; charter 55 ton / 95.000 USD, ilave aktif kapasite sağlamaz.",
            (
                "Pasif taşıma yazılı müşteri/kalite onayına bağlıdır. Ürün önceliği kuralı "
                "taşınmayan tonları önce sıralar; objective öncelik cezası çıkarılmış değerdir."
            ),
            *(
                []
                if base
                else [
                    "Charter olmadan allotment kısıtları sağlanamıyor; parasal başabaş tanımsızdır."
                ]
            ),
        ],
    )
