"""Validated normalization for USDA FoodData Central Branded records."""
from __future__ import annotations

import math
from typing import Any


SOURCE = "USDA FoodData Central Branded"
NUTRIENTS = {1008: "kcal", 1003: "protein", 1005: "carbs", 1004: "fat"}
LIMITS = {"kcal": 10000, "protein": 1000, "carbs": 1000, "fat": 1000}


def _identifier(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not str(value).isascii() or not str(value).isdecimal():
        raise ValueError("USDA record has an invalid FDC identifier")
    result = int(value)
    if result < 1 or result > 2_147_483_647:
        raise ValueError("USDA record has an invalid FDC identifier")
    return result


def _clean_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] or None


def _nutrition(record: dict[str, Any]) -> tuple[dict[str, float | None], dict[str, dict[str, str]]]:
    values: dict[str, float | None] = {key: None for key in NUTRIENTS.values()}
    provenance: dict[str, dict[str, str]] = {}
    nutrients = record.get("foodNutrients")
    if nutrients is not None and not isinstance(nutrients, list):
        raise ValueError("USDA nutrient data has an invalid format")
    for item in nutrients or []:
        if not isinstance(item, dict):
            continue
        nutrient = item.get("nutrient") if isinstance(item.get("nutrient"), dict) else {}
        raw_id = nutrient.get("id", item.get("nutrientId"))
        key = NUTRIENTS.get(raw_id)
        if not key or values[key] is not None or key in provenance:
            continue
        unit = str(nutrient.get("unitName", item.get("unitName", ""))).strip().casefold()
        if key == "kcal" and unit not in {"kcal", "calorie", "calories"}:
            continue
        if key != "kcal" and unit not in {"g", "gram", "grams"}:
            continue
        raw_amount = item.get("amount", item.get("value"))
        try:
            amount = float(raw_amount)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(amount) or amount < 0:
            provenance[key] = {"status": "unavailable", "reason": "USDA supplied an invalid nutrient amount; value withheld"}
            continue
        if amount > LIMITS[key]:
            raise ValueError(f"USDA branded nutrient {key} exceeded the accepted range")
        values[key] = amount
        provenance[key] = {"status": "imported", "source": "USDA FoodData Central Branded label data"}
    for key in NUTRIENTS.values():
        provenance.setdefault(key, {"status": "unavailable", "reason": "USDA record did not provide this nutrient"})
    return values, provenance


def normalize_search_hit(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or not isinstance(record.get("dataType"), str) or record["dataType"].casefold() != "branded":
        raise ValueError("USDA search result is not a Branded food")
    fdc_id = _identifier(record.get("fdcId"))
    name = _clean_text(record.get("description"), 160)
    if not name:
        raise ValueError("USDA branded record has no usable description")
    nutrients, _ = _nutrition(record)
    serving_size = record.get("servingSize")
    serving_unit = _clean_text(record.get("servingSizeUnit"), 24)
    package_serving = None
    if isinstance(serving_size, (float, int)) and not isinstance(serving_size, bool) and math.isfinite(serving_size) and 0 < serving_size <= 10000 and (serving_unit or "").casefold() in {"g", "gram", "grams"}:
        package_serving = f"{serving_size:g} g"
    return {
        "fdc_id": fdc_id,
        "name": name,
        "brand": _clean_text(record.get("brandName") or record.get("brandOwner"), 120),
        "package_serving": package_serving,
        "nutrients": nutrients,
        "source_url": f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients",
    }


def normalize_branded_food(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or not isinstance(record.get("dataType"), str) or record["dataType"].casefold() != "branded":
        raise ValueError("USDA record is not a Branded food")
    fdc_id = _identifier(record.get("fdcId"))
    name = _clean_text(record.get("description"), 160)
    if not name:
        raise ValueError("USDA branded record has no usable description")
    values, provenance = _nutrition(record)
    category_value = record.get("foodCategory")
    if isinstance(category_value, dict):
        category_value = category_value.get("description")
    category = _clean_text(category_value, 80)
    servings = []
    serving_size = record.get("servingSize")
    serving_unit = (record.get("servingSizeUnit") or "").strip().casefold() if isinstance(record.get("servingSizeUnit"), str) else ""
    label = _clean_text(record.get("householdServingFullText"), 100)
    if isinstance(serving_size, (int, float)) and not isinstance(serving_size, bool) and math.isfinite(serving_size) and 0 < serving_size <= 10000 and serving_unit in {"g", "gram", "grams"}:
        grams = float(serving_size)
        portion_label = label or f"1 serving ({grams:g} g)"
        if portion_label.casefold() != "100 g":
            servings.append({"label": portion_label, "grams": grams})
    notes = "Nutrition values are imported from USDA FoodData Central Branded records. Review the package label; missing nutrients remain unavailable."
    return {
        "name": name,
        "state": "prepared",
        "brand": _clean_text(record.get("brandName") or record.get("brandOwner"), 120),
        "category": category,
        "verification": "imported",
        "source": SOURCE,
        "source_record_id": str(fdc_id),
        "source_url": f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients",
        "nutrition_basis": "per_100g",
        "nutrition_provenance": provenance,
        "data_notes": notes,
        **values,
        "servings": servings,
    }
