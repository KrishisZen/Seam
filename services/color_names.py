"""Human-readable color descriptions for wardrobe summaries."""
import colorsys
import re
from PIL import ImageColor


HUE_NAMES = [
    (0, "red"), (12, "vermilion"), (25, "orange"), (38, "amber"),
    (52, "yellow"), (68, "chartreuse"), (86, "lime"), (105, "leaf green"),
    (125, "green"), (145, "sea green"), (162, "aquamarine"), (178, "teal"),
    (192, "cyan"), (207, "azure"), (225, "blue"), (247, "indigo"),
    (266, "violet"), (285, "purple"), (307, "magenta"), (330, "rose"),
    (348, "red"),
]
PLAIN_CSS_NAMES = {"aqua", "aquamarine", "blue", "cyan", "fuchsia", "gold", "green",
                   "lime", "magenta", "maroon", "navy", "olive", "orange", "purple", "red",
                   "teal", "tomato", "white", "yellow"}
CSS_RGB_NAMES = {}
for css_name in ImageColor.colormap:
    css_rgb = ImageColor.getrgb(css_name)[:3]
    if css_name in PLAIN_CSS_NAMES:
        CSS_RGB_NAMES[css_rgb] = css_name
GRAY_LIGHTNESS = {
    "black": .04, "near black": .105, "charcoal": .155, "graphite gray": .205,
    "gunmetal gray": .255, "slate gray": .305, "iron gray": .355, "ash gray": .405,
    "smoke gray": .455, "medium gray": .505, "dove gray": .555, "pewter gray": .605,
    "silver gray": .655, "silver": .705, "pale silver": .755, "light gray": .805,
    "fog gray": .855, "mist gray": .905, "near white": .95, "white": .985,
}


def color_rgb(value):
    """Convert hex, CSS names, or SEAM's descriptive shade names to RGB."""
    value = str(value or "").strip()
    if not value:
        return None
    try:
        rgb = ImageColor.getrgb(value)
        return rgb[:3]
    except ValueError:
        pass
    normalized = re.sub(r"\s+", " ", value.lower().replace("-", " "))
    try:
        return ImageColor.getrgb(normalized.replace(" ", ""))[:3]
    except ValueError:
        pass

    words = normalized.split()
    undertones = {"warm": 20, "brown": 35, "green": 125, "teal": 178, "blue": 225,
                  "violet": 275, "rose": 340}
    saturation = .58
    hue = None
    if words and words[0] in undertones:
        hue = undertones[words.pop(0)]
        saturation = .08
    if normalized in GRAY_LIGHTNESS:
        lightness, saturation, hue = GRAY_LIGHTNESS[normalized], 0, 0
    elif len(words) > 1 and " ".join(words[-2:]) in GRAY_LIGHTNESS:
        lightness = GRAY_LIGHTNESS[" ".join(words[-2:])]
        saturation = .08 if hue is not None else 0
        hue = hue or 0
    elif words and words[-1] in GRAY_LIGHTNESS:
        lightness = GRAY_LIGHTNESS[words[-1]]
        saturation = .08 if hue is not None else 0
        hue = hue or 0
    else:
        base = " ".join(words[-2:]) if len(words) >= 2 else (words[-1] if words else "")
        hue = next((degrees for degrees, name in HUE_NAMES if name == base), None)
        if hue is None and words:
            hue = next((degrees for degrees, name in HUE_NAMES if name == words[-1]), None)
        if hue is None:
            return None
        modifier = " ".join(words[:-2]) if base != words[-1] else " ".join(words[:-1])
        lightness = .55
        if modifier in {"very dark", "near black"}:
            lightness = .11
        elif modifier in {"dark", "darkened"}:
            lightness = .25
        elif modifier == "deep":
            lightness = .36
        elif modifier == "pale":
            lightness, saturation = .92, .48
        elif modifier == "light":
            lightness, saturation = .80, .5
        elif modifier == "soft":
            saturation = .25
        elif modifier == "muted":
            saturation = .38
        elif modifier == "bright":
            saturation = .82
        elif modifier == "vivid":
            saturation = .95
    red, green, blue = colorsys.hls_to_rgb((hue % 360) / 360, lightness, saturation)
    return tuple(round(component * 255) for component in (red, green, blue))


def color_name(value):
    """Turn a color value into a short descriptive name, preserving human input."""
    value = str(value or "").strip()
    if not value:
        return "Color not specified"
    if not re.fullmatch(r"#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", value):
        return re.sub(r"\s+", " ", value).title()
    rgb = color_rgb(value)
    if rgb is None:
        return "Color not specified"
    if tuple(rgb) in CSS_RGB_NAMES:
        return CSS_RGB_NAMES[tuple(rgb)].title()
    hue, lightness, saturation = colorsys.rgb_to_hls(*(component / 255 for component in rgb))
    if saturation < .12:
        gray_shades = [
            (.08, "black"), (.13, "near-black"), (.18, "charcoal"), (.23, "graphite gray"),
            (.28, "gunmetal gray"), (.33, "slate gray"), (.38, "iron gray"), (.43, "ash gray"),
            (.48, "smoke gray"), (.53, "medium gray"), (.58, "dove gray"), (.63, "pewter gray"),
            (.68, "silver gray"), (.73, "silver"), (.78, "pale silver"), (.83, "light gray"),
            (.88, "fog gray"), (.93, "mist gray"), (.97, "near-white"), (1.01, "white"),
        ]
        shade = next(name for limit, name in gray_shades if lightness < limit)
        if saturation < .035 or shade in {"black", "near-black", "near-white", "white"}:
            return shade.title()
        degrees = hue * 360
        if degrees < 25 or degrees >= 340:
            undertone = "warm"
        elif degrees < 80:
            undertone = "brown"
        elif degrees < 160:
            undertone = "green"
        elif degrees < 215:
            undertone = "teal"
        elif degrees < 265:
            undertone = "blue"
        elif degrees < 315:
            undertone = "violet"
        else:
            undertone = "rose"
        return f"{undertone.title()} {shade}"

    degrees = hue * 360
    _, base = min(HUE_NAMES, key=lambda item: min(abs(degrees - item[0]), 360 - abs(degrees - item[0])))
    if lightness < .18:
        modifier = "very dark"
    elif lightness < .30:
        modifier = "dark"
    elif lightness < .43:
        modifier = "deep"
    elif lightness > .88:
        modifier = "pale"
    elif lightness > .73:
        modifier = "light"
    elif saturation < .28:
        modifier = "soft"
    elif saturation < .48:
        modifier = "muted"
    elif saturation > .88 and lightness > .44:
        modifier = "vivid"
    elif saturation > .72:
        modifier = "bright"
    else:
        modifier = ""
    return f"{modifier} {base}".strip().title()
