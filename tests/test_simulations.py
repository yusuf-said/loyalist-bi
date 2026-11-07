"""Independent source regression: MIP JSON, Excel cached cells and original JS in Node."""

import json
import shutil
import subprocess
import time
from pathlib import Path

import openpyxl
import pytest

from flyup3.loader import sources_available
from flyup3.sim import (
    simulate_capacity_w48,
    simulate_churn_risk,
    simulate_loyalty_cost,
    simulate_program_roi,
)
from flyup3.sim.capacity import solve

ROOT = Path(__file__).resolve().parents[1]
# Referans dosyaları (mip/, Excel, dashboard/) git dışında; klonlarda bu testler atlanır.
requires_sources = pytest.mark.skipif(
    not sources_available(ROOT), reason="kaynak vaka dosyaları git dışında"
)
requires_node = pytest.mark.skipif(
    not (
        sources_available(ROOT)
        and (shutil.which("node") or Path("/opt/homebrew/bin/node").exists())
    ),
    reason="kaynak dosyalar veya Node yok",
)
SCENARIOS = {
    "urun_onceligi": {
        "relationship": False,
        "delay": True,
        "priority": True,
        "allow_charter": False,
    },
    "oneri_b": {
        "relationship": False,
        "delay": True,
        "priority": True,
        "allow_charter": False,
        "passive_consent": False,
    },
    "s1_mudahalesiz": {
        "relationship": False,
        "delay": True,
        "priority": True,
        "allow_charter": False,
        "passive_consent": False,
        "caps": {"rfs": 0, "pzt": 0},
    },
    "s0_iptal_oncesi": {
        "relationship": False,
        "delay": True,
        "priority": True,
        "allow_charter": False,
        "caps": {"krg": 200, "akt": 40},
    },
    "saf_katki": {"relationship": False},
    "iliski_maliyetli": {},
    "pasif_onayi_yok": {"passive_consent": False},
    "nord_disinda_herkes_kesilemez": {"p_override": {"Veloce": 0.9, "Bella": 0.9, "Medivia": 0.9}},
}


@requires_sources
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_capacity_all_original_scenarios(scenario):
    source = json.loads((ROOT / "mip/mip_sonuclari.json").read_text())["scenarios"][scenario]
    result = solve(**SCENARIOS[scenario])
    for key in ("rows", "net48", "def49", "contrib"):
        assert result[key] == source[key], (scenario, key)


def test_capacity_tool_and_charter_threshold():
    a = simulate_capacity_w48()["results"]
    b = simulate_capacity_w48(passive_consent=False)["results"]
    assert (a["net48"], a["contrib"], a["unserved_tons"]) == (390900, 102725, 1)
    assert (b["net48"], b["contrib"], b["unserved_tons"]) == (374200, 99600, 8)
    # Saf katkıda 1 ton kurtarma + kaçınılan RFS maliyeti; kaynak kısıtlarıyla hesaplanır.
    pure = simulate_capacity_w48(rule="pure_contribution")["results"]
    assert pure["charter_break_even"]["max_justified_cost"] == 4275
    assert (
        simulate_capacity_w48(capacities={"krg": 200, "akt": 40})["results"]["unserved_tons"] == 0
    )


def test_capacity_charter_required_and_impossible_caps():
    result = simulate_capacity_w48(allow_charter=True, capacities={"krg": 30})["results"]
    assert result["charter"] == 1
    assert result["charter_break_even"]["max_justified_cost"] is None
    assert result["charter_break_even"]["without_charter_feasible"] is False
    with pytest.raises(ValueError, match="allotment"):
        simulate_capacity_w48(capacities={"krg": 0})
    assert (
        simulate_capacity_w48(rule="relationship_cost", allow_charter=True, p={"Nord": 0})[
            "inputs"
        ]["p"]["Nord"]
        == 0
    )


@pytest.fixture(scope="module")
def excel():
    book = openpyxl.load_workbook(ROOT / "FlyUp3_Cozum_Modeli.xlsx", data_only=True)
    yield book["Sadakat"]
    book.close()


@requires_sources
def test_loyalty_against_calculated_excel_cells(excel):
    result = simulate_loyalty_cost()["results"]
    for key, cell, expected in (
        ("fixed", "H39", 52200),
        ("rebate", "H43", 49879.5),
        ("total", "H45", 102079.5),
        ("budget_utilization", "B60", 0.5103975),
        ("break_even_revenue", "B63", 408318),
    ):
        assert result[key] == pytest.approx(excel[cell].value)
        assert result[key] == pytest.approx(expected)
    assert result["stress"]["total"] == excel["H46"].value == 116114.5
    for col, row in enumerate(result["customers"], 2):
        assert row["tier"] == excel.cell(30, col).value
        for key, cellrow in (("fixed", 39), ("rebate", 43), ("total", 45)):
            assert row[key] == pytest.approx(excel.cell(cellrow, col).value)
    for col, row in enumerate(result["stress"]["customers"], 2):
        assert row["total"] == pytest.approx(excel.cell(46, col).value)


def test_loyalty_overrides_are_local_and_apply_caps():
    r = simulate_loyalty_cost(
        tier_overrides={"Nord": "Elite"},
        benefit_overrides={"Elite": {"rate": 1, "cap": 25000, "base": "total", "cip": 1}},
        growth_overrides={"Nord": 0},
        stress_growth_overrides={"Nord": 0.1},
        visit_overrides={"Nord": 1},
    )["results"]
    nord = next(x for x in r["customers"] if x["customer"] == "Nord")
    assert nord["rebate"] == 25000
    assert nord["fixed"] == 4000 + 3000 + 1500 + 800
    assert simulate_loyalty_cost()["results"]["total"] == pytest.approx(102079.5)
    assert simulate_loyalty_cost(benefit_overrides={"Classic Plus": {"dijital": 0}})["results"][
        "total"
    ] == pytest.approx(100079.5)


def js_reference(options=None):
    node = shutil.which("node") or "/opt/homebrew/bin/node"
    # Node and original reference files are required for this source regression suite.
    return json.loads(
        subprocess.check_output(
            [node, str(ROOT / "scripts/simulation_reference.cjs"), json.dumps(options or {})],
            text=True,
            timeout=10,
        )
    )


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"impact": 0.25},
        {"impact": 0.75, "margin": 0.35, "rebate": 0.02, "opp": 25000},
        {"impact": 0, "margin": 0, "rebate": 0.005, "opp": 10000},
    ],
)
@requires_node
def test_roi_against_original_javascript(options):
    ref = js_reference(options)
    kwargs = {
        ("rebate_multiplier" if k == "rebate" else "opportunity_cost" if k == "opp" else k): (
            v / 0.01 if k == "rebate" else v
        )
        for k, v in options.items()
    }
    r = simulate_program_roi(**kwargs)["results"]
    assert r["economy"] == pytest.approx(ref["economy"])
    assert r["stress_economy"] == pytest.approx(ref["stress"])
    assert r["break_even_impact"] == pytest.approx(ref["break_even_impact"])
    assert r["sensitivity"]["runs"] == ref["grid"]["runs"] == 108
    assert r["sensitivity"]["positive"] == ref["grid"]["positive"] == 52
    for cell, js in zip(r["sensitivity"]["grid"], ref["grid"]["cells"], strict=True):
        assert cell == pytest.approx(js)
    for series, js in zip(r["series_52_weeks"], ref["series"]):
        assert series["points"] == pytest.approx(js["pts"])
    assert r["net_52_weeks"] == pytest.approx(r["economy"]["net"])


def test_roi_horizon_and_reference_notes():
    r = simulate_program_roi(weeks=26)["results"]
    assert len(r["cumulative_net"]) == 26
    assert r["net_52_weeks"] == pytest.approx(71301.75)
    assert r["break_even_impact"] == 0.30
    assert simulate_program_roi(impact=0.25)["results"]["net_52_weeks"] == pytest.approx(-15388.875)


@requires_node
def test_churn_against_original_javascript():
    ref = js_reference()
    r = simulate_churn_risk()["results"]["customers"]
    for row, js in zip(r, ref["ev"]):
        assert row["customer"] == js["c"]["id"]
        assert row["score"] == js["ews"]
        assert row["level"] == js["lvl"]["t"]
        assert row["uncertainty"] == js["u"]["pts"]
        w = row["worst_case"]
        assert w["score_now"] == pytest.approx(js["score"])
        assert w["score_pessimistic"] == pytest.approx(js["pess"])
        assert w["tier_now"] == js["tier"]
        assert w["tier_pessimistic"] == js["pessTier"]
    assert {x["customer"]: x["score"] for x in r} == {
        "Nord": 100,
        "Medivia": 20,
        "Veloce": 30,
        "Lago": 14,
        "Rossi": 10,
        "Bella": 5,
    }
    assert {x["customer"]: x["uncertainty"] for x in r if x["uncertainty"]} == {
        "Nord": 45,
        "Rossi": 40,
        "Veloce": 30,
    }


def test_churn_overrides():
    rows = simulate_churn_risk(
        signal_overrides={"Nord": {"volume": 0, "offload": 0}},
        uncertainty_overrides={"Medivia": 100},
    )["results"]["customers"]
    nord = next(x for x in rows if x["customer"] == "Nord")
    med = next(x for x in rows if x["customer"] == "Medivia")
    assert nord["score"] == 80
    assert med["worst_case"]["tier_pessimistic"] == "Elite"
    assert med["worst_case"]["score_pessimistic"] < med["worst_case"]["score_now"]


@pytest.mark.parametrize(
    ("fn", "kwargs"),
    [
        (simulate_capacity_w48, {"p": {"Nord": -0.1}}),
        (simulate_capacity_w48, {"p": {"Nord": 1.01}}),
        (simulate_capacity_w48, {"p": {"Nord": float("nan")}}),
        (simulate_capacity_w48, {"capacities": {"bel": -1}}),
        (simulate_capacity_w48, {"capacities": {"typo": 30}}),
        (simulate_capacity_w48, {"rule": "typo"}),
        (simulate_program_roi, {"impact": 1.01}),
        (simulate_program_roi, {"margin": -0.1}),
        (simulate_program_roi, {"weeks": 0}),
        (simulate_program_roi, {"weeks": 52.5}),
        (simulate_loyalty_cost, {"benefit_overrides": {"Elite": {"rate": 1.01}}}),
        (simulate_loyalty_cost, {"tier_overrides": {"Nord": "typo"}}),
        (simulate_churn_risk, {"uncertainty_overrides": {"Nord": 101}}),
        (simulate_churn_risk, {"signal_overrides": {"Nord": {"rival": 16}}}),
        (simulate_churn_risk, {"signal_overrides": {"Nord": {"typo": 10}}}),
    ],
)
def test_invalid_inputs(fn, kwargs):
    with pytest.raises(ValueError):
        fn(**kwargs)


@pytest.mark.parametrize(
    ("fn", "key"),
    [
        (simulate_capacity_w48, "p"),
        (simulate_loyalty_cost, "tier_overrides"),
        (simulate_loyalty_cost, "growth_overrides"),
        (simulate_loyalty_cost, "visit_overrides"),
        (simulate_loyalty_cost, "stress_growth_overrides"),
        (simulate_churn_risk, "signal_overrides"),
        (simulate_churn_risk, "uncertainty_overrides"),
    ],
)
def test_unknown_customer_is_clear(fn, key):
    with pytest.raises(ValueError, match="Bilinmeyen müşteri.*Typo"):
        fn(**{key: {"Typo": 0}})


@pytest.mark.parametrize(
    "fn", [simulate_capacity_w48, simulate_loyalty_cost, simulate_program_roi, simulate_churn_risk]
)
def test_json_contract_and_speed(fn):
    start = time.perf_counter()
    r = fn()
    assert time.perf_counter() - start < 2
    assert set(r) == {"inputs", "results", "summary", "assumptions"}
    assert r["summary"] and r["assumptions"]
    json.dumps(r, allow_nan=False)
