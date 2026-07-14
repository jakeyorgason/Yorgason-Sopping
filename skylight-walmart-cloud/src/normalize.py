from __future__ import annotations

import re
from collections import OrderedDict
from typing import Iterable

from .models import GroceryItem

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

UNIT_ALIASES = {
    "lbs": "lb",
    "pounds": "lb",
    "pound": "lb",
    "ounces": "oz",
    "ounce": "oz",
    "ozs": "oz",
    "cans": "can",
    "boxes": "box",
    "bags": "bag",
    "bottles": "bottle",
    "jars": "jar",
    "packages": "package",
    "packs": "pack",
    "gallons": "gallon",
    "quarts": "quart",
    "pints": "pint",
    "dozen": "dozen",
    "bunches": "bunch",
    "heads": "head",
}

UNITS = {
    "lb", "lbs", "pound", "pounds", "oz", "ounce", "ounces", "can", "cans",
    "box", "boxes", "bag", "bags", "bottle", "bottles", "jar", "jars",
    "package", "packages", "pack", "packs", "gallon", "gallons", "quart",
    "quarts", "pint", "pints", "dozen", "bunch", "bunches", "head", "heads",
    "cup", "cups", "tbsp", "tsp", "item", "items",
}

FRACTIONS = {
    "1/2": 0.5,
    "1/3": 1 / 3,
    "2/3": 2 / 3,
    "1/4": 0.25,
    "3/4": 0.75,
    "1/8": 0.125,
}


def _parse_number(token: str) -> float | None:
    cleaned = token.strip().lower()
    if cleaned in NUMBER_WORDS:
        return float(NUMBER_WORDS[cleaned])
    if cleaned in FRACTIONS:
        return FRACTIONS[cleaned]
    if " " in cleaned:
        parts = cleaned.split()
        if len(parts) == 2:
            first = _parse_number(parts[0])
            second = _parse_number(parts[1])
            if first is not None and second is not None:
                return first + second
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_text_list(text: str) -> list[GroceryItem]:
    """Parse a simple newline-separated list without AI.

    Examples:
      2 cans diced tomatoes
      1.5 lb chicken breast
      shredded cheddar
    """
    items: list[GroceryItem] = []
    for raw_line in text.splitlines():
        line = re.sub(r"^[\s\-•*✓☐□]+", "", raw_line).strip()
        if not line:
            continue

        # Strip common checkbox/list suffixes while preserving useful notes.
        line = re.sub(r"\s+\(checked\)\s*$", "", line, flags=re.I)
        tokens = line.split()
        quantity = 1.0
        unit = "item"
        consumed = 0

        if tokens:
            # Handle mixed number such as "1 1/2".
            if len(tokens) >= 2 and _parse_number(tokens[0]) is not None and tokens[1] in FRACTIONS:
                quantity = float(_parse_number(tokens[0]) or 0) + FRACTIONS[tokens[1]]
                consumed = 2
            else:
                parsed = _parse_number(tokens[0])
                if parsed is not None:
                    quantity = parsed
                    consumed = 1

        if len(tokens) > consumed and tokens[consumed].lower().rstrip(".") in UNITS:
            raw_unit = tokens[consumed].lower().rstrip(".")
            unit = UNIT_ALIASES.get(raw_unit, raw_unit.rstrip("s"))
            consumed += 1

        name = " ".join(tokens[consumed:]).strip(" ,-")
        if not name:
            name = line
            quantity = 1.0
            unit = "item"

        # Split parenthetical qualifiers into notes.
        notes = ""
        match = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", name)
        if match:
            name = match.group(1).strip()
            notes = match.group(2).strip()

        items.append(GroceryItem(name=name, quantity=quantity, unit=unit, notes=notes))
    return items


def merge_exact_items(items: Iterable[GroceryItem]) -> list[GroceryItem]:
    merged: OrderedDict[tuple[str, str, str], GroceryItem] = OrderedDict()
    for item in items:
        key = (item.name.strip().lower(), item.unit.strip().lower(), item.notes.strip().lower())
        if key in merged:
            merged[key].quantity += item.quantity
        else:
            merged[key] = item.model_copy(deep=True)
    return list(merged.values())


def build_search_query(item: GroceryItem) -> str:
    parts = [item.name.strip()]
    if item.notes.strip():
        parts.append(item.notes.strip())
    if item.unit not in {"item", "items"} and item.quantity:
        qty = int(item.quantity) if float(item.quantity).is_integer() else item.quantity
        parts.append(f"{qty} {item.unit}")
    return " ".join(part for part in parts if part)
