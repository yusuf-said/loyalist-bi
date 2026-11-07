"""Resmi Superset host araç kayıt API'si; yalnız mcp_branding.apply() çağırır."""

from flyup3.sim import (
    simulate_capacity_w48,
    simulate_churn_risk,
    simulate_loyalty_cost,
    simulate_program_roi,
)

TOOLS = (
    (simulate_capacity_w48, "48. hafta kapasite, pasif onay, charter ve tahsis senaryosu."),
    (simulate_loyalty_cost, "Kademe, avantaj ve büyüme değişince sadakat maliyeti ve bütçe."),
    (simulate_program_roi, "Programın etki, marj, rebate ve fırsat maliyetine göre getirisi."),
    (simulate_churn_risk, "Müşteri sinyal puanları, kayıp riski ve belirsizlik kötü senaryosu."),
)


def register(mcp):
    """Host bağlamında öneksiz kaydeder; aynı sunucuya ikinci kez eklemez."""
    if getattr(mcp, "_flyup3_simulations", False):
        return
    from mcp.types import ToolAnnotations
    from superset.extensions.context import get_current_extension_context
    from superset_core.mcp.decorators import tool

    # superset_core.mcp paketinin __init__'i tool export etmez (Superset 6.1).
    # Public decorator, dependency injection sonrası decorators.tool üzerinden alınır.
    if get_current_extension_context() is not None:
        raise RuntimeError("FlyUp3 simülasyonları host bağlamında kaydedilmelidir.")
    for fn, description in TOOLS:
        tool(
            name=fn.__name__,
            description=description + "\n" + fn.__doc__,
            tags=["simulation", "read"],
            protect=False,
            annotations=ToolAnnotations(
                readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
            ),
        )(fn)
    mcp._flyup3_simulations = True
