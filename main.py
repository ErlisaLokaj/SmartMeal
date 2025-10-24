from core.services.user_service import get_user_info
from core.services.recipe_service import find_recipes
from core.services.planner_service import generate_plan

def main():
    print("=== SMARTMEAL DEMO ===")
    user = get_user_info("Anna")
    recipes = find_recipes("chicken")
    plan = generate_plan(user, recipes)

    print("\nUser:", user)
    print("\nRecipes found:", recipes["recipes"])
    print("Substitutes:", recipes["alternatives"])
    print("\nGenerated Weekly Plan:", plan)

if __name__ == "__main__":
    main()
