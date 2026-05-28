from __future__ import annotations


def map_category_to_nice_classes(category: str) -> list[str]:
    c = (category or "").strip().lower()
    if not c:
        return []

    mapping = {
        "phone accessory": ["009"],
        "electronics": ["009"],
        "charger": ["009"],
        "clothing": ["025"],
        "shoes": ["025"],
        "toys": ["028"],
        "cosmetics": ["003"],
        "cups": ["021"],
        "mugs": ["021"],
        "tumblers": ["021"],
        "kitchenware": ["021"],
        "bags": ["018"],
        "backpacks": ["018"],
        "jewelry": ["014"],
    }

    hits: list[str] = []
    for key, value in mapping.items():
        if key in c:
            hits.extend(value)

    if not hits and c in mapping:
        hits.extend(mapping[c])

    return sorted(set(hits))
