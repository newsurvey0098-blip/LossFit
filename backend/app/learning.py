"""Versioned, source-linked educational lessons shipped with LossFit."""

LESSONS = [
    {
        "slug": "read-a-food-label",
        "title": "Read a food label with confidence",
        "category": "Food basics",
        "minutes": 3,
        "version": 1,
        "summary": "Start with serving information, then use % Daily Value as a comparison tool.",
        "simple": "The numbers on a Nutrition Facts label are for the listed serving. If you eat two servings, the calories and nutrients shown are doubled. %DV helps you compare how much one serving contributes to a daily reference amount.",
        "detailed": "Check servings per container and serving size first: these describe the basis for the label, not a recommended portion. Nutrient amounts and % Daily Values refer to that serving. FDA’s general guide treats 5% DV or less as low and 20% DV or more as high for a nutrient in one serving. Use %DV to compare similar products with comparable serving sizes, while considering your own dietary needs.",
        "sources": [{"title": "How to Understand and Use the Nutrition Facts Label", "organization": "U.S. Food and Drug Administration", "url": "https://www.fda.gov/food/nutrition-facts-label/how-understand-and-use-nutrition-facts-label", "version": "Reviewed 2026-11-06"}],
        "quiz": {"question": "A package lists nutrition for one serving. You eat two servings. What should you do with the listed calorie and nutrient amounts?", "options": ["Use the amounts as listed", "Multiply the amounts by two", "Divide the amounts by two"], "answer": 1, "explanation": "The label’s amounts refer to its serving size, so two servings provide twice the listed amount."},
    },
    {
        "slug": "hydration-basics",
        "title": "Hydration without a one-size-fits-all target",
        "category": "Daily habits",
        "minutes": 2,
        "version": 1,
        "summary": "Fluid needs vary; water and water-rich foods both contribute.",
        "simple": "People do not all need the same amount of water. Weather, activity, health, and life stage can change fluid needs. Water-rich foods and other beverages also contribute to total water intake.",
        "detailed": "CDC describes daily water needs as varying with factors such as age, sex, pregnancy or breastfeeding status, and activity. Fluids come from water and other beverages, and foods—especially fruits and vegetables with high water content—also contribute. Heat, activity, fever, vomiting, or diarrhea can increase the need for fluids. LossFit’s hydration tracker records what you log; it does not measure hydration status or prescribe a clinical target.",
        "sources": [{"title": "About Water and Healthier Drinks", "organization": "U.S. Centers for Disease Control and Prevention", "url": "https://www.cdc.gov/healthy-weight-growth/water-healthy-drinks/", "version": "Reviewed 2026-11-06"}],
        "quiz": {"question": "Which statement best reflects general guidance about daily water needs?", "options": ["The same fixed amount is right for everyone", "Needs vary, and foods and beverages contribute to total fluid intake", "Only plain water counts toward fluid intake"], "answer": 1, "explanation": "CDC notes that needs vary and that total water comes from beverages and foods."},
    },
    {
        "slug": "movement-and-health",
        "title": "Movement can add up over the week",
        "category": "Daily habits",
        "minutes": 3,
        "version": 1,
        "summary": "Regular activity supports health, and activity does not need to happen all at once.",
        "simple": "The CDC says adults benefit from regular activity. The weekly guideline can be spread across the week; some activity is better than none. Choose movement that fits your abilities and circumstances.",
        "detailed": "For adults, CDC guidance describes at least 150 minutes of moderate-intensity aerobic activity weekly (or 75 minutes vigorous, or an equivalent combination) and muscle-strengthening activity on at least two days. Activity can be spread across the week, and adults who sit less and do any amount of moderate- or vigorous-intensity activity gain some health benefits. These are population-level guidelines, not an individualized exercise prescription.",
        "sources": [{"title": "Adult Activity: An Overview", "organization": "U.S. Centers for Disease Control and Prevention", "url": "https://www.cdc.gov/physical-activity-basics/guidelines/adults.html", "version": "Reviewed 2026-11-06"}],
        "quiz": {"question": "Which statement matches CDC guidance for adults?", "options": ["Activity must be completed in one long session", "Adults can gain some benefits from doing any amount of moderate-to-vigorous activity", "Only vigorous exercise counts"], "answer": 1, "explanation": "CDC states that adults who sit less and do any amount of moderate- or vigorous-intensity activity gain some health benefits."},
    },
]

LESSON_BY_SLUG = {lesson["slug"]: lesson for lesson in LESSONS}


def public_lesson(lesson: dict, *, detailed: bool = False) -> dict:
    """Return learner content without the answer key."""
    return {
        key: value for key, value in lesson.items() if key != "quiz"
    } | {
        "content": lesson["detailed"] if detailed else lesson["simple"],
        "quiz": {key: value for key, value in lesson["quiz"].items() if key != "answer"},
    }
