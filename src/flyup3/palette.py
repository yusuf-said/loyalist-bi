"""Turkish Cargo ekran paleti. THY PANTONE 7620 C ≈ #B7312C (referans notu)."""

import json
from pathlib import Path

PRIMARY = {
    "main": "#C90019",
    "dark": "#9B0013",
    "darker": "#5F000D",
    "light": "#FF8A92",
    "lighter": "#FFD9DE",
    "link": "#CE2228",
}
SECONDARY = {
    "main": "#34404F",
    "light": "#607083",
    "base": "#79889A",
    "subBase": "#A9B3BE",
    "lightest": "#F2F3F5",
}
TEXT = {
    "darkest": "#222530",
    "primary": "#313131",
    "dark": "#525866",
    "secondary": "#717784",
    "subBase": "#99A0AE",
    "light": "#CACFD8",
}
BACKGROUND = {"main": "#FFFFFF", "light": "#F9FAFC", "border": "#E1E4EA"}
STATUS = {
    "success": "#53C172",
    "success_dark": "#188A42",
    "warning": "#D6A42D",
    "warning_dark": "#A67602",
    "error": "#FF3D32",
    "error_dark": "#C62828",
    "info": "#3B82F6",
    "info_dark": "#005BA6",
}
COLORS = [
    PRIMARY["main"],
    SECONDARY["main"],
    STATUS["info_dark"],
    STATUS["warning_dark"],
    SECONDARY["base"],
    STATUS["success_dark"],
    PRIMARY["light"],
    SECONDARY["subBase"],
    "#5FB6FF",
    "#FACE63",
]
CUSTOMER_COLORS = dict(zip(["Medivia", "Nord", "Bella", "Veloce", "Lago", "Rossi"], COLORS))
TIER_COLORS = dict(
    zip(
        ["Elite Plus", "Elite", "Classic Plus", "Classic"],
        [PRIMARY["dark"], PRIMARY["main"], SECONDARY["light"], SECONDARY["subBase"]],
    )
)
MODE_COLORS = dict(
    zip(
        [
            "Aktif konteyner",
            "Pasif örtü",
            "Kargo uçağı",
            "Belly",
            "RFS (kamyon)",
            "49. hafta pazartesi",
            "Taşınamayan",
        ],
        [
            SECONDARY["main"],
            SECONDARY["light"],
            STATUS["info_dark"],
            SECONDARY["base"],
            STATUS["warning_dark"],
            SECONDARY["subBase"],
            PRIMARY["main"],
        ],
    )
)
MACRO_COLORS = {
    "Saf sadakat": PRIMARY["main"],
    "Kârlı sadakatsizlik": STATUS["info_dark"],
    "Sahte sadakat": STATUS["warning_dark"],
    "Sadakatsizlik": SECONDARY["base"],
}
LABEL_COLORS = {
    **CUSTOMER_COLORS,
    **TIER_COLORS,
    **MODE_COLORS,
    **MACRO_COLORS,
    "Normal (t)": SECONDARY["subBase"],
    "Güncel (t)": PRIMARY["main"],
    "Sabit hizmet": SECONDARY["main"],
    "Rebate": PRIMARY["main"],
}
PANEL_COLORS = dict(
    zip(CUSTOMER_COLORS, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"])
)
FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif'


def superset_theme(dark=False):
    from flyup3.branding import DARK_LOGO_URL, DASHBOARD_URL, LOGO_URL

    return {
        "algorithm": "dark" if dark else "default",
        "token": {
            "brandAppName": "THY · FlyUp3",
            "brandLogoUrl": DARK_LOGO_URL if dark else LOGO_URL,
            "brandLogoAlt": "Turkish Airlines · FlyUp3",
            "brandLogoHref": DASHBOARD_URL,
            "brandLogoHeight": "30px",
            "brandLogoMargin": "8px 16px 8px 0",
            "colorPrimary": PRIMARY["main"],
            "colorPrimaryHover": PRIMARY["dark"],
            "colorPrimaryActive": PRIMARY["darker"],
            "colorLink": PRIMARY["link"],
            "colorSuccess": STATUS["success"],
            "colorWarning": STATUS["warning"],
            "colorError": STATUS["error"],
            "colorInfo": STATUS["info"],
            "colorText": BACKGROUND["light"] if dark else TEXT["primary"],
            "colorTextSecondary": TEXT["light"] if dark else TEXT["secondary"],
            "colorBgBase": TEXT["darkest"] if dark else BACKGROUND["main"],
            "colorBgContainer": SECONDARY["main"] if dark else BACKGROUND["main"],
            "colorBgLayout": TEXT["darkest"] if dark else BACKGROUND["light"],
            "colorBorder": SECONDARY["light"] if dark else BACKGROUND["border"],
            "fontFamily": FONT,
            "fontUrls": [],
        },
    }


def powerbi_theme():
    return {
        "name": "THY Turkish Cargo · FlyUp3",
        "dataColors": COLORS,
        "background": BACKGROUND["main"],
        "foreground": TEXT["primary"],
        "tableAccent": PRIMARY["main"],
        "good": STATUS["success"],
        "neutral": STATUS["warning"],
        "bad": STATUS["error"],
        "textClasses": {
            k: {"fontFace": "Segoe UI", "color": TEXT["primary"]}
            for k in ["label", "callout", "title", "header"]
        },
    }


def main():
    path = Path(__file__).resolve().parents[2] / "powerbi/thy_turkish_cargo.json"
    path.write_text(json.dumps(powerbi_theme(), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
