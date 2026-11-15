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
PLAIN_CSS_NAMES = {"aqua", "aquamarine", "blue", "cyan", "fuchsia", "gold", "gray", "green",
                   "lime", "magenta", "maroon", "navy", "olive", "orange", "purple", "red",
                   "silver", "teal", "tomato", "white", "yellow"}
CSS_RGB_NAMES = {}
for css_name in ImageColor.colormap:
    css_rgb = ImageColor.getrgb(css_name)[:3]
    if css_name in PLAIN_CSS_NAMES:
        CSS_RGB_NAMES[css_rgb] = css_name


def color_name(value):
    """Turn a color value into a short descriptive name, preserving human input."""
    value = str(value or "").strip()
    if not value:
        return "Color not specified"
    try:
        rgb = ImageColor.getrgb(value)
    except ValueError:
        # Garment color fields also accept descriptive text such as "forest green".
        return re.sub(r"\s+", " ", value).title()
    if len(rgb) == 4:
        rgb = rgb[:3]
    if tuple(rgb) in CSS_RGB_NAMES:
        return CSS_RGB_NAMES[tuple(rgb)].title()
    hue, lightness, saturation = colorsys.rgb_to_hls(*(component / 255 for component in rgb))
    if saturation < .12:
        if lightness < .08:
            return "Black"
        if lightness < .22:
            return "Charcoal"
        if lightness < .43:
            return "Dark gray"
        if lightness < .69:
            return "Gray"
        if lightness < .87:
            return "Silver gray"
        if lightness < .96:
            return "Off-white"
        return "White"

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
