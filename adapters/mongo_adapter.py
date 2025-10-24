def search_recipes(ingredient: str):
    mock_recipes = [
        {"name": "Grilled Chicken Bowl", "ingredients": ["chicken", "rice", "broccoli"]},
        {"name": "Vegan Curry", "ingredients": ["tofu", "coconut milk", "spinach"]},
        {"name": "Chicken Pasta", "ingredients": ["chicken", "pasta", "tomato"]}
    ]
    return [r["name"] for r in mock_recipes if ingredient.lower() in [i.lower() for i in r["ingredients"]]]
