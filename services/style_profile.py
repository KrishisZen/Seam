"""Summarize style tags from garments supplied by the user."""
from collections import Counter


def summarize(garments):
    counts = Counter()
    for garment in garments:
        tags = dict.fromkeys(tag.strip().lower() for tag in (garment.get("style_tags") or "").split(",") if tag.strip())
        counts.update(tag.title() for tag in tags)
    total = sum(counts.values())
    return [{"name": name, "count": count, "percent": round(count / total * 100) if total else 0}
            for name, count in counts.most_common()]
