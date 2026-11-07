"""Gerçek stdio ve geçici HTTP MCP doğrulaması; mevcut servisleri durdurmaz."""

import argparse
import asyncio
import json
import os
import signal
import socket
import subprocess
import time

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from flyup3.settings import OUT, ROOT, prepare_superset_env

NAMES = (
    "simulate_capacity_w48",
    "simulate_loyalty_cost",
    "simulate_program_roi",
    "simulate_churn_risk",
)
OVERRIDES = (
    {"passive_consent": False},
    {"visit_overrides": {"Nord": 1}},
    {"impact": 0.25},
    {"uncertainty_overrides": {"Rossi": 0}},
)


def decode(result):
    assert not result.is_error, result
    texts = [c.text for c in result.content if c.type == "text"]
    assert len(texts) == 1, texts
    return json.loads(texts[0])


def assert_result(name, data, override):
    assert set(data) == {"inputs", "results", "summary", "assumptions"}, data
    r = data["results"]
    if name == NAMES[0]:
        assert (r["net48"], r["contrib"]) == ((374200, 99600) if override else (390900, 102725))
    elif name == NAMES[1]:
        assert abs(r["total"] - (102879.5 if override else 102079.5)) < 1e-6
    elif name == NAMES[2]:
        assert abs(r["net_52_weeks"] - (-15388.875 if override else 71301.75)) < 1e-6
        assert r["sensitivity"]["positive"] == 52
    else:
        rows = {row["customer"]: row for row in r["customers"]}
        assert rows["Nord"]["score"] == 100
        assert rows["Rossi"]["uncertainty"] == (0 if override else 40)


async def check_client(transport, meta=False):
    async with Client(transport, timeout=30) as client:
        init = client.initialize_result
        assert init.serverInfo.name == "loyalist", init.serverInfo
        assert "simulate_capacity_w48" in init.instructions
        assert "THY corporate color identity" in init.instructions
        assert "FlyUp3 data catalog" in init.instructions
        definitions = await client.list_tools()
        names = {tool.name for tool in definitions}
        if meta:
            assert {"search_tools", "call_tool"} <= names, names
        else:
            assert set(NAMES) <= names, names
        report = {"server_name": init.serverInfo.name, "listed_tools": sorted(names), "calls": []}
        for name, override in zip(NAMES, OVERRIDES):
            if meta:
                found = decode(await client.call_tool("search_tools", {"query": name}))
                definitions_found = {t["name"]: t for t in found}
                assert name in definitions_found, definitions_found
                definition = definitions_found[name]
                report.setdefault("discovered", []).append(name)
            else:
                definition = next(t.model_dump() for t in definitions if t.name == name)
            assert definition["annotations"]["readOnlyHint"] is True
            assert definition["annotations"]["destructiveHint"] is False
            for args in ({}, override):
                start = time.perf_counter()
                result = decode(
                    await client.call_tool(
                        "call_tool" if meta else name,
                        {"name": name, "arguments": args} if meta else args,
                    )
                )
                elapsed = time.perf_counter() - start
                assert_result(name, result, bool(args))
                assert elapsed < 2, (name, elapsed)
                report["calls"].append(
                    {
                        "name": name,
                        "arguments": args,
                        "seconds": round(elapsed, 4),
                        "summary": result["summary"],
                    }
                )
        return report


def port_open(port):
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http-port", type=int, default=5018)
    args = parser.parse_args()
    if args.http_port in (8088, 5008):
        raise ValueError("Mevcut servis portları (8088/5008) test için kullanılamaz.")
    if port_open(args.http_port):
        raise RuntimeError(f"Geçici test portu {args.http_port} zaten kullanımda.")
    prepare_superset_env()
    existing = {p: port_open(p) for p in (8088, 5008)}
    report = {}
    stdio = StdioTransport(
        str(ROOT / "scripts/mcp_stdio.sh"),
        [],
        cwd=str(ROOT),
        env=os.environ.copy(),
        keep_alive=False,
        log_file=OUT / "simulations_stdio_smoke.log",
    )
    report["stdio"] = asyncio.run(check_client(stdio))
    with (OUT / "simulations_http_smoke.log").open("w") as log:
        process = subprocess.Popen(
            [
                str(ROOT / "scripts/superset.sh"),
                "mcp",
                "run",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.http_port),
            ],
            cwd=ROOT,
            env=os.environ.copy(),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 50
            while not port_open(args.http_port):
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Geçici HTTP MCP açılmadı; out/simulations_http_smoke.log")
                time.sleep(0.2)
            report["http"] = asyncio.run(
                check_client(f"http://127.0.0.1:{args.http_port}/mcp", meta=True)
            )
        finally:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
    assert not port_open(args.http_port), "Geçici HTTP portu açık kaldı."
    assert {p: port_open(p) for p in existing} == existing, "Mevcut servis durumu değişti."
    report["temporary_http_stopped"] = True
    report["existing_ports_preserved"] = existing
    output = json.dumps(report, ensure_ascii=False, indent=2)
    (OUT / "simulations_runtime_verification.json").write_text(output + "\n")
    print(output)


if __name__ == "__main__":
    main()
