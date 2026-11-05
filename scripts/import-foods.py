"""Import pinned USDA Foundation Foods and FNDDS releases into the catalogue."""
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, delete

from backend.app.food_import import normalize_foundation_food
from backend.app.main import Food, FoodServing, SessionLocal

FOUNDATION_RELEASE = "October 2026"
FOUNDATION_ARCHIVE = "FoodData_Central_foundation_food_json_2026-10-29.zip"
FOUNDATION_SHA256 = "dd414cc9f1a132626bad354ef6655972c78b44aff14f16114dc899708663c579"
SURVEY_RELEASE = "2021-2023 (October 2024)"
SURVEY_ARCHIVE = "FoodData_Central_survey_food_json_2024-10-31.zip"
SURVEY_SHA256 = "dfb06ae7ddc397ccd570b91c14b75438ab2ba39f64f22d321f61d4a52a77f3eb"
MAX_ARCHIVE_BYTES = 5_000_000
MAX_JSON_BYTES = 70_000_000


def archive_path(name: str, checksum: str) -> Path:
    path = Path(__file__).resolve().parent.parent / ".local" / "cache" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with urlopen("https://fdc.nal.usda.gov/fdc-datasets/" + name, timeout=30) as response:
            data = response.read(MAX_ARCHIVE_BYTES + 1)
        if len(data) > MAX_ARCHIVE_BYTES:
            raise ValueError(f"USDA archive {name} exceeded its download limit")
        path.write_bytes(data)
    data = path.read_bytes()
    if len(data) > MAX_ARCHIVE_BYTES or hashlib.sha256(data).hexdigest() != checksum:
        raise ValueError(f"USDA archive {name} failed its pinned SHA-256 check")
    return path


def load_records(path: Path, internal_name: str, key: str) -> list[dict]:
    with ZipFile(path) as archive:
        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
        if len(entries) != 1 or entries[0].file_size > MAX_JSON_BYTES or entries[0].filename != internal_name:
            raise ValueError("Unexpected USDA archive layout or extracted size")
        document = json.loads(archive.read(entries[0]))
    records = document.get(key) if isinstance(document, dict) else None
    if not isinstance(records, list) or not records or len(records) > 10000:
            raise ValueError(f"USDA {internal_name} data file is missing or invalid")
    return records


def same_values(food: Food, imported: dict) -> bool:
    fields = ("name", "state", "category", "verification", "source", "source_record_id", "source_url", "nutrition_basis", "nutrition_provenance", "data_notes", "kcal", "protein", "carbs", "fat")
    return all(getattr(food, key) == imported[key] for key in fields)


def main() -> int:
    datasets = [
        (load_records(archive_path(FOUNDATION_ARCHIVE, FOUNDATION_SHA256), "FoodData_Central_foundation_food_json_2026-10-29.json", "FoundationFoods"), "Foundation", FOUNDATION_RELEASE),
        (load_records(archive_path(SURVEY_ARCHIVE, SURVEY_SHA256), "surveyDownload.json", "SurveyFoods"), "Survey", SURVEY_RELEASE),
    ]
    created = updated = excluded_nutrients = 0
    seen: set[str] = set()
    with SessionLocal() as session:
        try:
            existing_foods = {
                food.source_record_id: food
                for food in session.scalars(
                    select(Food).where(Food.owner_id.is_(None), Food.source_record_id.is_not(None))
                )
            }
            existing_servings: dict[int, list[FoodServing]] = {}
            if existing_foods:
                for serving in session.scalars(
                    select(FoodServing).where(FoodServing.food_id.in_([food.id for food in existing_foods.values()]))
                ):
                    existing_servings.setdefault(serving.food_id, []).append(serving)
            prepared: list[tuple[Food, dict, bool]] = []
            for records, data_type, release in datasets:
              for record in records:
                imported = normalize_foundation_food(record, release, data_type)
                if imported["source_record_id"] in seen:
                    raise ValueError("The USDA release contains a duplicate FDC identifier")
                seen.add(imported["source_record_id"])
                for nutrient, limit in (("kcal", 10000), ("protein", 1000), ("carbs", 1000), ("fat", 1000)):
                    value = imported[nutrient]
                    if value is not None and value > limit:
                        raise ValueError(f"Out-of-range {nutrient} value in FDC record {imported['source_record_id']}")
                excluded_nutrients += sum(1 for value in imported["nutrition_provenance"].values() if value["status"] == "unavailable")
                food = existing_foods.get(imported["source_record_id"])
                is_new = food is None
                if is_new:
                    food = Food(owner_id=None, aliases=[], brand=None)
                    existing_foods[imported["source_record_id"]] = food
                    session.add(food)
                changed = is_new or not same_values(food, imported)
                if changed:
                    for field in ("name", "state", "category", "verification", "source", "source_record_id", "source_url", "nutrition_basis", "nutrition_provenance", "data_notes", "kcal", "protein", "carbs", "fat"):
                        setattr(food, field, imported[field])
                    if is_new:
                        created += 1
                    else:
                        updated += 1
                prepared.append((food, imported, changed))
                if len(prepared) % 500 == 0:
                    session.flush()
            session.flush()
            additions: list[FoodServing] = []
            changed_portion_ids: list[int] = []
            for food, imported, changed in prepared:
                existing = existing_servings.get(food.id, []) if food.id else []
                standard = next((item for item in existing if item.label == "100 g"), None)
                if not standard:
                    additions.append(FoodServing(food_id=food.id, label="100 g", grams=100.0, source="standard"))
                old_imported = {(item.label, item.grams) for item in existing if item.source == "USDA"}
                new_imported = {(item["label"], item["grams"]) for item in imported["servings"]}
                if changed or old_imported != new_imported:
                    if food.id and old_imported:
                        changed_portion_ids.append(food.id)
                    additions.extend(FoodServing(food_id=food.id, label=item["label"], grams=item["grams"], source="USDA") for item in imported["servings"])
            if changed_portion_ids:
                session.execute(delete(FoodServing).where(FoodServing.food_id.in_(changed_portion_ids), FoodServing.source == "USDA"))
            if additions:
                session.add_all(additions)
            session.commit()
        except Exception:
            session.rollback()
            raise
    print(f"USDA Foundation Foods ({FOUNDATION_RELEASE}) and FNDDS ({SURVEY_RELEASE}): {len(seen)} source records checked; {created} added, {updated} refreshed, {excluded_nutrients} invalid nutrient values withheld as unavailable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
