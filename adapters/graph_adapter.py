def get_substitute(ingredient: str):
    substitutes = {
        "chicken": ["tofu", "tempeh"],
        "rice": ["quinoa"],
        "milk": ["soy milk", "almond milk"]
    }
    return substitutes.get(ingredient.lower(), [])
