"""Normalization for the USDA FoodData Central Foundation Foods release."""
import re
import math

NUTRIENT_IDS = {1008: "kcal", 1003: "protein", 1005: "carbs", 1004: "fat"}


def preparation_state(description: str) -> str:
    value = description.casefold()
    for state in ("raw", "boiled", "steamed", "fried", "grilled", "roasted", "baked", "dried", "frozen"):
        if re.search(rf"\b{state}\b", value):
            return state
    return "cooked" if re.search(r"\bcooked\b", value) else "prepared"


def portion_label(portion: dict, data_type: str = "Foundation") -> str | None:
    grams = portion.get("gramWeight")
    unit = portion.get("measureUnit") or {}
    if data_type == "Survey":
        description = (portion.get("portionDescription") or "").strip()
        return description[:100] if description and "quantity not specified" not in description.casefold() else None
    unit_name = unit.get("name") or unit.get("abbreviation") or ""
    if not isinstance(grams, (int, float)) or grams <= 0 or grams > 10000 or not unit_name or unit_name.casefold() == "racc":
        return None
    amount = portion.get("amount", portion.get("value"))
    if isinstance(amount, (int, float)) and amount > 0:
        amount_text = str(int(amount)) if float(amount).is_integer() else str(amount)
        label = f"{amount_text} {unit_name}"
    else:
        label = unit_name
    modifier = (portion.get("modifier") or "").strip()
    label = f"{label} {modifier}".strip()
    return label[:100]


def normalize_foundation_food(record: dict, release: str = "October 2026", data_type: str = "Foundation") -> dict:
    name = (record.get("description") or "").strip()
    fdc_id = record.get("fdcId")
    if not name or not fdc_id:
        raise ValueError("Foundation food record has no valid name or FDC identifier")
    nutrients = {}
    nutrient_provenance = {}
    quality_notes = []
    if len(name) > 160:
        name = name[:157].rstrip() + "..."
        quality_notes.append("The long USDA food description was shortened for display; use the source link for its full description.")
    for item in record.get("foodNutrients", []):
        nutrient = item.get("nutrient") or {}
        key = NUTRIENT_IDS.get(nutrient.get("id"))
        amount = item.get("amount")
        if not key or key in nutrients or key in nutrient_provenance:
            continue
        derivation = item.get("foodNutrientDerivation") or {}
        code = derivation.get("code")
        source_meta = derivation.get("foodNutrientSource") or {}
        if not isinstance(amount, (int, float)):
            continue
        if not math.isfinite(amount) or amount < 0:
            nutrient_provenance[key] = {"status": "unavailable", "reason": "USDA source amount was non-finite or negative and was excluded", "derivation": derivation.get("description"), "source": source_meta.get("description")}
            quality_notes.append(f"{nutrient.get('name', key)} excluded because the USDA source reported a non-finite or negative amount.")
            continue
        if amount > {"kcal": 10000, "protein": 1000, "carbs": 1000, "fat": 1000}[key]:
            raise ValueError(f"Out-of-range {key} amount in FDC record {fdc_id}")
        nutrients[key] = float(amount)
        nutrient_provenance[key] = {"status": "verified" if code == "A" else "reviewed", "derivation": derivation.get("description"), "source": source_meta.get("description")}
        if data_type == "Survey":
            nutrient_provenance[key]["status"] = "reviewed"
    category = (((record.get("foodCategory") or {}).get("description") or "") if data_type == "Foundation" else ((record.get("wweiaFoodCategory") or {}).get("wweiaFoodCategoryDescription") or ""))[:80] or None
    servings = []
    seen = {"100 g"}
    for item in record.get("foodPortions", []):
        label = portion_label(item, data_type)
        grams = item.get("gramWeight")
        if label and label.casefold() not in seen:
            seen.add(label.casefold())
            servings.append({"label": label, "grams": float(grams)})
    return {
        "name": name,
        "state": preparation_state(name),
        "category": category,
        "verification": "verified" if nutrient_provenance and all(item["status"] == "verified" for item in nutrient_provenance.values()) else "reviewed",
        "source": f"USDA FoodData Central {'Foundation Foods' if data_type == 'Foundation' else 'FNDDS'} ({release})",
        "source_record_id": str(fdc_id),
        "source_url": f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients",
        "nutrition_basis": "per_100g",
        "nutrition_provenance": nutrient_provenance,
        "data_notes": " ".join(quality_notes) or None,
        **{key: nutrients.get(key) for key in ("kcal", "protein", "carbs", "fat")},
        "servings": servings,
    }
