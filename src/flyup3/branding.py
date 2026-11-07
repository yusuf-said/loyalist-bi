"""Proje içindeki THY varlıkları; Superset paket dizinine dosya kopyalanmaz."""

from copy import deepcopy
from xml.etree import ElementTree as ET

from flyup3.settings import ROOT

ASSET_ROOT = ROOT / "assets/thy"
ASSET_URL = "/flyup3-assets/"
DASHBOARD_URL = "/superset/dashboard/flyup3-duckdb/"
LOGO_URL = ASSET_URL + "thy_logo_horizontal.svg"
DARK_LOGO_URL = ASSET_URL + "generated/thy_logo_horizontal_white.svg"
FAVICON_URL = ASSET_URL + "generated/thy_emblem.svg"


def generate_logo_assets():
    """Kaynak SVG'leri değiştirmeden beyaz yazı ve kare amblem türetir."""
    generated = ASSET_ROOT / "generated"
    generated.mkdir(exist_ok=True)
    source = (ASSET_ROOT / "thy_logo_horizontal.svg").read_text()
    (generated / "thy_logo_horizontal_white.svg").write_text(
        source.replace("fill:#000000", "fill:#FFFFFF")
    )
    ns = "http://www.w3.org/2000/svg"
    ET.register_namespace("", ns)
    emblem = ET.Element(
        f"{{{ns}}}svg",
        {"viewBox": "49 49 126 126", "width": "64", "height": "64"},
    )
    # İlk iki path beyaz kuş/kenar ve kırmızı amblemdir. Koordinatlar iç gruptadır.
    for path in ET.fromstring(source).iter(f"{{{ns}}}path"):
        if path.get("id") in {"path10", "path12"}:
            clean = ET.SubElement(emblem, f"{{{ns}}}path")
            clean.attrib.update({k: deepcopy(path.attrib[k]) for k in ["d", "style"]})
    ET.ElementTree(emblem).write(generated / "thy_emblem.svg", encoding="unicode")


def register_brand_assets(app):
    from flask import abort, send_from_directory

    allowed = {
        "thy_logo_horizontal.svg",
        "generated/thy_logo_horizontal_white.svg",
        "generated/thy_emblem.svg",
    }

    @app.get(ASSET_URL + "<path:filename>")
    def flyup3_brand_asset(filename):
        if filename not in allowed:
            abort(404)
        return send_from_directory(ASSET_ROOT, filename, mimetype="image/svg+xml")
