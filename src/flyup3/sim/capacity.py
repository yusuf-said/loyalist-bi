"""Kaynak: mip/mip_kapasite.py solve() modelinin bağımsız kopyası.

FlyUp3 – 48. hafta kapasite dağıtımı için karma tamsayılı programlama (MIP) modeli.

Karar: her gönderinin kaç tonu hangi yolla taşınır (aktif konteyner, pasif örtü,
kargo uçağı, yolcu uçağı belly, RFS kamyon, 49. hafta pazartesi, taşınmaz);
charter kiralanır mı; hangi müşteri bu hafta offload yaşar.

Amaç: iki haftalık katkı (gelir × %25) − kamyon − charter
      − beklenen müşteri kaybı maliyeti (offload yaşayan müşterinin yıllık katkısı × kayıp olasılığı)
      − gecikme maliyeti (ton × gün × müşterinin risk ağırlığı).

Çözücü: PuLP 2.9 + CBC. Çalıştırma:  .venv/bin/python mip/mip_kapasite.py
Çıktı: konsola sonuç tabloları, mip/mip_sonuclari.json
"""

import pulp

MARGIN = 0.25  # ortalama katkı marjı (vaka)
CAP = {
    "krg": 145,
    "bel": 30,
    "akt": 30,
    "rfs": 20,
    "pzt": 25,
}  # kargo uçağı, belly, aktif, RFS, 49H pazartesi
RFS_COST = 200  # USD/t (0,20 USD/kg)
PASSIVE_RATE = 2.40  # USD/kg
CHARTER = {
    "t": 55,
    "cost": 95000,
    "akt": 0,
}  # charter aktif konteyner kapasitesi teyit edilmedi → 0
DELAY_DAYS = {"rfs": 1.5, "pzt": 4.0}  # RFS ~36 saat, pazartesi ~4 gün

# Müşteri: yıllık gelir (CRM), kayıp riski skoru (erken uyarı) ve offload sonrası kayıp olasılığı (varsayım)
CUSTOMERS = {
    #          yıllık gelir USD, risk skoru, p(kayıp | bu hafta offload)
    "Medivia": (3_565_000, 20, 0.10),  # rakip peak aktif garanti veriyor
    "Nord": (3_570_000, 100, 0.50),  # yazılı: "bir offload daha yaşarsak rakibi imzalarız"
    "Bella": (1_218_000, 5, 0.20),  # defile tarihi sabit, kaçan koleksiyon telafi edilemez
    "Veloce": (798_000, 30, 0.20),  # "taşınamazsak yıllık anlaşmayı başkasıyla yaparız"
    "Lago": (1_620_000, 14, 0.05),
    "Rossi": (405_000, 10, 0.02),  # en sadık, 7 gün esnek
}

# Gönderiler: (müşteri, ad, talep t, USD/kg, izinli taşıma yolları, allotment grubu)
SHIPMENTS = [
    ("Medivia", "Pharma 2–8°C aşı", 28, 3.2, ["akt"], "A_Medivia"),
    ("Nord", "Pharma 15–25°C", 10, 2.6, ["akt", "pas"], None),
    ("Nord", "Genel – otomotiv (≤24 s)", 50, 1.1, ["krg", "bel"], "A_Nord"),
    ("Nord", "Genel – konsolidasyon (7 gün)", 30, 1.1, ["krg", "bel", "rfs", "pzt"], "A_Nord"),
    ("Bella", "Valuable – moda", 18, 3.0, ["krg"], None),
    ("Veloce", "Courier – e-ticaret (≤24 s)", 45, 2.3, ["krg"], None),
    ("Lago", "Fresh – taze gıda", 25, 1.9, ["krg"], "A_Lago"),
    ("Rossi", "Genel – makine (7 gün)", 15, 1.4, ["krg", "bel", "rfs", "pzt"], None),
]
ALLOTMENT = {
    "A_Medivia": 20,
    "A_Nord": 30,
    "A_Lago": 25,
}  # sözleşmeli, bu hafta havadan karşılanmalı
AIR_MODES = {"akt", "pas", "krg", "bel"}
FREIGHTER_MODES = {"akt", "pas", "krg"}
MODES = ["akt", "pas", "krg", "bel", "rfs", "pzt", "yok"]
# TK ürün öncelik listesi (organizatör): 1 en yüksek, 9 en düşük (TK General)
PRIORITY = [
    3,
    3,
    9,
    9,
    1,
    4,
    5,
    9,
]  # SHIPMENTS sırasıyla: pharma, pharma, genel, genel, valuable, courier, fresh, genel
PRIORITY_PENALTY = (
    1_000_000  # ton başına; öncelik kuralını ilişki maliyetinin önüne koyar (sözlük sırası)
)


def solve(
    p_override=None,
    delay_usd=50.0,
    passive_consent=True,
    allow_charter=True,
    relationship=True,
    priority=False,
    delay=None,
    caps=None,
    force_charter=None,
):
    cap = {**CAP, **(caps or {})}
    p = {c: v[2] for c, v in CUSTOMERS.items()}
    if p_override:
        p.update(p_override)
    m = pulp.LpProblem("FlyUp3_48H", pulp.LpMaximize)
    x = {}
    for i, (_, _, d, _, modes, _) in enumerate(SHIPMENTS):
        for k in modes + ["yok"]:
            x[i, k] = pulp.LpVariable(f"x_{i}_{k}", lowBound=0, upBound=d, cat="Integer")
    z = pulp.LpVariable("charter", cat="Binary")
    o = {c: pulp.LpVariable(f"offload_{c}", cat="Binary") for c in CUSTOMERS}

    def X(i, k):
        return x.get((i, k), 0)

    # amaç
    contrib = []
    for i, (c, _, d, r, modes, _) in enumerate(SHIPMENTS):
        unit = r * 1000 * MARGIN
        contrib += [
            unit * X(i, "akt"),
            PASSIVE_RATE * 1000 * MARGIN * X(i, "pas"),
            unit * X(i, "krg"),
            unit * X(i, "bel"),
            (unit - RFS_COST) * X(i, "rfs"),
            unit * X(i, "pzt"),
        ]
    churn = [o[c] * p[c] * CUSTOMERS[c][0] * MARGIN for c in CUSTOMERS] if relationship else []
    use_delay = relationship if delay is None else delay
    delay_terms = (
        [
            delay_usd
            * CUSTOMERS[c][1]
            / 100
            * (DELAY_DAYS["rfs"] * X(i, "rfs") + DELAY_DAYS["pzt"] * X(i, "pzt"))
            for i, (c, *_rest) in enumerate(SHIPMENTS)
        ]
        if use_delay
        else []
    )
    # ürün önceliği: taşınmayan tonun cezası önceliğe göre büyür; yalnız kesilecek yükü sıralar (charter kararına girmez)
    # aynı öncelikte zamana duyarlı yük (RFS/pazartesi kullanamayan) esnek yükten önce korunur
    flexible = [("rfs" in sh[4] or "pzt" in sh[4]) for sh in SHIPMENTS]
    prio_terms = (
        [
            PRIORITY_PENALTY * ((10 - PRIORITY[i]) + (0 if flexible[i] else 0.5)) * X(i, "yok")
            for i in range(len(SHIPMENTS))
        ]
        if priority
        else []
    )
    m += (
        pulp.lpSum(contrib)
        - CHARTER["cost"] * z
        - pulp.lpSum(churn)
        - pulp.lpSum(delay_terms)
        - pulp.lpSum(prio_terms)
    )

    # kısıtlar
    for i, (c, _, d, _, modes, _) in enumerate(SHIPMENTS):
        m += pulp.lpSum(X(i, k) for k in modes + ["yok"]) == d, f"talep_{i}"
        m += X(i, "yok") <= d * o[c], f"offload_bayragi_{i}"
    m += (
        pulp.lpSum(X(i, k) for i in range(len(SHIPMENTS)) for k in FREIGHTER_MODES)
        <= cap["krg"] + CHARTER["t"] * z,
        "kargo_ucagi",
    )
    m += pulp.lpSum(X(i, "bel") for i in range(len(SHIPMENTS))) <= cap["bel"], "belly"
    m += (
        pulp.lpSum(X(i, "akt") for i in range(len(SHIPMENTS))) <= cap["akt"] + CHARTER["akt"] * z,
        "aktif",
    )
    m += pulp.lpSum(X(i, "rfs") for i in range(len(SHIPMENTS))) <= cap["rfs"], "rfs"
    m += pulp.lpSum(X(i, "pzt") for i in range(len(SHIPMENTS))) <= cap["pzt"], "pazartesi"
    if not passive_consent:
        for i in range(len(SHIPMENTS)):
            if (i, "pas") in x:
                m += x[i, "pas"] == 0, f"pasif_onay_yok_{i}"
    if not allow_charter:
        m += z == 0, "charter_yok"
    if force_charter is not None:
        m += z == int(force_charter), "charter_sabit"
    for g, need in ALLOTMENT.items():
        m += (
            pulp.lpSum(X(i, k) for i, s in enumerate(SHIPMENTS) if s[5] == g for k in AIR_MODES)
            >= need,
            f"allotment_{g}",
        )

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(pulp.LpStatus[status])

    rows = []
    for i, (c, name, d, r, modes, _) in enumerate(SHIPMENTS):
        alloc = {k: round(pulp.value(x[i, k])) if (i, k) in x else 0 for k in MODES}
        rows.append({"cust": c, "name": name, "t": d, "r": r, **alloc})
    rev48 = sum(
        (rw["akt"] + rw["krg"] + rw["bel"]) * rw["r"] * 1000
        + rw["pas"] * PASSIVE_RATE * 1000
        + rw["rfs"] * rw["r"] * 1000
        for rw in rows
    )
    rfs_t = sum(rw["rfs"] for rw in rows)
    zc = round(pulp.value(z))
    rev49 = sum(rw["pzt"] * rw["r"] * 1000 for rw in rows)
    return {
        "rows": rows,
        "charter": zc,
        "offload": [c for c in CUSTOMERS if any(rw["cust"] == c and rw["yok"] > 0 for rw in rows)],
        "net48": rev48 - rfs_t * RFS_COST - zc * CHARTER["cost"],
        "def49": rev49,
        "contrib": sum(pulp.value(t) if not isinstance(t, (int, float)) else t for t in contrib)
        - zc * CHARTER["cost"],
        "objective": pulp.value(m.objective)
        + (
            sum(
                PRIORITY_PENALTY
                * (
                    (10 - PRIORITY[i])
                    + (0 if ("rfs" in SHIPMENTS[i][4] or "pzt" in SHIPMENTS[i][4]) else 0.5)
                )
                * rows[i]["yok"]
                for i in range(len(rows))
            )
            if priority
            else 0
        ),
        "p": p,
    }
