"""Panelin sinyal, belirsizlik, scoreOf ve makale kötü senaryo hesapları."""

from .common import CUSTOMERS, DATA, customer_keys, keys, number, response
from .loyalty import TIERS

SIGNAL_KEYS = (
    "volume",
    "competitor_share",
    "complaints",
    "csat",
    "nps",
    "contract",
    "visits",
    "offload",
    "rival",
    "decision_maker",
    "planned_offload",
)
SIGNAL_MAX = (20, 10, 10, 5, 5, 10, 5, 10, 15, 10, 10)


def signals(c):
    f = DATA["flags"][c["id"]]
    return dict(
        zip(
            SIGNAL_KEYS,
            (
                20 if c["vol"] <= -15 else 12 if c["vol"] <= -5 else 5 if c["vol"] < 0 else 0,
                10 if c["comp"] >= c["sow"] else 5 if c["comp"] >= c["sow"] / 2 else 0,
                10 if c["cmpl"] >= 5 else 5 if c["cmpl"] >= 3 else 0,
                5 if c["csat"] < 70 else 2 if c["csat"] < 80 else 0,
                5 if c["nps"] < 0 else 2 if c["nps"] < 20 else 0,
                10 if not c["contract"] or c["days"] <= 60 else 5 if c["days"] <= 120 else 0,
                5 if c["vd"] / c["vp"] < 0.75 else 0,
                10 if f["offload"] >= 2 else 5 if f["offload"] == 1 else 0,
                f["rival"] * 15,
                f["dm"] * 10,
                10 if c["id"] == "Nord" else 0,
            ),
        )
    )


def uncertainty(c):
    u = DATA["uncertainty"][c["id"]]
    return min(
        100,
        u["kusak"] * 40
        + u["karar"] * 30
        + u["kisa"] * 10
        + (15 if not c["contract"] or c["days"] <= 60 else 0)
        + (5 if c["vol"] >= 30 or c["q4"] >= 40 else 0),
    )


def score_of(c, drop=0):
    # indicator weights equal indWeight() with default dimension weights (35/25/20/20/0).
    getters = (
        c["rev"] / 1e6,
        c["yld"],
        c["sow"],
        c["csat"],
        c["nps"],
        c["cmpl"],
        c["ns"],
        c["pay"],
        c["dig"],
        c["allot"],
        c["vol"],
        c["prod"],
        c["st"],
    )
    numerator = denominator = 0
    for ind, value in zip(DATA["indicators"], getters):
        if value is None:
            continue
        band = next(
            (
                5 - i
                for i, th in enumerate(ind["th"])
                if (value >= th if ind["up"] else value <= th)
            ),
            1,
        )
        if ind["dim"] == "iliski":
            band = max(1, band - drop)
        numerator += ind["w"] * band / 5
        denominator += ind["w"]
    return numerator / denominator * 100


def paper_tier(c, attrs):
    loyal, profitable = c["sow"] >= 60, c["yld"] * 0.25 >= 0.5 - 1e-9
    if loyal and profitable:
        return "Elite Plus" if attrs["dostluk"] >= 5 else "Elite"
    return "Elite" if profitable else "Classic Plus" if loyal else "Classic"


def simulate_churn_risk(
    signal_overrides: dict[str, dict[str, float]] | None = None,
    uncertainty_overrides: dict[str, float] | None = None,
) -> dict:
    """Sinyal puanlarını ve müşteri belirsizliğini (0–100) değiştirip kötü senaryoyu hesaplar."""
    customer_keys(signal_overrides)
    customer_keys(uncertainty_overrides)
    rows = []
    used_signals, used_unc = {}, {}
    for cid, c in CUSTOMERS.items():
        parts = signals(c)
        overrides = (signal_overrides or {}).get(cid, {})
        keys(overrides, SIGNAL_KEYS, "Sinyal")
        for key, value in overrides.items():
            number(value, f"{cid}.{key}", maximum=SIGNAL_MAX[SIGNAL_KEYS.index(key)])
        parts.update(overrides)
        risk = min(100, sum(parts.values()))
        u = (uncertainty_overrides or {}).get(cid, uncertainty(c))
        number(u, f"{cid} belirsizlik", maximum=100)
        drop, reset = u / 20, min(1, u / 40)
        attrs = DATA["attributes"][cid].copy()
        for item in DATA["attribute_items"]:
            k = item["k"]
            if item.get("bag") == "kisi" and attrs[k] > 4:
                attrs[k] -= (attrs[k] - 4) * reset
        score, pess = score_of(c), score_of(c, drop)
        rows.append(
            {
                "customer": cid,
                "score": risk,
                "level": "KRİTİK"
                if risk >= 60
                else "YÜKSEK"
                if risk >= 35
                else "İZLE"
                if risk >= 15
                else "NORMAL",
                "signals": parts,
                "uncertainty": u,
                "discipline_alarm": c["ns"] > 15
                or c["pay"] > 30
                or (c["allot"] is not None and c["allot"] < 70),
                "worst_case": {
                    "band_drop": drop,
                    "personal_reset": reset,
                    "score_now": score,
                    "score_pessimistic": pess,
                    "score_delta": pess - score,
                    "tier_now": TIERS[cid],
                    "tier_pessimistic": paper_tier(c, attrs),
                },
            }
        )
        used_signals[cid], used_unc[cid] = parts, u
    critical = [r["customer"] for r in rows if r["score"] >= 60]
    return response(
        {
            "signals": used_signals,
            "uncertainty": used_unc,
            "allocation": "Plan A",
            "tier_mode": "makale",
        },
        {"customers": rows},
        f"Kritik riskteki müşteriler: {', '.join(critical) or 'yok'}. "
        "Kötü senaryo, ilişki göstergelerini ve kişiye bağlı maddeleri belirsizliğe göre düşürür.",
        [
            "Kaynak: dashboard/index.html; varsayılan saha girdileri ve Plan A kullanılır.",
            (
                "Risk skoru olasılık değildir; kötü senaryo ağırlıklı skoru etkiler, makale kademesi "
                "ayrı kuralla hesaplanır."
            ),
        ],
    )
