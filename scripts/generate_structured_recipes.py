#!/usr/bin/env python3
"""Transform simple recipes into structured format.

Reads recipes_clean.json and converts them to the structured schema.
Uses basic heuristics and defaults for missing data.
"""

import sys
import json
import re
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.schemas.recipe_schemas import RecipeCreate, SimpleIngredient, SimpleStep


def parse_ingredient(ingredient_text):
    """Parse ingredient string into structured format.

    Examples:
        "1 c. firmly packed brown sugar" -> (1, "cup", "brown sugar", "firmly packed")
        "1/2 tsp. vanilla" -> (0.5, "tsp", "vanilla", "")
        "2 Tbsp. butter or margarine" -> (2, "tbsp", "butter or margarine", "")
    """
    # Common unit mappings
    unit_map = {
        "c.": "cup",
        "c": "cup",
        "cup": "cup",
        "cups": "cup",
        "tbsp.": "tbsp",
        "tbsp": "tbsp",
        "tablespoon": "tbsp",
        "tablespoons": "tbsp",
        "tsp.": "tsp",
        "tsp": "tsp",
        "teaspoon": "tsp",
        "teaspoons": "tsp",
        "oz.": "oz",
        "oz": "oz",
        "ounce": "oz",
        "ounces": "oz",
        "lb.": "lb",
        "lb": "lb",
        "lbs": "lb",
        "pound": "lb",
        "pounds": "lb",
        "g": "g",
        "gram": "g",
        "grams": "g",
        "kg": "kg",
        "kilogram": "kg",
        "ml": "ml",
        "milliliter": "ml",
        "l": "l",
        "liter": "l",
    }

    # Try to match: quantity + unit + ingredient name
    # Pattern: number (with fractions) + optional unit + rest
    pattern = r"^([\d\/\.\s]+)\s*([a-zA-Z\.]+)?\s+(.+)$"
    match = re.match(pattern, ingredient_text.strip())

    if match:
        qty_str, unit_str, name = match.groups()

        # Parse quantity (handle fractions like "1/2")
        try:
            if "/" in qty_str:
                parts = qty_str.strip().split()
                if len(parts) == 2:  # "1 1/2"
                    whole = float(parts[0])
                    frac = parts[1].split("/")
                    quantity = whole + float(frac[0]) / float(frac[1])
                else:  # "1/2"
                    frac = qty_str.strip().split("/")
                    quantity = float(frac[0]) / float(frac[1])
            else:
                quantity = float(qty_str.strip())
        except:
            quantity = 1.0

        # Normalize unit
        unit = unit_map.get(unit_str.lower() if unit_str else "", "unit")

        # Clean up name
        name = name.strip()

        # Check for prep notes in parentheses
        prep_note = ""
        paren_match = re.search(r"\(([^)]+)\)", name)
        if paren_match:
            prep_note = paren_match.group(1)
            name = re.sub(r"\s*\([^)]+\)", "", name).strip()

        return SimpleIngredient(
            name=name, quantity=quantity, unit=unit, prep_note=prep_note
        )
    else:
        # Couldn't parse, use defaults
        return SimpleIngredient(
            name=ingredient_text.strip(), quantity=1, unit="unit", prep_note=""
        )


def infer_cuisine(title, ingredients):
    """Infer cuisine type from recipe title and ingredients."""
    title_lower = title.lower()
    ingredients_text = " ".join(ingredients).lower()

    # Simple keyword matching
    if any(
        word in title_lower for word in ["pasta", "spaghetti", "italian", "parmesan"]
    ):
        return "Italian"
    if any(word in title_lower for word in ["taco", "burrito", "mexican", "salsa"]):
        return "Mexican"
    if any(word in title_lower for word in ["stir-fry", "wok", "soy sauce", "asian"]):
        return "Asian"
    if any(
        word in title_lower or word in ingredients_text
        for word in ["curry", "garam", "indian"]
    ):
        return "Indian"
    if any(word in title_lower for word in ["french", "croissant", "baguette"]):
        return "French"

    return "International"


def infer_tags(title, ingredients, steps):
    """Infer tags from recipe content."""
    tags = []
    title_lower = title.lower()
    ingredients_text = " ".join(ingredients).lower()
    steps_text = " ".join(steps).lower()

    # Meal type
    if any(word in title_lower for word in ["breakfast", "oats", "pancake"]):
        tags.append("breakfast")
    if any(word in title_lower for word in ["lunch", "sandwich", "salad"]):
        tags.append("lunch")
    if any(word in title_lower for word in ["dinner", "supper"]):
        tags.append("dinner")
    if any(word in title_lower for word in ["dessert", "cookie", "cake", "pie"]):
        tags.append("dessert")

    # Dietary
    if (
        "chicken" not in ingredients_text
        and "beef" not in ingredients_text
        and "pork" not in ingredients_text
        and "meat" not in ingredients_text
    ):
        tags.append("vegetarian")

    # Cooking method
    if "no-bake" in title_lower or "no bake" in title_lower:
        tags.append("no-bake")
    if "grill" in steps_text or "bbq" in title_lower:
        tags.append("grilled")
    if "bake" in steps_text and "no-bake" not in title_lower:
        tags.append("baked")

    # Speed
    total_time = sum(1 for step in steps if len(step) < 100)  # rough estimate
    if total_time <= 3:
        tags.append("quick")

    # Default if no tags
    if not tags:
        tags.append("main-dish")

    return tags


def infer_servings(title, ingredients, steps):
    """Try to infer serving size from text."""
    # Look for numbers in steps like "serves 4" or "makes 12 cookies"
    all_text = title + " " + " ".join(ingredients) + " " + " ".join(steps)

    serve_match = re.search(r"serves?\s+(\d+)", all_text, re.IGNORECASE)
    if serve_match:
        return int(serve_match.group(1))

    makes_match = re.search(r"makes?\s+(\d+)", all_text, re.IGNORECASE)
    if makes_match:
        return int(makes_match.group(1))

    # Default
    return 4


def estimate_nutrition(servings, ingredients):
    """Very rough nutrition estimation based on ingredient count and servings."""
    # This is a placeholder - real nutrition would require a database
    base_kcal = len(ingredients) * 100  # rough estimate
    return {
        "kcal": base_kcal // servings,
        "protein_g": 15.0,
        "carb_g": 30.0,
        "fat_g": 10.0,
    }


def transform_recipe(simple_recipe):
    """Transform a simple recipe dict into RecipeCreate model."""
    title = simple_recipe.get("name", "Untitled Recipe")
    ingredients_raw = simple_recipe.get("ingredients", [])
    steps_raw = simple_recipe.get("steps", [])

    # Parse ingredients
    ingredients = [parse_ingredient(ing) for ing in ingredients_raw]

    # Infer metadata
    cuisine = infer_cuisine(title, ingredients_raw)
    tags = infer_tags(title, ingredients_raw, steps_raw)
    servings = infer_servings(title, ingredients_raw, steps_raw)

    # Create steps (estimate 5 min per step if not specified)
    steps = [SimpleStep(text=step_text, duration_min=5) for step_text in steps_raw]

    # Estimate nutrition
    nutrition = estimate_nutrition(servings, ingredients)

    # Create RecipeCreate object
    return RecipeCreate(
        title=title,
        cuisine=cuisine,
        tags=tags,
        servings=servings,
        ingredients=ingredients,
        steps=steps,
        **nutrition,
    )


def main():
    """Main transformation logic."""
    # Read input file
    input_file = Path(__file__).parent.parent / "data" / "recipes_clean.json"
    output_file = Path(__file__).parent.parent / "data" / "recipes_structured.json"

    if not input_file.exists():
        print(f"Input file not found: {input_file}")
        sys.exit(1)

    print(f"Reading {input_file}")
    with open(input_file, "r") as f:
        simple_recipes = json.load(f)

    print(f"Transforming {len(simple_recipes)} recipes...")

    # Transform all recipes
    structured_recipes = []
    errors = []

    for idx, simple_recipe in enumerate(simple_recipes, 1):
        try:
            recipe_create = transform_recipe(simple_recipe)
            recipe = recipe_create.to_recipe()
            recipe_dict = recipe.model_dump(by_alias=True, mode="json")
            structured_recipes.append(recipe_dict)

            if idx % 50 == 0:
                print(f"  Processed {idx}/{len(simple_recipes)}...")
        except Exception as e:
            errors.append((idx, simple_recipe.get("name", "Unknown"), str(e)))

    # Write output
    print(f" Writing {len(structured_recipes)} recipes to {output_file}")
    with open(output_file, "w") as f:
        json.dump(structured_recipes, f, indent=2, default=str)

    # Summary
    print("\n" + "=" * 60)
    print(f"Successfully transformed: {len(structured_recipes)} recipes")
    if errors:
        print(f"Errors: {len(errors)} recipes")
        print("\nFirst 5 errors:")
        for idx, name, error in errors[:5]:
            print(f"  #{idx}: {name} - {error}")
    print("=" * 60)


if __name__ == "__main__":
    main()
