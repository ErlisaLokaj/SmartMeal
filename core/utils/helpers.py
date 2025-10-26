"""
SmartMeal utility functions
"""

from __future__ import annotations
from typing import Iterable, List, Dict, Any, Tuple, Optional


# Text & ingredient utilities

STOPWORDS = {"fresh", "chopped", "diced", "minced", "ground", "large", "small",
             "cup", "cups", "tbsp", "tablespoon", "tablespoons", "tsp", "teaspoon",
             "teaspoons", "ounce", "ounces", "oz", "gram", "grams", "ml", "ltr",
             "package", "packages", "can", "cans"}

UNIT_ALIASES = {
    "tbs": "tbsp", "tbl": "tbsp", "tbls": "tbsp", "tablespoons": "tbsp",
    "teaspoons": "tsp", "tsps": "tsp", "ts": "tsp",
    "oz.": "oz", "g.": "g",
}

def normalize_text(s: str) -> str:
    """Basic normalization: lowercase, collapse spaces, strip punctuation edges."""
    import re
    s = s.lower().strip()
    s = re.sub(r"[()\[\],.;:]+", " ", s)  # light punctuation removal
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def normalize_unit(token: str) -> str:
    """Map common unit variants to a canonical form."""
    t = token.lower().strip(".")
    return UNIT_ALIASES.get(t, t)

def normalize_ingredient(ingredient: str) -> str:
    """
    Normalize a single ingredient string:
    - lowercase
    - remove obvious quantities/units
    - drop simple descriptors
    """
    import re
    s = normalize_text(ingredient)

    # remove obvious numeric quantities like "2", "1/2", "3-4", "250g", "10 oz"
    s = re.sub(r"\b\d+([./-]\d+)?\b", " ", s)         # 2, 1/2, 3-4
    s = re.sub(r"\b\d+\s?(oz|g|kg|ml|l|cups?|tbsp|tsp)\b", " ", s)

    # strip unit aliases to reduce noise
    tokens = [normalize_unit(t) for t in s.split()]
    tokens = [t for t in tokens if t not in STOPWORDS]

    # heuristic: drop trailing noise words like "optional", "to", "taste"
    NOISE = {"optional", "to", "taste"}
    tokens = [t for t in tokens if t not in NOISE]

    return " ".join(tokens).strip()

def normalize_ingredients(ingredients: Iterable[str]) -> List[str]:
    """Normalize a list of ingredient strings."""
    return [normalize_ingredient(i) for i in ingredients if i and i.strip()]

def contains_ingredient(needle: str, haystack_ingredients: Iterable[str]) -> bool:
    """Case/format-insensitive 'ingredient in list' check using normalization."""
    n = normalize_ingredient(needle)
    return any(n == normalize_ingredient(h) or n in normalize_ingredient(h) for h in haystack_ingredients)


# Recipe ranking & selection

GOAL_KEYWORDS = {
    "high protein": {"chicken", "egg", "eggs", "beef", "tofu", "tempeh", "yogurt", "lentil", "lentils", "beans"},
    "low carb": {"cauliflower", "zucchini", "egg", "eggs", "chicken", "fish", "steak", "tofu"},
    "vegan": {"tofu", "tempeh", "bean", "beans", "lentil", "lentils", "seitan"},
}

def score_recipe_against_goal(recipe: Dict[str, Any], goal: str) -> float:
    """
    Tiny heuristic scorer:
    +1 for each goal keyword found in ingredients (normalized)
    slight bonus for shorter steps (simplicity)
    """
    ingredients = normalize_ingredients(recipe.get("ingredients", []))
    goal_key = goal.lower()
    # map goal to a keyword set
    keywords = set()
    for g, words in GOAL_KEYWORDS.items():
        if g in goal_key:
            keywords = words
            break

    score = 0.0
    if keywords:
        for ing in ingredients:
            for kw in keywords:
                if kw in ing:
                    score += 1.0

    steps = recipe.get("steps", [])
    if steps:
        # fewer steps → slightly higher score (ease of cooking)
        score += max(0.0, 5.0 - min(5.0, len(steps))) * 0.1

    # cap/normalize (not strictly necessary)
    return float(score)

def rank_recipes(recipes: List[Dict[str, Any]], goal: str, top_n: int = 10) -> List[Dict[str, Any]]:
    """Return top_n recipes sorted by score (desc)."""
    scored = [(score_recipe_against_goal(r, goal), r) for r in recipes]
    scored.sort(key=lambda t: t[0], reverse=True)
    return [r for _, r in scored[:top_n]]

def safe_sample(items: List[Any], n: int) -> List[Any]:
    """Return at most n items without error; preserves order."""
    return items[: max(0, min(n, len(items)))]


# Shopping list helpers

def build_shopping_list(recipes: List[Dict[str, Any]], pantry: Optional[Iterable[str]] = None) -> Dict[str, List[str]]:
    """
    Create a basic shopping list from selected recipes.
    - Normalizes ingredient names
    - Dedupes
    - Splits into 'need' vs 'have' using an optional pantry list
    """
    pantry_norm = set(normalize_ingredient(p) for p in (pantry or []))
    all_ings = []
    for r in recipes:
        all_ings += normalize_ingredients(r.get("ingredients", []))

    unique = sorted({i for i in all_ings if i})
    need = [i for i in unique if i not in pantry_norm]
    have = [i for i in unique if i in pantry_norm]

    return {"need": need, "have": have}


# Serialization utilities

def to_jsonable(obj: Any) -> Any:
    """
    Convert common SmartMeal objects to JSON-serializable types.
    Works with dicts, lists, Pydantic models, and simple domain models exposing .to_dict().
    """
    from pydantic import BaseModel  # local import to avoid hard dependency at import time

    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        return obj.to_dict()
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    return str(obj)


# Pagination

def paginate(items: List[Any], page: int = 1, size: int = 10) -> Tuple[List[Any], Dict[str, int]]:
    """Return a slice of items with pagination metadata."""
    page = max(1, int(page))
    size = max(1, int(size))
    start = (page - 1) * size
    end = start + size
    data = items[start:end]
    meta = {"page": page, "size": size, "total": len(items), "pages": (len(items) + size - 1) // size}
    return data, meta
