"""Gerçek HTTP üzerinden /health, dashboard sorguları ve resmi MCP smoke testi."""

import asyncio
import json
import os
import signal
import socket
import subprocess
import time
from collections import Counter
from copy import deepcopy

import requests

from flyup3.branding import DARK_LOGO_URL, FAVICON_URL, LOGO_URL
from flyup3.palette import LABEL_COLORS
from flyup3.settings import OUT, ROOT, prepare_superset_env


def wait_http(url, process, timeout=50):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Servis kapandı (kod {process.returncode}): {url}")
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                return response
        except requests.RequestException:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"Servis {timeout}s içinde hazır olmadı: {url}")


async def verify_mcp():
    from fastmcp import Client

    async with Client("http://127.0.0.1:5018/mcp", timeout=15) as client:
        tools = await client.list_tools()
        names = [tool.name for tool in tools]
        assert "health_check" in names, names
        result = await client.call_tool("health_check", {})
        assert not result.is_error
        instance = await client.call_tool("get_instance_info", {})
        assert not instance.is_error
        return names


def main():
    prepare_superset_env()
    for port in (8098, 5018):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"Geçici test portu {port} zaten kullanımda.")
    processes = []
    logs = []
    report = {}
    try:
        for name, arguments in [
            ("web", ["run", "-h", "127.0.0.1", "-p", "8098", "--no-reload"]),
            ("mcp", ["mcp", "run", "--host", "127.0.0.1", "--port", "5018"]),
        ]:
            log = (OUT / f"{name}_smoke.log").open("w")
            logs.append(log)
            processes.append(
                subprocess.Popen(
                    [str(ROOT / "scripts/superset.sh"), *arguments],
                    cwd=ROOT,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            )
        response = wait_http("http://127.0.0.1:8098/health", processes[0])
        report["health_status"] = response.status_code
        report["assets"] = {}
        for url in [LOGO_URL, DARK_LOGO_URL, FAVICON_URL]:
            asset = requests.get("http://127.0.0.1:8098" + url, timeout=10)
            assert asset.status_code == 200, url
            assert "image/svg+xml" in asset.headers["Content-Type"], url
            report["assets"][url] = asset.status_code
        session = requests.Session()
        response = session.post(
            "http://127.0.0.1:8098/api/v1/security/login",
            json={
                "username": os.environ["SUPERSET_ADMIN_USERNAME"],
                "password": os.environ["SUPERSET_ADMIN_PASSWORD"],
                "provider": "db",
            },
            timeout=10,
        )
        response.raise_for_status()
        session.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        csrf = session.get("http://127.0.0.1:8098/api/v1/security/csrf_token/", timeout=10)
        csrf.raise_for_status()
        session.headers["X-CSRFToken"] = csrf.json()["result"]
        chart_response = session.get(
            "http://127.0.0.1:8098/api/v1/chart/?q=(page_size:100)", timeout=10
        )
        chart_response.raise_for_status()
        charts = chart_response.json()["result"]
        dashboards = session.get(
            "http://127.0.0.1:8098/api/v1/dashboard/flyup3-duckdb",
            timeout=10,
        )
        dashboards.raise_for_status()
        dashboard = dashboards.json()["result"]
        metadata = json.loads(dashboard["json_metadata"])
        report["native_filters"] = [f["name"] for f in metadata["native_filter_configuration"]]
        assert metadata["label_colors"] == LABEL_COLORS
        layout = json.loads(dashboard["position_json"])
        dashboard_chart_ids = {
            node["meta"]["chartId"]
            for node in layout.values()
            if isinstance(node, dict) and node.get("type") == "CHART"
        }
        charts = [chart for chart in charts if chart["id"] in dashboard_chart_ids]
        assert Counter(chart["viz_type"] for chart in charts) == {
            "big_number_total": 4,
            "echarts_timeseries_bar": 4,
            "pie": 1,
            "bubble_v2": 1,
            "gauge_chart": 1,
            "table": 3,
        }
        datasets = session.get(
            "http://127.0.0.1:8098/api/v1/dashboard/flyup3-duckdb/datasets",
            timeout=10,
        )
        datasets.raise_for_status()
        for dataset in datasets.json()["result"]:
            assert all(c.get("verbose_name") for c in dataset["columns"])
        customer_filter = next(
            f for f in metadata["native_filter_configuration"] if f["name"] == "Müşteri"
        )
        report["charts"] = []
        for chart in charts:
            detail = session.get(f"http://127.0.0.1:8098/api/v1/chart/{chart['id']}", timeout=10)
            detail.raise_for_status()
            context = detail.json()["result"]["query_context"]
            payload = json.loads(context) if isinstance(context, str) else context
            payload["force"] = True
            data = session.post("http://127.0.0.1:8098/api/v1/chart/data", json=payload, timeout=20)
            if data.status_code != 200:
                raise RuntimeError(f"{chart['slice_name']}: {data.status_code} {data.text}")
            result = data.json()["result"][0]
            assert not result.get("error"), result
            assert result["data"], chart["slice_name"]
            report["charts"].append(
                {
                    "name": chart["slice_name"],
                    "viz_type": chart["viz_type"],
                    "rows": len(result["data"]),
                    "data": result["data"],
                }
            )
            # Gerçek native filtre maskelerini sorgu context'ine uygula.
            columns = {f["col"] for f in payload["queries"][0]["filters"]}
            if "SCENARIO_NAME" in columns and "Plan A / B" not in chart["slice_name"]:
                alternative = deepcopy(payload)
                alternative["queries"][0]["filters"] = [
                    {**f, "val": ["Plan B"]} if f["col"] == "SCENARIO_NAME" else f
                    for f in alternative["queries"][0]["filters"]
                ]
                alt = session.post(
                    "http://127.0.0.1:8098/api/v1/chart/data", json=alternative, timeout=20
                )
                alt.raise_for_status()
                alt_result = alt.json()["result"][0]
                assert alt_result["data"] and not alt_result.get("error")
                report["charts"][-1]["plan_b_rows"] = len(alt_result["data"])
                if chart["slice_name"] == "48. hafta · net gelir":
                    assert list(result["data"][0].values()) == [390900]
                    assert list(alt_result["data"][0].values()) == [374200]
                if chart["slice_name"] == "Taşınan / teyitli talep":
                    assert list(result["data"][0].values()) == [220]
                    assert list(alt_result["data"][0].values()) == [213]
            if chart["id"] not in customer_filter["scope"]["excluded"]:
                selected = deepcopy(payload)
                selected["queries"][0]["filters"].append(
                    {"col": "CUSTOMER_ID", "op": "IN", "val": ["Medivia"]}
                )
                response = session.post(
                    "http://127.0.0.1:8098/api/v1/chart/data", json=selected, timeout=20
                )
                response.raise_for_status()
                selected_result = response.json()["result"][0]
                assert selected_result["data"] and not selected_result.get("error")
                report["charts"][-1]["medivia_rows"] = len(selected_result["data"])
                if chart["slice_name"] == "Yıllık sadakat maliyeti":
                    assert list(selected_result["data"][0].values()) == [62202]
                if chart["slice_name"] == "Sadakat bütçesi kullanımı":
                    assert list(selected_result["data"][0].values()) == [62202 / 200000]
        assert len(charts) == 14
        # Wait for MCP /health only if it exposes one; initialization uses the actual MCP client.
        deadline = time.monotonic() + 50
        while True:
            try:
                report["mcp_tools"] = asyncio.run(verify_mcp())
                break
            except Exception:
                if processes[1].poll() is not None or time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        for log in logs:
            log.close()
        for port in [8098, 5018]:
            with socket.socket() as sock:
                assert sock.connect_ex(("127.0.0.1", port)) != 0, f"Port {port} açık kaldı"

        report["processes_stopped"] = True
    print(json.dumps(report, ensure_ascii=False, indent=2))
    (OUT / "runtime_verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
