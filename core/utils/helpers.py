"""
SmartMeal utility functions
"""

from __future__ import annotations
import re
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
    s = re.sub(r"[()\[\],.;:]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def normalize_unit(token: str) -> str:
    """Map common unit variants to a canonical form."""
    t = token.lower().strip(".")
    return UNIT_ALIASES.get(t, t)

DESCRIPTORS = {
    "beaten", "chopped", "diced", "minced", "sliced", "crushed", "ground",
    "fresh", "large", "small", "medium", "optional", "boiled", "mashed",
    "drained", "washed", "prepared", "cooked", "baked", "fried"
}

def singularize(word: str) -> str:
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("oes"):
        return word[:-2]
    if word.endswith("s") and len(word) > 3:
        return word[:-1]
    return word


def normalize_ingredient(ingredient: str) -> str:
    s = normalize_text(ingredient)
    s = re.sub(r"\b\d+([./-]\d+)?\b", " ", s)
    s = re.sub(r"\b(c|lb|pkg|can|oz|g|kg|ml|l|cups?|tbsp|tsp)\b", " ", s)

    tokens = [normalize_unit(t) for t in s.split()]
    tokens = [t for t in tokens if t not in STOPWORDS and t not in DESCRIPTORS]

    NOISE = {"optional", "to", "taste", "and", "drain", "washed", "wash", "in", "no", "&", "m"}
    tokens = [t for t in tokens if t not in NOISE and len(t) > 1]

    s = " ".join(tokens)
    s = re.sub(r"\b(wash(ed)?|drain(ed)?)\b", "", s)
    s = re.sub(r"\bsauce\b", "", s)
    s = re.sub(r"\s+", " ", s).strip()


    if " of " in s and len(s.split()) > 5:
        s = s.split(" of ")[-1]


    if "salt" in s and "pepper" in s:
        s = "salt and pepper"

    tokens = [singularize(t) for t in s.split()]
    s = " ".join(tokens).strip()
    return s


def fuzzy_contains(a: str, b: str) -> bool:
    a_tokens = a.split()
    b_tokens = b.split()
    for t1 in a_tokens:
        for t2 in b_tokens:
            if t1 == t2:
                return True
            if t1 in t2 or t2 in t1:
                if len(t1) >= 4 or len(t2) >= 4:
                    return True
    return False


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
    """Score recipe based on goal alignment."""
    ingredients = recipe.get("ingredients", [])
    normalized = normalize_ingredients(ingredients)

    goal_key = goal.lower()
    keywords = set()
    for g, words in GOAL_KEYWORDS.items():
        if g in goal_key:
            keywords = words
            break

    if not keywords:
        return 0.0

    score = 0.0
    has_substantial_match = False

    for i, ing in enumerate(ingredients):
        ing_lower = ing.lower()

        for kw in keywords:
            if kw in ing_lower:
                # Check if this is a substantial use of the keyword
                is_minor = any(word in ing_lower for word in
                               ["broth", "bouillon", "cube", "powder", "soup", "stock"])
                is_substantial = any(word in ing_lower for word in
                                     ["breast", "thigh", "whole", "lb", "lbs", "pound",
                                      "cut up", "piece", "fillet", "drumstick"])

                if is_substantial:
                    has_substantial_match = True
                    position_bonus = 3.0 if i < 3 else 1.0
                    score += 10.0 * position_bonus
                elif not is_minor:
                    score += 2.0
                else:
                    score += 0.3

                break


    if not has_substantial_match and score > 0:
        score *= 0.1


    steps = recipe.get("steps", [])
    if len(steps) <= 3:
        score += 0.5

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
    pantry_norm = [normalize_ingredient(p) for p in (pantry or [])]
    all_ings = []
    for r in recipes:
        all_ings += normalize_ingredients(r.get("ingredients", []))

    unique = sorted({i for i in all_ings if i})
    need, have = [], []

    for ing in unique:
        ing_tokens = set(ing.split())
        matched = False
        for p in pantry_norm:
            p_tokens = set(p.split())
            if ing_tokens & p_tokens:
                matched = True
                break
        if matched:
            have.append(ing)
        else:
            need.append(ing)

    return {"need": need, "have": have}


# Serialization utilities

def to_jsonable(obj: Any) -> Any:
    from pydantic import BaseModel

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
