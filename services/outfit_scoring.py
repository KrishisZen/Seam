"""Transparent wardrobe outfit compatibility scoring."""
from collections import Counter
from itertools import combinations
import colorsys
from PIL import ImageColor
from config import SCORING_WEIGHTS

WEIGHTS = SCORING_WEIGHTS
CORE = {"Tops", "Bottoms", "Footwear"}


def _hex(value):
    value = (value or "").strip().lstrip("#")
    try:
        return ImageColor.getrgb("#" + value if len(value) == 6 else value)[:3]
    except (ValueError, TypeError):
        return None


def score_outfit(garments, weights=None):
    """Score garments with five deterministic dimensions, each from 0 to 100."""
    garments = list(garments)
    if not garments:
        return {"color": 0, "style": 0, "silhouette": 0, "completeness": 0, "balance": 0, "overall": 0}
    weights = dict(weights or WEIGHTS)
    if set(weights) != set(WEIGHTS) or any(value < 0 for value in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("Scoring weights must include all five dimensions, be non-negative, and have a positive total.")
    total_weight = sum(weights.values())
    weights = {key: value / total_weight for key, value in weights.items()}
    colors = []
    for g in garments:
        color = _hex(g.get("color"))
        if color:
            colors.append(colorsys.rgb_to_hsv(*(c / 255 for c in color)))
    if len(colors) < 2:
        color_score = 62.0 if colors else 50.0
    else:
        distances = []
        for (h1, s1, v1), (h2, s2, v2) in combinations(colors, 2):
            hue_dist = min(abs(h1 - h2), 1 - abs(h1 - h2)) * 2
            distances.append(min(1, .55 * hue_dist + .25 * abs(s1 - s2) + .20 * abs(v1 - v2)))
        # Moderate separation is useful; very similar or very distant combinations score lower.
        mean = sum(distances) / len(distances)
        color_score = 100 * max(0, 1 - abs(mean - .34) / .66)
    tags = [set(t.strip().lower() for t in (g.get("style_tags") or "").split(",") if t.strip()) for g in garments]
    nonempty = [t for t in tags if t]
    if len(nonempty) < 2:
        style_score = 58.0 if nonempty else 50.0
    else:
        style_score = 100 * sum(len(a & b) / len(a | b) if a | b else 0 for a, b in combinations(nonempty, 2)) / len(list(combinations(nonempty, 2)))
    fits = [g.get("fit", "").strip().lower() for g in garments if g.get("fit", "").strip()]
    silhouette_score = 72.0 if len(fits) < 2 else max(45.0, 100 - 14 * (len(set(fits)) - 1))
    cats = {g.get("category") for g in garments}
    completeness_score = min(100.0, 48 + 19 * len(cats & CORE) + 8 * bool(cats & {"Outerwear", "Accessories"}))
    category_counts = Counter(g.get("category") for g in garments)
    balance_score = 100 - min(55, 20 * sum(max(0, count - 1) for cat, count in category_counts.items() if cat in CORE))
    scores = {"color": color_score, "style": style_score, "silhouette": silhouette_score,
              "completeness": completeness_score, "balance": balance_score}
    scores = {key: round(max(0, min(100, value)), 1) for key, value in scores.items()}
    scores["overall"] = round(sum(scores[k] * weights[k] for k in weights), 1)
    return scores


def improvement_suggestions(selected, wardrobe):
    """Try each one-for-one replacement and return real re-scored improvements."""
    current = score_outfit(selected)
    if not selected:
        return current, []
    weakest = min(WEIGHTS, key=lambda key: current[key])
    suggestions = []
    selected_ids = {g["id"] for g in selected}
    selected_by_category = {g["category"]: g for g in selected}
    for original in selected:
        for candidate in wardrobe:
            if candidate["id"] in selected_ids or candidate["category"] != original["category"]:
                continue
            trial = [candidate if g["id"] == original["id"] else g for g in selected]
            revised = score_outfit(trial)
            if revised["overall"] > current["overall"]:
                suggestions.append({"remove": original, "add": candidate, "scores": revised,
                                    "gain": round(revised["overall"] - current["overall"], 1), "weakest": weakest})
    suggestions.sort(key=lambda s: s["gain"], reverse=True)
    return current, suggestions[:3]
