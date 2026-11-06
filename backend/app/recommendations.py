"""Conservative ingredient-aware food recommendation filters."""
from __future__ import annotations

import re
from typing import Any


ALLERGY_TERMS: dict[str, tuple[str, ...]] = {
    "dairy": ("milk", "whey", "casein", "lactose", "butter", "cheese", "cream", "yogurt", "ghee"),
    "gluten": ("wheat", "barley", "rye", "malt", "seitan", "spelt", "farro"),
    "peanuts": ("peanut", "groundnut", "arachis"),
    "tree nuts": ("almond", "hazelnut", "walnut", "cashew", "pecan", "pistachio", "macadamia", "brazil nut"),
    "shellfish": ("shrimp", "prawn", "crab", "lobster", "crayfish", "shellfish"),
    "egg": ("egg", "albumin", "ovalbumin", "mayonnaise"),
    "soy": ("soy", "soya", "tofu", "tempeh", "edamame"),
    "sesame": ("sesame", "tahini", "benne"),
}
VEGAN_TERMS = (
    "meat", "beef", "pork", "bacon", "ham", "lamb", "mutton", "chicken", "turkey", "duck",
    "fish", "salmon", "tuna", "anchovy", "seafood", "shrimp", "prawn", "crab", "lobster",
    "milk", "whey", "casein", "cheese", "butter", "cream", "yogurt", "ghee", "egg", "honey", "gelatin",
)
VEGETARIAN_TERMS = (
    "meat", "beef", "pork", "bacon", "ham", "lamb", "mutton", "chicken", "turkey", "duck",
    "fish", "salmon", "tuna", "anchovy", "seafood", "shrimp", "prawn", "crab", "lobster", "gelatin",
)
PESCATARIAN_TERMS = (
    "meat", "beef", "pork", "bacon", "ham", "lamb", "mutton", "chicken", "turkey", "duck", "gelatin",
)
SUPPORTED_DIETS = {"no_restrictions", "vegetarian", "vegan", "halal", "dairy_free", "gluten_free", "pescatarian"}


def normalize_diet(diet: str | None) -> str:
    return re.sub(r"[\s-]+", "_", (diet or "no_restrictions").casefold().strip())


def _has_term(text: str, term: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)", text.casefold()) is not None


def ingredient_conflicts(ingredients: str, allergies: list[str]) -> list[str]:
    found: list[str] = []
    for allergy in allergies:
        key = allergy.casefold().strip()
        terms = ALLERGY_TERMS.get(key, (key,))
        searchable = ingredients.casefold()
        if key == "dairy":
            # Plant-based milks do not indicate dairy; retain matches for any
            # separate dairy ingredient appearing elsewhere in the text.
            searchable = re.sub(r"\b(?:almond|oat|soy|soya|coconut|rice|hemp|cashew)\s+milk\b", " ", searchable)
        if any(_has_term(searchable, term) for term in terms):
            found.append(allergy)
    return found


def recommendation_eligibility(food: Any, diet: str, allergies: list[str]) -> tuple[bool, str | None]:
    """Return whether a saved food can be suggested and why it was excluded.

    Foods are never asserted safe. With allergy or vegetarian restrictions, the
    candidate must have recorded ingredients so obvious conflicts can be
    screened. Cross-contact and omitted label ingredients remain unknowable.
    """
    diet_key = normalize_diet(diet)
    if diet_key not in SUPPORTED_DIETS:
        return False, "LossFit does not yet support this custom diet preference."
    if diet_key == "halal":
        return False, "Halal status cannot be verified from LossFit's food records."
    ingredients = food.get("ingredients") if isinstance(food, dict) else getattr(food, "ingredients", None)
    name = food.get("name", "") if isinstance(food, dict) else getattr(food, "name", "")
    category = food.get("category", "") if isinstance(food, dict) else getattr(food, "category", "")
    restricted = allergies or diet_key in {"vegan", "vegetarian", "dairy_free", "gluten_free", "pescatarian"}
    if restricted and not (isinstance(ingredients, str) and ingredients.strip()):
        return False, "Recorded ingredients are missing, so this food cannot be screened against your preferences."
    searchable = " ".join(part for part in (ingredients or "", name or "", category or "") if isinstance(part, str))
    effective_allergies = list(allergies)
    if diet_key == "dairy_free":
        effective_allergies.append("dairy")
    elif diet_key == "gluten_free":
        effective_allergies.append("gluten")
    conflicts = ingredient_conflicts(searchable, effective_allergies)
    if conflicts:
        return False, "Recorded ingredients mention a listed allergy or restriction."
    if diet_key == "vegan" and any(_has_term(searchable, term) for term in VEGAN_TERMS):
        return False, "Recorded ingredients do not match a vegan preference."
    if diet_key == "vegetarian" and any(_has_term(searchable, term) for term in VEGETARIAN_TERMS):
        return False, "Recorded ingredients do not match a vegetarian preference."
    if diet_key == "pescatarian" and any(_has_term(searchable, term) for term in PESCATARIAN_TERMS):
        return False, "Recorded ingredients do not match a pescatarian preference."
    return True, None
