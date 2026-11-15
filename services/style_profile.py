"""Normalize curated style tags and summarize them across garments."""
from collections import Counter
from config import STYLE_TAGS

TAG_BY_KEY = {tag.casefold(): tag for tag in STYLE_TAGS}


def parse_style_tags(values):
    """Return unique canonical tags, silently ignoring legacy free-text values."""
    if isinstance(values, str):
        values = values.split(",")
    tags = []
    seen = set()
    for value in values or []:
        key = str(value).strip().casefold()
        canonical = TAG_BY_KEY.get(key)
        if canonical and key not in seen:
            tags.append(canonical)
            seen.add(key)
    return tags


def summarize(garments):
    counts = Counter()
    for garment in garments:
        counts.update(parse_style_tags(garment.get("style_tags") or ""))
    total = sum(counts.values())
    return [{"name": name, "count": count, "percent": round(count / total * 100) if total else 0}
            for name, count in counts.most_common()]
