import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from backend.app import main
from backend.app.branded_catalog import normalize_branded_food, normalize_search_hit
from backend.app.main import app


def register(client):
    suffix = uuid4().hex
    response = client.post("/api/v1/auth/register", json={"name": "Test User", "email": f"{suffix}@gmail.com", "password": "safe-password-987"})
    assert response.status_code == 201
    user = response.json()
    client.headers.update({"Authorization": f"Bearer {user['access_token']}"})
    return user


def sample_record():
    return {
        "fdcId": 123456,
        "dataType": "Branded",
        "description": "Unsweetened oat drink",
        "brandName": "North Farm",
        "brandOwner": "North Farm Foods",
        "foodCategory": {"description": "Plant-based beverages"},
        "servingSize": 240,
        "servingSizeUnit": "g",
        "householdServingFullText": "1 cup",
        "foodNutrients": [
            {"nutrient": {"id": 1008, "unitName": "kcal"}, "amount": 42},
            {"nutrient": {"id": 1003, "unitName": "g"}, "amount": 1.2},
            {"nutrient": {"id": 1005, "unitName": "g"}, "amount": 6.5},
            {"nutrient": {"id": 1004, "unitName": "g"}, "amount": 1.5},
        ],
    }


def test_branded_normalization_retains_missing_values_and_gram_serving():
    record = sample_record()
    record["foodNutrients"] = [
        {"nutrient": {"id": 1008, "unitName": "kcal"}, "amount": 0},
        {"nutrient": {"id": 1003, "unitName": "g"}, "amount": -1},
    ]
    normalized = normalize_branded_food(record)
    assert normalized["kcal"] == 0
    assert normalized["protein"] is None
    assert normalized["nutrition_provenance"]["protein"]["status"] == "unavailable"
    assert normalized["carbs"] is None
    assert normalized["servings"] == [{"label": "1 cup", "grams": 240.0}]
    assert normalized["source_record_id"] == "123456"


def test_branded_search_result_validates_type_and_uses_safe_package_weight():
    hit = normalize_search_hit(sample_record())
    assert hit["fdc_id"] == 123456
    assert hit["package_serving"] == "240 g"
    assert hit["nutrients"]["kcal"] == 42
    bad = sample_record()
    bad["dataType"] = "Foundation"
    with pytest.raises(ValueError):
        normalize_search_hit(bad)


def test_branded_import_rejects_non_ascii_ids_and_does_not_convert_volume_to_grams():
    record = sample_record()
    record["fdcId"] = "١٢٣٤٥٦"
    with pytest.raises(ValueError):
        normalize_branded_food(record)
    record = sample_record()
    record["servingSizeUnit"] = "ml"
    normalized = normalize_branded_food(record)
    assert normalized["servings"] == []


def test_branded_status_does_not_expose_api_key(monkeypatch):
    monkeypatch.delenv("FDC_API_KEY", raising=False)
    with TestClient(app) as client:
        register(client)
        status = client.get("/api/v1/food-sources/usda-branded/status")
        assert status.status_code == 200
        assert status.json()["available"] is False
        assert "FDC_API_KEY" in status.json()["message"]


def test_branded_search_and_private_import_persist_source_snapshots(monkeypatch):
    monkeypatch.setenv("FDC_API_KEY", "server-only-test-secret")
    record = sample_record()
    calls = []

    def fake_request(path, *, params, body=None):
        calls.append((path, body))
        return {"foods": [record]} if path == "foods/search" else record

    monkeypatch.setattr(main, "fdc_json_request", fake_request)
    with TestClient(app) as owner, TestClient(app) as other:
        register(owner)
        register(other)
        hits = owner.get("/api/v1/food-sources/usda-branded/search?q=oat%20drink")
        assert hits.status_code == 200
        assert hits.json()[0]["fdc_id"] == 123456
        assert calls[0][1]["dataType"] == ["Branded"]
        csrf = owner.cookies["lf_csrf"]
        headers = {"origin": "http://localhost:5173", "x-csrf-token": csrf}
        imported = owner.post("/api/v1/food-sources/usda-branded/123456/import", headers=headers)
        assert imported.status_code == 201
        food = imported.json()
        assert food["brand"] == "North Farm"
        assert food["verification"] == "imported"
        assert food["nutrition_provenance"]["kcal"]["status"] == "imported"
        assert owner.get(f"/api/v1/foods/{food['id']}").status_code == 200
        assert other.get(f"/api/v1/foods/{food['id']}").status_code == 404
        meal = owner.post("/api/v1/meals", headers=headers, json={"name": "Oat drink", "meal_type": "snack", "items": [{"food_id": food["id"], "grams": 120}]}).json()
        assert meal["items"][0]["source_record_id"] == "123456"
        assert meal["items"][0]["per100"]["kcal"] == 42
        repeated = owner.post("/api/v1/food-sources/usda-branded/123456/import", headers=headers)
        assert repeated.status_code == 201 and repeated.json()["id"] == food["id"]
        assert len([path for path, _ in calls if path == "food/123456"]) == 1
        assert owner.delete(f"/api/v1/foods/{food['id']}", headers=headers).status_code == 204
        assert owner.get(f"/api/v1/meals/{meal['id']}").json()["items"][0]["source_record_id"] == "123456"


def test_branded_search_fails_closed_without_credentials_or_on_provider_outage(monkeypatch):
    monkeypatch.delenv("FDC_API_KEY", raising=False)
    with TestClient(app) as client:
        register(client)
        missing = client.get("/api/v1/food-sources/usda-branded/search?q=oats")
        assert missing.status_code == 503
        assert "barcode" in missing.json()["detail"]
    monkeypatch.setenv("FDC_API_KEY", "server-only-test-secret")

    def outage(*args, **kwargs):
        raise main.HTTPException(503, "USDA Branded food lookup is temporarily unavailable. Try again later.")

    monkeypatch.setattr(main, "fdc_json_request", outage)
    with TestClient(app) as client:
        register(client)
        assert client.get("/api/v1/food-sources/usda-branded/search?q=oats").status_code == 503
