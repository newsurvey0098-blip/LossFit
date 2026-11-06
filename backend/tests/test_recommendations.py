from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.recommendations import ingredient_conflicts, recommendation_eligibility
from backend.app.main import Food
from backend.tests.test_core_flows import register


def test_ingredient_conflicts_use_boundaries_and_common_allergen_aliases():
    assert ingredient_conflicts("Roasted peanut flour, salt", ["peanuts"]) == ["peanuts"]
    assert ingredient_conflicts("Coconut milk, rice, cinnamon", ["dairy"]) == []
    assert ingredient_conflicts("Wheat flour and whey", ["gluten", "dairy"]) == ["gluten", "dairy"]


def test_preference_screen_requires_known_ingredients_and_never_assumes_safe():
    assert recommendation_eligibility(Food(name="Lentil bowl", category="meal", ingredients=None), "vegan", [])[0] is False
    assert recommendation_eligibility(Food(name="Lentil bowl", category="meal", ingredients="lentils, water"), "vegan", [])[0] is True
    allowed, reason = recommendation_eligibility(Food(name="Coconut rice", category="meal", ingredients="coconut milk, rice"), "no_restrictions", ["dairy"])
    assert allowed is True and reason is None
    allowed, reason = recommendation_eligibility(Food(name="Coconut rice with butter", category="meal", ingredients="coconut milk, rice, butter"), "no_restrictions", ["dairy"])
    assert allowed is False and "allergy" in reason
    assert recommendation_eligibility(Food(name="Vegan gummies", category="snack", ingredients="fruit juice, gelatin"), "vegan", [])[0] is False
    allowed, reason = recommendation_eligibility(Food(name="Uncertified meal", category="meal", ingredients="rice"), "halal", [])
    assert allowed is False and "cannot be verified" in reason


def test_daily_recommendations_respect_user_ownership_and_preferences():
    with TestClient(__import__("backend.app.main", fromlist=["app"]).app) as owner, TestClient(__import__("backend.app.main", fromlist=["app"]).app) as other:
        register(owner)
        register(other)
        headers = {"origin": "http://localhost:5173", "x-csrf-token": owner.cookies["lf_csrf"]}
        owner.put("/api/v1/users/preferences", headers=headers, json={"diet": "vegan", "allergies": ["peanuts"], "timezone": "UTC", "units": "metric"})
        safe = owner.post("/api/v1/foods", headers=headers, json={"name": "Owner lentil bowl", "ingredients": "lentils, water, herbs", "kcal": 120, "protein": 8, "carbs": 20, "fat": 1}).json()
        owner.post("/api/v1/foods", headers=headers, json={"name": "Peanut tofu bowl", "ingredients": "tofu, peanut sauce", "kcal": 150, "protein": 10})
        owner.post("/api/v1/foods", headers=headers, json={"name": "Unknown ingredient bowl", "kcal": 150, "protein": 10})
        private = other.post("/api/v1/foods", headers={"origin": "http://localhost:5173", "x-csrf-token": other.cookies["lf_csrf"]}, json={"name": "Other private lentils", "ingredients": "lentils, water", "kcal": 110, "protein": 9}).json()
        response = owner.get("/api/v1/recommendations/daily")
        assert response.status_code == 200
        result = response.json()
        names = {item["name"] for item in result["items"]}
        assert "Owner lentil bowl" in names
        assert "Peanut tofu bowl" not in names
        assert "Unknown ingredient bowl" not in names
        assert "Other private lentils" not in names
        assert private["id"] not in {item["food_id"] for item in result["items"]}
        assert "cannot confirm any food is safe" in result["caution"]
        assert result["items"][0]["source"] == "User provided"
        invalid = owner.put("/api/v1/users/preferences", headers=headers, json={"diet": "vegan", "allergies": None, "timezone": "UTC", "units": "metric"})
        if invalid.status_code == 200:
            assert owner.get("/api/v1/recommendations/daily").status_code == 200
